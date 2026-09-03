import asyncio
import json
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import AsyncIterator, DefaultDict, Optional
from uuid import UUID

from sqlalchemy import and_, or_
from sqlmodel import Session as DbSession
from sqlmodel import func, select

from app.models import Task, TaskRun, TaskRunEvent


class SessionEventWakeup:
    """Coalesce cross-thread notifications without retaining event payloads."""

    maxsize = 1

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._event = asyncio.Event()
        self._state_lock = Lock()
        self._pending = False

    def notify(self) -> None:
        with self._state_lock:
            if self._pending:
                return
            self._pending = True
        try:
            self._loop.call_soon_threadsafe(self._event.set)
        except RuntimeError:
            with self._state_lock:
                self._pending = False

    async def get(self) -> None:
        await self._event.wait()
        with self._state_lock:
            self._event.clear()
            self._pending = False

    def qsize(self) -> int:
        with self._state_lock:
            return int(self._pending)

    def empty(self) -> bool:
        return self.qsize() == 0


@dataclass(frozen=True)
class SessionEventSubscriber:
    queue: SessionEventWakeup


_session_subscribers: DefaultDict[str, list[SessionEventSubscriber]] = defaultdict(list)


def _naive_utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _next_persisted_event_created_at(
    db: DbSession,
    *,
    event_id: str,
) -> datetime:
    latest = db.exec(
        select(func.max(TaskRunEvent.created_at)).where(TaskRunEvent.id != event_id)
    ).one()
    candidate = _naive_utc_now()
    if latest is not None and candidate <= latest:
        return latest + timedelta(microseconds=1)
    return candidate


def format_session_cursor(event: TaskRunEvent) -> str:
    created_at = event.created_at
    event_id = str(UUID(event.id))
    if created_at.tzinfo is not None or event_id != event.id:
        raise ValueError("Session cursor must use a server-issued timestamp and event id")
    return f"{created_at.isoformat()}|{event_id}"


def parse_session_cursor(cursor: str) -> tuple[datetime, str]:
    if not isinstance(cursor, str):
        raise ValueError("Invalid session event cursor")

    timestamp, separator, event_id = cursor.partition("|")
    if not separator or "|" in event_id:
        raise ValueError("Invalid session event cursor")

    try:
        created_at = datetime.fromisoformat(timestamp)
        normalized_event_id = str(UUID(event_id))
    except ValueError as exc:
        raise ValueError("Invalid session event cursor") from exc

    if (
        created_at.tzinfo is not None
        or created_at.isoformat() != timestamp
        or normalized_event_id != event_id
    ):
        raise ValueError("Invalid session event cursor")
    return created_at, event_id


def append_task_run_event(
    db: DbSession,
    task_run_id: str,
    event_type: str,
    payload_json: str = "{}",
) -> TaskRunEvent:
    event = stage_task_run_event(
        db,
        task_run_id=task_run_id,
        event_type=event_type,
        payload_json=payload_json,
    )
    db.commit()
    db.refresh(event)
    publish_task_run_event(db, event)
    return event


def stage_task_run_event(
    db: DbSession,
    task_run_id: str,
    event_type: str,
    payload_json: str = "{}",
) -> TaskRunEvent:
    max_sequence = db.exec(
        select(func.max(TaskRunEvent.sequence)).where(
            TaskRunEvent.task_run_id == task_run_id
        )
    ).one()
    sequence = int(max_sequence or 0) + 1
    event = TaskRunEvent(
        task_run_id=task_run_id,
        event_type=event_type,
        payload_json=payload_json,
        sequence=sequence,
        created_at=_naive_utc_now(),
    )
    db.add(event)
    db.flush()
    # The first flush acquires SQLite's writer lock. Allocate the cursor timestamp
    # while that lock is held so later committed events cannot receive an older
    # cursor, even when their TaskRun-local sequence starts again at one.
    event.created_at = _next_persisted_event_created_at(db, event_id=event.id)
    db.add(event)
    db.flush()
    return event


def publish_task_run_event(db: DbSession, event: TaskRunEvent) -> None:
    task_run_id = event.task_run_id
    session_id = session_id_for_task_run(db, task_run_id)
    if session_id is not None:
        publish_event(session_id, event)


def list_session_events(
    db: DbSession,
    session_id: str,
    after: str | None = None,
    *,
    through: str | None = None,
    limit: int | None = None,
) -> list[TaskRunEvent]:
    statement = (
        select(TaskRunEvent)
        .join(TaskRun)
        .join(Task)
        .where(Task.session_id == session_id)
    )
    if after is not None:
        created_at, event_id = parse_session_cursor(after)
        statement = statement.where(
            or_(
                TaskRunEvent.created_at > created_at,
                and_(
                    TaskRunEvent.created_at == created_at,
                    TaskRunEvent.id > event_id,
                ),
            )
        )
    if through is not None:
        created_at, event_id = parse_session_cursor(through)
        statement = statement.where(
            or_(
                TaskRunEvent.created_at < created_at,
                and_(
                    TaskRunEvent.created_at == created_at,
                    TaskRunEvent.id <= event_id,
                ),
            )
        )
    statement = statement.order_by(TaskRunEvent.created_at, TaskRunEvent.id)
    if limit is not None:
        if limit < 1:
            raise ValueError("Session event replay limit must be positive")
        statement = statement.limit(limit)
    return db.exec(statement).all()


def latest_session_event_cursor(db: DbSession, session_id: str) -> str | None:
    event = db.exec(
        select(TaskRunEvent)
        .join(TaskRun)
        .join(Task)
        .where(Task.session_id == session_id)
        .order_by(TaskRunEvent.created_at.desc(), TaskRunEvent.id.desc())
        .limit(1)
    ).first()
    return format_session_cursor(event) if event is not None else None


def session_id_for_task_run(db: DbSession, task_run_id: str) -> Optional[str]:
    return db.exec(
        select(Task.session_id)
        .join(TaskRun)
        .where(TaskRun.id == task_run_id)
    ).first()


def publish_event(session_id: str, event: TaskRunEvent) -> None:
    for subscriber in list(_session_subscribers.get(session_id, ())):
        # The event itself is already durable. Keep only one payload-free wake
        # per subscriber; the stream replays every row from SQLite by cursor.
        subscriber.queue.notify()


def encode_sse_event(event: TaskRunEvent) -> str:
    cursor = format_session_cursor(event)
    payload = {
        "id": event.id,
        "taskRunId": event.task_run_id,
        "eventType": event.event_type,
        "payload": json.loads(event.payload_json),
        "sequence": event.sequence,
        "createdAt": event.created_at.isoformat(),
        "cursor": cursor,
    }
    return (
        f"id: {cursor}\n"
        f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"
    )


def event_is_after_session_cursor(event: TaskRunEvent, cursor: str | None) -> bool:
    if cursor is None:
        return True
    created_at, event_id = parse_session_cursor(cursor)
    return (event.created_at, event.id) > (created_at, event_id)


@asynccontextmanager
async def subscribe_session_events(
    session_id: str,
) -> AsyncIterator[SessionEventWakeup]:
    loop = asyncio.get_running_loop()
    queue = SessionEventWakeup(loop)
    subscriber = SessionEventSubscriber(queue=queue)
    _session_subscribers[session_id].append(subscriber)
    try:
        yield queue
    finally:
        _session_subscribers[session_id].remove(subscriber)
        if not _session_subscribers[session_id]:
            del _session_subscribers[session_id]
