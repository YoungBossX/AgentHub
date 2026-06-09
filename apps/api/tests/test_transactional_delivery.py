import json

from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.models import TaskRunEvent
from app.models import TaskRun
from app.transactional_delivery import (
    DeliveryEvidenceKind,
    DeliveryArtifactState,
    DeliveryRetryMode,
    DeliveryState,
    DeliveryValidationEvidence,
    checkpoint_evidence_for_task_run,
    accept_delivery_decision,
    evaluate_delivery_validation,
    pending_validation_decision,
    retry_mode_decision,
    rollback_decision,
    rollback_preflight_decision,
    record_delivery_decision_event,
)


def test_checkpoint_evidence_reads_task_run_metrics() -> None:
    task_run = _task_run(
        metrics={
            "preRunCheckpoint": {
                "checkpointId": "checkpoint-1",
                "targetId": "external-vite",
                "targetRoot": "/tmp/external-vite",
                "allowedPaths": ["src"],
                "deniedPaths": [".env", ".git"],
                "plannedFiles": ["src/App.tsx"],
                "dirtyFiles": ["src/App.tsx"],
                "contractId": "contract-1",
                "contractHash": "hash-1",
            }
        }
    )

    evidence = checkpoint_evidence_for_task_run(task_run)

    assert evidence is not None
    assert evidence.checkpoint_id == "checkpoint-1"
    assert evidence.target_id == "external-vite"
    assert evidence.worktree_path == "/tmp/worktree"
    assert evidence.allowed_paths == ("src",)
    assert evidence.denied_paths == (".env", ".git")
    assert evidence.planned_files == ("src/App.tsx",)
    assert evidence.to_payload()["contractHash"] == "hash-1"


def test_pending_validation_decision_includes_checkpoint() -> None:
    task_run = _task_run(
        metrics={
            "preRunCheckpoint": {
                "targetId": "demo-frontend",
                "allowedPaths": ["apps/demo/src"],
            }
        }
    )

    decision = pending_validation_decision(task_run)

    assert decision.state == DeliveryState.PENDING_VALIDATION
    assert decision.checkpoint is not None
    assert decision.to_event_payload()["checkpoint"]["targetId"] == "demo-frontend"


def test_rollback_preflight_refuses_without_checkpoint() -> None:
    decision = rollback_preflight_decision(_task_run(metrics={}))

    assert decision.state == DeliveryState.ROLLBACK_REFUSED
    assert "pre-run checkpoint" in decision.reason
    assert decision.evidence["eventType"] == "delivery.rollback_refused"


def test_rollback_preflight_allows_checkpoint_path() -> None:
    decision = rollback_preflight_decision(
        _task_run(metrics={"preRunCheckpoint": {"targetId": "external-vite"}})
    )

    assert decision.state == DeliveryState.ROLLED_BACK
    assert decision.evidence["eventType"] == "delivery.rollback_ready"


def test_retry_mode_decision_is_explicit() -> None:
    task_run = _task_run(metrics={"preRunCheckpoint": {"targetId": "external-vite"}})

    current = retry_mode_decision(task_run, mode=DeliveryRetryMode.CURRENT_STATE)
    checkpoint = retry_mode_decision(task_run, mode=DeliveryRetryMode.CHECKPOINT)

    assert current.state == DeliveryState.RETRY_FROM_CURRENT_STATE
    assert current.evidence["retryMode"] == "current_state"
    assert checkpoint.state == DeliveryState.RETRY_FROM_CHECKPOINT
    assert checkpoint.evidence["retryMode"] == "checkpoint"


def test_accept_delivery_records_artifact_state() -> None:
    decision = accept_delivery_decision(
        _task_run(metrics={"preRunCheckpoint": {"targetId": "external-vite"}}),
        artifact_state=DeliveryArtifactState(
            diff_artifact_ids=("diff-1",),
            review_artifact_ids=("review-1",),
            command_evidence_ids=("command-1",),
            policy_evidence_ids=("policy-1",),
        ),
        accepted_by="user",
        accepted_at="2026-06-09T00:00:00Z",
    )

    assert decision.state == DeliveryState.ACCEPTED
    assert decision.evidence["eventType"] == "delivery.accepted"
    assert decision.evidence["diffArtifactIds"] == ["diff-1"]
    assert decision.evidence["acceptedBy"] == "user"


def test_rollback_decision_records_restored_paths_from_checkpoint() -> None:
    decision = rollback_decision(
        _task_run(
            metrics={
                "preRunCheckpoint": {
                    "targetId": "external-vite",
                    "plannedFiles": ["src/App.tsx"],
                }
            }
        ),
        actor="user",
    )

    assert decision.state == DeliveryState.ROLLED_BACK
    assert decision.evidence["eventType"] == "delivery.rolled_back"
    assert decision.evidence["restoredPaths"] == ["src/App.tsx"]


def test_rollback_decision_refuses_without_checkpoint() -> None:
    decision = rollback_decision(_task_run(metrics={}), actor="user")

    assert decision.state == DeliveryState.ROLLBACK_REFUSED


def test_record_delivery_decision_event_persists_payload() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        task_run = _task_run(metrics={})
        db.add(task_run)
        db.commit()
        decision = evaluate_delivery_validation(
            task_run,
            [
                DeliveryValidationEvidence(
                    kind=DeliveryEvidenceKind.POLICY,
                    status="denied",
                    summary="Target path denied",
                )
            ],
        )

        record_delivery_decision_event(db, decision)

        event = db.exec(select(TaskRunEvent)).one()
        payload = json.loads(event.payload_json)

    assert event.event_type == "delivery.review_required"
    assert payload["state"] == "review_required"
    assert payload["evidence"]["failures"][0]["kind"] == "policy"


def test_delivery_validation_passes_clean_evidence() -> None:
    decision = evaluate_delivery_validation(
        _task_run(metrics={}),
        [
            DeliveryValidationEvidence(
                kind=DeliveryEvidenceKind.COMMAND,
                status="passed",
                artifact_id="command-1",
            ),
            DeliveryValidationEvidence(
                kind=DeliveryEvidenceKind.REVIEW,
                status="passed",
                artifact_id="review-1",
                risk_level="low",
            ),
        ],
    )

    assert decision.state == DeliveryState.PENDING_VALIDATION
    assert decision.evidence["eventType"] == "delivery.validation_passed"


def test_delivery_validation_requires_review_for_failed_command() -> None:
    decision = evaluate_delivery_validation(
        _task_run(metrics={}),
        [
            DeliveryValidationEvidence(
                kind=DeliveryEvidenceKind.COMMAND,
                status="failed",
                artifact_id="command-1",
                summary="pnpm build failed",
            )
        ],
    )

    assert decision.state == DeliveryState.REVIEW_REQUIRED
    assert decision.evidence["eventType"] == "delivery.review_required"
    assert decision.evidence["failures"][0]["summary"] == "pnpm build failed"


def test_delivery_validation_requires_review_for_high_risk_review() -> None:
    decision = evaluate_delivery_validation(
        _task_run(metrics={}),
        [
            DeliveryValidationEvidence(
                kind=DeliveryEvidenceKind.REVIEW,
                status="passed",
                artifact_id="review-1",
                risk_level="high",
                summary="Protected path concern",
            )
        ],
    )

    assert decision.state == DeliveryState.REVIEW_REQUIRED
    assert decision.evidence["failures"][0]["kind"] == "review"


def test_delivery_validation_requires_review_for_policy_denial() -> None:
    decision = evaluate_delivery_validation(
        _task_run(metrics={}),
        [
            DeliveryValidationEvidence(
                kind=DeliveryEvidenceKind.POLICY,
                status="denied",
                summary="Target path denied",
            )
        ],
    )

    assert decision.state == DeliveryState.REVIEW_REQUIRED
    assert decision.evidence["failures"][0]["kind"] == "policy"


def _task_run(*, metrics: dict) -> TaskRun:
    return TaskRun(
        id="task-run-1",
        task_id="task-1",
        agent_id="agent-1",
        state="completed",
        worktree_path="/tmp/worktree",
        metrics_json=json.dumps(metrics, separators=(",", ":")),
    )
