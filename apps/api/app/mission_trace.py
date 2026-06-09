import json
import re
from typing import Any

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.ledger import refresh_session_ledger
from app.memory_snapshots import (
    memory_snapshot_for_session,
    memory_snapshot_metadata,
)
from app.models import Artifact, Task, TaskRun, TaskRunEvent
from app.models import Session as AgentHubSession
from app.schemas import SessionMissionTraceResponse

BLOCKING_SCHEDULER_STATES = {
    "blocked",
    "waiting_dependency",
    "waiting_target_lock",
    "failed",
    "retryable",
    "fallback_available",
}


def build_session_mission_trace(
    db: DbSession,
    session_id: str,
) -> SessionMissionTraceResponse:
    ledger = refresh_session_ledger(db, session_id)
    tasks = db.exec(
        select(Task)
        .where(Task.session_id == session_id)
        .order_by(Task.priority, Task.created_at, Task.id)
    ).all()
    task_ids = [task.id for task in tasks]
    task_runs = _task_runs_for_tasks(db, task_ids)
    run_ids = [task_run.id for task_run in task_runs]
    events = _events_for_runs(db, run_ids)
    artifacts = _artifacts_for_runs(db, run_ids)
    blockers = _blockers_for_tasks(tasks)
    session = db.get(AgentHubSession, session_id)
    snapshot = (
        memory_snapshot_for_session(db, session)
        if session is not None
        else None
    )
    return SessionMissionTraceResponse(
        currentGoal=ledger.current_goal,
        memorySnapshot=memory_snapshot_metadata(snapshot) or None,
        tasks=[_task_trace(task) for task in tasks],
        taskGraphReadiness=_task_graph_readiness(tasks),
        taskRuns=[_task_run_trace(db, task_run) for task_run in task_runs],
        events=[_event_trace(event) for event in events],
        artifacts=[_artifact_trace(artifact) for artifact in artifacts],
        blockers=blockers,
        pmoEvidence=_pmo_evidence(tasks, blockers),
        nextActions=_next_actions(tasks, blockers, task_runs),
    )


def _task_runs_for_tasks(db: DbSession, task_ids: list[str]) -> list[TaskRun]:
    if not task_ids:
        return []
    return db.exec(
        select(TaskRun)
        .where(TaskRun.task_id.in_(task_ids))
        .order_by(TaskRun.created_at, TaskRun.id)
    ).all()


def _events_for_runs(db: DbSession, run_ids: list[str]) -> list[TaskRunEvent]:
    if not run_ids:
        return []
    return db.exec(
        select(TaskRunEvent)
        .where(TaskRunEvent.task_run_id.in_(run_ids))
        .order_by(TaskRunEvent.created_at, TaskRunEvent.sequence, TaskRunEvent.id)
    ).all()


def _artifacts_for_runs(db: DbSession, run_ids: list[str]) -> list[Artifact]:
    if not run_ids:
        return []
    return db.exec(
        select(Artifact)
        .where(Artifact.task_run_id.in_(run_ids))
        .order_by(Artifact.created_at, Artifact.id)
    ).all()


def _task_trace(task: Task) -> dict[str, Any]:
    plan = _json_dict(task.plan_json)
    scheduler = _json_dict(json.dumps(plan.get("scheduler", {})))
    return {
        "id": task.id,
        "title": task.title,
        "intentType": task.intent_type,
        "status": task.status,
        "priority": task.priority,
        "assignedAgentId": task.assigned_agent_id,
        "dependsOnTaskIds": _json_list(task.depends_on_task_ids),
        "scheduler": scheduler,
        "plannerEvidence": _planner_evidence(plan),
        "contextHandoff": _json_dict(json.dumps(plan.get("contextHandoff", {}))),
        "pmoDecision": _json_dict(json.dumps(plan.get("pmoDecision", {}))),
        "navigation": {"taskId": task.id},
    }


def _task_run_trace(db: DbSession, task_run: TaskRun) -> dict[str, Any]:
    from app.preview_deploy_jobs import job_diagnostics_for_task_run
    from app.session_queue import queue_diagnostics_for_task_run
    from app.target_locks import lock_diagnostics_for_task_run

    metrics = _json_dict(task_run.metrics_json)
    return {
        "id": task_run.id,
        "taskId": task_run.task_id,
        "agentId": task_run.agent_id,
        "state": task_run.state,
        "adapterType": metrics.get("adapterType"),
        "providerAssignment": metrics.get("providerAssignment"),
        "runtimeConfigResolution": metrics.get("runtimeConfigResolution"),
        "memorySnapshot": metrics.get("memorySnapshot"),
        "sessionQueue": queue_diagnostics_for_task_run(db, task_run.id),
        "targetLock": lock_diagnostics_for_task_run(db, task_run.id),
        "previewDeployJobs": job_diagnostics_for_task_run(db, task_run.id),
        "durableRun": {
            "runnerId": task_run.runner_id,
            "adapterRunId": task_run.adapter_run_id,
            "startedAt": task_run.started_at.isoformat()
            if task_run.started_at is not None
            else None,
            "endedAt": task_run.ended_at.isoformat()
            if task_run.ended_at is not None
            else None,
            "lastHeartbeatAt": task_run.last_heartbeat_at.isoformat()
            if task_run.last_heartbeat_at is not None
            else None,
            "leaseExpiresAt": task_run.lease_expires_at.isoformat()
            if task_run.lease_expires_at is not None
            else None,
            "staleDetectedAt": task_run.stale_detected_at.isoformat()
            if task_run.stale_detected_at is not None
            else None,
            "staleReason": task_run.stale_reason,
        },
        "errorCode": task_run.error_code,
        "errorMessage": task_run.error_message,
        "navigation": {
            "taskRunId": task_run.id,
            "taskId": task_run.task_id,
        },
    }


def _event_trace(event: TaskRunEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "taskRunId": event.task_run_id,
        "eventType": event.event_type,
        "sequence": event.sequence,
        "payload": _json_dict(event.payload_json),
        "createdAt": event.created_at.isoformat(),
        "navigation": {"taskRunId": event.task_run_id, "eventId": event.id},
    }


def _artifact_trace(artifact: Artifact) -> dict[str, Any]:
    return {
        "id": artifact.id,
        "taskRunId": artifact.task_run_id,
        "artifactType": artifact.artifact_type,
        "title": artifact.title,
        "status": artifact.status,
        "version": artifact.version,
        "meta": _json_dict(artifact.meta_json),
        "navigation": {"artifactId": artifact.id, "taskRunId": artifact.task_run_id},
    }


def _blockers_for_tasks(tasks: list[Task]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for task in tasks:
        plan = _json_dict(task.plan_json)
        scheduler = plan.get("scheduler")
        if not isinstance(scheduler, dict):
            continue
        state = scheduler.get("state")
        if state not in BLOCKING_SCHEDULER_STATES:
            continue
        blockers.append(
            {
                "taskId": task.id,
                "state": state,
                "reason": scheduler.get("reason"),
                "dependencyIds": scheduler.get("dependencyIds", []),
                "blockingDependencyIds": scheduler.get("blockingDependencyIds", []),
                "targetId": scheduler.get("targetId"),
                "navigation": {"taskId": task.id},
            }
        )
    return blockers


def _planner_evidence(plan: dict[str, Any]) -> dict[str, Any]:
    evidence = plan.get("plannerEvidence")
    if isinstance(evidence, dict):
        return evidence
    fallback = plan.get("plannerFallback")
    if isinstance(fallback, dict):
        return {
            "providerId": fallback.get("providerId"),
            "providerType": fallback.get("providerType"),
            "plannerSource": fallback.get("plannerSource") or "fallback",
            "status": fallback.get("status") or "fallback",
            "fallbackReason": fallback.get("reason"),
            "errorCode": fallback.get("errorCode"),
            "errorSummary": fallback.get("errorSummary"),
            "validationResult": "not_run",
        }
    planner = plan.get("planner")
    if isinstance(planner, str) and planner:
        return {
            "plannerSource": "deterministic",
            "status": "succeeded",
            "validationResult": "passed",
            "planner": planner,
        }
    return {}


def _pmo_evidence(tasks: list[Task], blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for task in tasks:
        plan = _json_dict(task.plan_json)
        decision = plan.get("pmoDecision")
        if isinstance(decision, dict) and decision:
            evidence.append(
                _redact_pmo_value(
                    {
                        "type": "plan_decision",
                        "taskId": task.id,
                        "state": decision.get("state"),
                        "actor": decision.get("actor"),
                        "reason": decision.get("reason"),
                        "createdAt": decision.get("createdAt"),
                        "decidedAt": decision.get("decidedAt"),
                        "nextActionSummary": decision.get("nextActionSummary"),
                        "navigation": {"taskId": task.id},
                    }
                )
            )
        scheduler = plan.get("scheduler")
        if isinstance(scheduler, dict):
            state = scheduler.get("state")
            if state in BLOCKING_SCHEDULER_STATES:
                evidence.append(
                    _redact_pmo_value(
                        {
                            "type": "blocker",
                            "taskId": task.id,
                            "state": state,
                            "reason": scheduler.get("reason"),
                            "targetId": scheduler.get("targetId"),
                            "dependencyIds": scheduler.get("dependencyIds", []),
                            "blockingDependencyIds": scheduler.get("blockingDependencyIds", []),
                            "conflictType": scheduler.get("conflictType"),
                            "conflictingTaskIds": scheduler.get("conflictingTaskIds", []),
                            "conflictingFiles": scheduler.get("conflictingFiles", []),
                            "navigation": {"taskId": task.id},
                        }
                    )
                )
        fallback = plan.get("plannerFallback")
        if isinstance(fallback, dict) and fallback:
            evidence.append(
                _redact_pmo_value(
                    {
                        "type": "fallback",
                        "taskId": task.id,
                        "reason": fallback.get("reason"),
                        "providerId": fallback.get("providerId"),
                        "errorCode": fallback.get("errorCode"),
                        "errorSummary": fallback.get("errorSummary"),
                        "validationResult": fallback.get("validationResult"),
                        "navigation": {"taskId": task.id},
                    }
                )
            )
    for blocker in blockers:
        evidence.append(_redact_pmo_value({"type": "blocker_summary", **blocker}))
    return evidence


def _task_graph_readiness(tasks: list[Task]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {
        "ready": [],
        "waitingDependency": [],
        "waitingTargetLock": [],
        "blocked": [],
        "running": [],
        "complete": [],
    }
    for task in tasks:
        plan = _json_dict(task.plan_json)
        scheduler = plan.get("scheduler")
        scheduler_state = scheduler.get("state") if isinstance(scheduler, dict) else None
        item = {
            "taskId": task.id,
            "title": task.title,
            "state": scheduler_state or task.status,
            "reason": scheduler.get("reason") if isinstance(scheduler, dict) else None,
            "navigation": {"taskId": task.id},
        }
        if task.status in {"completed"} or scheduler_state == "completed":
            groups["complete"].append(item)
        elif task.status == "running":
            groups["running"].append(item)
        elif scheduler_state == "waiting_dependency" or task.status == "waiting_dependency":
            groups["waitingDependency"].append(item)
        elif scheduler_state == "waiting_target_lock" or task.status == "waiting_target_lock":
            groups["waitingTargetLock"].append(item)
        elif scheduler_state in {"blocked", "failed", "retryable", "fallback_available"} or task.status in {
            "blocked",
            "failed",
            "waiting_approval",
        }:
            groups["blocked"].append(item)
        else:
            groups["ready"].append(item)
    return groups


def _next_actions(
    tasks: list[Task],
    blockers: list[dict[str, Any]],
    task_runs: list[TaskRun],
) -> list[dict[str, str]]:
    blocked_task_ids = {str(blocker["taskId"]) for blocker in blockers}
    latest_runs_by_task_id: dict[str, TaskRun] = {}
    for task_run in task_runs:
        latest_runs_by_task_id[task_run.task_id] = task_run

    actions: list[dict[str, str]] = []
    for task in tasks:
        plan = _json_dict(task.plan_json)
        scheduler = plan.get("scheduler") if isinstance(plan.get("scheduler"), dict) else {}
        scheduler_state = scheduler.get("state")
        pmo_decision = plan.get("pmoDecision") if isinstance(plan.get("pmoDecision"), dict) else {}
        if pmo_decision.get("state") == "pending_review":
            actions.extend(
                [
                    {
                        "type": "approve_plan",
                        "taskId": task.id,
                        "label": "Approve PMO-reviewed plan",
                    },
                    {
                        "type": "reject_plan",
                        "taskId": task.id,
                        "label": "Reject PMO-reviewed plan",
                    },
                    {
                        "type": "request_clarification",
                        "taskId": task.id,
                        "label": "Request clarification from the Main Agent",
                    },
                ]
            )
            continue
        if scheduler_state == "retryable" or task.status == "failed":
            actions.append(
                {
                    "type": "retry_task",
                    "taskId": task.id,
                    "label": "Retry failed task",
                }
            )
        if scheduler_state == "fallback_available":
            actions.append(
                {
                    "type": "retry_with_explicit_fallback",
                    "taskId": task.id,
                    "label": "Retry with explicit fallback",
                }
            )
        latest_run = latest_runs_by_task_id.get(task.id)
        if task.status == "waiting_approval" or (
            latest_run is not None and latest_run.state == "waiting_approval"
        ):
            run_id = latest_run.id if latest_run is not None else ""
            actions.extend(
                [
                    {
                        "type": "approve_task_run",
                        "taskId": task.id,
                        "taskRunId": run_id,
                        "label": "Approve waiting TaskRun",
                    },
                    {
                        "type": "deny_task_run",
                        "taskId": task.id,
                        "taskRunId": run_id,
                        "label": "Deny waiting TaskRun",
                    },
                ]
            )
        if task.id in blocked_task_ids:
            subtype = (
                "dependency"
                if scheduler_state == "waiting_dependency"
                else "target_lock"
                if scheduler_state == "waiting_target_lock"
                else "generic"
            )
            actions.append(
                {
                    "type": "inspect_blocker",
                    "subtype": subtype,
                    "taskId": task.id,
                    "label": "Inspect scheduler blocker",
                }
            )
        elif task.status == "pending":
            actions.append(
                {
                    "type": "start_ready_task",
                    "taskId": task.id,
                    "label": "Start when dependencies and target locks allow",
                }
            )
    return actions


def _redact_pmo_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _redact_pmo_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_pmo_value(item) for item in value if not _is_sensitive_string(item)]
    if isinstance(value, str):
        return _redact_sensitive_text(value)
    return value


def _redact_sensitive_text(value: str) -> str:
    if _is_sensitive_string(value):
        return "[protected]"
    redacted = re.sub(
        r"(?i)(secret|token|password|api[_-]?key)\s*[:=]\s*[^\s;]+",
        "[protected]",
        value,
    )
    redacted = re.sub(
        r"/[^\s]*?(?:\.env|/\.git|/node_modules|/\.venv|/secrets)(?:[^\s]*)?",
        "[protected]",
        redacted,
    )
    return redacted[:240] + ("..." if len(redacted) > 240 else "")


def _is_sensitive_string(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.lower()
    return any(
        marker in normalized
        for marker in (
            "/.env",
            ".env",
            "/.git",
            "node_modules",
            "/.venv",
            "/secrets",
            "secret_",
            "secret=",
            "token=",
            "password=",
            "api_key=",
        )
    )


def _json_dict(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str)]
