import json
from collections.abc import Iterator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

import pytest
from app.deployments import DeployError, DeployProviderResult, DeployService
from app.main import app, get_db
from app.models import (
    Agent,
    Artifact,
    Deployment,
    Preview,
    Session,
    Task,
    TaskRun,
    TaskRunEvent,
    Workspace,
)


def db_fixture() -> Iterator[DbSession]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with DbSession(engine) as session:
        yield session


def create_preview_fixture(db: DbSession, worktree_path: Path) -> tuple[str, str]:
    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="Deploy session",
        bound_branch="main",
        worktree_path=str(worktree_path),
    )
    agent = Agent(
        name="Frontend Agent",
        role="frontend",
        adapter_type="scripted_mock",
        provider="local",
    )
    task = Task(
        session_id=session.id,
        title="Build login page",
        intent_type="frontend_change",
        assigned_agent_id=agent.id,
    )
    task_run = TaskRun(
        task_id=task.id,
        agent_id=agent.id,
        state="completed",
        worktree_path=session.worktree_path,
        base_ref="abc123",
        head_ref="def456+worktree",
    )
    preview_artifact = Artifact(
        task_run_id=task_run.id,
        artifact_type="preview",
        title="Vite React preview",
        status="ready",
    )
    preview = Preview(
        artifact_id=preview_artifact.id,
        port=4317,
        url="http://127.0.0.1:4317",
        command="pnpm dev --host 127.0.0.1 --port 4317",
        process_id=4242,
        health_status="healthy",
    )
    db.add(workspace)
    db.add(session)
    db.add(agent)
    db.add(task)
    db.add(task_run)
    db.add(preview_artifact)
    db.add(preview)
    db.commit()
    db.refresh(task_run)
    db.refresh(preview)
    return preview.id, task_run.id


def test_mock_deploy_persists_deployment_artifact_and_ready_event(tmp_path: Path) -> None:
    with next(db_fixture()) as db:
        preview_id, task_run_id = create_preview_fixture(db, tmp_path / "session-worktree")
        service = DeployService()

        stored = service.create_mock_deployment(db, preview_id)

        deployment = db.get(Deployment, stored.id)
        artifact = db.get(Artifact, stored.artifact_id)
        event = db.exec(
            select(TaskRunEvent).where(
                TaskRunEvent.task_run_id == task_run_id,
                TaskRunEvent.event_type == "artifact.deploy.ready",
            )
        ).one()

        assert deployment is not None
        assert artifact is not None
        assert artifact.task_run_id == task_run_id
        assert artifact.artifact_type == "deployment"
        assert artifact.status == "ready"
        assert deployment.provider == "mock"
        assert deployment.environment == "preview"
        assert deployment.commit_sha == "def456+worktree"
        assert deployment.url == f"https://mock.agenthub.local/deployments/{deployment.id}"
        assert deployment.deploy_log_uri == f"mock://deployments/{deployment.id}/logs"
        assert json.loads(event.payload_json)["deploymentId"] == deployment.id


def test_deploy_provider_result_records_standard_metadata(tmp_path: Path) -> None:
    with next(db_fixture()) as db:
        preview_id, _ = create_preview_fixture(db, tmp_path / "session-worktree")
        service = DeployService()

        stored = service.create_deployment(db, preview_id, provider_id="mock")
        artifact = db.get(Artifact, stored.artifact_id)

        assert artifact is not None
        metadata = json.loads(artifact.meta_json)
        provider_result = metadata["providerResult"]

        assert provider_result["providerId"] == "mock"
        assert provider_result["providerType"] == "mock"
        assert provider_result["targetId"] == "demo-frontend"
        assert provider_result["buildCommand"] is None
        assert provider_result["deployCommand"] == "mock deploy preview"
        assert provider_result["outputUrl"] == stored.url
        assert provider_result["status"] == "ready"
        assert provider_result["logs"]


def test_deploy_service_rejects_unknown_provider(tmp_path: Path) -> None:
    with next(db_fixture()) as db:
        preview_id, _ = create_preview_fixture(db, tmp_path / "session-worktree")
        service = DeployService()

        with pytest.raises(DeployError, match="Unknown deploy provider"):
            service.create_deployment(db, preview_id, provider_id="missing-provider")


def test_deploy_service_rejects_failed_provider_result_without_success_artifact(
    tmp_path: Path,
) -> None:
    class FailedProvider:
        provider_id = "failed-provider"
        provider_type = "test"

        def deploy(
            self,
            *,
            preview: Preview,
            task_run: TaskRun,
            deployment_id: str,
        ) -> DeployProviderResult:
            return DeployProviderResult(
                provider_id=self.provider_id,
                provider_type=self.provider_type,
                target_id="demo-frontend",
                build_command=None,
                deploy_command="fail deliberately",
                output_url=None,
                status="failed",
                logs=("provider failed deliberately",),
                environment="staging",
            )

    with next(db_fixture()) as db:
        preview_id, _ = create_preview_fixture(db, tmp_path / "session-worktree")
        service = DeployService(providers=(FailedProvider(),))

        with pytest.raises(DeployError, match="failed-provider failed"):
            service.create_deployment(db, preview_id, provider_id="failed-provider")

        deployments = db.exec(select(Deployment)).all()
        artifacts = db.exec(select(Artifact).where(Artifact.artifact_type == "deployment")).all()
        assert deployments == []
        assert artifacts == []


def test_deploy_api_creates_and_lists_mock_deployments(tmp_path: Path) -> None:
    with next(db_fixture()) as db:
        preview_id, task_run_id = create_preview_fixture(db, tmp_path / "session-worktree")

        def override_db() -> Iterator[DbSession]:
            yield db

        app.dependency_overrides[get_db] = override_db
        try:
            client = TestClient(app)
            create_response = client.post(f"/previews/{preview_id}/deploy")
            list_response = client.get(f"/task-runs/{task_run_id}/deployments")
            task_run = db.get(TaskRun, task_run_id)
            assert task_run is not None
            task = db.get(Task, task_run.task_id)
            assert task is not None
            ledger_response = client.get(f"/sessions/{task.session_id}/ledger")
        finally:
            app.dependency_overrides.clear()

        assert create_response.status_code == 201
        assert list_response.status_code == 200
        assert ledger_response.status_code == 200
        assert create_response.json()["provider"] == "mock"
        assert create_response.json()["environment"] == "preview"
        assert create_response.json()["commitSha"] == "def456+worktree"
        assert list_response.json()[0]["url"].startswith("https://mock.agenthub.local/")
        assert ledger_response.json()["latestDeploymentId"] == create_response.json()["id"]
        assert ledger_response.json()["latestDeploymentProvider"] == "mock"
        assert ledger_response.json()["latestDeploymentStatus"] == "ready"


def test_mock_deploy_rejects_nonexistent_preview(tmp_path: Path) -> None:
    with next(db_fixture()) as db:
        service = DeployService()
        with pytest.raises(DeployError, match="Preview not found"):
            service.create_mock_deployment(db, "nonexistent-preview-id")


def test_mock_deploy_rejects_unhealthy_preview(tmp_path: Path) -> None:
    with next(db_fixture()) as db:
        preview_id, _ = create_preview_fixture(db, tmp_path / "session-worktree")
        preview = db.get(Preview, preview_id)
        assert preview is not None
        preview.health_status = "unhealthy"
        db.add(preview)
        db.commit()

        service = DeployService()
        with pytest.raises(DeployError, match="healthy preview"):
            service.create_mock_deployment(db, preview_id)


def test_mock_deploy_rejects_failed_task_run(tmp_path: Path) -> None:
    with next(db_fixture()) as db:
        preview_id, task_run_id = create_preview_fixture(db, tmp_path / "session-worktree")
        task_run = db.get(TaskRun, task_run_id)
        assert task_run is not None
        task_run.state = "failed"
        db.add(task_run)
        db.commit()

        service = DeployService()
        with pytest.raises(DeployError, match="completed TaskRun"):
            service.create_mock_deployment(db, preview_id)


def test_mock_deploy_rejects_failed_dependency_prerequisite(tmp_path: Path) -> None:
    with next(db_fixture()) as db:
        preview_id, task_run_id = create_preview_fixture(db, tmp_path / "session-worktree")
        task_run = db.get(TaskRun, task_run_id)
        assert task_run is not None
        task = db.get(Task, task_run.task_id)
        assert task is not None
        upstream = Task(
            session_id=task.session_id,
            title="Failed backend prerequisite",
            intent_type="backend_change",
            status="failed",
            assigned_agent_id=task.assigned_agent_id,
        )
        db.add(upstream)
        db.commit()
        db.refresh(upstream)
        task.depends_on_task_ids = json.dumps([upstream.id], separators=(",", ":"))
        db.add(task)
        db.commit()

        service = DeployService()
        with pytest.raises(DeployError, match="failed prerequisite"):
            service.create_mock_deployment(db, preview_id)
