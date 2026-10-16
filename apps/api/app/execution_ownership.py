"""Exact execution ownership and transactional lease renewal, independent of orchestration."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import update
from sqlmodel import Session as DbSession, select

from app.models import Session as AgentHubSession
from app.models import SessionQueueEntry, TargetLock, Task, TaskRun, utc_now
from app.scheduler import target_id_for_task, write_lock_required_for_task
from app.session_queue import entry_for_task_run, target_lock_key_for_target
from app.task_run_scope import TaskRunScopeError, get_task_run_target_lock_acquisition_context
from app.task_runs import ACTIVE_STATES, DEFAULT_LEASE_SECONDS, internal_metrics_for_run


@dataclass(frozen=True)
class _ExecutionLeaseToken:
    task_run_id: str
    task_id: str
    session_id: str
    workspace_id: str
    queue_entry_id: str
    runner_id: str
    access_mode: str
    task_write_lock_required: bool
    target_id: Optional[str]
    expected_lock_id: Optional[str] = field(repr=False)
    execution_attempt_id: str = field(repr=False)
    adapter_run_id: Optional[str] = field(default=None, repr=False)



@dataclass(frozen=True)
class _RecoveredTaskRunState:
    state: str
    error_code: Optional[str]
    error_message: Optional[str]
    updated_at: datetime
    ended_at: Optional[datetime]



@dataclass(frozen=True)
class _RequestLaunchSnapshot:
    task_run_id: str
    task_run_task_id: str
    task_run_agent_id: str
    task_run_runner_id: Optional[str]
    task_run_adapter_run_id: Optional[str]
    task_run_started_at: Optional[datetime]
    task_run_state: str
    task_run_worktree_path: str
    task_run_last_heartbeat_at: Optional[datetime]
    task_run_lease_expires_at: Optional[datetime]
    task_run_metrics_json: str
    task_run_updated_at: datetime
    queue_entry_id: str
    queue_session_id: str
    queue_task_id: str
    queue_task_run_id: str
    queue_access_mode: str
    queue_target_id: Optional[str]
    queue_target_lock_key: Optional[str]
    queue_state: str
    queue_started_at: datetime
    queue_finished_at: Optional[datetime]
    queue_updated_at: datetime
    task_session_id: str
    task_assigned_agent_id: Optional[str]
    task_intent_type: str
    task_plan_json: str
    task_updated_at: datetime
    task_target_id: Optional[str]
    external_target_registration_fingerprint: Optional[str]
    task_write_lock_required: bool
    session_id: str
    session_workspace_id: str
    session_worktree_path: str
    session_active_frontend_target_id: Optional[str]
    session_active_backend_target_id: Optional[str]
    session_updated_at: datetime



@dataclass(frozen=True)
class _PrepareFailureOwnershipSnapshot:
    task_run_id: str
    task_run_task_id: str
    task_run_agent_id: str
    task_run_runner_id: str
    task_run_adapter_run_id: Optional[str]
    task_run_started_at: Optional[datetime]
    task_run_ended_at: Optional[datetime]
    task_run_worktree_path: str
    task_run_last_heartbeat_at: Optional[datetime]
    task_run_lease_expires_at: datetime
    task_run_metrics_json: str
    task_run_updated_at: datetime
    queue_entry_id: str
    queue_session_id: str
    queue_task_id: str
    queue_task_run_id: str
    queue_access_mode: str
    queue_target_id: Optional[str]
    queue_target_lock_key: Optional[str]
    queue_state: str
    queue_started_at: datetime
    queue_finished_at: Optional[datetime]
    queue_updated_at: datetime
    expected_lock_id: Optional[str] = field(default=None, repr=False)



def renew_execution_lease(
    db: DbSession,
    token: _ExecutionLeaseToken,
    *,
    now: Optional[datetime] = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> bool:
    renewed_at = now or utc_now()
    if lease_seconds <= 0:
        return False
    db.rollback()
    try:
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        db.expire_all()
        task_run = db.exec(
            select(TaskRun)
            .where(TaskRun.id == token.task_run_id)
            .execution_options(populate_existing=True)
        ).first()
        if not _task_run_matches_execution_lease(task_run, token, renewed_at):
            db.rollback()
            return False
        assert task_run is not None
        task = db.exec(
            select(Task)
            .where(Task.id == token.task_id)
            .execution_options(populate_existing=True)
        ).first()
        session = db.exec(
            select(AgentHubSession)
            .where(AgentHubSession.id == token.session_id)
            .execution_options(populate_existing=True)
        ).first()
        if (
            task is None
            or task.session_id != token.session_id
            or target_id_for_task(task, db) != token.target_id
            or write_lock_required_for_task(task)
            != token.task_write_lock_required
            or not _session_matches_execution_lease(session, token)
        ):
            db.rollback()
            return False
        queue_entry = db.exec(
            select(SessionQueueEntry)
            .where(SessionQueueEntry.id == token.queue_entry_id)
            .execution_options(populate_existing=True)
        ).first()
        if not _queue_entry_matches_execution_lease(queue_entry, token):
            db.rollback()
            return False
        current_expiry = task_run.lease_expires_at
        assert current_expiry is not None
        original_metrics_json = task_run.metrics_json
        new_expiry = renewed_at + timedelta(seconds=lease_seconds)
        task_run_result = db.execute(
            update(TaskRun)
            .where(TaskRun.id == token.task_run_id)
            .where(TaskRun.task_id == token.task_id)
            .where(TaskRun.runner_id == token.runner_id)
            .where(TaskRun.state.in_(ACTIVE_STATES))
            .where(TaskRun.lease_expires_at == current_expiry)
            .where(TaskRun.metrics_json == original_metrics_json)
            .where(TaskRun.adapter_run_id == token.adapter_run_id)
            .values(
                last_heartbeat_at=renewed_at,
                lease_expires_at=new_expiry,
                updated_at=renewed_at,
            )
            .execution_options(synchronize_session=False)
        )
        if task_run_result.rowcount != 1:
            db.rollback()
            return False
        if token.access_mode == "write":
            current_lock = db.exec(
                select(TargetLock)
                .where(TargetLock.id == token.expected_lock_id)
                .execution_options(populate_existing=True)
            ).first()
            if not _target_lock_matches_execution_lease(
                current_lock,
                token,
                renewed_at,
            ):
                db.rollback()
                return False
            assert current_lock is not None
            current_lock_expiry = current_lock.lease_expires_at
            assert current_lock_expiry is not None
            lock_result = db.execute(
                update(TargetLock)
                .where(TargetLock.id == token.expected_lock_id)
                .where(TargetLock.target_id == token.target_id)
                .where(TargetLock.session_id == token.session_id)
                .where(TargetLock.task_run_id == token.task_run_id)
                .where(TargetLock.worker_id == token.runner_id)
                .where(TargetLock.mode == "write")
                .where(TargetLock.state == "held")
                .where(TargetLock.lease_expires_at == current_lock_expiry)
                .values(lease_expires_at=new_expiry, updated_at=renewed_at)
                .execution_options(synchronize_session=False)
            )
            if lock_result.rowcount != 1:
                db.rollback()
                return False
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise



def _task_run_matches_execution_lease(
    task_run: Optional[TaskRun],
    token: _ExecutionLeaseToken,
    now: datetime,
) -> bool:
    if (
        task_run is None
        or task_run.task_id != token.task_id
        or task_run.runner_id != token.runner_id
        or task_run.state not in ACTIVE_STATES
        or task_run.lease_expires_at is None
        or task_run.lease_expires_at <= now
    ):
        return False
    binding = internal_metrics_for_run(task_run).get("taskRunExecutionAccessBinding")
    return (
        isinstance(binding, dict)
        and binding.get("taskRunId") == token.task_run_id
        and binding.get("taskId") == token.task_id
        and binding.get("sessionId") == token.session_id
        and binding.get("queueEntryId") == token.queue_entry_id
        and binding.get("runnerId") == token.runner_id
        and binding.get("accessMode") == token.access_mode
        and binding.get("executionAttemptId") == token.execution_attempt_id
        and task_run.adapter_run_id == token.adapter_run_id
        and (
            (
                token.access_mode == "readonly"
                and token.expected_lock_id is None
            )
            or (
                token.access_mode == "write"
                and isinstance(token.target_id, str)
                and bool(token.target_id)
                and isinstance(token.expected_lock_id, str)
                and bool(token.expected_lock_id)
            )
        )
    )



def _queue_entry_matches_execution_lease(
    entry: Optional[SessionQueueEntry],
    token: _ExecutionLeaseToken,
) -> bool:
    if (
        entry is None
        or entry.id != token.queue_entry_id
        or entry.task_run_id != token.task_run_id
        or entry.task_id != token.task_id
        or entry.session_id != token.session_id
        or entry.access_mode != token.access_mode
        or entry.target_id != token.target_id
        or entry.state != "running"
        or entry.started_at is None
    ):
        return False
    if token.access_mode == "write":
        return entry.target_lock_key == target_lock_key_for_target(token.target_id)
    return token.access_mode == "readonly" and entry.target_lock_key is None



def _session_matches_execution_lease(
    session: Optional[AgentHubSession],
    token: _ExecutionLeaseToken,
) -> bool:
    return bool(
        session is not None
        and session.id == token.session_id
        and session.workspace_id == token.workspace_id
    )



def _target_lock_matches_execution_lease(
    lock: Optional[TargetLock],
    token: _ExecutionLeaseToken,
    now: datetime,
) -> bool:
    return bool(
        lock is not None
        and lock.id == token.expected_lock_id
        and lock.target_id == token.target_id
        and lock.session_id == token.session_id
        and lock.task_run_id == token.task_run_id
        and lock.worker_id == token.runner_id
        and lock.mode == "write"
        and lock.state == "held"
        and lock.lease_expires_at is not None
        and lock.lease_expires_at > now
    )



def execution_lease_token_for_task_run(
    db: DbSession,
    task_run_id: str,
    *,
    access_mode: str,
    execution_attempt_id: str,
    expected_session_id: str,
    now: Optional[datetime] = None,
) -> _ExecutionLeaseToken:
    now = now or utc_now()
    db.expire_all()
    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        raise _execution_lease_ownership_error()
    db.refresh(task_run)
    task = db.get(Task, task_run.task_id)
    session = db.get(AgentHubSession, task.session_id) if task is not None else None
    queue_entry = entry_for_task_run(db, task_run.id)
    binding = internal_metrics_for_run(task_run).get("taskRunExecutionAccessBinding")
    if (
        task is None
        or session is None
        or session.id != expected_session_id
        or queue_entry is None
        or not isinstance(task_run.runner_id, str)
        or not task_run.runner_id
        or not isinstance(binding, dict)
        or binding.get("taskRunId") != task_run.id
        or binding.get("taskId") != task.id
        or binding.get("sessionId") != task.session_id
        or binding.get("queueEntryId") != queue_entry.id
        or binding.get("runnerId") != task_run.runner_id
        or binding.get("accessMode") != access_mode
        or binding.get("executionAttemptId") != execution_attempt_id
        or queue_entry.task_run_id != task_run.id
        or queue_entry.task_id != task.id
        or queue_entry.session_id != task.session_id
        or queue_entry.access_mode != access_mode
    ):
        raise _execution_lease_ownership_error()
    target_id = queue_entry.target_id
    current_target_id = target_id_for_task(task, db)
    if target_id != current_target_id:
        raise _execution_lease_ownership_error()
    expected_lock_id: Optional[str] = None
    if access_mode == "write":
        context = get_task_run_target_lock_acquisition_context(task_run.id)
        if (
            context is None
            or current_target_id is None
            or target_id != current_target_id
            or context.task_run_id != task_run.id
            or context.target_id != target_id
            or context.session_id != task.session_id
            or context.worker_id != task_run.runner_id
        ):
            raise _execution_lease_ownership_error()
        expected_lock_id = context.lock_id
    elif access_mode != "readonly":
        raise _execution_lease_ownership_error()
    token = _ExecutionLeaseToken(
        task_run_id=task_run.id,
        task_id=task.id,
        session_id=task.session_id,
        workspace_id=session.workspace_id,
        queue_entry_id=queue_entry.id,
        runner_id=task_run.runner_id,
        access_mode=access_mode,
        task_write_lock_required=write_lock_required_for_task(task),
        target_id=target_id,
        expected_lock_id=expected_lock_id,
        execution_attempt_id=execution_attempt_id,
        adapter_run_id=task_run.adapter_run_id,
    )
    if not _task_run_matches_execution_lease(task_run, token, now):
        raise _execution_lease_ownership_error()
    if not _queue_entry_matches_execution_lease(queue_entry, token):
        raise _execution_lease_ownership_error()
    if access_mode == "write":
        durable_lock = db.exec(
            select(TargetLock)
            .where(TargetLock.id == token.expected_lock_id)
            .execution_options(populate_existing=True)
        ).first()
        if not _target_lock_matches_execution_lease(durable_lock, token, now):
            raise _execution_lease_ownership_error()
    return token



def _execution_lease_ownership_error() -> TaskRunScopeError:
    return TaskRunScopeError(
        "TASK_RUN_SCOPE_UNVERIFIABLE",
        "The task run execution lease ownership cannot be verified.",
    )
