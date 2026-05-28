import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.external_evidence import (
    ExternalEvidenceError,
    list_task_run_command_evidence,
    record_command_evidence,
)
from app.main import app, get_db
from app.models import Agent, Artifact, Session, Task, TaskRun, TaskRunEvent, Workspace
from app.target_registry import DEMO_BACKEND_TARGET_ID
from app.task_runs import create_task_run


@pytest.fixture
def db() -> Iterator[DbSession]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as session:
        yield session


@pytest.fixture
def client(db: DbSession) -> Iterator[TestClient]:
    def override_db() -> Iterator[DbSession]:
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def create_task_run_fixture(db: DbSession) -> str:
    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="Evidence session",
        bound_branch="main",
        worktree_path=".worktrees/evidence-session",
    )
    agent = Agent(name="QA Agent", role="qa", adapter_type="scripted_mock", provider="local")
    task = Task(
        session_id=session.id,
        title="Record command evidence",
        intent_type="review",
        assigned_agent_id=agent.id,
        plan_json=json.dumps({"readOnly": True}, separators=(",", ":")),
    )
    db.add(workspace)
    db.add(session)
    db.add(agent)
    db.add(task)
    db.commit()
    db.refresh(task)
    return create_task_run(db, task.id, adapter_type="scripted_mock").id


def test_records_passed_and_failed_command_evidence(db: DbSession) -> None:
    task_run_id = create_task_run_fixture(db)

    passed = record_command_evidence(
        db,
        task_run_id,
        command_type="test",
        command="pnpm test",
        exit_code=0,
        stdout="all green",
    )
    failed = record_command_evidence(
        db,
        task_run_id,
        command_type="build",
        command="pnpm build",
        exit_code=1,
        stderr="build failed",
    )
    evidence = list_task_run_command_evidence(db, task_run_id)
    events = db.exec(
        select(TaskRunEvent).where(
            TaskRunEvent.task_run_id == task_run_id,
            TaskRunEvent.event_type == "artifact.command_evidence.ready",
        )
    ).all()

    assert [item.status for item in evidence] == ["passed", "failed"]
    assert passed.command_type == "test"
    assert failed.command_type == "build"
    assert failed.stderr == "build failed"
    assert len(events) == 2
    assert db.get(Artifact, passed.artifact_id).artifact_type == "command_evidence"


def test_target_command_evidence_uses_registered_target_policy(db: DbSession) -> None:
    task_run_id = create_task_run_fixture(db)
    task_run = db.get(TaskRun, task_run_id)
    task = db.get(Task, task_run.task_id)
    task.plan_json = json.dumps({"targetId": DEMO_BACKEND_TARGET_ID}, separators=(",", ":"))
    db.add(task)
    db.commit()

    evidence = record_command_evidence(
        db,
        task_run_id,
        command_type="test",
        command="pnpm demo:api:test",
        exit_code=0,
        stdout="5 passed",
    )
    event = db.exec(
        select(TaskRunEvent).where(
            TaskRunEvent.task_run_id == task_run_id,
            TaskRunEvent.event_type == "artifact.command_evidence.ready",
        )
    ).one()
    event_payload = json.loads(event.payload_json)
    artifact_meta = json.loads(db.get(Artifact, evidence.artifact_id).meta_json)

    assert evidence.target_id == DEMO_BACKEND_TARGET_ID
    assert artifact_meta["targetId"] == DEMO_BACKEND_TARGET_ID
    assert event_payload["targetId"] == DEMO_BACKEND_TARGET_ID


def test_target_command_evidence_rejects_unregistered_command(db: DbSession) -> None:
    task_run_id = create_task_run_fixture(db)

    with pytest.raises(ExternalEvidenceError, match="not allowed for target"):
        record_command_evidence(
            db,
            task_run_id,
            command_type="test",
            command="pnpm test",
            exit_code=0,
            target_id=DEMO_BACKEND_TARGET_ID,
        )


def test_command_evidence_api_records_failed_output_honestly(
    client: TestClient,
    db: DbSession,
) -> None:
    task_run_id = create_task_run_fixture(db)

    response = client.post(
        f"/task-runs/{task_run_id}/command-evidence",
        json={
            "commandType": "check",
            "command": "pnpm check",
            "exitCode": 2,
            "stdout": "",
            "stderr": "type error",
        },
    )
    list_response = client.get(f"/task-runs/{task_run_id}/command-evidence")

    assert response.status_code == 201
    assert response.json()["status"] == "failed"
    assert response.json()["exitCode"] == 2
    assert response.json()["stderr"] == "type error"
    assert list_response.status_code == 200
    assert list_response.json()[0]["commandType"] == "check"


def test_command_evidence_api_rejects_unknown_type(
    client: TestClient,
    db: DbSession,
) -> None:
    task_run_id = create_task_run_fixture(db)

    response = client.post(
        f"/task-runs/{task_run_id}/command-evidence",
        json={
            "commandType": "deploy",
            "command": "pnpm deploy",
            "exitCode": 0,
        },
    )

    assert response.status_code == 400
