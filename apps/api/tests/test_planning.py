from collections.abc import Iterator
import json
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.external_workspaces import (
    ExternalWorkspaceRegistration,
    register_external_project_target,
)
from app.main import app, get_db
from app.main import _should_auto_start_task
from app.models import Agent, Message, Session, Task, Workspace
from app.agent_runtime_config import RuntimeRoleConfig, upsert_runtime_config
from app.config import Settings
from app.planner_providers import FakePlannerProvider, OpenAIResponsesPlannerProvider
import app.planning as planning_module
from app.planning import (
    MentionParseError,
    parse_app_contract_intent,
    parse_followup_change,
    parse_frontend_intent,
    parse_mentions,
)
from app.plan_validator import PlanValidationError, validate_task_graph
from app.planner_service import build_plan_draft
from app.task_graph_builder import TaskGraphTaskSpec
from app.target_registry import (
    AGENTHUB_PLATFORM_TARGET_ID,
    DEMO_BACKEND_TARGET_ID,
    DEMO_FRONTEND_TARGET_ID,
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
    assert [task["status"] for task in tasks] == [
        "completed",
        "pending",
        "waiting_dependency",
    ]
    assert {task["assignedAgentRole"] for task in tasks} == {
        "orchestrator",
        "frontend",
        "qa",
    }
    assert tasks[0]["dependsOnTaskIds"] == []
    assert tasks[1]["dependsOnTaskIds"] == [tasks[0]["id"]]
    assert tasks[2]["dependsOnTaskIds"] == [tasks[1]["id"]]
    assert tasks[0]["planJson"]["scheduler"]["state"] == "completed"
    assert tasks[1]["planJson"]["scheduler"]["state"] == "ready"
    assert tasks[1]["planJson"]["scheduler"]["blockingDependencyIds"] == []
    assert tasks[2]["planJson"]["scheduler"]["state"] == "waiting_dependency"
    assert tasks[2]["planJson"]["scheduler"]["blockingDependencyIds"] == [tasks[1]["id"]]

    frontend_task = next(task for task in tasks if task["assignedAgentRole"] == "frontend")
    assert frontend_task["intentType"] == "frontend_change"
    assert "login_page" in frontend_task["planJson"]["target"]
    assert frontend_task["planJson"]["planner"] == "deterministic_login_v1"
    assert frontend_task["planJson"]["expectedArtifactTypes"] == ["diff", "review"]
    assert frontend_task["planJson"]["taskGraph"]["goal"] == (
        "@orchestrator build a login page for the demo app"
    )
    plan_draft = frontend_task["planJson"]["planDraft"]
    assert plan_draft["planner"] == "deterministic_login_v1"
    assert plan_draft["plannerMode"] == "deterministic_login_v1"
    assert plan_draft["version"] == 1
    assert plan_draft["agentRole"] == "frontend"
    assert plan_draft["targetId"] == DEMO_FRONTEND_TARGET_ID
    assert plan_draft["plannedFiles"] == [
        "apps/demo/src/App.tsx",
        "apps/demo/src/styles.css",
    ]
    plan_review = frontend_task["planReviewMetadata"]
    assert plan_review["plannerMode"] == "deterministic_login_v1"
    assert "login-page demo fallback" in plan_review["rationale"]
    assert plan_review["targetId"] == DEMO_FRONTEND_TARGET_ID
    assert plan_review["plannedFiles"] == [
        "apps/demo/src/App.tsx",
        "apps/demo/src/styles.css",
    ]
    assert plan_review["taskBreakdown"]
    assert plan_review["readOnly"] is True

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
    assert contacts[0]["providerId"] == "local-scripted-mock"
    assert contacts[0]["safeForWrite"] is False
    assert contacts[0]["safeForReview"] is True

    frontend = contacts[1]
    assert frontend["displayName"] == "Frontend Agent"
    assert frontend["adapterType"] == "codex"
    assert frontend["providerId"] == "local-codex-cli"
    assert "code_write" in frontend["capabilityTags"]
    assert "demo-frontend" in frontend["supportedTargets"]
    assert frontend["supportedModes"] == ["frontend"]
    assert frontend["safeForWrite"] is True

    review = contacts[-2]
    assert review["displayName"] == "Review Agent"
    assert review["providerId"] == "local-claude-code-cli"
    assert review["status"] == "planned"
    assert review["contactType"] == "placeholder"
    assert review["safeForReview"] is True

    fallback = contacts[-1]
    assert fallback["displayName"] == "Fallback Agent / ScriptedMock"
    assert fallback["adapterType"] == "scripted_mock"
    assert fallback["providerId"] == "local-scripted-mock"
    assert fallback["contactType"] == "service"


def test_workspace_agent_profiles_return_registry_profile_contract(client: TestClient) -> None:
    with next(db_from_override()) as db:
        workspace = db.exec(select(Workspace).where(Workspace.name == "AgentHub Demo")).one()

    response = client.get(f"/workspaces/{workspace.id}/agent-profiles")

    assert response.status_code == 200
    profiles = response.json()
    assert [profile["role"] for profile in profiles] == [
        "orchestrator",
        "frontend",
        "backend",
        "qa",
        "review",
        "fallback",
    ]

    frontend = profiles[1]
    assert frontend == {
        "id": frontend["id"],
        "displayName": "Frontend Agent",
        "avatarInitials": "FE",
        "role": "frontend",
        "adapterType": "codex",
        "providerId": "local-codex-cli",
        "capabilityTags": ["code_write", "diff_analysis", "preview"],
        "supportedRoles": ["frontend"],
        "supportedTargets": ["demo-frontend", "external-frontend"],
        "supportedModes": ["frontend"],
        "safeForWrite": True,
        "safeForReview": False,
        "description": "Executes bounded frontend changes inside assigned target paths.",
        "status": "available",
    }

    backend = profiles[2]
    assert backend["supportedTargets"] == [
        "demo-backend",
        "external-backend",
        "agenthub-platform",
    ]
    assert backend["supportedRoles"] == ["backend"]
    assert backend["safeForWrite"] is True
    assert "AgentHub platform backend" in backend["description"]

    review = profiles[-2]
    assert review["id"] == "virtual-review-agent"
    assert review["role"] == "review"
    assert review["status"] == "planned"
    assert review["safeForWrite"] is False
    assert review["safeForReview"] is True

    fallback = profiles[-1]
    assert fallback["id"] == "virtual-fallback-agent"
    assert fallback["role"] == "fallback"
    assert fallback["adapterType"] == "scripted_mock"
    assert fallback["providerId"] == "local-scripted-mock"
    assert fallback["status"] == "available"


def test_workspace_agent_profiles_match_provider_assignment_matrix(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "AGENTHUB_PROVIDER_ASSIGNMENT_MATRIX",
        json.dumps(
            {
                "roles": {
                    "frontend": {
                        "adapterType": "claude_code",
                        "providerId": "local-claude-code-cli",
                    },
                    "review": {
                        "adapterType": "scripted_mock",
                        "providerId": "local-scripted-review",
                    },
                }
            }
        ),
    )
    with next(db_from_override()) as db:
        workspace = db.exec(select(Workspace).where(Workspace.name == "AgentHub Demo")).one()

    response = client.get(f"/workspaces/{workspace.id}/agent-profiles")

    assert response.status_code == 200
    profiles = response.json()
    frontend = next(profile for profile in profiles if profile["role"] == "frontend")
    qa = next(profile for profile in profiles if profile["role"] == "qa")
    review = next(profile for profile in profiles if profile["role"] == "review")

    assert frontend["adapterType"] == "claude_code"
    assert frontend["providerId"] == "local-claude-code-cli"
    assert frontend["supportedRoles"] == ["frontend"]
    assert qa["adapterType"] == "scripted_mock"
    assert qa["providerId"] == "local-scripted-review"
    assert qa["supportedRoles"] == ["qa", "review"]
    assert review["providerId"] == "local-scripted-review"
    assert review["status"] == "planned"


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


def test_plan_draft_boundary_captures_task_graph_contract() -> None:
    specs = [
        TaskGraphTaskSpec(
            title="Plan the demo",
            intent_type="planning",
            role="orchestrator",
            priority=0,
            plan={"target": "login_page"},
            expected_artifact_types=["plan"],
        ),
        TaskGraphTaskSpec(
            title="Build the demo",
            intent_type="frontend_change",
            role="frontend",
            priority=1,
            plan={
                "target": "login_page",
                "files": ["apps/demo/src/App.tsx", "apps/demo/src/styles.css"],
            },
            expected_artifact_types=["diff", "review"],
        ),
    ]

    draft = build_plan_draft(
        goal="@orchestrator build a login page for the demo app",
        intent="login_page",
        planner="deterministic_login_v1",
        task_specs=specs,
    )

    metadata = draft.to_metadata()
    assert metadata["planId"].startswith("plan-deterministic_login_v1-")
    assert metadata["version"] == 1
    assert metadata["taskGraph"]["tasks"][1]["dependsOn"] == [
        "1-orchestrator-planning"
    ]
    assert metadata["dependencyEdges"] == [
        {
            "from": "1-orchestrator-planning",
            "to": "2-frontend-frontend_change",
        }
    ]
    assert metadata["agentRole"] == "frontend"
    assert metadata["targetId"] == DEMO_FRONTEND_TARGET_ID
    assert metadata["plannedFiles"] == [
        "apps/demo/src/App.tsx",
        "apps/demo/src/styles.css",
    ]
    assert "login-page demo fallback" in metadata["rationale"]
    assert metadata["plannerMode"] == "deterministic_login_v1"
    assert metadata["acceptanceCriteria"] == []


def test_plan_validator_rejects_unsafe_task_graph_files() -> None:
    with pytest.raises(PlanValidationError, match="unsupported target files"):
        validate_task_graph(
            [
                TaskGraphTaskSpec(
                    title="Unsafe platform edit",
                    intent_type="frontend_change",
                    role="frontend",
                    priority=0,
                    plan={"files": ["apps/api/app/main.py"]},
                    expected_artifact_types=["diff"],
                )
            ]
        )


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
    assert frontend_plan["planDraft"]["planner"] == "dynamic_manager_v1"
    assert frontend_plan["planDraft"]["agentRole"] == "frontend"
    assert frontend_plan["planDraft"]["targetId"] == DEMO_FRONTEND_TARGET_ID

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
    assert task["planJson"]["plannerFallback"] == {
        "attemptedPlanner": "llm_v1",
        "reason": "disabled",
        "providerId": "disabled",
        "providerType": "disabled",
        "plannerSource": "disabled",
        "status": "disabled",
    }
    assert task["planJson"]["plannerSource"] == "fallback"
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


def test_disabled_llm_router_returns_friendly_chat_fallback_without_task(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        planning_module,
        "get_settings",
        lambda: Settings(
            llm_planner_enabled=False,
            llm_planner_provider="disabled",
        ),
    )

    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        session_id = session.id

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": "你好"},
    )

    assert response.status_code == 201
    assert client.get(f"/sessions/{session_id}/tasks").json() == []

    with next(db_from_override()) as db:
        messages = db.exec(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at)
        ).all()

    assert messages[-1].sender_type == "orchestrator"
    assert "不会为这条普通聊天创建代码任务" in messages[-1].content_md


def test_no_mention_message_uses_configured_llm_planner_provider(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        planning_module,
        "get_settings",
        lambda: Settings(
            llm_planner_enabled=True,
            llm_planner_provider="claude_cli",
        ),
    )
    monkeypatch.setattr(
        planning_module,
        "resolve_planner_provider",
        lambda settings, **_kwargs: FakePlannerProvider(
            provider_id="fake-llm-planner",
            payload={
                "planId": "plan-breakout",
                "planner": "llm_v1",
                "plannerMode": "llm_v1",
                "rationale": "A bounded frontend task can implement Breakout.",
                "acceptanceCriteria": ["Game is playable"],
                "validationExpectations": ["pnpm build"],
                "tasks": [
                    {
                        "title": "Build Breakout game",
                        "role": "frontend",
                        "targetId": DEMO_FRONTEND_TARGET_ID,
                        "intentType": "frontend_change",
                        "plannedFiles": ["apps/demo/src/App.tsx"],
                        "dependsOn": [],
                        "expectedArtifactTypes": ["diff", "review"],
                        "acceptanceCriteria": ["Keyboard controls work"],
                        "validationExpectations": ["pnpm build"],
                        "riskLevel": "medium",
                        "requiresApproval": False,
                    }
                ],
            },
        ),
    )
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        session_id = session.id

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": "帮我在当前前端项目里实现一个 Breakout / 打砖块游戏"},
    )

    assert response.status_code == 201
    tasks = client.get(f"/sessions/{session_id}/tasks").json()

    assert len(tasks) == 1
    task = tasks[0]
    assert task["status"] == "pending"
    assert task["assignedAgentRole"] == "frontend"
    assert task["planJson"]["planner"] == "llm_v1"
    assert task["planJson"]["plannerProviderId"] == "fake-llm-planner"
    assert task["planJson"]["plannerEvidence"]["plannerSource"] == "fake_test"
    assert task["planJson"]["originalRequest"] == "帮我在当前前端项目里实现一个 Breakout / 打砖块游戏"


def test_llm_task_plan_bypasses_legacy_signal_gates(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        planning_module,
        "get_settings",
        lambda: Settings(
            llm_planner_enabled=True,
            llm_planner_provider="claude_cli",
        ),
    )
    monkeypatch.setattr(
        planning_module,
        "resolve_planner_provider",
        lambda settings, **_kwargs: FakePlannerProvider(
            provider_id="fake-llm-planner",
            payload={
                "planId": "plan-breakout",
                "planner": "llm_v1",
                "plannerMode": "llm_v1",
                "rationale": "A bounded frontend task can implement Breakout.",
                "acceptanceCriteria": ["Game is playable"],
                "validationExpectations": ["pnpm build"],
                "tasks": [
                    {
                        "title": "Build Breakout game",
                        "role": "frontend",
                        "targetId": DEMO_FRONTEND_TARGET_ID,
                        "intentType": "frontend_change",
                        "plannedFiles": ["apps/demo/src/App.tsx"],
                        "dependsOn": [],
                        "expectedArtifactTypes": ["diff", "review"],
                        "acceptanceCriteria": ["Keyboard controls work"],
                        "validationExpectations": ["pnpm build"],
                        "riskLevel": "medium",
                        "requiresApproval": False,
                    }
                ],
            },
        ),
    )

    def fail_if_called(_content: str) -> bool:
        raise AssertionError("legacy signal gate should not run for LLM task_plan")

    monkeypatch.setattr(planning_module, "_is_safe_demo_frontend_request", fail_if_called)
    monkeypatch.setattr(planning_module, "_is_safe_external_frontend_request", fail_if_called)
    monkeypatch.setattr(planning_module, "_is_passthrough_frontend_request", fail_if_called)
    monkeypatch.setattr(planning_module, "_is_unsupported_broad_request", fail_if_called)

    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        session_id = session.id

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": "帮我做打砖块"},
    )

    assert response.status_code == 201
    tasks = client.get(f"/sessions/{session_id}/tasks").json()
    assert len(tasks) == 1
    assert tasks[0]["planJson"]["planner"] == "llm_v1"
    assert tasks[0]["planJson"]["plannerProviderId"] == "fake-llm-planner"


def test_llm_assistant_reply_creates_orchestrator_message_without_task(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        planning_module,
        "get_settings",
        lambda: Settings(
            llm_planner_enabled=True,
            llm_planner_provider="claude_cli",
        ),
    )
    monkeypatch.setattr(
        planning_module,
        "resolve_planner_provider",
        lambda settings, **_kwargs: FakePlannerProvider(
            provider_id="fake-llm-planner",
            payload={
                "outcomeType": "assistant_reply",
                "reply": "你好，我可以帮你规划任务、调用编码 Agent、生成 diff、预览和部署证据。",
                "riskLevel": "low",
                "reason": "Pure greeting.",
                "plannerProvider": {"providerId": "fake-llm-planner"},
                "validationResult": "not_required",
            },
        ),
    )

    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        session_id = session.id

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": "你好"},
    )

    assert response.status_code == 201
    assert client.get(f"/sessions/{session_id}/tasks").json() == []

    with next(db_from_override()) as db:
        messages = db.exec(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at)
        ).all()

    assert [message.sender_type for message in messages] == ["user", "orchestrator"]
    assert messages[-1].content_md.startswith("你好")
    assert messages[-1].message_kind == "chat"


def test_api_planner_assistant_reply_creates_orchestrator_message_without_task(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        planning_module,
        "get_settings",
        lambda: Settings(
            llm_planner_enabled=True,
            llm_planner_provider="openai_api",
        ),
    )
    monkeypatch.setattr(
        planning_module,
        "resolve_planner_provider",
        lambda settings, **_kwargs: OpenAIResponsesPlannerProvider(
            http_client=FakePlannerHttpClient(
                {
                    "output_text": json.dumps(
                        {
                            "outcomeType": "assistant_reply",
                            "reply": "你好，我可以聊天，也可以在需要时规划代码任务。",
                            "riskLevel": "low",
                            "reason": "Pure greeting.",
                            "plannerProvider": {"providerId": "openai-api-planner"},
                            "validationResult": "not_required",
                        }
                    )
                }
            ),
            api_key_env="OPENAI_API_KEY",
            environ={"OPENAI_API_KEY": "test-secret-value"},
        ),
    )

    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        session_id = session.id

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": "你好"},
    )

    assert response.status_code == 201
    assert client.get(f"/sessions/{session_id}/tasks").json() == []

    with next(db_from_override()) as db:
        messages = db.exec(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at)
        ).all()
        assert db.exec(select(Task)).all() == []

    assert [message.sender_type for message in messages] == ["user", "orchestrator"]
    assert messages[-1].content_md.startswith("你好")


def test_conversation_task_plan_creates_validated_task(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        planning_module,
        "get_settings",
        lambda: Settings(
            llm_planner_enabled=True,
            llm_planner_provider="claude_cli",
        ),
    )
    monkeypatch.setattr(
        planning_module,
        "resolve_planner_provider",
        lambda settings, **_kwargs: FakePlannerProvider(
            provider_id="fake-llm-planner",
            payload={
                "outcomeType": "task_plan",
                "reply": None,
                "riskLevel": "medium",
                "reason": "A frontend game request should become a validated task plan.",
                "plannerProvider": {"providerId": "fake-llm-planner"},
                "validationResult": "pending",
                "planDraft": {
                    "planId": "plan-breakout",
                    "planner": "llm_v1",
                    "plannerMode": "llm_v1",
                    "rationale": "A bounded frontend task can implement Breakout.",
                    "acceptanceCriteria": ["Game is playable"],
                    "validationExpectations": ["pnpm build"],
                    "tasks": [
                        {
                            "title": "Build Breakout game",
                            "role": "frontend",
                            "targetId": DEMO_FRONTEND_TARGET_ID,
                            "intentType": "frontend_change",
                            "plannedFiles": ["apps/demo/src/App.tsx"],
                            "dependsOn": [],
                            "expectedArtifactTypes": ["diff", "review"],
                            "acceptanceCriteria": ["Keyboard controls work"],
                            "validationExpectations": ["pnpm build"],
                            "riskLevel": "medium",
                            "requiresApproval": False,
                        }
                    ],
                },
            },
        ),
    )

    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        session_id = session.id

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": "帮我做打砖块"},
    )

    assert response.status_code == 201
    tasks = client.get(f"/sessions/{session_id}/tasks").json()
    assert len(tasks) == 1
    task = tasks[0]
    assert task["assignedAgentRole"] == "frontend"
    assert task["planJson"]["planner"] == "llm_v1"
    assert task["planJson"]["planDraft"]["plannerMode"] == "llm_v1"
    assert task["planJson"]["planDraft"]["acceptanceCriteria"] == ["Game is playable"]
    assert task["planJson"]["plannerEvidence"]["validationResult"] == "passed"


@pytest.mark.parametrize(
    ("outcome_type", "request_text", "reply_text"),
    [
        ("clarification", "帮我改一下", "你想修改哪个目标项目和功能？"),
        ("refusal", "修改 /etc/hosts", "我不能修改受保护的系统路径。"),
        ("approval_required", "进入平台维护模式修改 apps/api", "这需要显式平台维护审批。"),
    ],
)
def test_non_task_conversation_outcomes_do_not_create_tasks(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    outcome_type: str,
    request_text: str,
    reply_text: str,
) -> None:
    monkeypatch.setattr(
        planning_module,
        "get_settings",
        lambda: Settings(
            llm_planner_enabled=True,
            llm_planner_provider="claude_cli",
        ),
    )
    monkeypatch.setattr(
        planning_module,
        "resolve_planner_provider",
        lambda settings, **_kwargs: FakePlannerProvider(
            provider_id="fake-llm-planner",
            payload={
                "outcomeType": outcome_type,
                "reply": reply_text,
                "riskLevel": "high" if outcome_type != "clarification" else "low",
                "reason": "Non-task safety outcome.",
                "plannerProvider": {"providerId": "fake-llm-planner"},
                "validationResult": "not_required",
            },
        ),
    )

    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        session_id = session.id

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": request_text},
    )

    assert response.status_code == 201
    assert client.get(f"/sessions/{session_id}/tasks").json() == []

    with next(db_from_override()) as db:
        messages = db.exec(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at)
        ).all()

    assert messages[-1].sender_type == "orchestrator"
    assert messages[-1].content_md == reply_text


def test_followup_message_still_routes_through_llm_router(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, bool] = {"called": False}
    monkeypatch.setattr(
        planning_module,
        "get_settings",
        lambda: Settings(
            llm_planner_enabled=True,
            llm_planner_provider="claude_cli",
        ),
    )

    def fake_resolver(settings: Settings, **_kwargs) -> FakePlannerProvider:
        captured["called"] = True
        return FakePlannerProvider(
            provider_id="fake-llm-planner",
            payload={
                "outcomeType": "assistant_reply",
                "reply": "我会基于当前任务上下文继续处理。",
                "riskLevel": "low",
                "reason": "Follow-up routed through LLM.",
                "plannerProvider": {"providerId": "fake-llm-planner"},
                "validationResult": "not_required",
            },
        )

    monkeypatch.setattr(planning_module, "resolve_planner_provider", fake_resolver)

    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        frontend_agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        task = Task(
            session_id=session.id,
            title="Existing frontend task",
            intent_type="frontend_change",
            status="completed",
            assigned_agent_id=frontend_agent.id,
            plan_json=json.dumps({"planner": "llm_v1"}),
        )
        db.add(task)
        db.commit()
        session_id = session.id

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": "继续把按钮加大一点"},
    )

    assert response.status_code == 201
    assert captured["called"] is True
    tasks = client.get(f"/sessions/{session_id}/tasks").json()
    assert len(tasks) == 1


def test_runtime_config_selects_planner_provider_for_no_mention_message(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str | None] = {}
    monkeypatch.setattr(
        planning_module,
        "get_settings",
        lambda: Settings(
            llm_planner_enabled=True,
            llm_planner_provider="disabled",
        ),
    )

    def fake_resolver(settings: Settings, **kwargs: Optional[str]) -> FakePlannerProvider:
        captured["provider_id"] = kwargs.get("provider_id")
        captured["adapter_type"] = kwargs.get("adapter_type")
        return FakePlannerProvider(
            provider_id="runtime-planner-test",
            payload={
                "outcomeType": "task_plan",
                "reply": None,
                "riskLevel": "medium",
                "reason": "Runtime planner config selected the provider.",
                "plannerProvider": {"providerId": "runtime-planner-test"},
                "validationResult": "pending",
                "planDraft": {
                    "planId": "plan-runtime-config",
                    "planner": "llm_v1",
                    "plannerMode": "llm_v1",
                    "rationale": "Create one frontend task from the configured planner.",
                    "acceptanceCriteria": ["Task is created"],
                    "validationExpectations": ["pnpm build"],
                    "tasks": [
                        {
                            "title": "Build settings-aware frontend",
                            "role": "frontend",
                            "targetId": DEMO_FRONTEND_TARGET_ID,
                            "intentType": "frontend_change",
                            "plannedFiles": ["apps/demo/src/App.tsx"],
                            "dependsOn": [],
                            "expectedArtifactTypes": ["diff"],
                            "acceptanceCriteria": ["Task is created"],
                            "validationExpectations": ["pnpm build"],
                            "riskLevel": "medium",
                            "requiresApproval": False,
                        }
                    ],
                },
            },
        )

    monkeypatch.setattr(planning_module, "resolve_planner_provider", fake_resolver)
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        session_id = session.id
        upsert_runtime_config(
            db,
            session.workspace_id,
            {
                "planner": RuntimeRoleConfig(
                    role="planner",
                    agent_profile_id="agent-orchestrator",
                    provider_id="claude-cli-planner",
                    adapter_type="claude_cli",
                    mode="read_only",
                    enabled=True,
                    fallback_policy="deterministic",
                )
            },
        )

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": "请规划一个小功能"},
    )

    assert response.status_code == 201
    tasks = client.get(f"/sessions/{session_id}/tasks").json()

    assert captured == {
        "provider_id": "claude-cli-planner",
        "adapter_type": "claude_cli",
    }
    assert tasks[0]["planJson"]["plannerProviderId"] == "runtime-planner-test"
    assert (
        tasks[0]["planJson"]["plannerEvidence"]["runtimeConfigResolution"]["providerId"]
        == "claude-cli-planner"
    )
    assert (
        tasks[0]["planJson"]["runtimeConfigResolution"]["configSource"]
        == "workspace"
    )


def test_auto_start_policy_allows_registered_target_allowed_paths(
    client: TestClient,
) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        frontend_agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        task = Task(
            session_id=session.id,
            title="Frontend: add game component",
            intent_type="frontend_change",
            status="pending",
            assigned_agent_id=frontend_agent.id,
            plan_json=json.dumps({}),
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        assert _should_auto_start_task(
            db,
            task,
            {
                "autoStart": True,
                "targetId": DEMO_FRONTEND_TARGET_ID,
                "safeTarget": "apps/demo/src",
                "files": [
                    "apps/demo/src/App.tsx",
                    "apps/demo/src/game/Breakout.tsx",
                ],
            },
        ) is True
        assert _should_auto_start_task(
            db,
            task,
            {
                "autoStart": True,
                "targetId": DEMO_FRONTEND_TARGET_ID,
                "safeTarget": "apps/demo/src",
                "files": ["apps/demo-api/app/main.py"],
            },
        ) is False


def test_no_mention_breakout_request_routes_to_passthrough_frontend_task(
    client: TestClient,
) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()

    request = (
        "帮我在当前前端项目里实现一个 Breakout / 打砖块游戏，要求可以用键盘控制挡板，"
        "球能反弹，能击碎砖块，有得分、胜利/失败状态和重新开始按钮。"
    )
    response = client.post(
        f"/sessions/{session.id}/messages",
        json={"contentMd": request},
    )
    task_response = client.get(f"/sessions/{session.id}/tasks")
    tasks = task_response.json()

    assert response.status_code == 201
    assert len(tasks) == 1
    task = tasks[0]
    assert task["assignedAgentRole"] == "frontend"
    assert task["planJson"]["planner"] == "passthrough_v1"
    assert task["planJson"]["plannerMode"] == "passthrough_v1"
    assert task["planJson"]["instructionMode"] == "passthrough_v1"
    assert task["planJson"]["originalRequest"] == request
    assert task["planJson"]["targetId"] == DEMO_FRONTEND_TARGET_ID
    assert task["planJson"]["autoStart"] is True
    assert "Breakout" in task["title"]
    assert task["planReviewMetadata"]["plannerMode"] == "passthrough_v1"
    assert "original request" in task["planReviewMetadata"]["rationale"]


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
    assert [task["status"] for task in tasks] == [
        "completed",
        "running",
        "waiting_dependency",
        "waiting_dependency",
    ]
    assert tasks[0]["dependsOnTaskIds"] == []
    assert tasks[1]["dependsOnTaskIds"] == [tasks[0]["id"]]
    assert tasks[2]["dependsOnTaskIds"] == [tasks[1]["id"]]
    assert tasks[3]["dependsOnTaskIds"] == [tasks[2]["id"]]
    assert tasks[0]["planJson"]["scheduler"]["state"] == "completed"
    assert tasks[1]["planJson"]["scheduler"]["state"] == "ready"
    assert tasks[1]["planJson"]["scheduler"]["blockingDependencyIds"] == []
    assert len(tasks[1]["taskRuns"]) == 1
    assert tasks[1]["taskRuns"][0]["state"] == "queued"
    assert tasks[2]["planJson"]["scheduler"]["state"] == "waiting_dependency"
    assert tasks[2]["planJson"]["scheduler"]["blockingDependencyIds"] == [tasks[1]["id"]]
    assert tasks[3]["planJson"]["scheduler"]["state"] == "waiting_dependency"
    assert tasks[3]["planJson"]["scheduler"]["blockingDependencyIds"] == [tasks[2]["id"]]

    contract = tasks[0]["planJson"]["appContract"]
    contract_id = contract["contractId"]
    assert contract["appName"] == "Mini CRM Contacts"
    assert contract["appType"] == "mini_crm_contacts"
    assert contract["userGoal"] == "帮我做一个 mini CRM，包含联系人和备注"
    assert contract["frontendTargetId"] == DEMO_FRONTEND_TARGET_ID
    assert contract["backendTargetId"] == DEMO_BACKEND_TARGET_ID
    assert contract["backendTarget"] == "apps/demo-api"
    assert contract["frontendTarget"] == "apps/demo"
    assert contract["backendAllowedPaths"] == ["apps/demo-api"]
    assert contract["frontendAllowedPaths"] == ["apps/demo/src"]
    assert contract["backendBaseUrl"] == "http://127.0.0.1:5174"
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

    for index, task in enumerate(tasks):
        if index != 1:
            assert task["taskRuns"] == []
        assert task["planJson"]["planner"] == "contract_first_v1"
        assert task["planJson"]["contractId"] == contract_id
        assert task["planJson"]["appContract"] == contract
        assert task["planJson"]["taskGraph"]["planner"] == "contract_first_v1"
        assert task["planJson"]["planDraft"]["planner"] == "contract_first_v1"
        assert task["planJson"]["planDraft"]["dependencyEdges"]

    backend = tasks[1]
    frontend = tasks[2]
    review = tasks[3]
    assert backend["planJson"]["targetId"] == DEMO_BACKEND_TARGET_ID
    assert backend["planJson"]["autoStart"] is True
    assert backend["planJson"]["backendTargetId"] == DEMO_BACKEND_TARGET_ID
    assert backend["planJson"]["frontendTargetId"] == DEMO_FRONTEND_TARGET_ID
    assert backend["planJson"]["safeTarget"] == "apps/demo-api"
    assert backend["planJson"]["files"] == [
        "apps/demo-api/app/main.py",
        "apps/demo-api/tests/test_contacts.py",
    ]
    assert frontend["planJson"]["targetId"] == DEMO_FRONTEND_TARGET_ID
    assert frontend["planJson"]["autoStart"] is True
    assert frontend["planJson"]["frontendTargetId"] == DEMO_FRONTEND_TARGET_ID
    assert frontend["planJson"]["backendTargetId"] == DEMO_BACKEND_TARGET_ID
    assert frontend["planJson"]["frontendTarget"] == "apps/demo"
    assert frontend["planJson"]["safeTarget"] == "apps/demo/src"
    assert review["planJson"]["targetId"] == DEMO_FRONTEND_TARGET_ID
    assert review["planJson"]["frontendTargetId"] == DEMO_FRONTEND_TARGET_ID
    assert review["planJson"]["backendTargetId"] == DEMO_BACKEND_TARGET_ID
    assert review["planJson"]["target"] == "contract_review"
    assert review["planJson"]["appContract"]["contractId"] == contract_id
    assert frontend["planJson"]["taskGraph"]["tasks"][1]["targetId"] == DEMO_BACKEND_TARGET_ID
    assert frontend["planJson"]["taskGraph"]["tasks"][2]["targetId"] == DEMO_FRONTEND_TARGET_ID

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


def test_direct_frontend_mention_includes_safe_referenced_demo_file(
    client: TestClient,
) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        session_id = session.id

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={
            "contentMd": (
                "@frontend fix apps/demo/src/components/BreakoutGame.tsx "
                "for the demo app TypeScript build"
            )
        },
    )

    assert response.status_code == 201
    tasks = client.get(f"/sessions/{session_id}/tasks").json()

    assert len(tasks) == 1
    assert "apps/demo/src/components/BreakoutGame.tsx" in tasks[0]["planJson"]["files"]


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
    assert task["planJson"]["targetId"] == DEMO_BACKEND_TARGET_ID
    assert task["planJson"]["backendTargetId"] == DEMO_BACKEND_TARGET_ID
    assert task["planJson"]["safeTarget"] == "apps/demo-api"
    assert task["planJson"]["files"] == [
        "apps/demo-api/app/main.py",
        "apps/demo-api/tests/test_contacts.py",
    ]
    assert task["planJson"]["originalRequest"] == "@backend add a contacts endpoint"


def test_direct_frontend_mention_uses_active_external_target(
    client: TestClient,
    tmp_path,
) -> None:
    with next(db_from_override()) as db:
        workspace = db.exec(select(Workspace).where(Workspace.name == "AgentHub Demo")).one()
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        project = tmp_path / "external-app"
        (project / "src").mkdir(parents=True)
        (project / "src" / "App.tsx").write_text("export default function App() { return null }\n")
        register_external_project_target(
            db,
            workspace,
            ExternalWorkspaceRegistration(
                target_id="external-planning-app",
                name="External Planning App",
                root_path=str(project),
                project_type="vite-react",
                allowed_paths=["src"],
                dev_command="pnpm dev",
                test_command="pnpm test",
                package_manager="pnpm",
                detected_framework="vite-react",
            ),
        )
        session.active_frontend_target_id = "external-planning-app"
        db.add(session)
        db.commit()
        session_id = session.id

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": "@frontend update the app hero copy"},
    )

    assert response.status_code == 201
    task = client.get(f"/sessions/{session_id}/tasks").json()[0]

    assert task["assignedAgentRole"] == "frontend"
    assert task["intentType"] == "frontend_change"
    assert task["planJson"]["targetId"] == "external-planning-app"
    assert task["planJson"]["frontendTargetId"] == "external-planning-app"
    assert task["planJson"]["safeTarget"] == "src"
    assert task["planJson"]["files"] == ["src/App.tsx"]
    assert task["planJson"]["autoStart"] is False
    assert task["planJson"]["originalRequest"] == "@frontend update the app hero copy"


def test_orchestrator_can_create_auto_start_external_frontend_task(
    client: TestClient,
    tmp_path,
) -> None:
    with next(db_from_override()) as db:
        workspace = db.exec(select(Workspace).where(Workspace.name == "AgentHub Demo")).one()
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        project = tmp_path / "external-dashboard"
        (project / "src").mkdir(parents=True)
        (project / "src" / "App.tsx").write_text("export default function App() { return null }\n")
        register_external_project_target(
            db,
            workspace,
            ExternalWorkspaceRegistration(
                target_id="external-dashboard",
                name="External Dashboard",
                root_path=str(project),
                project_type="vite-react",
                allowed_paths=["src"],
            ),
        )
        session.active_frontend_target_id = "external-dashboard"
        db.add(session)
        db.commit()
        session_id = session.id

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": "build a dashboard page with cards"},
    )

    assert response.status_code == 201
    task = client.get(f"/sessions/{session_id}/tasks").json()[0]

    assert task["assignedAgentRole"] == "frontend"
    assert task["status"] == "running"
    assert len(task["taskRuns"]) == 1
    assert task["taskRuns"][0]["state"] == "queued"
    assert task["planJson"]["planner"] == "orchestrator_external_target_v1"
    assert task["planJson"]["routing"] == "orchestrator_default"
    assert task["planJson"]["targetId"] == "external-dashboard"
    assert task["planJson"]["autoStart"] is True


def test_explicit_platform_mode_request_creates_approval_gated_platform_task(
    client: TestClient,
) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Planning session")).one()
        session_id = session.id

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"contentMd": "@backend platform mode update AgentHub API health metadata"},
    )

    assert response.status_code == 201
    tasks = client.get(f"/sessions/{session_id}/tasks").json()

    assert len(tasks) == 1
    task = tasks[0]
    assert task["assignedAgentRole"] == "backend"
    assert task["intentType"] == "platform_maintenance"
    assert task["status"] == "pending"
    assert task["taskRuns"] == []
    assert task["planJson"]["planner"] == "platform_maintenance_v1"
    assert task["planJson"]["routing"] == "explicit_platform_mode"
    assert task["planJson"]["targetId"] == AGENTHUB_PLATFORM_TARGET_ID
    assert task["planJson"]["platformMode"] is True
    assert task["planJson"]["requiresApproval"] is True
    assert task["planJson"]["safeTarget"] == "apps/api"
    assert task["planJson"]["validationExpectations"] == ["pnpm check", "pnpm test"]

    with next(db_from_override()) as db:
        messages = db.exec(
            select(Message).where(
                Message.session_id == session_id,
                Message.sender_type == "orchestrator",
            )
        ).all()

    assert len(messages) == 1
    assert "requires approval" in messages[0].content_md


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


class FakePlannerHttpClient:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response

    def post_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, object],
        timeout: int,
    ) -> dict[str, object]:
        return self.response
