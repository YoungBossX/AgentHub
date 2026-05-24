from collections.abc import Iterator
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.main import app, get_db
from app.models import Agent, Message, Session, Task, Workspace
from app.planning import (
    MentionParseError,
    parse_app_contract_intent,
    parse_followup_change,
    parse_frontend_intent,
    parse_mentions,
)


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
        parsed = parse_mentions(db, "@orchestrator please ask @frontend and @review")

    assert parsed.roles == ["orchestrator", "frontend", "review"]


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
    assert frontend_task["planJson"]["planner"] == "deterministic_login_v1"
    assert frontend_task["planJson"]["expectedArtifactTypes"] == ["diff", "review"]
    assert frontend_task["planJson"]["taskGraph"]["goal"] == (
        "@orchestrator build a login page for the demo app"
    )

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

    ledger_response = client.get(f"/sessions/{session.id}/ledger")
    assert ledger_response.status_code == 200
    ledger = ledger_response.json()
    assert ledger["currentGoal"] == "@orchestrator build a login page for the demo app"
    assert ledger["activeAgents"] == ["orchestrator", "frontend", "qa"]
    assert ledger["latestTaskId"] == tasks[-1]["id"]
    assert "Current goal" in ledger["summaryMd"]


def test_workspace_agent_registry_returns_im_contacts(client: TestClient) -> None:
    with next(db_from_override()) as db:
        workspace = db.exec(select(Workspace).where(Workspace.name == "AgentHub Demo")).one()

    response = client.get(f"/workspaces/{workspace.id}/agents")

    assert response.status_code == 200
    contacts = response.json()

    assert [contact["role"] for contact in contacts] == [
        "orchestrator",
        "frontend",
        "backend",
        "qa",
        "review",
        "fallback",
    ]
    assert contacts[0]["displayName"] == "Manager / Orchestrator"
    assert contacts[0]["adapterType"] == "scripted_mock"
    assert contacts[0]["safeForWrite"] is False
    assert contacts[0]["safeForReview"] is True

    frontend = contacts[1]
    assert frontend["displayName"] == "Frontend Agent"
    assert frontend["adapterType"] == "codex"
    assert "Vite React" in frontend["capabilityTags"]
    assert frontend["safeForWrite"] is True

    review = contacts[-2]
    assert review["displayName"] == "Review Agent"
    assert review["status"] == "planned"
    assert review["contactType"] == "placeholder"
    assert review["safeForReview"] is True

    fallback = contacts[-1]
    assert fallback["displayName"] == "Fallback Agent / ScriptedMock"
    assert fallback["adapterType"] == "scripted_mock"
    assert fallback["contactType"] == "service"


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


def test_parse_frontend_intent_supports_bounded_p5_dynamic_intents() -> None:
    title = parse_frontend_intent("change the title to Welcome back")
    button = parse_frontend_intent("把按钮文案改成 Sign in")
    color = parse_frontend_intent("@orchestrator change the accent color to #14b8a6")
    input_field = parse_frontend_intent("add a phone number input field")
    status_text = parse_frontend_intent("add help text Use your work email")
    layout_copy = parse_frontend_intent("adjust layout copy to Fast local demo")

    assert title is not None
    assert title.target == "demo_heading_text"
    assert button is not None
    assert button.target == "primary_action_button_text"
    assert color is not None
    assert color.target == "theme_accent_color"
    assert color.files == ["apps/demo/src/styles.css"]
    assert input_field is not None
    assert input_field.target == "simple_input_field"
    assert status_text is not None
    assert status_text.target == "status_help_text"
    assert layout_copy is not None
    assert layout_copy.target == "layout_copy"


def test_parse_app_contract_intent_supports_bounded_app_types() -> None:
    todo = parse_app_contract_intent("build a todo app")
    notes = parse_app_contract_intent("帮我做一个笔记应用")
    crm = parse_app_contract_intent("帮我做一个 mini CRM，包含联系人和备注")

    assert todo is not None
    assert todo.app_type == "todo"
    assert notes is not None
    assert notes.app_type == "notes"
    assert crm is not None
    assert crm.app_type == "mini_crm_contacts"


def test_orchestrator_supported_frontend_intent_creates_dynamic_task_graph(
    client: TestClient,
) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        session_id = session.id

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": "@orchestrator change the accent color to #14b8a6"},
    )

    assert response.status_code == 201
    tasks = client.get(f"/sessions/{session_id}/tasks").json()

    assert len(tasks) == 3
    assert [task["assignedAgentRole"] for task in tasks] == [
        "orchestrator",
        "frontend",
        "qa",
    ]
    assert [task["intentType"] for task in tasks] == [
        "planning",
        "frontend_change",
        "review",
    ]
    assert tasks[1]["dependsOnTaskIds"] == [tasks[0]["id"]]
    assert tasks[2]["dependsOnTaskIds"] == [tasks[1]["id"]]

    frontend_plan = tasks[1]["planJson"]
    assert frontend_plan["planner"] == "dynamic_manager_v1"
    assert frontend_plan["intent"] == "theme_accent_color_change"
    assert frontend_plan["target"] == "theme_accent_color"
    assert frontend_plan["targetText"] == "#14b8a6"
    assert frontend_plan["files"] == ["apps/demo/src/styles.css"]
    assert frontend_plan["expectedArtifactTypes"] == ["diff", "review"]
    assert frontend_plan["taskGraph"]["goal"] == (
        "@orchestrator change the accent color to #14b8a6"
    )
    assert frontend_plan["taskGraph"]["tasks"][2]["expectedArtifactTypes"] == [
        "review"
    ]

    with next(db_from_override()) as db:
        messages = db.exec(
            select(Message).where(
                Message.session_id == session_id,
                Message.sender_type == "orchestrator",
            )
        ).all()

    assert len(messages) == 1
    assert "bounded dynamic plan" in messages[0].content_md


def test_no_mention_message_routes_to_orchestrator_and_auto_starts_demo_task(
    client: TestClient,
) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        session_id = session.id

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": "帮我把当前 demo app 改成一个 dashboard，有三张统计卡片和一个最近活动列表"},
    )

    assert response.status_code == 201
    tasks = client.get(f"/sessions/{session_id}/tasks").json()

    assert len(tasks) == 1
    task = tasks[0]
    assert task["assignedAgentRole"] == "frontend"
    assert task["intentType"] == "frontend_change"
    assert task["status"] == "running"
    assert task["title"].startswith("Frontend:")
    assert task["planJson"]["planner"] == "orchestrator_auto_run_v1"
    assert task["planJson"]["routing"] == "orchestrator_default"
    assert task["planJson"]["originalRequest"] == (
        "帮我把当前 demo app 改成一个 dashboard，有三张统计卡片和一个最近活动列表"
    )
    assert task["planJson"]["safeTarget"] == "apps/demo/src"
    assert task["taskRuns"]
    assert task["taskRuns"][0]["adapterType"] == "codex"

    with next(db_from_override()) as db:
        messages = db.exec(
            select(Message).where(
                Message.session_id == session_id,
                Message.sender_type == "orchestrator",
            )
        ).all()

    assert len(messages) == 1
    assert "started it automatically" in messages[0].content_md


def test_no_mention_mini_crm_request_creates_contract_first_task_graph(
    client: TestClient,
) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        session_id = session.id

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": "帮我做一个 mini CRM，包含联系人和备注"},
    )

    assert response.status_code == 201
    tasks = client.get(f"/sessions/{session_id}/tasks").json()

    assert len(tasks) == 4
    assert [task["assignedAgentRole"] for task in tasks] == [
        "orchestrator",
        "backend",
        "frontend",
        "qa",
    ]
    assert [task["intentType"] for task in tasks] == [
        "planning",
        "backend_change",
        "frontend_change",
        "review",
    ]
    assert [task["status"] for task in tasks] == ["pending"] * 4
    assert tasks[0]["dependsOnTaskIds"] == []
    assert tasks[1]["dependsOnTaskIds"] == [tasks[0]["id"]]
    assert tasks[2]["dependsOnTaskIds"] == [tasks[1]["id"]]
    assert tasks[3]["dependsOnTaskIds"] == [tasks[2]["id"]]

    contract = tasks[0]["planJson"]["appContract"]
    contract_id = contract["contractId"]
    assert contract["appName"] == "Mini CRM Contacts"
    assert contract["appType"] == "mini_crm_contacts"
    assert contract["userGoal"] == "帮我做一个 mini CRM，包含联系人和备注"
    assert contract["backendTarget"] == "apps/demo-api"
    assert contract["frontendTarget"] == "apps/demo"
    assert contract["demoApiBaseUrl"] == "http://127.0.0.1:5174"
    assert contract["apiRoutes"] == [
        {"method": "GET", "path": "/health", "description": "Health check"},
        {"method": "GET", "path": "/contacts", "description": "List Contact records"},
        {"method": "POST", "path": "/contacts", "description": "Create a Contact record"},
    ]
    assert (
        "Frontend app data calls must use the demo API base URL http://127.0.0.1:5174."
        in contract["validationExpectations"]
    )
    assert "notes" in [field["name"] for field in contract["fields"]]

    for task in tasks:
        assert task["taskRuns"] == []
        assert task["planJson"]["planner"] == "contract_first_v1"
        assert task["planJson"]["contractId"] == contract_id
        assert task["planJson"]["appContract"] == contract
        assert task["planJson"]["taskGraph"]["planner"] == "contract_first_v1"

    backend = tasks[1]
    frontend = tasks[2]
    review = tasks[3]
    assert backend["planJson"]["safeTarget"] == "apps/demo-api"
    assert backend["planJson"]["files"] == [
        "apps/demo-api/app/main.py",
        "apps/demo-api/tests/test_contacts.py",
    ]
    assert frontend["planJson"]["frontendTarget"] == "apps/demo"
    assert frontend["planJson"]["safeTarget"] == "apps/demo/src"
    assert review["planJson"]["target"] == "contract_review"
    assert review["planJson"]["appContract"]["contractId"] == contract_id

    with next(db_from_override()) as db:
        messages = db.exec(
            select(Message).where(
                Message.session_id == session_id,
                Message.sender_type == "orchestrator",
            )
        ).all()

    assert len(messages) == 1
    assert "contract-first plan" in messages[0].content_md
    assert contract_id in messages[0].content_md


def test_direct_frontend_mention_creates_assignment_task_without_auto_start(
    client: TestClient,
) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        session_id = session.id

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": "@frontend update the demo app hero copy"},
    )

    assert response.status_code == 201
    tasks = client.get(f"/sessions/{session_id}/tasks").json()

    assert len(tasks) == 1
    task = tasks[0]
    assert task["assignedAgentRole"] == "frontend"
    assert task["intentType"] == "frontend_change"
    assert task["status"] == "pending"
    assert task["taskRuns"] == []
    assert task["planJson"]["planner"] == "direct_assignment_v1"
    assert task["planJson"]["routing"] == "direct_mention"
    assert task["planJson"]["originalRequest"] == "@frontend update the demo app hero copy"


def test_backend_mention_creates_safe_demo_backend_task(
    client: TestClient,
) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        session_id = session.id

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": "@backend add a contacts endpoint"},
    )

    assert response.status_code == 201
    tasks = client.get(f"/sessions/{session_id}/tasks").json()

    assert len(tasks) == 1
    task = tasks[0]
    assert task["assignedAgentRole"] == "backend"
    assert task["intentType"] == "backend_change"
    assert task["status"] == "pending"
    assert task["taskRuns"] == []
    assert task["planJson"]["planner"] == "direct_assignment_v1"
    assert task["planJson"]["routing"] == "direct_mention"
    assert task["planJson"]["assignedRole"] == "backend"
    assert task["planJson"]["safeTarget"] == "apps/demo-api"
    assert task["planJson"]["files"] == [
        "apps/demo-api/app/main.py",
        "apps/demo-api/tests/test_contacts.py",
    ]
    assert task["planJson"]["originalRequest"] == "@backend add a contacts endpoint"


def test_review_mention_creates_read_only_review_assignment(
    client: TestClient,
) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        session_id = session.id

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": "@review check the latest diff"},
    )

    assert response.status_code == 201
    tasks = client.get(f"/sessions/{session_id}/tasks").json()

    assert len(tasks) == 1
    task = tasks[0]
    assert task["assignedAgentRole"] == "qa"
    assert task["intentType"] == "review"
    assert task["planJson"]["assignedRole"] == "review"
    assert task["planJson"]["expectedArtifactTypes"] == ["review"]


def test_followup_message_creates_frontend_and_review_tasks_in_same_session(
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
    followup = tasks[-2]
    review = tasks[-1]

    assert len(tasks) == 5
    assert followup["sessionId"] == session_id
    assert followup["assignedAgentRole"] == "frontend"
    assert followup["intentType"] == "frontend_change"
    assert followup["title"] == "Change primary button text to Sign in"
    assert followup["planJson"]["target"] == "primary_action_button_text"
    assert followup["planJson"]["targetText"] == "Sign in"
    assert followup["planJson"]["planner"] == "dynamic_manager_v1"
    assert followup["planJson"]["expectedArtifactTypes"] == ["diff", "review"]
    assert followup["dependsOnTaskIds"] == [tasks[-3]["id"]]
    assert review["assignedAgentRole"] == "qa"
    assert review["intentType"] == "review"
    assert review["dependsOnTaskIds"] == [followup["id"]]

    with next(db_from_override()) as db:
        messages = db.exec(
            select(Message).where(
                Message.session_id == session_id,
                Message.sender_type == "orchestrator",
            )
        ).all()

    assert len(messages) == 2
    assert "bounded dynamic plan" in messages[-1].content_md


def test_unsupported_orchestrator_request_falls_back_without_claiming_support(
    client: TestClient,
) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        session_id = session.id

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": "@orchestrator refactor the whole app into a dashboard"},
    )

    assert response.status_code == 201
    assert client.get(f"/sessions/{session_id}/tasks").json() == []


def test_unsupported_broad_saas_request_is_handled_honestly(
    client: TestClient,
) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        session_id = session.id

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": "帮我做一个生产级 SaaS，带支付、认证和多租户"},
    )

    assert response.status_code == 201
    assert client.get(f"/sessions/{session_id}/tasks").json() == []
    with next(db_from_override()) as db:
        messages = db.exec(
            select(Message).where(
                Message.session_id == session_id,
                Message.sender_type == "orchestrator",
            )
        ).all()

    assert len(messages) == 1
    assert "could not safely turn that into a demo-target task" in messages[0].content_md


def test_no_mention_bounded_request_without_existing_plan_uses_orchestrator_default(
    client: TestClient,
) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        session_id = session.id

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": "change the primary button text to Sign in"},
    )

    assert response.status_code == 201
    tasks = client.get(f"/sessions/{session_id}/tasks").json()
    assert [task["assignedAgentRole"] for task in tasks] == [
        "orchestrator",
        "frontend",
        "qa",
    ]
    assert tasks[1]["planJson"]["autoStart"] is True
    assert tasks[1]["taskRuns"]
