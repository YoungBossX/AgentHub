import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from fastapi import BackgroundTasks
from sqlalchemy import event, exists, func, inspect as sa_inspect, update
from sqlmodel import Session as DbSession
from sqlmodel import select

from app.adapters import (
    _cancel_adapter_stream_after_interrupt_started,
    AdapterApproval,
    AdapterArtifact,
    AdapterCapabilities,
    AdapterRun,
    AgentAdapter,
    AgentRunRequest,
    RawAgentEvent,
    run_adapter_event_stream,
)
from app.claude_code_adapter import ClaudeCodeAdapter
from app.codex_adapter import CodexAdapter
from app.context_pack import build_session_context_pack
from app.deployments import DeployError, DeployService
from app.diffs import DiffCollectionError, collect_task_run_diff, record_diff_collection_failure
from app.events import append_task_run_event
from app.execution_worktrees import (
    ExecutionWorktreeError,
    requires_integration,
    validate_execution_worktree,
)
from app.instruction_builder import build_role_instruction
from app.ledger import refresh_session_ledger_for_task_run
from app.models import Agent, ExternalProjectTarget, SessionQueueEntry, TargetLock, Task, TaskRun
from app.models import Session as AgentHubSession
from app.models import utc_now
from app.previews import PreviewError, PreviewService
from app.provider_gateway import (
    CodingRunContext,
    ProviderConcurrencyLimiter,
    ProviderHealthProbe,
    ProviderResolver,
    record_provider_capacity_event,
    record_provider_health_check,
    record_provider_resolution,
)
from app.repositories import list_session_tasks
from app.reviews import (
    ReviewError,
    create_scripted_review_for_task_run,
    list_task_run_reviews,
    record_review_collection_failure,
)
from app.run_supervisor import (
    RunRegistrationRejected,
    RunSupervisor,
    SupervisedRun,
    default_run_supervisor,
)
from app.scheduler import SCHEDULER_WAITING_TARGET_LOCK, evaluate_and_apply_scheduler_readiness
from app.scheduler import target_id_for_task, write_lock_required_for_task
from app.session_queue import (
    entry_for_task_run,
    mark_task_run_running,
    mark_task_run_waiting_lock,
    queue_gate_for_task_run,
    target_lock_key_for_target,
)
from app.scripted_mock import ScriptedMockAdapter
from app.target_registry import effective_write_scope_identity, external_target_to_project
from app.target_locks import (
    acquire_target_lock,
    held_lock_for_target,
    release_target_lock_for_task_run,
)
from app.task_run_scope import (
    TaskRunScopeError,
    get_task_run_target_lock_acquisition_context,
    store_task_run_target_lock_acquisition_context,
)
from app.task_runs import (
    ACTIVE_STATES,
    DEFAULT_LEASE_SECONDS,
    TaskRunLifecycleError,
    adapter_type_for_run,
    capture_task_run_scope_baseline,
    claim_task_run_for_worker,
    create_task_run,
    list_task_runs,
    mark_stale_task_runs,
    internal_metrics_for_run,
    metrics_for_run,
    persist_scope_decision,
    persist_task_run_execution_access_binding,
    release_task_run_claim,
    refresh_task_run_heartbeat,
    require_task_run_artifact_scope_passed,
    require_task_run_execution_access_mode,
    require_task_run_scope_baseline,
    require_task_run_scope_passed,
    transition_task_run,
    validate_task_run_scope,
)

_preview_service = PreviewService()
_deploy_service = DeployService()
_provider_resolver = ProviderResolver()
_provider_health_probe = ProviderHealthProbe()
_provider_capacity_limiter = ProviderConcurrencyLimiter()
DEFAULT_RUN_WORKER_ID_PREFIX = "worker"
DEFAULT_DISPATCH_CONCURRENCY = 2
AUTO_PIPELINE_PLANNERS = {"contract_first_v1", "orchestrator_external_target_v1"}
EXECUTION_LEASE_RENEWAL_INTERVAL_SECONDS = DEFAULT_LEASE_SECONDS / 3


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


def _renew_execution_lease(
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


def _execution_lease_token_for_task_run(
    db: DbSession,
    task_run_id: str,
    *,
    access_mode: str,
    execution_attempt_id: str,
    expected_session_id: str,
) -> _ExecutionLeaseToken:
    now = utc_now()
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


class _RequestPersistenceOwnershipError(TaskRunScopeError):
    pass


def _request_persistence_ownership_error(
    exc: TaskRunScopeError,
) -> _RequestPersistenceOwnershipError:
    return _RequestPersistenceOwnershipError(exc.error_code, exc.message)


@dataclass
class _FinalizerCommitFence:
    token: _ExecutionLeaseToken
    authorized_terminal_state: Optional[str] = None
    pending_terminal_state: Optional[str] = None
    on_terminal_commit: Optional[Callable[[], bool]] = field(
        default=None,
        repr=False,
    )

    def after_commit(self, db: DbSession) -> None:
        if self.pending_terminal_state is None:
            return
        self.authorized_terminal_state = self.pending_terminal_state
        self.pending_terminal_state = None
        if self.on_terminal_commit is not None and not self.on_terminal_commit():
            raise _execution_lease_ownership_error()

    def after_rollback(self, db: DbSession) -> None:
        self.pending_terminal_state = None

    def before_commit(self, db: DbSession) -> None:
        try:
            self._before_commit(db)
        except TaskRunScopeError:
            raise
        except Exception as exc:
            raise _execution_lease_ownership_error() from exc

    def _before_commit(self, db: DbSession) -> None:
        connection = db.connection()
        task_run_row = self._task_run_row(connection)
        if task_run_row is None or not self._matches_task_run_identity(task_run_row):
            raise _execution_lease_ownership_error()

        if self.authorized_terminal_state is not None:
            if task_run_row["state"] != self.authorized_terminal_state:
                raise _execution_lease_ownership_error()
            pre_terminal = False
        else:
            pre_terminal = task_run_row["state"] == "collecting_diff"
            if not pre_terminal:
                raise _execution_lease_ownership_error()
        if not pre_terminal and (
            self._session_task_run_state(db) != self.authorized_terminal_state
        ):
            raise _execution_lease_ownership_error()

        task_run_update = (
            update(TaskRun)
            .where(TaskRun.id == self.token.task_run_id)
            .where(TaskRun.task_id == self.token.task_id)
            .where(TaskRun.runner_id == self.token.runner_id)
            .where(TaskRun.adapter_run_id == self.token.adapter_run_id)
            .where(TaskRun.state == task_run_row["state"])
            .where(TaskRun.metrics_json == task_run_row["metrics_json"])
        )
        if pre_terminal:
            task_run_update = task_run_update.where(
                func.julianday(TaskRun.lease_expires_at) > func.julianday("now")
            )
        task_run_cas = connection.execute(
            task_run_update.values(updated_at=TaskRun.updated_at)
        )
        if task_run_cas.rowcount != 1:
            raise _execution_lease_ownership_error()

        fenced_task_run_row = self._task_run_row(connection)
        if (
            fenced_task_run_row is None
            or not self._matches_task_run_identity(fenced_task_run_row)
            or fenced_task_run_row["state"] != task_run_row["state"]
            or fenced_task_run_row["metrics_json"] != task_run_row["metrics_json"]
            or (pre_terminal and not fenced_task_run_row["lease_is_current"])
        ):
            raise _execution_lease_ownership_error()

        task_row = connection.execute(
            select(
                Task.id,
                Task.session_id,
                Task.intent_type,
                Task.plan_json,
            ).where(Task.id == self.token.task_id)
        ).mappings().one_or_none()
        session_row = connection.execute(
            select(AgentHubSession.id, AgentHubSession.workspace_id).where(
                AgentHubSession.id == self.token.session_id
            )
        ).mappings().one_or_none()
        queue_row = connection.execute(
            select(
                SessionQueueEntry.id,
                SessionQueueEntry.task_run_id,
                SessionQueueEntry.task_id,
                SessionQueueEntry.session_id,
                SessionQueueEntry.access_mode,
                SessionQueueEntry.target_id,
                SessionQueueEntry.target_lock_key,
                SessionQueueEntry.state,
                SessionQueueEntry.started_at,
            ).where(SessionQueueEntry.id == self.token.queue_entry_id)
        ).mappings().one_or_none()
        if (
            task_row is None
            or task_row["id"] != self.token.task_id
            or task_row["session_id"] != self.token.session_id
            or not self._matches_task_execution_decision(db, task_row)
            or session_row is None
            or session_row["id"] != self.token.session_id
            or session_row["workspace_id"] != self.token.workspace_id
            or not self._matches_queue(queue_row, pre_terminal=pre_terminal)
        ):
            raise _execution_lease_ownership_error()

        if self.token.access_mode == "write":
            self._require_write_lock(connection, pre_terminal=pre_terminal)
        elif self.token.access_mode != "readonly":
            raise _execution_lease_ownership_error()

        if pre_terminal:
            self.pending_terminal_state = self._pending_terminal_transition(db)

    def _task_run_row(self, connection: Any) -> Any:
        return connection.execute(
            select(
                TaskRun.id,
                TaskRun.task_id,
                TaskRun.runner_id,
                TaskRun.adapter_run_id,
                TaskRun.state,
                TaskRun.lease_expires_at,
                TaskRun.metrics_json,
                (
                    func.julianday(TaskRun.lease_expires_at)
                    > func.julianday("now")
                ).label("lease_is_current"),
            ).where(TaskRun.id == self.token.task_run_id)
        ).mappings().one_or_none()

    def _matches_task_run_identity(self, row: Any) -> bool:
        if (
            row["id"] != self.token.task_run_id
            or row["task_id"] != self.token.task_id
            or row["runner_id"] != self.token.runner_id
            or row["adapter_run_id"] != self.token.adapter_run_id
        ):
            return False
        try:
            metrics = json.loads(row["metrics_json"])
        except (TypeError, json.JSONDecodeError):
            return False
        binding = metrics.get("taskRunExecutionAccessBinding")
        return bool(
            isinstance(binding, dict)
            and binding.get("taskRunId") == self.token.task_run_id
            and binding.get("taskId") == self.token.task_id
            and binding.get("sessionId") == self.token.session_id
            and binding.get("queueEntryId") == self.token.queue_entry_id
            and binding.get("runnerId") == self.token.runner_id
            and binding.get("accessMode") == self.token.access_mode
            and binding.get("executionAttemptId")
            == self.token.execution_attempt_id
        )

    def _matches_task_execution_decision(
        self,
        db: DbSession,
        row: Any,
    ) -> bool:
        durable_task = Task(
            id=row["id"],
            session_id=row["session_id"],
            title="",
            intent_type=row["intent_type"],
            plan_json=row["plan_json"],
        )
        return bool(
            target_id_for_task(durable_task, db) == self.token.target_id
            and write_lock_required_for_task(durable_task)
            == self.token.task_write_lock_required
        )

    def _matches_queue(self, row: Any, *, pre_terminal: bool) -> bool:
        if (
            row is None
            or row["id"] != self.token.queue_entry_id
            or row["task_run_id"] != self.token.task_run_id
            or row["task_id"] != self.token.task_id
            or row["session_id"] != self.token.session_id
            or row["access_mode"] != self.token.access_mode
            or row["target_id"] != self.token.target_id
            or row["started_at"] is None
        ):
            return False
        if pre_terminal:
            if row["state"] != "running":
                return False
        elif (
            self.authorized_terminal_state is None
            or row["state"]
            not in {"running", self.authorized_terminal_state}
        ):
            return False
        if self.token.access_mode == "write":
            return row["target_lock_key"] == target_lock_key_for_target(
                self.token.target_id
            )
        return self.token.access_mode == "readonly" and row["target_lock_key"] is None

    def _require_write_lock(
        self,
        connection: Any,
        *,
        pre_terminal: bool,
    ) -> None:
        exact_lock = connection.execute(
            select(
                TargetLock.id,
                TargetLock.target_id,
                TargetLock.session_id,
                TargetLock.task_run_id,
                TargetLock.worker_id,
                TargetLock.mode,
                TargetLock.state,
                TargetLock.lease_expires_at,
                (
                    func.julianday(TargetLock.lease_expires_at)
                    > func.julianday("now")
                ).label("lease_is_current"),
            ).where(TargetLock.id == self.token.expected_lock_id)
        ).mappings().one_or_none()
        if exact_lock is None or (
            exact_lock["id"] != self.token.expected_lock_id
            or exact_lock["target_id"] != self.token.target_id
            or exact_lock["session_id"] != self.token.session_id
            or exact_lock["task_run_id"] != self.token.task_run_id
            or exact_lock["mode"] != "write"
        ):
            raise _execution_lease_ownership_error()

        held_lock_id = connection.execute(
            select(TargetLock.id)
            .where(TargetLock.target_id == self.token.target_id)
            .where(TargetLock.state == "held")
        ).scalar_one_or_none()
        if exact_lock["state"] == "held":
            if (
                exact_lock["worker_id"] != self.token.runner_id
                or exact_lock["lease_expires_at"] is None
                or not exact_lock["lease_is_current"]
                or held_lock_id != self.token.expected_lock_id
            ):
                raise _execution_lease_ownership_error()
            return
        if (
            pre_terminal
            or exact_lock["state"] not in {"released", "stale_released"}
            or exact_lock["worker_id"] is not None
            or exact_lock["lease_expires_at"] is not None
            or held_lock_id is not None
        ):
            raise _execution_lease_ownership_error()

    def _session_task_run_state(self, db: DbSession) -> Optional[str]:
        for candidate in db.identity_map.values():
            if (
                isinstance(candidate, TaskRun)
                and candidate.id == self.token.task_run_id
            ):
                return candidate.state
        return None

    def _pending_terminal_transition(self, db: DbSession) -> Optional[str]:
        for candidate in db.identity_map.values():
            if not isinstance(candidate, TaskRun) or candidate.id != self.token.task_run_id:
                continue
            if candidate.state == "collecting_diff":
                return None
            if candidate.state not in {"completed", "failed"}:
                raise _execution_lease_ownership_error()
            candidate_state = sa_inspect(candidate)
            state_history = candidate_state.attrs.state.history
            if (
                not candidate_state.persistent
                or candidate not in db.dirty
                or tuple(state_history.added) != (candidate.state,)
                or tuple(state_history.deleted) != ("collecting_diff",)
                or not self._matches_task_run_identity(
                    {
                        "id": candidate.id,
                        "task_id": candidate.task_id,
                        "runner_id": candidate.runner_id,
                        "adapter_run_id": candidate.adapter_run_id,
                        "metrics_json": candidate.metrics_json,
                    }
                )
            ):
                raise _execution_lease_ownership_error()
            return candidate.state
        raise _execution_lease_ownership_error()


def _task_run_row_matches_execution_identity(
    task_run_row: Any,
    token: _ExecutionLeaseToken,
) -> bool:
    if (
        task_run_row is None
        or task_run_row["id"] != token.task_run_id
        or task_run_row["task_id"] != token.task_id
        or task_run_row["runner_id"] != token.runner_id
        or task_run_row["adapter_run_id"] != token.adapter_run_id
        or task_run_row["state"] != "collecting_diff"
    ):
        return False
    try:
        metrics = json.loads(task_run_row["metrics_json"])
    except (TypeError, json.JSONDecodeError):
        return False
    binding = metrics.get("taskRunExecutionAccessBinding")
    return bool(
        isinstance(binding, dict)
        and binding.get("taskRunId") == token.task_run_id
        and binding.get("taskId") == token.task_id
        and binding.get("sessionId") == token.session_id
        and binding.get("queueEntryId") == token.queue_entry_id
        and binding.get("runnerId") == token.runner_id
        and binding.get("accessMode") == token.access_mode
        and binding.get("executionAttemptId") == token.execution_attempt_id
    )


def _recover_finalizer_scope_error(
    db: DbSession,
    task_run_id: str,
    error: TaskRunScopeError,
    lease_controller: "_ExecutionLeaseController",
) -> tuple[bool, Optional[_RecoveredTaskRunState]]:
    bind = db.get_bind()
    try:
        db.rollback()
    except Exception:
        pass

    token = lease_controller._token
    if token is None or token.task_run_id != task_run_id:
        return False, None
    try:
        with DbSession(bind) as recovery_db:
            connection = recovery_db.connection()
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            recovery_db.expire_all()
            task_run_row = connection.execute(
                select(
                    TaskRun.id,
                    TaskRun.task_id,
                    TaskRun.runner_id,
                    TaskRun.adapter_run_id,
                    TaskRun.state,
                    TaskRun.lease_expires_at,
                    TaskRun.metrics_json,
                    TaskRun.error_code,
                    TaskRun.error_message,
                    TaskRun.updated_at,
                    TaskRun.ended_at,
                    (
                        func.julianday(TaskRun.lease_expires_at)
                        > func.julianday("now")
                    ).label("lease_is_current"),
                ).where(TaskRun.id == task_run_id)
            ).mappings().one_or_none()
            if task_run_row is None:
                recovery_db.rollback()
                return True, None
            if task_run_row["state"] not in ACTIVE_STATES:
                recovered_state = _RecoveredTaskRunState(
                    state=task_run_row["state"],
                    error_code=task_run_row["error_code"],
                    error_message=task_run_row["error_message"],
                    updated_at=task_run_row["updated_at"],
                    ended_at=task_run_row["ended_at"],
                )
                recovery_db.rollback()
                return True, recovered_state
            task = recovery_db.get(Task, token.task_id)
            session = recovery_db.get(AgentHubSession, token.session_id)
            queue_entry = recovery_db.get(SessionQueueEntry, token.queue_entry_id)
            exact_owner = bool(
                _task_run_row_matches_execution_identity(task_run_row, token)
                and task_run_row["lease_expires_at"] is not None
                and task_run_row["lease_is_current"]
                and task is not None
                and task.id == token.task_id
                and task.session_id == token.session_id
                and target_id_for_task(task, recovery_db) == token.target_id
                and write_lock_required_for_task(task)
                == token.task_write_lock_required
                and session is not None
                and session.id == token.session_id
                and session.workspace_id == token.workspace_id
                and _queue_entry_matches_execution_lease(queue_entry, token)
            )
            if token.access_mode == "write":
                acquisition = get_task_run_target_lock_acquisition_context(
                    task_run_id
                )
                durable_lock_row = connection.execute(
                    select(
                        TargetLock.id,
                        TargetLock.target_id,
                        TargetLock.session_id,
                        TargetLock.task_run_id,
                        TargetLock.worker_id,
                        TargetLock.mode,
                        TargetLock.state,
                        TargetLock.lease_expires_at,
                        (
                            func.julianday(TargetLock.lease_expires_at)
                            > func.julianday("now")
                        ).label("lease_is_current"),
                    ).where(TargetLock.id == token.expected_lock_id)
                ).mappings().one_or_none()
                exact_owner = bool(
                    exact_owner
                    and acquisition is not None
                    and acquisition.task_run_id == token.task_run_id
                    and acquisition.target_id == token.target_id
                    and acquisition.session_id == token.session_id
                    and acquisition.worker_id == token.runner_id
                    and acquisition.lock_id == token.expected_lock_id
                    and durable_lock_row is not None
                    and durable_lock_row["id"] == token.expected_lock_id
                    and durable_lock_row["target_id"] == token.target_id
                    and durable_lock_row["session_id"] == token.session_id
                    and durable_lock_row["task_run_id"] == token.task_run_id
                    and durable_lock_row["worker_id"] == token.runner_id
                    and durable_lock_row["mode"] == "write"
                    and durable_lock_row["state"] == "held"
                    and durable_lock_row["lease_expires_at"] is not None
                    and durable_lock_row["lease_is_current"]
                )
            if not exact_owner:
                recovery_db.rollback()
                return True, None
            recovered = transition_task_run(
                recovery_db,
                task_run_id,
                "failed",
                error_code=error.error_code,
                error_message=error.message,
            )
            return True, _RecoveredTaskRunState(
                state=recovered.state,
                error_code=recovered.error_code,
                error_message=recovered.error_message,
                updated_at=recovered.updated_at,
                ended_at=recovered.ended_at,
            )
    except Exception:
        return False, None


class _ExecutionLeaseController:
    def __init__(
        self,
        bind: Any,
        *,
        interval_seconds: Optional[float] = None,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
    ) -> None:
        self._bind = bind
        self._interval_seconds = (
            EXECUTION_LEASE_RENEWAL_INTERVAL_SECONDS
            if interval_seconds is None
            else interval_seconds
        )
        self._lease_seconds = lease_seconds
        self._stop = asyncio.Event()
        self._ownership_lost = asyncio.Event()
        self._task: Optional[asyncio.Task[None]] = None
        self._token: Optional[_ExecutionLeaseToken] = None

    def start(self, token: _ExecutionLeaseToken) -> None:
        if self._task is not None or self._interval_seconds <= 0:
            raise _execution_lease_ownership_error()
        self._token = token
        try:
            with DbSession(self._bind) as ownership_db:
                if not self.owns_current_execution(ownership_db):
                    raise _execution_lease_ownership_error()
        except Exception:
            self._token = None
            raise
        self._task = asyncio.create_task(self._run())

    def bind_adapter_run(self, adapter_run_id: str) -> None:
        if not isinstance(adapter_run_id, str) or not adapter_run_id:
            raise _execution_lease_ownership_error()
        token = self._token
        if token is None or (
            token.adapter_run_id is not None
            and token.adapter_run_id != adapter_run_id
        ):
            raise _execution_lease_ownership_error()
        bound_token = replace(token, adapter_run_id=adapter_run_id)
        with DbSession(self._bind) as ownership_db:
            if not self._token_owns_current_execution(ownership_db, bound_token):
                raise _execution_lease_ownership_error()
        self._token = bound_token

    def owns_current_execution(self, db: DbSession) -> bool:
        token = self._token
        if token is None:
            return False
        return self._token_owns_current_execution(db, token)

    def _token_owns_current_execution(
        self,
        db: DbSession,
        token: _ExecutionLeaseToken,
    ) -> bool:
        now = utc_now()
        db.expire_all()
        task_run = db.get(TaskRun, token.task_run_id)
        if not _task_run_matches_execution_lease(task_run, token, now):
            return False
        task = db.get(Task, token.task_id)
        if (
            task is None
            or task.session_id != token.session_id
            or target_id_for_task(task, db) != token.target_id
            or write_lock_required_for_task(task)
            != token.task_write_lock_required
        ):
            return False
        session = db.get(AgentHubSession, token.session_id)
        if not _session_matches_execution_lease(session, token):
            return False
        queue_entry = db.get(SessionQueueEntry, token.queue_entry_id)
        if not _queue_entry_matches_execution_lease(queue_entry, token):
            return False
        if token.access_mode == "readonly":
            return True
        lock = db.get(TargetLock, token.expected_lock_id)
        return _target_lock_matches_execution_lease(lock, token, now)

    async def wait_until_ownership_lost(self) -> None:
        await self._ownership_lost.wait()

    async def stop(self) -> None:
        self._stop.set()
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass

    async def _run(self) -> None:
        try:
            while True:
                try:
                    await asyncio.wait_for(
                        self._stop.wait(),
                        timeout=self._interval_seconds,
                    )
                    return
                except asyncio.TimeoutError:
                    pass
                token = self._token
                if token is None:
                    self._ownership_lost.set()
                    return
                with DbSession(self._bind) as lease_db:
                    renewed = _renew_execution_lease(
                        lease_db,
                        token,
                        lease_seconds=self._lease_seconds,
                    )
                if not renewed:
                    self._ownership_lost.set()
                    return
        except asyncio.CancelledError:
            raise
        except Exception:
            self._ownership_lost.set()


def get_preview_service() -> PreviewService:
    return _preview_service


def get_deploy_service() -> DeployService:
    return _deploy_service


def schedule_task_run_execution(
    background_tasks: BackgroundTasks,
) -> None:
    background_tasks.add_task(_background_dispatch_queued_task_runs)


@dataclass(frozen=True)
class DispatchClaim:
    task_run_id: str
    adapter_type: str
    worker_id: str


DispatchExecutor = Callable[[Any, DispatchClaim], Awaitable[bool]]


class BoundedRunDispatcher:
    def __init__(
        self,
        *,
        dispatcher_id: Optional[str] = None,
        max_concurrency: int = DEFAULT_DISPATCH_CONCURRENCY,
        executor: Optional[DispatchExecutor] = None,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("Dispatcher concurrency must be at least one.")
        self.dispatcher_id = dispatcher_id or f"dispatcher:{uuid4()}"
        self.max_concurrency = max_concurrency
        self._executor = executor or _execute_dispatch_claim

    async def run_once(
        self,
        db: DbSession,
        *,
        recover_stale: bool = True,
        excluded_task_run_ids: Optional[set[str]] = None,
    ) -> list[str]:
        if recover_stale:
            RunWorker(worker_id=self.dispatcher_id).recover_stale_runs(db)
        _advance_ready_integrations(db)
        claims = self._claim_ready_task_runs(
            db,
            excluded_task_run_ids=excluded_task_run_ids or set(),
        )
        if not claims:
            return []
        results = await asyncio.gather(
            *(self._executor(db.get_bind(), claim) for claim in claims),
            return_exceptions=True,
        )
        for claim, result in zip(claims, results):
            if result is True:
                continue
            with DbSession(db.get_bind()) as release_db:
                release_task_run_claim(
                    release_db,
                    claim.task_run_id,
                    worker_id=claim.worker_id,
                    reason=(
                        "Dispatcher execution gate did not start the TaskRun."
                        if result is False
                        else "Dispatcher executor raised before the TaskRun started."
                    ),
                )
        db.expire_all()
        return [claim.task_run_id for claim in claims]

    async def run_until_idle(self, db: DbSession) -> list[str]:
        RunWorker(worker_id=self.dispatcher_id).recover_stale_runs(db)
        dispatched: list[str] = []
        while True:
            batch = await self.run_once(
                db,
                recover_stale=False,
                excluded_task_run_ids=set(dispatched),
            )
            if not batch:
                return dispatched
            dispatched.extend(batch)

    def _claim_ready_task_runs(
        self,
        db: DbSession,
        *,
        excluded_task_run_ids: set[str],
    ) -> list[DispatchClaim]:
        claims: list[DispatchClaim] = []
        db.expire_all()
        for task_run in queued_task_runs(db):
            if task_run.id in excluded_task_run_ids:
                continue
            if len(claims) >= self.max_concurrency:
                break
            task = db.get(Task, task_run.task_id)
            if task is None:
                continue
            decision = evaluate_and_apply_scheduler_readiness(db, task)
            if not decision.runnable:
                continue
            queue_decision = queue_gate_for_task_run(db, task_run.id)
            if not queue_decision.runnable:
                continue
            worker_id = f"{self.dispatcher_id}:slot:{len(claims) + 1}"
            try:
                claimed = claim_task_run_for_worker(
                    db,
                    task_run.id,
                    worker_id=worker_id,
                )
            except TaskRunLifecycleError:
                db.rollback()
                db.expire_all()
                continue
            claims.append(
                DispatchClaim(
                    task_run_id=claimed.id,
                    adapter_type=adapter_type_for_run(db, claimed),
                    worker_id=worker_id,
                )
            )
        return claims


class RunWorker:
    def __init__(self, *, worker_id: Optional[str] = None) -> None:
        self.worker_id = worker_id or _new_worker_id()

    async def run_once(self, db: DbSession) -> Optional[TaskRun]:
        self.recover_stale_runs(db)
        for task_run in queued_task_runs(db):
            adapter_type = adapter_type_for_run(db, task_run)
            executed = await execute_task_run_background(
                db,
                task_run.id,
                adapter_type,
                worker_id=self.worker_id,
            )
            if executed:
                return db.get(TaskRun, task_run.id)
        return None

    def recover_stale_runs(self, db: DbSession, *, reason: str = "worker_startup") -> dict[str, Any]:
        from app.session_queue import recover_queue_entries
        from app.target_locks import recover_stale_target_locks

        recovered_locks = recover_stale_target_locks(db)
        marked = mark_stale_task_runs(
            db,
            reason=reason,
            exclude_target_lock_holders=True,
        )
        recovered_entries = recover_queue_entries(db)
        return {
            "workerId": self.worker_id,
            "reason": reason,
            "staleRunIds": [run.id for run in marked],
            "staleRunCount": len(marked),
            "recoveredQueueEntryIds": [entry.id for entry in recovered_entries],
            "recoveredLockKeys": [lock.lock_key for lock in recovered_locks],
        }


def next_queued_task_run(db: DbSession) -> Optional[TaskRun]:
    return queued_task_runs(db)[0] if queued_task_runs(db) else None


def queued_task_runs(db: DbSession) -> list[TaskRun]:
    return db.exec(
        select(TaskRun)
        .where(TaskRun.state == "queued")
        .order_by(TaskRun.created_at, TaskRun.id)
    ).all()


def agent_run_request_for(
    db: DbSession,
    task_run: TaskRun,
    *,
    adapter_type: str,
    plan_context: Optional[dict[str, Any]] = None,
    fence_current_execution: bool = False,
    _launch_snapshot_out: Optional[list[_RequestLaunchSnapshot]] = None,
) -> AgentRunRequest:
    task = db.get(Task, task_run.task_id)
    if task is None:
        raise TaskRunLifecycleError(f"Task not found: {task_run.task_id}")
    session = db.get(AgentHubSession, task.session_id)
    if session is None:
        raise TaskRunLifecycleError(f"Session not found: {task.session_id}")
    agent = db.get(Agent, task_run.agent_id)
    if agent is None:
        raise TaskRunLifecycleError(f"Agent not found: {task_run.agent_id}")
    launch_snapshot = (
        _capture_request_launch_snapshot(db, task_run, task, session)
        if fence_current_execution
        else None
    )
    task_plan = plan_json_for_task(task)
    merged_plan_context = dict(task_plan)
    if plan_context:
        merged_plan_context.update(plan_context)
    context_pack = build_session_context_pack(
        db,
        task,
        plan_context=merged_plan_context,
    )
    merged_plan_context["sessionContext"] = context_pack
    request = AgentRunRequest(
        taskRunId=task_run.id,
        sessionId=session.id,
        workspaceId=session.workspace_id,
        worktreePath=task_run.worktree_path,
        agentId=task_run.agent_id,
        adapterType=adapter_type,
        instruction=build_role_instruction(
            task,
            agent,
            context_pack,
            adapter_type=adapter_type,
        ),
        planContext=merged_plan_context,
        permissionProfile={"network": "off"},
        demoMode=True,
        fallbackPolicy="scripted_mock" if adapter_type == "scripted_mock" else "none",
    )
    persisted_launch_snapshot = _persist_context_snapshot(
        db,
        task_run,
        context_pack,
        fence_current_execution=fence_current_execution,
        launch_snapshot=launch_snapshot,
    )
    if _launch_snapshot_out is not None:
        if persisted_launch_snapshot is None:
            raise _execution_lease_ownership_error()
        _launch_snapshot_out.append(persisted_launch_snapshot)
    return request


def _capture_request_launch_snapshot(
    db: DbSession,
    task_run: TaskRun,
    task: Task,
    session: AgentHubSession,
) -> _RequestLaunchSnapshot:
    queue_entry = entry_for_task_run(db, task_run.id)
    task_target_id = target_id_for_task(task, db)
    expected_worktree_path = _expected_task_run_worktree_path(
        db,
        task,
        session,
        task_target_id,
        task_run,
    )
    external_target_registration_fingerprint = (
        _external_target_registration_fingerprint_for(
            db,
            session.workspace_id,
            task_target_id,
        )
    )
    task_write_lock_required = write_lock_required_for_task(task)
    expected_access_mode = require_task_run_execution_access_mode(
        db,
        task_run,
        require_started=False,
    )
    expected_target_lock_key = (
        target_lock_key_for_target(task_target_id)
        if expected_access_mode == "write" and task_target_id is not None
        else None
    )
    if (
        task_run.state != "queued"
        or task_run.task_id != task.id
        or task_run.agent_id != task.assigned_agent_id
        or expected_worktree_path is None
        or task_run.worktree_path != expected_worktree_path
        or task_run.started_at is not None
        or task.session_id != session.id
        or queue_entry is None
        or queue_entry.task_run_id != task_run.id
        or queue_entry.task_id != task.id
        or queue_entry.session_id != session.id
        or queue_entry.access_mode != expected_access_mode
        or queue_entry.target_id != task_target_id
        or queue_entry.target_lock_key != expected_target_lock_key
        or queue_entry.state != "running"
        or queue_entry.started_at is None
        or queue_entry.finished_at is not None
    ):
        raise _execution_lease_ownership_error()
    return _RequestLaunchSnapshot(
        task_run_id=task_run.id,
        task_run_task_id=task_run.task_id,
        task_run_agent_id=task_run.agent_id,
        task_run_runner_id=task_run.runner_id,
        task_run_adapter_run_id=task_run.adapter_run_id,
        task_run_started_at=task_run.started_at,
        task_run_state=task_run.state,
        task_run_worktree_path=task_run.worktree_path,
        task_run_last_heartbeat_at=task_run.last_heartbeat_at,
        task_run_lease_expires_at=task_run.lease_expires_at,
        task_run_metrics_json=task_run.metrics_json,
        task_run_updated_at=task_run.updated_at,
        queue_entry_id=queue_entry.id,
        queue_session_id=queue_entry.session_id,
        queue_task_id=queue_entry.task_id,
        queue_task_run_id=queue_entry.task_run_id,
        queue_access_mode=queue_entry.access_mode,
        queue_target_id=queue_entry.target_id,
        queue_target_lock_key=queue_entry.target_lock_key,
        queue_state=queue_entry.state,
        queue_started_at=queue_entry.started_at,
        queue_finished_at=queue_entry.finished_at,
        queue_updated_at=queue_entry.updated_at,
        task_session_id=task.session_id,
        task_assigned_agent_id=task.assigned_agent_id,
        task_intent_type=task.intent_type,
        task_plan_json=task.plan_json,
        task_updated_at=task.updated_at,
        task_target_id=task_target_id,
        external_target_registration_fingerprint=(
            external_target_registration_fingerprint
        ),
        task_write_lock_required=task_write_lock_required,
        session_id=session.id,
        session_workspace_id=session.workspace_id,
        session_worktree_path=session.worktree_path,
        session_active_frontend_target_id=session.active_frontend_target_id,
        session_active_backend_target_id=session.active_backend_target_id,
        session_updated_at=session.updated_at,
    )


_EXTERNAL_TARGET_REGISTRATION_FIELDS = tuple(ExternalProjectTarget.model_fields)


def _expected_task_run_worktree_path(
    db: DbSession,
    task: Task,
    session: AgentHubSession,
    task_target_id: Optional[str],
    task_run: Optional[TaskRun] = None,
) -> Optional[str]:
    if task_run is not None and requires_integration(task_run):
        try:
            return validate_execution_worktree(db, task_run)["worktreePath"]
        except ExecutionWorktreeError:
            return None
    if not task_target_id or not task_target_id.startswith("external-"):
        return session.worktree_path
    target = db.exec(
        select(ExternalProjectTarget).where(
            ExternalProjectTarget.workspace_id == session.workspace_id,
            ExternalProjectTarget.target_id == task_target_id,
        )
    ).first()
    if target is None:
        return None
    return target.root_path


def _external_target_registration_fingerprint_for(
    db: DbSession,
    workspace_id: str,
    target_id: Optional[str],
    *,
    fresh: bool = False,
) -> Optional[str]:
    if target_id is None:
        return None
    if fresh:
        columns = tuple(
            getattr(ExternalProjectTarget, field_name)
            for field_name in _EXTERNAL_TARGET_REGISTRATION_FIELDS
        )
        row = db.connection().execute(
            select(*columns).where(
                ExternalProjectTarget.workspace_id == workspace_id,
                ExternalProjectTarget.target_id == target_id,
            )
        ).mappings().one_or_none()
        target = (
            ExternalProjectTarget.model_validate(dict(row))
            if row is not None
            else None
        )
    else:
        target = db.exec(
            select(ExternalProjectTarget).where(
                ExternalProjectTarget.workspace_id == workspace_id,
                ExternalProjectTarget.target_id == target_id,
            )
        ).first()
    if target is None:
        return None
    payload = target.model_dump(mode="json")
    payload["effectiveWriteScopeIdentity"] = effective_write_scope_identity(
        external_target_to_project(target)
    )
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _persist_context_snapshot(
    db: DbSession,
    task_run: TaskRun,
    context_pack: dict[str, Any],
    *,
    fence_current_execution: bool = False,
    launch_snapshot: Optional[_RequestLaunchSnapshot] = None,
) -> Optional[_RequestLaunchSnapshot]:
    canonical_context = context_pack.get("canonicalContext")
    if not isinstance(canonical_context, dict):
        if fence_current_execution:
            raise _execution_lease_ownership_error()
        return
    if fence_current_execution and (
        launch_snapshot is None
        or launch_snapshot.task_run_id != task_run.id
        or launch_snapshot.task_run_state != "queued"
    ):
        raise _execution_lease_ownership_error()
    metrics = internal_metrics_for_run(task_run)
    metrics["canonicalContextSnapshot"] = canonical_context
    metrics_json = json.dumps(metrics, separators=(",", ":"))
    updated_at = utc_now()
    persisted_launch_snapshot: Optional[_RequestLaunchSnapshot] = None
    expire_on_commit = getattr(db, "expire_on_commit", True)
    db.expire_on_commit = False
    try:
        if fence_current_execution:
            assert launch_snapshot is not None
            current_queue = select(SessionQueueEntry.id).where(
                SessionQueueEntry.id == launch_snapshot.queue_entry_id,
                SessionQueueEntry.task_run_id
                == launch_snapshot.queue_task_run_id,
                SessionQueueEntry.task_id == launch_snapshot.queue_task_id,
                SessionQueueEntry.session_id == launch_snapshot.queue_session_id,
                SessionQueueEntry.access_mode == launch_snapshot.queue_access_mode,
                SessionQueueEntry.target_id == launch_snapshot.queue_target_id,
                SessionQueueEntry.target_lock_key
                == launch_snapshot.queue_target_lock_key,
                SessionQueueEntry.state == launch_snapshot.queue_state,
                SessionQueueEntry.started_at == launch_snapshot.queue_started_at,
                SessionQueueEntry.finished_at == launch_snapshot.queue_finished_at,
                SessionQueueEntry.updated_at == launch_snapshot.queue_updated_at,
            )
            current_task = select(Task.id).where(
                Task.id == launch_snapshot.task_run_task_id,
                Task.session_id == launch_snapshot.task_session_id,
                Task.assigned_agent_id == launch_snapshot.task_assigned_agent_id,
                Task.intent_type == launch_snapshot.task_intent_type,
                Task.plan_json == launch_snapshot.task_plan_json,
                Task.updated_at == launch_snapshot.task_updated_at,
            )
            current_session = select(AgentHubSession.id).where(
                AgentHubSession.id == launch_snapshot.session_id,
                AgentHubSession.workspace_id
                == launch_snapshot.session_workspace_id,
                AgentHubSession.worktree_path
                == launch_snapshot.session_worktree_path,
                AgentHubSession.active_frontend_target_id
                == launch_snapshot.session_active_frontend_target_id,
                AgentHubSession.active_backend_target_id
                == launch_snapshot.session_active_backend_target_id,
                AgentHubSession.updated_at == launch_snapshot.session_updated_at,
            )
            result = db.execute(
                update(TaskRun)
                .where(TaskRun.id == launch_snapshot.task_run_id)
                .where(TaskRun.task_id == launch_snapshot.task_run_task_id)
                .where(TaskRun.agent_id == launch_snapshot.task_run_agent_id)
                .where(TaskRun.runner_id == launch_snapshot.task_run_runner_id)
                .where(
                    TaskRun.adapter_run_id
                    == launch_snapshot.task_run_adapter_run_id
                )
                .where(TaskRun.started_at == launch_snapshot.task_run_started_at)
                .where(TaskRun.state == "queued")
                .where(
                    TaskRun.worktree_path
                    == launch_snapshot.task_run_worktree_path
                )
                .where(
                    TaskRun.last_heartbeat_at
                    == launch_snapshot.task_run_last_heartbeat_at
                )
                .where(
                    TaskRun.lease_expires_at
                    == launch_snapshot.task_run_lease_expires_at
                )
                .where(TaskRun.metrics_json == launch_snapshot.task_run_metrics_json)
                .where(TaskRun.updated_at == launch_snapshot.task_run_updated_at)
                .where(
                    func.julianday(TaskRun.lease_expires_at)
                    > func.julianday("now")
                )
                .where(exists(current_queue))
                .where(exists(current_task))
                .where(exists(current_session))
                .values(metrics_json=metrics_json, updated_at=updated_at)
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                db.rollback()
                raise _execution_lease_ownership_error()
            if not _request_launch_snapshot_matches(
                db,
                launch_snapshot,
                expected_metrics_json=metrics_json,
                expected_updated_at=updated_at,
            ):
                db.rollback()
                raise _execution_lease_ownership_error()
            persisted_launch_snapshot = replace(
                launch_snapshot,
                task_run_metrics_json=metrics_json,
                task_run_updated_at=updated_at,
            )
        else:
            task_run.metrics_json = metrics_json
            task_run.updated_at = updated_at
            db.add(task_run)
        db.commit()
        db.refresh(task_run)
    except TaskRunScopeError as exc:
        db.rollback()
        raise _request_persistence_ownership_error(exc) from exc
    except Exception as exc:
        db.rollback()
        raise _request_persistence_ownership_error(
            _execution_lease_ownership_error()
        ) from exc
    finally:
        db.expire_on_commit = expire_on_commit
    return persisted_launch_snapshot


def _request_launch_snapshot_matches(
    db: DbSession,
    snapshot: _RequestLaunchSnapshot,
    *,
    expected_metrics_json: str,
    expected_updated_at: datetime,
) -> bool:
    connection = db.connection()
    task_run_row = connection.execute(
        select(
            TaskRun.id,
            TaskRun.task_id,
            TaskRun.agent_id,
            TaskRun.runner_id,
            TaskRun.adapter_run_id,
            TaskRun.started_at,
            TaskRun.state,
            TaskRun.worktree_path,
            TaskRun.last_heartbeat_at,
            TaskRun.lease_expires_at,
            TaskRun.metrics_json,
            TaskRun.updated_at,
            (
                func.julianday(TaskRun.lease_expires_at)
                > func.julianday("now")
            ).label("lease_is_current"),
        ).where(TaskRun.id == snapshot.task_run_id)
    ).mappings().one_or_none()
    queue_row = connection.execute(
        select(
            SessionQueueEntry.id,
            SessionQueueEntry.task_run_id,
            SessionQueueEntry.task_id,
            SessionQueueEntry.session_id,
            SessionQueueEntry.access_mode,
            SessionQueueEntry.target_id,
            SessionQueueEntry.target_lock_key,
            SessionQueueEntry.state,
            SessionQueueEntry.started_at,
            SessionQueueEntry.finished_at,
            SessionQueueEntry.updated_at,
        ).where(SessionQueueEntry.id == snapshot.queue_entry_id)
    ).mappings().one_or_none()
    task_row = connection.execute(
        select(
            Task.id,
            Task.session_id,
            Task.assigned_agent_id,
            Task.intent_type,
            Task.plan_json,
            Task.updated_at,
        ).where(Task.id == snapshot.task_run_task_id)
    ).mappings().one_or_none()
    session_row = connection.execute(
        select(
            AgentHubSession.id,
            AgentHubSession.workspace_id,
            AgentHubSession.worktree_path,
            AgentHubSession.active_frontend_target_id,
            AgentHubSession.active_backend_target_id,
            AgentHubSession.updated_at,
        ).where(AgentHubSession.id == snapshot.session_id)
    ).mappings().one_or_none()
    if (
        task_run_row is None
        or task_run_row["id"] != snapshot.task_run_id
        or task_run_row["task_id"] != snapshot.task_run_task_id
        or task_run_row["agent_id"] != snapshot.task_run_agent_id
        or task_run_row["runner_id"] != snapshot.task_run_runner_id
        or task_run_row["adapter_run_id"] != snapshot.task_run_adapter_run_id
        or snapshot.task_run_started_at is not None
        or task_run_row["started_at"] != snapshot.task_run_started_at
        or snapshot.task_run_state != "queued"
        or task_run_row["state"] != "queued"
        or task_run_row["worktree_path"] != snapshot.task_run_worktree_path
        or task_run_row["last_heartbeat_at"]
        != snapshot.task_run_last_heartbeat_at
        or task_run_row["lease_expires_at"]
        != snapshot.task_run_lease_expires_at
        or task_run_row["metrics_json"] != expected_metrics_json
        or task_run_row["updated_at"] != expected_updated_at
        or not task_run_row["lease_is_current"]
        or queue_row is None
        or queue_row["id"] != snapshot.queue_entry_id
        or queue_row["task_run_id"] != snapshot.queue_task_run_id
        or queue_row["task_id"] != snapshot.queue_task_id
        or queue_row["session_id"] != snapshot.queue_session_id
        or queue_row["access_mode"] != snapshot.queue_access_mode
        or queue_row["target_id"] != snapshot.queue_target_id
        or queue_row["target_lock_key"] != snapshot.queue_target_lock_key
        or queue_row["state"] != snapshot.queue_state
        or queue_row["started_at"] != snapshot.queue_started_at
        or queue_row["finished_at"] != snapshot.queue_finished_at
        or queue_row["updated_at"] != snapshot.queue_updated_at
        or task_row is None
        or task_row["session_id"] != snapshot.task_session_id
        or task_row["assigned_agent_id"] != snapshot.task_assigned_agent_id
        or task_row["intent_type"] != snapshot.task_intent_type
        or task_row["plan_json"] != snapshot.task_plan_json
        or task_row["updated_at"] != snapshot.task_updated_at
        or session_row is None
        or session_row["id"] != snapshot.session_id
        or session_row["workspace_id"] != snapshot.session_workspace_id
        or session_row["worktree_path"] != snapshot.session_worktree_path
        or session_row["active_frontend_target_id"]
        != snapshot.session_active_frontend_target_id
        or session_row["active_backend_target_id"]
        != snapshot.session_active_backend_target_id
        or session_row["updated_at"] != snapshot.session_updated_at
    ):
        return False
    durable_task = Task(
        id=task_row["id"],
        session_id=task_row["session_id"],
        title="",
        assigned_agent_id=task_row["assigned_agent_id"],
        intent_type=task_row["intent_type"],
        plan_json=task_row["plan_json"],
        updated_at=task_row["updated_at"],
    )
    current_external_target_fingerprint = (
        _external_target_registration_fingerprint_for(
            db,
            snapshot.session_workspace_id,
            snapshot.task_target_id,
            fresh=True,
        )
    )
    return bool(
        target_id_for_task(durable_task, db) == snapshot.task_target_id
        and current_external_target_fingerprint
        == snapshot.external_target_registration_fingerprint
        and write_lock_required_for_task(durable_task)
        == snapshot.task_write_lock_required
    )


def plan_json_for_task(task: Task) -> dict[str, Any]:
    try:
        plan = json.loads(task.plan_json)
    except json.JSONDecodeError:
        return {}
    return plan if isinstance(plan, dict) else {}


def adapter_for_type(
    adapter_type: str,
    *,
    codex_adapter: AgentAdapter,
    claude_code_adapter: AgentAdapter,
    scripted_mock_adapter: AgentAdapter,
) -> AgentAdapter:
    if adapter_type == "codex":
        return codex_adapter
    if adapter_type == "claude_code":
        return claude_code_adapter
    if adapter_type == "scripted_mock":
        return scripted_mock_adapter
    raise TaskRunLifecycleError(f"Unsupported adapter type: {adapter_type}")


def _require_request_launch_snapshot_current(
    db: DbSession,
    snapshot: _RequestLaunchSnapshot,
) -> None:
    try:
        db.rollback()
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        db.expire_all()
        if not _request_launch_snapshot_matches(
            db,
            snapshot,
            expected_metrics_json=snapshot.task_run_metrics_json,
            expected_updated_at=snapshot.task_run_updated_at,
        ):
            raise _execution_lease_ownership_error()
    except TaskRunScopeError:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise _execution_lease_ownership_error() from exc


def _post_binding_launch_snapshot(
    snapshot: _RequestLaunchSnapshot,
    bound_task_run: TaskRun,
) -> _RequestLaunchSnapshot:
    bound_values = bound_task_run.__dict__
    metrics_json = bound_values.get("metrics_json")
    updated_at = bound_values.get("updated_at")
    if (
        bound_task_run.id != snapshot.task_run_id
        or not isinstance(metrics_json, str)
        or not isinstance(updated_at, datetime)
    ):
        raise _execution_lease_ownership_error()
    return replace(
        snapshot,
        task_run_metrics_json=metrics_json,
        task_run_updated_at=updated_at,
    )


def _final_launch_token_matches(
    db: DbSession,
    snapshot: _RequestLaunchSnapshot,
    token: _ExecutionLeaseToken,
) -> bool:
    if (
        token.task_run_id != snapshot.task_run_id
        or token.task_id != snapshot.task_run_task_id
        or token.session_id != snapshot.session_id
        or token.workspace_id != snapshot.session_workspace_id
        or token.queue_entry_id != snapshot.queue_entry_id
        or token.runner_id != snapshot.task_run_runner_id
        or token.access_mode != snapshot.queue_access_mode
        or token.task_write_lock_required != snapshot.task_write_lock_required
        or token.target_id != snapshot.task_target_id
    ):
        return False
    if token.access_mode == "readonly":
        return token.expected_lock_id is None
    if token.access_mode != "write" or token.expected_lock_id is None:
        return False
    acquisition = get_task_run_target_lock_acquisition_context(token.task_run_id)
    if (
        acquisition is None
        or acquisition.task_run_id != token.task_run_id
        or acquisition.target_id != token.target_id
        or acquisition.session_id != token.session_id
        or acquisition.worker_id != token.runner_id
        or acquisition.lock_id != token.expected_lock_id
    ):
        return False
    lock_row = db.connection().execute(
        select(
            TargetLock.id,
            TargetLock.target_id,
            TargetLock.session_id,
            TargetLock.task_run_id,
            TargetLock.worker_id,
            TargetLock.mode,
            TargetLock.state,
            TargetLock.lease_expires_at,
            (
                func.julianday(TargetLock.lease_expires_at)
                > func.julianday("now")
            ).label("lease_is_current"),
        ).where(TargetLock.id == token.expected_lock_id)
    ).mappings().one_or_none()
    return bool(
        lock_row is not None
        and lock_row["id"] == token.expected_lock_id
        and lock_row["target_id"] == token.target_id
        and lock_row["session_id"] == token.session_id
        and lock_row["task_run_id"] == token.task_run_id
        and lock_row["worker_id"] == token.runner_id
        and lock_row["mode"] == "write"
        and lock_row["state"] == "held"
        and lock_row["lease_expires_at"] is not None
        and lock_row["lease_is_current"]
    )


async def _launch_adapter_at_final_execution_boundary(
    db: DbSession,
    adapter: AgentAdapter,
    request: AgentRunRequest,
    snapshot: _RequestLaunchSnapshot,
    token: _ExecutionLeaseToken,
    *,
    supervisor_ownership_guard: Callable[[], bool],
) -> AdapterRun:
    boundary_verified = False
    try:
        db.rollback()
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        db.expire_all()
        if (
            not _request_launch_snapshot_matches(
                db,
                snapshot,
                expected_metrics_json=snapshot.task_run_metrics_json,
                expected_updated_at=snapshot.task_run_updated_at,
            )
            or not _final_launch_token_matches(db, snapshot, token)
            or not supervisor_ownership_guard()
        ):
            raise _execution_lease_ownership_error()
        boundary_verified = True
        return await adapter.createRun(request)
    except BaseException as exc:
        db.rollback()
        if boundary_verified or isinstance(exc, TaskRunScopeError):
            raise
        raise _execution_lease_ownership_error() from exc
    finally:
        db.rollback()


class _ExecutionAccessBindingAdapter(AgentAdapter):
    def __init__(
        self,
        db: DbSession,
        task_run_id: str,
        adapter: AgentAdapter,
        launch_reservation: Callable[
            [Callable[[], Awaitable[AdapterRun]]],
            Awaitable[tuple[bool, Optional[AdapterRun]]],
        ],
        expected_capabilities: Optional[AdapterCapabilities] = None,
        expected_launch_snapshot: Optional[_RequestLaunchSnapshot] = None,
        on_execution_bound: Optional[Callable[[_ExecutionLeaseToken], None]] = None,
        supervisor_ownership_guard: Optional[Callable[[], bool]] = None,
    ) -> None:
        self._db = db
        self._task_run_id = task_run_id
        self._adapter = adapter
        self._expected_capabilities = expected_capabilities
        self._expected_launch_snapshot = expected_launch_snapshot
        self._on_execution_bound = on_execution_bound
        self._launch_reservation = launch_reservation
        self._supervisor_ownership_guard = supervisor_ownership_guard

    def getCapabilities(self) -> AdapterCapabilities:
        if self._expected_capabilities is not None:
            return self._expected_capabilities
        return _adapter_capabilities_for_execution(self._adapter)

    async def createRun(self, request: AgentRunRequest) -> AdapterRun:
        async def bind_and_launch() -> AdapterRun:
            try:
                if self._expected_launch_snapshot is not None:
                    _require_request_launch_snapshot_current(
                        self._db,
                        self._expected_launch_snapshot,
                    )
                task_run = self._db.get(TaskRun, self._task_run_id)
                if task_run is None:
                    raise TaskRunScopeError(
                        "TASK_RUN_SCOPE_UNVERIFIABLE",
                        "The task run execution access binding cannot be verified.",
                    )
                access_mode = require_task_run_execution_access_mode(
                    self._db,
                    task_run,
                    require_started=False,
                )
                if access_mode == "write":
                    execution_attempt_id = _claim_scope_execution_attempt(
                        self._db,
                        self._task_run_id,
                    )
                    capture_task_run_scope_baseline(
                        self._db,
                        self._task_run_id,
                        execution_attempt_id=execution_attempt_id,
                    )
                    require_task_run_scope_baseline(self._db, self._task_run_id)
                else:
                    execution_attempt_id = str(uuid4())
                capabilities = _adapter_capabilities_for_execution(self._adapter)
                if (
                    self._expected_capabilities is not None
                    and capabilities != self._expected_capabilities
                ) or (
                    access_mode == "readonly"
                    and (
                        capabilities.supports_file_edit
                        or capabilities.supports_shell_command
                    )
                ):
                    raise _execution_access_capabilities_error()
                bound_task_run = persist_task_run_execution_access_binding(
                    self._db,
                    self._task_run_id,
                    access_mode=access_mode,
                    execution_attempt_id=execution_attempt_id,
                )
                if self._expected_launch_snapshot is None:
                    raise _execution_lease_ownership_error()
                final_launch_snapshot = _post_binding_launch_snapshot(
                    self._expected_launch_snapshot,
                    bound_task_run,
                )
                token = _execution_lease_token_for_task_run(
                    self._db,
                    self._task_run_id,
                    access_mode=access_mode,
                    execution_attempt_id=execution_attempt_id,
                    expected_session_id=request.session_id,
                )
                if self._on_execution_bound is not None:
                    self._on_execution_bound(token)
            except TaskRunScopeError:
                raise
            except Exception as exc:
                self._db.rollback()
                raise TaskRunScopeError(
                    "TASK_RUN_SCOPE_UNVERIFIABLE",
                    "The task run has no verifiable scope evidence.",
                ) from exc
            if self._supervisor_ownership_guard is None:
                raise _execution_lease_ownership_error()
            return await _launch_adapter_at_final_execution_boundary(
                self._db,
                self._adapter,
                request,
                final_launch_snapshot,
                token,
                supervisor_ownership_guard=self._supervisor_ownership_guard,
            )

        current, run = await self._launch_reservation(bind_and_launch)
        if not current or run is None:
            self._db.rollback()
            raise _execution_lease_ownership_error()
        return run

    def streamEvents(self, run_id: str) -> AsyncIterator[RawAgentEvent]:
        return self._adapter.streamEvents(run_id)

    async def interrupt(self, run_id: str) -> None:
        await self._adapter.interrupt(run_id)

    async def approve(self, run_id: str, approval: AdapterApproval) -> None:
        await self._adapter.approve(run_id, approval)

    async def collectArtifacts(self, run_id: str) -> list[AdapterArtifact]:
        return await self._adapter.collectArtifacts(run_id)

    async def cleanup(self, run_id: str) -> None:
        await self._adapter.cleanup(run_id)


def _execution_access_capabilities_error() -> TaskRunScopeError:
    return TaskRunScopeError(
        "TASK_RUN_SCOPE_UNVERIFIABLE",
        "The task run execution access binding cannot be verified.",
    )


def _adapter_capabilities_for_execution(
    adapter: AgentAdapter,
) -> AdapterCapabilities:
    try:
        capabilities = adapter.getCapabilities()
        if not isinstance(capabilities, AdapterCapabilities):
            raise TypeError("Adapter capabilities have an invalid type.")
        capability_data = capabilities.model_dump(mode="python")
        return AdapterCapabilities.model_validate(capability_data, strict=True)
    except Exception as exc:
        raise _execution_access_capabilities_error() from exc


def _claim_scope_execution_attempt(
    db: DbSession,
    task_run_id: str,
) -> str:
    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        raise TaskRunScopeError(
            "TASK_RUN_SCOPE_UNVERIFIABLE",
            "The task run has no verifiable scope evidence.",
        )
    db.refresh(task_run)
    if task_run.state != "queued":
        raise TaskRunScopeError(
            "TASK_RUN_SCOPE_UNVERIFIABLE",
            "The task run has no verifiable scope evidence.",
        )
    _scope_baseline_required_for_run(db, task_run)

    metrics = internal_metrics_for_run(task_run)
    checkpoint = metrics.get("preRunCheckpoint")
    checkpoint = dict(checkpoint) if isinstance(checkpoint, dict) else {}
    if "scopeExecutionAttemptId" in checkpoint or "scopeBaseline" in checkpoint:
        raise TaskRunScopeError(
            "TASK_RUN_SCOPE_UNVERIFIABLE",
            "The task run has no verifiable scope evidence.",
        )

    original_metrics_json = task_run.metrics_json
    execution_attempt_id = str(uuid4())
    checkpoint["scopeExecutionAttemptId"] = execution_attempt_id
    metrics["preRunCheckpoint"] = checkpoint
    now = utc_now()
    try:
        result = db.execute(
            update(TaskRun)
            .where(TaskRun.id == task_run.id)
            .where(TaskRun.state == task_run.state)
            .where(TaskRun.runner_id == task_run.runner_id)
            .where(TaskRun.metrics_json == original_metrics_json)
            .values(
                metrics_json=json.dumps(metrics, separators=(",", ":")),
                updated_at=now,
            )
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise TaskRunScopeError(
            "TASK_RUN_SCOPE_UNVERIFIABLE",
            "The task run has no verifiable scope evidence.",
        ) from exc
    db.refresh(task_run)
    if result.rowcount != 1:
        raise TaskRunScopeError(
            "TASK_RUN_SCOPE_UNVERIFIABLE",
            "The task run has no verifiable scope evidence.",
        )
    return execution_attempt_id


def _persist_active_task_run_scope_failure(
    db: DbSession,
    task_run_id: str,
    exc: TaskRunScopeError,
    ownership: Optional[_PrepareFailureOwnershipSnapshot],
) -> Optional[TaskRun]:
    if ownership is None or ownership.task_run_id != task_run_id:
        db.rollback()
        return None
    db.rollback()
    try:
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        db.expire_all()
        current_task_run = db.exec(
            select(TaskRun)
            .where(TaskRun.id == task_run_id)
            .execution_options(populate_existing=True)
        ).first()
        current_queue_entry = db.exec(
            select(SessionQueueEntry)
            .where(SessionQueueEntry.id == ownership.queue_entry_id)
            .execution_options(populate_existing=True)
        ).first()
        lease_is_current = db.connection().execute(
            select(
                func.julianday(TaskRun.lease_expires_at)
                > func.julianday("now")
            ).where(TaskRun.id == task_run_id)
        ).scalar_one_or_none()
        write_lock_is_current = _prepare_failure_write_lock_is_current(
            db,
            ownership,
        )
    except Exception:
        db.rollback()
        return None
    if not _prepare_failure_ownership_matches(
        current_task_run,
        current_queue_entry,
        ownership,
        lease_is_current=lease_is_current is True,
        write_lock_is_current=write_lock_is_current,
    ):
        db.rollback()
        return None
    return transition_task_run(
        db,
        task_run_id,
        "failed",
        error_code=exc.error_code,
        error_message=exc.message,
    )


def _freeze_prepare_failure_ownership(
    task_run: TaskRun,
    queue_entry: SessionQueueEntry,
) -> _PrepareFailureOwnershipSnapshot:
    if (
        task_run.state != "queued"
        or not isinstance(task_run.runner_id, str)
        or not task_run.runner_id
        or task_run.adapter_run_id is not None
        or task_run.started_at is not None
        or task_run.ended_at is not None
        or task_run.lease_expires_at is None
        or queue_entry.task_run_id != task_run.id
        or queue_entry.task_id != task_run.task_id
        or queue_entry.state != "running"
        or queue_entry.started_at is None
        or queue_entry.finished_at is not None
    ):
        raise _execution_lease_ownership_error()
    expected_lock_id: Optional[str] = None
    if queue_entry.access_mode == "write":
        acquisition = get_task_run_target_lock_acquisition_context(task_run.id)
        if (
            acquisition is None
            or acquisition.task_run_id != task_run.id
            or acquisition.target_id != queue_entry.target_id
            or acquisition.session_id != queue_entry.session_id
            or acquisition.worker_id != task_run.runner_id
            or not isinstance(acquisition.lock_id, str)
            or not acquisition.lock_id
            or not isinstance(queue_entry.target_id, str)
            or not queue_entry.target_id
            or not isinstance(queue_entry.target_lock_key, str)
            or not queue_entry.target_lock_key
        ):
            raise _execution_lease_ownership_error()
        expected_lock_id = acquisition.lock_id
    elif queue_entry.access_mode != "readonly":
        raise _execution_lease_ownership_error()
    return _PrepareFailureOwnershipSnapshot(
        task_run_id=task_run.id,
        task_run_task_id=task_run.task_id,
        task_run_agent_id=task_run.agent_id,
        task_run_runner_id=task_run.runner_id,
        task_run_adapter_run_id=task_run.adapter_run_id,
        task_run_started_at=task_run.started_at,
        task_run_ended_at=task_run.ended_at,
        task_run_worktree_path=task_run.worktree_path,
        task_run_last_heartbeat_at=task_run.last_heartbeat_at,
        task_run_lease_expires_at=task_run.lease_expires_at,
        task_run_metrics_json=task_run.metrics_json,
        task_run_updated_at=task_run.updated_at,
        queue_entry_id=queue_entry.id,
        queue_session_id=queue_entry.session_id,
        queue_task_id=queue_entry.task_id,
        queue_task_run_id=queue_entry.task_run_id,
        queue_access_mode=queue_entry.access_mode,
        queue_target_id=queue_entry.target_id,
        queue_target_lock_key=queue_entry.target_lock_key,
        queue_state=queue_entry.state,
        queue_started_at=queue_entry.started_at,
        queue_finished_at=queue_entry.finished_at,
        queue_updated_at=queue_entry.updated_at,
        expected_lock_id=expected_lock_id,
    )


def _prepare_failure_write_lock_is_current(
    db: DbSession,
    ownership: _PrepareFailureOwnershipSnapshot,
) -> bool:
    if ownership.queue_access_mode == "readonly":
        return ownership.expected_lock_id is None
    if (
        ownership.queue_access_mode != "write"
        or ownership.expected_lock_id is None
        or ownership.queue_target_id is None
        or ownership.queue_target_lock_key is None
    ):
        return False
    acquisition = get_task_run_target_lock_acquisition_context(
        ownership.task_run_id
    )
    if (
        acquisition is None
        or acquisition.task_run_id != ownership.task_run_id
        or acquisition.target_id != ownership.queue_target_id
        or acquisition.session_id != ownership.queue_session_id
        or acquisition.worker_id != ownership.task_run_runner_id
        or acquisition.lock_id != ownership.expected_lock_id
    ):
        return False
    connection = db.connection()
    lock_row = connection.execute(
        select(
            TargetLock.id,
            TargetLock.lock_key,
            TargetLock.target_id,
            TargetLock.session_id,
            TargetLock.task_run_id,
            TargetLock.worker_id,
            TargetLock.mode,
            TargetLock.state,
            (
                func.julianday(TargetLock.lease_expires_at)
                > func.julianday("now")
            ).label("lease_is_current"),
        ).where(TargetLock.id == ownership.expected_lock_id)
    ).mappings().one_or_none()
    held_generation_ids = connection.execute(
        select(TargetLock.id).where(
            TargetLock.target_id == ownership.queue_target_id,
            TargetLock.state == "held",
        )
    ).scalars().all()
    return bool(
        lock_row is not None
        and lock_row["id"] == ownership.expected_lock_id
        and lock_row["lock_key"] == ownership.queue_target_lock_key
        and lock_row["target_id"] == ownership.queue_target_id
        and lock_row["session_id"] == ownership.queue_session_id
        and lock_row["task_run_id"] == ownership.task_run_id
        and lock_row["worker_id"] == ownership.task_run_runner_id
        and lock_row["mode"] == "write"
        and lock_row["state"] == "held"
        and lock_row["lease_is_current"]
        and held_generation_ids == [ownership.expected_lock_id]
    )


def _prepare_failure_ownership_matches(
    task_run: Optional[TaskRun],
    queue_entry: Optional[SessionQueueEntry],
    ownership: _PrepareFailureOwnershipSnapshot,
    *,
    lease_is_current: bool,
    write_lock_is_current: bool,
) -> bool:
    return bool(
        task_run is not None
        and queue_entry is not None
        and task_run.id == ownership.task_run_id
        and task_run.task_id == ownership.task_run_task_id
        and task_run.agent_id == ownership.task_run_agent_id
        and task_run.state == "queued"
        and task_run.runner_id == ownership.task_run_runner_id
        and task_run.adapter_run_id == ownership.task_run_adapter_run_id
        and task_run.adapter_run_id is None
        and task_run.started_at == ownership.task_run_started_at
        and task_run.started_at is None
        and task_run.ended_at == ownership.task_run_ended_at
        and task_run.ended_at is None
        and task_run.worktree_path == ownership.task_run_worktree_path
        and task_run.last_heartbeat_at
        == ownership.task_run_last_heartbeat_at
        and task_run.lease_expires_at
        == ownership.task_run_lease_expires_at
        and task_run.lease_expires_at is not None
        and lease_is_current
        and write_lock_is_current
        and task_run.metrics_json == ownership.task_run_metrics_json
        and task_run.updated_at == ownership.task_run_updated_at
        and queue_entry.id == ownership.queue_entry_id
        and queue_entry.session_id == ownership.queue_session_id
        and queue_entry.task_id == ownership.queue_task_id
        and queue_entry.task_run_id == ownership.queue_task_run_id
        and queue_entry.task_run_id == ownership.task_run_id
        and queue_entry.access_mode == ownership.queue_access_mode
        and queue_entry.target_id == ownership.queue_target_id
        and queue_entry.target_lock_key == ownership.queue_target_lock_key
        and queue_entry.state == ownership.queue_state
        and queue_entry.state == "running"
        and queue_entry.started_at == ownership.queue_started_at
        and queue_entry.started_at is not None
        and queue_entry.finished_at == ownership.queue_finished_at
        and queue_entry.finished_at is None
        and queue_entry.updated_at == ownership.queue_updated_at
    )


async def execute_task_run(
    db: DbSession,
    task_run: TaskRun,
    *,
    adapter_type: str,
    adapter: AgentAdapter,
    plan_context: Optional[dict[str, Any]] = None,
    supervisor: RunSupervisor = default_run_supervisor,
    max_runtime_seconds: Optional[float] = None,
    lease_renewal_interval_seconds: Optional[float] = None,
) -> TaskRun:
    identity = sa_inspect(task_run).identity
    if identity is None or len(identity) != 1 or not isinstance(identity[0], str):
        raise TaskRunLifecycleError("TaskRun must be persistent before execution.")
    task_run_id = identity[0]
    cached_adapter_run_id = task_run.__dict__.get("adapter_run_id")
    if not isinstance(cached_adapter_run_id, str):
        cached_adapter_run_id = None
    try:
        supervised_run = supervisor.register(
            task_run_id=task_run_id,
            adapter_type=adapter_type,
            adapter_run_id=cached_adapter_run_id,
            adapter=adapter,
        )
    except RunRegistrationRejected:
        db.rollback()
        raise
    lease_controller: Optional[_ExecutionLeaseController] = None
    prepare_failure_ownership: Optional[_PrepareFailureOwnershipSnapshot] = None
    try:
        def prepare_request() -> tuple[
            TaskRun,
            _ExecutionLeaseController,
            AgentRunRequest,
            AdapterCapabilities,
            _RequestLaunchSnapshot,
        ]:
            nonlocal prepare_failure_ownership
            db.rollback()
            db.expire_all()
            fresh_task_run = db.get(TaskRun, task_run_id)
            if fresh_task_run is None:
                raise TaskRunLifecycleError(f"TaskRun not found: {task_run_id}")
            queue_entry = entry_for_task_run(db, fresh_task_run.id)
            if (
                queue_entry is None
                or fresh_task_run.state != "queued"
                or fresh_task_run.adapter_run_id != cached_adapter_run_id
                or queue_entry.state not in {"queued", "running"}
            ):
                raise _execution_lease_ownership_error()
            prepared_lease_controller = _ExecutionLeaseController(
                db.get_bind(),
                interval_seconds=lease_renewal_interval_seconds,
            )
            if queue_entry.started_at is None:
                mark_task_run_running(
                    db,
                    fresh_task_run.id,
                    "Adapter execution started.",
                )
                db.expire_all()
                fresh_task_run = db.exec(
                    select(TaskRun)
                    .where(TaskRun.id == task_run_id)
                    .execution_options(populate_existing=True)
                ).one()
                queue_entry = db.exec(
                    select(SessionQueueEntry)
                    .where(SessionQueueEntry.id == queue_entry.id)
                    .execution_options(populate_existing=True)
                ).one()
            prepare_failure_ownership = _freeze_prepare_failure_ownership(
                fresh_task_run,
                queue_entry,
            )
            _scope_baseline_required_for_run(db, fresh_task_run)
            capabilities = _adapter_capabilities_for_execution(adapter)
            launch_snapshots: list[_RequestLaunchSnapshot] = []
            request = agent_run_request_for(
                db,
                fresh_task_run,
                adapter_type=adapter_type,
                plan_context=plan_context,
                fence_current_execution=True,
                _launch_snapshot_out=launch_snapshots,
            )
            if len(launch_snapshots) != 1:
                raise _execution_lease_ownership_error()
            return (
                fresh_task_run,
                prepared_lease_controller,
                request,
                capabilities,
                launch_snapshots[0],
            )

        try:
            current, prepared = supervisor.run_if_current(
                supervised_run,
                prepare_request,
            )
        except TaskRunScopeError as exc:
            if isinstance(exc, _RequestPersistenceOwnershipError):
                db.rollback()
                raise
            current, failed_task_run = supervisor.run_if_current(
                supervised_run,
                lambda: _persist_active_task_run_scope_failure(
                    db,
                    task_run_id,
                    exc,
                    prepare_failure_ownership,
                ),
            )
            if not current or failed_task_run is None:
                db.rollback()
                raise
            return failed_task_run
        if not current or prepared is None:
            db.rollback()
            raise _execution_lease_ownership_error()
        task_run, lease_controller, request, capabilities, launch_snapshot = prepared
        binding_launch_started = False
        try:
            async def reserve_binding_launch(operation):
                async def run_started_operation():
                    nonlocal binding_launch_started
                    binding_launch_started = True
                    return await operation()

                return await supervisor.run_async_if_current(
                    supervised_run,
                    run_started_operation,
                )

            stream_adapter = _ExecutionAccessBindingAdapter(
                db,
                task_run.id,
                adapter,
                expected_capabilities=capabilities,
                expected_launch_snapshot=launch_snapshot,
                on_execution_bound=lease_controller.start,
                launch_reservation=reserve_binding_launch,
                supervisor_ownership_guard=lambda: supervisor.is_current(
                    supervised_run
                ),
            )

            def bind_adapter_run(run: AdapterRun) -> None:
                nonlocal supervised_run
                if not supervisor.is_current(supervised_run):
                    raise _execution_lease_ownership_error()
                lease_controller.bind_adapter_run(run.adapter_run_id)
                supervised = supervisor.update_adapter_run_id(
                    task_run.id,
                    run.adapter_run_id,
                    expected=supervised_run,
                )
                if (
                    supervised is None
                    or not supervisor.is_current(supervised)
                ):
                    raise _execution_lease_ownership_error()
                supervised_run = supervised

            def owns_supervised_execution(ownership_db: DbSession) -> bool:
                return bool(
                    supervisor.is_current(supervised_run)
                    and lease_controller.owns_current_execution(ownership_db)
                )

            stream = run_adapter_event_stream(
                db,
                stream_adapter,
                request,
                on_adapter_run_created=bind_adapter_run,
                ownership_guard=owns_supervised_execution,
            )
            guarded_stream = _run_adapter_stream_with_execution_lease(
                stream,
                lease_controller,
                supervisor=supervisor,
                task_run_id=task_run.id,
                expected_supervised_run=supervised_run,
            )
            runtime_timeout = (
                max_runtime_seconds
                if max_runtime_seconds is not None
                else capabilities.max_runtime_sec
            )
            if runtime_timeout is not None:
                await asyncio.wait_for(guarded_stream, timeout=runtime_timeout)
            else:
                await guarded_stream
        except TaskRunScopeError as exc:
            stale_before_launch = bool(
                not binding_launch_started
                and not supervisor.is_current(supervised_run)
                and lease_controller._token is None
            )
            if stale_before_launch:
                db.rollback()
            else:
                db.refresh(task_run)
                if task_run.state not in {"completed", "failed", "interrupted"}:
                    transition_task_run(
                        db,
                        task_run.id,
                        "failed",
                        error_code=exc.error_code,
                        error_message=exc.message,
                    )
        except asyncio.TimeoutError:
            transition_task_run(
                db,
                task_run.id,
                "failed",
                payload={"reason": "TaskRun exceeded max runtime."},
                error_code="TASK_RUN_TIMEOUT",
                error_message="TaskRun exceeded its maximum runtime.",
            )
        db.refresh(task_run)
        try:
            if task_run.state == "collecting_diff":
                await _run_with_execution_lease(
                    finalize_adapter_completed_task_run(
                        db,
                        task_run,
                        lease_controller=lease_controller,
                        supervisor=supervisor,
                        expected_supervised_run=supervised_run,
                    ),
                    lease_controller,
                    supervisor=supervisor,
                    task_run_id=task_run.id,
                    expected_supervised_run=supervised_run,
                )
            elif task_run.state == "completed":
                await _run_with_execution_lease(
                    finalize_completed_task_run(db, task_run),
                    lease_controller,
                    supervisor=supervisor,
                    task_run_id=task_run.id,
                    expected_supervised_run=supervised_run,
                )
        except TaskRunScopeError as exc:
            if not supervisor.is_current(supervised_run):
                handled, recovered = True, None
            else:
                handled, recovered = _recover_finalizer_scope_error(
                    db,
                    task_run.id,
                    exc,
                    lease_controller,
                )
            if not handled:
                raise
            if recovered is not None:
                task_run.state = recovered.state
                task_run.error_code = recovered.error_code
                task_run.error_message = recovered.error_message
                task_run.updated_at = recovered.updated_at
                task_run.ended_at = recovered.ended_at
        return task_run
    finally:
        if lease_controller is not None:
            await lease_controller.stop()
        supervisor.unregister(task_run_id, expected=supervised_run)


async def _run_adapter_stream_with_execution_lease(
    stream: Any,
    lease_controller: _ExecutionLeaseController,
    *,
    supervisor: RunSupervisor,
    task_run_id: str,
    expected_supervised_run: Optional[SupervisedRun] = None,
) -> Any:
    return await _run_with_execution_lease(
        stream,
        lease_controller,
        supervisor=supervisor,
        task_run_id=task_run_id,
        durable_ownership_preflight=False,
        expected_supervised_run=expected_supervised_run,
        cancel_operation_after_interrupt_started=(
            _cancel_adapter_stream_after_interrupt_started
        ),
    )


async def _interrupt_exact_supervised_run(
    supervisor: RunSupervisor,
    supervised_run: Optional[SupervisedRun],
    *,
    preserve_primary_error: bool = False,
) -> bool:
    if (
        supervised_run is None
        or supervised_run.adapter is None
        or supervised_run.adapter_run_id is None
    ):
        return False
    try:
        return await supervisor.interrupt_exact(supervised_run)
    except asyncio.CancelledError:
        if preserve_primary_error:
            return False
        raise
    except Exception:
        return False


async def _run_with_execution_lease(
    operation: Any,
    lease_controller: _ExecutionLeaseController,
    *,
    supervisor: RunSupervisor,
    task_run_id: str,
    durable_ownership_preflight: bool = True,
    expected_supervised_run: Optional[SupervisedRun] = None,
    cancel_operation_after_interrupt_started: Optional[
        Callable[[asyncio.Task[Any]], None]
    ] = None,
) -> Any:
    bootstrap_adapter_run = expected_supervised_run or supervisor.active(task_run_id)
    frozen_adapter_run = bootstrap_adapter_run
    if (
        frozen_adapter_run is None
        or frozen_adapter_run.task_run_id != task_run_id
        or frozen_adapter_run.adapter is None
        or frozen_adapter_run.adapter_run_id is None
    ):
        frozen_adapter_run = None
    ownership_task = asyncio.create_task(
        lease_controller.wait_until_ownership_lost()
    )
    supervisor_ownership_task = (
        asyncio.create_task(bootstrap_adapter_run.wait_until_ownership_lost())
        if bootstrap_adapter_run is not None
        else None
    )
    operation_started = False
    ownership_preflight_failed = False

    async def run_operation_after_ownership_waiter() -> Any:
        nonlocal operation_started, ownership_preflight_failed
        try:
            await asyncio.sleep(0)
            if (
                ownership_task.done()
                or (
                    supervisor_ownership_task is not None
                    and supervisor_ownership_task.done()
                )
                or bootstrap_adapter_run is None
                or not supervisor.is_current(bootstrap_adapter_run)
            ):
                raise _execution_lease_ownership_error()
            if durable_ownership_preflight:
                try:
                    with DbSession(lease_controller._bind) as ownership_db:
                        owns_current_execution = (
                            lease_controller.owns_current_execution(ownership_db)
                        )
                        durable_task_run = ownership_db.get(TaskRun, task_run_id)
                        owns_adapter_run = bool(
                            durable_task_run is not None
                            and (
                                (
                                    frozen_adapter_run is None
                                    and durable_task_run.adapter_run_id is None
                                )
                                or (
                                    frozen_adapter_run is not None
                                    and frozen_adapter_run.adapter_run_id
                                    == durable_task_run.adapter_run_id
                                )
                            )
                        )
                except Exception as exc:
                    ownership_preflight_failed = True
                    raise _execution_lease_ownership_error() from exc
                if not owns_current_execution or not owns_adapter_run:
                    ownership_preflight_failed = True
                    raise _execution_lease_ownership_error()
            if (
                ownership_task.done()
                or (
                    supervisor_ownership_task is not None
                    and supervisor_ownership_task.done()
                )
                or not supervisor.is_current(bootstrap_adapter_run)
            ):
                raise _execution_lease_ownership_error()
            operation_started = True
            return await operation
        finally:
            if not operation_started:
                close_operation = getattr(operation, "close", None)
                if callable(close_operation):
                    close_operation()

    operation_task = asyncio.create_task(run_operation_after_ownership_waiter())
    try:
        wait_tasks = {operation_task, ownership_task}
        if supervisor_ownership_task is not None:
            wait_tasks.add(supervisor_ownership_task)
        await asyncio.wait(
            wait_tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        supervisor_ownership_lost = bool(
            bootstrap_adapter_run is None
            or not supervisor.is_current(bootstrap_adapter_run)
            or (
                supervisor_ownership_task is not None
                and supervisor_ownership_task.done()
            )
        )
        if (
            ownership_task.done()
            or supervisor_ownership_lost
            or ownership_preflight_failed
        ):
            if frozen_adapter_run is not None:
                if cancel_operation_after_interrupt_started is None:
                    operation_task.cancel()
                    await asyncio.gather(operation_task, return_exceptions=True)
                    await _interrupt_exact_supervised_run(
                        supervisor,
                        frozen_adapter_run,
                        preserve_primary_error=True,
                    )
                else:
                    interrupt_task = asyncio.create_task(
                        _interrupt_exact_supervised_run(
                            supervisor,
                            frozen_adapter_run,
                            preserve_primary_error=True,
                        )
                    )
                    cancel_operation_after_interrupt_started(operation_task)
                    await asyncio.gather(
                        operation_task,
                        interrupt_task,
                        return_exceptions=True,
                    )
            else:
                bound_token = lease_controller._token
                bound_adapter_run_id = (
                    bound_token.adapter_run_id
                    if bound_token is not None
                    else None
                )
                operation_failed = bool(
                    operation_task.done()
                    and not operation_task.cancelled()
                    and operation_task.exception() is not None
                )
                interrupt_task = None
                if (
                    not operation_failed
                    and bootstrap_adapter_run is not None
                    and bootstrap_adapter_run.task_run_id == task_run_id
                    and bootstrap_adapter_run.adapter is not None
                    and bound_adapter_run_id is not None
                ):
                    interrupt_task = asyncio.create_task(
                        bootstrap_adapter_run.adapter.interrupt(
                            bound_adapter_run_id
                        )
                    )
                if (
                    interrupt_task is not None
                    and cancel_operation_after_interrupt_started is not None
                ):
                    cancel_operation_after_interrupt_started(operation_task)
                else:
                    operation_task.cancel()
                await asyncio.gather(
                    operation_task,
                    *([interrupt_task] if interrupt_task is not None else []),
                    return_exceptions=True,
                )
            raise _execution_lease_ownership_error()
        return await operation_task
    finally:
        ownership_task.cancel()
        if supervisor_ownership_task is not None:
            supervisor_ownership_task.cancel()
        if not operation_task.done():
            operation_task.cancel()
        cleanup_tasks = [ownership_task, operation_task]
        if supervisor_ownership_task is not None:
            cleanup_tasks.append(supervisor_ownership_task)
        await asyncio.gather(
            *cleanup_tasks,
            return_exceptions=True,
        )


async def finalize_adapter_completed_task_run(
    db: DbSession,
    task_run: TaskRun,
    *,
    lease_controller: Optional[_ExecutionLeaseController] = None,
    supervisor: Optional[RunSupervisor] = None,
    expected_supervised_run: Optional[SupervisedRun] = None,
) -> TaskRun:
    fence_args = (
        lease_controller,
        supervisor,
        expected_supervised_run,
    )
    if all(item is None for item in fence_args):
        run_downstream = _commit_adapter_completed_task_run(db, task_run)
    elif all(item is not None for item in fence_args):
        assert lease_controller is not None
        assert supervisor is not None
        assert expected_supervised_run is not None
        run_downstream = _commit_exact_generation_finalizer(
            db,
            task_run,
            lease_controller=lease_controller,
            supervisor=supervisor,
            expected_supervised_run=expected_supervised_run,
        )
    else:
        raise _execution_lease_ownership_error()
    if run_downstream:
        await _finish_completed_task_run_side_effects(db, task_run)
    else:
        db.refresh(task_run)
    return task_run


def _commit_exact_generation_finalizer(
    db: DbSession,
    task_run: TaskRun,
    *,
    lease_controller: _ExecutionLeaseController,
    supervisor: RunSupervisor,
    expected_supervised_run: SupervisedRun,
) -> bool:
    token = lease_controller._token
    if (
        token is None
        or token.task_run_id != task_run.id
        or expected_supervised_run.task_run_id != token.task_run_id
        or expected_supervised_run.adapter_run_id != token.adapter_run_id
    ):
        raise _execution_lease_ownership_error()

    def commit() -> bool:
        if (
            lease_controller._token is not token
            or not lease_controller._token_owns_current_execution(db, token)
        ):
            raise _execution_lease_ownership_error()
        fence = _FinalizerCommitFence(
            token,
            on_terminal_commit=lambda: supervisor.seal_reserved_if_current(
                expected_supervised_run
            ),
        )
        before_commit_listener = fence.before_commit
        after_commit_listener = fence.after_commit
        after_rollback_listener = fence.after_rollback
        event.listen(db, "before_commit", before_commit_listener)
        event.listen(db, "after_commit", after_commit_listener)
        event.listen(db, "after_rollback", after_rollback_listener)
        try:
            return _commit_adapter_completed_task_run(db, task_run)
        finally:
            event.remove(db, "before_commit", before_commit_listener)
            event.remove(db, "after_commit", after_commit_listener)
            event.remove(db, "after_rollback", after_rollback_listener)

    committed, run_downstream = supervisor.commit_if_current(
        expected_supervised_run,
        commit,
    )
    if not committed:
        raise _execution_lease_ownership_error()
    return bool(run_downstream)


def _commit_adapter_completed_task_run(
    db: DbSession,
    task_run: TaskRun,
) -> bool:
    task = db.get(Task, task_run.task_id)
    if task is None:
        raise TaskRunLifecycleError(f"Task not found: {task_run.task_id}")
    if not _claim_scope_finalization(db, task_run):
        db.refresh(task_run)
        return False
    try:
        access_mode = require_task_run_execution_access_mode(db, task_run)
    except TaskRunScopeError as exc:
        status = (
            "rejected"
            if exc.error_code == "TASK_RUN_SCOPE_VIOLATION"
            else "unverifiable"
        )
        _record_scope_validation_event(db, task_run, status, exc.error_code)
        transition_task_run(
            db,
            task_run.id,
            "failed",
            error_code=exc.error_code,
            error_message=exc.message,
        )
        db.refresh(task_run)
        return False
    if access_mode == "readonly":
        transition_task_run(db, task_run.id, "completed")
        require_task_run_artifact_scope_passed(db, task_run.id)
        _collect_completed_task_run_artifacts(db, task_run)
        _run_completed_task_run_sync_side_effects(db, task_run)
        return True

    decision = validate_task_run_scope(db, task_run.id)
    persist_scope_decision(db, task_run, decision)
    try:
        require_task_run_scope_passed(db, task_run.id)
    except TaskRunScopeError as exc:
        status = (
            "rejected"
            if exc.error_code == "TASK_RUN_SCOPE_VIOLATION"
            else "unverifiable"
        )
        _record_scope_validation_event(db, task_run, status, exc.error_code)
        transition_task_run(
            db,
            task_run.id,
            "failed",
            error_code=exc.error_code,
            error_message=exc.message,
        )
        refresh_session_ledger_for_task_run(db, task_run.id)
        db.refresh(task_run)
        return False

    _record_scope_validation_event(db, task_run, "passed", None)
    _collect_completed_task_run_artifacts(db, task_run)
    transition_task_run(db, task_run.id, "completed")
    _run_completed_task_run_sync_side_effects(db, task_run)
    return True


def _claim_scope_finalization(
    db: DbSession,
    task_run: TaskRun,
) -> bool:
    db.refresh(task_run)
    if task_run.state in {"completed", "failed", "interrupted"}:
        return False
    if task_run.state != "collecting_diff":
        raise TaskRunLifecycleError(
            "Only collecting_diff TaskRuns can enter scope finalization."
        )

    metrics = internal_metrics_for_run(task_run)
    if isinstance(metrics.get("scopeFinalizationClaim"), dict):
        return False

    original_metrics_json = task_run.metrics_json
    now = utc_now()
    metrics["scopeFinalizationClaim"] = {
        "status": "claimed",
        "claimId": str(uuid4()),
        "claimedAt": now.isoformat(),
    }
    result = db.execute(
        update(TaskRun)
        .where(TaskRun.id == task_run.id)
        .where(TaskRun.state == "collecting_diff")
        .where(TaskRun.metrics_json == original_metrics_json)
        .values(
            metrics_json=json.dumps(metrics, separators=(",", ":")),
            updated_at=now,
        )
    )
    db.commit()
    db.refresh(task_run)
    return result.rowcount == 1


async def finalize_completed_task_run(
    db: DbSession,
    task_run: TaskRun,
) -> TaskRun:
    require_task_run_artifact_scope_passed(db, task_run.id)
    _collect_completed_task_run_artifacts(db, task_run)
    return await _run_completed_task_run_side_effects(db, task_run)


def _collect_completed_task_run_artifacts(
    db: DbSession,
    task_run: TaskRun,
) -> None:
    diff_ready = True
    try:
        collect_task_run_diff(db, task_run.id)
    except DiffCollectionError as exc:
        diff_ready = False
        record_diff_collection_failure(db, task_run.id, exc)
        record_review_collection_failure(db, task_run.id, ReviewError("No diff artifact found for review."), skipped=True)
    if diff_ready:
        try:
            create_scripted_review_for_task_run(db, task_run.id)
        except ReviewError as exc:
            record_review_collection_failure(db, task_run.id, exc)


async def _run_completed_task_run_side_effects(
    db: DbSession,
    task_run: TaskRun,
) -> TaskRun:
    _run_completed_task_run_sync_side_effects(db, task_run)
    return await _finish_completed_task_run_side_effects(db, task_run)


def _run_completed_task_run_sync_side_effects(
    db: DbSession,
    task_run: TaskRun,
) -> None:
    refresh_session_ledger_for_task_run(db, task_run.id)
    _advance_ready_integrations(db)
    _complete_ready_pipeline_review_tasks(db, task_run.task_id)
    _maybe_auto_preview_and_mock_deploy(db, task_run)


def _advance_ready_integrations(db: DbSession) -> None:
    from app.dag_integration import integrate_ready_joins

    for run_id in integrate_ready_joins(db):
        run = db.get(TaskRun, run_id)
        if run is not None:
            _complete_ready_pipeline_review_tasks(db, run.task_id)
            _maybe_auto_preview_and_mock_deploy(db, run)


async def _finish_completed_task_run_side_effects(
    db: DbSession,
    task_run: TaskRun,
) -> TaskRun:
    await _auto_start_next_pipeline_task(db, task_run.task_id)
    db.refresh(task_run)
    return task_run


def _record_scope_validation_event(
    db: DbSession,
    task_run: TaskRun,
    status: str,
    error_code: Optional[str],
) -> None:
    payload: dict[str, Any] = {
        "result": status,
        "taskRunId": task_run.id,
    }
    if error_code is not None:
        payload["errorCode"] = error_code
    append_task_run_event(
        db,
        task_run_id=task_run.id,
        event_type=(
            "task.scope_validation.passed"
            if status == "passed"
            else "task.scope_validation.failed"
        ),
        payload_json=json.dumps(payload, separators=(",", ":")),
    )


async def _auto_start_next_pipeline_task(
    db: DbSession,
    completed_task_id: str,
) -> Optional[TaskRun]:
    completed_task = db.get(Task, completed_task_id)
    if completed_task is None:
        return None
    for task in list_session_tasks(db, completed_task.session_id):
        if task.id == completed_task_id:
            continue
        if not _is_auto_pipeline_task(task):
            continue
        if _has_task_run(db, task.id):
            continue
        decision = evaluate_and_apply_scheduler_readiness(db, task)
        if not decision.runnable:
            continue
        task_run = create_task_run(db, task.id)
        adapter_type = adapter_type_for_run(db, task_run)
        await execute_task_run_background(
            db,
            task_run.id,
            adapter_type,
        )
        return db.get(TaskRun, task_run.id)
    return None


def _complete_ready_pipeline_review_tasks(
    db: DbSession,
    completed_task_id: str,
) -> list[Task]:
    completed_task = db.get(Task, completed_task_id)
    if completed_task is None:
        return []

    completed: list[Task] = []
    for task in list_session_tasks(db, completed_task.session_id):
        if task.intent_type not in {"review", "qa_review"}:
            continue
        if task.status not in {"pending", "waiting_dependency", "blocked"}:
            continue
        plan = plan_json_for_task(task)
        if plan.get("planner") not in {"contract_first_v1", "llm_v1"}:
            continue
        if not _dependencies_have_review_artifacts(db, task):
            continue
        decision = evaluate_and_apply_scheduler_readiness(db, task)
        if not decision.runnable:
            continue
        plan = plan_json_for_task(task)
        scheduler = dict(plan.get("scheduler") or {})
        scheduler.update(
            {
                "state": "completed",
                "runnable": False,
                "reason": "Planned review was satisfied by the generated review artifact.",
            }
        )
        plan["scheduler"] = scheduler
        task.plan_json = json.dumps(plan, separators=(",", ":"))
        task.status = "completed"
        task.updated_at = utc_now()
        db.add(task)
        db.commit()
        db.refresh(task)
        completed.append(task)
    return completed


def _dependencies_have_review_artifacts(db: DbSession, task: Task) -> bool:
    try:
        dependency_ids = json.loads(task.depends_on_task_ids)
    except json.JSONDecodeError:
        return False
    if not isinstance(dependency_ids, list) or not dependency_ids:
        return False

    for dependency_id in dependency_ids:
        if not isinstance(dependency_id, str):
            return False
        dependency_runs = list_task_runs(db, dependency_id)
        completed_runs = [run for run in dependency_runs if run.state == "completed"]
        if not completed_runs:
            return False
        if not any(list_task_run_reviews(db, run.id) for run in completed_runs):
            return False
    return True


def _maybe_auto_preview_and_mock_deploy(db: DbSession, task_run: TaskRun) -> None:
    from app.dag_integration import IntegrationError, delivery_worktree_path

    try:
        delivery_path = delivery_worktree_path(db, task_run)
    except IntegrationError:
        return
    task = db.get(Task, task_run.task_id)
    if task is None or task.intent_type != "frontend_change":
        return
    plan = plan_json_for_task(task)
    if plan.get("planner") != "contract_first_v1":
        return
    demo_root = Path(delivery_path) / "apps/demo"
    if not demo_root.exists():
        return
    from app.preview_deploy_jobs import (
        enqueue_deploy_job,
        enqueue_preview_job,
        run_deploy_job,
        run_preview_job,
    )

    preview_job = enqueue_preview_job(db, task_run)
    if preview_job is None:
        return
    preview_job = run_preview_job(db, preview_job, preview_service=_preview_service)
    if preview_job.state != "completed":
        return
    evidence = json.loads(preview_job.evidence_json)
    preview_id = evidence.get("previewId")
    if not isinstance(preview_id, str):
        return
    deploy_job = enqueue_deploy_job(db, task_run.id, preview_id)
    run_deploy_job(db, deploy_job, deploy_service=_deploy_service)
    refresh_session_ledger_for_task_run(db, task_run.id)


def _is_auto_pipeline_task(task: Task) -> bool:
    plan = plan_json_for_task(task)
    return (
        plan.get("planner") in AUTO_PIPELINE_PLANNERS
        and plan.get("autoStart") is True
        and task.intent_type in {"backend_change", "frontend_change"}
    )


def _has_task_run(db: DbSession, task_id: str) -> bool:
    return bool(list_task_runs(db, task_id))


async def _background_execute_task_run(
    task_run_id: str,
    adapter_type: str,
) -> None:
    from app.db import engine as db_engine

    with DbSession(db_engine) as db:
        await execute_task_run_background(db, task_run_id, adapter_type)


async def _background_run_worker_once() -> None:
    from app.db import engine as db_engine

    with DbSession(db_engine) as db:
        await RunWorker().run_once(db)


async def _background_dispatch_queued_task_runs() -> None:
    from app.db import engine as db_engine

    with DbSession(db_engine) as db:
        await BoundedRunDispatcher().run_until_idle(db)


async def _execute_dispatch_claim(bind: Any, claim: DispatchClaim) -> bool:
    with DbSession(bind) as db:
        return await execute_task_run_background(
            db,
            claim.task_run_id,
            claim.adapter_type,
            worker_id=claim.worker_id,
        )


async def execute_task_run_background(
    db: DbSession,
    task_run_id: str,
    adapter_type: str,
    *,
    worker_id: Optional[str] = None,
) -> bool:
    worker_id = worker_id or _new_worker_id()
    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        return False
    try:
        if task_run.state == "queued":
            if task_run.runner_id != worker_id:
                try:
                    task_run = claim_task_run_for_worker(
                        db,
                        task_run.id,
                        worker_id=worker_id,
                    )
                except TaskRunLifecycleError:
                    return False
            if not _prepare_claimed_task_run_for_adapter(db, task_run, worker_id):
                return False
        refresh_task_run_heartbeat(
            db,
            task_run.id,
            runner_id=task_run.runner_id,
        )
        _scope_baseline_required_for_run(db, task_run)
        if metrics_for_run(task_run).get("forceFailure") is True:
            await execute_task_run(
                db,
                task_run,
                adapter_type="codex",
                adapter=CodexAdapter(),
                plan_context={"forceFailure": True},
            )
            return True
        if adapter_type == "scripted_mock":
            await execute_task_run(
                db,
                task_run,
                adapter_type="scripted_mock",
                adapter=ScriptedMockAdapter(),
            )
            return True
        gateway = _resolve_provider_gateway_for_run(db, task_run, adapter_type)
        adapter_type = gateway["adapter_type"]
        adapter = adapter_for_type(
            adapter_type,
            codex_adapter=CodexAdapter(),
            claude_code_adapter=ClaudeCodeAdapter(),
            scripted_mock_adapter=ScriptedMockAdapter(),
        )
        await execute_task_run(
            db,
            task_run,
            adapter_type=adapter_type,
            adapter=adapter,
        )
        return True
    except TaskRunScopeError as exc:
        db.refresh(task_run)
        if task_run.state not in {"completed", "failed", "interrupted"}:
            transition_task_run(
                db,
                task_run_id,
                "failed",
                error_code=exc.error_code,
                error_message=exc.message,
            )
        return True
    except Exception:
        db.refresh(task_run)
        if task_run.state not in {"completed", "failed", "interrupted"}:
            try:
                transition_task_run(
                    db,
                    task_run_id,
                    "failed",
                    error_code="ADAPTER_EXECUTION_ERROR",
                    error_message="Adapter execution failed unexpectedly.",
                )
            except Exception:
                pass
        return True
    finally:
        _release_provider_capacity(db, task_run_id)


def _prepare_claimed_task_run_for_adapter(
    db: DbSession,
    task_run: TaskRun,
    worker_id: str,
) -> bool:
    task = db.get(Task, task_run.task_id)
    if task is None:
        return False
    decision = evaluate_and_apply_scheduler_readiness(db, task)
    if not decision.runnable:
        if decision.state == SCHEDULER_WAITING_TARGET_LOCK:
            mark_task_run_waiting_lock(db, task_run.id, decision.reason)
        return False
    queue_decision = queue_gate_for_task_run(db, task_run.id)
    if not queue_decision.runnable:
        return False
    access_mode = require_task_run_execution_access_mode(
        db,
        task_run,
        require_started=False,
    )
    if access_mode == "readonly":
        mark_task_run_running(db, task_run.id, queue_decision.reason)
        return True
    target_id = target_id_for_task(task, db)
    if target_id is None:
        mark_task_run_running(
            db,
            task_run.id,
            "Legacy write TaskRun has no target id; preserving existing demo path.",
        )
        return True
    result = acquire_target_lock(
        db,
        target_id=target_id,
        session_id=task.session_id,
        task_run_id=task_run.id,
        worker_id=worker_id,
        lease_expires_at=task_run.lease_expires_at,
    )
    if not result.acquired or result.lock is None:
        mark_task_run_waiting_lock(db, task_run.id, result.reason)
        evaluate_and_apply_scheduler_readiness(db, task)
        return False
    try:
        store_task_run_target_lock_acquisition_context(
            task_run.id,
            target_id=target_id,
            session_id=task.session_id,
            worker_id=worker_id,
            lock_id=result.lock.id,
        )
    except TaskRunScopeError:
        release_target_lock_for_task_run(
            db,
            target_id=target_id,
            expected_lock_id=result.lock.id,
            worker_id=worker_id,
            task_run_id=task_run.id,
            session_id=task.session_id,
            release_reason="target_lock_context_unavailable",
        )
        raise
    mark_task_run_running(db, task_run.id, "Target write lock acquired.")
    return True


def _scope_baseline_required_for_run(
    db: DbSession,
    task_run: TaskRun,
) -> bool:
    task = db.get(Task, task_run.task_id)
    if task is None:
        raise TaskRunScopeError(
            "TASK_RUN_SCOPE_UNVERIFIABLE",
            "The task run scope execution binding cannot be verified.",
        )
    access_mode = require_task_run_execution_access_mode(
        db,
        task_run,
        require_started=False,
    )
    if access_mode == "readonly":
        return False
    target_id = target_id_for_task(task, db)
    if target_id is None:
        raise TaskRunScopeError(
            "TASK_RUN_SCOPE_UNVERIFIABLE",
            "The task run scope target cannot be verified.",
        )
    held_lock = held_lock_for_target(db, target_id)
    if (
        held_lock is None
        or held_lock.task_run_id != task_run.id
        or held_lock.session_id != task.session_id
        or not isinstance(task_run.runner_id, str)
        or not task_run.runner_id
        or held_lock.worker_id != task_run.runner_id
    ):
        raise TaskRunScopeError(
            "TASK_RUN_SCOPE_UNVERIFIABLE",
            "The task run scope execution lock cannot be verified.",
        )
    return True


def _resolve_provider_gateway_for_run(
    db: DbSession,
    task_run: TaskRun,
    fallback_adapter_type: str,
) -> dict[str, str]:
    task = db.get(Task, task_run.task_id)
    if task is None:
        raise TaskRunLifecycleError(f"Task not found: {task_run.task_id}")
    session = db.get(AgentHubSession, task.session_id)
    if session is None:
        raise TaskRunLifecycleError(f"Session not found: {task.session_id}")
    target_id = target_id_for_task(task, db)
    metrics = metrics_for_run(task_run)
    runtime_resolution = metrics.get("runtimeConfigResolution")
    provider_assignment = metrics.get("providerAssignment")
    runtime_provider_id = None
    if isinstance(runtime_resolution, dict):
        candidate_provider_id = runtime_resolution.get("providerId")
        if isinstance(candidate_provider_id, str) and candidate_provider_id:
            runtime_provider_id = candidate_provider_id
    if runtime_provider_id is None and isinstance(provider_assignment, dict):
        candidate_provider_id = provider_assignment.get("providerId")
        if isinstance(candidate_provider_id, str) and candidate_provider_id:
            runtime_provider_id = candidate_provider_id
    context = CodingRunContext(
        workspace_id=session.workspace_id,
        session_id=session.id,
        task_id=task.id,
        task_run_id=task_run.id,
        role=_role_for_task_run(db, task_run),
        target_id=target_id,
        mode="write" if write_lock_required_for_task(task) else "review",
        required_capabilities=("file_edit",)
        if write_lock_required_for_task(task)
        else ("review",),
        worktree_path=task_run.worktree_path,
        runtime_provider_id=runtime_provider_id,
        runtime_adapter_type=fallback_adapter_type,
        fallback_policy="scripted_mock",
    )
    plan = _provider_resolver.resolve(context)
    record_provider_resolution(db, task_run_id=task_run.id, plan=plan)
    if plan.selected_provider_id is None or plan.selected_adapter_type is None:
        transition_task_run(
            db,
            task_run.id,
            "failed",
            error_code="PROVIDER_RESOLUTION_FAILED",
            error_message=plan.selection_reason,
        )
        raise TaskRunLifecycleError(plan.selection_reason)
    provider = _provider_resolver.registry.get(plan.selected_provider_id)
    if provider is not None:
        health = _provider_health_probe.check_provider(provider, context=context)
        record_provider_health_check(db, task_run_id=task_run.id, health=health)
        if not health.available and provider.is_real_provider:
            transition_task_run(
                db,
                task_run.id,
                "failed",
                error_code="PROVIDER_UNAVAILABLE",
                error_message=health.reason,
            )
            raise TaskRunLifecycleError(health.reason)
    capacity = _provider_capacity_limiter.acquire(plan.selected_provider_id, task_run.id)
    record_provider_capacity_event(db, task_run_id=task_run.id, capacity=capacity)
    if not capacity.acquired:
        transition_task_run(
            db,
            task_run.id,
            "failed",
            error_code="PROVIDER_CAPACITY_EXHAUSTED",
            error_message=capacity.reason or "Provider capacity is exhausted.",
        )
        raise TaskRunLifecycleError(capacity.reason or "Provider capacity is exhausted.")
    return {"adapter_type": plan.selected_adapter_type}


def _release_provider_capacity(db: DbSession, task_run_id: str) -> None:
    release = _provider_capacity_limiter.release(task_run_id)
    if release.provider_id == "unknown":
        return
    record_provider_capacity_event(
        db,
        task_run_id=task_run_id,
        capacity=release,
        released=True,
    )


def _role_for_task_run(db: DbSession, task_run: TaskRun) -> str:
    agent = db.get(Agent, task_run.agent_id)
    return agent.role if agent is not None else "frontend"


def _new_worker_id() -> str:
    return f"{DEFAULT_RUN_WORKER_ID_PREFIX}:{uuid4()}"


async def interrupt_supervised_task_run(
    task_run_id: str,
    *,
    supervisor: RunSupervisor = default_run_supervisor,
) -> bool:
    return await supervisor.interrupt(task_run_id)
