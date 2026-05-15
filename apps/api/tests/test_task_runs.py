import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.main import app, get_db
from app.models import Agent, Session, Task, TaskRun, TaskRunEvent, Workspace
from app.task_runs import transition_task_run


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with DbSession(engine) as db:
        workspace = Workspace(
            name="AgentHub Demo",
            repo_url="local://apps/demo",
            root_path="apps/demo",
            default_branch="main",
        )
        session = Session(
            workspace_id=workspace.id,
            title="TaskRun session",
            bound_branch="main",
            worktree_path=".worktrees/taskrun-session",
        )
        frontend = Agent(
            name="Frontend Agent",
            role="frontend",
            adapter_type="codex",
            provider="local",
        )
        qa = Agent(
            name="QA Agent",
            role="qa",
            adapter_type="scripted_mock",
            provider="local",
        )
        task = Task(
            session_id=session.id,
            title="Build login page",
            intent_type="frontend_change",
            status="pending",
            assigned_agent_id=frontend.id,
        )
        db.add(workspace)
        db.add(session)
        db.add(frontend)
        db.add(qa)
        db.add(task)
        db.commit()

    def override_db() -> Iterator[DbSession]:
        with DbSession(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def db_from_override() -> DbSession:
    override = app.dependency_overrides[get_db]
    return next(override())


def task_id() -> str:
    with db_from_override() as db:
        return db.exec(select(Task).where(Task.title == "Build login page")).one().id


def test_create_task_run_persists_queued_state_before_event(client: TestClient) -> None:
    response = client.post(f"/tasks/{task_id()}/runs")

    assert response.status_code == 201
    run = response.json()
    assert run["state"] == "queued"
    assert run["adapterType"] == "codex"
    assert run["worktreePath"] == ".worktrees/taskrun-session"

    with db_from_override() as db:
        stored = db.get(TaskRun, run["id"])
        event = db.exec(select(TaskRunEvent).where(TaskRunEvent.task_run_id == run["id"])).one()
        task = db.get(Task, stored.task_id)

        assert stored.state == "queued"
        assert task.status == "running"
        assert event.sequence == 1
        assert event.event_type == "task.state"
        assert json.loads(event.payload_json)["state"] == "queued"


def test_transition_helper_rejects_unknown_states(client: TestClient) -> None:
    run = client.post(f"/tasks/{task_id()}/runs").json()

    with db_from_override() as db:
        with pytest.raises(ValueError, match="Unsupported TaskRun state"):
            transition_task_run(db, run["id"], "sleeping")


def test_interrupt_running_task_run_updates_task_and_preserves_history(
    client: TestClient,
) -> None:
    run = client.post(f"/tasks/{task_id()}/runs").json()

    response = client.post(f"/task-runs/{run['id']}/interrupt")

    assert response.status_code == 200
    interrupted = response.json()
    assert interrupted["id"] == run["id"]
    assert interrupted["state"] == "interrupted"
    assert interrupted["errorCode"] == "TASK_RUN_INTERRUPTED"

    task_response = client.get(f"/sessions/{interrupted['sessionId']}/tasks")
    task = task_response.json()[0]
    assert task["status"] == "interrupted"
    assert [task_run["id"] for task_run in task["taskRuns"]] == [run["id"]]
    assert task["taskRuns"][0]["state"] == "interrupted"


def test_retry_failed_or_interrupted_run_creates_new_history_row(
    client: TestClient,
) -> None:
    original = client.post(f"/tasks/{task_id()}/runs").json()
    client.post(f"/task-runs/{original['id']}/interrupt")

    retry_response = client.post(f"/task-runs/{original['id']}/retry")

    assert retry_response.status_code == 201
    retried = retry_response.json()
    assert retried["id"] != original["id"]
    assert retried["state"] == "queued"
    assert retried["adapterType"] == "codex"
    assert retried["metricsJson"]["retryOfRunId"] == original["id"]

    with db_from_override() as db:
        previous = db.get(TaskRun, original["id"])
        runs = db.exec(select(TaskRun).where(TaskRun.task_id == previous.task_id)).all()
        assert previous.state == "interrupted"
        assert len(runs) == 2


def test_retry_with_scripted_mock_fallback_after_codex_failure(
    client: TestClient,
) -> None:
    original = client.post(f"/tasks/{task_id()}/runs").json()

    with db_from_override() as db:
        transition_task_run(
            db,
            original["id"],
            "failed",
            payload={"errorCode": "CODEX_USAGE_LIMIT"},
            error_code="CODEX_USAGE_LIMIT",
            error_message="Codex usage limit reached.",
        )

    response = client.post(f"/task-runs/{original['id']}/retry-with-fallback")

    assert response.status_code == 201
    fallback = response.json()
    assert fallback["id"] != original["id"]
    assert fallback["adapterType"] == "scripted_mock"
    assert fallback["state"] in {"queued", "failed"}
    assert fallback["metricsJson"]["fallbackFromRunId"] == original["id"]

    task_response = client.get(f"/sessions/{fallback['sessionId']}/tasks")
    task = task_response.json()[0]
    assert [run["id"] for run in task["taskRuns"]] == [original["id"], fallback["id"]]


def test_force_codex_failure_creates_failed_visible_run(client: TestClient) -> None:
    response = client.post(f"/tasks/{task_id()}/runs/force-codex-failure")

    assert response.status_code == 201
    run = response.json()
    assert run["adapterType"] == "codex"
    assert run["state"] == "failed"
    assert run["errorCode"] == "CODEX_DEMO_FORCED_FAILURE"

    task_response = client.get(f"/sessions/{run['sessionId']}/tasks")
    task = task_response.json()[0]
    assert task["status"] == "failed"
    assert [task_run["id"] for task_run in task["taskRuns"]] == [run["id"]]


def test_retry_with_fallback_requires_failed_codex_run(client: TestClient) -> None:
    run = client.post(f"/tasks/{task_id()}/runs").json()

    response = client.post(f"/task-runs/{run['id']}/retry-with-fallback")

    assert response.status_code == 400
    assert "failed or interrupted Codex run" in response.json()["detail"]
