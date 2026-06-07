from datetime import datetime, timezone
import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine

from app.main import app, get_db
from app.mission_trace import build_session_mission_trace
from app.models import Agent, Session, Task, TaskRun, Workspace
from app.pmo_decisions import (
    PMO_DECISION_KEY,
    PmoDecisionError,
    apply_pmo_decision,
    require_supported_decision_payload,
)


FIXED_TIME = datetime(2026, 6, 8, 9, 30, tzinfo=timezone.utc)


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
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_db() -> Iterator[DbSession]:
        with DbSession(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _seed_pending_review_task(db: DbSession) -> Task:
    workspace = Workspace(
        name="PMO workspace",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="PMO session",
        bound_branch="main",
        worktree_path=".worktrees/pmo-session",
    )
    plan = apply_pmo_decision(
        {"planner": "llm_v1", "targetId": "demo-frontend"},
        state="pending_review",
        actor="orchestrator",
        reason="User review required before execution",
        now=FIXED_TIME,
    )
    task = Task(
        session_id=session.id,
        title="Reviewed frontend task",
        intent_type="frontend_change",
        plan_json=json.dumps(plan, separators=(",", ":")),
    )
    db.add(workspace)
    db.add(session)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def test_apply_pmo_decision_records_pending_review_metadata() -> None:
    plan = {"planner": "llm_v1", "targetId": "demo-frontend"}

    updated = apply_pmo_decision(
        plan,
        state="pending_review",
        actor="orchestrator",
        reason="User review required before execution",
        now=FIXED_TIME,
    )

    assert updated is not plan
    assert updated["planner"] == "llm_v1"
    assert updated[PMO_DECISION_KEY] == {
        "schemaVersion": 1,
        "state": "pending_review",
        "actor": "orchestrator",
        "reason": "User review required before execution",
        "createdAt": "2026-06-08T09:30:00+00:00",
        "decidedAt": None,
        "nextActionSummary": "Review the plan and approve, reject, or request clarification.",
    }


@pytest.mark.parametrize(
    ("state", "summary"),
    [
        ("approved", "Plan approved; existing scheduler and TaskRun paths may evaluate readiness."),
        ("rejected", "Plan rejected; no TaskRun should be created for this plan."),
        ("clarification_needed", "Clarification requested; wait for user follow-up before execution."),
    ],
)
def test_apply_pmo_decision_records_terminal_or_waiting_states(
    state: str,
    summary: str,
) -> None:
    updated = apply_pmo_decision(
        {"pmoDecision": {"state": "pending_review"}},
        state=state,
        actor="user",
        reason="Need a decision",
        now=FIXED_TIME,
    )

    decision = updated[PMO_DECISION_KEY]
    assert decision["state"] == state
    assert decision["actor"] == "user"
    assert decision["reason"] == "Need a decision"
    assert decision["createdAt"] == "2026-06-08T09:30:00+00:00"
    assert decision["decidedAt"] == "2026-06-08T09:30:00+00:00"
    assert decision["nextActionSummary"] == summary


def test_apply_pmo_decision_rejects_unknown_state() -> None:
    with pytest.raises(PmoDecisionError, match="Unsupported PMO decision state"):
        apply_pmo_decision(
            {},
            state="auto_merge",
            actor="user",
            now=FIXED_TIME,
        )


def test_require_supported_decision_payload_rejects_raw_plan_mutation() -> None:
    with pytest.raises(PmoDecisionError, match="Unsupported PMO decision fields"):
        require_supported_decision_payload(
            {
                "state": "approved",
                "reason": "Looks good",
                "planJson": {"targetId": "agenthub-platform"},
            }
        )


def test_pmo_decision_is_visible_in_mission_trace(db: DbSession) -> None:
    workspace = Workspace(
        name="PMO workspace",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="PMO session",
        bound_branch="main",
        worktree_path=".worktrees/pmo-session",
    )
    plan = apply_pmo_decision(
        {"planner": "llm_v1", "targetId": "demo-frontend"},
        state="pending_review",
        actor="orchestrator",
        reason="User review required before execution",
        now=FIXED_TIME,
    )
    task = Task(
        session_id=session.id,
        title="Reviewed frontend task",
        intent_type="frontend_change",
        plan_json=json.dumps(plan, separators=(",", ":")),
    )
    db.add(workspace)
    db.add(session)
    db.add(task)
    db.commit()

    trace = build_session_mission_trace(db, session.id)

    assert trace.tasks[0]["pmoDecision"]["state"] == "pending_review"
    assert trace.tasks[0]["pmoDecision"]["actor"] == "orchestrator"
    assert trace.tasks[0]["pmoDecision"]["reason"] == "User review required before execution"


def test_approve_plan_decision_updates_task_without_creating_task_run(
    client: TestClient,
) -> None:
    with next(app.dependency_overrides[get_db]()) as db:
        task = _seed_pending_review_task(db)
        task_id = task.id

    response = client.post(
        f"/tasks/{task_id}/plan-decision/approve",
        json={"reason": "Looks safe"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["planJson"]["pmoDecision"]["state"] == "approved"
    assert body["planJson"]["pmoDecision"]["actor"] == "user"
    assert body["planJson"]["pmoDecision"]["reason"] == "Looks safe"
    assert body["taskRuns"] == []


@pytest.mark.parametrize(
    ("action", "state"),
    [
        ("reject", "rejected"),
        ("clarification", "clarification_needed"),
    ],
)
def test_reject_or_clarification_plan_decision_does_not_create_task_run(
    client: TestClient,
    action: str,
    state: str,
) -> None:
    with next(app.dependency_overrides[get_db]()) as db:
        task = _seed_pending_review_task(db)
        task_id = task.id

    response = client.post(
        f"/tasks/{task_id}/plan-decision/{action}",
        json={"reason": "Need more control"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["planJson"]["pmoDecision"]["state"] == state
    assert body["planJson"]["pmoDecision"]["reason"] == "Need more control"
    assert body["taskRuns"] == []


def test_plan_decision_action_rejects_raw_plan_mutation_payload(
    client: TestClient,
) -> None:
    with next(app.dependency_overrides[get_db]()) as db:
        task = _seed_pending_review_task(db)
        task_id = task.id

    response = client.post(
        f"/tasks/{task_id}/plan-decision/approve",
        json={"reason": "Looks safe", "planJson": {"targetId": "agenthub-platform"}},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "planJson"]


def test_mission_trace_exposes_pmo_readiness_groups_and_next_actions(
    db: DbSession,
) -> None:
    workspace = Workspace(
        name="PMO workspace",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="PMO session",
        bound_branch="main",
        worktree_path=".worktrees/pmo-session",
    )
    ready = Task(
        session_id=session.id,
        title="Ready task",
        intent_type="frontend_change",
        status="pending",
        priority=1,
        plan_json=json.dumps(
            {"scheduler": {"state": "ready", "runnable": True}},
            separators=(",", ":"),
        ),
    )
    waiting = Task(
        session_id=session.id,
        title="Waiting task",
        intent_type="frontend_change",
        status="waiting_dependency",
        priority=2,
        depends_on_task_ids=json.dumps([ready.id]),
        plan_json=json.dumps(
            {
                "scheduler": {
                    "state": "waiting_dependency",
                    "reason": "Waiting for upstream dependencies to complete.",
                    "dependencyIds": [ready.id],
                    "blockingDependencyIds": [ready.id],
                }
            },
            separators=(",", ":"),
        ),
    )
    review = Task(
        session_id=session.id,
        title="Review me",
        intent_type="frontend_change",
        status="pending",
        priority=3,
        plan_json=json.dumps(
            apply_pmo_decision(
                {"planner": "llm_v1"},
                state="pending_review",
                actor="orchestrator",
                reason="Needs PMO approval",
                now=FIXED_TIME,
            ),
            separators=(",", ":"),
        ),
    )
    db.add(workspace)
    db.add(session)
    db.add(ready)
    db.add(waiting)
    db.add(review)
    db.commit()

    trace = build_session_mission_trace(db, session.id)

    groups = trace.model_dump(by_alias=True)["taskGraphReadiness"]
    assert groups["ready"][0]["taskId"] == ready.id
    assert groups["waitingDependency"][0]["taskId"] == waiting.id
    assert groups["blocked"] == []
    action_types = {action["type"] for action in trace.next_actions}
    assert "start_ready_task" in action_types
    assert any(
        action["type"] == "inspect_blocker" and action["subtype"] == "dependency"
        for action in trace.next_actions
    )
    assert "approve_plan" in action_types
    assert "reject_plan" in action_types
    assert "request_clarification" in action_types


def test_mission_trace_exposes_retry_fallback_and_approval_next_actions(
    db: DbSession,
) -> None:
    workspace = Workspace(
        name="PMO workspace",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="PMO session",
        bound_branch="main",
        worktree_path=".worktrees/pmo-session",
    )
    agent = Agent(
        name="Frontend Agent",
        role="frontend",
        adapter_type="codex",
        provider="local",
    )
    retryable = Task(
        session_id=session.id,
        title="Retryable task",
        intent_type="frontend_change",
        status="failed",
        priority=1,
        plan_json=json.dumps(
            {"scheduler": {"state": "retryable", "reason": "Adapter failed"}},
            separators=(",", ":"),
        ),
    )
    fallback = Task(
        session_id=session.id,
        title="Fallback task",
        intent_type="frontend_change",
        status="blocked",
        priority=2,
        plan_json=json.dumps(
            {
                "scheduler": {
                    "state": "fallback_available",
                    "reason": "Explicit fallback is available.",
                }
            },
            separators=(",", ":"),
        ),
    )
    approval = Task(
        session_id=session.id,
        title="Approval task",
        intent_type="platform_maintenance",
        status="waiting_approval",
        priority=3,
        plan_json=json.dumps({"scheduler": {"state": "blocked"}}, separators=(",", ":")),
    )
    db.add(workspace)
    db.add(session)
    db.add(agent)
    db.add(retryable)
    db.add(fallback)
    db.add(approval)
    db.commit()
    run = TaskRun(
        task_id=approval.id,
        agent_id=agent.id,
        state="waiting_approval",
        worktree_path=session.worktree_path,
    )
    db.add(run)
    db.commit()

    trace = build_session_mission_trace(db, session.id)

    actions = trace.next_actions
    action_types = {action["type"] for action in actions}
    assert "retry_task" in action_types
    assert "retry_with_explicit_fallback" in action_types
    assert "approve_task_run" in action_types
    assert "deny_task_run" in action_types


def test_mission_trace_exposes_redacted_pmo_evidence(db: DbSession) -> None:
    workspace = Workspace(
        name="PMO workspace",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="PMO session",
        bound_branch="main",
        worktree_path=".worktrees/pmo-session",
    )
    decision_task = Task(
        session_id=session.id,
        title="Review decision",
        intent_type="frontend_change",
        status="pending",
        priority=1,
        plan_json=json.dumps(
            apply_pmo_decision(
                {"planner": "llm_v1"},
                state="pending_review",
                actor="orchestrator",
                reason="Review before editing /Users/me/secrets/token.txt",
                now=FIXED_TIME,
            ),
            separators=(",", ":"),
        ),
    )
    conflict_task = Task(
        session_id=session.id,
        title="Conflict",
        intent_type="frontend_change",
        status="blocked",
        priority=2,
        plan_json=json.dumps(
            {
                "scheduler": {
                    "state": "blocked",
                    "reason": "Dirty file /Users/me/project/.env has SECRET_TOKEN=abc123",
                    "conflictType": "dirty_worktree",
                    "conflictingFiles": [
                        "apps/demo/src/App.tsx",
                        "/Users/me/project/.env",
                        "/Users/me/secrets/token.txt",
                    ],
                },
                "plannerFallback": {
                    "reason": "task_plan_validation_failed",
                    "errorSummary": "token=abc123 and /Users/me/secrets/token.txt",
                    "providerId": "fake-llm-planner",
                },
            },
            separators=(",", ":"),
        ),
    )
    db.add(workspace)
    db.add(session)
    db.add(decision_task)
    db.add(conflict_task)
    db.commit()

    trace = build_session_mission_trace(db, session.id).model_dump(by_alias=True)

    evidence_json = json.dumps(trace["pmoEvidence"], sort_keys=True)
    assert "plan_decision" in evidence_json
    assert "blocker" in evidence_json
    assert "fallback" in evidence_json
    assert "dirty_worktree" in evidence_json
    assert "SECRET_TOKEN" not in evidence_json
    assert "abc123" not in evidence_json
    assert ".env" not in evidence_json
    assert "/Users/me/secrets" not in evidence_json
    assert "apps/demo/src/App.tsx" in evidence_json
