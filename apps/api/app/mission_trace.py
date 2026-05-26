import json
from typing import Any

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.ledger import refresh_session_ledger
from app.models import Artifact, Task, TaskRun, TaskRunEvent
from app.schemas import SessionMissionTraceResponse

BLOCKING_SCHEDULER_STATES = {
    "blocked",
    "waiting_dependency",
    "waiting_target_lock",
    "failed",
    "retryable",
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
    return SessionMissionTraceResponse(
        currentGoal=ledger.current_goal,
        tasks=[_task_trace(task) for task in tasks],
        taskRuns=[_task_run_trace(task_run) for task_run in task_runs],
        events=[_event_trace(event) for event in events],
        artifacts=[_artifact_trace(artifact) for artifact in artifacts],
        blockers=blockers,
        nextActions=_next_actions(tasks, blockers),
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
        "navigation": {"taskId": task.id},
    }


def _task_run_trace(task_run: TaskRun) -> dict[str, Any]:
    metrics = _json_dict(task_run.metrics_json)
    return {
        "id": task_run.id,
        "taskId": task_run.task_id,
        "agentId": task_run.agent_id,
        "state": task_run.state,
        "adapterType": metrics.get("adapterType"),
        "providerAssignment": metrics.get("providerAssignment"),
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


def _next_actions(tasks: list[Task], blockers: list[dict[str, Any]]) -> list[dict[str, str]]:
    blocked_task_ids = {str(blocker["taskId"]) for blocker in blockers}
    actions: list[dict[str, str]] = []
    for task in tasks:
        if task.id in blocked_task_ids:
            actions.append(
                {
                    "type": "inspect_blocker",
                    "taskId": task.id,
                    "label": "Inspect scheduler blocker",
                }
            )
        elif task.status == "pending":
            actions.append(
                {
                    "type": "start_or_wait",
                    "taskId": task.id,
                    "label": "Start when dependencies and target locks allow",
                }
            )
    return actions


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
