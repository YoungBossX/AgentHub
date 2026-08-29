import json
import os
import hashlib
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import exists, func, or_, update
from sqlmodel import Session as DbSession
from sqlmodel import select

from app.events import append_task_run_event
from app.diffs import capture_base_ref_for_worktree, capture_file_snapshot_for_worktree
from app.agent_selection_policy import AgentSelectionError, validate_agent_selection
from app.memory_snapshots import (
    ensure_session_memory_snapshot,
    memory_snapshot_metadata,
)
from app.models import Agent, SessionQueueEntry, TargetLock, Task, TaskRun, TaskRunEvent
from app.models import Session as AgentHubSession
from app.models import utc_now
from app.provider_assignments import (
    ProviderAssignmentError,
    resolve_provider_assignment,
)
from app.provider_gateway import CAPABILITIES_BY_ADAPTER
from app.agent_runtime_config import resolve_runtime_role_config
from app.target_registry import (
    AGENTHUB_PLATFORM_TARGET_ID,
    EFFECTIVE_WRITE_SCOPE_SCHEMA_VERSION,
    TargetRegistryError,
    canonical_write_scope_pattern,
    effective_write_scope_identity,
    get_target_for_workspace,
    is_canonical_repository_path,
)
from app.task_run_scope import (
    SCOPE_SNAPSHOT_SCHEMA_VERSION,
    SCOPE_VALIDATION_SCHEMA_VERSION,
    ScopeDecision,
    ScopeSnapshot,
    TargetLockAcquisitionContext,
    TaskRunScopeError,
    capture_worktree_scope_snapshot,
    clear_task_run_target_lock_acquisition_context,
    clear_task_run_scope_runtime_context,
    get_task_run_target_lock_acquisition_context,
    get_task_run_scope_runtime_context,
    new_scope_control_key,
    require_task_run_scope_runtime_context,
    scope_snapshot_from_metadata,
    store_task_run_scope_runtime_context,
    validate_scope_delta,
)

TASK_RUN_STATES = {
    "created",
    "queued",
    "streaming",
    "waiting_approval",
    "applying_changes",
    "collecting_diff",
    "starting_preview",
    "completed",
    "failed",
    "interrupted",
}
ACTIVE_STATES = {
    "created",
    "queued",
    "streaming",
    "waiting_approval",
    "applying_changes",
    "collecting_diff",
    "starting_preview",
}
RETRYABLE_STATES = {"failed", "interrupted"}
TERMINAL_STATES = {"completed", "failed", "interrupted"}
DEFAULT_CODE_ADAPTER_ENV = "AGENTHUB_DEFAULT_CODE_ADAPTER"
_SAFE_SCOPE_EVENT_CATEGORIES = frozenset({".env", ".git", "node_modules", "secrets"})
CODE_AGENT_ROLES = {"frontend", "backend"}
SUPPORTED_CODE_ADAPTERS = {"codex", "claude_code"}
DEFAULT_LEASE_SECONDS = 300
_SCOPE_DECISION_FALLBACK_CAS_ATTEMPTS = 3
_EXECUTION_ACCESS_BINDING_KEY = "taskRunExecutionAccessBinding"
_EXECUTION_ACCESS_BINDING_FIELDS = {
    "taskRunId",
    "taskId",
    "sessionId",
    "queueEntryId",
    "accessMode",
    "runnerId",
    "executionAttemptId",
}
_POST_LAUNCH_QUEUE_STATES = {
    "running",
    "completed",
    "failed",
    "interrupted",
    "cancelled",
}


class TaskRunLifecycleError(ValueError):
    pass


def create_task_run(
    db: DbSession,
    task_id: str,
    adapter_type: Optional[str] = None,
    retry_of_run_id: Optional[str] = None,
    fallback_from_run_id: Optional[str] = None,
    retry_metadata: Optional[dict[str, Any]] = None,
) -> TaskRun:
    task = _task_or_raise(db, task_id)
    session = _session_or_raise(db, task.session_id)
    memory_snapshot = ensure_session_memory_snapshot(db, session)
    agent = _agent_or_raise(db, task.assigned_agent_id)
    runtime_resolution = _runtime_resolution_for_task(db, task, session, agent)
    selected_adapter = adapter_type or (
        runtime_resolution.role_config.adapter_type
        if runtime_resolution is not None
        else _default_adapter_for_agent(agent)
    )
    try:
        provider_assignment = resolve_provider_assignment(
            task,
            agent,
            selected_adapter=selected_adapter,
            explicit_adapter_type=adapter_type,
            runtime_adapter_type=(
                runtime_resolution.role_config.adapter_type
                if adapter_type is None and runtime_resolution is not None
                else None
            ),
            runtime_provider_id=(
                runtime_resolution.role_config.provider_id
                if adapter_type is None and runtime_resolution is not None
                else None
            ),
            runtime_fallback_policy=(
                runtime_resolution.role_config.fallback_policy
                if adapter_type is None and runtime_resolution is not None
                else None
            ),
        )
    except ProviderAssignmentError as exc:
        raise TaskRunLifecycleError(str(exc)) from exc
    selected_adapter = provider_assignment.adapter_type
    execution_access_mode = _effective_execution_access_mode(
        task,
        selected_adapter,
    )
    try:
        agent_selection = validate_agent_selection(
            db,
            task,
            agent,
            explicit_adapter_type=adapter_type,
        )
    except AgentSelectionError as exc:
        raise TaskRunLifecycleError(str(exc)) from exc
    _recover_terminal_target_locks_before_run_creation(db)
    _ensure_scheduler_allows_run_creation(db, task)

    now = utc_now()
    worktree_path = _worktree_path_for_task(db, task, session)
    base_ref = capture_base_ref_for_worktree(worktree_path)
    metrics = {
        "adapterType": selected_adapter,
        "providerAssignment": provider_assignment.to_metadata(),
        "agentSelection": agent_selection.to_metadata(),
        "memorySnapshot": memory_snapshot_metadata(memory_snapshot),
    }
    if runtime_resolution is not None and adapter_type is None:
        metrics["runtimeConfigResolution"] = runtime_resolution.to_metadata()
    if retry_of_run_id is not None:
        metrics["retryOfRunId"] = retry_of_run_id
    if fallback_from_run_id is not None:
        metrics["fallbackFromRunId"] = fallback_from_run_id
    if retry_metadata is not None:
        metrics.update(retry_metadata)
    checkpoint = _pre_run_checkpoint_for_task(
        db,
        task,
        session,
        require_write_access=execution_access_mode == "write",
        worktree_path=worktree_path,
        base_ref=base_ref,
        now=now,
    )
    if checkpoint is not None:
        metrics["preRunCheckpoint"] = checkpoint

    approval_payload = _platform_approval_payload(task)
    initial_state = "waiting_approval" if approval_payload is not None else "queued"
    task.status = _task_status_for_run_state(initial_state)
    task.updated_at = now
    runner_id = _new_runner_id()
    task_run = TaskRun(
        task_id=task.id,
        agent_id=agent.id,
        state=initial_state,
        runner_id=runner_id,
        last_heartbeat_at=now,
        lease_expires_at=_lease_expires_at(now),
        worktree_path=worktree_path,
        base_ref=base_ref,
        metrics_json=json.dumps(metrics, separators=(",", ":")),
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    db.add(task_run)
    db.commit()
    db.refresh(task_run)

    _append_state_event(
        db,
        task_run,
        initial_state,
        {
            "adapterType": selected_adapter,
            "providerAssignment": provider_assignment.to_metadata(),
            "memorySnapshotId": memory_snapshot.id,
        },
    )
    _enqueue_session_queue_entry(
        db,
        task,
        task_run,
        access_mode=execution_access_mode,
    )
    if checkpoint is not None:
        append_task_run_event(
            db,
            task_run_id=task_run.id,
            event_type="task.checkpoint.created",
            payload_json=json.dumps(
                {"checkpoint": _public_scope_checkpoint(checkpoint)},
                separators=(",", ":"),
            ),
        )
    if approval_payload is not None:
        append_task_run_event(
            db,
            task_run_id=task_run.id,
            event_type="approval.requested",
            payload_json=json.dumps(approval_payload, separators=(",", ":")),
        )
    return task_run


def transition_task_run(
    db: DbSession,
    task_run_id: str,
    state: str,
    payload: Optional[dict[str, Any]] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
) -> TaskRun:
    if state not in TASK_RUN_STATES:
        raise ValueError(f"Unsupported TaskRun state: {state}")

    task_run = _task_run_or_raise(db, task_run_id)
    task = _task_or_raise(db, task_run.task_id)
    now = utc_now()

    task_run.state = state
    task_run.error_code = error_code
    task_run.error_message = error_message
    task_run.updated_at = now
    if state in ACTIVE_STATES:
        _touch_task_run_heartbeat(task_run, now=now)
    if state in {"streaming", "applying_changes"} and task_run.started_at is None:
        task_run.started_at = now
    if state in TERMINAL_STATES:
        task_run.ended_at = now

    task.status = _task_status_for_run_state(state)
    task.updated_at = now
    db.add(task)
    db.add(task_run)
    db.commit()
    db.refresh(task_run)
    event_payload = dict(payload or {})
    event_payload.setdefault("state", state)
    if error_code is not None:
        event_payload.setdefault("errorCode", error_code)
    if error_message is not None:
        event_payload.setdefault("errorMessage", error_message)
    event_payload.setdefault("adapterType", adapter_type_for_run(db, task_run))
    _append_state_event(db, task_run, state, event_payload)
    if state in TERMINAL_STATES:
        _finalize_queue_and_lock_for_terminal_run(db, task, task_run, state)
        from app.scheduler import mark_task_run_terminal_scheduler_state
        from app.scheduler import refresh_downstream_scheduler_state
        from app.scheduler import refresh_session_scheduler_state

        if state == "completed":
            from app.handoffs import create_dependency_handoffs

            create_dependency_handoffs(db, task_run)
        mark_task_run_terminal_scheduler_state(
            db,
            task,
            run_state=state,
            adapter_type=adapter_type_for_run(db, task_run),
            task_run_id=task_run.id,
        )
        refresh_downstream_scheduler_state(db, task.id)
        refresh_session_scheduler_state(db, task.session_id)
    return task_run


def refresh_task_run_heartbeat(
    db: DbSession,
    task_run_id: str,
    *,
    runner_id: Optional[str] = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> TaskRun:
    task_run = _task_run_or_raise(db, task_run_id)
    if task_run.state not in ACTIVE_STATES:
        raise TaskRunLifecycleError("Only active TaskRuns can refresh heartbeat.")
    if runner_id is not None and task_run.runner_id not in {None, runner_id}:
        raise TaskRunLifecycleError("Heartbeat runner does not own this TaskRun.")

    now = utc_now()
    _touch_task_run_heartbeat(
        task_run,
        now=now,
        runner_id=runner_id,
        lease_seconds=lease_seconds,
    )
    db.add(task_run)
    db.commit()
    db.refresh(task_run)
    append_task_run_event(
        db,
        task_run_id=task_run.id,
        event_type="task.heartbeat",
        payload_json=json.dumps(
            {
                "runnerId": task_run.runner_id,
                "lastHeartbeatAt": task_run.last_heartbeat_at.isoformat()
                if task_run.last_heartbeat_at is not None
                else None,
                "leaseExpiresAt": task_run.lease_expires_at.isoformat()
                if task_run.lease_expires_at is not None
                else None,
            },
            separators=(",", ":"),
        ),
    )
    return task_run


def claim_task_run_for_worker(
    db: DbSession,
    task_run_id: str,
    *,
    worker_id: str,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> TaskRun:
    task_run = _task_run_or_raise(db, task_run_id)
    if task_run.state != "queued":
        raise TaskRunLifecycleError("Only queued TaskRuns can be claimed by a worker.")

    now = utc_now()
    task_run.runner_id = worker_id
    task_run.last_heartbeat_at = now
    task_run.lease_expires_at = _lease_expires_at(now, lease_seconds)
    task_run.updated_at = now
    db.add(task_run)
    db.commit()
    db.refresh(task_run)
    append_task_run_event(
        db,
        task_run_id=task_run.id,
        event_type="run.claimed",
        payload_json=json.dumps(
            {
                "workerId": worker_id,
                "runnerId": task_run.runner_id,
                "claimedAt": now.isoformat(),
                "leaseExpiresAt": task_run.lease_expires_at.isoformat()
                if task_run.lease_expires_at is not None
                else None,
            },
            separators=(",", ":"),
        ),
    )
    return task_run


def stale_task_runs(
    db: DbSession,
    *,
    now: Optional[datetime] = None,
    exclude_target_lock_holders: bool = False,
) -> list[TaskRun]:
    timestamp = now or utc_now()
    statement = (
        select(TaskRun)
        .where(TaskRun.state.in_(ACTIVE_STATES))
        .where(TaskRun.lease_expires_at.is_not(None))
        .where(TaskRun.lease_expires_at < timestamp)
    )
    if exclude_target_lock_holders:
        held_target_lock = select(TargetLock.id).where(
            TargetLock.task_run_id == TaskRun.id,
            TargetLock.state == "held",
        )
        statement = statement.where(~exists(held_target_lock))
    return db.exec(statement.order_by(TaskRun.updated_at, TaskRun.id)).all()


def mark_stale_task_runs(
    db: DbSession,
    *,
    now: Optional[datetime] = None,
    reason: str = "lease_expired",
    exclude_target_lock_holders: bool = False,
) -> list[TaskRun]:
    timestamp = now or utc_now()
    marked: list[TaskRun] = []
    for task_run in stale_task_runs(
        db,
        now=timestamp,
        exclude_target_lock_holders=exclude_target_lock_holders,
    ):
        task = _task_or_raise(db, task_run.task_id)
        previous_state = task_run.state
        scope_error_code = _stale_collecting_diff_scope_error_code(
            db,
            task,
            task_run,
            previous_state=previous_state,
        )
        task_run.state = "failed"
        task_run.error_code = scope_error_code or "TASK_RUN_STALE"
        task_run.error_message = (
            "The task run changed paths outside the assigned target."
            if scope_error_code == "TASK_RUN_SCOPE_VIOLATION"
            else (
                "The task run scope evidence is unavailable or invalid after recovery."
                if scope_error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
                else (
                    "TaskRun heartbeat lease expired before completion; adapter success "
                    "was not claimed."
                )
            )
        )
        task_run.stale_detected_at = timestamp
        task_run.stale_reason = reason
        task_run.ended_at = timestamp
        task_run.updated_at = timestamp
        task.status = "failed"
        task.updated_at = timestamp
        db.add(task)
        db.add(task_run)
        db.commit()
        db.refresh(task_run)
        _finalize_queue_and_lock_for_terminal_run(db, task, task_run, "failed")

        if scope_error_code is not None:
            scope_payload = _scope_failure_event_payload(
                task_run,
                scope_error_code,
            )
            scope_payload["reasonCategory"] = "crash_recovery"
            append_task_run_event(
                db,
                task_run_id=task_run.id,
                event_type="task.scope_validation.failed",
                payload_json=json.dumps(scope_payload, separators=(",", ":")),
            )

        _append_state_event(
            db,
            task_run,
            "failed",
            {
                "previousState": previous_state,
                "errorCode": task_run.error_code,
                "errorMessage": task_run.error_message,
                "runnerId": task_run.runner_id,
                "leaseExpiresAt": task_run.lease_expires_at.isoformat()
                if task_run.lease_expires_at is not None
                else None,
                "staleDetectedAt": task_run.stale_detected_at.isoformat(),
                "staleReason": reason,
            },
        )
        append_task_run_event(
            db,
            task_run_id=task_run.id,
            event_type="task.stale",
            payload_json=json.dumps(
                {
                    "previousState": previous_state,
                    "newState": "failed",
                    "runnerId": task_run.runner_id,
                    "leaseExpiresAt": task_run.lease_expires_at.isoformat()
                    if task_run.lease_expires_at is not None
                    else None,
                    "staleDetectedAt": task_run.stale_detected_at.isoformat(),
                    "reason": reason,
                    "errorCode": task_run.error_code,
                    "errorMessage": task_run.error_message,
                },
                separators=(",", ":"),
            ),
        )

        from app.scheduler import mark_task_run_terminal_scheduler_state
        from app.scheduler import refresh_downstream_scheduler_state
        from app.scheduler import refresh_session_scheduler_state

        mark_task_run_terminal_scheduler_state(
            db,
            task,
            run_state="failed",
            adapter_type=adapter_type_for_run(db, task_run),
            task_run_id=task_run.id,
        )
        refresh_downstream_scheduler_state(db, task.id)
        refresh_session_scheduler_state(db, task.session_id)
        marked.append(task_run)
    return marked


def _stale_collecting_diff_scope_error_code(
    db: DbSession,
    task: Task,
    task_run: TaskRun,
    *,
    previous_state: str,
) -> Optional[str]:
    if previous_state != "collecting_diff":
        return None
    try:
        access_mode = require_task_run_execution_access_mode(db, task_run)
    except TaskRunScopeError:
        return "TASK_RUN_SCOPE_UNVERIFIABLE"
    if access_mode == "readonly":
        return None
    try:
        require_task_run_scope_passed(db, task_run.id)
    except TaskRunScopeError as exc:
        if exc.error_code == "TASK_RUN_SCOPE_VIOLATION":
            return "TASK_RUN_SCOPE_VIOLATION"
        return "TASK_RUN_SCOPE_UNVERIFIABLE"
    return None


def interrupt_task_run(db: DbSession, task_run_id: str) -> TaskRun:
    task_run = _task_run_or_raise(db, task_run_id)
    if task_run.state not in ACTIVE_STATES:
        raise TaskRunLifecycleError("Only active TaskRuns can be interrupted.")

    return transition_task_run(
        db,
        task_run_id,
        "interrupted",
        payload={"reason": "Interrupted by user."},
        error_code="TASK_RUN_INTERRUPTED",
        error_message="Task run was interrupted by the user.",
    )


def retry_task_run(
    db: DbSession,
    task_run_id: str,
    *,
    retry_mode: str = "current_state",
) -> TaskRun:
    previous = _retryable_run_or_raise(db, task_run_id)
    retry_metadata = _retry_metadata_for_previous_run(
        previous,
        retry_mode=retry_mode,
    )
    return create_task_run(
        db,
        task_id=previous.task_id,
        adapter_type=adapter_type_for_run(db, previous),
        retry_of_run_id=previous.id,
        retry_metadata=retry_metadata,
    )


def retry_with_scripted_mock(db: DbSession, task_run_id: str) -> TaskRun:
    previous = _task_run_or_raise(db, task_run_id)
    if previous.state not in RETRYABLE_STATES or adapter_type_for_run(db, previous) != "codex":
        raise TaskRunLifecycleError("Fallback requires a failed or interrupted Codex run.")

    retry_metadata = _retry_metadata_for_previous_run(
        previous,
        retry_mode="scripted_mock_fallback",
    )
    return create_task_run(
        db,
        task_id=previous.task_id,
        adapter_type="scripted_mock",
        retry_of_run_id=previous.id,
        fallback_from_run_id=previous.id,
        retry_metadata=retry_metadata,
    )


def list_task_runs(db: DbSession, task_id: str) -> list[TaskRun]:
    return db.exec(
        select(TaskRun)
        .where(TaskRun.task_id == task_id)
        .order_by(TaskRun.created_at, TaskRun.id)
    ).all()


def adapter_type_for_run(db: DbSession, task_run: TaskRun) -> str:
    metrics = _metrics(task_run)
    adapter_type = metrics.get("adapterType")
    if isinstance(adapter_type, str) and adapter_type:
        return adapter_type

    agent = db.get(Agent, task_run.agent_id)
    if agent is not None:
        return agent.adapter_type
    return "unknown"


def metrics_for_run(task_run: TaskRun) -> dict[str, Any]:
    metrics = dict(internal_metrics_for_run(task_run))
    metrics.pop("scopeControlKey", None)
    metrics.pop("scopeFinalizationClaim", None)
    metrics.pop(_EXECUTION_ACCESS_BINDING_KEY, None)

    public_decision = _public_scope_decision(
        task_run,
        metrics.get("taskRunScopeDecision"),
    )
    if public_decision is None:
        metrics.pop("taskRunScopeDecision", None)
    else:
        metrics["taskRunScopeDecision"] = public_decision

    public_guard = _public_scope_guard(
        task_run,
        metrics.get("taskRunScopeGuard"),
    )
    if public_guard is None:
        metrics.pop("taskRunScopeGuard", None)
    else:
        metrics["taskRunScopeGuard"] = public_guard

    checkpoint = metrics.get("preRunCheckpoint")
    if not isinstance(checkpoint, dict):
        metrics.pop("preRunCheckpoint", None)
        return metrics
    metrics["preRunCheckpoint"] = _public_scope_checkpoint(checkpoint)
    return metrics


def _public_scope_decision(
    task_run: TaskRun,
    evidence: object,
) -> Optional[dict[str, Any]]:
    if (
        not _is_valid_scope_decision_evidence(evidence)
        or evidence["taskRunId"] != task_run.id
        or not _is_safe_scope_event_identifier(evidence["targetId"])
    ):
        return None
    status = evidence["status"]
    return {
        "schemaVersion": SCOPE_VALIDATION_SCHEMA_VERSION,
        "taskRunId": task_run.id,
        "targetId": evidence["targetId"],
        "baselineSchemaVersion": SCOPE_SNAPSHOT_SCHEMA_VERSION,
        "status": status,
        "changedPathCount": evidence["changedPathCount"],
        "timestamp": evidence["timestamp"],
        "errorCode": evidence["errorCode"],
        "reason": _public_scope_reason(status),
    }


def _public_scope_guard(
    task_run: TaskRun,
    evidence: object,
) -> Optional[dict[str, Any]]:
    if (
        not _is_valid_scope_guard_marker(evidence)
        or evidence["taskRunId"] != task_run.id
        or not _is_safe_scope_event_identifier(evidence["targetId"])
    ):
        return None
    return {
        "schemaVersion": SCOPE_VALIDATION_SCHEMA_VERSION,
        "taskRunId": task_run.id,
        "targetId": evidence["targetId"],
        "baselineSchemaVersion": SCOPE_SNAPSHOT_SCHEMA_VERSION,
        "status": "passed",
        "changedPathCount": evidence["changedPathCount"],
        "timestamp": evidence["timestamp"],
    }


def _public_scope_reason(status: str) -> Optional[str]:
    if status == "rejected":
        return "The task run changed paths outside the assigned target."
    if status == "unverifiable":
        return "The task run scope evidence is unavailable or invalid."
    return None


def _public_scope_checkpoint(checkpoint: object) -> dict[str, Any]:
    if not isinstance(checkpoint, dict):
        return {}
    public: dict[str, Any] = {}

    target_id = checkpoint.get("targetId")
    if _is_safe_scope_event_identifier(target_id):
        public["targetId"] = target_id

    for field_name in ("allowedPaths", "deniedPaths"):
        patterns = _public_policy_patterns(checkpoint.get(field_name))
        if patterns is not None:
            public[field_name] = patterns

    for field_name in ("plannedFiles", "dirtyFiles"):
        paths = _public_repository_paths(checkpoint.get(field_name))
        if paths is not None:
            public[field_name] = paths

    base_commit = checkpoint.get("baseCommit")
    if _is_hex_digest(base_commit, lengths={40, 64}):
        public["baseCommit"] = base_commit

    git_status = _public_git_status(checkpoint.get("gitStatus"))
    if git_status is not None:
        public["gitStatus"] = git_status

    contract_id = checkpoint.get("contractId")
    contract_hash = checkpoint.get("contractHash")
    if (
        _is_safe_checkpoint_identifier(contract_id)
        and _is_hex_digest(contract_hash, lengths={64})
    ):
        public["contractId"] = contract_id
        public["contractHash"] = contract_hash

    created_at = checkpoint.get("createdAt")
    if _is_safe_checkpoint_timestamp(created_at):
        public["createdAt"] = created_at

    if "scopeBaseline" in checkpoint:
        public["scopeBaseline"] = _public_scope_baseline(
            checkpoint.get("scopeBaseline")
        )
    return public


def _public_policy_patterns(value: object) -> Optional[list[str]]:
    if not isinstance(value, list):
        return None
    try:
        return [canonical_write_scope_pattern(pattern) for pattern in value]
    except TargetRegistryError:
        return None


def _public_repository_paths(value: object) -> Optional[list[str]]:
    if not isinstance(value, list) or not all(
        is_canonical_repository_path(path) for path in value
    ):
        return None
    return list(value)


def _public_git_status(value: object) -> Optional[dict[str, Any]]:
    if not isinstance(value, dict) or type(value.get("available")) is not bool:
        return None
    dirty_files = _public_repository_paths(value.get("dirtyFiles"))
    if dirty_files is None:
        return None
    result: dict[str, Any] = {
        "available": value["available"],
        "dirtyFiles": dirty_files,
    }
    if not value["available"]:
        result["reason"] = "git_status_unavailable"
    return result


def _public_scope_baseline(value: object) -> dict[str, object]:
    snapshot = scope_snapshot_from_metadata(value)
    metadata = snapshot.to_metadata()
    if not snapshot.available:
        metadata["reason"] = "scope_snapshot_unavailable"
    return metadata


def _is_hex_digest(value: object, *, lengths: set[int]) -> bool:
    return (
        isinstance(value, str)
        and len(value) in lengths
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_safe_checkpoint_identifier(value: object) -> bool:
    if not _is_safe_scope_event_identifier(value):
        return False
    normalized = value.lower()
    return not normalized.startswith(("sk-", "ghp_", "xox")) and not any(
        marker in normalized
        for marker in ("secret", "token", "password", "api-key", "apikey")
    )


def _is_safe_checkpoint_timestamp(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def internal_metrics_for_run(task_run: TaskRun) -> dict[str, Any]:
    return _metrics(task_run)


def capture_task_run_scope_baseline(
    db: DbSession,
    task_run_id: str,
    *,
    execution_attempt_id: Optional[str] = None,
) -> TaskRun:
    task_run = _task_run_or_raise(db, task_run_id)
    claimed_execution_attempt = execution_attempt_id is not None
    if claimed_execution_attempt:
        checkpoint = _metrics(task_run).get("preRunCheckpoint")
        if (
            not isinstance(execution_attempt_id, str)
            or not execution_attempt_id
            or not isinstance(checkpoint, dict)
            or checkpoint.get("scopeExecutionAttemptId") != execution_attempt_id
            or "scopeBaseline" in checkpoint
        ):
            raise _scope_unverifiable_error()
    else:
        execution_attempt_id = str(uuid4())
    access_mode = require_task_run_execution_access_mode(
        db,
        task_run,
        require_started=False,
    )
    if access_mode == "readonly":
        return task_run
    task = db.get(Task, task_run.task_id)

    control_key = new_scope_control_key()
    baseline_identity = str(uuid4())
    clear_task_run_scope_runtime_context(task_run.id)
    snapshot = _unavailable_scope_baseline("scope_baseline_target_unavailable")
    scope_workspace_id: Optional[str] = None
    scope_target_id: Optional[str] = None
    scope_policy_identity: Optional[str] = None
    scope_lock_identity: Optional[str] = None
    session = db.get(AgentHubSession, task.session_id) if task is not None else None
    if task is not None and session is not None:
        from app.scheduler import target_id_for_task

        target_id = target_id_for_task(task, db)
        if target_id is not None:
            try:
                target = get_target_for_workspace(db, session.workspace_id, target_id)
                policy_identity = effective_write_scope_identity(target)
            except Exception:
                snapshot = _unavailable_scope_baseline(
                    "scope_baseline_target_unavailable"
                )
            else:
                scope_workspace_id = session.workspace_id
                scope_target_id = target_id
                scope_policy_identity = policy_identity
                from app.target_locks import held_lock_for_target

                held_lock = held_lock_for_target(db, target_id)
                acquisition_context = _matching_target_lock_acquisition_context(
                    task_run,
                    task,
                    target_id,
                    held_lock,
                )
                if acquisition_context is None:
                    snapshot = _unavailable_scope_baseline(
                        "scope_baseline_lock_unavailable"
                    )
                else:
                    scope_lock_identity = acquisition_context.lock_id
                    try:
                        captured_snapshot = capture_worktree_scope_snapshot(
                            task_run.worktree_path,
                            control_key=control_key,
                        )
                    except Exception:
                        snapshot = _unavailable_scope_baseline(
                            "scope_capture_unavailable"
                        )
                    else:
                        snapshot = (
                            captured_snapshot
                            if captured_snapshot.available
                            else _unavailable_scope_baseline(
                                "scope_capture_unavailable"
                            )
                        )

    baseline_captured_at = _utc_scope_timestamp()
    if claimed_execution_attempt:
        db.refresh(task_run)
        claimed_checkpoint = _metrics(task_run).get("preRunCheckpoint")
        if (
            not isinstance(claimed_checkpoint, dict)
            or claimed_checkpoint.get("scopeExecutionAttemptId")
            != execution_attempt_id
            or "scopeBaseline" in claimed_checkpoint
            or scope_target_id is None
            or scope_lock_identity is None
            or not _task_run_holds_scope_target_lock(
                db,
                task_run,
                scope_target_id,
                lock_identity=scope_lock_identity,
            )
        ):
            raise _scope_unverifiable_error()
    metrics = _metrics(task_run)
    checkpoint = metrics.get("preRunCheckpoint")
    checkpoint = dict(checkpoint) if isinstance(checkpoint, dict) else {}
    checkpoint["scopeBaseline"] = snapshot.to_metadata(include_internal=True)
    checkpoint["scopeBaselineTaskRunId"] = task_run.id
    checkpoint["scopeBaselineIdentity"] = baseline_identity
    checkpoint["scopeBaselineCapturedAt"] = baseline_captured_at
    checkpoint["scopeExecutionAttemptId"] = execution_attempt_id
    checkpoint["scopeWorkspaceId"] = scope_workspace_id
    checkpoint["scopePolicySchemaVersion"] = EFFECTIVE_WRITE_SCOPE_SCHEMA_VERSION
    checkpoint["scopePolicyIdentity"] = scope_policy_identity
    metrics["preRunCheckpoint"] = checkpoint
    metrics.pop("scopeControlKey", None)
    metrics.pop("taskRunScopeGuard", None)
    metrics.pop("taskRunScopeDecision", None)
    task_run.metrics_json = json.dumps(metrics, separators=(",", ":"))
    task_run.updated_at = utc_now()
    db.add(task_run)
    db.commit()
    db.refresh(task_run)

    if snapshot.available and snapshot._trusted_git_dir:
        if scope_lock_identity is None:
            raise _scope_unverifiable_error()
        store_task_run_scope_runtime_context(
            task_run.id,
            trusted_git_dir=snapshot._trusted_git_dir,
            workspace_id=scope_workspace_id,
            target_id=scope_target_id,
            policy_identity=scope_policy_identity,
            baseline_identity=baseline_identity,
            baseline_captured_at=baseline_captured_at,
            execution_attempt_id=execution_attempt_id,
            lock_id=scope_lock_identity,
            control_key=control_key,
        )
    return task_run


def require_task_run_scope_baseline(
    db: DbSession,
    task_run_id: str,
) -> ScopeSnapshot:
    task_run = _task_run_or_raise(db, task_run_id)
    binding = _scope_baseline_binding(task_run)
    target_resolution = _workspace_target_for_task_run(db, task_run)
    if (
        binding is None
        or target_resolution is None
        or not _scope_resolution_matches_binding(target_resolution, binding)
    ):
        raise _scope_unverifiable_error()
    runtime_context = require_task_run_scope_runtime_context(
        task_run.id,
        workspace_id=binding["workspace_id"],
        target_id=binding["target_id"],
        policy_identity=binding["policy_identity"],
        baseline_identity=binding["baseline_identity"],
        baseline_captured_at=binding["baseline_captured_at"],
        execution_attempt_id=binding["execution_attempt_id"],
    )
    task = db.get(Task, task_run.task_id)
    from app.target_locks import held_lock_for_target

    held_lock = held_lock_for_target(db, target_resolution[1])
    acquisition_context = (
        _matching_target_lock_acquisition_context(
            task_run,
            task,
            target_resolution[1],
            held_lock,
        )
        if task is not None
        else None
    )
    if (
        acquisition_context is None
        or runtime_context.lock_id is None
        or runtime_context.lock_id != acquisition_context.lock_id
        or not _task_run_holds_scope_target_lock(
            db,
            task_run,
            target_resolution[1],
            lock_identity=runtime_context.lock_id,
        )
    ):
        raise _scope_unverifiable_error()
    return binding["snapshot"]


def validate_task_run_scope(
    db: DbSession,
    task_run_id: str,
) -> ScopeDecision:
    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        return _unverifiable_scope_decision("")
    target_resolution = _workspace_target_for_task_run(db, task_run)
    if target_resolution is None:
        return _unverifiable_scope_decision(_target_id_for_task_run(db, task_run))
    _, target_id, target = target_resolution
    binding = _scope_baseline_binding(task_run)
    if (
        binding is None
        or not _scope_resolution_matches_binding(target_resolution, binding)
    ):
        return _unverifiable_scope_decision(target_id)
    try:
        runtime_context = require_task_run_scope_runtime_context(
            task_run.id,
            workspace_id=binding["workspace_id"],
            target_id=binding["target_id"],
            policy_identity=binding["policy_identity"],
            baseline_identity=binding["baseline_identity"],
            baseline_captured_at=binding["baseline_captured_at"],
            execution_attempt_id=binding["execution_attempt_id"],
        )
        if (
            runtime_context.lock_id is None
            or not _task_run_holds_scope_target_lock(
                db,
                task_run,
                target_id,
                lock_identity=runtime_context.lock_id,
            )
        ):
            return _unverifiable_scope_decision(target_id)
        current = capture_worktree_scope_snapshot(
            task_run.worktree_path,
            control_key=runtime_context.control_key,
            trusted_git_dir=runtime_context.trusted_git_dir,
        )
        if not _task_run_holds_scope_target_lock(
            db,
            task_run,
            target_id,
            lock_identity=runtime_context.lock_id,
        ):
            return _unverifiable_scope_decision(target_id)
    except Exception:
        return _unverifiable_scope_decision(target_id)
    return validate_scope_delta(target, binding["snapshot"], current)


def persist_scope_decision(
    db: DbSession,
    task_run: TaskRun,
    decision: ScopeDecision,
) -> TaskRun:
    task_run = _task_run_or_raise(db, task_run.id)
    expected_metrics_json = task_run.metrics_json
    binding = _scope_baseline_binding(task_run)
    decision_to_persist = decision
    if decision.status in {"passed", "rejected"}:
        validated_decision = validate_task_run_scope(db, task_run.id)
        if validated_decision != decision:
            decision_to_persist = _unverifiable_scope_decision(
                _target_id_for_task_run(db, task_run)
            )
        else:
            decision_to_persist = validated_decision
    persisted_decision = _persistable_scope_decision(
        db,
        task_run,
        decision_to_persist,
        binding=binding,
    )
    expected_lock_id: Optional[str] = None
    if persisted_decision.status in {"passed", "rejected"}:
        expected_lock_id = _scope_runtime_lock_id(task_run, binding)
        if expected_lock_id is None:
            persisted_decision = _unverifiable_scope_decision(
                _target_id_for_task_run(db, task_run)
            )
    timestamp = _utc_scope_timestamp()
    decision_evidence = _scope_decision_evidence(
        task_run,
        persisted_decision,
        binding=binding,
        timestamp=timestamp,
    )
    metrics = _scope_metrics_with_decision(
        _metrics(task_run),
        persisted_decision,
        decision_evidence,
        binding=binding,
    )
    updated_at = utc_now()
    metrics_json = json.dumps(metrics, separators=(",", ":"))
    if (
        persisted_decision.status in {"passed", "rejected"}
        and expected_lock_id is not None
    ):
        if _persist_scope_metrics_under_current_lock(
            db,
            task_run,
            target_id=persisted_decision.target_id,
            expected_lock_id=expected_lock_id,
            expected_metrics_json=expected_metrics_json,
            metrics_json=metrics_json,
            updated_at=updated_at,
        ):
            db.refresh(task_run)
            return task_run

        persisted_decision = _unverifiable_scope_decision(
            persisted_decision.target_id
        )
    return _persist_unverifiable_scope_decision_with_cas(
        db,
        task_run,
        persisted_decision,
        timestamp=timestamp,
    )


def _persist_unverifiable_scope_decision_with_cas(
    db: DbSession,
    task_run: TaskRun,
    decision: ScopeDecision,
    *,
    timestamp: str,
) -> TaskRun:
    if decision.status != "unverifiable":
        decision = _unverifiable_scope_decision(decision.target_id)
    for _ in range(_SCOPE_DECISION_FALLBACK_CAS_ATTEMPTS):
        db.refresh(task_run)
        expected_metrics_json = task_run.metrics_json
        binding = _scope_baseline_binding(task_run)
        current_decision = _unverifiable_scope_decision(
            _target_id_for_task_run(db, task_run)
        )
        decision_evidence = _scope_decision_evidence(
            task_run,
            current_decision,
            binding=binding,
            timestamp=timestamp,
        )
        metrics = _scope_metrics_with_decision(
            _metrics(task_run),
            current_decision,
            decision_evidence,
            binding=binding,
        )
        if _persist_scope_metrics_cas(
            db,
            task_run_id=task_run.id,
            expected_metrics_json=expected_metrics_json,
            metrics_json=json.dumps(metrics, separators=(",", ":")),
            updated_at=utc_now(),
        ):
            db.refresh(task_run)
            return task_run
    db.refresh(task_run)
    raise _scope_unverifiable_error()


def _persist_scope_metrics_cas(
    db: DbSession,
    *,
    task_run_id: str,
    expected_metrics_json: str,
    metrics_json: str,
    updated_at: datetime,
) -> bool:
    try:
        result = db.execute(
            update(TaskRun)
            .where(TaskRun.id == task_run_id)
            .where(TaskRun.metrics_json == expected_metrics_json)
            .values(metrics_json=metrics_json, updated_at=updated_at)
            .execution_options(synchronize_session=False)
        )
        db.commit()
    except Exception:
        db.rollback()
        return False
    return result.rowcount == 1


def _scope_decision_evidence(
    task_run: TaskRun,
    decision: ScopeDecision,
    *,
    binding: Optional[dict[str, Any]],
    timestamp: str,
) -> dict[str, Any]:
    return {
        "schemaVersion": SCOPE_VALIDATION_SCHEMA_VERSION,
        "taskRunId": task_run.id,
        "targetId": decision.target_id,
        "workspaceId": (
            binding["workspace_id"] if binding is not None else None
        ),
        "scopePolicySchemaVersion": (
            binding["policy_schema_version"] if binding is not None else None
        ),
        "scopePolicyIdentity": (
            binding["policy_identity"] if binding is not None else None
        ),
        "baselineSchemaVersion": (
            binding["snapshot"].schema_version if binding is not None else None
        ),
        "baselineIdentity": (
            binding["baseline_identity"] if binding is not None else None
        ),
        "baselineCapturedAt": (
            binding["baseline_captured_at"] if binding is not None else None
        ),
        "executionAttemptId": (
            binding["execution_attempt_id"] if binding is not None else None
        ),
        "status": decision.status,
        "changedPathCount": len(decision.changed_paths),
        "timestamp": timestamp,
        "errorCode": decision.error_code,
        "reason": _safe_scope_marker_reason(decision),
    }


def _scope_metrics_with_decision(
    metrics: dict[str, Any],
    decision: ScopeDecision,
    decision_evidence: dict[str, Any],
    *,
    binding: Optional[dict[str, Any]],
) -> dict[str, Any]:
    metrics = dict(metrics)
    metrics["taskRunScopeDecision"] = decision_evidence
    metrics.pop("taskRunScopeGuard", None)
    if decision.status == "passed" and binding is not None:
        metrics["taskRunScopeGuard"] = {
            key: decision_evidence[key]
            for key in (
                "schemaVersion",
                "taskRunId",
                "targetId",
                "workspaceId",
                "scopePolicySchemaVersion",
                "scopePolicyIdentity",
                "baselineSchemaVersion",
                "baselineIdentity",
                "baselineCapturedAt",
                "executionAttemptId",
                "status",
                "changedPathCount",
                "timestamp",
            )
        }
    return metrics


def _scope_runtime_lock_id(
    task_run: TaskRun,
    binding: Optional[dict[str, Any]],
) -> Optional[str]:
    if binding is None:
        return None
    try:
        runtime_context = require_task_run_scope_runtime_context(
            task_run.id,
            workspace_id=binding["workspace_id"],
            target_id=binding["target_id"],
            policy_identity=binding["policy_identity"],
            baseline_identity=binding["baseline_identity"],
            baseline_captured_at=binding["baseline_captured_at"],
            execution_attempt_id=binding["execution_attempt_id"],
        )
    except TaskRunScopeError:
        return None
    if not isinstance(runtime_context.lock_id, str) or not runtime_context.lock_id:
        return None
    return runtime_context.lock_id


def _persist_scope_metrics_under_current_lock(
    db: DbSession,
    task_run: TaskRun,
    *,
    target_id: str,
    expected_lock_id: str,
    expected_metrics_json: str,
    metrics_json: str,
    updated_at: datetime,
) -> bool:
    task = db.get(Task, task_run.task_id)
    runner_id = task_run.runner_id
    if (
        task is None
        or not isinstance(runner_id, str)
        or not runner_id
        or not target_id
        or not expected_lock_id
    ):
        return False
    current_lock = select(TargetLock.id).where(
        TargetLock.id == expected_lock_id,
        TargetLock.target_id == target_id,
        TargetLock.session_id == task.session_id,
        TargetLock.task_run_id == task_run.id,
        TargetLock.worker_id == runner_id,
        TargetLock.mode == "write",
        TargetLock.state == "held",
        or_(
            TargetLock.lease_expires_at.is_(None),
            func.julianday(TargetLock.lease_expires_at) > func.julianday("now"),
        ),
    )
    try:
        result = db.execute(
            update(TaskRun)
            .where(TaskRun.id == task_run.id)
            .where(TaskRun.runner_id == runner_id)
            .where(TaskRun.metrics_json == expected_metrics_json)
            .where(exists(current_lock))
            .values(metrics_json=metrics_json, updated_at=updated_at)
            .execution_options(synchronize_session=False)
        )
        db.commit()
    except Exception:
        db.rollback()
        return False
    return result.rowcount == 1


def require_task_run_scope_passed(
    db: DbSession,
    task_run_id: str,
) -> ScopeDecision:
    task_run = _task_run_or_raise(db, task_run_id)
    metrics = _metrics(task_run)
    marker = metrics.get("taskRunScopeGuard")
    checkpoint = metrics.get("preRunCheckpoint")
    decision_evidence = metrics.get("taskRunScopeDecision")
    target_resolution = _workspace_target_for_task_run(db, task_run)
    if not _is_valid_scope_guard_marker(marker):
        _raise_for_persisted_scope_failure(
            decision_evidence,
            task_run=task_run,
            checkpoint=checkpoint,
            target_resolution=target_resolution,
        )
    if (
        not _scope_marker_matches_checkpoint(marker, task_run, checkpoint)
        or not _scope_marker_matches_decision(marker, decision_evidence)
    ):
        raise _scope_unverifiable_error()
    if (
        target_resolution is None
        or not _scope_resolution_matches_evidence(target_resolution, marker)
    ):
        raise _scope_unverifiable_error()
    target_id = target_resolution[1]
    return ScopeDecision(
        status="passed",
        error_code=None,
        target_id=target_id,
        changed_paths=(),
        rejected_paths=(),
        reason=None,
    )


def require_task_run_artifact_scope_passed(
    db: DbSession,
    task_run_id: str,
) -> Optional[ScopeDecision]:
    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        raise TaskRunScopeError(
            "TASK_RUN_SCOPE_UNVERIFIABLE",
            "The artifact source TaskRun cannot be verified.",
        )
    task = db.get(Task, task_run.task_id)
    if task is None:
        error = TaskRunScopeError(
            "TASK_RUN_SCOPE_UNVERIFIABLE",
            "The artifact source task cannot be verified.",
        )
        _record_artifact_scope_refusal_event(db, task_run, error.error_code)
        raise error
    try:
        access_mode = require_task_run_execution_access_mode(db, task_run)
        if access_mode == "readonly":
            return None
        return require_task_run_scope_passed(db, task_run_id)
    except TaskRunScopeError as exc:
        _record_artifact_scope_refusal_event(db, task_run, exc.error_code)
        raise


def require_task_run_execution_access_mode(
    db: DbSession,
    task_run: TaskRun,
    *,
    require_started: bool = True,
) -> str:
    from app.scheduler import target_id_for_task, write_lock_required_for_task
    from app.session_queue import (
        READONLY_ACCESS_MODE,
        WRITE_ACCESS_MODE,
        target_lock_key_for_target,
    )

    task = db.get(Task, task_run.task_id)
    entry = db.exec(
        select(SessionQueueEntry).where(
            SessionQueueEntry.task_run_id == task_run.id
        )
    ).first()
    if (
        task is None
        or entry is None
        or entry.task_id != task_run.task_id
        or entry.session_id != task.session_id
        or entry.access_mode not in {WRITE_ACCESS_MODE, READONLY_ACCESS_MODE}
    ):
        raise _execution_access_mode_error(db, task_run)

    metrics = _metrics(task_run)
    adapter_type = metrics.get("adapterType")
    if (
        not isinstance(adapter_type, str)
        or not adapter_type
        or adapter_type != adapter_type.strip()
        or adapter_type not in CAPABILITIES_BY_ADAPTER
    ):
        raise _execution_access_mode_error(db, task_run)
    expected_access_mode = _effective_execution_access_mode(task, adapter_type)
    if entry.access_mode != expected_access_mode:
        raise _execution_access_mode_error(db, task_run)

    current_target_id = target_id_for_task(task, db)
    if entry.target_id != current_target_id:
        raise _execution_access_mode_error(db, task_run)
    if entry.access_mode == WRITE_ACCESS_MODE:
        if entry.target_lock_key != target_lock_key_for_target(entry.target_id):
            raise _execution_access_mode_error(db, task_run)
        access_mode = WRITE_ACCESS_MODE
    elif entry.target_lock_key is not None or write_lock_required_for_task(task):
        raise _execution_access_mode_error(db, task_run)
    else:
        if isinstance(metrics.get("preRunCheckpoint"), dict) or any(
            key in metrics
            for key in ("scopeControlKey", "taskRunScopeDecision", "taskRunScopeGuard")
        ):
            raise _execution_access_mode_error(db, task_run)
        access_mode = READONLY_ACCESS_MODE

    if require_started:
        _require_post_launch_execution_access_binding(
            task_run,
            task,
            entry,
            access_mode=access_mode,
        )
    return access_mode


def persist_task_run_execution_access_binding(
    db: DbSession,
    task_run_id: str,
    *,
    access_mode: str,
    execution_attempt_id: str,
) -> TaskRun:
    task_run = _task_run_or_raise(db, task_run_id)
    db.refresh(task_run)
    bound_mode = require_task_run_execution_access_mode(
        db,
        task_run,
        require_started=False,
    )
    task = db.get(Task, task_run.task_id)
    entry = db.exec(
        select(SessionQueueEntry).where(
            SessionQueueEntry.task_run_id == task_run.id
        )
    ).first()
    if (
        task is None
        or entry is None
        or access_mode != bound_mode
        or entry.state != "running"
        or entry.started_at is None
        or not isinstance(task_run.runner_id, str)
        or not task_run.runner_id
        or not isinstance(execution_attempt_id, str)
        or not execution_attempt_id
        or task_run.adapter_run_id is not None
        or task_run.started_at is not None
    ):
        raise _scope_unverifiable_error()

    metrics = _metrics(task_run)
    if _EXECUTION_ACCESS_BINDING_KEY in metrics:
        raise _scope_unverifiable_error()
    checkpoint = metrics.get("preRunCheckpoint")
    if access_mode == "write":
        binding = _scope_baseline_binding(task_run)
        if (
            binding is None
            or binding["execution_attempt_id"] != execution_attempt_id
        ):
            raise _scope_unverifiable_error()
    elif isinstance(checkpoint, dict):
        raise _scope_unverifiable_error()

    access_binding = {
        "taskRunId": task_run.id,
        "taskId": task.id,
        "sessionId": task.session_id,
        "queueEntryId": entry.id,
        "accessMode": access_mode,
        "runnerId": task_run.runner_id,
        "executionAttemptId": execution_attempt_id,
    }
    original_metrics_json = task_run.metrics_json
    metrics[_EXECUTION_ACCESS_BINDING_KEY] = access_binding
    try:
        result = db.execute(
            update(TaskRun)
            .where(TaskRun.id == task_run.id)
            .where(TaskRun.state == task_run.state)
            .where(TaskRun.runner_id == task_run.runner_id)
            .where(TaskRun.adapter_run_id.is_(None))
            .where(TaskRun.started_at.is_(None))
            .where(TaskRun.metrics_json == original_metrics_json)
            .values(
                metrics_json=json.dumps(metrics, separators=(",", ":")),
                updated_at=utc_now(),
            )
            .execution_options(synchronize_session=False)
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise _scope_unverifiable_error() from exc
    db.refresh(task_run)
    if result.rowcount != 1:
        raise _scope_unverifiable_error()

    task = db.get(Task, task_run.task_id)
    entry = db.exec(
        select(SessionQueueEntry).where(
            SessionQueueEntry.task_run_id == task_run.id
        )
    ).first()
    if task is None or entry is None:
        raise _scope_unverifiable_error()
    _require_execution_access_binding_values(
        task_run,
        task,
        entry,
        access_mode=access_mode,
        require_adapter_created=False,
    )
    return task_run


def _require_post_launch_execution_access_binding(
    task_run: TaskRun,
    task: Task,
    entry: SessionQueueEntry,
    *,
    access_mode: str,
) -> None:
    _require_execution_access_binding_values(
        task_run,
        task,
        entry,
        access_mode=access_mode,
        require_adapter_created=True,
    )


def _require_execution_access_binding_values(
    task_run: TaskRun,
    task: Task,
    entry: SessionQueueEntry,
    *,
    access_mode: str,
    require_adapter_created: bool,
) -> None:
    from app.scheduler import write_lock_required_for_task

    metrics = _metrics(task_run)
    binding = metrics.get(_EXECUTION_ACCESS_BINDING_KEY)
    if not isinstance(binding, dict) or set(binding) != _EXECUTION_ACCESS_BINDING_FIELDS:
        raise _scope_unverifiable_error()
    expected = {
        "taskRunId": task_run.id,
        "taskId": task.id,
        "sessionId": task.session_id,
        "queueEntryId": entry.id,
        "accessMode": access_mode,
        "runnerId": task_run.runner_id,
    }
    if any(binding.get(key) != value for key, value in expected.items()):
        raise _scope_unverifiable_error()
    execution_attempt_id = binding.get("executionAttemptId")
    if not isinstance(execution_attempt_id, str) or not execution_attempt_id:
        raise _scope_unverifiable_error()
    if entry.state not in _POST_LAUNCH_QUEUE_STATES or entry.started_at is None:
        raise _scope_unverifiable_error()
    if require_adapter_created and (
        task_run.started_at is None
        or not isinstance(task_run.adapter_run_id, str)
        or not task_run.adapter_run_id
    ):
        raise _scope_unverifiable_error()

    checkpoint = metrics.get("preRunCheckpoint")
    if access_mode == "write":
        scope_binding = _scope_baseline_binding(task_run)
        if (
            scope_binding is None
            or scope_binding["execution_attempt_id"] != execution_attempt_id
        ):
            raise _scope_unverifiable_error()
    elif isinstance(checkpoint, dict) or write_lock_required_for_task(task):
        raise _scope_unverifiable_error()


def _execution_access_mode_error(
    db: DbSession,
    task_run: TaskRun,
) -> TaskRunScopeError:
    try:
        require_task_run_scope_passed(db, task_run.id)
    except TaskRunScopeError as exc:
        if exc.error_code == "TASK_RUN_SCOPE_VIOLATION":
            return exc
    return _scope_unverifiable_error()


def _record_artifact_scope_refusal_event(
    db: DbSession,
    task_run: TaskRun,
    error_code: str,
) -> None:
    existing = db.exec(
        select(TaskRunEvent.id)
        .where(TaskRunEvent.task_run_id == task_run.id)
        .where(TaskRunEvent.event_type == "task.artifact_scope_refused")
    ).first()
    if existing is not None:
        return
    append_task_run_event(
        db,
        task_run_id=task_run.id,
        event_type="task.artifact_scope_refused",
        payload_json=json.dumps(
            _scope_failure_event_payload(task_run, error_code),
            separators=(",", ":"),
        ),
    )


def _scope_failure_event_payload(
    task_run: TaskRun,
    error_code: str,
) -> dict[str, Any]:
    violation = error_code == "TASK_RUN_SCOPE_VIOLATION"
    payload: dict[str, Any] = {
        "result": "violation" if violation else "unverifiable",
        "errorCode": (
            "TASK_RUN_SCOPE_VIOLATION"
            if violation
            else "TASK_RUN_SCOPE_UNVERIFIABLE"
        ),
        "taskRunId": task_run.id,
    }
    metrics = _metrics(task_run)
    decision = metrics.get("taskRunScopeDecision")
    if (
        _is_valid_scope_decision_evidence(decision)
        and decision["taskRunId"] == task_run.id
    ):
        target_id = decision["targetId"]
        if _is_safe_scope_event_identifier(target_id):
            payload["targetId"] = target_id
        if decision["baselineSchemaVersion"] == SCOPE_SNAPSHOT_SCHEMA_VERSION:
            payload["snapshotVersion"] = SCOPE_SNAPSHOT_SCHEMA_VERSION
        payload["changedPathCount"] = decision["changedPathCount"]

    checkpoint = metrics.get("preRunCheckpoint")
    baseline = checkpoint.get("scopeBaseline") if isinstance(checkpoint, dict) else None
    if (
        isinstance(baseline, dict)
        and baseline.get("schema_version") == SCOPE_SNAPSHOT_SCHEMA_VERSION
    ):
        payload.setdefault("snapshotVersion", SCOPE_SNAPSHOT_SCHEMA_VERSION)
        categories = baseline.get("protected_categories")
        entry_count = baseline.get("protected_entry_count")
        if _is_safe_scope_event_audit(categories, entry_count):
            payload["protectedEntryCount"] = entry_count
            payload["protectedCategories"] = list(categories)

    payload["reasonCategory"] = (
        "scope_violation" if violation else "scope_evidence_unverifiable"
    )
    return payload


def _is_safe_scope_event_identifier(value: object) -> bool:
    if not isinstance(value, str) or not value or len(value) > 128:
        return False
    return all(character.isalnum() or character in "-_.:" for character in value)


def _is_safe_scope_event_audit(
    categories: object,
    entry_count: object,
) -> bool:
    return (
        isinstance(categories, list)
        and all(isinstance(category, str) for category in categories)
        and tuple(categories) == tuple(sorted(set(categories)))
        and set(categories).issubset(_SAFE_SCOPE_EVENT_CATEGORIES)
        and type(entry_count) is int
        and entry_count >= 0
    )


def _safe_scope_marker_reason(decision: ScopeDecision) -> Optional[str]:
    if decision.status == "rejected":
        return "The task run changed paths outside the assigned target."
    if decision.status == "unverifiable":
        return "The task run scope evidence is unavailable or invalid."
    return None


def _is_valid_scope_guard_marker(marker: object) -> bool:
    if not isinstance(marker, dict) or set(marker) != {
        "schemaVersion",
        "taskRunId",
        "targetId",
        "workspaceId",
        "scopePolicySchemaVersion",
        "scopePolicyIdentity",
        "baselineSchemaVersion",
        "baselineIdentity",
        "baselineCapturedAt",
        "executionAttemptId",
        "status",
        "changedPathCount",
        "timestamp",
    }:
        return False
    if (
        marker.get("schemaVersion") != SCOPE_VALIDATION_SCHEMA_VERSION
        or not isinstance(marker.get("taskRunId"), str)
        or not marker["taskRunId"]
        or marker.get("baselineSchemaVersion") != SCOPE_SNAPSHOT_SCHEMA_VERSION
        or not isinstance(marker.get("targetId"), str)
        or not marker["targetId"]
        or not isinstance(marker.get("workspaceId"), str)
        or not marker["workspaceId"]
        or marker.get("scopePolicySchemaVersion")
        != EFFECTIVE_WRITE_SCOPE_SCHEMA_VERSION
        or not _is_scope_policy_identity(marker.get("scopePolicyIdentity"))
        or not isinstance(marker.get("baselineIdentity"), str)
        or not marker["baselineIdentity"]
        or not isinstance(marker.get("executionAttemptId"), str)
        or not marker["executionAttemptId"]
        or marker.get("status") != "passed"
        or type(marker.get("changedPathCount")) is not int
        or marker["changedPathCount"] < 0
        or not _is_utc_scope_timestamp(marker.get("baselineCapturedAt"))
        or not _is_utc_scope_timestamp(marker.get("timestamp"))
    ):
        return False
    return _scope_timestamp_not_before(
        marker["timestamp"], marker["baselineCapturedAt"]
    )


def _scope_marker_matches_checkpoint(
    marker: dict[str, Any],
    task_run: TaskRun,
    checkpoint: object,
) -> bool:
    if marker["taskRunId"] != task_run.id or not isinstance(checkpoint, dict):
        return False
    baseline = checkpoint.get("scopeBaseline")
    return (
        marker["targetId"] == checkpoint.get("targetId")
        and marker["workspaceId"] == checkpoint.get("scopeWorkspaceId")
        and marker["scopePolicySchemaVersion"]
        == checkpoint.get("scopePolicySchemaVersion")
        and marker["scopePolicyIdentity"]
        == checkpoint.get("scopePolicyIdentity")
        and marker["taskRunId"] == checkpoint.get("scopeBaselineTaskRunId")
        and marker["baselineIdentity"] == checkpoint.get("scopeBaselineIdentity")
        and marker["baselineCapturedAt"]
        == checkpoint.get("scopeBaselineCapturedAt")
        and marker["executionAttemptId"]
        == checkpoint.get("scopeExecutionAttemptId")
        and isinstance(baseline, dict)
        and marker["baselineSchemaVersion"] == baseline.get("schema_version")
        and scope_snapshot_from_metadata(baseline).available
    )


def _scope_marker_matches_decision(
    marker: dict[str, Any],
    decision: object,
) -> bool:
    if not _is_valid_scope_decision_evidence(decision):
        return False
    return all(
        marker[key] == decision[key]
        for key in marker
    ) and decision["errorCode"] is None and decision["reason"] is None


def _scope_baseline_binding(task_run: TaskRun) -> Optional[dict[str, Any]]:
    checkpoint = _metrics(task_run).get("preRunCheckpoint")
    if not isinstance(checkpoint, dict):
        return None
    baseline = scope_snapshot_from_metadata(checkpoint.get("scopeBaseline"))
    task_run_id = checkpoint.get("scopeBaselineTaskRunId")
    target_id = checkpoint.get("targetId")
    baseline_identity = checkpoint.get("scopeBaselineIdentity")
    baseline_captured_at = checkpoint.get("scopeBaselineCapturedAt")
    execution_attempt_id = checkpoint.get("scopeExecutionAttemptId")
    workspace_id = checkpoint.get("scopeWorkspaceId")
    policy_schema_version = checkpoint.get("scopePolicySchemaVersion")
    policy_identity = checkpoint.get("scopePolicyIdentity")
    if (
        not baseline.available
        or task_run_id != task_run.id
        or not isinstance(target_id, str)
        or not target_id
        or not isinstance(baseline_identity, str)
        or not baseline_identity
        or not _is_utc_scope_timestamp(baseline_captured_at)
        or not isinstance(execution_attempt_id, str)
        or not execution_attempt_id
        or not isinstance(workspace_id, str)
        or not workspace_id
        or policy_schema_version != EFFECTIVE_WRITE_SCOPE_SCHEMA_VERSION
        or not _is_scope_policy_identity(policy_identity)
    ):
        return None
    return {
        "snapshot": baseline,
        "target_id": target_id,
        "baseline_identity": baseline_identity,
        "baseline_captured_at": baseline_captured_at,
        "execution_attempt_id": execution_attempt_id,
        "workspace_id": workspace_id,
        "policy_schema_version": policy_schema_version,
        "policy_identity": policy_identity,
    }


def _target_id_for_task_run(db: DbSession, task_run: TaskRun) -> str:
    task = db.get(Task, task_run.task_id)
    if task is None:
        return ""
    from app.scheduler import target_id_for_task

    target_id = target_id_for_task(task, db)
    return target_id if isinstance(target_id, str) else ""


def _workspace_target_for_task_run(
    db: DbSession,
    task_run: TaskRun,
) -> Optional[tuple[str, str, Any]]:
    task = db.get(Task, task_run.task_id)
    if task is None:
        return None
    session = db.get(AgentHubSession, task.session_id)
    if session is None:
        return None
    target_id = _target_id_for_task_run(db, task_run)
    if not target_id:
        return None
    try:
        target = get_target_for_workspace(db, session.workspace_id, target_id)
    except Exception:
        return None
    return session.workspace_id, target_id, target


def _scope_resolution_matches_binding(
    target_resolution: tuple[str, str, Any],
    binding: dict[str, Any],
) -> bool:
    workspace_id, target_id, target = target_resolution
    try:
        policy_identity = effective_write_scope_identity(target)
    except Exception:
        return False
    return (
        binding["workspace_id"] == workspace_id
        and binding["target_id"] == target_id
        and binding["policy_schema_version"]
        == EFFECTIVE_WRITE_SCOPE_SCHEMA_VERSION
        and binding["policy_identity"] == policy_identity
    )


def _scope_resolution_matches_evidence(
    target_resolution: tuple[str, str, Any],
    evidence: dict[str, Any],
) -> bool:
    workspace_id, target_id, target = target_resolution
    try:
        policy_identity = effective_write_scope_identity(target)
    except Exception:
        return False
    return (
        evidence["workspaceId"] == workspace_id
        and evidence["targetId"] == target_id
        and evidence["scopePolicySchemaVersion"]
        == EFFECTIVE_WRITE_SCOPE_SCHEMA_VERSION
        and evidence["scopePolicyIdentity"] == policy_identity
    )


def _task_run_holds_scope_target_lock(
    db: DbSession,
    task_run: TaskRun,
    target_id: str,
    *,
    lock_identity: Optional[str] = None,
) -> bool:
    task = db.get(Task, task_run.task_id)
    if task is None:
        return False
    from app.target_locks import held_lock_for_target

    held_lock = held_lock_for_target(db, target_id)
    current_identity = _scope_target_lock_identity(held_lock)
    return (
        held_lock is not None
        and held_lock.task_run_id == task_run.id
        and held_lock.session_id == task.session_id
        and isinstance(task_run.runner_id, str)
        and bool(task_run.runner_id)
        and held_lock.worker_id == task_run.runner_id
        and (lock_identity is None or current_identity == lock_identity)
    )


def _matching_target_lock_acquisition_context(
    task_run: TaskRun,
    task: Task,
    target_id: str,
    held_lock: Any,
) -> Optional[TargetLockAcquisitionContext]:
    acquisition_context = get_task_run_target_lock_acquisition_context(task_run.id)
    runner_id = task_run.runner_id
    if (
        acquisition_context is None
        or acquisition_context.task_run_id != task_run.id
        or acquisition_context.target_id != target_id
        or acquisition_context.session_id != task.session_id
        or not isinstance(runner_id, str)
        or not runner_id
        or acquisition_context.worker_id != runner_id
        or held_lock is None
        or held_lock.id != acquisition_context.lock_id
        or held_lock.task_run_id != task_run.id
        or held_lock.session_id != task.session_id
        or held_lock.worker_id != runner_id
    ):
        return None
    return acquisition_context


def _scope_target_lock_identity(lock: Any) -> Optional[str]:
    if (
        lock is None
        or not isinstance(lock.id, str)
        or not lock.id
    ):
        return None
    return lock.id


def _persistable_scope_decision(
    db: DbSession,
    task_run: TaskRun,
    decision: ScopeDecision,
    *,
    binding: Optional[dict[str, Any]],
) -> ScopeDecision:
    target_resolution = _workspace_target_for_task_run(db, task_run)
    target_id = target_resolution[1] if target_resolution is not None else ""
    if (
        decision.status not in {"passed", "rejected", "unverifiable"}
        or decision.target_id != target_id
    ):
        return _unverifiable_scope_decision(target_id)
    if decision.status in {"passed", "rejected"} and (
        binding is None
        or target_resolution is None
        or not _scope_resolution_matches_binding(target_resolution, binding)
    ):
        return _unverifiable_scope_decision(target_id)
    if decision.status == "passed":
        if (
            decision.error_code is not None
            or decision.reason is not None
            or decision.rejected_paths
        ):
            return _unverifiable_scope_decision(target_id)
        try:
            require_task_run_scope_runtime_context(
                task_run.id,
                workspace_id=binding["workspace_id"],
                target_id=binding["target_id"],
                policy_identity=binding["policy_identity"],
                baseline_identity=binding["baseline_identity"],
                baseline_captured_at=binding["baseline_captured_at"],
                execution_attempt_id=binding["execution_attempt_id"],
            )
        except TaskRunScopeError:
            return _unverifiable_scope_decision(target_id)
        return decision
    if (
        decision.status == "rejected"
        and decision.error_code == "TASK_RUN_SCOPE_VIOLATION"
    ):
        return decision
    if (
        decision.status == "unverifiable"
        and decision.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    ):
        return decision
    return _unverifiable_scope_decision(target_id)


def _unverifiable_scope_decision(target_id: str) -> ScopeDecision:
    return ScopeDecision(
        status="unverifiable",
        error_code="TASK_RUN_SCOPE_UNVERIFIABLE",
        target_id=target_id,
        changed_paths=(),
        rejected_paths=(),
        reason="The task run scope evidence is unavailable or invalid.",
    )


def _scope_unverifiable_error() -> TaskRunScopeError:
    return TaskRunScopeError(
        "TASK_RUN_SCOPE_UNVERIFIABLE",
        "The task run has no verifiable scope evidence.",
    )


def _raise_for_persisted_scope_failure(
    decision: object,
    *,
    task_run: TaskRun,
    checkpoint: object,
    target_resolution: Optional[tuple[str, str, Any]],
) -> None:
    if _is_valid_scope_decision_evidence(decision):
        if (
            decision["status"] == "rejected"
            and target_resolution is not None
            and _scope_resolution_matches_evidence(target_resolution, decision)
            and _scope_marker_matches_checkpoint(decision, task_run, checkpoint)
        ):
            raise TaskRunScopeError(
                "TASK_RUN_SCOPE_VIOLATION",
                "The task run changed paths outside the assigned target.",
            )
    raise _scope_unverifiable_error()


def _is_valid_scope_decision_evidence(decision: object) -> bool:
    if not isinstance(decision, dict) or set(decision) != {
        "schemaVersion",
        "taskRunId",
        "targetId",
        "workspaceId",
        "scopePolicySchemaVersion",
        "scopePolicyIdentity",
        "baselineSchemaVersion",
        "baselineIdentity",
        "baselineCapturedAt",
        "executionAttemptId",
        "status",
        "changedPathCount",
        "timestamp",
        "errorCode",
        "reason",
    }:
        return False
    if (
        decision.get("schemaVersion") != SCOPE_VALIDATION_SCHEMA_VERSION
        or not isinstance(decision.get("taskRunId"), str)
        or not decision["taskRunId"]
        or not isinstance(decision.get("targetId"), str)
        or not decision["targetId"]
        or not isinstance(decision.get("workspaceId"), str)
        or not decision["workspaceId"]
        or decision.get("scopePolicySchemaVersion")
        != EFFECTIVE_WRITE_SCOPE_SCHEMA_VERSION
        or not _is_scope_policy_identity(decision.get("scopePolicyIdentity"))
        or decision.get("baselineSchemaVersion")
        != SCOPE_SNAPSHOT_SCHEMA_VERSION
        or not isinstance(decision.get("baselineIdentity"), str)
        or not decision["baselineIdentity"]
        or not isinstance(decision.get("executionAttemptId"), str)
        or not decision["executionAttemptId"]
        or decision.get("status") not in {"passed", "rejected", "unverifiable"}
        or type(decision.get("changedPathCount")) is not int
        or decision["changedPathCount"] < 0
        or not _is_utc_scope_timestamp(decision.get("baselineCapturedAt"))
        or not _is_utc_scope_timestamp(decision.get("timestamp"))
        or not _scope_timestamp_not_before(
            decision["timestamp"], decision["baselineCapturedAt"]
        )
    ):
        return False
    if decision["status"] == "passed":
        return decision["errorCode"] is None and decision["reason"] is None
    expected_error = (
        "TASK_RUN_SCOPE_VIOLATION"
        if decision["status"] == "rejected"
        else "TASK_RUN_SCOPE_UNVERIFIABLE"
    )
    return (
        decision["errorCode"] == expected_error
        and isinstance(decision["reason"], str)
        and bool(decision["reason"])
    )


def _scope_timestamp_not_before(value: str, baseline_value: str) -> bool:
    try:
        return datetime.fromisoformat(value) >= datetime.fromisoformat(baseline_value)
    except (TypeError, ValueError):
        return False


def _utc_scope_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _unavailable_scope_baseline(reason: str) -> ScopeSnapshot:
    return ScopeSnapshot(
        schema_version=SCOPE_SNAPSHOT_SCHEMA_VERSION,
        available=False,
        reason=reason,
        entries=(),
        protected_control_digest=None,
    )


def _is_utc_scope_timestamp(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0)


def _is_scope_policy_identity(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _default_adapter_for_agent(agent: Agent) -> str:
    configured = os.environ.get(DEFAULT_CODE_ADAPTER_ENV, "").strip()
    if not configured:
        return agent.adapter_type

    if configured not in SUPPORTED_CODE_ADAPTERS:
        raise TaskRunLifecycleError(
            f"Unsupported {DEFAULT_CODE_ADAPTER_ENV}: {configured}"
        )

    if agent.adapter_type == "codex" and agent.role in CODE_AGENT_ROLES:
        return configured

    return agent.adapter_type


def _runtime_resolution_for_task(
    db: DbSession,
    task: Task,
    session: AgentHubSession,
    agent: Agent,
):
    role = _role_for_runtime_config(task, agent)
    return resolve_runtime_role_config(db, session.workspace_id, role)


def _role_for_runtime_config(task: Task, agent: Agent) -> str:
    plan = _plan_json(task)
    assigned_role = plan.get("assignedRole") or plan.get("assigned_role")
    if isinstance(assigned_role, str) and assigned_role:
        return "review" if assigned_role == "qa" else assigned_role
    if agent.role == "qa":
        return "review"
    return agent.role


def _retryable_run_or_raise(db: DbSession, task_run_id: str) -> TaskRun:
    previous = _task_run_or_raise(db, task_run_id)
    if previous.state not in RETRYABLE_STATES:
        raise TaskRunLifecycleError("Only failed or interrupted TaskRuns can be retried.")
    return previous


def _append_state_event(
    db: DbSession,
    task_run: TaskRun,
    state: str,
    payload: dict[str, Any],
) -> None:
    event_payload = dict(payload)
    event_payload["state"] = state
    append_task_run_event(
        db,
        task_run_id=task_run.id,
        event_type="task.state",
        payload_json=json.dumps(event_payload, separators=(",", ":")),
    )


def _new_runner_id() -> str:
    return f"local:{uuid4()}"


def _lease_expires_at(now: datetime, lease_seconds: int = DEFAULT_LEASE_SECONDS) -> datetime:
    return now + timedelta(seconds=lease_seconds)


def _touch_task_run_heartbeat(
    task_run: TaskRun,
    *,
    now: datetime,
    runner_id: Optional[str] = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> None:
    if runner_id is not None:
        task_run.runner_id = runner_id
    if task_run.runner_id is None:
        task_run.runner_id = _new_runner_id()
    task_run.last_heartbeat_at = now
    task_run.lease_expires_at = _lease_expires_at(now, lease_seconds)


def _task_status_for_run_state(state: str) -> str:
    if state == "waiting_approval":
        return "waiting_approval"
    if state == "completed":
        return "completed"
    if state == "failed":
        return "failed"
    if state == "interrupted":
        return "interrupted"
    return "running"


def _metrics(task_run: TaskRun) -> dict[str, Any]:
    try:
        value = json.loads(task_run.metrics_json)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _retry_metadata_for_previous_run(
    previous: TaskRun,
    *,
    retry_mode: str,
) -> dict[str, Any]:
    previous_metrics = _metrics(previous)
    checkpoint = previous_metrics.get("preRunCheckpoint")
    dirty_decision = _dirty_worktree_decision(previous, checkpoint)
    if dirty_decision["status"] == "unsafe":
        files = ", ".join(dirty_decision.get("unsafeFiles") or [])
        raise TaskRunLifecycleError(
            f"Unsafe retry blocked: dirty worktree contains files outside "
            f"the previous checkpoint or planned safe paths ({files})."
        )

    return {
        "previousRunId": previous.id,
        "failureSummary": {
            "state": previous.state,
            "errorCode": previous.error_code,
            "errorMessage": previous.error_message,
            "endedAt": previous.ended_at.isoformat()
            if previous.ended_at is not None
            else None,
        },
        "retryMode": retry_mode,
        "checkpointId": previous.id if isinstance(checkpoint, dict) else None,
        "dirtyWorktreeDecision": dirty_decision,
    }


def _dirty_worktree_decision(
    previous: TaskRun,
    checkpoint: Any,
) -> dict[str, Any]:
    if not isinstance(checkpoint, dict):
        return {
            "status": "safe",
            "reason": "No pre-run checkpoint was available for this legacy run.",
            "dirtyFiles": [],
            "unsafeFiles": [],
        }

    worktree_path = Path(previous.worktree_path)
    dirty_result = _git_dirty_files(worktree_path)
    if dirty_result.get("available") is not True:
        return {
            "status": "safe",
            "reason": dirty_result.get("reason") or "git_status_unavailable",
            "dirtyFiles": [],
            "unsafeFiles": [],
        }

    dirty_files = [
        path for path in dirty_result["dirtyFiles"] if isinstance(path, str)
    ]
    safe_files = {
        path
        for path in [
            *checkpoint.get("dirtyFiles", []),
            *checkpoint.get("plannedFiles", []),
        ]
        if isinstance(path, str) and path
    }
    unsafe_files = [
        path for path in dirty_files if path not in safe_files
    ]
    if unsafe_files:
        return {
            "status": "unsafe",
            "reason": "Dirty files are outside the previous checkpoint and planned safe paths.",
            "dirtyFiles": dirty_files,
            "unsafeFiles": unsafe_files,
        }
    return {
        "status": "safe",
        "reason": "Dirty files are limited to the previous checkpoint and planned safe paths.",
        "dirtyFiles": dirty_files,
        "unsafeFiles": [],
    }


def _platform_approval_payload(task: Task) -> Optional[dict[str, Any]]:
    plan = _plan_json(task)
    if (
        plan.get("targetId") == AGENTHUB_PLATFORM_TARGET_ID
        and plan.get("platformMode") is True
        and plan.get("requiresApproval") is True
    ):
        return {
            "approvalType": "security_approval",
            "reason": "AgentHub platform maintenance targets control-plane code and requires explicit approval.",
            "requestedAction": "execute platform maintenance task",
            "riskLevel": "high",
            "command": None,
            "path": plan.get("safeTarget") or "apps/api",
            "expiresAt": None,
        }
    return None


def _worktree_path_for_task(
    db: DbSession,
    task: Task,
    session: AgentHubSession,
) -> str:
    plan = _plan_json(task)
    target_id = plan.get("targetId")
    if not isinstance(target_id, str) or not target_id.startswith("external-"):
        return session.worktree_path
    try:
        target = get_target_for_workspace(db, session.workspace_id, target_id)
    except TargetRegistryError:
        return session.worktree_path
    return target.root


def _ensure_scheduler_allows_run_creation(db: DbSession, task: Task) -> None:
    from app.scheduler import (
        SCHEDULER_BLOCKED,
        SCHEDULER_WAITING_TARGET_LOCK,
        SCHEDULER_WAITING_DEPENDENCY,
        apply_scheduler_decision,
        evaluate_scheduler_readiness,
    )

    decision = evaluate_scheduler_readiness(db, task)
    if decision.state in {
        SCHEDULER_WAITING_DEPENDENCY,
        SCHEDULER_BLOCKED,
    }:
        apply_scheduler_decision(db, task, decision)
        raise TaskRunLifecycleError(decision.reason)
    if decision.state == SCHEDULER_WAITING_TARGET_LOCK:
        apply_scheduler_decision(db, task, decision)


def _enqueue_session_queue_entry(
    db: DbSession,
    task: Task,
    task_run: TaskRun,
    *,
    access_mode: str,
) -> None:
    from app.scheduler import target_id_for_task
    from app.session_queue import enqueue_task_run

    target_id = target_id_for_task(task, db)
    scheduler = _plan_json(task).get("scheduler")
    initial_queue_state = "queued"
    blocked_reason = None
    if isinstance(scheduler, dict) and scheduler.get("state") == "waiting_target_lock":
        initial_queue_state = "waiting_lock"
        blocked_reason = scheduler.get("reason")
    if task_run.state == "waiting_approval":
        blocked_reason = "Waiting for approval before queue claim."
    enqueue_task_run(
        db,
        task=task,
        task_run=task_run,
        access_mode=access_mode,
        target_id=target_id,
        initial_state=initial_queue_state,
        blocked_reason=blocked_reason,
    )


def _finalize_queue_and_lock_for_terminal_run(
    db: DbSession,
    task: Task,
    task_run: TaskRun,
    terminal_state: str,
) -> None:
    finalize_terminal_task_run(db, task, task_run, terminal_state)


def finalize_terminal_task_run(
    db: DbSession,
    task: Task,
    task_run: TaskRun,
    terminal_state: str,
) -> None:
    from app.session_queue import mark_task_run_terminal
    from app.target_locks import release_target_lock_for_task_run

    runtime_context = get_task_run_scope_runtime_context(task_run.id)
    acquisition_context = get_task_run_target_lock_acquisition_context(task_run.id)
    contexts_conflict = _terminal_scope_contexts_conflict(
        task,
        task_run,
        runtime_context,
        acquisition_context,
    )
    if acquisition_context is not None:
        expected_lock_id = acquisition_context.lock_id
        target_id = acquisition_context.target_id
        worker_id = acquisition_context.worker_id
        session_id = acquisition_context.session_id
    else:
        expected_lock_id = runtime_context.lock_id if runtime_context is not None else None
        target_id = runtime_context.target_id if runtime_context is not None else None
        worker_id = task_run.runner_id
        session_id = task.session_id
    release_confirmed = False
    try:
        if (
            isinstance(expected_lock_id, str)
            and expected_lock_id
            and isinstance(target_id, str)
            and target_id
            and isinstance(worker_id, str)
            and worker_id
        ):
            released_lock = release_target_lock_for_task_run(
                db,
                target_id=target_id,
                expected_lock_id=expected_lock_id,
                worker_id=worker_id,
                task_run_id=task_run.id,
                session_id=session_id,
                release_reason=f"task_run_{terminal_state}",
            )
            release_confirmed = released_lock is not None
        mark_task_run_terminal(
            db,
            task_run.id,
            terminal_state,
            reason=f"TaskRun finalized as {terminal_state}.",
        )
    finally:
        if release_confirmed and not contexts_conflict:
            if _task_run_has_durable_scope_decision(task_run):
                clear_task_run_scope_runtime_context(task_run.id)
            if acquisition_context is not None:
                clear_task_run_target_lock_acquisition_context(task_run.id)


def _terminal_scope_contexts_conflict(
    task: Task,
    task_run: TaskRun,
    runtime_context: Any,
    acquisition_context: Optional[TargetLockAcquisitionContext],
) -> bool:
    if acquisition_context is not None and (
        acquisition_context.task_run_id != task_run.id
        or acquisition_context.session_id != task.session_id
        or acquisition_context.worker_id != task_run.runner_id
    ):
        return True
    if runtime_context is not None and runtime_context.task_run_id != task_run.id:
        return True
    return bool(
        acquisition_context is not None
        and runtime_context is not None
        and (
            acquisition_context.target_id != runtime_context.target_id
            or acquisition_context.lock_id != runtime_context.lock_id
        )
    )


def _task_run_has_durable_scope_decision(task_run: TaskRun) -> bool:
    decision = _metrics(task_run).get("taskRunScopeDecision")
    return _public_scope_decision(task_run, decision) is not None


def _recover_terminal_target_locks_before_run_creation(db: DbSession) -> None:
    from app.target_locks import recover_terminal_holder_target_locks

    recover_terminal_holder_target_locks(db)


def _plan_json(task: Task) -> dict[str, Any]:
    try:
        value = json.loads(task.plan_json)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _pre_run_checkpoint_for_task(
    db: DbSession,
    task: Task,
    session: AgentHubSession,
    *,
    require_write_access: bool,
    worktree_path: str,
    base_ref: Optional[str],
    now: datetime,
) -> Optional[dict[str, Any]]:
    from app.scheduler import target_id_for_task

    if not require_write_access:
        return None

    target_id = target_id_for_task(task, db)
    if target_id is None:
        return None

    try:
        target = get_target_for_workspace(db, session.workspace_id, target_id)
    except TargetRegistryError:
        return None

    plan = _plan_json(task)
    planned_files = [
        path for path in plan.get("files", []) if isinstance(path, str) and path
    ]
    contract = plan.get("appContract")
    contract_id = plan.get("contractId")
    if not isinstance(contract_id, str) and isinstance(contract, dict):
        contract_id = contract.get("contractId")

    git_status = _git_status_checkpoint(
        Path(worktree_path),
        allowed_paths=list(target.allowed_paths),
        denied_paths=list(target.denied_paths),
    )
    checkpoint = {
        "targetId": target.target_id,
        "targetRoot": target.root,
        "allowedPaths": list(target.allowed_paths),
        "deniedPaths": list(target.denied_paths),
        "baseCommit": base_ref,
        "gitStatus": git_status,
        "dirtyFiles": git_status["dirtyFiles"],
        "plannedFiles": planned_files,
        "contractId": contract_id if isinstance(contract_id, str) else None,
        "contractHash": _contract_hash(contract),
        "createdAt": now.isoformat(),
    }
    if base_ref is None:
        checkpoint["fileSnapshot"] = capture_file_snapshot_for_worktree(
            worktree_path,
            allowed_paths=list(target.allowed_paths),
            denied_paths=list(target.denied_paths),
        )
    return checkpoint


def _effective_execution_access_mode(task: Task, adapter_type: str) -> str:
    from app.scheduler import write_lock_required_for_task
    from app.session_queue import READONLY_ACCESS_MODE, WRITE_ACCESS_MODE

    adapter_capabilities = CAPABILITIES_BY_ADAPTER.get(adapter_type)
    adapter_requires_write = adapter_capabilities is None or bool(
        {"file_edit", "shell_command"}.intersection(adapter_capabilities)
    )
    if write_lock_required_for_task(task) or adapter_requires_write:
        return WRITE_ACCESS_MODE
    return READONLY_ACCESS_MODE


def _git_status_checkpoint(
    worktree_path: Path,
    *,
    allowed_paths: list[str],
    denied_paths: list[str],
) -> dict[str, Any]:
    dirty_result = _git_dirty_files(worktree_path)
    if dirty_result.get("available") is not True:
        return dirty_result

    dirty_files = dirty_result["dirtyFiles"]
    scoped_dirty_files = [
        path
        for path in dirty_files
        if _matches_any_path(path, allowed_paths) and not _matches_any_path(path, denied_paths)
    ]
    return {
        "available": True,
        "dirtyFiles": scoped_dirty_files,
    }


def _git_dirty_files(worktree_path: Path) -> dict[str, Any]:
    if not worktree_path.exists():
        return {
            "available": False,
            "reason": "worktree_not_found",
            "dirtyFiles": [],
        }
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return {
            "available": False,
            "reason": str(exc),
            "dirtyFiles": [],
        }
    if result.returncode != 0:
        return {
            "available": False,
            "reason": result.stderr.strip() or result.stdout.strip() or "git_status_failed",
            "dirtyFiles": [],
        }
    return {
        "available": True,
        "dirtyFiles": _parse_porcelain_dirty_files(result.stdout),
    }


def _parse_porcelain_dirty_files(output: str) -> list[str]:
    files: list[str] = []
    for line in output.splitlines():
        if not line:
            continue
        path = line[3:] if len(line) > 3 else line
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip()
        if path:
            files.append(path)
    return files


def _contract_hash(contract: Any) -> Optional[str]:
    if not isinstance(contract, dict):
        return None
    normalized = json.dumps(contract, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _matches_any_path(path: str, patterns: list[str]) -> bool:
    normalized = _normalize_path(path)
    return any(_matches_path_pattern(normalized, pattern) for pattern in patterns)


def _matches_path_pattern(path: str, pattern: str) -> bool:
    normalized_pattern = _normalize_path(pattern)
    if not normalized_pattern:
        return False
    if normalized_pattern.endswith("*"):
        return path.startswith(normalized_pattern[:-1])
    if "/" not in normalized_pattern:
        return normalized_pattern in path.split("/")
    return path == normalized_pattern or path.startswith(f"{normalized_pattern}/")


def _normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.rstrip("/")


def _task_or_raise(db: DbSession, task_id: str) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise TaskRunLifecycleError(f"Task not found: {task_id}")
    return task


def _session_or_raise(db: DbSession, session_id: str) -> AgentHubSession:
    session = db.get(AgentHubSession, session_id)
    if session is None:
        raise TaskRunLifecycleError(f"Session not found: {session_id}")
    return session


def _agent_or_raise(db: DbSession, agent_id: Optional[str]) -> Agent:
    if agent_id is None:
        raise TaskRunLifecycleError("Task has no assigned agent.")
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise TaskRunLifecycleError(f"Agent not found: {agent_id}")
    return agent


def _task_run_or_raise(db: DbSession, task_run_id: str) -> TaskRun:
    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        raise TaskRunLifecycleError(f"TaskRun not found: {task_run_id}")
    return task_run
