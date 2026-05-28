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
from app.models import Agent, Message, Session, Workspace
from app.planner_providers import FakePlannerProvider
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
    assert frontend_plan["originalRequest"] == "Build a playable canvas game"
    assert frontend_plan["planDraft"]["plannerMode"] == "llm_v1"
    assert frontend_plan["planDraft"]["acceptanceCriteria"] == [
        "Keyboard controls work",
        "Score updates",
    ]
    assert frontend_plan["planDraft"]["validationExpectations"] == ["pnpm build"]
    assert json.loads(outcome.tasks[1].depends_on_task_ids) == [frontend_task.id]


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
