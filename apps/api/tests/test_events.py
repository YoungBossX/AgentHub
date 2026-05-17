from datetime import datetime

from app.events import encode_sse_event
from app.models import TaskRunEvent

CREATED_AT = datetime(2026, 5, 17, 10, 0, 0)


def test_encode_sse_event_produces_valid_wire_format() -> None:
    event = TaskRunEvent(
        id="evt-1",
        task_run_id="run-1",
        event_type="task.state",
        payload_json='{"state":"queued","adapterType":"codex"}',
        sequence=7,
    )
    event.created_at = CREATED_AT
    result = encode_sse_event(event)

    lines = result.splitlines()
    assert lines[0] == "id: 7"
    assert lines[1] == "event: task.state"
    assert lines[2].startswith("data: ")
    assert lines[3] == ""

    import json

    data = json.loads(lines[2].removeprefix("data: "))
    assert data["id"] == "evt-1"
    assert data["taskRunId"] == "run-1"
    assert data["eventType"] == "task.state"
    assert data["payload"]["state"] == "queued"
    assert data["payload"]["adapterType"] == "codex"
    assert data["sequence"] == 7


def test_encode_sse_event_includes_all_required_fields() -> None:
    event = TaskRunEvent(
        id="evt-2",
        task_run_id="run-2",
        event_type="error",
        payload_json='{"code":"CODEX_NOT_FOUND","message":"Codex CLI not found."}',
        sequence=42,
    )
    event.created_at = CREATED_AT
    result = encode_sse_event(event)

    assert "id: 42" in result
    assert "event: error" in result

    data_line = [l for l in result.splitlines() if l.startswith("data: ")][0]
    import json

    data = json.loads(data_line.removeprefix("data: "))
    assert data["sequence"] == 42
    assert data["taskRunId"] == "run-2"
    assert data["eventType"] == "error"
    assert data["payload"]["code"] == "CODEX_NOT_FOUND"
    assert data["createdAt"] is not None


def test_encode_sse_event_handles_empty_payload() -> None:
    event = TaskRunEvent(
        id="evt-3",
        task_run_id="run-3",
        event_type="artifact.diff.ready",
        payload_json="{}",
        sequence=1,
    )
    event.created_at = CREATED_AT
    result = encode_sse_event(event)

    assert result.endswith("\n\n")
    import json

    data_line = [l for l in result.splitlines() if l.startswith("data: ")][0]
    data = json.loads(data_line.removeprefix("data: "))
    assert data["payload"] == {}
