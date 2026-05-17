from collections.abc import Iterator
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.main import app, get_db
from app.models import Agent, Message, Session, Task, Workspace
from app.planning import MentionParseError, parse_followup_change, parse_mentions


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


def test_parse_followup_change_supports_english_and_chinese_copy_requests() -> None:
    button = parse_followup_change("change the primary button text to Sign in")
    chinese_button = parse_followup_change("把按钮文案改成 Continue")
    title = parse_followup_change("把标题改成 Welcome back")

    assert button is not None
    assert button.target == "primary_action_button_text"
    assert button.target_text == "Sign in"
    assert chinese_button is not None
    assert chinese_button.target == "primary_action_button_text"
    assert chinese_button.target_text == "Continue"
    assert title is not None
    assert title.target == "demo_heading_text"
    assert title.target_text == "Welcome back"


def test_followup_message_creates_single_frontend_task_in_same_session(
    client: TestClient,
) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        session_id = session.id

    first_response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": "@orchestrator build a login page for the demo app"},
    )
    followup_response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": "把按钮文案改成 Sign in"},
    )

    assert first_response.status_code == 201
    assert followup_response.status_code == 201

    task_response = client.get(f"/sessions/{session_id}/tasks")
    assert task_response.status_code == 200
    tasks = task_response.json()
    followup = tasks[-1]

    assert len(tasks) == 4
    assert followup["sessionId"] == session_id
    assert followup["assignedAgentRole"] == "frontend"
    assert followup["intentType"] == "frontend_change"
    assert followup["title"] == "Change primary button text to Sign in"
    assert followup["planJson"]["target"] == "primary_action_button_text"
    assert followup["planJson"]["targetText"] == "Sign in"
    assert followup["dependsOnTaskIds"] == [tasks[-2]["id"]]

    with next(db_from_override()) as db:
        messages = db.exec(
            select(Message).where(
                Message.session_id == session_id,
                Message.sender_type == "orchestrator",
            )
        ).all()

    assert len(messages) == 2
    assert "focused follow-up task" in messages[-1].content_md


def test_followup_message_without_existing_plan_is_ignored(client: TestClient) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        session_id = session.id

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": "change the primary button text to Sign in"},
    )

    assert response.status_code == 201
    assert client.get(f"/sessions/{session_id}/tasks").json() == []
