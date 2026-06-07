from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

PMO_DECISION_KEY = "pmoDecision"

SUPPORTED_PMO_DECISION_STATES = {
    "pending_review",
    "approved",
    "rejected",
    "clarification_needed",
}

SUPPORTED_DECISION_PAYLOAD_FIELDS = {"state", "reason", "actor"}

NEXT_ACTION_SUMMARIES = {
    "pending_review": "Review the plan and approve, reject, or request clarification.",
    "approved": "Plan approved; existing scheduler and TaskRun paths may evaluate readiness.",
    "rejected": "Plan rejected; no TaskRun should be created for this plan.",
    "clarification_needed": "Clarification requested; wait for user follow-up before execution.",
}


class PmoDecisionError(ValueError):
    pass


def apply_pmo_decision(
    plan: dict[str, Any],
    *,
    state: str,
    actor: str,
    reason: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if state not in SUPPORTED_PMO_DECISION_STATES:
        raise PmoDecisionError(f"Unsupported PMO decision state: {state}")

    timestamp = _utc_now(now).isoformat()
    decision_time = None if state == "pending_review" else timestamp
    updated = deepcopy(plan)
    updated[PMO_DECISION_KEY] = {
        "schemaVersion": 1,
        "state": state,
        "actor": actor,
        "reason": reason,
        "createdAt": timestamp,
        "decidedAt": decision_time,
        "nextActionSummary": NEXT_ACTION_SUMMARIES[state],
    }
    return updated


def require_supported_decision_payload(payload: dict[str, Any]) -> None:
    unsupported = sorted(set(payload) - SUPPORTED_DECISION_PAYLOAD_FIELDS)
    if unsupported:
        fields = ", ".join(unsupported)
        raise PmoDecisionError(f"Unsupported PMO decision fields: {fields}")


def _utc_now(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
