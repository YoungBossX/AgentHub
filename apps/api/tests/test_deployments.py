import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Optional

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

import pytest
from app.deployments import (
    CommandResult,
    DeployError,
    DeployProviderResult,
    DeployService,
    LocalStagingDeployProvider,
    ManualExternalDeployProvider,
    MockDeployProvider,
    UnavailableExternalDeployProvider,
    StagingServerProcess,
    StaticDirectoryServer,
)
from app.main import app, get_db
from app.models import (
    Agent,
    Artifact,
    Deployment,
    Diff,
    Preview,
    Review,
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
        plan_json=json.dumps({"targetId": "demo-frontend"}, separators=(",", ":")),
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


def add_diff_and_review(
    db: DbSession,
    task_run_id: str,
    *,
    review_status: str = "passed",
    risk_level: str = "low",
    changed_files: Optional[list[str]] = None,
) -> tuple[str, str]:
    files = changed_files or ["apps/demo/src/App.tsx"]
    diff_artifact = Artifact(
        task_run_id=task_run_id,
        artifact_type="diff",
        title="Git diff",
        status="ready",
    )
    db.add(diff_artifact)
    db.commit()
    db.refresh(diff_artifact)
    diff = Diff(
        artifact_id=diff_artifact.id,
        base_ref="abc123",
        head_ref="def456+worktree",
        patch_text="\n".join([f"diff --git a/{path} b/{path}" for path in files]),
        changed_files_json=json.dumps(files, separators=(",", ":")),
        stats_json="{}",
    )
    review_artifact = Artifact(
        task_run_id=task_run_id,
        artifact_type="review",
        title="Review Agent report",
        status=review_status,
    )
    db.add(diff)
    db.add(review_artifact)
    db.commit()
    db.refresh(review_artifact)
    review = Review(
        artifact_id=review_artifact.id,
        reviewed_diff_artifact_id=diff_artifact.id,
        adapter_type="scripted_mock",
        status=review_status,
        risk_level=risk_level,
        summary=f"{review_status} review",
        files_reviewed_json=json.dumps(files, separators=(",", ":")),
        findings_json="[]",
        suggested_changes_json="[]",
    )
    db.add(review)
    db.commit()
    return diff_artifact.id, review_artifact.id


class RecordingBuildRunner:
    def __init__(
        self,
        *,
        exit_code: int = 0,
        stdout: str = "build ok",
        stderr: str = "",
        create_output: bool = True,
    ) -> None:
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.create_output = create_output
        self.commands: list[tuple[str, Path]] = []

    def run(self, command: str, cwd: Path) -> CommandResult:
        self.commands.append((command, cwd))
        if self.create_output:
            output = cwd / "dist"
            output.mkdir(parents=True, exist_ok=True)
            (output / "index.html").write_text("<h1>staging</h1>\n")
        return CommandResult(
            exit_code=self.exit_code,
            stdout=self.stdout,
            stderr=self.stderr,
        )


class RecordingStaticServer:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, int]] = []

    def start(self, output_dir: Path, port: int) -> StagingServerProcess:
        self.calls.append((output_dir, port))
        return StagingServerProcess(
            pid=5252,
            url=f"http://127.0.0.1:{port}",
            command=f"python -m http.server {port} --bind 127.0.0.1 --directory {output_dir}",
        )


class StaticHealthChecker:
    def __init__(self, healthy: bool = True) -> None:
        self.healthy = healthy
        self.urls: list[str] = []

    def is_healthy(self, url: str) -> bool:
        self.urls.append(url)
        return self.healthy


def test_static_directory_server_uses_current_python_interpreter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    class FakeProcess:
        pid = 5151

    def fake_popen(command, **kwargs):
        calls.append(command)
        return FakeProcess()

    monkeypatch.setattr("app.deployments.subprocess.Popen", fake_popen)

    server = StaticDirectoryServer()
    output_dir = tmp_path / "dist"
    output_dir.mkdir()
    process = server.start(output_dir, 45111)

    assert process.pid == 5151
    assert calls[0][0] == sys.executable
    assert process.command.startswith(sys.executable)


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
        assert metadata["logs"] == provider_result["logs"]
        assert metadata["statusHistory"][-1]["status"] == "ready"
        assert metadata["source"]["previewId"] == preview_id
        assert metadata["providerEvidence"]["taskRunId"] == stored.task_run_id
        assert metadata["providerEvidence"]["adapterType"] == "scripted_mock"
        assert metadata["providerEvidence"]["artifactRefs"]["previewId"] == stored.source_preview_id
        assert (
            metadata["providerEvidence"]["artifactRefs"]["previewArtifactId"]
            == metadata["source"]["previewArtifactId"]
        )


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
            db: DbSession,
            preview: Preview,
            preview_artifact: Artifact,
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


def test_manual_external_provider_persists_handoff_evidence(tmp_path: Path) -> None:
    with next(db_fixture()) as db:
        preview_id, _ = create_preview_fixture(db, tmp_path / "session-worktree")
        service = DeployService(providers=(ManualExternalDeployProvider(),))

        stored = service.create_deployment(db, preview_id, provider_id="manual_external")
        artifact = db.get(Artifact, stored.artifact_id)

        assert stored.provider == "manual_external"
        assert stored.provider_type == "manual_handoff"
        assert stored.status == "handoff"
        assert stored.url is None
        assert artifact is not None
        metadata = json.loads(artifact.meta_json)
        assert metadata["statusHistory"][-1]["status"] == "handoff"
        assert "No third-party deploy was executed" in "\n".join(metadata["logs"])


def test_unavailable_external_provider_persists_blocked_evidence(tmp_path: Path) -> None:
    with next(db_fixture()) as db:
        preview_id, _ = create_preview_fixture(db, tmp_path / "session-worktree")
        service = DeployService(
            providers=(
                UnavailableExternalDeployProvider(
                    provider_id="vercel",
                    display_name="Vercel",
                    reason="Missing VERCEL_TOKEN.",
                ),
            ),
        )

        stored = service.create_deployment(db, preview_id, provider_id="vercel")
        artifact = db.get(Artifact, stored.artifact_id)

        assert stored.provider == "vercel"
        assert stored.provider_type == "external_static"
        assert stored.status == "blocked"
        assert stored.url is None
        assert artifact is not None
        metadata = json.loads(artifact.meta_json)
        assert metadata["statusHistory"][-1]["status"] == "blocked"
        assert "Missing VERCEL_TOKEN" in "\n".join(metadata["logs"])
        assert "ready" not in [item["status"] for item in metadata["statusHistory"]]


def test_local_staging_provider_builds_serves_and_persists_ready_artifact(
    tmp_path: Path,
) -> None:
    with next(db_fixture()) as db:
        worktree = tmp_path / "session-worktree"
        (worktree / "apps/demo").mkdir(parents=True)
        preview_id, task_run_id = create_preview_fixture(db, worktree)
        build_runner = RecordingBuildRunner()
        static_server = RecordingStaticServer()
        health_checker = StaticHealthChecker()
        provider = LocalStagingDeployProvider(
            command_runner=build_runner,
            static_server=static_server,
            health_checker=health_checker,
            port_allocator=lambda: 45217,
        )
        service = DeployService(providers=(MockDeployProvider(), provider))

        stored = service.create_deployment(db, preview_id, provider_id="local_staging")

        artifact = db.get(Artifact, stored.artifact_id)
        deployment = db.get(Deployment, stored.id)
        event = db.exec(
            select(TaskRunEvent).where(
                TaskRunEvent.task_run_id == task_run_id,
                TaskRunEvent.event_type == "artifact.deploy.ready",
            )
        ).one()

        assert artifact is not None
        assert deployment is not None
        assert stored.provider == "local_staging"
        assert stored.environment == "staging"
        assert stored.status == "ready"
        assert stored.url == "http://127.0.0.1:45217"
        assert build_runner.commands == [("pnpm build", worktree / "apps/demo")]
        assert static_server.calls == [(worktree / "apps/demo/dist", 45217)]
        assert health_checker.urls == ["http://127.0.0.1:45217"]

        metadata = json.loads(artifact.meta_json)
        provider_result = metadata["providerResult"]
        assert provider_result["providerId"] == "local_staging"
        assert provider_result["providerType"] == "local_staging"
        assert provider_result["targetId"] == "demo-frontend"
        assert provider_result["buildCommand"] == "pnpm build"
        assert provider_result["deployCommand"].startswith("python -m http.server")
        assert provider_result["outputUrl"] == "http://127.0.0.1:45217"
        assert "build ok" in "\n".join(provider_result["logs"])
        assert json.loads(event.payload_json)["provider"] == "local_staging"


def test_local_staging_provider_reports_failed_build_without_ready_artifact(
    tmp_path: Path,
) -> None:
    with next(db_fixture()) as db:
        worktree = tmp_path / "session-worktree"
        (worktree / "apps/demo").mkdir(parents=True)
        preview_id, _ = create_preview_fixture(db, worktree)
        provider = LocalStagingDeployProvider(
            command_runner=RecordingBuildRunner(
                exit_code=1,
                stdout="",
                stderr="build exploded",
                create_output=False,
            ),
            static_server=RecordingStaticServer(),
            health_checker=StaticHealthChecker(),
            port_allocator=lambda: 45218,
        )
        service = DeployService(providers=(provider,))

        stored = service.create_deployment(db, preview_id, provider_id="local_staging")
        artifact = db.get(Artifact, stored.artifact_id)

        assert stored.status == "failed"
        assert artifact is not None
        metadata = json.loads(artifact.meta_json)
        assert metadata["statusHistory"][-1]["status"] == "failed"
        assert "Build command failed" in "\n".join(metadata["logs"])


def test_local_staging_provider_reports_missing_output_without_ready_artifact(
    tmp_path: Path,
) -> None:
    with next(db_fixture()) as db:
        worktree = tmp_path / "session-worktree"
        (worktree / "apps/demo").mkdir(parents=True)
        preview_id, _ = create_preview_fixture(db, worktree)
        provider = LocalStagingDeployProvider(
            command_runner=RecordingBuildRunner(create_output=False),
            static_server=RecordingStaticServer(),
            health_checker=StaticHealthChecker(),
            port_allocator=lambda: 45219,
        )
        service = DeployService(providers=(provider,))

        stored = service.create_deployment(db, preview_id, provider_id="local_staging")
        artifact = db.get(Artifact, stored.artifact_id)

        assert stored.status == "failed"
        assert artifact is not None
        assert "output directory missing" in "\n".join(json.loads(artifact.meta_json)["logs"])


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


def test_deploy_api_can_select_local_staging_provider(tmp_path: Path) -> None:
    with next(db_fixture()) as db:
        worktree = tmp_path / "session-worktree"
        (worktree / "apps/demo").mkdir(parents=True)
        preview_id, _ = create_preview_fixture(db, worktree)
        provider = LocalStagingDeployProvider(
            command_runner=RecordingBuildRunner(),
            static_server=RecordingStaticServer(),
            health_checker=StaticHealthChecker(),
            port_allocator=lambda: 45220,
        )
        service = DeployService(providers=(MockDeployProvider(), provider))

        def override_db() -> Iterator[DbSession]:
            yield db

        def override_deploy_service() -> DeployService:
            return service

        app.dependency_overrides[get_db] = override_db
        from app.main import get_deploy_service

        app.dependency_overrides[get_deploy_service] = override_deploy_service
        try:
            client = TestClient(app)
            response = client.post(
                f"/previews/{preview_id}/deploy",
                json={"providerId": "local_staging"},
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 201
        assert response.json()["provider"] == "local_staging"
        assert response.json()["environment"] == "staging"
        assert response.json()["url"] == "http://127.0.0.1:45220"
        assert response.json()["targetId"] == "demo-frontend"
        assert response.json()["providerType"] == "local_staging"
        assert response.json()["sourcePreviewId"] == preview_id
        assert response.json()["logs"]
        assert response.json()["statusHistory"][-1]["status"] == "ready"


def test_deploy_api_creates_blocked_external_provider_card(tmp_path: Path) -> None:
    with next(db_fixture()) as db:
        preview_id, _ = create_preview_fixture(db, tmp_path / "session-worktree")

        def override_db() -> Iterator[DbSession]:
            yield db

        app.dependency_overrides[get_db] = override_db
        try:
            client = TestClient(app)
            response = client.post(
                f"/previews/{preview_id}/deploy",
                json={"providerId": "vercel"},
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 201
        assert response.json()["provider"] == "vercel"
        assert response.json()["providerType"] == "external_static"
        assert response.json()["status"] == "blocked"
        assert response.json()["url"] is None
        assert response.json()["statusHistory"][-1]["status"] == "blocked"
        assert "third-party production deploy" in "\n".join(response.json()["logs"])


def test_local_staging_deploy_blocks_failed_review(tmp_path: Path) -> None:
    with next(db_fixture()) as db:
        worktree = tmp_path / "session-worktree"
        (worktree / "apps/demo").mkdir(parents=True)
        preview_id, task_run_id = create_preview_fixture(db, worktree)
        add_diff_and_review(db, task_run_id, review_status="failed", risk_level="high")
        provider = LocalStagingDeployProvider(
            command_runner=RecordingBuildRunner(),
            static_server=RecordingStaticServer(),
            health_checker=StaticHealthChecker(),
            port_allocator=lambda: 45221,
        )
        service = DeployService(providers=(provider,))

        with pytest.raises(DeployError, match="review failed"):
            service.create_deployment(db, preview_id, provider_id="local_staging")


def test_local_staging_deploy_blocks_unhealthy_preview(tmp_path: Path) -> None:
    with next(db_fixture()) as db:
        worktree = tmp_path / "session-worktree"
        (worktree / "apps/demo").mkdir(parents=True)
        preview_id, _ = create_preview_fixture(db, worktree)
        preview = db.get(Preview, preview_id)
        assert preview is not None
        preview.health_status = "unhealthy"
        db.add(preview)
        db.commit()
        service = DeployService()

        with pytest.raises(DeployError, match="healthy preview"):
            service.create_deployment(db, preview_id, provider_id="local_staging")


def test_local_staging_deploy_blocks_target_policy_violation(tmp_path: Path) -> None:
    with next(db_fixture()) as db:
        worktree = tmp_path / "session-worktree"
        (worktree / "apps/demo").mkdir(parents=True)
        preview_id, task_run_id = create_preview_fixture(db, worktree)
        add_diff_and_review(
            db,
            task_run_id,
            review_status="warning",
            risk_level="medium",
            changed_files=["apps/api/app/main.py"],
        )
        provider = LocalStagingDeployProvider(
            command_runner=RecordingBuildRunner(),
            static_server=RecordingStaticServer(),
            health_checker=StaticHealthChecker(),
            port_allocator=lambda: 45222,
        )
        service = DeployService(providers=(provider,))

        with pytest.raises(DeployError, match="target policy violation"):
            service.create_deployment(db, preview_id, provider_id="local_staging")


def test_production_deploy_request_is_rejected(tmp_path: Path) -> None:
    with next(db_fixture()) as db:
        preview_id, _ = create_preview_fixture(db, tmp_path / "session-worktree")
        service = DeployService()

        with pytest.raises(DeployError, match="Production deploy is not supported"):
            service.create_deployment(
                db,
                preview_id,
                provider_id="local_staging",
                environment="production",
            )


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
