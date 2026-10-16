import asyncio
import json

from app.planner_observation import observe_planner_calls, record_planner_call
from app.planner_providers import PlannerProviderResult


class Provider:
    provider_id = "test-planner"
    planner_source = "fake_test"


def result(raw):
    return PlannerProviderResult("test-planner", "fake_test", "fake_test", "succeeded", raw_output=raw)


def test_observation_is_opt_in_thread_scoped_and_records_paths_without_raw_prompt():
    record_planner_call({"request": "not retained"}, Provider(), result("{}"))
    with observe_planner_calls() as calls:
        asyncio.run(asyncio.to_thread(record_planner_call, {"request": "private prompt contents"}, Provider(),
            result(json.dumps({"planDraft": {"validationExpectations": ["pnpm build"], "tasks": [{"plannedFiles": ["app/main.py"], "validationExpectations": ["pnpm demo:api:test"]}]}}))))
    assert len(calls) == 1 and calls[0]["plannedFiles"] == [["app/main.py"]]
    assert calls[0]["plannerSource"] == "fake_test"
    assert calls[0]["validationExpectations"] == ["pnpm build"]
    assert calls[0]["taskValidationExpectations"] == [["pnpm demo:api:test"]]
    assert len(calls[0]["inputSha256"]) == 64 and len(calls[0]["outputSha256"]) == 64
    assert "private prompt contents" not in json.dumps(calls)
    record_planner_call({}, Provider(), result("{}"))
    assert len(calls) == 1


def test_parse_and_provider_failures_are_retained_and_never_promoted():
    with observe_planner_calls() as calls:
        record_planner_call({}, Provider(), result("invalid output"))
        record_planner_call({}, Provider(), error=TimeoutError())
    assert calls[0]["outputParsed"] is False
    assert calls[1]["status"] == "exception" and calls[1]["errorType"] == "TimeoutError"


def test_observation_caps_entries_and_redacts_sensitive_metadata():
    value = PlannerProviderResult("test-planner", "fake_test", "fake_test", "failed", error_summary="api_key=private-value")
    with observe_planner_calls() as calls:
        for _ in range(12): record_planner_call({}, Provider(), value)
    assert len(calls) == 8 and "private-value" not in json.dumps(calls)
