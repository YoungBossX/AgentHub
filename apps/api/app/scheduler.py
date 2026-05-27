import json
import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
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
    conflict_type: Optional[str] = None
    conflicting_task_ids: Optional[list[str]] = None
    conflicting_files: Optional[list[str]] = None


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
    target_lock_decision = evaluate_target_lock_readiness(db, task)
    if not target_lock_decision.runnable:
        return target_lock_decision
    return evaluate_conflict_readiness(db, task)


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
    if decision.conflict_type is not None:
        plan["scheduler"]["conflictType"] = decision.conflict_type
    if decision.conflicting_task_ids:
        plan["scheduler"]["conflictingTaskIds"] = decision.conflicting_task_ids
    if decision.conflicting_files:
        plan["scheduler"]["conflictingFiles"] = decision.conflicting_files
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


def evaluate_conflict_readiness(db: DbSession, task: Task) -> SchedulerDecision:
    target_id = target_id_for_task(task, db)
    dependency_ids = dependency_ids_for_task(task)
    write_lock_required = write_lock_required_for_task(task)
    if not write_lock_required:
        return SchedulerDecision(
            state=SCHEDULER_READY,
            runnable=True,
            reason="No write conflicts apply to read-only task.",
            dependency_ids=dependency_ids,
            blocking_dependency_ids=[],
            target_id=target_id,
            write_lock_required=False,
            lock_holder_task_run_ids=[],
        )

    contract_conflict = _contract_drift_conflict(task)
    if contract_conflict is not None:
        return SchedulerDecision(
            state=SCHEDULER_BLOCKED,
            runnable=False,
            reason="Blocked by contract drift conflict.",
            dependency_ids=dependency_ids,
            blocking_dependency_ids=[],
            target_id=target_id,
            write_lock_required=True,
            lock_holder_task_run_ids=[],
            conflict_type="contract_drift",
            conflicting_files=[],
        )

    overlap = _file_overlap_conflict(db, task)
    if overlap is not None:
        return SchedulerDecision(
            state=SCHEDULER_BLOCKED,
            runnable=False,
            reason="Blocked by file overlap conflict.",
            dependency_ids=dependency_ids,
            blocking_dependency_ids=[],
            target_id=target_id,
            write_lock_required=True,
            lock_holder_task_run_ids=[],
            conflict_type="file_overlap",
            conflicting_task_ids=overlap["taskIds"],
            conflicting_files=overlap["files"],
        )

    dirty_files = _dirty_worktree_conflict(db, task)
    if dirty_files:
        return SchedulerDecision(
            state=SCHEDULER_BLOCKED,
            runnable=False,
            reason="Blocked by dirty worktree conflict.",
            dependency_ids=dependency_ids,
            blocking_dependency_ids=[],
            target_id=target_id,
            write_lock_required=True,
            lock_holder_task_run_ids=[],
            conflict_type="dirty_worktree",
            conflicting_files=dirty_files,
        )

    return SchedulerDecision(
        state=SCHEDULER_READY,
        runnable=True,
        reason="No write conflicts detected.",
        dependency_ids=dependency_ids,
        blocking_dependency_ids=[],
        target_id=target_id,
        write_lock_required=True,
        lock_holder_task_run_ids=[],
    )


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
    provider_metadata = _provider_metadata_for_task_run(db, task_run_id)
    if provider_metadata.get("providerId") is not None:
        scheduler["providerId"] = provider_metadata["providerId"]
    if provider_metadata.get("providerAssignment") is not None:
        scheduler["providerAssignment"] = provider_metadata["providerAssignment"]
    if provider_metadata.get("fallbackFromRunId") is not None:
        scheduler["fallbackFromRunId"] = provider_metadata["fallbackFromRunId"]
    if provider_metadata.get("retryOfRunId") is not None:
        scheduler["retryOfRunId"] = provider_metadata["retryOfRunId"]

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


def _provider_metadata_for_task_run(
    db: DbSession,
    task_run_id: str,
) -> dict[str, Any]:
    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        return {}
    metrics = _json_dict(task_run.metrics_json)
    assignment = metrics.get("providerAssignment")
    provider_id = None
    if isinstance(assignment, dict):
        provider_id = assignment.get("providerId")
    return {
        "providerId": provider_id if isinstance(provider_id, str) else None,
        "providerAssignment": assignment if isinstance(assignment, dict) else None,
        "fallbackFromRunId": metrics.get("fallbackFromRunId")
        if isinstance(metrics.get("fallbackFromRunId"), str)
        else None,
        "retryOfRunId": metrics.get("retryOfRunId")
        if isinstance(metrics.get("retryOfRunId"), str)
        else None,
    }


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


def _contract_drift_conflict(task: Task) -> Optional[dict[str, Any]]:
    plan = _plan_for_task(task)
    contract = plan.get("appContract")
    contract_id = plan.get("contractId")
    if isinstance(contract, dict):
        active_contract_id = contract.get("contractId")
        if (
            isinstance(contract_id, str)
            and isinstance(active_contract_id, str)
            and contract_id != active_contract_id
        ):
            return {"expected": contract_id, "actual": active_contract_id}
        contract_hash = plan.get("contractHash")
        if isinstance(contract_hash, str) and contract_hash != _contract_hash(contract):
            return {"expectedHash": contract_hash}
    return None


def _file_overlap_conflict(db: DbSession, task: Task) -> Optional[dict[str, Any]]:
    if dependency_ids_for_task(task):
        return None
    planned_files = set(_planned_files_for_task(task))
    if not planned_files:
        return None
    dependency_ids = set(dependency_ids_for_task(task))
    conflicts: list[str] = []
    overlapping_files: set[str] = set()
    candidates = db.exec(
        select(Task)
        .where(Task.session_id == task.session_id)
        .order_by(Task.priority, Task.created_at, Task.id)
    ).all()
    for candidate in candidates:
        if candidate.id == task.id:
            break
        if candidate.status in {"completed", "failed", "interrupted", "blocked"}:
            continue
        if candidate.id in dependency_ids or task.id in dependency_ids_for_task(candidate):
            continue
        if not write_lock_required_for_task(candidate):
            continue
        candidate_files = set(_planned_files_for_task(candidate))
        overlap = planned_files.intersection(candidate_files)
        if overlap:
            conflicts.append(candidate.id)
            overlapping_files.update(overlap)
    if not conflicts:
        return None
    return {"taskIds": conflicts, "files": sorted(overlapping_files)}


def _dirty_worktree_conflict(db: DbSession, task: Task) -> list[str]:
    plan = _plan_for_task(task)
    planned_files = set(_planned_files_for_task(task))
    target_id = target_id_for_task(task, db)
    if target_id is None:
        return []
    workspace_id = _workspace_id_for_task(db, task)
    if workspace_id is None:
        return []
    target = maybe_get_target_for_workspace(db, workspace_id, target_id)
    if target is None:
        return []
    root = Path(target.root)
    if not root.is_absolute():
        session = db.get(AgentHubSession, task.session_id)
        if session is None:
            return []
        root = Path(session.worktree_path)
    dirty_files = _git_dirty_files(root)
    if dirty_files is None:
        return []
    checkpoint = plan.get("preRunCheckpoint")
    checkpoint_dirty = (
        set(checkpoint.get("dirtyFiles", [])) if isinstance(checkpoint, dict) else set()
    )
    safe_files = planned_files.union(path for path in checkpoint_dirty if isinstance(path, str))
    return sorted(path for path in dirty_files if path not in safe_files)


def _planned_files_for_task(task: Task) -> list[str]:
    plan = _plan_for_task(task)
    files = plan.get("files")
    if not isinstance(files, list):
        return []
    return [path for path in files if isinstance(path, str) and path]


def _git_dirty_files(root: Path) -> Optional[list[str]]:
    if not root.exists():
        return None
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    files: list[str] = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        path = line[3:] if len(line) > 3 else line
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip()
        if path:
            files.append(path)
    return files


def _contract_hash(contract: dict[str, Any]) -> str:
    normalized = json.dumps(contract, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _workspace_id_for_task(db: DbSession, task: Task) -> Optional[str]:
    session = db.get(AgentHubSession, task.session_id)
    return session.workspace_id if session is not None else None


def _plan_for_task(task: Task) -> dict[str, Any]:
    try:
        value = json.loads(task.plan_json)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _json_dict(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
