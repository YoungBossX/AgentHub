from collections.abc import Iterator
import json

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.llm_planner import (
    LLMPlannerError,
    build_llm_planner_input,
    create_llm_plan_tasks,
    parse_llm_plan_output,
)
from app.mission_trace import build_session_mission_trace
from app.models import Agent, Message, Session, Task, Workspace
from app.planner_providers import FakePlannerProvider, OpenAIResponsesPlannerProvider
from app.target_registry import DEMO_FRONTEND_TARGET_ID


@pytest.fixture
def db() -> Iterator[DbSession]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as session:
        workspace = Workspace(
            name="AgentHub Demo",
            repo_url="local://apps/demo",
            root_path="apps/demo",
            default_branch="main",
        )
        planning_session = Session(
            workspace_id=workspace.id,
            title="LLM planning session",
            bound_branch="main",
            worktree_path=".worktrees/llm-planning-session",
        )
        session.add(workspace)
        session.add(planning_session)
        session.add(Agent(name="Orchestrator", role="orchestrator", adapter_type="scripted_mock", provider="local"))
        session.add(Agent(name="Frontend Agent", role="frontend", adapter_type="codex", provider="local"))
        session.add(Agent(name="QA Agent", role="qa", adapter_type="scripted_mock", provider="local"))
        session.commit()
        yield session


def test_llm_planner_input_includes_context_targets_messages_and_guardrails(
    db: DbSession,
) -> None:
    message = _message(db, "Build a playable canvas game")

    planner_input = build_llm_planner_input(db, message)

    assert planner_input["originalUserRequest"] == "Build a playable canvas game"
    assert planner_input["canonicalSharedContext"]["version"] == "canonical_shared_context_v1"
    assert planner_input["recentMessages"][0]["contentMd"] == "Build a playable canvas game"
    assert any(
        target["targetId"] == DEMO_FRONTEND_TARGET_ID
        for target in planner_input["targetRegistry"]
    )
    assert ".env" in planner_input["guardrails"]["protectedPaths"]
    assert planner_input["guardrails"]["denyProductionDeploy"] is True


def test_llm_planner_input_includes_followup_mission_trace(db: DbSession) -> None:
    session = db.exec(select(Session).where(Session.title == "LLM planning session")).one()
    frontend_agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
    task = Task(
        session_id=session.id,
        title="Existing frontend task",
        intent_type="frontend_change",
        status="completed",
        assigned_agent_id=frontend_agent.id,
        plan_json=json.dumps(
            {
                "planner": "llm_v1",
                "plannerEvidence": {
                    "providerId": "test-llm-planner",
                    "plannerSource": "fake_test",
                    "validationResult": "passed",
                },
            }
        ),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    message = _message(db, "继续基于上一次结果加一个重新开始按钮")

    planner_input = build_llm_planner_input(db, message)
    mission_trace = planner_input["canonicalSharedContext"]["fields"]["missionTrace"]["value"]

    assert mission_trace["tasks"][0]["id"] == task.id
    assert mission_trace["tasks"][0]["status"] == "completed"
    assert mission_trace["tasks"][0]["plannerEvidence"]["providerId"] == "test-llm-planner"


def test_llm_planner_creates_validated_tasks_and_plan_draft(db: DbSession) -> None:
    message = _message(db, "Build a playable canvas game")
    provider = FakePlannerProvider(
        provider_id="test-llm-planner",
        payload={
            "planId": "plan-test-game",
            "planner": "llm_v1",
            "plannerMode": "llm_v1",
            "version": 1,
            "intent": "frontend_game",
            "rationale": "A single frontend task can implement the game inside the registered target.",
            "acceptanceCriteria": ["Keyboard controls work", "Score updates"],
            "validationExpectations": ["pnpm build"],
            "guardrailNotes": ["Stay inside demo-frontend allowed paths"],
            "tasks": [
                {
                        "title": "Implement playable game",
                        "intentType": "frontend_change",
                        "role": "frontend",
                        "targetId": DEMO_FRONTEND_TARGET_ID,
                        "plannedFiles": [
                            "apps/demo/src/App.tsx",
                        "apps/demo/src/styles.css",
                    ],
                        "expectedArtifactTypes": ["diff", "review"],
                        "acceptanceCriteria": ["Keyboard controls work"],
                        "validationExpectations": ["pnpm build"],
                        "riskLevel": "medium",
                        "requiresApproval": False,
                    },
                    {
                        "title": "Review playable game",
                        "intentType": "review",
                        "role": "qa",
                        "targetId": DEMO_FRONTEND_TARGET_ID,
                        "plannedFiles": [],
                        "expectedArtifactTypes": ["review"],
                        "dependsOn": ["1-frontend-frontend_change"],
                        "acceptanceCriteria": ["Review gameplay criteria"],
                        "validationExpectations": ["Inspect diff"],
                        "riskLevel": "low",
                        "requiresApproval": False,
                    },
                ],
            },
    )

    outcome = create_llm_plan_tasks(db, message, provider=provider)

    assert len(outcome.tasks) == 2
    frontend_task = outcome.tasks[0]
    frontend_plan = json.loads(frontend_task.plan_json)
    assert frontend_plan["planner"] == "llm_v1"
    assert frontend_plan["plannerProviderId"] == "test-llm-planner"
    assert frontend_plan["plannerProvider"]["providerId"] == "test-llm-planner"
    assert frontend_plan["plannerProvider"]["plannerSource"] == "fake_test"
    assert frontend_plan["llmPlanner"]["plannerSource"] == "fake_test"
    assert frontend_plan["plannerEvidence"]["plannerSource"] == "fake_test"
    assert frontend_plan["plannerEvidence"]["validationResult"] == "passed"
    assert frontend_plan["plannerEvidence"]["createdTaskIds"] == [
        task.id for task in outcome.tasks
    ]
    assert "raw_output" not in frontend_plan["plannerEvidence"]
    assert frontend_plan["originalRequest"] == "Build a playable canvas game"
    assert frontend_plan["planDraft"]["plannerMode"] == "llm_v1"
    assert frontend_plan["planDraft"]["acceptanceCriteria"] == [
        "Keyboard controls work",
        "Score updates",
    ]
    assert frontend_plan["planDraft"]["validationExpectations"] == ["pnpm build"]
    assert json.loads(outcome.tasks[1].depends_on_task_ids) == [frontend_task.id]

    trace = build_session_mission_trace(db, message.session_id)
    traced_task = next(task for task in trace.tasks if task["id"] == frontend_task.id)
    assert traced_task["plannerEvidence"]["providerId"] == "test-llm-planner"
    assert traced_task["plannerEvidence"]["plannerSource"] == "fake_test"


def test_llm_planner_normalizes_safe_dependency_aliases(db: DbSession) -> None:
    message = _message(db, "Build a playable canvas game")
    provider = FakePlannerProvider(
        payload={
            "planId": "plan-dependency-alias",
            "planner": "llm_v1",
            "plannerMode": "llm_v1",
            "intent": "frontend_game",
            "rationale": "The planner used a target-based dependency alias.",
            "acceptanceCriteria": ["Game is playable"],
            "validationExpectations": ["pnpm build"],
            "tasks": [
                {
                    "title": "Implement game",
                    "intentType": "frontend_change",
                    "role": "frontend",
                    "targetId": DEMO_FRONTEND_TARGET_ID,
                    "plannedFiles": ["apps/demo/src/App.tsx"],
                    "expectedArtifactTypes": ["diff"],
                    "acceptanceCriteria": ["Keyboard controls work"],
                    "validationExpectations": ["pnpm build"],
                    "riskLevel": "medium",
                    "requiresApproval": False,
                },
                {
                    "title": "Review game",
                    "intentType": "review",
                    "role": "qa",
                    "targetId": DEMO_FRONTEND_TARGET_ID,
                    "plannedFiles": [],
                    "expectedArtifactTypes": ["review"],
                    "dependsOn": ["1-demo-frontend-frontend_change"],
                    "acceptanceCriteria": ["Review gameplay"],
                    "validationExpectations": [],
                    "riskLevel": "low",
                    "requiresApproval": False,
                },
            ],
        },
    )

    outcome = create_llm_plan_tasks(db, message, provider=provider)

    assert json.loads(outcome.tasks[1].depends_on_task_ids) == [outcome.tasks[0].id]


def test_llm_planner_rejects_invalid_json_or_unsafe_files(db: DbSession) -> None:
    with pytest.raises(LLMPlannerError, match="invalid JSON"):
        parse_llm_plan_output("not json")

    message = _message(db, "Edit unsafe file")
    provider = FakePlannerProvider(
        payload={
            "planId": "plan-unsafe",
            "planner": "llm_v1",
            "plannerMode": "llm_v1",
            "rationale": "Unsafe file should be rejected.",
            "acceptanceCriteria": ["No unsafe paths"],
            "validationExpectations": ["none"],
            "tasks": [
                {
                    "title": "Edit platform file",
                    "intentType": "frontend_change",
                    "role": "frontend",
                    "targetId": DEMO_FRONTEND_TARGET_ID,
                    "plannedFiles": ["apps/api/app/main.py"],
                    "expectedArtifactTypes": ["diff"],
                    "acceptanceCriteria": ["Do not edit unsafe files"],
                    "riskLevel": "high",
                    "requiresApproval": False,
                }
            ],
        },
    )

    with pytest.raises(LLMPlannerError, match="unsupported target files"):
        create_llm_plan_tasks(db, message, provider=provider)


def test_api_planner_provider_output_flows_through_plan_validator(db: DbSession) -> None:
    message = _message(db, "Build a playable canvas game")
    provider = OpenAIResponsesPlannerProvider(
        http_client=FakePlannerHttpClient(
            {
                "output_text": json.dumps(
                    {
                        "outcomeType": "task_plan",
                        "reason": "Create a validated frontend task.",
                        "planDraft": _valid_plan_payload(
                            [
                                {
                                    "title": "Implement playable game",
                                    "intentType": "frontend_change",
                                    "role": "frontend",
                                    "targetId": DEMO_FRONTEND_TARGET_ID,
                                    "plannedFiles": ["apps/demo/src/App.tsx"],
                                    "expectedArtifactTypes": ["diff", "review"],
                                    "acceptanceCriteria": ["Keyboard controls work"],
                                    "validationExpectations": ["pnpm build"],
                                    "riskLevel": "medium",
                                    "requiresApproval": False,
                                }
                            ]
                        ),
                    }
                )
            }
        ),
        api_key_env="OPENAI_API_KEY",
        environ={"OPENAI_API_KEY": "test-secret-value"},
    )

    outcome = create_llm_plan_tasks(db, message, provider=provider)

    assert len(outcome.tasks) == 1
    plan = json.loads(outcome.tasks[0].plan_json)
    assert plan["plannerProvider"]["providerType"] == "openai_responses"
    assert plan["plannerEvidence"]["validationResult"] == "passed"
    assert "test-secret-value" not in json.dumps(plan)


def test_api_planner_provider_unsafe_plan_is_rejected_before_persistence(
    db: DbSession,
) -> None:
    message = _message(db, "Edit unsafe file")
    provider = OpenAIResponsesPlannerProvider(
        http_client=FakePlannerHttpClient(
            {
                "output_text": json.dumps(
                    {
                        "outcomeType": "task_plan",
                        "reason": "This unsafe plan must not persist.",
                        "planDraft": _valid_plan_payload(
                            [
                                {
                                    "title": "Edit unsafe file",
                                    "intentType": "frontend_change",
                                    "role": "frontend",
                                    "targetId": DEMO_FRONTEND_TARGET_ID,
                                    "plannedFiles": ["apps/api/app/main.py"],
                                    "expectedArtifactTypes": ["diff"],
                                    "acceptanceCriteria": ["Should be rejected"],
                                    "validationExpectations": ["pnpm build"],
                                    "riskLevel": "high",
                                    "requiresApproval": False,
                                }
                            ]
                        ),
                    }
                )
            }
        ),
        api_key_env="OPENAI_API_KEY",
        environ={"OPENAI_API_KEY": "test-secret-value"},
    )

    with pytest.raises(LLMPlannerError, match="unsupported target files"):
        create_llm_plan_tasks(db, message, provider=provider)

    assert db.exec(select(Task)).all() == []


@pytest.mark.parametrize(
    ("response_text", "error_match"),
    [
        ("not-json", "invalid JSON"),
        (json.dumps({"outcomeType": "task_plan"}), "ConversationOutcome schema"),
    ],
)
def test_api_planner_invalid_output_creates_no_task(
    db: DbSession,
    response_text: str,
    error_match: str,
) -> None:
    message = _message(db, "帮我做打砖块")
    provider = OpenAIResponsesPlannerProvider(
        http_client=FakePlannerHttpClient({"output_text": response_text}),
        api_key_env="OPENAI_API_KEY",
        environ={"OPENAI_API_KEY": "test-secret-value"},
    )

    with pytest.raises(LLMPlannerError, match=error_match):
        create_llm_plan_tasks(db, message, provider=provider)

    assert db.exec(select(Task)).all() == []


def test_llm_planner_rejects_role_capability_target_and_command_policy_violations(
    db: DbSession,
) -> None:
    message = _message(db, "Create unsafe LLM plan")

    qa_writes_diff = _provider_for_single_task(
        {
            "title": "QA writes code",
            "intentType": "frontend_change",
            "role": "qa",
            "targetId": DEMO_FRONTEND_TARGET_ID,
            "plannedFiles": ["apps/demo/src/App.tsx"],
            "expectedArtifactTypes": ["diff"],
            "acceptanceCriteria": ["QA should not write code"],
            "riskLevel": "high",
            "requiresApproval": False,
        }
    )
    with pytest.raises(LLMPlannerError, match="not safe for write"):
        create_llm_plan_tasks(db, message, provider=qa_writes_diff)

    unsupported_command = _provider_for_single_task(
        {
            "title": "Run unsafe command",
            "intentType": "frontend_change",
            "role": "frontend",
            "targetId": DEMO_FRONTEND_TARGET_ID,
            "plannedFiles": ["apps/demo/src/App.tsx"],
            "expectedArtifactTypes": ["diff"],
            "acceptanceCriteria": ["Command policy must reject install"],
            "validationExpectations": ["pnpm install"],
            "riskLevel": "medium",
            "requiresApproval": False,
        }
    )
    with pytest.raises(LLMPlannerError, match="unsupported validation command"):
        create_llm_plan_tasks(db, message, provider=unsupported_command)

    allowed_command_note = _provider_for_single_task(
        {
            "title": "Run configured build",
            "intentType": "frontend_change",
            "role": "frontend",
            "targetId": DEMO_FRONTEND_TARGET_ID,
            "plannedFiles": ["apps/demo/src/App.tsx"],
            "expectedArtifactTypes": ["diff"],
            "acceptanceCriteria": ["Build passes"],
            "validationExpectations": ["pnpm build succeeds"],
            "riskLevel": "low",
            "requiresApproval": False,
        }
    )
    outcome = create_llm_plan_tasks(db, message, provider=allowed_command_note)
    assert len(outcome.tasks) == 1


def _message(db: DbSession, content: str) -> Message:
    session = db.exec(select(Session).where(Session.title == "LLM planning session")).one()
    message = Message(
        session_id=session.id,
        sender_type="user",
        content_md=content,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def _provider_for_single_task(task: dict) -> FakePlannerProvider:
    return FakePlannerProvider(
        payload={
            "planId": "plan-policy-test",
            "planner": "llm_v1",
            "plannerMode": "llm_v1",
            "rationale": "Policy tests should reject this plan.",
            "acceptanceCriteria": ["Reject unsafe plan"],
            "validationExpectations": ["pnpm build"],
            "tasks": [task],
        },
    )


def _valid_plan_payload(tasks: list[dict[str, object]]) -> dict[str, object]:
    return {
        "planId": "plan-api-provider-test",
        "planner": "llm_v1",
        "plannerMode": "llm_v1",
        "version": 1,
        "intent": "frontend_game",
        "rationale": "API planner output must pass the same validator path.",
        "acceptanceCriteria": ["Plan is validated"],
        "validationExpectations": ["pnpm build"],
        "guardrailNotes": ["Stay inside target allowed paths"],
        "tasks": tasks,
    }


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
