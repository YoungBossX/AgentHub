import json
from dataclasses import dataclass
from typing import Any

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.models import Task
from app.models import utc_now


SCHEDULER_READY = "ready"
SCHEDULER_COMPLETED = "completed"
SCHEDULER_WAITING_DEPENDENCY = "waiting_dependency"
SCHEDULER_BLOCKED = "blocked"

DEPENDENCY_COMPLETE_STATUSES = {"completed"}
DEPENDENCY_BLOCKING_STATUSES = {"failed", "interrupted", "blocked"}
SCHEDULER_MANAGED_STATUSES = {"pending", "waiting_dependency", "blocked"}


@dataclass(frozen=True)
class SchedulerDecision:
    state: str
    runnable: bool
    reason: str
    dependency_ids: list[str]
    blocking_dependency_ids: list[str]


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
    }
    task.plan_json = json.dumps(plan, separators=(",", ":"))

    if task.status in SCHEDULER_MANAGED_STATUSES:
        if decision.state == SCHEDULER_WAITING_DEPENDENCY:
            task.status = SCHEDULER_WAITING_DEPENDENCY
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
        }
        task.status = "completed"
        task.plan_json = json.dumps(plan, separators=(",", ":"))
        task.updated_at = utc_now()
        db.add(task)
        db.commit()
        db.refresh(task)
        completed.append(task)
    return completed


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
        decision = evaluate_dependency_readiness(db, task)
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
        if not dependency_ids_for_task(task):
            continue
        decision = evaluate_dependency_readiness(db, task)
        refreshed.append(apply_scheduler_decision(db, task, decision))
    return refreshed


def _plan_for_task(task: Task) -> dict[str, Any]:
    try:
        value = json.loads(task.plan_json)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}
