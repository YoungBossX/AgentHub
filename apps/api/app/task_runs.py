import json
import os
import hashlib
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.events import append_task_run_event
from app.diffs import capture_base_ref_for_worktree
from app.agent_selection_policy import AgentSelectionError, validate_agent_selection
from app.models import Agent, Task, TaskRun
from app.models import Session as AgentHubSession
from app.models import utc_now
from app.provider_assignments import (
    ProviderAssignmentError,
    resolve_provider_assignment,
)
from app.target_registry import (
    AGENTHUB_PLATFORM_TARGET_ID,
    TargetRegistryError,
    get_target_for_workspace,
)

TASK_RUN_STATES = {
    "created",
    "queued",
    "streaming",
    "waiting_approval",
    "applying_changes",
    "collecting_diff",
    "starting_preview",
    "completed",
    "failed",
    "interrupted",
}
ACTIVE_STATES = {
    "created",
    "queued",
    "streaming",
    "waiting_approval",
    "applying_changes",
    "collecting_diff",
    "starting_preview",
}
RETRYABLE_STATES = {"failed", "interrupted"}
TERMINAL_STATES = {"completed", "failed", "interrupted"}
DEFAULT_CODE_ADAPTER_ENV = "AGENTHUB_DEFAULT_CODE_ADAPTER"
CODE_AGENT_ROLES = {"frontend", "backend"}
SUPPORTED_CODE_ADAPTERS = {"codex", "claude_code"}
DEFAULT_LEASE_SECONDS = 300


class TaskRunLifecycleError(ValueError):
    pass


def create_task_run(
    db: DbSession,
    task_id: str,
    adapter_type: Optional[str] = None,
    retry_of_run_id: Optional[str] = None,
    fallback_from_run_id: Optional[str] = None,
    retry_metadata: Optional[dict[str, Any]] = None,
) -> TaskRun:
    task = _task_or_raise(db, task_id)
    session = _session_or_raise(db, task.session_id)
    agent = _agent_or_raise(db, task.assigned_agent_id)
    selected_adapter = adapter_type or _default_adapter_for_agent(agent)
    try:
        provider_assignment = resolve_provider_assignment(
            task,
            agent,
            selected_adapter=selected_adapter,
            explicit_adapter_type=adapter_type,
        )
    except ProviderAssignmentError as exc:
        raise TaskRunLifecycleError(str(exc)) from exc
    selected_adapter = provider_assignment.adapter_type
    try:
        agent_selection = validate_agent_selection(
            db,
            task,
            agent,
            explicit_adapter_type=adapter_type,
        )
    except AgentSelectionError as exc:
        raise TaskRunLifecycleError(str(exc)) from exc
    _ensure_target_write_lock_available(db, task)

    now = utc_now()
    worktree_path = _worktree_path_for_task(db, task, session)
    base_ref = capture_base_ref_for_worktree(worktree_path)
    metrics = {
        "adapterType": selected_adapter,
        "providerAssignment": provider_assignment.to_metadata(),
        "agentSelection": agent_selection.to_metadata(),
    }
    if retry_of_run_id is not None:
        metrics["retryOfRunId"] = retry_of_run_id
    if fallback_from_run_id is not None:
        metrics["fallbackFromRunId"] = fallback_from_run_id
    if retry_metadata is not None:
        metrics.update(retry_metadata)
    checkpoint = _pre_run_checkpoint_for_task(
        db,
        task,
        session,
        worktree_path=worktree_path,
        base_ref=base_ref,
        now=now,
    )
    if checkpoint is not None:
        metrics["preRunCheckpoint"] = checkpoint

    approval_payload = _platform_approval_payload(task)
    initial_state = "waiting_approval" if approval_payload is not None else "queued"
    task.status = _task_status_for_run_state(initial_state)
    task.updated_at = now
    runner_id = _new_runner_id()
    task_run = TaskRun(
        task_id=task.id,
        agent_id=agent.id,
        state=initial_state,
        runner_id=runner_id,
        last_heartbeat_at=now,
        lease_expires_at=_lease_expires_at(now),
        worktree_path=worktree_path,
        base_ref=base_ref,
        metrics_json=json.dumps(metrics, separators=(",", ":")),
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    db.add(task_run)
    db.commit()
    db.refresh(task_run)

    _append_state_event(
        db,
        task_run,
        initial_state,
        {
            "adapterType": selected_adapter,
            "providerAssignment": provider_assignment.to_metadata(),
        },
    )
    if checkpoint is not None:
        append_task_run_event(
            db,
            task_run_id=task_run.id,
            event_type="task.checkpoint.created",
            payload_json=json.dumps(
                {"checkpoint": checkpoint},
                separators=(",", ":"),
            ),
        )
    if approval_payload is not None:
        append_task_run_event(
            db,
            task_run_id=task_run.id,
            event_type="approval.requested",
            payload_json=json.dumps(approval_payload, separators=(",", ":")),
        )
    return task_run


def transition_task_run(
    db: DbSession,
    task_run_id: str,
    state: str,
    payload: Optional[dict[str, Any]] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
) -> TaskRun:
    if state not in TASK_RUN_STATES:
        raise ValueError(f"Unsupported TaskRun state: {state}")

    task_run = _task_run_or_raise(db, task_run_id)
    task = _task_or_raise(db, task_run.task_id)
    now = utc_now()

    task_run.state = state
    task_run.error_code = error_code
    task_run.error_message = error_message
    task_run.updated_at = now
    if state in ACTIVE_STATES:
        _touch_task_run_heartbeat(task_run, now=now)
    if state in {"streaming", "applying_changes"} and task_run.started_at is None:
        task_run.started_at = now
    if state in TERMINAL_STATES:
        task_run.ended_at = now

    task.status = _task_status_for_run_state(state)
    task.updated_at = now
    db.add(task)
    db.add(task_run)
    db.commit()
    db.refresh(task_run)

    event_payload = dict(payload or {})
    event_payload.setdefault("state", state)
    if error_code is not None:
        event_payload.setdefault("errorCode", error_code)
    if error_message is not None:
        event_payload.setdefault("errorMessage", error_message)
    event_payload.setdefault("adapterType", adapter_type_for_run(db, task_run))
    _append_state_event(db, task_run, state, event_payload)
    if state in TERMINAL_STATES:
        from app.scheduler import mark_task_run_terminal_scheduler_state
        from app.scheduler import refresh_downstream_scheduler_state
        from app.scheduler import refresh_session_scheduler_state

        if state == "completed":
            from app.handoffs import create_dependency_handoffs

            create_dependency_handoffs(db, task_run)
        mark_task_run_terminal_scheduler_state(
            db,
            task,
            run_state=state,
            adapter_type=adapter_type_for_run(db, task_run),
            task_run_id=task_run.id,
        )
        refresh_downstream_scheduler_state(db, task.id)
        refresh_session_scheduler_state(db, task.session_id)
    return task_run


def refresh_task_run_heartbeat(
    db: DbSession,
    task_run_id: str,
    *,
    runner_id: Optional[str] = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> TaskRun:
    task_run = _task_run_or_raise(db, task_run_id)
    if task_run.state not in ACTIVE_STATES:
        raise TaskRunLifecycleError("Only active TaskRuns can refresh heartbeat.")
    if runner_id is not None and task_run.runner_id not in {None, runner_id}:
        raise TaskRunLifecycleError("Heartbeat runner does not own this TaskRun.")

    now = utc_now()
    _touch_task_run_heartbeat(
        task_run,
        now=now,
        runner_id=runner_id,
        lease_seconds=lease_seconds,
    )
    db.add(task_run)
    db.commit()
    db.refresh(task_run)
    append_task_run_event(
        db,
        task_run_id=task_run.id,
        event_type="task.heartbeat",
        payload_json=json.dumps(
            {
                "runnerId": task_run.runner_id,
                "lastHeartbeatAt": task_run.last_heartbeat_at.isoformat()
                if task_run.last_heartbeat_at is not None
                else None,
                "leaseExpiresAt": task_run.lease_expires_at.isoformat()
                if task_run.lease_expires_at is not None
                else None,
            },
            separators=(",", ":"),
        ),
    )
    return task_run


def stale_task_runs(
    db: DbSession,
    *,
    now: Optional[datetime] = None,
) -> list[TaskRun]:
    timestamp = now or utc_now()
    return db.exec(
        select(TaskRun)
        .where(TaskRun.state.in_(ACTIVE_STATES))
        .where(TaskRun.lease_expires_at.is_not(None))
        .where(TaskRun.lease_expires_at < timestamp)
        .order_by(TaskRun.updated_at, TaskRun.id)
    ).all()


def mark_stale_task_runs(
    db: DbSession,
    *,
    now: Optional[datetime] = None,
    reason: str = "lease_expired",
) -> list[TaskRun]:
    timestamp = now or utc_now()
    marked: list[TaskRun] = []
    for task_run in stale_task_runs(db, now=timestamp):
        task = _task_or_raise(db, task_run.task_id)
        previous_state = task_run.state
        task_run.state = "failed"
        task_run.error_code = "TASK_RUN_STALE"
        task_run.error_message = (
            "TaskRun heartbeat lease expired before completion; adapter success "
            "was not claimed."
        )
        task_run.stale_detected_at = timestamp
        task_run.stale_reason = reason
        task_run.ended_at = timestamp
        task_run.updated_at = timestamp
        task.status = "failed"
        task.updated_at = timestamp
        db.add(task)
        db.add(task_run)
        db.commit()
        db.refresh(task_run)

        _append_state_event(
            db,
            task_run,
            "failed",
            {
                "previousState": previous_state,
                "errorCode": task_run.error_code,
                "errorMessage": task_run.error_message,
                "runnerId": task_run.runner_id,
                "leaseExpiresAt": task_run.lease_expires_at.isoformat()
                if task_run.lease_expires_at is not None
                else None,
                "staleDetectedAt": task_run.stale_detected_at.isoformat(),
                "staleReason": reason,
            },
        )
        append_task_run_event(
            db,
            task_run_id=task_run.id,
            event_type="task.stale",
            payload_json=json.dumps(
                {
                    "previousState": previous_state,
                    "newState": "failed",
                    "runnerId": task_run.runner_id,
                    "leaseExpiresAt": task_run.lease_expires_at.isoformat()
                    if task_run.lease_expires_at is not None
                    else None,
                    "staleDetectedAt": task_run.stale_detected_at.isoformat(),
                    "reason": reason,
                    "errorCode": task_run.error_code,
                    "errorMessage": task_run.error_message,
                },
                separators=(",", ":"),
            ),
        )

        from app.scheduler import mark_task_run_terminal_scheduler_state
        from app.scheduler import refresh_downstream_scheduler_state
        from app.scheduler import refresh_session_scheduler_state

        mark_task_run_terminal_scheduler_state(
            db,
            task,
            run_state="failed",
            adapter_type=adapter_type_for_run(db, task_run),
            task_run_id=task_run.id,
        )
        refresh_downstream_scheduler_state(db, task.id)
        refresh_session_scheduler_state(db, task.session_id)
        marked.append(task_run)
    return marked


def interrupt_task_run(db: DbSession, task_run_id: str) -> TaskRun:
    task_run = _task_run_or_raise(db, task_run_id)
    if task_run.state not in ACTIVE_STATES:
        raise TaskRunLifecycleError("Only active TaskRuns can be interrupted.")

    return transition_task_run(
        db,
        task_run_id,
        "interrupted",
        payload={"reason": "Interrupted by user."},
        error_code="TASK_RUN_INTERRUPTED",
        error_message="Task run was interrupted by the user.",
    )


def retry_task_run(
    db: DbSession,
    task_run_id: str,
    *,
    retry_mode: str = "current_state",
) -> TaskRun:
    previous = _retryable_run_or_raise(db, task_run_id)
    retry_metadata = _retry_metadata_for_previous_run(
        previous,
        retry_mode=retry_mode,
    )
    return create_task_run(
        db,
        task_id=previous.task_id,
        adapter_type=adapter_type_for_run(db, previous),
        retry_of_run_id=previous.id,
        retry_metadata=retry_metadata,
    )


def retry_with_scripted_mock(db: DbSession, task_run_id: str) -> TaskRun:
    previous = _task_run_or_raise(db, task_run_id)
    if previous.state not in RETRYABLE_STATES or adapter_type_for_run(db, previous) != "codex":
        raise TaskRunLifecycleError("Fallback requires a failed or interrupted Codex run.")

    retry_metadata = _retry_metadata_for_previous_run(
        previous,
        retry_mode="scripted_mock_fallback",
    )
    return create_task_run(
        db,
        task_id=previous.task_id,
        adapter_type="scripted_mock",
        retry_of_run_id=previous.id,
        fallback_from_run_id=previous.id,
        retry_metadata=retry_metadata,
    )


def list_task_runs(db: DbSession, task_id: str) -> list[TaskRun]:
    return db.exec(
        select(TaskRun)
        .where(TaskRun.task_id == task_id)
        .order_by(TaskRun.created_at, TaskRun.id)
    ).all()


def adapter_type_for_run(db: DbSession, task_run: TaskRun) -> str:
    metrics = _metrics(task_run)
    adapter_type = metrics.get("adapterType")
    if isinstance(adapter_type, str) and adapter_type:
        return adapter_type

    agent = db.get(Agent, task_run.agent_id)
    if agent is not None:
        return agent.adapter_type
    return "unknown"


def metrics_for_run(task_run: TaskRun) -> dict[str, Any]:
    return _metrics(task_run)


def _default_adapter_for_agent(agent: Agent) -> str:
    configured = os.environ.get(DEFAULT_CODE_ADAPTER_ENV, "").strip()
    if not configured:
        return agent.adapter_type

    if configured not in SUPPORTED_CODE_ADAPTERS:
        raise TaskRunLifecycleError(
            f"Unsupported {DEFAULT_CODE_ADAPTER_ENV}: {configured}"
        )

    if agent.adapter_type == "codex" and agent.role in CODE_AGENT_ROLES:
        return configured

    return agent.adapter_type


def _retryable_run_or_raise(db: DbSession, task_run_id: str) -> TaskRun:
    previous = _task_run_or_raise(db, task_run_id)
    if previous.state not in RETRYABLE_STATES:
        raise TaskRunLifecycleError("Only failed or interrupted TaskRuns can be retried.")
    return previous


def _append_state_event(
    db: DbSession,
    task_run: TaskRun,
    state: str,
    payload: dict[str, Any],
) -> None:
    event_payload = dict(payload)
    event_payload["state"] = state
    append_task_run_event(
        db,
        task_run_id=task_run.id,
        event_type="task.state",
        payload_json=json.dumps(event_payload, separators=(",", ":")),
    )


def _new_runner_id() -> str:
    return f"local:{uuid4()}"


def _lease_expires_at(now: datetime, lease_seconds: int = DEFAULT_LEASE_SECONDS) -> datetime:
    return now + timedelta(seconds=lease_seconds)


def _touch_task_run_heartbeat(
    task_run: TaskRun,
    *,
    now: datetime,
    runner_id: Optional[str] = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> None:
    if runner_id is not None:
        task_run.runner_id = runner_id
    if task_run.runner_id is None:
        task_run.runner_id = _new_runner_id()
    task_run.last_heartbeat_at = now
    task_run.lease_expires_at = _lease_expires_at(now, lease_seconds)


def _task_status_for_run_state(state: str) -> str:
    if state == "waiting_approval":
        return "waiting_approval"
    if state == "completed":
        return "completed"
    if state == "failed":
        return "failed"
    if state == "interrupted":
        return "interrupted"
    return "running"


def _metrics(task_run: TaskRun) -> dict[str, Any]:
    try:
        value = json.loads(task_run.metrics_json)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _retry_metadata_for_previous_run(
    previous: TaskRun,
    *,
    retry_mode: str,
) -> dict[str, Any]:
    previous_metrics = _metrics(previous)
    checkpoint = previous_metrics.get("preRunCheckpoint")
    dirty_decision = _dirty_worktree_decision(previous, checkpoint)
    if dirty_decision["status"] == "unsafe":
        files = ", ".join(dirty_decision.get("unsafeFiles") or [])
        raise TaskRunLifecycleError(
            f"Unsafe retry blocked: dirty worktree contains files outside "
            f"the previous checkpoint or planned safe paths ({files})."
        )

    return {
        "previousRunId": previous.id,
        "failureSummary": {
            "state": previous.state,
            "errorCode": previous.error_code,
            "errorMessage": previous.error_message,
            "endedAt": previous.ended_at.isoformat()
            if previous.ended_at is not None
            else None,
        },
        "retryMode": retry_mode,
        "checkpointId": previous.id if isinstance(checkpoint, dict) else None,
        "dirtyWorktreeDecision": dirty_decision,
    }


def _dirty_worktree_decision(
    previous: TaskRun,
    checkpoint: Any,
) -> dict[str, Any]:
    if not isinstance(checkpoint, dict):
        return {
            "status": "safe",
            "reason": "No pre-run checkpoint was available for this legacy run.",
            "dirtyFiles": [],
            "unsafeFiles": [],
        }

    worktree_path = Path(previous.worktree_path)
    dirty_result = _git_dirty_files(worktree_path)
    if dirty_result.get("available") is not True:
        return {
            "status": "safe",
            "reason": dirty_result.get("reason") or "git_status_unavailable",
            "dirtyFiles": [],
            "unsafeFiles": [],
        }

    dirty_files = [
        path for path in dirty_result["dirtyFiles"] if isinstance(path, str)
    ]
    safe_files = {
        path
        for path in [
            *checkpoint.get("dirtyFiles", []),
            *checkpoint.get("plannedFiles", []),
        ]
        if isinstance(path, str) and path
    }
    unsafe_files = [
        path for path in dirty_files if path not in safe_files
    ]
    if unsafe_files:
        return {
            "status": "unsafe",
            "reason": "Dirty files are outside the previous checkpoint and planned safe paths.",
            "dirtyFiles": dirty_files,
            "unsafeFiles": unsafe_files,
        }
    return {
        "status": "safe",
        "reason": "Dirty files are limited to the previous checkpoint and planned safe paths.",
        "dirtyFiles": dirty_files,
        "unsafeFiles": [],
    }


def _platform_approval_payload(task: Task) -> Optional[dict[str, Any]]:
    plan = _plan_json(task)
    if (
        plan.get("targetId") == AGENTHUB_PLATFORM_TARGET_ID
        and plan.get("platformMode") is True
        and plan.get("requiresApproval") is True
    ):
        return {
            "approvalType": "security_approval",
            "reason": "AgentHub platform maintenance targets control-plane code and requires explicit approval.",
            "requestedAction": "execute platform maintenance task",
            "riskLevel": "high",
            "command": None,
            "path": plan.get("safeTarget") or "apps/api",
            "expiresAt": None,
        }
    return None


def _worktree_path_for_task(
    db: DbSession,
    task: Task,
    session: AgentHubSession,
) -> str:
    plan = _plan_json(task)
    target_id = plan.get("targetId")
    if not isinstance(target_id, str) or not target_id.startswith("external-"):
        return session.worktree_path
    try:
        target = get_target_for_workspace(db, session.workspace_id, target_id)
    except TargetRegistryError:
        return session.worktree_path
    return target.root


def _ensure_target_write_lock_available(db: DbSession, task: Task) -> None:
    from app.scheduler import (
        SCHEDULER_BLOCKED,
        SCHEDULER_WAITING_TARGET_LOCK,
        SCHEDULER_WAITING_DEPENDENCY,
        apply_scheduler_decision,
        evaluate_scheduler_readiness,
    )

    decision = evaluate_scheduler_readiness(db, task)
    if decision.state in {
        SCHEDULER_WAITING_DEPENDENCY,
        SCHEDULER_WAITING_TARGET_LOCK,
        SCHEDULER_BLOCKED,
    }:
        apply_scheduler_decision(db, task, decision)
        raise TaskRunLifecycleError(decision.reason)


def _plan_json(task: Task) -> dict[str, Any]:
    try:
        value = json.loads(task.plan_json)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _pre_run_checkpoint_for_task(
    db: DbSession,
    task: Task,
    session: AgentHubSession,
    *,
    worktree_path: str,
    base_ref: Optional[str],
    now: datetime,
) -> Optional[dict[str, Any]]:
    from app.scheduler import target_id_for_task, write_lock_required_for_task

    if not write_lock_required_for_task(task):
        return None

    target_id = target_id_for_task(task, db)
    if target_id is None:
        return None

    try:
        target = get_target_for_workspace(db, session.workspace_id, target_id)
    except TargetRegistryError:
        return None

    plan = _plan_json(task)
    planned_files = [
        path for path in plan.get("files", []) if isinstance(path, str) and path
    ]
    contract = plan.get("appContract")
    contract_id = plan.get("contractId")
    if not isinstance(contract_id, str) and isinstance(contract, dict):
        contract_id = contract.get("contractId")

    git_status = _git_status_checkpoint(
        Path(worktree_path),
        allowed_paths=list(target.allowed_paths),
        denied_paths=list(target.denied_paths),
    )
    return {
        "targetId": target.target_id,
        "targetRoot": target.root,
        "allowedPaths": list(target.allowed_paths),
        "deniedPaths": list(target.denied_paths),
        "baseCommit": base_ref,
        "gitStatus": git_status,
        "dirtyFiles": git_status["dirtyFiles"],
        "plannedFiles": planned_files,
        "contractId": contract_id if isinstance(contract_id, str) else None,
        "contractHash": _contract_hash(contract),
        "createdAt": now.isoformat(),
    }


def _git_status_checkpoint(
    worktree_path: Path,
    *,
    allowed_paths: list[str],
    denied_paths: list[str],
) -> dict[str, Any]:
    dirty_result = _git_dirty_files(worktree_path)
    if dirty_result.get("available") is not True:
        return dirty_result

    dirty_files = dirty_result["dirtyFiles"]
    scoped_dirty_files = [
        path
        for path in dirty_files
        if _matches_any_path(path, allowed_paths) and not _matches_any_path(path, denied_paths)
    ]
    return {
        "available": True,
        "dirtyFiles": scoped_dirty_files,
    }


def _git_dirty_files(worktree_path: Path) -> dict[str, Any]:
    if not worktree_path.exists():
        return {
            "available": False,
            "reason": "worktree_not_found",
            "dirtyFiles": [],
        }
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return {
            "available": False,
            "reason": str(exc),
            "dirtyFiles": [],
        }
    if result.returncode != 0:
        return {
            "available": False,
            "reason": result.stderr.strip() or result.stdout.strip() or "git_status_failed",
            "dirtyFiles": [],
        }
    return {
        "available": True,
        "dirtyFiles": _parse_porcelain_dirty_files(result.stdout),
    }


def _parse_porcelain_dirty_files(output: str) -> list[str]:
    files: list[str] = []
    for line in output.splitlines():
        if not line:
            continue
        path = line[3:] if len(line) > 3 else line
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip()
        if path:
            files.append(path)
    return files


def _contract_hash(contract: Any) -> Optional[str]:
    if not isinstance(contract, dict):
        return None
    normalized = json.dumps(contract, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _matches_any_path(path: str, patterns: list[str]) -> bool:
    normalized = _normalize_path(path)
    return any(_matches_path_pattern(normalized, pattern) for pattern in patterns)


def _matches_path_pattern(path: str, pattern: str) -> bool:
    normalized_pattern = _normalize_path(pattern)
    if not normalized_pattern:
        return False
    if normalized_pattern.endswith("*"):
        return path.startswith(normalized_pattern[:-1])
    if "/" not in normalized_pattern:
        return normalized_pattern in path.split("/")
    return path == normalized_pattern or path.startswith(f"{normalized_pattern}/")


def _normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.rstrip("/")


def _task_or_raise(db: DbSession, task_id: str) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise TaskRunLifecycleError(f"Task not found: {task_id}")
    return task


def _session_or_raise(db: DbSession, session_id: str) -> AgentHubSession:
    session = db.get(AgentHubSession, session_id)
    if session is None:
        raise TaskRunLifecycleError(f"Session not found: {session_id}")
    return session


def _agent_or_raise(db: DbSession, agent_id: Optional[str]) -> Agent:
    if agent_id is None:
        raise TaskRunLifecycleError("Task has no assigned agent.")
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise TaskRunLifecycleError(f"Agent not found: {agent_id}")
    return agent


def _task_run_or_raise(db: DbSession, task_run_id: str) -> TaskRun:
    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        raise TaskRunLifecycleError(f"TaskRun not found: {task_run_id}")
    return task_run
