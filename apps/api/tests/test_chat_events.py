from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.events import append_task_run_event, list_session_events
from app.main import app, get_db
from app.models import Agent, Message, Session, Task, TaskRun, Workspace


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
        orchestrator = Agent(
            name="Orchestrator",
            role="orchestrator",
            adapter_type="scripted_mock",
            provider="local",
            enabled=True,
        )
        agent = Agent(
            name="Frontend Agent",
            role="frontend",
            adapter_type="codex",
            provider="local",
            enabled=True,
        )
        session_one = Session(
            workspace_id=workspace.id,
            title="Session one",
            bound_branch="main",
            worktree_path=".worktrees/session-one",
        )
        session_two = Session(
            workspace_id=workspace.id,
            title="Session two",
            bound_branch="main",
            worktree_path=".worktrees/session-two",
        )
        db.add(workspace)
        db.add(orchestrator)
        db.add(agent)
        db.add(session_one)
        db.add(session_two)
        db.commit()

    def override_db() -> Iterator[DbSession]:
        with DbSession(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def db_from_override() -> Iterator[DbSession]:
    override = app.dependency_overrides[get_db]
    return override()


def test_messages_are_persisted_and_scoped_to_selected_session(
    client: TestClient,
) -> None:
    with next(db_from_override()) as db:
        sessions = db.exec(select(Session).order_by(Session.title)).all()
        session_one = sessions[0]
        session_two = sessions[1]

    first = client.post(
        f"/sessions/{session_one.id}/messages",
        json={"contentMd": "@orchestrator build a login page"},
    )
    second = client.post(
        f"/sessions/{session_two.id}/messages",
        json={"contentMd": "separate thread", "senderType": "system"},
    )

    assert first.status_code == 201
    assert second.status_code == 201

    session_one_messages = client.get(f"/sessions/{session_one.id}/messages")
    session_two_messages = client.get(f"/sessions/{session_two.id}/messages")

    assert [message["contentMd"] for message in session_one_messages.json()] == [
        "@orchestrator build a login page",
        "I could not safely turn that into a demo-target task yet. Please ask for a bounded change inside the demo app, or explicitly mention @frontend for a frontend assignment.",
    ]
    assert [message["contentMd"] for message in session_two_messages.json()] == [
        "separate thread"
    ]

    with next(db_from_override()) as db:
        stored_session = db.get(Session, session_one.id)
        stored_message = db.exec(
            select(Message)
            .where(Message.session_id == session_one.id)
            .order_by(Message.created_at.desc())
        ).first()
        assert stored_session is not None
        assert stored_message is not None
        assert stored_session.last_message_at == stored_message.created_at


def test_task_run_events_append_and_query_by_sequence(client: TestClient) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Session one")).one()
        agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        task = Task(
            session_id=session.id,
            title="Future task",
            intent_type="frontend_change",
            assigned_agent_id=agent.id,
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        task_run = TaskRun(
            task_id=task.id,
            agent_id=agent.id,
            state="created",
            worktree_path=session.worktree_path,
        )
        db.add(task_run)
        db.commit()
        db.refresh(task_run)

        first = append_task_run_event(
            db,
            task_run_id=task_run.id,
            event_type="task.state",
            payload_json='{"state":"queued"}',
        )
        second = append_task_run_event(
            db,
            task_run_id=task_run.id,
            event_type="message.delta",
            payload_json='{"text":"working"}',
        )

        assert first.sequence == 1
        assert second.sequence == 2

        replayed = list_session_events(db, session_id=session.id, after_sequence=1)
        assert [event.sequence for event in replayed] == [2]
        assert replayed[0].event_type == "message.delta"

    response = client.get(f"/sessions/{session.id}/events?after=1", headers={"accept": "text/event-stream"})

    assert response.status_code == 200
    assert "event: message.delta" in response.text
    assert '"sequence":2' in response.text
