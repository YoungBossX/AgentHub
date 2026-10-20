"""Bound derived Planner history without replaying UI telemetry or editing evidence."""
from sqlalchemy import func
from sqlmodel import Session, select

from app.mission_trace import build_session_mission_trace
from app.models import Task, TaskRun, TaskRunEvent

RECORD_LIMIT = 32
TEXT_LIMIT = 600


def build_planner_mission_trace(db: Session, session_id: str) -> dict:
    # Full UI traces still include all events. Avoid loading their payloads at
    # all for planning: thousands of small stream chunks are not task context.
    full = build_session_mission_trace(db, session_id, include_events=False).model_dump(by_alias=True)
    event_count = db.exec(select(func.count(TaskRunEvent.id)).join(
        TaskRun, TaskRun.id == TaskRunEvent.task_run_id,
    ).join(Task, Task.id == TaskRun.task_id).where(Task.session_id == session_id)).one()
    selection = {"policy": "planner_history_summary_v1", "truncated": 0,
                 "events": {"total": event_count, "included": 0, "omitted": event_count}}

    def value(item):
        if isinstance(item, str):
            if len(item) > TEXT_LIMIT:
                selection["truncated"] += 1
            return item[:TEXT_LIMIT]
        if isinstance(item, list):
            selection["truncated"] += int(len(item) > RECORD_LIMIT)
            return [value(child) for child in item[:RECORD_LIMIT] if isinstance(child, str)]
        return item if item is None or isinstance(item, (bool, int, float)) else None

    def fields(item, names):
        return {name: value(item[name]) for name in names.split() if name in item}

    def task_summary(item):
        result = fields(item, "id title intentType status priority assignedAgentId dependsOnTaskIds")
        result["scheduler"] = fields(item.get("scheduler", {}),
            "state reason targetId dependencyIds blockingDependencyIds")
        result["plannerEvidence"] = fields(item.get("plannerEvidence", {}),
            "providerId providerType plannerSource status errorCode validationResult")
        result["pmoDecision"] = fields(item.get("pmoDecision", {}), "state reason nextActionSummary")
        return result

    def section(name, projector, *, state_key=None):
        items = list(reversed(full[name]))
        if state_key:
            # Keep unresolved work before completed history, even when older.
            items.sort(key=lambda item: item.get(state_key) in {"completed", "cancelled"})
        chosen = items[:RECORD_LIMIT]
        selection[name] = {"total": len(items), "included": len(chosen), "omitted": len(items) - len(chosen)}
        return [projector(item) for item in chosen]

    result = {"version": "planner_mission_summary_v1", "currentGoal": full["currentGoal"],
        "memorySnapshot": full["memorySnapshot"], "events": [],
        "tasks": section("tasks", task_summary, state_key="status"),
        "taskRuns": section("taskRuns", lambda item: fields(item,
            "id taskId agentId state adapterType errorCode errorMessage"), state_key="state"),
        "artifacts": section("artifacts", lambda item: fields(item,
            "id taskRunId artifactType title status version")),
        "blockers": section("blockers", lambda item: fields(item,
            "taskId state reason dependencyIds blockingDependencyIds targetId")),
        "pmoEvidence": section("pmoEvidence", lambda item: fields(item,
            "type taskId state actor reason createdAt decidedAt nextActionSummary")),
        "nextActions": section("nextActions", lambda item: fields(item, "type taskId label")),
        "selection": selection,
        "scope": "Historical summaries only, not proof of completion. Raw event payloads, nested telemetry and duplicate readiness views are omitted; full evidence remains in the session trace."}
    counts = [item for item in selection.values() if isinstance(item, dict)]
    selection.update(total=sum(item["total"] for item in counts),
                     included=sum(item["included"] for item in counts),
                     omitted=sum(item["omitted"] for item in counts))
    return result
