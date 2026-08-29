import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from sqlalchemy import func, insert, literal, true, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session as DbSession
from sqlmodel import select

from app.events import (
    append_task_run_event,
    publish_task_run_event,
    stage_task_run_event,
)
from app.models import TargetLock, Task, TaskRun, TaskRunEvent, new_id, utc_now
from app.session_queue import (
    stage_task_run_terminal,
    target_lock_key_for_target,
)

LOCK_HELD = "held"
LOCK_RELEASED = "released"
LOCK_STALE_RELEASED = "stale_released"
LOCK_LEASE_SECONDS = 300
TERMINAL_TASK_RUN_STATES = {"completed", "failed", "interrupted", "cancelled"}


@dataclass(frozen=True)
class TargetLockAcquireResult:
    acquired: bool
    lock: Optional[TargetLock] = field(repr=False)
    holder_task_run_id: Optional[str]
    reason: str


@dataclass(frozen=True)
class RecoveredTargetLock:
    id: str = field(repr=False)
    lock_key: str
    target_id: str
    session_id: Optional[str]
    task_run_id: Optional[str]
    worker_id: Optional[str]
    mode: str
    state: str
    lease_expires_at: Optional[datetime]
    acquired_at: Optional[datetime]
    released_at: datetime
    release_reason: str


@dataclass(frozen=True)
class _TargetLockGeneration:
    id: str = field(repr=False)
    lock_key: str
    target_id: str
    session_id: Optional[str]
    task_run_id: Optional[str]
    worker_id: Optional[str]
    mode: str
    state: str
    lease_expires_at: Optional[datetime]
    acquired_at: Optional[datetime]


def acquire_target_lock(
    db: DbSession,
    *,
    target_id: str,
    session_id: str,
    task_run_id: str,
    worker_id: str,
    lease_expires_at: Optional[datetime],
) -> TargetLockAcquireResult:
    lock_key = target_lock_key_for_target(target_id)
    if lock_key is None:
        return TargetLockAcquireResult(False, None, None, "Target id is required.")

    now = utc_now()
    expires_at = lease_expires_at
    if expires_at is not None and expires_at <= now:
        return TargetLockAcquireResult(
            False,
            None,
            None,
            "Target write lock lease is expired.",
        )

    next_lock_id = new_id()
    released_result = db.execute(
        update(TargetLock)
        .where(TargetLock.lock_key == lock_key)
        .where(TargetLock.state != LOCK_HELD)
        .where(_lease_is_current_at_database(expires_at))
        .values(
            id=next_lock_id,
            target_id=target_id,
            session_id=session_id,
            task_run_id=task_run_id,
            worker_id=worker_id,
            mode="write",
            state=LOCK_HELD,
            lease_expires_at=expires_at,
            acquired_at=now,
            released_at=None,
            release_reason=None,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    if released_result.rowcount == 1:
        lock = _commit_acquired_target_lock(
            db,
            lock_id=next_lock_id,
            target_id=target_id,
            session_id=session_id,
            task_run_id=task_run_id,
            worker_id=worker_id,
        )
        if lock is not None:
            return TargetLockAcquireResult(
                True,
                lock,
                task_run_id,
                "Target write lock acquired.",
            )
    else:
        lock = lock_for_key(db, lock_key)

    if lock is None:
        insert_values = {
            "id": next_lock_id,
            "lock_key": lock_key,
            "target_id": target_id,
            "session_id": session_id,
            "task_run_id": task_run_id,
            "worker_id": worker_id,
            "mode": "write",
            "state": LOCK_HELD,
            "lease_expires_at": expires_at,
            "acquired_at": now,
            "released_at": None,
            "release_reason": None,
            "created_at": now,
            "updated_at": now,
        }
        try:
            inserted_result = db.execute(
                insert(TargetLock).from_select(
                    list(insert_values),
                    select(
                        *(literal(value) for value in insert_values.values())
                    ).where(_lease_is_current_at_database(expires_at)),
                )
            )
            if inserted_result.rowcount == 1:
                lock = _commit_acquired_target_lock(
                    db,
                    lock_id=next_lock_id,
                    target_id=target_id,
                    session_id=session_id,
                    task_run_id=task_run_id,
                    worker_id=worker_id,
                )
                if lock is not None:
                    return TargetLockAcquireResult(
                        True,
                        lock,
                        task_run_id,
                        "Target write lock acquired.",
                    )
            else:
                db.rollback()
                lock = lock_for_key(db, lock_key)
        except IntegrityError:
            db.rollback()
            lock = lock_for_key(db, lock_key)

    if _lock_matches_holder(
        lock,
        target_id=target_id,
        session_id=session_id,
        task_run_id=task_run_id,
        worker_id=worker_id,
    ):
        if _lock_lease_is_current(lock, utc_now()):
            _append_lock_event(db, lock, "target_lock.acquired", "acquired")
            return TargetLockAcquireResult(
                True,
                lock,
                task_run_id,
                "Target write lock acquired.",
            )

    holder_id = lock.task_run_id if lock is not None else None
    if lock is not None:
        _append_lock_event(
            db,
            lock,
            "target_lock.acquire_failed",
            "waiting_lock",
            waiting_task_run_id=task_run_id,
            waiting_session_id=session_id,
        )
    return TargetLockAcquireResult(
        False,
        lock,
        holder_id,
        f"Waiting for target write lock: {target_id}.",
    )


def _commit_acquired_target_lock(
    db: DbSession,
    *,
    lock_id: str,
    target_id: str,
    session_id: str,
    task_run_id: str,
    worker_id: str,
) -> Optional[TargetLock]:
    lock = db.get(TargetLock, lock_id)
    if not _lock_matches_holder(
        lock,
        target_id=target_id,
        session_id=session_id,
        task_run_id=task_run_id,
        worker_id=worker_id,
    ):
        db.rollback()
        return None
    try:
        event = _stage_lock_event(
            db,
            lock,
            "target_lock.acquired",
            "acquired",
        )
        db.expunge(lock)
        db.commit()
    except Exception:
        db.rollback()
        raise
    _publish_staged_lock_event(db, event)
    return lock


def release_target_lock_for_task_run(
    db: DbSession,
    *,
    target_id: str,
    expected_lock_id: str,
    worker_id: str,
    task_run_id: str,
    session_id: str,
    release_reason: str,
    stale: bool = False,
) -> Optional[RecoveredTargetLock]:
    lock_key = target_lock_key_for_target(target_id)
    if lock_key is None:
        return None
    now = utc_now()
    try:
        result = db.execute(
            update(TargetLock)
            .where(TargetLock.id == expected_lock_id)
            .where(TargetLock.lock_key == lock_key)
            .where(TargetLock.target_id == target_id)
            .where(TargetLock.session_id == session_id)
            .where(TargetLock.task_run_id == task_run_id)
            .where(TargetLock.worker_id == worker_id)
            .where(TargetLock.mode == "write")
            .where(TargetLock.state == LOCK_HELD)
            .values(
                state=LOCK_STALE_RELEASED if stale else LOCK_RELEASED,
                released_at=now,
                release_reason=release_reason,
                worker_id=None,
                lease_expires_at=None,
                updated_at=now,
            )
            .returning(
                TargetLock.id,
                TargetLock.lock_key,
                TargetLock.target_id,
                TargetLock.session_id,
                TargetLock.task_run_id,
                TargetLock.mode,
                TargetLock.state,
                TargetLock.acquired_at,
                TargetLock.released_at,
                TargetLock.release_reason,
            )
            .execution_options(synchronize_session=False)
        )
        row = result.mappings().one_or_none()
        if row is None:
            db.rollback()
            return None
        released = RecoveredTargetLock(
            id=row["id"],
            lock_key=row["lock_key"],
            target_id=row["target_id"],
            session_id=row["session_id"],
            task_run_id=row["task_run_id"],
            worker_id=None,
            mode=row["mode"],
            state=row["state"],
            lease_expires_at=None,
            acquired_at=row["acquired_at"],
            released_at=row["released_at"],
            release_reason=row["release_reason"],
        )
        event = _stage_lock_event(
            db,
            released,
            "target_lock.stale_released" if stale else "target_lock.released",
            release_reason,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    _publish_staged_lock_event(db, event)
    return released


def _publish_staged_lock_event(
    db: DbSession,
    event: Optional[TaskRunEvent],
) -> None:
    if event is None:
        return None
    try:
        db.refresh(event)
        publish_task_run_event(db, event)
    except Exception:
        db.rollback()


def held_lock_for_target(db: DbSession, target_id: str) -> Optional[TargetLock]:
    lock_key = target_lock_key_for_target(target_id)
    if lock_key is None:
        return None
    lock = lock_for_key(db, lock_key)
    if (
        lock is None
        or lock.state != LOCK_HELD
        or not _lock_lease_is_current(lock, utc_now())
    ):
        return None
    return lock


def lock_for_key(db: DbSession, lock_key: str) -> Optional[TargetLock]:
    return db.exec(
        select(TargetLock)
        .where(TargetLock.lock_key == lock_key)
        .execution_options(populate_existing=True)
    ).first()


def _lock_matches_holder(
    lock: Optional[TargetLock],
    *,
    target_id: str,
    session_id: str,
    task_run_id: str,
    worker_id: str,
) -> bool:
    return (
        lock is not None
        and lock.target_id == target_id
        and lock.session_id == session_id
        and lock.task_run_id == task_run_id
        and lock.worker_id == worker_id
        and lock.mode == "write"
        and lock.state == LOCK_HELD
    )


def _lock_lease_is_current(lock: TargetLock, now: datetime) -> bool:
    return lock.lease_expires_at is None or lock.lease_expires_at > now


def _lease_is_current_at_database(lease_expires_at: Optional[datetime]):
    if lease_expires_at is None:
        return true()
    return func.julianday(literal(lease_expires_at)) > func.julianday("now")


def recover_stale_target_locks(
    db: DbSession,
    *,
    now: Optional[datetime] = None,
) -> list[RecoveredTargetLock]:
    timestamp = now or utc_now()
    recovered: list[RecoveredTargetLock] = []
    locks = tuple(
        _freeze_lock_generation(lock)
        for lock in db.exec(
            select(TargetLock)
            .where(TargetLock.state == LOCK_HELD)
            .order_by(TargetLock.acquired_at, TargetLock.id)
        ).all()
    )
    for lock in locks:
        if lock.task_run_id is None or lock.session_id is None:
            continue
        if not _lock_generation_is_current(db, lock):
            continue
        if not _begin_immediate_generation_recovery(db, lock):
            continue
        task_run = db.get(TaskRun, lock.task_run_id)
        if task_run is None:
            released = _commit_recovered_generation(
                db,
                lock,
                release_reason="missing_holder",
                stale=True,
                released_at=timestamp,
            )
            if released is not None:
                recovered.append(released)
            continue
        if task_run.state in {"completed", "failed", "interrupted", "cancelled"}:
            task_run_state = task_run.state
            released = _commit_recovered_generation(
                db,
                lock,
                release_reason="terminal_holder",
                stale=True,
                released_at=timestamp,
                queue_terminal_state=task_run_state,
                queue_reason="Recovered terminal TaskRun lock holder.",
            )
            if released is not None:
                recovered.append(released)
            continue
        if (
            lock.lease_expires_at is not None
            and lock.lease_expires_at <= timestamp
        ):
            if _matching_holder_heartbeat_is_current(task_run, lock, timestamp):
                db.rollback()
                continue
            task_run_id = task_run.id
            task_run_task_id = task_run.task_id
            task = db.get(Task, task_run_task_id)
            scope_error_code = None
            scope_failure_payload = None
            if task_run.state == "collecting_diff" and lock.mode == "write":
                from app.task_runs import (
                    _scope_failure_event_payload,
                    _stale_collecting_diff_scope_error_code,
                )

                if task is None:
                    scope_error_code = "TASK_RUN_SCOPE_UNVERIFIABLE"
                else:
                    from app.scheduler import write_lock_required_for_task

                    scope_error_code = (
                        _stale_collecting_diff_scope_error_code(
                            db,
                            task,
                            task_run,
                            previous_state=task_run.state,
                        )
                        if write_lock_required_for_task(task)
                        else "TASK_RUN_SCOPE_UNVERIFIABLE"
                    )
                if scope_error_code is not None:
                    scope_failure_payload = _scope_failure_event_payload(
                        task_run,
                        scope_error_code,
                    )
                    scope_failure_payload["reasonCategory"] = "crash_recovery"
            stale_error_code = scope_error_code or "TASK_RUN_STALE"
            stale_error_message = (
                "The task run changed paths outside the assigned target."
                if stale_error_code == "TASK_RUN_SCOPE_VIOLATION"
                else (
                    "The task run scope evidence is unavailable or invalid after "
                    "recovery."
                    if stale_error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
                    else (
                        "Target lock lease expired before provider result could be "
                        "confirmed."
                    )
                )
            )
            if task is not None:
                task.status = "failed"
                task.updated_at = timestamp
                db.add(task)
            task_run.state = "failed"
            task_run.error_code = stale_error_code
            task_run.error_message = stale_error_message
            task_run.stale_detected_at = timestamp
            task_run.stale_reason = "target_lock_lease_expired"
            task_run.ended_at = timestamp
            task_run.updated_at = timestamp
            db.add(task_run)
            try:
                staged_recovery = _stage_recovered_generation(
                    db,
                    lock,
                    release_reason="stale_lease_expired",
                    stale=True,
                    released_at=timestamp,
                )
                if staged_recovery is None:
                    continue
                released, lock_event = staged_recovery
                scope_event = (
                    stage_task_run_event(
                        db,
                        task_run_id=task_run_id,
                        event_type="task.scope_validation.failed",
                        payload_json=json.dumps(
                            scope_failure_payload,
                            separators=(",", ":"),
                        ),
                    )
                    if scope_failure_payload is not None
                    else None
                )
                stale_event = stage_task_run_event(
                    db,
                    task_run_id=task_run_id,
                    event_type="task.stale",
                    payload_json=json.dumps(
                        {
                            "reason": "target_lock_lease_expired",
                            "errorCode": stale_error_code,
                            "errorMessage": stale_error_message,
                            "lockKey": lock.lock_key,
                        },
                        separators=(",", ":"),
                    ),
                )
                queue_event = stage_task_run_terminal(
                    db,
                    task_run_id,
                    "failed",
                    reason="Recovered stale target lock holder as failed.",
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
            for event in (lock_event, scope_event, stale_event, queue_event):
                _publish_staged_lock_event(db, event)
            recovered.append(released)
            continue
        db.rollback()
    return recovered


def _matching_holder_heartbeat_is_current(
    task_run: TaskRun,
    expected: _TargetLockGeneration,
    timestamp: datetime,
) -> bool:
    return (
        expected.worker_id is not None
        and task_run.runner_id == expected.worker_id
        and task_run.last_heartbeat_at is not None
        and task_run.lease_expires_at is not None
        and task_run.lease_expires_at > timestamp
    )


def recover_terminal_holder_target_locks(
    db: DbSession,
) -> list[RecoveredTargetLock]:
    recovered: list[RecoveredTargetLock] = []
    locks = tuple(
        _freeze_lock_generation(lock)
        for lock in db.exec(
            select(TargetLock)
            .where(TargetLock.state == LOCK_HELD)
            .order_by(TargetLock.acquired_at, TargetLock.id)
        ).all()
    )
    for lock in locks:
        if lock.task_run_id is None:
            continue
        if not _lock_generation_is_current(db, lock):
            continue
        if not _begin_immediate_generation_recovery(db, lock):
            continue
        task_run = db.get(TaskRun, lock.task_run_id)
        if task_run is None or task_run.state not in TERMINAL_TASK_RUN_STATES:
            db.rollback()
            continue
        task_run_state = task_run.state
        released = _commit_recovered_generation(
            db,
            lock,
            release_reason="terminal_holder",
            stale=True,
            released_at=utc_now(),
            queue_terminal_state=task_run_state,
            queue_reason="Recovered terminal TaskRun lock holder.",
        )
        if released is not None:
            recovered.append(released)
    return recovered


def lock_diagnostics_for_task_run(db: DbSession, task_run_id: str) -> Optional[dict]:
    lock = db.exec(select(TargetLock).where(TargetLock.task_run_id == task_run_id)).first()
    if lock is None:
        return None
    return _lock_payload(lock)


def _freeze_lock_generation(lock: TargetLock) -> _TargetLockGeneration:
    return _TargetLockGeneration(
        id=lock.id,
        lock_key=lock.lock_key,
        target_id=lock.target_id,
        session_id=lock.session_id,
        task_run_id=lock.task_run_id,
        worker_id=lock.worker_id,
        mode=lock.mode,
        state=lock.state,
        lease_expires_at=lock.lease_expires_at,
        acquired_at=lock.acquired_at,
    )


def _lock_generation_is_current(
    db: DbSession,
    expected: _TargetLockGeneration,
) -> bool:
    current_lock = lock_for_key(db, expected.lock_key)
    if current_lock is None:
        return False
    return _lock_matches_generation(current_lock, expected)


def _lock_matches_generation(
    current_lock: TargetLock,
    expected: _TargetLockGeneration,
) -> bool:
    current = _freeze_lock_generation(current_lock)
    return (
        current.id == expected.id
        and current.lock_key == expected.lock_key
        and current.target_id == expected.target_id
        and current.session_id == expected.session_id
        and current.task_run_id == expected.task_run_id
        and current.worker_id == expected.worker_id
        and current.mode == expected.mode == "write"
        and current.state == expected.state == LOCK_HELD
        and current.lease_expires_at == expected.lease_expires_at
        and current.acquired_at == expected.acquired_at
    )


def _begin_immediate_generation_recovery(
    db: DbSession,
    expected: _TargetLockGeneration,
) -> bool:
    db.rollback()
    try:
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        current_lock = lock_for_key(db, expected.lock_key)
    except Exception:
        db.rollback()
        raise
    if current_lock is None or not _lock_matches_generation(current_lock, expected):
        db.rollback()
        return False
    return True


def _commit_recovered_generation(
    db: DbSession,
    expected: _TargetLockGeneration,
    *,
    release_reason: str,
    stale: bool,
    released_at: datetime,
    queue_terminal_state: Optional[str] = None,
    queue_reason: Optional[str] = None,
) -> Optional[RecoveredTargetLock]:
    try:
        staged_recovery = _stage_recovered_generation(
            db,
            expected,
            release_reason=release_reason,
            stale=stale,
            released_at=released_at,
        )
        if staged_recovery is None:
            return None
        released, event = staged_recovery
        queue_event = (
            stage_task_run_terminal(
                db,
                expected.task_run_id,
                queue_terminal_state,
                reason=queue_reason,
            )
            if expected.task_run_id is not None
            and queue_terminal_state is not None
            else None
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    for staged_event in (event, queue_event):
        _publish_staged_lock_event(db, staged_event)
    return released


def _stage_recovered_generation(
    db: DbSession,
    expected: _TargetLockGeneration,
    *,
    release_reason: str,
    stale: bool,
    released_at: datetime,
) -> Optional[tuple[RecoveredTargetLock, Optional[TaskRunEvent]]]:
    released = RecoveredTargetLock(
        id=expected.id,
        lock_key=expected.lock_key,
        target_id=expected.target_id,
        session_id=expected.session_id,
        task_run_id=expected.task_run_id,
        worker_id=None,
        mode=expected.mode,
        state=LOCK_STALE_RELEASED if stale else LOCK_RELEASED,
        lease_expires_at=None,
        acquired_at=expected.acquired_at,
        released_at=released_at,
        release_reason=release_reason,
    )
    result = db.execute(
        update(TargetLock)
        .where(TargetLock.id == expected.id)
        .where(TargetLock.lock_key == expected.lock_key)
        .where(TargetLock.target_id == expected.target_id)
        .where(TargetLock.session_id == expected.session_id)
        .where(TargetLock.task_run_id == expected.task_run_id)
        .where(TargetLock.worker_id == expected.worker_id)
        .where(TargetLock.mode == "write")
        .where(TargetLock.state == LOCK_HELD)
        .where(TargetLock.lease_expires_at == expected.lease_expires_at)
        .where(TargetLock.acquired_at == expected.acquired_at)
        .values(
            state=LOCK_STALE_RELEASED if stale else LOCK_RELEASED,
            released_at=released_at,
            release_reason=release_reason,
            worker_id=None,
            lease_expires_at=None,
            updated_at=released_at,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        return None
    event = _stage_lock_event(
        db,
        released,
        "target_lock.stale_released" if stale else "target_lock.released",
        release_reason,
    )
    return released, event


def _append_lock_event(
    db: DbSession,
    lock: TargetLock | RecoveredTargetLock,
    event_type: str,
    reason: str,
    *,
    waiting_task_run_id: Optional[str] = None,
    waiting_session_id: Optional[str] = None,
) -> None:
    task_run_id = waiting_task_run_id or lock.task_run_id
    if task_run_id is None:
        return
    payload = _lock_payload(lock)
    payload["reason"] = reason
    if waiting_task_run_id is not None:
        payload["waitingTaskRunId"] = waiting_task_run_id
        payload["waitingSessionId"] = waiting_session_id
    append_task_run_event(
        db,
        task_run_id=task_run_id,
        event_type=event_type,
        payload_json=json.dumps(payload, separators=(",", ":")),
    )


def _stage_lock_event(
    db: DbSession,
    lock: TargetLock | RecoveredTargetLock,
    event_type: str,
    reason: str,
    *,
    waiting_task_run_id: Optional[str] = None,
    waiting_session_id: Optional[str] = None,
) -> Optional[TaskRunEvent]:
    task_run_id = waiting_task_run_id or lock.task_run_id
    if task_run_id is None:
        return None
    payload = _lock_payload(lock)
    payload["reason"] = reason
    if waiting_task_run_id is not None:
        payload["waitingTaskRunId"] = waiting_task_run_id
        payload["waitingSessionId"] = waiting_session_id
    return stage_task_run_event(
        db,
        task_run_id=task_run_id,
        event_type=event_type,
        payload_json=json.dumps(payload, separators=(",", ":")),
    )


def _lock_payload(lock: TargetLock | RecoveredTargetLock) -> dict:
    return {
        "lockKey": lock.lock_key,
        "targetId": lock.target_id,
        "sessionId": lock.session_id,
        "holderTaskRunId": lock.task_run_id,
        "workerId": lock.worker_id,
        "mode": lock.mode,
        "state": lock.state,
        "leaseExpiresAt": lock.lease_expires_at.isoformat()
        if lock.lease_expires_at
        else None,
        "acquiredAt": lock.acquired_at.isoformat() if lock.acquired_at else None,
        "releasedAt": lock.released_at.isoformat() if lock.released_at else None,
        "releaseReason": lock.release_reason,
    }
