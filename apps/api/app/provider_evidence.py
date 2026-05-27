import json
from typing import Any, Optional

from sqlmodel import Session as DbSession

from app.models import Agent, TaskRun


def provider_evidence_for_task_run(
    db: DbSession,
    task_run: TaskRun,
    *,
    changed_files: Optional[list[str]] = None,
    logs: Optional[list[str]] = None,
    artifact_refs: Optional[dict[str, Optional[str]]] = None,
) -> dict[str, Any]:
    metrics = _json_dict(task_run.metrics_json)
    assignment = metrics.get("providerAssignment")
    if not isinstance(assignment, dict):
        assignment = {}

    agent = db.get(Agent, task_run.agent_id)
    adapter_type = _string_value(metrics.get("adapterType"))
    if adapter_type is None:
        adapter_type = _string_value(assignment.get("adapterType"))
    if adapter_type is None and agent is not None:
        adapter_type = agent.adapter_type

    provider_id = _string_value(assignment.get("providerId"))
    if provider_id is None and agent is not None:
        provider_id = agent.provider

    evidence: dict[str, Any] = {
        "taskRunId": task_run.id,
        "runStatus": task_run.state,
        "adapterType": adapter_type,
        "providerId": provider_id,
        "providerAssignment": assignment or None,
        "errorCode": task_run.error_code,
        "errorMessage": task_run.error_message,
        "changedFiles": changed_files or [],
        "logs": logs or [],
        "artifactRefs": _compact_refs(artifact_refs or {}),
    }

    fallback_from = _string_value(metrics.get("fallbackFromRunId"))
    if fallback_from is not None:
        evidence["fallbackFromRunId"] = fallback_from

    retry_of = _string_value(metrics.get("retryOfRunId"))
    if retry_of is not None:
        evidence["retryOfRunId"] = retry_of

    return evidence


def scripted_provider_evidence(
    origin_evidence: dict[str, Any],
    *,
    provider_id: str = "local-scripted-review",
    adapter_type: str = "scripted_mock",
) -> dict[str, Any]:
    evidence = dict(origin_evidence)
    evidence["adapterType"] = adapter_type
    evidence["providerId"] = provider_id
    evidence["providerAssignment"] = {
        "adapterType": adapter_type,
        "providerId": provider_id,
        "source": "scripted_review",
        "supportedMode": "review",
        "fallbackPolicy": "deterministic_review",
    }
    return evidence


def _json_dict(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _string_value(value: object) -> Optional[str]:
    return value if isinstance(value, str) and value else None


def _compact_refs(refs: dict[str, Optional[str]]) -> dict[str, str]:
    return {key: value for key, value in refs.items() if isinstance(value, str) and value}
