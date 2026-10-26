"""Provider selection, health and capacity using engine-owned service instances."""
from collections.abc import Callable

from sqlmodel import Session as DbSession
from app.models import Task, TaskRun
from app.models import Session as AgentHubSession
from app.provider_gateway import (
    CodingRunContext, ProviderConcurrencyLimiter, ProviderHealthProbe, ProviderResolver,
    record_provider_capacity_event, record_provider_health_check, record_provider_resolution,
)
from app.scheduler import target_id_for_task, write_lock_required_for_task
from app.task_runs import TaskRunLifecycleError, metrics_for_run, transition_task_run


def _resolve_provider_gateway_for_run(
    db: DbSession,
    task_run: TaskRun,
    fallback_adapter_type: str,
    *, resolver: ProviderResolver, health_probe: ProviderHealthProbe,
    capacity_limiter: ProviderConcurrencyLimiter, role_for_run: Callable[[DbSession, TaskRun], str],
) -> dict[str, str]:
    task = db.get(Task, task_run.task_id)
    if task is None:
        raise TaskRunLifecycleError(f"Task not found: {task_run.task_id}")
    session = db.get(AgentHubSession, task.session_id)
    if session is None:
        raise TaskRunLifecycleError(f"Session not found: {task.session_id}")
    target_id = target_id_for_task(task, db)
    metrics = metrics_for_run(task_run)
    runtime_resolution = metrics.get("runtimeConfigResolution")
    provider_assignment = metrics.get("providerAssignment")
    runtime_provider_id = None
    if isinstance(runtime_resolution, dict):
        candidate_provider_id = runtime_resolution.get("providerId")
        if isinstance(candidate_provider_id, str) and candidate_provider_id:
            runtime_provider_id = candidate_provider_id
    if runtime_provider_id is None and isinstance(provider_assignment, dict):
        candidate_provider_id = provider_assignment.get("providerId")
        if isinstance(candidate_provider_id, str) and candidate_provider_id:
            runtime_provider_id = candidate_provider_id
    selection = metrics.get("agentSelection")
    custom = selection.get("customProfile") if isinstance(selection, dict) else None
    read_only_custom = isinstance(custom, dict) and custom.get("toolPolicy") == "claude_read_only"
    required_capabilities = () if read_only_custom else (
        ("file_edit",) if write_lock_required_for_task(task) else ("review",)
    )
    context = CodingRunContext(
        workspace_id=session.workspace_id,
        session_id=session.id,
        task_id=task.id,
        task_run_id=task_run.id,
        role=custom["role"] if isinstance(custom, dict) else role_for_run(db, task_run),
        target_id=target_id,
        mode="write" if write_lock_required_for_task(task) else "review",
        required_capabilities=required_capabilities,
        worktree_path=task_run.worktree_path,
        runtime_provider_id=runtime_provider_id,
        runtime_adapter_type=fallback_adapter_type,
        fallback_policy="scripted_mock",
    )
    plan = resolver.resolve(context)
    record_provider_resolution(db, task_run_id=task_run.id, plan=plan)
    if plan.selected_provider_id is None or plan.selected_adapter_type is None:
        transition_task_run(
            db,
            task_run.id,
            "failed",
            error_code="PROVIDER_RESOLUTION_FAILED",
            error_message=plan.selection_reason,
        )
        raise TaskRunLifecycleError(plan.selection_reason)
    provider = resolver.registry.get(plan.selected_provider_id)
    if provider is not None:
        health = health_probe.check_provider(provider, context=context)
        record_provider_health_check(db, task_run_id=task_run.id, health=health)
        if not health.available and provider.is_real_provider:
            transition_task_run(
                db,
                task_run.id,
                "failed",
                error_code="PROVIDER_UNAVAILABLE",
                error_message=health.reason,
            )
            raise TaskRunLifecycleError(health.reason)
    capacity = capacity_limiter.acquire(plan.selected_provider_id, task_run.id)
    record_provider_capacity_event(db, task_run_id=task_run.id, capacity=capacity)
    if not capacity.acquired:
        transition_task_run(
            db,
            task_run.id,
            "failed",
            error_code="PROVIDER_CAPACITY_EXHAUSTED",
            error_message=capacity.reason or "Provider capacity is exhausted.",
        )
        raise TaskRunLifecycleError(capacity.reason or "Provider capacity is exhausted.")
    return {"adapter_type": plan.selected_adapter_type}


def _release_provider_capacity(
    db: DbSession, task_run_id: str, *, capacity_limiter: ProviderConcurrencyLimiter,
) -> None:
    release = capacity_limiter.release(task_run_id)
    if release.provider_id == "unknown":
        return
    record_provider_capacity_event(
        db,
        task_run_id=task_run_id,
        capacity=release,
        released=True,
    )
