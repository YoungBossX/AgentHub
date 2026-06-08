import json
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine

from app.main import app, get_db
from app.models import Agent, Artifact, ArtifactVersion, Session, Task, TaskRun, Workspace


def test_session_artifact_workbench_lists_safe_renderer_metadata() -> None:
    with _client() as client:
        session_id, artifact_id, _ = _seed_artifact_fixture()

        response = client.get(f"/sessions/{session_id}/artifact-workbench")

        assert response.status_code == 200
        payload = response.json()
        assert payload["sessionId"] == session_id
        assert payload["artifacts"][0]["artifactId"] == artifact_id
        assert payload["artifacts"][0]["rendererKind"] == "markdown_document"
        assert payload["artifacts"][0]["editable"] is True
        serialized = json.dumps(payload)
        assert "sk-secret" not in serialized
        assert ".env" not in serialized
        assert "node_modules" not in serialized


def test_artifact_workbench_detail_and_versions_include_content_hash() -> None:
    with _client() as client:
        _, artifact_id, version_id = _seed_artifact_fixture()

        detail_response = client.get(f"/artifacts/{artifact_id}/workbench")
        versions_response = client.get(f"/artifacts/{artifact_id}/workbench/versions")
        version_response = client.get(
            f"/artifacts/{artifact_id}/workbench/versions/{version_id}"
        )

        assert detail_response.status_code == 200
        assert detail_response.json()["contentHash"].startswith("sha256:")
        assert versions_response.status_code == 200
        assert versions_response.json()[0]["id"] == version_id
        assert versions_response.json()[0]["contentHash"].startswith("sha256:")
        assert version_response.status_code == 200
        assert version_response.json()["artifactId"] == artifact_id
        assert version_response.json()["contentHash"].startswith("sha256:")


def test_artifact_workbench_unknown_artifact_uses_safe_fallback() -> None:
    with _client() as client:
        session_id, _, _ = _seed_artifact_fixture(artifact_type="custom_binary")

        response = client.get(f"/sessions/{session_id}/artifact-workbench")

        assert response.status_code == 200
        artifact = response.json()["artifacts"][0]
        assert artifact["rendererKind"] == "unknown"
        assert artifact["editable"] is False


def test_artifact_workbench_rejects_missing_artifact_or_version() -> None:
    with _client() as client:
        _, artifact_id, _ = _seed_artifact_fixture()

        missing_artifact = client.get("/artifacts/missing/workbench")
        missing_version = client.get(
            f"/artifacts/{artifact_id}/workbench/versions/missing-version"
        )

        assert missing_artifact.status_code == 404
        assert missing_version.status_code == 404


@contextmanager
def _client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_db() -> Iterator[DbSession]:
        with DbSession(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _seed_artifact_fixture(
    *,
    artifact_type: str = "markdown_document",
) -> tuple[str, str, str]:
    with next(app.dependency_overrides[get_db]()) as db:
        workspace = Workspace(
            name="Artifact Workspace",
            repo_url="local://artifact",
            root_path="apps/demo",
            default_branch="main",
        )
        agent = Agent(
            name="Frontend Agent",
            role="frontend",
            adapter_type="codex",
            provider="local-codex-cli",
        )
        session = Session(
            workspace_id=workspace.id,
            title="Artifact session",
            session_type="group",
            bound_branch="main",
            worktree_path="/tmp/artifact-session",
        )
        task = Task(
            session_id=session.id,
            title="Create artifact",
            intent_type="frontend_change",
            assigned_agent_id=agent.id,
        )
        task_run = TaskRun(
            task_id=task.id,
            agent_id=agent.id,
            state="completed",
            worktree_path="/tmp/artifact-session",
        )
        artifact = Artifact(
            task_run_id=task_run.id,
            artifact_type=artifact_type,
            title="Artifact Notes",
            status="ready",
            meta_json=json.dumps(
                {
                    "safePath": "docs/change-log.md",
                    "apiToken": "sk-secret",
                    "unsafePath": "/tmp/project/.env",
                    "dependency": "node_modules/pkg/index.js",
                }
            ),
        )
        db.add(workspace)
        db.add(agent)
        db.add(session)
        db.add(task)
        db.add(task_run)
        db.add(artifact)
        db.commit()
        db.refresh(session)
        db.refresh(artifact)
        version = ArtifactVersion(
            artifact_id=artifact.id,
            version=1,
            source_task_run_id=task_run.id,
            summary="Initial artifact version.",
        )
        db.add(version)
        db.commit()
        db.refresh(version)
        return session.id, artifact.id, version.id
