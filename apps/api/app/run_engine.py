import json
from pathlib import Path
from typing import Any, Optional

from fastapi import BackgroundTasks
from sqlmodel import Session as DbSession

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
from app.repositories import list_session_tasks
from app.reviews import create_scripted_review_for_task_run, list_task_run_reviews
from app.run_supervisor import RunSupervisor, default_run_supervisor
from app.scheduler import evaluate_and_apply_scheduler_readiness
from app.scripted_mock import ScriptedMockAdapter
from app.task_runs import (
    TaskRunLifecycleError,
    adapter_type_for_run,
    create_task_run,
    list_task_runs,
    metrics_for_run,
    transition_task_run,
)

_preview_service = PreviewService()
_deploy_service = DeployService()


def get_preview_service() -> PreviewService:
    return _preview_service


def get_deploy_service() -> DeployService:
    return _deploy_service


def schedule_task_run_execution(
    background_tasks: BackgroundTasks,
    task_run_id: str,
    adapter_type: str,
) -> None:
    background_tasks.add_task(
        _background_execute_task_run,
        task_run_id,
        adapter_type,
    )


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
    )
    try:
        await run_adapter_event_stream(db, adapter, request)
    finally:
        supervisor.unregister(task_run.id)
    db.refresh(task_run)
    if task_run.state == "completed":
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
    try:
        preview = _preview_service.start_task_run_preview(db, task_run.id)
        if preview.health_status != "healthy":
            return
        _deploy_service.create_mock_deployment(db, preview.id)
        refresh_session_ledger_for_task_run(db, task_run.id)
    except (PreviewError, DeployError):
        return


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

    adapter = adapter_for_type(
        adapter_type,
        codex_adapter=CodexAdapter(),
        claude_code_adapter=ClaudeCodeAdapter(),
        scripted_mock_adapter=ScriptedMockAdapter(),
    )
    with DbSession(db_engine) as db:
        task_run = db.get(TaskRun, task_run_id)
        if task_run is None:
            return
        try:
            await execute_task_run(
                db,
                task_run,
                adapter_type=adapter_type,
                adapter=adapter,
            )
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
