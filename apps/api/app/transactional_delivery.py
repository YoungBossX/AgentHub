import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from app.models import TaskRun


class DeliveryState(str, Enum):
    PENDING_VALIDATION = "pending_validation"
    REVIEW_REQUIRED = "review_required"
    ACCEPTED = "accepted"
    ROLLED_BACK = "rolled_back"
    ROLLBACK_REFUSED = "rollback_refused"
    RETRY_FROM_CURRENT_STATE = "retry_from_current_state"
    RETRY_FROM_CHECKPOINT = "retry_from_checkpoint"


class DeliveryEvidenceKind(str, Enum):
    COMMAND = "command"
    DIFF = "diff"
    REVIEW = "review"
    POLICY = "policy"


class DeliveryRetryMode(str, Enum):
    CURRENT_STATE = "current_state"
    CHECKPOINT = "checkpoint"


@dataclass(frozen=True)
class DeliveryCheckpointEvidence:
    checkpoint_id: Optional[str]
    task_run_id: str
    target_id: Optional[str]
    target_root: Optional[str]
    worktree_path: Optional[str]
    allowed_paths: tuple[str, ...]
    denied_paths: tuple[str, ...]
    planned_files: tuple[str, ...]
    dirty_files: tuple[str, ...]
    contract_id: Optional[str] = None
    contract_hash: Optional[str] = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "checkpointId": self.checkpoint_id,
            "taskRunId": self.task_run_id,
            "targetId": self.target_id,
            "targetRoot": self.target_root,
            "worktreePath": self.worktree_path,
            "allowedPaths": list(self.allowed_paths),
            "deniedPaths": list(self.denied_paths),
            "plannedFiles": list(self.planned_files),
            "dirtyFiles": list(self.dirty_files),
            "contractId": self.contract_id,
            "contractHash": self.contract_hash,
        }


@dataclass(frozen=True)
class DeliveryDecision:
    state: DeliveryState
    reason: str
    task_run_id: str
    checkpoint: Optional[DeliveryCheckpointEvidence] = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_event_payload(self) -> dict[str, Any]:
        payload = {
            "state": self.state.value,
            "reason": self.reason,
            "taskRunId": self.task_run_id,
            "evidence": dict(self.evidence),
        }
        if self.checkpoint is not None:
            payload["checkpoint"] = self.checkpoint.to_payload()
        return payload


@dataclass(frozen=True)
class DeliveryValidationEvidence:
    kind: DeliveryEvidenceKind
    status: str
    artifact_id: Optional[str] = None
    summary: str = ""
    risk_level: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


def checkpoint_evidence_for_task_run(
    task_run: TaskRun,
) -> Optional[DeliveryCheckpointEvidence]:
    checkpoint = _metrics_dict(task_run).get("preRunCheckpoint")
    if not isinstance(checkpoint, dict):
        return None
    return DeliveryCheckpointEvidence(
        checkpoint_id=str(checkpoint.get("checkpointId") or task_run.id),
        task_run_id=task_run.id,
        target_id=_string_or_none(checkpoint.get("targetId")),
        target_root=_string_or_none(checkpoint.get("targetRoot")),
        worktree_path=task_run.worktree_path,
        allowed_paths=tuple(_string_list(checkpoint.get("allowedPaths"))),
        denied_paths=tuple(_string_list(checkpoint.get("deniedPaths"))),
        planned_files=tuple(_string_list(checkpoint.get("plannedFiles"))),
        dirty_files=tuple(_string_list(checkpoint.get("dirtyFiles"))),
        contract_id=_string_or_none(checkpoint.get("contractId")),
        contract_hash=_string_or_none(checkpoint.get("contractHash")),
    )


def pending_validation_decision(task_run: TaskRun) -> DeliveryDecision:
    checkpoint = checkpoint_evidence_for_task_run(task_run)
    return DeliveryDecision(
        state=DeliveryState.PENDING_VALIDATION,
        reason="TaskRun is ready for delivery validation.",
        task_run_id=task_run.id,
        checkpoint=checkpoint,
    )


def rollback_preflight_decision(task_run: TaskRun) -> DeliveryDecision:
    checkpoint = checkpoint_evidence_for_task_run(task_run)
    if checkpoint is None:
        return DeliveryDecision(
            state=DeliveryState.ROLLBACK_REFUSED,
            reason="Rollback requires a pre-run checkpoint, but none was recorded.",
            task_run_id=task_run.id,
            evidence={"eventType": "delivery.rollback_refused"},
        )
    return DeliveryDecision(
        state=DeliveryState.ROLLED_BACK,
        reason="Rollback can proceed from the recorded pre-run checkpoint.",
        task_run_id=task_run.id,
        checkpoint=checkpoint,
        evidence={"eventType": "delivery.rollback_ready"},
    )


def retry_mode_decision(
    task_run: TaskRun,
    *,
    mode: DeliveryRetryMode,
) -> DeliveryDecision:
    state = (
        DeliveryState.RETRY_FROM_CHECKPOINT
        if mode == DeliveryRetryMode.CHECKPOINT
        else DeliveryState.RETRY_FROM_CURRENT_STATE
    )
    return DeliveryDecision(
        state=state,
        reason=f"Retry requested from {mode.value}.",
        task_run_id=task_run.id,
        checkpoint=checkpoint_evidence_for_task_run(task_run),
        evidence={"retryMode": mode.value},
    )


def evaluate_delivery_validation(
    task_run: TaskRun,
    evidence: list[DeliveryValidationEvidence],
) -> DeliveryDecision:
    failures = [
        item
        for item in evidence
        if item.status in {"failed", "blocked", "denied"}
        or item.risk_level in {"high", "critical"}
    ]
    if failures:
        return DeliveryDecision(
            state=DeliveryState.REVIEW_REQUIRED,
            reason="Delivery validation found failed or high-risk evidence.",
            task_run_id=task_run.id,
            checkpoint=checkpoint_evidence_for_task_run(task_run),
            evidence={
                "eventType": "delivery.review_required",
                "failures": [_validation_item_payload(item) for item in failures],
            },
        )
    return DeliveryDecision(
        state=DeliveryState.PENDING_VALIDATION,
        reason="Delivery validation passed available evidence.",
        task_run_id=task_run.id,
        checkpoint=checkpoint_evidence_for_task_run(task_run),
        evidence={
            "eventType": "delivery.validation_passed",
            "checkedEvidence": [_validation_item_payload(item) for item in evidence],
        },
    )


def _metrics_dict(task_run: TaskRun) -> dict[str, Any]:
    try:
        parsed = json.loads(task_run.metrics_json)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _validation_item_payload(item: DeliveryValidationEvidence) -> dict[str, Any]:
    return {
        "kind": item.kind.value,
        "status": item.status,
        "artifactId": item.artifact_id,
        "summary": item.summary,
        "riskLevel": item.risk_level,
        "metadata": dict(item.metadata),
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _string_or_none(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and value else None
