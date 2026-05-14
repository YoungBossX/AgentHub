from collections.abc import Iterator
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.main import app, get_db
from app.models import Agent, Message, Session, Task, Workspace
from app.planning import MentionParseError, parse_mentions


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
            title="Planning session",
            bound_branch="main",
            worktree_path=".worktrees/planning-session",
        )
        agents = [
            Agent(name="Orchestrator", role="orchestrator", adapter_type="scripted_mock", provider="local"),
            Agent(name="Frontend Agent", role="frontend", adapter_type="codex", provider="local"),
            Agent(name="Backend Agent", role="backend", adapter_type="codex", provider="local"),
            Agent(name="QA Agent", role="qa", adapter_type="scripted_mock", provider="local"),
        ]
        db.add(workspace)
        db.add(session)
        for agent in agents:
            db.add(agent)
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


def test_parse_mentions_resolves_supported_enabled_agents(client: TestClient) -> None:
    with next(db_from_override()) as db:
        parsed = parse_mentions(db, "@orchestrator please ask @frontend and @qa")

    assert parsed.roles == ["orchestrator", "frontend", "qa"]


def test_parse_mentions_rejects_unknown_or_disabled_agents(client: TestClient) -> None:
    with next(db_from_override()) as db:
        qa_agent = db.exec(select(Agent).where(Agent.role == "qa")).one()
        qa_agent.enabled = False
        db.add(qa_agent)
        db.commit()

        with pytest.raises(MentionParseError, match="@designer"):
            parse_mentions(db, "@designer build a page")

        with pytest.raises(MentionParseError, match="@qa"):
            parse_mentions(db, "@qa verify it")


def test_orchestrator_login_request_creates_visible_tasks(client: TestClient) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()

    response = client.post(
        f"/sessions/{session.id}/messages",
        json={"contentMd": "@orchestrator build a login page for the demo app"},
    )

    assert response.status_code == 201

    task_response = client.get(f"/sessions/{session.id}/tasks")
    assert task_response.status_code == 200
    tasks = task_response.json()

    assert len(tasks) == 3
    assert [task["status"] for task in tasks] == ["pending", "pending", "pending"]
    assert {task["assignedAgentRole"] for task in tasks} == {
        "orchestrator",
        "frontend",
        "qa",
    }
    assert tasks[0]["dependsOnTaskIds"] == []
    assert tasks[1]["dependsOnTaskIds"] == [tasks[0]["id"]]
    assert tasks[2]["dependsOnTaskIds"] == [tasks[1]["id"]]

    frontend_task = next(task for task in tasks if task["assignedAgentRole"] == "frontend")
    assert frontend_task["intentType"] == "frontend_change"
    assert "login_page" in frontend_task["planJson"]["target"]

    with next(db_from_override()) as db:
        messages = db.exec(
            select(Message).where(
                Message.session_id == session.id,
                Message.sender_type == "orchestrator",
            )
        ).all()
        stored_tasks = db.exec(select(Task).where(Task.session_id == session.id)).all()

    assert len(messages) == 1
    assert "I created a 3-step plan" in messages[0].content_md
    assert all(json.loads(task.plan_json) for task in stored_tasks)


def test_disabled_mention_returns_user_facing_parse_error(client: TestClient) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        frontend = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        frontend.enabled = False
        db.add(frontend)
        db.commit()
        session_id = session.id

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": "@frontend adjust the button copy"},
    )

    assert response.status_code == 400
    assert "disabled" in response.json()["detail"]
