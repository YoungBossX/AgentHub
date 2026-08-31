import asyncio
import json
from datetime import datetime

import pytest

from app import events
from app.events import encode_sse_event
from app.models import TaskRunEvent

CREATED_AT = datetime(2026, 5, 17, 10, 0, 0)
EVENT_ID = "4be7f260-e023-4f92-9b8e-2dc8815c3e74"


def test_encode_sse_event_produces_valid_wire_format() -> None:
    event = TaskRunEvent(
        id=EVENT_ID,
        task_run_id="run-1",
        event_type="task.state",
        payload_json='{"state":"queued","adapterType":"codex"}',
        sequence=7,
    )
    event.created_at = CREATED_AT
    result = encode_sse_event(event)

    lines = result.splitlines()
    cursor = events.format_session_cursor(event)
    assert lines[0] == f"id: {cursor}"
    assert lines[1].startswith("data: ")
    assert lines[2] == ""
    assert not any(line.startswith("event: ") for line in lines)

    data = json.loads(lines[1].removeprefix("data: "))
    assert data["id"] == EVENT_ID
    assert data["taskRunId"] == "run-1"
    assert data["eventType"] == "task.state"
    assert data["payload"]["state"] == "queued"
    assert data["payload"]["adapterType"] == "codex"
    assert data["sequence"] == 7
    assert data["createdAt"] == CREATED_AT.isoformat()
    assert data["cursor"] == cursor


def test_encode_sse_event_includes_all_required_fields() -> None:
    event = TaskRunEvent(
        id="4e06acb9-e31a-4a4a-8db8-8291cf62bc96",
        task_run_id="run-2",
        event_type="error",
        payload_json='{"code":"CODEX_NOT_FOUND","message":"Codex CLI not found."}',
        sequence=42,
    )
    event.created_at = CREATED_AT
    result = encode_sse_event(event)

    assert f"id: {events.format_session_cursor(event)}" in result
    assert "event: error" not in result

    data_line = [l for l in result.splitlines() if l.startswith("data: ")][0]
    data = json.loads(data_line.removeprefix("data: "))
    assert data["sequence"] == 42
    assert data["taskRunId"] == "run-2"
    assert data["eventType"] == "error"
    assert data["payload"]["code"] == "CODEX_NOT_FOUND"
    assert data["createdAt"] is not None


def test_encode_sse_event_handles_empty_payload() -> None:
    event = TaskRunEvent(
        id="e468a5d1-4bb8-4f9f-88a2-8f936866648f",
        task_run_id="run-3",
        event_type="artifact.diff.ready",
        payload_json="{}",
        sequence=1,
    )
    event.created_at = CREATED_AT
    result = encode_sse_event(event)

    assert result.endswith("\n\n")
    data_line = [l for l in result.splitlines() if l.startswith("data: ")][0]
    data = json.loads(data_line.removeprefix("data: "))
    assert data["payload"] == {}


def test_session_cursor_round_trips_created_at_and_event_id() -> None:
    event = TaskRunEvent(
        id=EVENT_ID,
        task_run_id="run-1",
        event_type="task.state",
        sequence=1,
    )
    event.created_at = CREATED_AT

    cursor = events.format_session_cursor(event)

    assert events.parse_session_cursor(cursor) == (CREATED_AT, EVENT_ID)


@pytest.mark.parametrize(
    "cursor",
    [
        "7",
        "2026-05-17T10:00:00|not-a-uuid",
        "2026-05-17 10:00:00|4be7f260-e023-4f92-9b8e-2dc8815c3e74",
        "2026-05-17T10:00:00|4BE7F260-E023-4F92-9B8E-2DC8815C3E74",
    ],
)
def test_parse_session_cursor_rejects_non_server_issued_values(cursor: str) -> None:
    with pytest.raises(ValueError):
        events.parse_session_cursor(cursor)


@pytest.mark.anyio
async def test_publish_event_from_worker_thread_wakes_subscriber_loop() -> None:
    event = TaskRunEvent(
        id=EVENT_ID,
        task_run_id="run-1",
        event_type="task.state",
        sequence=1,
        created_at=CREATED_AT,
    )

    async with events.subscribe_session_events("session-1") as queue:
        await asyncio.to_thread(events.publish_event, "session-1", event)
        received = await asyncio.wait_for(queue.get(), timeout=0.2)

    assert received is event
