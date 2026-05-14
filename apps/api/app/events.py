import asyncio
import json
from collections import defaultdict
from typing import AsyncIterator, DefaultDict, Optional

from sqlmodel import Session as DbSession
from sqlmodel import func, select

from app.models import Task, TaskRun, TaskRunEvent

_session_subscribers: DefaultDict[str, list[asyncio.Queue[TaskRunEvent]]] = defaultdict(list)


def append_task_run_event(
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
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    session_id = session_id_for_task_run(db, task_run_id)
    if session_id is not None:
        publish_event(session_id, event)

    return event


def list_session_events(
    db: DbSession,
    session_id: str,
    after_sequence: int = 0,
) -> list[TaskRunEvent]:
    return db.exec(
        select(TaskRunEvent)
        .join(TaskRun)
        .join(Task)
        .where(Task.session_id == session_id)
        .where(TaskRunEvent.sequence > after_sequence)
        .order_by(TaskRunEvent.sequence, TaskRunEvent.created_at)
    ).all()


def session_id_for_task_run(db: DbSession, task_run_id: str) -> Optional[str]:
    return db.exec(
        select(Task.session_id)
        .join(TaskRun)
        .where(TaskRun.id == task_run_id)
    ).first()


def publish_event(session_id: str, event: TaskRunEvent) -> None:
    for queue in list(_session_subscribers[session_id]):
        queue.put_nowait(event)


def encode_sse_event(event: TaskRunEvent) -> str:
    payload = {
        "id": event.id,
        "taskRunId": event.task_run_id,
        "eventType": event.event_type,
        "payload": json.loads(event.payload_json),
        "sequence": event.sequence,
        "createdAt": event.created_at.isoformat(),
    }
    return (
        f"id: {event.sequence}\n"
        f"event: {event.event_type}\n"
        f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"
    )


async def subscribe_session_events(session_id: str) -> AsyncIterator[TaskRunEvent]:
    queue: asyncio.Queue[TaskRunEvent] = asyncio.Queue()
    _session_subscribers[session_id].append(queue)
    try:
        while True:
            yield await queue.get()
    finally:
        _session_subscribers[session_id].remove(queue)
