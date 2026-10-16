"""Opt-in bounded planner evidence for trusted evaluation; no behavior changes."""
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json

from app.process_environment import redact_process_evidence

_calls = ContextVar("agenthub_planner_observation", default=None)


@contextmanager
def observe_planner_calls():
    calls = []
    token = _calls.set(calls)
    try:
        yield calls
    finally:
        _calls.reset(token)


def record_planner_call(planner_input, provider, result=None, *, error=None):
    calls = _calls.get()
    if calls is None or len(calls) >= 8:
        return
    value = {"providerId": getattr(provider, "provider_id", None),
             "plannerSource": getattr(provider, "planner_source", None),
             "inputSha256": hashlib.sha256(json.dumps(planner_input, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
    if result is not None:
        value.update(redact_process_evidence(result.to_metadata()))
        if isinstance(value.get("errorSummary"), str):
            value["errorSummary"] = value["errorSummary"][:1200]
        raw = result.raw_output or ""
        value["outputSha256"] = hashlib.sha256(raw.encode()).hexdigest()
        try:
            parsed = json.loads(raw[:128000])
            draft = parsed.get("planDraft") or parsed
            value["plannedFiles"] = [[redact_process_evidence(path[:200]) for path in item.get("plannedFiles", [])[:12]
                                      if isinstance(path, str)] for item in draft.get("tasks", [])[:6] if isinstance(item, dict)]
            value["validationExpectations"] = [redact_process_evidence(text[:400]) for text in draft.get("validationExpectations", [])[:12] if isinstance(text, str)]
            value["taskValidationExpectations"] = [[redact_process_evidence(text[:400]) for text in item.get("validationExpectations", [])[:12]
                                                   if isinstance(text, str)] for item in draft.get("tasks", [])[:6] if isinstance(item, dict)]
        except (ValueError, TypeError, AttributeError):
            value["outputParsed"] = False
    if error is not None:
        value.update(status="exception", errorType=type(error).__name__)
    calls.append(value)
