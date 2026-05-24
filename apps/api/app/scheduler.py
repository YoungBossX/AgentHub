import json
from dataclasses import dataclass
from typing import Any, Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.events import append_task_run_event
from app.models import Task, TaskRun
from app.models import Session as AgentHubSession
from app.models import utc_now
from app.target_registry import (
    AGENTHUB_PLATFORM_TARGET_ID,
    list_targets,
    list_targets_for_workspace,
    maybe_get_target_for_workspace,
)


SCHEDULER_READY = "ready"
SCHEDULER_COMPLETED = "completed"
SCHEDULER_WAITING_DEPENDENCY = "waiting_dependency"
SCHEDULER_WAITING_TARGET_LOCK = "waiting_target_lock"
SCHEDULER_BLOCKED = "blocked"
SCHEDULER_RETRYABLE = "retryable"
SCHEDULER_FALLBACK_AVAILABLE = "fallback_available"

DEPENDENCY_COMPLETE_STATUSES = {"completed"}
DEPENDENCY_BLOCKING_STATUSES = {"failed", "interrupted", "blocked"}
SCHEDULER_MANAGED_STATUSES = {
    "pending",
    "waiting_dependency",
    "waiting_target_lock",
    "blocked",
}
LOCK_ACTIVE_RUN_STATES = {
    "created",
    "queued",
    "streaming",
    "waiting_approval",
    "applying_changes",
    "collecting_diff",
    "starting_preview",
}
WRITE_INTENT_TYPES = {"frontend_change", "backend_change", "platform_maintenance"}
READ_INTENT_TYPES = {"planning", "review", "qa_review"}
FALLBACK_ELIGIBLE_INTENT_TYPES = {"frontend_change", "backend_change"}


@dataclass(frozen=True)
class SchedulerDecision:
    state: str
    runnable: bool
    reason: str
    dependency_ids: list[str]
    blocking_dependency_ids: list[str]
    target_id: Optional[str] = None
    write_lock_required: bool = False
    lock_holder_task_run_ids: Optional[list[str]] = None


def dependency_ids_for_task(task: Task) -> list[str]:
    try:
        value = json.loads(task.depends_on_task_ids)
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def evaluate_dependency_readiness(db: DbSession, task: Task) -> SchedulerDecision:
    dependency_ids = dependency_ids_for_task(task)
    if not dependency_ids:
        return SchedulerDecision(
            state=SCHEDULER_READY,
            runnable=True,
            reason="Task has no dependencies.",
            dependency_ids=[],
            blocking_dependency_ids=[],
        )

    waiting_dependency_ids: list[str] = []
    failed_dependency_ids: list[str] = []
    for dependency_id in dependency_ids:
        dependency = db.get(Task, dependency_id)
        if dependency is None:
            waiting_dependency_ids.append(dependency_id)
            continue
        if dependency.status in DEPENDENCY_COMPLETE_STATUSES:
            continue
        if dependency.status in DEPENDENCY_BLOCKING_STATUSES:
            failed_dependency_ids.append(dependency_id)
            continue
        waiting_dependency_ids.append(dependency_id)

    if failed_dependency_ids:
        return SchedulerDecision(
            state=SCHEDULER_BLOCKED,
            runnable=False,
            reason="One or more dependencies failed, were interrupted, or are blocked.",
            dependency_ids=dependency_ids,
            blocking_dependency_ids=failed_dependency_ids,
        )

    if waiting_dependency_ids:
        return SchedulerDecision(
            state=SCHEDULER_WAITING_DEPENDENCY,
            runnable=False,
            reason="Waiting for upstream dependencies to complete.",
            dependency_ids=dependency_ids,
            blocking_dependency_ids=waiting_dependency_ids,
        )

    return SchedulerDecision(
        state=SCHEDULER_READY,
        runnable=True,
        reason="All dependencies completed.",
        dependency_ids=dependency_ids,
        blocking_dependency_ids=[],
    )


def evaluate_target_lock_readiness(db: DbSession, task: Task) -> SchedulerDecision:
    target_id = target_id_for_task(task, db)
    write_lock_required = write_lock_required_for_task(task)
    dependency_ids = dependency_ids_for_task(task)
    if target_id is None or not write_lock_required:
        return SchedulerDecision(
            state=SCHEDULER_READY,
            runnable=True,
            reason="No target write lock is required.",
            dependency_ids=dependency_ids,
            blocking_dependency_ids=[],
            target_id=target_id,
            write_lock_required=False,
            lock_holder_task_run_ids=[],
        )

    if target_id == AGENTHUB_PLATFORM_TARGET_ID:
        plan = _plan_for_task(task)
        if plan.get("platformMode") is not True or plan.get("requiresApproval") is not True:
            return SchedulerDecision(
                state=SCHEDULER_BLOCKED,
                runnable=False,
                reason="AgentHub platform writes require explicit platform mode and approval.",
                dependency_ids=dependency_ids,
                blocking_dependency_ids=[],
                target_id=target_id,
                write_lock_required=True,
                lock_holder_task_run_ids=[],
            )

    workspace_id = _workspace_id_for_task(db, task)
    if workspace_id is None or maybe_get_target_for_workspace(db, workspace_id, target_id) is None:
        return SchedulerDecision(
            state=SCHEDULER_BLOCKED,
            runnable=False,
            reason=f"Unknown target project: {target_id}.",
            dependency_ids=dependency_ids,
            blocking_dependency_ids=[],
            target_id=target_id,
            write_lock_required=True,
            lock_holder_task_run_ids=[],
        )

    lock_holders = active_write_lock_holder_run_ids(db, task, target_id)
    if lock_holders:
        return SchedulerDecision(
            state=SCHEDULER_WAITING_TARGET_LOCK,
            runnable=False,
            reason=f"Waiting for target write lock: {target_id}.",
            dependency_ids=dependency_ids,
            blocking_dependency_ids=[],
            target_id=target_id,
            write_lock_required=True,
            lock_holder_task_run_ids=lock_holders,
        )

    return SchedulerDecision(
        state=SCHEDULER_READY,
        runnable=True,
        reason=f"Target write lock is available: {target_id}.",
        dependency_ids=dependency_ids,
        blocking_dependency_ids=[],
        target_id=target_id,
        write_lock_required=True,
        lock_holder_task_run_ids=[],
    )


def evaluate_scheduler_readiness(db: DbSession, task: Task) -> SchedulerDecision:
    dependency_decision = evaluate_dependency_readiness(db, task)
    if not dependency_decision.runnable:
        return dependency_decision
    return evaluate_target_lock_readiness(db, task)


def apply_scheduler_decision(
    db: DbSession,
    task: Task,
    decision: SchedulerDecision,
) -> Task:
    plan = _plan_for_task(task)
    plan["scheduler"] = {
        "state": decision.state,
        "runnable": decision.runnable,
        "reason": decision.reason,
        "dependencyIds": decision.dependency_ids,
        "blockingDependencyIds": decision.blocking_dependency_ids,
        "targetId": decision.target_id,
        "writeLockRequired": decision.write_lock_required,
        "lockHolderTaskRunIds": decision.lock_holder_task_run_ids or [],
    }
    task.plan_json = json.dumps(plan, separators=(",", ":"))

    if task.status in SCHEDULER_MANAGED_STATUSES:
        if decision.state == SCHEDULER_WAITING_DEPENDENCY:
            task.status = SCHEDULER_WAITING_DEPENDENCY
        elif decision.state == SCHEDULER_WAITING_TARGET_LOCK:
            task.status = SCHEDULER_WAITING_TARGET_LOCK
        elif decision.state == SCHEDULER_BLOCKED:
            task.status = SCHEDULER_BLOCKED
        elif decision.state == SCHEDULER_READY:
            task.status = "pending"

    task.updated_at = utc_now()
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def evaluate_and_apply_dependency_readiness(db: DbSession, task: Task) -> SchedulerDecision:
    decision = evaluate_dependency_readiness(db, task)
    apply_scheduler_decision(db, task, decision)
    return decision


def evaluate_and_apply_scheduler_readiness(db: DbSession, task: Task) -> SchedulerDecision:
    decision = evaluate_scheduler_readiness(db, task)
    apply_scheduler_decision(db, task, decision)
    return decision


def complete_synthetic_planning_tasks(db: DbSession, tasks: list[Task]) -> list[Task]:
    completed: list[Task] = []
    for task in tasks:
        if task.intent_type != "planning" or dependency_ids_for_task(task):
            continue
        plan = _plan_for_task(task)
        plan["scheduler"] = {
            "state": SCHEDULER_COMPLETED,
            "runnable": False,
            "reason": "Planning completed when the task graph was created.",
            "dependencyIds": [],
            "blockingDependencyIds": [],
            "targetId": target_id_for_task(task),
            "writeLockRequired": False,
            "lockHolderTaskRunIds": [],
        }
        task.status = "completed"
        task.plan_json = json.dumps(plan, separators=(",", ":"))
        task.updated_at = utc_now()
        db.add(task)
        db.commit()
        db.refresh(task)
        completed.append(task)
    return completed


def mark_task_run_terminal_scheduler_state(
    db: DbSession,
    task: Task,
    *,
    run_state: str,
    adapter_type: str,
    task_run_id: str,
) -> Task:
    plan = _plan_for_task(task)
    scheduler = dict(plan.get("scheduler") or {})
    scheduler.setdefault("dependencyIds", dependency_ids_for_task(task))
    scheduler.setdefault("blockingDependencyIds", [])
    scheduler.setdefault("targetId", target_id_for_task(task))
    scheduler.setdefault("writeLockRequired", write_lock_required_for_task(task))
    scheduler.setdefault("lockHolderTaskRunIds", [])
    scheduler["taskRunId"] = task_run_id
    scheduler["adapterType"] = adapter_type

    if run_state == "completed":
        scheduler.update(
            {
                "state": SCHEDULER_COMPLETED,
                "runnable": False,
                "reason": "TaskRun completed.",
                "retryable": False,
                "fallbackAvailable": False,
            }
        )
    elif run_state in {"failed", "interrupted"}:
        fallback_available = (
            adapter_type == "codex"
            and task.intent_type in FALLBACK_ELIGIBLE_INTENT_TYPES
        )
        scheduler.update(
            {
                "state": SCHEDULER_FALLBACK_AVAILABLE
                if fallback_available
                else SCHEDULER_RETRYABLE,
                "runnable": False,
                "reason": "TaskRun did not complete; retry is available.",
                "retryable": True,
                "fallbackAvailable": fallback_available,
            }
        )

    plan["scheduler"] = scheduler
    task.plan_json = json.dumps(plan, separators=(",", ":"))
    task.updated_at = utc_now()
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def refresh_downstream_scheduler_state(
    db: DbSession,
    dependency_task_id: str,
) -> list[Task]:
    dependency = db.get(Task, dependency_task_id)
    if dependency is None:
        return []

    refreshed: list[Task] = []
    tasks = db.exec(
        select(Task)
        .where(Task.session_id == dependency.session_id)
        .order_by(Task.priority, Task.created_at, Task.id)
    ).all()
    for task in tasks:
        if task.id == dependency_task_id:
            continue
        if dependency_task_id not in dependency_ids_for_task(task):
            continue
        decision = evaluate_scheduler_readiness(db, task)
        refreshed.append(apply_scheduler_decision(db, task, decision))
    return refreshed


def refresh_session_scheduler_state(db: DbSession, session_id: str) -> list[Task]:
    refreshed: list[Task] = []
    tasks = db.exec(
        select(Task)
        .where(Task.session_id == session_id)
        .order_by(Task.priority, Task.created_at, Task.id)
    ).all()
    for task in tasks:
        if task.status in {"completed", "failed", "interrupted"}:
            continue
        if not dependency_ids_for_task(task) and not write_lock_required_for_task(task):
            continue
        decision = evaluate_scheduler_readiness(db, task)
        refreshed.append(apply_scheduler_decision(db, task, decision))
    return refreshed


def cleanup_stale_target_locks(
    db: DbSession,
    *,
    session_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    from app.task_runs import mark_stale_task_runs

    stale_runs = mark_stale_task_runs(db, reason="target_lock_owner_stale")
    released: list[dict[str, Any]] = []
    for task_run in stale_runs:
        task = db.get(Task, task_run.task_id)
        if task is None:
            continue
        if session_id is not None and task.session_id != session_id:
            continue
        if not write_lock_required_for_task(task):
            continue
        target_id = target_id_for_task(task, db)
        if target_id is None:
            continue

        released_at = utc_now()
        payload = {
            "targetId": target_id,
            "ownerTaskRunId": task_run.id,
            "ownerTaskId": task.id,
            "sessionId": task.session_id,
            "lockMode": "write",
            "acquiredAt": task_run.created_at.isoformat(),
            "leaseExpiresAt": task_run.lease_expires_at.isoformat()
            if task_run.lease_expires_at is not None
            else None,
            "releasedAt": released_at.isoformat(),
            "releaseReason": "stale_owner",
            "ownerState": task_run.state,
        }
        append_task_run_event(
            db,
            task_run_id=task_run.id,
            event_type="target_lock.released",
            payload_json=json.dumps(payload, separators=(",", ":")),
        )
        released.append(
            {
                "taskRunId": task_run.id,
                "taskId": task.id,
                "sessionId": task.session_id,
                "targetId": target_id,
                "releaseReason": "stale_owner",
            }
        )

    if session_id is not None:
        refresh_session_scheduler_state(db, session_id)
    else:
        refreshed_session_ids = {
            item["sessionId"] for item in released if isinstance(item.get("sessionId"), str)
        }
        for refreshed_session_id in refreshed_session_ids:
            refresh_session_scheduler_state(db, refreshed_session_id)
    return released


def target_id_for_task(task: Task, db: Optional[DbSession] = None) -> Optional[str]:
    plan = _plan_for_task(task)
    target_id = plan.get("targetId")
    if isinstance(target_id, str) and target_id:
        return target_id

    safe_target = plan.get("safeTarget")
    if isinstance(safe_target, str) and safe_target:
        workspace_id = _workspace_id_for_task(db, task) if db is not None else None
        targets = (
            list_targets_for_workspace(db, workspace_id)
            if db is not None and workspace_id is not None
            else list_targets()
        )
        for target in targets:
            if target.permits_path(safe_target):
                return target.target_id
    return None


def write_lock_required_for_task(task: Task) -> bool:
    plan = _plan_for_task(task)
    if plan.get("writeMode") is True or plan.get("requiresWriteLock") is True:
        return True
    if plan.get("writeMode") is False or plan.get("readOnly") is True:
        return False
    if task.intent_type in READ_INTENT_TYPES:
        return False
    return task.intent_type in WRITE_INTENT_TYPES


def active_write_lock_holder_run_ids(
    db: DbSession,
    task: Task,
    target_id: str,
) -> list[str]:
    runs = db.exec(select(TaskRun).where(TaskRun.state.in_(LOCK_ACTIVE_RUN_STATES))).all()
    holders: list[str] = []
    for run in runs:
        run_task = db.get(Task, run.task_id)
        if run_task is None or run_task.session_id != task.session_id:
            continue
        if not write_lock_required_for_task(run_task):
            continue
        if target_id_for_task(run_task, db) == target_id:
            holders.append(run.id)
    return holders


def _workspace_id_for_task(db: DbSession, task: Task) -> Optional[str]:
    session = db.get(AgentHubSession, task.session_id)
    return session.workspace_id if session is not None else None


def _plan_for_task(task: Task) -> dict[str, Any]:
    try:
        value = json.loads(task.plan_json)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}
