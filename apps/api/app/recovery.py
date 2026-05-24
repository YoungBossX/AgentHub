import json
from typing import Any, Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.events import append_task_run_event
from app.models import Task, TaskRun, utc_now
from app.scheduler import (
    cleanup_stale_target_locks,
    dependency_ids_for_task,
    refresh_downstream_scheduler_state,
)
from app.task_runs import (
    TaskRunLifecycleError,
    mark_stale_task_runs,
    retry_task_run,
)


class RecoveryError(ValueError):
    pass


def mark_stale_task_failed(
    db: DbSession,
    task_run_id: str,
    *,
    actor: str,
    reason: str,
) -> TaskRun:
    marked = mark_stale_task_runs(db, reason=reason)
    for task_run in marked:
        if task_run.id == task_run_id:
            _append_recovery_event(
                db,
                task_run.id,
                action="mark_stale_task_failed",
                actor=actor,
                reason=reason,
                previous_state=None,
                new_state=task_run.state,
            )
            return task_run
    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        raise RecoveryError(f"TaskRun not found: {task_run_id}")
    if task_run.state != "failed" or task_run.error_code != "TASK_RUN_STALE":
        raise RecoveryError("TaskRun is not stale and cannot be marked failed.")
    _append_recovery_event(
        db,
        task_run.id,
        action="mark_stale_task_failed",
        actor=actor,
        reason=reason,
        previous_state=task_run.state,
        new_state=task_run.state,
    )
    return task_run


def release_stale_lock(
    db: DbSession,
    task_run_id: str,
    *,
    actor: str,
    reason: str,
) -> dict[str, Any]:
    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        raise RecoveryError(f"TaskRun not found: {task_run_id}")
    task = db.get(Task, task_run.task_id)
    if task is None:
        raise RecoveryError(f"Task not found for TaskRun: {task_run_id}")

    released = cleanup_stale_target_locks(db, session_id=task.session_id)
    for item in released:
        if item["taskRunId"] == task_run_id:
            _append_recovery_event(
                db,
                task_run_id,
                action="release_stale_lock",
                actor=actor,
                reason=reason,
                previous_state=None,
                new_state="released",
                extra={"targetId": item["targetId"]},
            )
            return item
    raise RecoveryError("No stale target lock was released for this TaskRun.")


def retry_from_current_state(
    db: DbSession,
    task_run_id: str,
    *,
    actor: str,
) -> TaskRun:
    retry = retry_task_run(db, task_run_id, retry_mode="current_state")
    _append_recovery_event(
        db,
        retry.id,
        action="retry_from_current_state",
        actor=actor,
        reason="Retry from current target state.",
        previous_state=None,
        new_state=retry.state,
        extra={"previousRunId": task_run_id},
    )
    return retry


def retry_from_checkpoint(
    db: DbSession,
    task_run_id: str,
    *,
    actor: str,
) -> TaskRun:
    retry = retry_task_run(db, task_run_id, retry_mode="checkpoint")
    _append_recovery_event(
        db,
        retry.id,
        action="retry_from_checkpoint",
        actor=actor,
        reason="Retry from checkpoint after safety checks.",
        previous_state=None,
        new_state=retry.state,
        extra={"previousRunId": task_run_id},
    )
    return retry


def stop_downstream_pipeline(
    db: DbSession,
    dependency_task_id: str,
    *,
    actor: str,
    reason: str,
) -> list[Task]:
    source_run = _latest_task_run_for_task(db, dependency_task_id)
    stopped: list[Task] = []
    dependency = db.get(Task, dependency_task_id)
    if dependency is None:
        raise RecoveryError(f"Task not found: {dependency_task_id}")

    tasks = db.exec(
        select(Task)
        .where(Task.session_id == dependency.session_id)
        .order_by(Task.priority, Task.created_at, Task.id)
    ).all()
    for task in tasks:
        if dependency_task_id not in dependency_ids_for_task(task):
            continue
        if task.status in {"completed", "failed", "interrupted"}:
            continue
        plan = _plan_for_task(task)
        scheduler = dict(plan.get("scheduler") or {})
        scheduler.update(
            {
                "state": "blocked",
                "runnable": False,
                "reason": reason,
                "recoveryStopped": True,
            }
        )
        plan["scheduler"] = scheduler
        task.status = "blocked"
        task.plan_json = json.dumps(plan, separators=(",", ":"))
        task.updated_at = utc_now()
        db.add(task)
        stopped.append(task)
    db.commit()
    for task in stopped:
        db.refresh(task)
    if source_run is not None:
        _append_recovery_event(
            db,
            source_run.id,
            action="stop_downstream_pipeline",
            actor=actor,
            reason=reason,
            previous_state=None,
            new_state="blocked",
            extra={"downstreamTaskIds": [task.id for task in stopped]},
        )
    return stopped


def resume_downstream_pipeline(
    db: DbSession,
    dependency_task_id: str,
    *,
    actor: str,
    reason: str,
) -> list[Task]:
    source_run = _latest_task_run_for_task(db, dependency_task_id)
    resumed = refresh_downstream_scheduler_state(db, dependency_task_id)
    if source_run is not None:
        _append_recovery_event(
            db,
            source_run.id,
            action="resume_downstream_pipeline",
            actor=actor,
            reason=reason,
            previous_state=None,
            new_state="reevaluated",
            extra={"downstreamTaskIds": [task.id for task in resumed]},
        )
    return resumed


def _append_recovery_event(
    db: DbSession,
    task_run_id: str,
    *,
    action: str,
    actor: str,
    reason: str,
    previous_state: Optional[str],
    new_state: str,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    payload = {
        "action": action,
        "actor": actor,
        "reason": reason,
        "previousState": previous_state,
        "newState": new_state,
        **(extra or {}),
    }
    append_task_run_event(
        db,
        task_run_id=task_run_id,
        event_type="recovery.action",
        payload_json=json.dumps(payload, separators=(",", ":")),
    )


def _latest_task_run_for_task(db: DbSession, task_id: str) -> Optional[TaskRun]:
    return db.exec(
        select(TaskRun)
        .where(TaskRun.task_id == task_id)
        .order_by(TaskRun.created_at.desc(), TaskRun.id.desc())
    ).first()


def _plan_for_task(task: Task) -> dict[str, Any]:
    try:
        value = json.loads(task.plan_json)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}
