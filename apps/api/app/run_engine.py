import asyncio
import json
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from fastapi import BackgroundTasks
from sqlmodel import Session as DbSession
from sqlmodel import select

from app.adapters import AgentAdapter, AgentRunRequest, run_adapter_event_stream
from app.claude_code_adapter import ClaudeCodeAdapter
from app.codex_adapter import CodexAdapter
from app.context_pack import build_session_context_pack
from app.deployments import DeployError, DeployService
from app.diffs import collect_task_run_diff
from app.instruction_builder import build_role_instruction
from app.ledger import refresh_session_ledger_for_task_run
from app.models import Agent, Task, TaskRun
from app.models import Session as AgentHubSession
from app.models import utc_now
from app.previews import PreviewError, PreviewService
from app.provider_gateway import (
    CodingRunContext,
    ProviderConcurrencyLimiter,
    ProviderHealthProbe,
    ProviderResolver,
    record_provider_capacity_event,
    record_provider_health_check,
    record_provider_resolution,
)
from app.repositories import list_session_tasks
from app.reviews import create_scripted_review_for_task_run, list_task_run_reviews
from app.run_supervisor import RunSupervisor, default_run_supervisor
from app.scheduler import SCHEDULER_WAITING_TARGET_LOCK, evaluate_and_apply_scheduler_readiness
from app.scheduler import target_id_for_task, write_lock_required_for_task
from app.session_queue import (
    mark_task_run_running,
    mark_task_run_waiting_lock,
    queue_gate_for_task_run,
)
from app.scripted_mock import ScriptedMockAdapter
from app.target_locks import acquire_target_lock
from app.task_runs import (
    TaskRunLifecycleError,
    adapter_type_for_run,
    claim_task_run_for_worker,
    create_task_run,
    list_task_runs,
    mark_stale_task_runs,
    metrics_for_run,
    refresh_task_run_heartbeat,
    transition_task_run,
)

_preview_service = PreviewService()
_deploy_service = DeployService()
_provider_resolver = ProviderResolver()
_provider_health_probe = ProviderHealthProbe()
_provider_capacity_limiter = ProviderConcurrencyLimiter()
DEFAULT_RUN_WORKER_ID_PREFIX = "worker"


def get_preview_service() -> PreviewService:
    return _preview_service


def get_deploy_service() -> DeployService:
    return _deploy_service


def schedule_task_run_execution(
    background_tasks: BackgroundTasks,
) -> None:
    background_tasks.add_task(_background_run_worker_once)


class RunWorker:
    def __init__(self, *, worker_id: Optional[str] = None) -> None:
        self.worker_id = worker_id or _new_worker_id()

    async def run_once(self, db: DbSession) -> Optional[TaskRun]:
        for task_run in queued_task_runs(db):
            adapter_type = adapter_type_for_run(db, task_run)
            executed = await execute_task_run_background(
                db,
                task_run.id,
                adapter_type,
                worker_id=self.worker_id,
            )
            if executed:
                return db.get(TaskRun, task_run.id)
        return None

    def recover_stale_runs(self, db: DbSession, *, reason: str = "worker_startup") -> dict[str, Any]:
        from app.session_queue import recover_queue_entries
        from app.target_locks import recover_stale_target_locks

        recovered_entries = recover_queue_entries(db)
        recovered_locks = recover_stale_target_locks(db)
        marked = mark_stale_task_runs(db, reason=reason)
        return {
            "workerId": self.worker_id,
            "reason": reason,
            "staleRunIds": [run.id for run in marked],
            "staleRunCount": len(marked),
            "recoveredQueueEntryIds": [entry.id for entry in recovered_entries],
            "recoveredLockKeys": [lock.lock_key for lock in recovered_locks],
        }


def next_queued_task_run(db: DbSession) -> Optional[TaskRun]:
    return queued_task_runs(db)[0] if queued_task_runs(db) else None


def queued_task_runs(db: DbSession) -> list[TaskRun]:
    return db.exec(
        select(TaskRun)
        .where(TaskRun.state == "queued")
        .order_by(TaskRun.created_at, TaskRun.id)
    ).all()


def agent_run_request_for(
    db: DbSession,
    task_run: TaskRun,
    *,
    adapter_type: str,
    plan_context: Optional[dict[str, Any]] = None,
) -> AgentRunRequest:
    task = db.get(Task, task_run.task_id)
    if task is None:
        raise TaskRunLifecycleError(f"Task not found: {task_run.task_id}")
    session = db.get(AgentHubSession, task.session_id)
    if session is None:
        raise TaskRunLifecycleError(f"Session not found: {task.session_id}")
    agent = db.get(Agent, task_run.agent_id)
    if agent is None:
        raise TaskRunLifecycleError(f"Agent not found: {task_run.agent_id}")
    task_plan = plan_json_for_task(task)
    merged_plan_context = dict(task_plan)
    if plan_context:
        merged_plan_context.update(plan_context)
    context_pack = build_session_context_pack(
        db,
        task,
        plan_context=merged_plan_context,
    )
    _persist_context_snapshot(db, task_run, context_pack)
    merged_plan_context["sessionContext"] = context_pack
    return AgentRunRequest(
        taskRunId=task_run.id,
        sessionId=session.id,
        workspaceId=session.workspace_id,
        worktreePath=task_run.worktree_path,
        agentId=task_run.agent_id,
        adapterType=adapter_type,
        instruction=build_role_instruction(
            task,
            agent,
            context_pack,
            adapter_type=adapter_type,
        ),
        planContext=merged_plan_context,
        permissionProfile={"network": "off"},
        demoMode=True,
        fallbackPolicy="scripted_mock" if adapter_type == "scripted_mock" else "none",
    )


def _persist_context_snapshot(
    db: DbSession,
    task_run: TaskRun,
    context_pack: dict[str, Any],
) -> None:
    canonical_context = context_pack.get("canonicalContext")
    if not isinstance(canonical_context, dict):
        return
    metrics = metrics_for_run(task_run)
    metrics["canonicalContextSnapshot"] = canonical_context
    task_run.metrics_json = json.dumps(metrics, separators=(",", ":"))
    task_run.updated_at = utc_now()
    db.add(task_run)
    expire_on_commit = getattr(db, "expire_on_commit", True)
    db.expire_on_commit = False
    try:
        db.commit()
        db.refresh(task_run)
    finally:
        db.expire_on_commit = expire_on_commit


def plan_json_for_task(task: Task) -> dict[str, Any]:
    try:
        plan = json.loads(task.plan_json)
    except json.JSONDecodeError:
        return {}
    return plan if isinstance(plan, dict) else {}


def adapter_for_type(
    adapter_type: str,
    *,
    codex_adapter: AgentAdapter,
    claude_code_adapter: AgentAdapter,
    scripted_mock_adapter: AgentAdapter,
) -> AgentAdapter:
    if adapter_type == "codex":
        return codex_adapter
    if adapter_type == "claude_code":
        return claude_code_adapter
    if adapter_type == "scripted_mock":
        return scripted_mock_adapter
    raise TaskRunLifecycleError(f"Unsupported adapter type: {adapter_type}")


async def execute_task_run(
    db: DbSession,
    task_run: TaskRun,
    *,
    adapter_type: str,
    adapter: AgentAdapter,
    plan_context: Optional[dict[str, Any]] = None,
    supervisor: RunSupervisor = default_run_supervisor,
    max_runtime_seconds: Optional[float] = None,
) -> TaskRun:
    request = agent_run_request_for(
        db,
        task_run,
        adapter_type=adapter_type,
        plan_context=plan_context,
    )
    supervisor.register(
        task_run_id=task_run.id,
        adapter_type=adapter_type,
        adapter_run_id=task_run.adapter_run_id,
        adapter=adapter,
    )
    try:
        capabilities = adapter.getCapabilities()
        stream = run_adapter_event_stream(
            db,
            adapter,
            request,
            on_adapter_run_created=lambda run: supervisor.update_adapter_run_id(
                task_run.id,
                run.adapter_run_id,
            ),
        )
        runtime_timeout = (
            max_runtime_seconds
            if max_runtime_seconds is not None
            else capabilities.max_runtime_sec
        )
        if runtime_timeout is not None:
            await asyncio.wait_for(stream, timeout=runtime_timeout)
        else:
            await stream
    except asyncio.TimeoutError:
        await supervisor.interrupt(task_run.id)
        transition_task_run(
            db,
            task_run.id,
            "failed",
            payload={"reason": "TaskRun exceeded max runtime."},
            error_code="TASK_RUN_TIMEOUT",
            error_message="TaskRun exceeded its maximum runtime.",
        )
    finally:
        supervisor.unregister(task_run.id)
    db.refresh(task_run)
    if task_run.state == "completed":
        await finalize_completed_task_run(db, task_run)
    return task_run


async def finalize_completed_task_run(
    db: DbSession,
    task_run: TaskRun,
) -> TaskRun:
    collect_task_run_diff(db, task_run.id)
    create_scripted_review_for_task_run(db, task_run.id)
    refresh_session_ledger_for_task_run(db, task_run.id)
    _complete_ready_pipeline_review_tasks(db, task_run.task_id)
    _maybe_auto_preview_and_mock_deploy(db, task_run)
    await _auto_start_next_pipeline_task(db, task_run.task_id)
    db.refresh(task_run)
    return task_run


async def _auto_start_next_pipeline_task(
    db: DbSession,
    completed_task_id: str,
) -> Optional[TaskRun]:
    completed_task = db.get(Task, completed_task_id)
    if completed_task is None:
        return None
    for task in list_session_tasks(db, completed_task.session_id):
        if not _is_auto_pipeline_task(task):
            continue
        if _has_task_run(db, task.id):
            continue
        decision = evaluate_and_apply_scheduler_readiness(db, task)
        if not decision.runnable:
            continue
        task_run = create_task_run(db, task.id)
        adapter_type = adapter_type_for_run(db, task_run)
        adapter = adapter_for_type(
            adapter_type,
            codex_adapter=CodexAdapter(),
            claude_code_adapter=ClaudeCodeAdapter(),
            scripted_mock_adapter=ScriptedMockAdapter(),
        )
        return await execute_task_run(
            db,
            task_run,
            adapter_type=adapter_type,
            adapter=adapter,
        )
    return None


def _complete_ready_pipeline_review_tasks(
    db: DbSession,
    completed_task_id: str,
) -> list[Task]:
    completed_task = db.get(Task, completed_task_id)
    if completed_task is None:
        return []

    completed: list[Task] = []
    for task in list_session_tasks(db, completed_task.session_id):
        if task.intent_type not in {"review", "qa_review"}:
            continue
        if task.status not in {"pending", "waiting_dependency"}:
            continue
        plan = plan_json_for_task(task)
        if plan.get("planner") not in {"contract_first_v1", "llm_v1"}:
            continue
        if not _dependencies_have_review_artifacts(db, task):
            continue
        decision = evaluate_and_apply_scheduler_readiness(db, task)
        if not decision.runnable:
            continue
        plan = plan_json_for_task(task)
        scheduler = dict(plan.get("scheduler") or {})
        scheduler.update(
            {
                "state": "completed",
                "runnable": False,
                "reason": "Planned review was satisfied by the generated review artifact.",
            }
        )
        plan["scheduler"] = scheduler
        task.plan_json = json.dumps(plan, separators=(",", ":"))
        task.status = "completed"
        task.updated_at = utc_now()
        db.add(task)
        db.commit()
        db.refresh(task)
        completed.append(task)
    return completed


def _dependencies_have_review_artifacts(db: DbSession, task: Task) -> bool:
    try:
        dependency_ids = json.loads(task.depends_on_task_ids)
    except json.JSONDecodeError:
        return False
    if not isinstance(dependency_ids, list) or not dependency_ids:
        return False

    for dependency_id in dependency_ids:
        if not isinstance(dependency_id, str):
            return False
        dependency_runs = list_task_runs(db, dependency_id)
        completed_runs = [run for run in dependency_runs if run.state == "completed"]
        if not completed_runs:
            return False
        if not any(list_task_run_reviews(db, run.id) for run in completed_runs):
            return False
    return True


def _maybe_auto_preview_and_mock_deploy(db: DbSession, task_run: TaskRun) -> None:
    task = db.get(Task, task_run.task_id)
    if task is None or task.intent_type != "frontend_change":
        return
    plan = plan_json_for_task(task)
    if plan.get("planner") != "contract_first_v1":
        return
    demo_root = Path(task_run.worktree_path) / "apps/demo"
    if not demo_root.exists():
        return
    from app.preview_deploy_jobs import (
        enqueue_deploy_job,
        enqueue_preview_job,
        run_deploy_job,
        run_preview_job,
    )

    preview_job = enqueue_preview_job(db, task_run)
    if preview_job is None:
        return
    preview_job = run_preview_job(db, preview_job, preview_service=_preview_service)
    if preview_job.state != "completed":
        return
    evidence = json.loads(preview_job.evidence_json)
    preview_id = evidence.get("previewId")
    if not isinstance(preview_id, str):
        return
    deploy_job = enqueue_deploy_job(db, task_run.id, preview_id)
    run_deploy_job(db, deploy_job, deploy_service=_deploy_service)
    refresh_session_ledger_for_task_run(db, task_run.id)


def _is_auto_pipeline_task(task: Task) -> bool:
    plan = plan_json_for_task(task)
    return (
        plan.get("planner") == "contract_first_v1"
        and plan.get("autoStart") is True
        and task.intent_type in {"backend_change", "frontend_change"}
    )


def _has_task_run(db: DbSession, task_id: str) -> bool:
    return bool(list_task_runs(db, task_id))


async def _background_execute_task_run(
    task_run_id: str,
    adapter_type: str,
) -> None:
    from app.db import engine as db_engine

    with DbSession(db_engine) as db:
        await execute_task_run_background(db, task_run_id, adapter_type)


async def _background_run_worker_once() -> None:
    from app.db import engine as db_engine

    with DbSession(db_engine) as db:
        await RunWorker().run_once(db)


async def execute_task_run_background(
    db: DbSession,
    task_run_id: str,
    adapter_type: str,
    *,
    worker_id: Optional[str] = None,
) -> bool:
    worker_id = worker_id or _new_worker_id()
    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        return False
    try:
        if task_run.state == "queued":
            task_run = claim_task_run_for_worker(
                db,
                task_run.id,
                worker_id=worker_id,
            )
            if not _prepare_claimed_task_run_for_adapter(db, task_run, worker_id):
                return False
        refresh_task_run_heartbeat(
            db,
            task_run.id,
            runner_id=task_run.runner_id,
        )
        gateway = _resolve_provider_gateway_for_run(db, task_run, adapter_type)
        adapter_type = gateway["adapter_type"]
        adapter = adapter_for_type(
            adapter_type,
            codex_adapter=CodexAdapter(),
            claude_code_adapter=ClaudeCodeAdapter(),
            scripted_mock_adapter=ScriptedMockAdapter(),
        )
        await execute_task_run(
            db,
            task_run,
            adapter_type=adapter_type,
            adapter=adapter,
        )
        return True
    except Exception:
        db.refresh(task_run)
        if task_run.state not in {"completed", "failed", "interrupted"}:
            try:
                transition_task_run(
                    db,
                    task_run_id,
                    "failed",
                    error_code="ADAPTER_EXECUTION_ERROR",
                    error_message="Adapter execution failed unexpectedly.",
                )
            except Exception:
                pass
        return True
    finally:
        _release_provider_capacity(db, task_run_id)


def _prepare_claimed_task_run_for_adapter(
    db: DbSession,
    task_run: TaskRun,
    worker_id: str,
) -> bool:
    task = db.get(Task, task_run.task_id)
    if task is None:
        return False
    decision = evaluate_and_apply_scheduler_readiness(db, task)
    if not decision.runnable:
        if decision.state == SCHEDULER_WAITING_TARGET_LOCK:
            mark_task_run_waiting_lock(db, task_run.id, decision.reason)
        return False
    queue_decision = queue_gate_for_task_run(db, task_run.id)
    if not queue_decision.runnable:
        return False
    if not write_lock_required_for_task(task):
        mark_task_run_running(db, task_run.id, queue_decision.reason)
        return True
    target_id = target_id_for_task(task, db)
    if target_id is None:
        mark_task_run_running(
            db,
            task_run.id,
            "Legacy write TaskRun has no target id; preserving existing demo path.",
        )
        return True
    result = acquire_target_lock(
        db,
        target_id=target_id,
        session_id=task.session_id,
        task_run_id=task_run.id,
        worker_id=worker_id,
        lease_expires_at=task_run.lease_expires_at,
    )
    if not result.acquired:
        mark_task_run_waiting_lock(db, task_run.id, result.reason)
        evaluate_and_apply_scheduler_readiness(db, task)
        return False
    mark_task_run_running(db, task_run.id, "Target write lock acquired.")
    return True


def _resolve_provider_gateway_for_run(
    db: DbSession,
    task_run: TaskRun,
    fallback_adapter_type: str,
) -> dict[str, str]:
    task = db.get(Task, task_run.task_id)
    if task is None:
        raise TaskRunLifecycleError(f"Task not found: {task_run.task_id}")
    session = db.get(AgentHubSession, task.session_id)
    if session is None:
        raise TaskRunLifecycleError(f"Session not found: {task.session_id}")
    target_id = target_id_for_task(task, db)
    context = CodingRunContext(
        workspace_id=session.workspace_id,
        session_id=session.id,
        task_id=task.id,
        task_run_id=task_run.id,
        role=_role_for_task_run(db, task_run),
        target_id=target_id,
        mode="write" if write_lock_required_for_task(task) else "review",
        required_capabilities=("file_edit",)
        if write_lock_required_for_task(task)
        else ("review",),
        worktree_path=task_run.worktree_path,
        runtime_adapter_type=fallback_adapter_type,
        fallback_policy="scripted_mock",
    )
    plan = _provider_resolver.resolve(context)
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
    provider = _provider_resolver.registry.get(plan.selected_provider_id)
    if provider is not None:
        health = _provider_health_probe.check_provider(provider, context=context)
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
    capacity = _provider_capacity_limiter.acquire(plan.selected_provider_id, task_run.id)
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


def _release_provider_capacity(db: DbSession, task_run_id: str) -> None:
    release = _provider_capacity_limiter.release(task_run_id)
    if release.provider_id == "unknown":
        return
    record_provider_capacity_event(
        db,
        task_run_id=task_run_id,
        capacity=release,
        released=True,
    )


def _role_for_task_run(db: DbSession, task_run: TaskRun) -> str:
    agent = db.get(Agent, task_run.agent_id)
    return agent.role if agent is not None else "frontend"


def _new_worker_id() -> str:
    return f"{DEFAULT_RUN_WORKER_ID_PREFIX}:{uuid4()}"


async def interrupt_supervised_task_run(
    task_run_id: str,
    *,
    supervisor: RunSupervisor = default_run_supervisor,
) -> bool:
    return await supervisor.interrupt(task_run_id)
