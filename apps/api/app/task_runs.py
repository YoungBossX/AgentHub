import json
import os
from typing import Any, Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.events import append_task_run_event
from app.diffs import capture_base_ref_for_worktree
from app.models import Agent, Task, TaskRun
from app.models import Session as AgentHubSession
from app.models import utc_now
from app.target_registry import AGENTHUB_PLATFORM_TARGET_ID

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


class TaskRunLifecycleError(ValueError):
    pass


def create_task_run(
    db: DbSession,
    task_id: str,
    adapter_type: Optional[str] = None,
    retry_of_run_id: Optional[str] = None,
    fallback_from_run_id: Optional[str] = None,
) -> TaskRun:
    task = _task_or_raise(db, task_id)
    session = _session_or_raise(db, task.session_id)
    agent = _agent_or_raise(db, task.assigned_agent_id)
    selected_adapter = adapter_type or _default_adapter_for_agent(agent)
    _ensure_target_write_lock_available(db, task)

    now = utc_now()
    metrics = {
        "adapterType": selected_adapter,
    }
    if retry_of_run_id is not None:
        metrics["retryOfRunId"] = retry_of_run_id
    if fallback_from_run_id is not None:
        metrics["fallbackFromRunId"] = fallback_from_run_id

    approval_payload = _platform_approval_payload(task)
    initial_state = "waiting_approval" if approval_payload is not None else "queued"
    task.status = _task_status_for_run_state(initial_state)
    task.updated_at = now
    task_run = TaskRun(
        task_id=task.id,
        agent_id=agent.id,
        state=initial_state,
        worktree_path=session.worktree_path,
        base_ref=capture_base_ref_for_worktree(session.worktree_path),
        metrics_json=json.dumps(metrics, separators=(",", ":")),
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    db.add(task_run)
    db.commit()
    db.refresh(task_run)

    _append_state_event(db, task_run, initial_state, {"adapterType": selected_adapter})
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
        from app.scheduler import refresh_downstream_scheduler_state
        from app.scheduler import refresh_session_scheduler_state

        refresh_downstream_scheduler_state(db, task.id)
        refresh_session_scheduler_state(db, task.session_id)
    return task_run


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


def retry_task_run(db: DbSession, task_run_id: str) -> TaskRun:
    previous = _retryable_run_or_raise(db, task_run_id)
    return create_task_run(
        db,
        task_id=previous.task_id,
        adapter_type=adapter_type_for_run(db, previous),
        retry_of_run_id=previous.id,
    )


def retry_with_scripted_mock(db: DbSession, task_run_id: str) -> TaskRun:
    previous = _task_run_or_raise(db, task_run_id)
    if previous.state not in RETRYABLE_STATES or adapter_type_for_run(db, previous) != "codex":
        raise TaskRunLifecycleError("Fallback requires a failed or interrupted Codex run.")

    return create_task_run(
        db,
        task_id=previous.task_id,
        adapter_type="scripted_mock",
        retry_of_run_id=previous.id,
        fallback_from_run_id=previous.id,
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


def _ensure_target_write_lock_available(db: DbSession, task: Task) -> None:
    from app.scheduler import (
        SCHEDULER_BLOCKED,
        SCHEDULER_WAITING_TARGET_LOCK,
        apply_scheduler_decision,
        evaluate_target_lock_readiness,
    )

    decision = evaluate_target_lock_readiness(db, task)
    if decision.state in {SCHEDULER_WAITING_TARGET_LOCK, SCHEDULER_BLOCKED}:
        apply_scheduler_decision(db, task, decision)
        raise TaskRunLifecycleError(decision.reason)


def _plan_json(task: Task) -> dict[str, Any]:
    try:
        value = json.loads(task.plan_json)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


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
