import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.main import agent_run_request_for, app, get_db
from app.guardrails import ApprovalRequestPayload, request_task_run_approval
from app.models import Agent, Session, Task, TaskRun, TaskRunEvent, Workspace
from app.task_runs import create_task_run, transition_task_run


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


def test_agent_run_request_bounds_frontend_login_demo_instruction(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps(
            {
                "target": "login_page",
                "files": ["apps/demo/src/App.tsx", "apps/demo/src/styles.css"],
            },
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        task_run = create_task_run(db, task.id)

        request = agent_run_request_for(db, task_run, adapter_type="codex")

    assert 'data-agenthub-target="login-page-slot"' in request.instruction
    assert "apps/demo/src/App.tsx" in request.instruction
    assert "do not read the OpenSpec change" in request.instruction
    assert "dependency install" in request.instruction
    assert request.instruction != "Build login page"


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


def test_approval_request_is_visible_and_approve_deny_endpoints_work(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        approved_run = create_task_run(db, task.id)
        request_task_run_approval(
            db,
            approved_run.id,
            ApprovalRequestPayload(
                approvalType="product_confirmation",
                reason="Deploy requires confirmation.",
                requestedAction="deploy preview",
                riskLevel="medium",
            ),
        )
        denied_run = create_task_run(db, task.id)
        request_task_run_approval(
            db,
            denied_run.id,
            ApprovalRequestPayload(
                approvalType="security_approval",
                reason="Network access is disabled.",
                requestedAction="network access",
                riskLevel="high",
            ),
        )
        session_id = task.session_id
        approved_run_id = approved_run.id
        denied_run_id = denied_run.id

    task_response = client.get(f"/sessions/{session_id}/tasks")
    assert task_response.status_code == 200
    runs = {
        run["id"]: run
        for task_payload in task_response.json()
        for run in task_payload["taskRuns"]
    }
    assert runs[approved_run_id]["state"] == "waiting_approval"
    assert runs[approved_run_id]["approvalRequest"] == {
        "approvalType": "product_confirmation",
        "reason": "Deploy requires confirmation.",
        "requestedAction": "deploy preview",
        "riskLevel": "medium",
        "command": None,
        "path": None,
        "expiresAt": None,
    }

    approved_response = client.post(f"/task-runs/{approved_run_id}/approve")
    denied_response = client.post(
        f"/task-runs/{denied_run_id}/deny",
        json={"reason": "User denied network access."},
    )

    assert approved_response.status_code == 200
    assert approved_response.json()["state"] == "queued"
    assert approved_response.json()["approvalRequest"] is None
    assert denied_response.status_code == 200
    assert denied_response.json()["state"] == "failed"
    assert denied_response.json()["errorCode"] == "APPROVAL_DENIED"
    assert denied_response.json()["errorMessage"] == "User denied network access."


def test_direct_ui_start_dispatch_creates_queued_run_with_adapter_type(
    client: TestClient,
) -> None:
    response = client.post(f"/tasks/{task_id()}/runs")

    assert response.status_code == 201
    run = response.json()
    assert run["state"] == "queued"
    assert run["adapterType"] == "codex"
    assert run.get("id")

    with db_from_override() as db:
        task = db.get(Task, run["taskId"])
        assert task is not None
        assert task.status == "running"


def test_direct_ui_start_background_execution_persists_events(
    client: TestClient,
) -> None:
    """Prove background adapter dispatch runs and persists TaskRunEvents after Start."""
    import app.db as db_module

    with db_from_override() as db:
        test_engine = db.get_bind()

    original_engine = db_module.engine
    db_module.engine = test_engine
    try:
        response = client.post(f"/tasks/{task_id()}/runs")
    finally:
        db_module.engine = original_engine

    assert response.status_code == 201
    run = response.json()
    assert run["state"] == "queued"
    assert run["adapterType"] == "codex"

    with db_from_override() as db:
        events = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == run["id"])
            .order_by(TaskRunEvent.sequence)
        ).all()
        stored = db.get(TaskRun, run["id"])

    # The endpoint creates a "queued" event (sequence 1).
    # The background task invokes CodexAdapter:
    #   - If Codex CLI is installed and worktree exists: streaming/completed events
    #   - If Codex CLI is not installed or worktree missing: failed with CODEX_* error
    assert len(events) >= 2, (
        f"Background execution did not persist events beyond queued: {len(events)} events"
    )
    assert stored.state in {"failed", "streaming", "completed"}, (
        f"Background execution did not transition state past queued: {stored.state}"
    )

    # At least one event after queued must be from CodexAdapter execution
    later_events = events[1:]
    adapter_event_types = {e.event_type for e in later_events}
    assert adapter_event_types & {"error", "task.state", "completed", "message.delta"}, (
        f"No adapter lifecycle events found after queued: {adapter_event_types}"
    )

    if stored.state == "failed":
        assert stored.error_code is not None, "Failed TaskRun must have error_code"
        assert "CODEX_" in (stored.error_code or ""), (
            f"Expected CODEX_* error code, got: {stored.error_code}"
        )
        assert stored.error_message is not None, "Failed TaskRun must have error_message"


def test_direct_ui_start_scripted_mock_background_execution_persists_events(
    client: TestClient,
) -> None:
    """Prove ScriptedMockAdapter background dispatch persists events after Start."""
    import app.db as db_module

    with db_from_override() as db:
        test_engine = db.get_bind()
        qa_agent_id = db.exec(select(Agent).where(Agent.role == "qa")).one().id
        session_id = db.exec(select(Task).where(Task.title == "Build login page")).one().session_id

    qa_task = Task(
        session_id=session_id,
        title="Review login page",
        intent_type="review",
        status="pending",
        assigned_agent_id=qa_agent_id,
    )
    with db_from_override() as db:
        db.add(qa_task)
        db.commit()
        qa_task_id = qa_task.id

    original_engine = db_module.engine
    db_module.engine = test_engine
    try:
        response = client.post(f"/tasks/{qa_task_id}/runs")
    finally:
        db_module.engine = original_engine

    assert response.status_code == 201
    run = response.json()
    assert run["adapterType"] == "scripted_mock"

    with db_from_override() as db:
        events = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == run["id"])
            .order_by(TaskRunEvent.sequence)
        ).all()
        stored = db.get(TaskRun, run["id"])

    assert len(events) >= 2, (
        f"Background execution did not persist events: {len(events)} events"
    )
    assert stored.state != "queued", (
        f"Background execution did not transition past queued: {stored.state}"
    )
