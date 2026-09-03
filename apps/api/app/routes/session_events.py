import asyncio
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session as DbSession

from app.dependencies import get_db
from app.events import (
    encode_sse_event,
    event_is_after_session_cursor,
    format_session_cursor,
    latest_session_event_cursor,
    list_session_events,
    parse_session_cursor,
    subscribe_session_events,
)
from app.repositories import get_session


router = APIRouter()

SESSION_EVENT_POLL_INTERVAL_SECONDS = 1.0
SESSION_EVENT_HEARTBEAT_INTERVAL_SECONDS = 15.0
SESSION_EVENT_HEARTBEAT_FRAME = ": keep-alive\n\n"
SESSION_EVENT_REPLAY_BATCH_SIZE = 100


def session_event_poll_interval_seconds() -> float:
    return SESSION_EVENT_POLL_INTERVAL_SECONDS


def session_event_heartbeat_interval_seconds() -> float:
    return SESSION_EVENT_HEARTBEAT_INTERVAL_SECONDS


def session_event_heartbeat_frame() -> str:
    return SESSION_EVENT_HEARTBEAT_FRAME


def session_event_replay_batch_size() -> int:
    return SESSION_EVENT_REPLAY_BATCH_SIZE


@router.get("/sessions/{session_id}/events")
async def stream_session_events(
    session_id: str,
    after: str | None = Query(default=None),
    last_event_id: str | None = Header(default=None),
    stream: bool = False,
    db: DbSession = Depends(get_db),
) -> StreamingResponse:
    if get_session(db, session_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    resume_after = last_event_id if last_event_id else after
    if resume_after is not None:
        try:
            parse_session_cursor(resume_after)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    def persisted_events_after(
        cursor: str | None,
        *,
        through: str,
        limit: int,
    ):
        # Use a fresh read transaction for every replay. The request-scoped
        # Session can otherwise keep an older SQLite snapshot for the lifetime
        # of the streaming response.
        with DbSession(db.get_bind()) as replay_db:
            return list_session_events(
                replay_db,
                session_id=session_id,
                after=cursor,
                through=through,
                limit=limit,
            )

    def persisted_replay_high_water() -> str | None:
        with DbSession(db.get_bind()) as replay_db:
            return latest_session_event_cursor(replay_db, session_id)

    async def event_generator() -> AsyncIterator[str]:
        last_emitted_cursor = resume_after
        loop = asyncio.get_running_loop()
        last_output_at = loop.time()

        async def replay_persisted_events() -> AsyncIterator[str]:
            nonlocal last_emitted_cursor, last_output_at
            batch_size = session_event_replay_batch_size()
            high_water_cursor = persisted_replay_high_water()
            if high_water_cursor is None:
                return
            while True:
                batch_start_cursor = last_emitted_cursor
                events = persisted_events_after(
                    last_emitted_cursor,
                    through=high_water_cursor,
                    limit=batch_size,
                )
                if not events:
                    return
                for event in events:
                    if event_is_after_session_cursor(event, last_emitted_cursor):
                        yield encode_sse_event(event)
                        last_emitted_cursor = format_session_cursor(event)
                        last_output_at = loop.time()
                if (
                    len(events) < batch_size
                    or last_emitted_cursor == batch_start_cursor
                    or last_emitted_cursor == high_water_cursor
                ):
                    return

        if not stream:
            async for frame in replay_persisted_events():
                yield frame
            return

        async with subscribe_session_events(session_id) as queue:
            async for frame in replay_persisted_events():
                yield frame

            while True:
                # The queue is a low-latency same-process wake-up only. The
                # timeout also polls persisted evidence, so another API worker
                # or a lost notification cannot strand an open stream.
                try:
                    await asyncio.wait_for(
                        queue.get(),
                        timeout=session_event_poll_interval_seconds(),
                    )
                except asyncio.TimeoutError:
                    pass

                emitted_event = False
                cursor_before_replay = last_emitted_cursor
                async for frame in replay_persisted_events():
                    yield frame
                emitted_event = last_emitted_cursor != cursor_before_replay

                if (
                    not emitted_event
                    and loop.time() - last_output_at
                    >= session_event_heartbeat_interval_seconds()
                ):
                    yield session_event_heartbeat_frame()
                    last_output_at = loop.time()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )
