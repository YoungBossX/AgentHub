import json
from dataclasses import dataclass
from typing import Optional

from sqlmodel import Session as DbSession
from sqlmodel import func, select

from app.events import append_task_run_event
from app.models import SessionQueueEntry, Task, TaskRun, utc_now

QUEUE_TERMINAL_STATES = {"completed", "failed", "interrupted", "cancelled"}
WRITE_ACCESS_MODE = "write"
READONLY_ACCESS_MODE = "readonly"


@dataclass(frozen=True)
class QueueGateDecision:
    runnable: bool
    state: str
    reason: str
    blocking_task_run_ids: list[str]


def target_lock_key_for_target(target_id: Optional[str]) -> Optional[str]:
    if not target_id:
        return None
    return f"target:{target_id}:write"


def enqueue_task_run(
    db: DbSession,
    *,
    task: Task,
    task_run: TaskRun,
    access_mode: str,
    target_id: Optional[str],
    initial_state: str = "queued",
    blocked_reason: Optional[str] = None,
) -> SessionQueueEntry:
    existing = entry_for_task_run(db, task_run.id)
    if existing is not None:
        return existing

    position = _next_position(db, task.session_id)
    now = utc_now()
    entry = SessionQueueEntry(
        session_id=task.session_id,
        task_id=task.id,
        task_run_id=task_run.id,
        access_mode=access_mode,
        target_id=target_id,
        target_lock_key=(
            target_lock_key_for_target(target_id)
            if access_mode == WRITE_ACCESS_MODE
            else None
        ),
        position=position,
        state=initial_state,
        blocked_reason=blocked_reason,
        created_at=now,
        updated_at=now,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    _append_queue_event(db, entry, "session_queue.enqueued")
    return entry


def entry_for_task_run(db: DbSession, task_run_id: str) -> Optional[SessionQueueEntry]:
    return db.exec(
        select(SessionQueueEntry).where(SessionQueueEntry.task_run_id == task_run_id)
    ).first()


def queue_gate_for_task_run(db: DbSession, task_run_id: str) -> QueueGateDecision:
    entry = entry_for_task_run(db, task_run_id)
    if entry is None:
        return QueueGateDecision(
            runnable=True,
            state="ready",
            reason="No persisted queue entry exists for this legacy TaskRun.",
            blocking_task_run_ids=[],
        )
    if entry.state in QUEUE_TERMINAL_STATES:
        return QueueGateDecision(
            runnable=False,
            state=entry.state,
            reason="Queue entry is terminal.",
            blocking_task_run_ids=[],
        )
    task_run = db.get(TaskRun, task_run_id)
    if task_run is None or task_run.state in QUEUE_TERMINAL_STATES:
        mark_task_run_terminal(db, task_run_id, task_run.state if task_run else "failed")
        return QueueGateDecision(
            runnable=False,
            state=task_run.state if task_run else "failed",
            reason="TaskRun is terminal and must not be restarted.",
            blocking_task_run_ids=[],
        )
    if entry.access_mode == READONLY_ACCESS_MODE:
        _mark_entry_state(
            db,
            entry,
            "ready",
            "Readonly queue entry is safe to run concurrently.",
        )
        return QueueGateDecision(
            runnable=True,
            state="ready",
            reason="Readonly queue entry is safe to run concurrently.",
            blocking_task_run_ids=[],
        )

    blocking = db.exec(
        select(SessionQueueEntry)
        .where(SessionQueueEntry.session_id == entry.session_id)
        .where(SessionQueueEntry.queue_kind == entry.queue_kind)
        .where(SessionQueueEntry.access_mode == WRITE_ACCESS_MODE)
        .where(SessionQueueEntry.position < entry.position)
        .where(SessionQueueEntry.state.notin_(QUEUE_TERMINAL_STATES))
        .order_by(SessionQueueEntry.position, SessionQueueEntry.id)
    ).all()
    blocking_run_ids = [item.task_run_id for item in blocking]
    if blocking_run_ids:
        _mark_entry_state(
            db,
            entry,
            "queued",
            "Waiting for earlier session write queue entry.",
        )
        return QueueGateDecision(
            runnable=False,
            state="queued",
            reason="Waiting for earlier session write queue entry.",
            blocking_task_run_ids=blocking_run_ids,
        )

    _mark_entry_state(
        db,
        entry,
        "ready",
        "Session write queue entry is at the head of the queue.",
    )
    return QueueGateDecision(
        runnable=True,
        state="ready",
        reason="Session write queue entry is at the head of the queue.",
        blocking_task_run_ids=[],
    )


def mark_task_run_running(db: DbSession, task_run_id: str, reason: str) -> None:
    entry = entry_for_task_run(db, task_run_id)
    if entry is None:
        return
    now = utc_now()
    entry.state = "running"
    entry.started_at = entry.started_at or now
    entry.blocked_reason = reason
    entry.updated_at = now
    db.add(entry)
    db.commit()
    db.refresh(entry)
    _append_queue_event(db, entry, "session_queue.running")


def mark_task_run_waiting_lock(
    db: DbSession,
    task_run_id: str,
    reason: str,
) -> None:
    entry = entry_for_task_run(db, task_run_id)
    if entry is None:
        return
    _mark_entry_state(db, entry, "waiting_lock", reason)


def mark_task_run_terminal(
    db: DbSession,
    task_run_id: str,
    terminal_state: str,
    reason: Optional[str] = None,
) -> None:
    entry = entry_for_task_run(db, task_run_id)
    if entry is None:
        return
    state = terminal_state if terminal_state in QUEUE_TERMINAL_STATES else "failed"
    now = utc_now()
    entry.state = state
    entry.finished_at = entry.finished_at or now
    entry.blocked_reason = reason or f"TaskRun entered terminal state: {state}."
    entry.updated_at = now
    db.add(entry)
    db.commit()
    db.refresh(entry)
    _append_queue_event(db, entry, "session_queue.advanced")


def queue_diagnostics_for_task_run(db: DbSession, task_run_id: str) -> Optional[dict]:
    entry = entry_for_task_run(db, task_run_id)
    if entry is None:
        return None
    return {
        "queueEntryId": entry.id,
        "queueKind": entry.queue_kind,
        "position": entry.position,
        "accessMode": entry.access_mode,
        "targetId": entry.target_id,
        "targetLockKey": entry.target_lock_key,
        "state": entry.state,
        "waitReason": entry.blocked_reason,
        "startedAt": entry.started_at.isoformat() if entry.started_at else None,
        "finishedAt": entry.finished_at.isoformat() if entry.finished_at else None,
    }


def recover_queue_entries(db: DbSession) -> list[SessionQueueEntry]:
    recovered: list[SessionQueueEntry] = []
    entries = db.exec(
        select(SessionQueueEntry)
        .where(SessionQueueEntry.state.in_({"queued", "ready", "waiting_lock", "running"}))
        .order_by(SessionQueueEntry.session_id, SessionQueueEntry.position, SessionQueueEntry.id)
    ).all()
    for entry in entries:
        task_run = db.get(TaskRun, entry.task_run_id)
        if task_run is not None and task_run.state in QUEUE_TERMINAL_STATES:
            mark_task_run_terminal(
                db,
                task_run.id,
                task_run.state,
                reason="Recovered terminal TaskRun queue entry.",
            )
            recovered.append(entry)
    return recovered


def _next_position(db: DbSession, session_id: str) -> int:
    max_position = db.exec(
        select(func.max(SessionQueueEntry.position)).where(
            SessionQueueEntry.session_id == session_id
        )
    ).one()
    return int(max_position or 0) + 1


def _mark_entry_state(
    db: DbSession,
    entry: SessionQueueEntry,
    state: str,
    reason: str,
) -> None:
    if entry.state == state and entry.blocked_reason == reason:
        return
    entry.state = state
    entry.blocked_reason = reason
    entry.updated_at = utc_now()
    db.add(entry)
    db.commit()
    db.refresh(entry)
    event_type = {
        "ready": "session_queue.ready",
        "waiting_lock": "session_queue.waiting_lock",
        "queued": "session_queue.queued",
    }.get(state, "session_queue.updated")
    _append_queue_event(db, entry, event_type)


def _append_queue_event(
    db: DbSession,
    entry: SessionQueueEntry,
    event_type: str,
) -> None:
    append_task_run_event(
        db,
        task_run_id=entry.task_run_id,
        event_type=event_type,
        payload_json=json.dumps(queue_diagnostics_for_task_run(db, entry.task_run_id), separators=(",", ":")),
    )
