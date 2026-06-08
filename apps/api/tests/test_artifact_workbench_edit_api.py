import json
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.main import app, get_db
from app.models import Agent, Artifact, ArtifactVersion, Diff, Session, Task, TaskRun, Workspace


def test_editable_artifact_save_creates_new_version_without_repo_diff() -> None:
    with _client() as client:
        _, artifact_id, task_run_id = _seed_artifact_fixture()

        response = client.post(
            f"/artifacts/{artifact_id}/workbench/edits",
            json={
                "contentMd": "# Updated notes\n\nKeep this as an artifact draft.",
                "summary": "Update artifact notes.",
            },
        )

        assert response.status_code == 201
        payload = response.json()
        assert payload["artifactId"] == artifact_id
        assert payload["version"] == 2
        assert payload["parentVersionId"] is not None
        assert payload["contentMd"] == "# Updated notes\n\nKeep this as an artifact draft."
        assert payload["contentHash"].startswith("sha256:")
        assert payload["changedFiles"] == []

        versions_response = client.get(f"/artifacts/{artifact_id}/workbench/versions")
        assert versions_response.status_code == 200
        versions = versions_response.json()
        assert [version["version"] for version in versions] == [1, 2]
        assert versions[-1]["contentMd"] == "# Updated notes\n\nKeep this as an artifact draft."

        diff_response = client.get(f"/task-runs/{task_run_id}/diffs")
        assert diff_response.status_code == 200
        assert diff_response.json() == []


def test_artifact_edit_rejects_unsupported_types_without_mutation() -> None:
    with _client() as client:
        _, artifact_id, _ = _seed_artifact_fixture(artifact_type="diff")

        response = client.post(
            f"/artifacts/{artifact_id}/workbench/edits",
            json={"contentMd": "try to edit a diff", "summary": "Nope."},
        )

        assert response.status_code == 400
        assert "not editable" in response.json()["detail"]
        versions = client.get(f"/artifacts/{artifact_id}/workbench/versions").json()
        assert [version["version"] for version in versions] == [1]


def test_artifact_edit_rejects_missing_or_empty_content() -> None:
    with _client() as client:
        _, artifact_id, _ = _seed_artifact_fixture()

        missing = client.post(
            "/artifacts/missing/workbench/edits",
            json={"contentMd": "new content"},
        )
        empty = client.post(
            f"/artifacts/{artifact_id}/workbench/edits",
            json={"contentMd": ""},
        )

        assert missing.status_code == 404
        assert empty.status_code == 422


def test_artifact_edit_does_not_modify_existing_version_content() -> None:
    with _client() as client:
        _, artifact_id, _ = _seed_artifact_fixture()

        first_before = client.get(f"/artifacts/{artifact_id}/workbench/versions").json()[0]
        response = client.post(
            f"/artifacts/{artifact_id}/workbench/edits",
            json={"contentMd": "Second version content."},
        )
        first_after = client.get(f"/artifacts/{artifact_id}/workbench/versions").json()[0]

        assert response.status_code == 201
        assert first_after["id"] == first_before["id"]
        assert first_after["contentHash"] == first_before["contentHash"]
        assert first_after["contentMd"] == first_before["contentMd"]


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
            name="Artifact Edit Workspace",
            repo_url="local://artifact-edit",
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
            title="Artifact edit session",
            session_type="group",
            bound_branch="main",
            worktree_path="/tmp/artifact-edit-session",
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
            worktree_path="/tmp/artifact-edit-session",
        )
        artifact = Artifact(
            task_run_id=task_run.id,
            artifact_type=artifact_type,
            title="Artifact Notes",
            status="ready",
            meta_json=json.dumps({"safePath": "docs/change-log.md"}),
        )
        db.add(workspace)
        db.add(agent)
        db.add(session)
        db.add(task)
        db.add(task_run)
        db.add(artifact)
        db.commit()
        db.refresh(artifact)
        db.refresh(task_run)
        version = ArtifactVersion(
            artifact_id=artifact.id,
            version=1,
            source_task_run_id=task_run.id,
            summary="Initial artifact version.",
            content_md="Initial artifact content.",
            content_hash="sha256:initial",
        )
        db.add(version)
        db.commit()
        assert db.exec(select(Diff).where(Diff.artifact_id == artifact.id)).first() is None
        return session.id, artifact.id, task_run.id
