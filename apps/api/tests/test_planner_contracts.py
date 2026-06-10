import json
from collections.abc import Iterator

import pytest
from pydantic import ValidationError
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.llm_planner import (
    LLMPlannerError,
    build_llm_planner_request,
    parse_conversation_outcome_output,
    parse_llm_plan_output,
)
from app.models import Agent, Message, Session, Workspace
from app.planner_contracts import (
    ConversationOutcome,
    PlannerRequest,
    PlannerResponse,
    conversation_outcome_json_schema,
    planner_conversation_system_prompt,
)
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
            title="Planner contract session",
            bound_branch="main",
            worktree_path=".worktrees/planner-contract-session",
        )
        session.add(workspace)
        session.add(planning_session)
        session.add(Agent(name="Orchestrator", role="orchestrator", adapter_type="scripted_mock", provider="local"))
        session.add(Agent(name="Frontend Agent", role="frontend", adapter_type="codex", provider="local"))
        session.add(Agent(name="QA Agent", role="qa", adapter_type="scripted_mock", provider="local"))
        session.commit()
        yield session


def test_planner_request_contract_preserves_user_request_and_policy_context(
    db: DbSession,
) -> None:
    message = _message(db, "帮我实现一个 Breakout 游戏")

    request = build_llm_planner_request(db, message)
    payload = request.to_provider_payload()

    assert isinstance(request, PlannerRequest)
    assert payload["plannerMode"] == "llm_v1"
    assert payload["originalUserRequest"] == "帮我实现一个 Breakout 游戏"
    assert payload["canonicalSharedContext"]["version"] == "canonical_shared_context_v1"
    assert payload["targetRegistry"]
    assert payload["projectAnalyzer"]
    assert payload["recentMessages"][0]["contentMd"] == "帮我实现一个 Breakout 游戏"
    assert payload["artifactReferences"] == []
    assert "frontend" in payload["supportedRoles"]
    assert "code_write" in payload["supportedCapabilities"]
    assert ".env" in payload["guardrails"]["protectedPaths"]


def test_planner_request_provider_payload_excludes_secret_like_values(
    db: DbSession,
) -> None:
    message = _message(db, "Do not leak SECRET_TOKEN=abc123 or /Users/me/.env")

    payload = build_llm_planner_request(db, message).to_provider_payload()
    serialized = json.dumps(payload)

    assert "SECRET_TOKEN=abc123" not in serialized
    assert "/Users/me/.env" not in serialized
    assert "[protected]" in serialized


def test_planner_response_contract_requires_plan_and_task_fields() -> None:
    response = PlannerResponse.model_validate(
        {
            "planId": "plan-breakout",
            "planner": "llm_v1",
            "plannerMode": "llm_v1",
            "rationale": "Implement this as one target-scoped frontend task.",
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
                    "riskLevel": "medium",
                    "requiresApproval": False,
                }
            ],
        }
    )

    assert response.plan_id == "plan-breakout"
    assert response.tasks[0].role == "frontend"
    assert response.tasks[0].requires_approval is False


def test_planner_response_contract_accepts_project_setup_metadata() -> None:
    response = PlannerResponse.model_validate(
        {
            "planId": "plan-health-management",
            "planner": "llm_v1",
            "plannerMode": "llm_v1",
            "rationale": "Prepare a new fullstack project before assigning work.",
            "acceptanceCriteria": ["Project boundaries are prepared"],
            "validationExpectations": ["configured commands are used"],
            "projectSetup": {
                "projectKind": "new_project",
                "plannedProjectRoot": "~/Desktop/agenthub-rehearsals/health-management",
                "defaultFrontendStack": "vite-react",
                "defaultBackendStack": "fastapi",
                "approvalRequiredCommands": ["pnpm install"],
                "provisionalTargets": [
                    {
                        "targetId": "external-frontend-health-management",
                        "role": "frontend",
                        "rootPath": "~/Desktop/agenthub-rehearsals/health-management/frontend",
                        "projectType": "vite-react",
                        "allowedPaths": ["src", "package.json"],
                        "validationCommands": ["pnpm build"],
                    }
                ],
            },
            "tasks": [
                {
                    "title": "Build health frontend",
                    "role": "frontend",
                    "targetId": "external-frontend-health-management",
                    "intentType": "frontend_change",
                    "plannedFiles": ["src/App.tsx"],
                    "dependsOn": [],
                    "expectedArtifactTypes": ["diff"],
                    "acceptanceCriteria": ["Login page renders"],
                    "riskLevel": "medium",
                    "requiresApproval": False,
                }
            ],
        }
    )

    payload = response.to_payload()

    assert payload["projectSetup"]["projectKind"] == "new_project"
    assert payload["projectSetup"]["provisionalTargets"][0]["role"] == "frontend"


def test_planner_response_contract_rejects_incomplete_plan() -> None:
    with pytest.raises(ValidationError):
        PlannerResponse.model_validate(
            {
                "planner": "llm_v1",
                "plannerMode": "llm_v1",
                "rationale": "Missing required task fields.",
                "tasks": [{"title": "Incomplete"}],
            }
        )


def test_planner_response_contract_safely_normalizes_version_and_guardrail_notes() -> None:
    response = PlannerResponse.model_validate(
        {
            "planId": "plan-normalized",
            "planner": "llm_v1",
            "plannerMode": "llm_v1",
            "rationale": "Normalize safe scalar fields only.",
            "acceptanceCriteria": ["Game is playable"],
            "validationExpectations": ["pnpm build"],
            "version": "1.0.0",
            "guardrailNotes": "Stay inside demo-frontend.",
            "tasks": [
                {
                    "title": "Build Breakout game",
                    "role": "frontend",
                    "targetId": DEMO_FRONTEND_TARGET_ID,
                    "intentType": "frontend_change",
                    "plannedFiles": ["apps/demo/src/App.tsx"],
                    "dependsOn": [],
                    "expectedArtifactTypes": ["diff"],
                    "acceptanceCriteria": ["Keyboard controls work"],
                    "riskLevel": "medium",
                    "requiresApproval": False,
                }
            ],
        }
    )

    assert response.version == 1
    assert response.guardrail_notes == ["Stay inside demo-frontend."]


def test_parse_llm_plan_output_returns_contract_validated_payload() -> None:
    payload = parse_llm_plan_output(
        json.dumps(
            {
                "planId": "plan-breakout",
                "planner": "llm_v1",
                "plannerMode": "llm_v1",
                "rationale": "Implement a playable game in the frontend target.",
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
                        "expectedArtifactTypes": ["diff"],
                        "acceptanceCriteria": ["Keyboard controls work"],
                        "riskLevel": "medium",
                        "requiresApproval": False,
                    }
                ],
            }
        )
    )

    assert payload["planId"] == "plan-breakout"
    assert payload["tasks"][0]["role"] == "frontend"


def test_parse_conversation_outcome_output_accepts_task_plan_wrapper() -> None:
    outcome = parse_conversation_outcome_output(
        json.dumps(
            {
                "outcomeType": "task_plan",
                "reply": None,
                "planDraft": _valid_plan_response_payload(),
                "riskLevel": "medium",
                "reason": "A frontend task can satisfy the request.",
                "plannerProvider": {"providerId": "fake-test-planner"},
                "validationResult": "pending",
            }
        )
    )

    assert outcome["outcomeType"] == "task_plan"
    assert outcome["planDraft"]["planId"] == "plan-breakout"
    assert outcome["plannerProvider"]["providerId"] == "fake-test-planner"


def test_parse_conversation_outcome_output_accepts_assistant_reply() -> None:
    outcome = parse_conversation_outcome_output(
        json.dumps(
            {
                "outcomeType": "assistant_reply",
                "reply": "你好，我可以帮你规划和执行代码任务。",
                "riskLevel": "low",
                "reason": "Pure greeting.",
                "plannerProvider": {"providerId": "fake-test-planner"},
                "validationResult": "not_required",
            }
        )
    )

    assert outcome["outcomeType"] == "assistant_reply"
    assert outcome["reply"].startswith("你好")
    assert outcome["planDraft"] is None


def test_parse_conversation_outcome_output_ignores_non_task_plan_draft_noise() -> None:
    outcome = parse_conversation_outcome_output(
        json.dumps(
            {
                "outcomeType": "assistant_reply",
                "reply": "你好，我可以帮你规划代码任务。",
                "planDraft": {"tasks": [{"title": "invalid accidental draft"}]},
                "codingAgentProvider": {"providerId": "should-not-be-here"},
                "riskLevel": "low",
                "reason": "Pure greeting.",
                "validationResult": "not_required",
            }
        )
    )

    assert outcome["outcomeType"] == "assistant_reply"
    assert outcome["reply"].startswith("你好")
    assert outcome["planDraft"] is None
    assert outcome["codingAgentProvider"] is None


def test_parse_conversation_outcome_output_normalizes_loose_assistant_reply() -> None:
    outcome = parse_conversation_outcome_output(
        json.dumps({"reply": "你好，我可以帮你规划代码任务。"})
    )

    assert outcome["outcomeType"] == "assistant_reply"
    assert outcome["reply"].startswith("你好")
    assert outcome["planDraft"] is None
    assert outcome["validationResult"] == "not_required"


def test_conversation_outcome_supports_assistant_reply_without_task_plan() -> None:
    outcome = ConversationOutcome.model_validate(
        {
            "outcomeType": "assistant_reply",
            "reply": "你好，我可以帮你规划和执行代码任务。",
            "riskLevel": "low",
            "reason": "Pure greeting.",
            "plannerProvider": {
                "providerId": "claude-cli-planner",
                "providerType": "claude_cli",
            },
            "validationResult": "not_required",
        }
    )

    payload = outcome.to_payload()

    assert payload["outcomeType"] == "assistant_reply"
    assert payload["reply"].startswith("你好")
    assert payload["planDraft"] is None
    assert payload["plannerProvider"]["providerId"] == "claude-cli-planner"
    assert payload["codingAgentProvider"] is None


def test_conversation_outcome_requires_plan_draft_for_task_plan() -> None:
    with pytest.raises(ValidationError):
        ConversationOutcome.model_validate(
            {
                "outcomeType": "task_plan",
                "riskLevel": "medium",
                "reason": "Coding request.",
                "plannerProvider": {"providerId": "fake-test-planner"},
                "validationResult": "pending",
            }
        )


def test_conversation_outcome_keeps_coding_provider_evidence_downstream() -> None:
    plan = _valid_plan_response_payload()

    with pytest.raises(ValidationError):
        ConversationOutcome.model_validate(
            {
                "outcomeType": "task_plan",
                "planDraft": plan,
                "riskLevel": "medium",
                "reason": "Coding request.",
                "plannerProvider": {"providerId": "fake-test-planner"},
                "codingAgentProvider": {"providerId": "local-claude-code-cli"},
                "validationResult": "pending",
            }
        )


def test_conversation_outcome_rejects_plan_draft_for_non_task_outcome() -> None:
    plan = _valid_plan_response_payload()

    with pytest.raises(ValidationError):
        ConversationOutcome.model_validate(
            {
                "outcomeType": "clarification",
                "reply": "你想修改哪个前端项目？",
                "planDraft": plan,
                "riskLevel": "low",
                "reason": "Needs target clarification.",
                "plannerProvider": {"providerId": "fake-test-planner"},
                "validationResult": "not_required",
            }
        )


def test_parse_llm_plan_output_extracts_single_embedded_json_payload() -> None:
    raw = """
    Here is the validated plan:

    ```json
    {
      "planId": "plan-embedded",
      "planner": "llm_v1",
      "plannerMode": "llm_v1",
      "rationale": "One frontend task is enough.",
      "acceptanceCriteria": ["Game is playable"],
      "validationExpectations": ["pnpm build"],
      "tasks": [
        {
          "title": "Build game",
          "role": "frontend",
          "targetId": "demo-frontend",
          "intentType": "frontend_change",
          "plannedFiles": ["apps/demo/src/App.tsx"],
          "dependsOn": [],
          "expectedArtifactTypes": ["diff"],
          "acceptanceCriteria": ["Keyboard controls work"],
          "riskLevel": "medium",
          "requiresApproval": false
        }
      ]
    }
    ```
    """

    payload = parse_llm_plan_output(raw)

    assert payload["planId"] == "plan-embedded"


def test_parse_llm_plan_output_rejects_ambiguous_json_payloads() -> None:
    valid_plan = json.dumps(
        {
            "planId": "plan-a",
            "planner": "llm_v1",
            "plannerMode": "llm_v1",
            "rationale": "Plan A.",
            "acceptanceCriteria": ["A"],
            "validationExpectations": ["pnpm build"],
            "tasks": [
                {
                    "title": "Build A",
                    "role": "frontend",
                    "targetId": DEMO_FRONTEND_TARGET_ID,
                    "intentType": "frontend_change",
                    "plannedFiles": ["apps/demo/src/App.tsx"],
                    "dependsOn": [],
                    "expectedArtifactTypes": ["diff"],
                    "acceptanceCriteria": ["A"],
                    "riskLevel": "low",
                    "requiresApproval": False,
                }
            ],
        }
    )

    with pytest.raises(LLMPlannerError, match="ambiguous JSON"):
        parse_llm_plan_output(f"{valid_plan}\n{valid_plan}")


def test_parse_llm_plan_output_rejects_missing_required_fields() -> None:
    with pytest.raises(LLMPlannerError, match="PlannerResponse schema"):
        parse_llm_plan_output(
            json.dumps(
                {
                    "planId": "plan-incomplete",
                    "planner": "llm_v1",
                    "plannerMode": "llm_v1",
                    "rationale": "Missing required task fields.",
                    "acceptanceCriteria": ["No missing fields"],
                    "validationExpectations": ["pnpm build"],
                    "tasks": [{"title": "Incomplete"}],
                }
            )
        )


def test_conversation_outcome_structured_output_helpers_are_shared() -> None:
    schema = conversation_outcome_json_schema()
    prompt = planner_conversation_system_prompt()

    assert schema["properties"]["outcomeType"]["enum"] == [
        "assistant_reply",
        "task_plan",
        "clarification",
        "refusal",
        "approval_required",
        "unsupported",
    ]
    assert schema["required"] == ["outcomeType"]
    assert schema["properties"]["planDraft"]["type"] == ["object", "null"]
    assert "ConversationOutcome" in prompt or "conversation router" in prompt
    assert "execute code" in prompt.lower()
    assert "Never execute code" in prompt or "call agents" in prompt


def test_parse_llm_plan_output_does_not_normalize_unknown_target() -> None:
    payload = parse_llm_plan_output(
        json.dumps(
            {
                "planId": "plan-unknown-target",
                "planner": "llm_v1",
                "plannerMode": "llm_v1",
                "rationale": "Schema allows parsing but policy validation must reject later.",
                "acceptanceCriteria": ["Target policy is checked later"],
                "validationExpectations": ["pnpm build"],
                "tasks": [
                    {
                        "title": "Build game",
                        "role": "frontend",
                        "targetId": "unknown-target",
                        "intentType": "frontend_change",
                        "plannedFiles": ["apps/demo/src/App.tsx"],
                        "dependsOn": [],
                        "expectedArtifactTypes": ["diff"],
                        "acceptanceCriteria": ["Keyboard controls work"],
                        "riskLevel": "medium",
                        "requiresApproval": False,
                    }
                ],
            }
        )
    )

    assert payload["tasks"][0]["targetId"] == "unknown-target"


def _valid_plan_response_payload() -> dict[str, object]:
    return {
        "planId": "plan-breakout",
        "planner": "llm_v1",
        "plannerMode": "llm_v1",
        "rationale": "Implement a playable game in the frontend target.",
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
                "expectedArtifactTypes": ["diff"],
                "acceptanceCriteria": ["Keyboard controls work"],
                "riskLevel": "medium",
                "requiresApproval": False,
            }
        ],
    }


def _message(db: DbSession, content: str) -> Message:
    session = db.exec(select(Session).where(Session.title == "Planner contract session")).one()
    message = Message(
        session_id=session.id,
        sender_type="user",
        content_md=content,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message
