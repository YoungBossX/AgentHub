from datetime import datetime, timezone
import json
from collections.abc import Iterator

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine

from app.mission_trace import build_session_mission_trace
from app.models import Session, Task, Workspace
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
