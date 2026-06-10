import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session as DbSession
from sqlmodel import select

from app.events import append_task_run_event
from app.models import TargetLock, Task, TaskRun, utc_now
from app.session_queue import mark_task_run_terminal, target_lock_key_for_target

LOCK_HELD = "held"
LOCK_RELEASED = "released"
LOCK_STALE_RELEASED = "stale_released"
LOCK_LEASE_SECONDS = 300
TERMINAL_TASK_RUN_STATES = {"completed", "failed", "interrupted", "cancelled"}


@dataclass(frozen=True)
class TargetLockAcquireResult:
    acquired: bool
    lock: Optional[TargetLock]
    holder_task_run_id: Optional[str]
    reason: str


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
    db.execute(
        update(TargetLock)
        .where(TargetLock.lock_key == lock_key)
        .where(TargetLock.state != LOCK_HELD)
        .values(
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
    )
    db.commit()
    lock = lock_for_key(db, lock_key)
    if lock is not None and lock.state == LOCK_HELD and lock.task_run_id == task_run_id:
        _append_lock_event(db, lock, "target_lock.acquired", "acquired")
        return TargetLockAcquireResult(True, lock, task_run_id, "Target write lock acquired.")

    if lock is None:
        lock = TargetLock(
            lock_key=lock_key,
            target_id=target_id,
            session_id=session_id,
            task_run_id=task_run_id,
            worker_id=worker_id,
            mode="write",
            state=LOCK_HELD,
            lease_expires_at=expires_at,
            acquired_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(lock)
        try:
            db.commit()
            db.refresh(lock)
            _append_lock_event(db, lock, "target_lock.acquired", "acquired")
            return TargetLockAcquireResult(
                True,
                lock,
                task_run_id,
                "Target write lock acquired.",
            )
        except IntegrityError:
            db.rollback()
            lock = lock_for_key(db, lock_key)

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


def release_target_lock_for_task_run(
    db: DbSession,
    *,
    task_run_id: str,
    session_id: str,
    release_reason: str,
    stale: bool = False,
) -> Optional[TargetLock]:
    lock = db.exec(
        select(TargetLock)
        .where(TargetLock.task_run_id == task_run_id)
        .where(TargetLock.session_id == session_id)
        .where(TargetLock.state == LOCK_HELD)
    ).first()
    if lock is None:
        return None
    now = utc_now()
    lock.state = LOCK_STALE_RELEASED if stale else LOCK_RELEASED
    lock.released_at = now
    lock.release_reason = release_reason
    lock.worker_id = None
    lock.lease_expires_at = None
    lock.updated_at = now
    db.add(lock)
    db.commit()
    db.refresh(lock)
    _append_lock_event(
        db,
        lock,
        "target_lock.stale_released" if stale else "target_lock.released",
        release_reason,
    )
    return lock


def held_lock_for_target(db: DbSession, target_id: str) -> Optional[TargetLock]:
    lock_key = target_lock_key_for_target(target_id)
    if lock_key is None:
        return None
    lock = lock_for_key(db, lock_key)
    if lock is None or lock.state != LOCK_HELD:
        return None
    return lock


def lock_for_key(db: DbSession, lock_key: str) -> Optional[TargetLock]:
    return db.exec(select(TargetLock).where(TargetLock.lock_key == lock_key)).first()


def recover_stale_target_locks(db: DbSession, *, now: Optional[datetime] = None) -> list[TargetLock]:
    timestamp = now or utc_now()
    recovered: list[TargetLock] = []
    locks = db.exec(
        select(TargetLock)
        .where(TargetLock.state == LOCK_HELD)
        .order_by(TargetLock.acquired_at, TargetLock.id)
    ).all()
    for lock in locks:
        if lock.task_run_id is None or lock.session_id is None:
            continue
        task_run = db.get(TaskRun, lock.task_run_id)
        if task_run is None:
            released = _release_lock(
                db,
                lock,
                release_reason="missing_holder",
                stale=True,
            )
            recovered.append(released)
            continue
        if task_run.state in {"completed", "failed", "interrupted", "cancelled"}:
            released = _release_lock(
                db,
                lock,
                release_reason="terminal_holder",
                stale=True,
            )
            recovered.append(released)
            continue
        if lock.lease_expires_at is not None and lock.lease_expires_at < timestamp:
            task = db.get(Task, task_run.task_id)
            if task is not None:
                task.status = "failed"
                task.updated_at = timestamp
                db.add(task)
            task_run.state = "failed"
            task_run.error_code = "TASK_RUN_STALE"
            task_run.error_message = (
                "Target lock lease expired before provider result could be confirmed."
            )
            task_run.stale_detected_at = timestamp
            task_run.stale_reason = "target_lock_lease_expired"
            task_run.ended_at = timestamp
            task_run.updated_at = timestamp
            db.add(task_run)
            db.commit()
            db.refresh(task_run)
            append_task_run_event(
                db,
                task_run_id=task_run.id,
                event_type="task.stale",
                payload_json=json.dumps(
                    {
                        "reason": "target_lock_lease_expired",
                        "errorCode": task_run.error_code,
                        "errorMessage": task_run.error_message,
                        "lockKey": lock.lock_key,
                    },
                    separators=(",", ":"),
                ),
            )
            mark_task_run_terminal(
                db,
                task_run.id,
                "failed",
                reason="Recovered stale target lock holder as failed.",
            )
            released = _release_lock(
                db,
                lock,
                release_reason="stale_lease_expired",
                stale=True,
            )
            recovered.append(released)
    return recovered


def recover_terminal_holder_target_locks(db: DbSession) -> list[TargetLock]:
    recovered: list[TargetLock] = []
    locks = db.exec(
        select(TargetLock)
        .where(TargetLock.state == LOCK_HELD)
        .order_by(TargetLock.acquired_at, TargetLock.id)
    ).all()
    for lock in locks:
        if lock.task_run_id is None:
            continue
        task_run = db.get(TaskRun, lock.task_run_id)
        if task_run is None or task_run.state not in TERMINAL_TASK_RUN_STATES:
            continue
        mark_task_run_terminal(
            db,
            task_run.id,
            task_run.state,
            reason="Recovered terminal TaskRun lock holder.",
        )
        refreshed_lock = lock_for_key(db, lock.lock_key)
        if refreshed_lock is None or refreshed_lock.state != LOCK_HELD:
            continue
        released = _release_lock(
            db,
            refreshed_lock,
            release_reason="terminal_holder",
            stale=True,
        )
        recovered.append(released)
    return recovered


def lock_diagnostics_for_task_run(db: DbSession, task_run_id: str) -> Optional[dict]:
    lock = db.exec(select(TargetLock).where(TargetLock.task_run_id == task_run_id)).first()
    if lock is None:
        return None
    return _lock_payload(lock)


def _release_lock(
    db: DbSession,
    lock: TargetLock,
    *,
    release_reason: str,
    stale: bool,
) -> TargetLock:
    now = utc_now()
    lock.state = LOCK_STALE_RELEASED if stale else LOCK_RELEASED
    lock.released_at = now
    lock.release_reason = release_reason
    lock.worker_id = None
    lock.lease_expires_at = None
    lock.updated_at = now
    db.add(lock)
    db.commit()
    db.refresh(lock)
    _append_lock_event(
        db,
        lock,
        "target_lock.stale_released" if stale else "target_lock.released",
        release_reason,
    )
    return lock


def _append_lock_event(
    db: DbSession,
    lock: TargetLock,
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


def _lock_payload(lock: TargetLock) -> dict:
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
