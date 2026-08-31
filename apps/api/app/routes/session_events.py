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
    list_session_events,
    parse_session_cursor,
    subscribe_session_events,
)
from app.repositories import get_session


router = APIRouter()

SESSION_EVENT_POLL_INTERVAL_SECONDS = 1.0
SESSION_EVENT_HEARTBEAT_INTERVAL_SECONDS = 15.0
SESSION_EVENT_HEARTBEAT_FRAME = ": keep-alive\n\n"


def session_event_poll_interval_seconds() -> float:
    return SESSION_EVENT_POLL_INTERVAL_SECONDS


def session_event_heartbeat_interval_seconds() -> float:
    return SESSION_EVENT_HEARTBEAT_INTERVAL_SECONDS


def session_event_heartbeat_frame() -> str:
    return SESSION_EVENT_HEARTBEAT_FRAME


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

    def persisted_events_after(cursor: str | None):
        # Use a fresh read transaction for every replay. The request-scoped
        # Session can otherwise keep an older SQLite snapshot for the lifetime
        # of the streaming response.
        with DbSession(db.get_bind()) as replay_db:
            return list_session_events(
                replay_db,
                session_id=session_id,
                after=cursor,
            )

    async def event_generator() -> AsyncIterator[str]:
        last_emitted_cursor = resume_after
        loop = asyncio.get_running_loop()
        last_output_at = loop.time()
        if not stream:
            for event in persisted_events_after(resume_after):
                if event_is_after_session_cursor(event, last_emitted_cursor):
                    yield encode_sse_event(event)
                    last_emitted_cursor = format_session_cursor(event)
            return

        async with subscribe_session_events(session_id) as queue:
            for event in persisted_events_after(resume_after):
                if event_is_after_session_cursor(event, last_emitted_cursor):
                    yield encode_sse_event(event)
                    last_emitted_cursor = format_session_cursor(event)
                    last_output_at = loop.time()

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
                for event in persisted_events_after(last_emitted_cursor):
                    if event_is_after_session_cursor(event, last_emitted_cursor):
                        yield encode_sse_event(event)
                        last_emitted_cursor = format_session_cursor(event)
                        last_output_at = loop.time()
                        emitted_event = True

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
