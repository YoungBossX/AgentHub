"""Post-completion pipeline coordination; execution ownership stays in run_engine."""
from collections.abc import Awaitable, Callable
import json
from pathlib import Path
from typing import Any, Optional

from sqlmodel import Session as DbSession
from app.deployments import DeployService
from app.ledger import refresh_session_ledger_for_task_run
from app.models import Artifact, Task, TaskRun, utc_now
from app.previews import PreviewService
from app.repositories import list_session_tasks
from app.reviews import list_task_run_reviews
from app.scheduler import evaluate_and_apply_scheduler_readiness
from app.task_runs import adapter_type_for_run, create_task_run, list_task_runs

AUTO_PIPELINE_PLANNERS = {"contract_first_v1", "orchestrator_external_target_v1", "dynamic_manager_v1"}
GENERATED_REVIEW_PLANNERS = {
    "contract_first_v1", "llm_v1", "deterministic_login_v1", "dynamic_manager_v1",
}


def plan_json_for_task(task: Task) -> dict[str, Any]:
    try:
        plan = json.loads(task.plan_json)
    except json.JSONDecodeError:
        return {}
    return plan if isinstance(plan, dict) else {}


async def _auto_start_next_pipeline_task(
    db: DbSession,
    completed_task_id: str,
    *, start_run: Callable[..., Awaitable[Any]],
) -> Optional[TaskRun]:
    completed_task = db.get(Task, completed_task_id)
    if completed_task is None:
        return None
    for task in list_session_tasks(db, completed_task.session_id):
        if task.id == completed_task_id:
            continue
        # Group continuation belongs to the dispatcher. Recursive execution here
        # would retain the upstream provider slot until all descendants finish.
        if plan_json_for_task(task).get("planner") == "explicit_group_v1":
            continue
        if not _is_auto_pipeline_task(task):
            continue
        if _has_task_run(db, task.id):
            continue
        decision = evaluate_and_apply_scheduler_readiness(db, task)
        if not decision.runnable:
            continue
        task_run = create_task_run(db, task.id)
        adapter_type = adapter_type_for_run(db, task_run)
        await start_run(
            db,
            task_run.id,
            adapter_type,
        )
        return db.get(TaskRun, task_run.id)
    return None


def complete_ready_session_review_tasks(
    db: DbSession, session_id: str, *,
    review_evidence_for_task: Callable[[DbSession, Task], list[dict[str, Any]]],
) -> list[Task]:
    completed: list[Task] = []
    for task in list_session_tasks(db, session_id):
        if task.intent_type not in {"review", "qa_review"}:
            continue
        if task.status not in {"pending", "waiting_dependency", "blocked"}:
            continue
        plan = plan_json_for_task(task)
        if plan.get("planner") not in GENERATED_REVIEW_PLANNERS:
            continue
        if _has_task_run(db, task.id):
            continue
        review_evidence = review_evidence_for_task(db, task)
        if not review_evidence:
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
        plan["reviewSatisfaction"] = {
            "source": "generated_review_artifacts",
            "reports": review_evidence,
        }
        task.plan_json = json.dumps(plan, separators=(",", ":"))
        task.status = "completed"
        task.updated_at = utc_now()
        db.add(task)
        db.commit()
        db.refresh(task)
        completed.append(task)
    return completed


def _dependency_review_evidence(db: DbSession, task: Task) -> list[dict[str, Any]]:
    try:
        dependency_ids = json.loads(task.depends_on_task_ids)
    except json.JSONDecodeError:
        return []
    if not isinstance(dependency_ids, list) or not dependency_ids:
        return []

    evidence: list[dict[str, Any]] = []
    for dependency_id in dependency_ids:
        if not isinstance(dependency_id, str):
            return []
        dependency = db.get(Task, dependency_id)
        if dependency is None or dependency.session_id != task.session_id:
            return []
        dependency_runs = list_task_runs(db, dependency_id)
        if not dependency_runs or dependency_runs[-1].state != "completed":
            return []
        run = dependency_runs[-1]
        reviews = list_task_run_reviews(db, run.id)
        if not reviews:
            return []
        review = reviews[-1]
        diff_artifact = db.get(Artifact, review.reviewed_diff_artifact_id)
        if (
            diff_artifact is None
            or diff_artifact.artifact_type != "diff"
            or diff_artifact.task_run_id != run.id
        ):
            return []
        # Advisory report completion is independent of its passed/warning/failed verdict.
        evidence.append({
            "taskId": dependency_id, "taskRunId": run.id,
            "reviewArtifactId": review.artifact_id,
            "reviewedDiffArtifactId": diff_artifact.id,
            "status": review.status, "adapterType": review.adapter_type,
            **({"qaAssessment": review.qa_assessment} if review.qa_assessment is not None else {}),
        })
    return evidence


def _maybe_auto_preview_and_mock_deploy(
    db: DbSession, task_run: TaskRun, *,
    preview_service: PreviewService, deploy_service: DeployService,
) -> None:
    from app.dag_integration import IntegrationError, delivery_worktree_path

    try:
        delivery_path = delivery_worktree_path(db, task_run)
    except IntegrationError:
        return
    task = db.get(Task, task_run.task_id)
    if task is None or task.intent_type != "frontend_change":
        return
    plan = plan_json_for_task(task)
    if plan.get("planner") != "contract_first_v1":
        return
    demo_root = Path(delivery_path) / "apps/demo"
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
    preview_job = run_preview_job(db, preview_job, preview_service=preview_service)
    if preview_job.state != "completed":
        return
    evidence = json.loads(preview_job.evidence_json)
    preview_id = evidence.get("previewId")
    if not isinstance(preview_id, str):
        return
    deploy_job = enqueue_deploy_job(db, task_run.id, preview_id)
    run_deploy_job(db, deploy_job, deploy_service=deploy_service)
    refresh_session_ledger_for_task_run(db, task_run.id)


def _is_auto_pipeline_task(task: Task) -> bool:
    plan = plan_json_for_task(task)
    return (
        plan.get("planner") in AUTO_PIPELINE_PLANNERS
        and plan.get("autoStart") is True
        and task.intent_type in {"backend_change", "frontend_change"}
    )


def _has_task_run(db: DbSession, task_id: str) -> bool:
    return bool(list_task_runs(db, task_id))
