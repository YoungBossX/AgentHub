import asyncio
import json
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlmodel import Session as DbSession
from sqlmodel import select

from app.dependencies import get_db
from app.guardrails import approve_task_run, deny_task_run
from app.ledger import refresh_session_ledger
from app.models import Agent, Task, TaskRun, TaskRunEvent, utc_now
from app.pmo_decisions import (
    PmoDecisionError,
    apply_pmo_decision,
    require_supported_decision_payload,
)
from app.repositories import get_session, list_session_tasks
from app.run_diagnostics import build_task_run_diagnostics
from app.run_engine import (
    interrupt_supervised_task_run,
    plan_json_for_task,
    schedule_task_run_execution,
)
from app.schemas import (
    ApprovalDecisionRequest,
    ApprovalRequestResponse,
    PMOPlanDecisionRequest,
    RunDiagnosticsResponse,
    TaskResponse,
    TaskRunResponse,
)
from app.task_runs import (
    TaskRunLifecycleError,
    adapter_type_for_run,
    create_task_run,
    interrupt_task_run,
    list_task_runs,
    metrics_for_run,
    retry_task_run,
    retry_with_scripted_mock,
)


router = APIRouter()


def task_run_response(db: DbSession, task_run: TaskRun) -> TaskRunResponse:
    from app.preview_deploy_jobs import job_diagnostics_for_task_run
    from app.session_queue import queue_diagnostics_for_task_run
    from app.target_locks import lock_diagnostics_for_task_run

    task = db.get(Task, task_run.task_id)
    metrics = metrics_for_run(task_run)
    return TaskRunResponse(
        id=task_run.id,
        taskId=task_run.task_id,
        sessionId=task.session_id if task is not None else "",
        agentId=task_run.agent_id,
        adapterType=adapter_type_for_run(db, task_run),
        adapterRunId=task_run.adapter_run_id,
        state=task_run.state,
        startedAt=task_run.started_at,
        endedAt=task_run.ended_at,
        runnerId=task_run.runner_id,
        lastHeartbeatAt=task_run.last_heartbeat_at,
        leaseExpiresAt=task_run.lease_expires_at,
        staleDetectedAt=task_run.stale_detected_at,
        staleReason=task_run.stale_reason,
        worktreePath=task_run.worktree_path,
        baseRef=task_run.base_ref,
        headRef=task_run.head_ref,
        errorCode=task_run.error_code,
        errorMessage=task_run.error_message,
        metricsJson=metrics,
        providerAssignment=metrics.get("providerAssignment"),
        runtimeConfigResolution=metrics.get("runtimeConfigResolution"),
        memorySnapshot=metrics.get("memorySnapshot"),
        sessionQueue=queue_diagnostics_for_task_run(db, task_run.id),
        targetLock=lock_diagnostics_for_task_run(db, task_run.id),
        previewDeployJobs=job_diagnostics_for_task_run(db, task_run.id),
        approvalRequest=latest_approval_request(db, task_run),
        createdAt=task_run.created_at,
        updatedAt=task_run.updated_at,
    )


def latest_approval_request(
    db: DbSession,
    task_run: TaskRun,
) -> Optional[ApprovalRequestResponse]:
    if task_run.state != "waiting_approval":
        return None

    event = db.exec(
        select(TaskRunEvent)
        .where(TaskRunEvent.task_run_id == task_run.id)
        .where(TaskRunEvent.event_type == "approval.requested")
        .order_by(TaskRunEvent.sequence.desc())
    ).first()
    if event is None:
        return None

    try:
        return ApprovalRequestResponse.model_validate(json.loads(event.payload_json))
    except (json.JSONDecodeError, ValueError):
        return None


def task_response(db: DbSession, task: Task) -> TaskResponse:
    assigned_role = None
    if task.assigned_agent_id is not None:
        agent = db.get(Agent, task.assigned_agent_id)
        assigned_role = agent.role if agent is not None else None
    plan = plan_json_for_task(task)
    dependency_ids = json.loads(task.depends_on_task_ids)

    return TaskResponse(
        id=task.id,
        sessionId=task.session_id,
        createdByMessageId=task.created_by_message_id,
        title=task.title,
        intentType=task.intent_type,
        status=task.status,
        priority=task.priority,
        planJson=plan,
        planReviewMetadata=plan_review_metadata_for_task(
            task,
            plan=plan,
            dependency_ids=dependency_ids,
        ),
        dependsOnTaskIds=dependency_ids,
        assignedAgentId=task.assigned_agent_id,
        assignedAgentRole=assigned_role,
        taskRuns=[task_run_response(db, task_run) for task_run in list_task_runs(db, task.id)],
        createdAt=task.created_at,
        updatedAt=task.updated_at,
    )


def plan_review_metadata_for_task(
    task: Task,
    *,
    plan: dict[str, Any],
    dependency_ids: list[str],
) -> dict[str, Any]:
    plan_draft = _dict_value(plan.get("planDraft"))
    task_graph = _dict_value(plan.get("taskGraph"))
    return {
        "plannerMode": _first_string(
            plan.get("plannerMode"),
            plan.get("planner"),
            plan_draft.get("plannerMode"),
            plan_draft.get("planner"),
        ),
        "rationale": _first_string(plan.get("rationale"), plan_draft.get("rationale")),
        "assignedRole": _first_string(plan.get("assignedRole")),
        "targetId": _first_string(
            plan.get("targetId"),
            plan.get("frontendTargetId"),
            plan.get("backendTargetId"),
            plan_draft.get("targetId"),
        ),
        "dependencies": dependency_ids,
        "plannedFiles": _string_list(
            plan.get("plannedFiles"),
            plan.get("files"),
            plan_draft.get("plannedFiles"),
        ),
        "acceptanceCriteria": _string_list(
            plan.get("acceptanceCriteria"),
            plan_draft.get("acceptanceCriteria"),
        ),
        "validationExpectations": _string_list(
            plan.get("validationExpectations"),
            plan_draft.get("validationExpectations"),
        ),
        "taskBreakdown": _task_breakdown(task_graph.get("tasks")),
        "readOnly": True,
        "sourceTaskId": task.id,
    }


def _task_breakdown(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "title": _first_string(item.get("title"), item.get("name")),
                "role": _first_string(item.get("role"), item.get("assignedRole")),
                "targetId": _first_string(item.get("targetId")),
                "dependsOn": _string_list(item.get("dependsOn")),
                "plannedFiles": _string_list(item.get("plannedFiles"), item.get("files")),
            }
        )
    return items


def _dict_value(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_string(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _string_list(*values: object) -> list[str]:
    for value in values:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, str) and item]
    return []


@router.get("/sessions/{session_id}/tasks", response_model=list[TaskResponse])
def read_session_tasks(
    session_id: str,
    db: DbSession = Depends(get_db),
) -> list[TaskResponse]:
    if get_session(db, session_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return [task_response(db, task) for task in list_session_tasks(db, session_id)]


@router.post("/tasks/{task_id}/plan-decision/approve", response_model=TaskResponse)
def approve_task_plan_decision(
    task_id: str,
    request: PMOPlanDecisionRequest,
    db: DbSession = Depends(get_db),
) -> TaskResponse:
    return _apply_task_plan_decision(
        db,
        task_id,
        state="approved",
        request=request,
    )


@router.post("/tasks/{task_id}/plan-decision/reject", response_model=TaskResponse)
def reject_task_plan_decision(
    task_id: str,
    request: PMOPlanDecisionRequest,
    db: DbSession = Depends(get_db),
) -> TaskResponse:
    return _apply_task_plan_decision(
        db,
        task_id,
        state="rejected",
        request=request,
    )


@router.post("/tasks/{task_id}/plan-decision/clarification", response_model=TaskResponse)
def request_task_plan_clarification(
    task_id: str,
    request: PMOPlanDecisionRequest,
    db: DbSession = Depends(get_db),
) -> TaskResponse:
    return _apply_task_plan_decision(
        db,
        task_id,
        state="clarification_needed",
        request=request,
    )


def _apply_task_plan_decision(
    db: DbSession,
    task_id: str,
    *,
    state: str,
    request: PMOPlanDecisionRequest,
) -> TaskResponse:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    try:
        payload = request.model_dump(exclude_none=True)
        require_supported_decision_payload(payload)
        plan = plan_json_for_task(task)
        task.plan_json = json.dumps(
            apply_pmo_decision(
                plan,
                state=state,
                actor="user",
                reason=request.reason,
            ),
            separators=(",", ":"),
        )
    except PmoDecisionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if state in {"rejected", "clarification_needed"}:
        task.status = "blocked"
    task.updated_at = utc_now()
    db.add(task)
    db.commit()
    db.refresh(task)
    refresh_session_ledger(db, task.session_id)
    return task_response(db, task)


@router.post(
    "/tasks/{task_id}/runs",
    response_model=TaskRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task_run_for_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    db: DbSession = Depends(get_db),
) -> TaskRunResponse:
    try:
        task_run = create_task_run(db, task_id)
    except TaskRunLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    schedule_task_run_execution(background_tasks)
    return task_run_response(db, task_run)


@router.post(
    "/tasks/{task_id}/runs/force-codex-failure",
    response_model=TaskRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def force_codex_failure_for_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    db: DbSession = Depends(get_db),
) -> TaskRunResponse:
    try:
        task_run = create_task_run(
            db,
            task_id,
            adapter_type="codex",
            retry_metadata={"forceFailure": True},
        )
    except TaskRunLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    schedule_task_run_execution(background_tasks)
    return task_run_response(db, task_run)


@router.get(
    "/task-runs/{task_run_id}/diagnostics",
    response_model=RunDiagnosticsResponse,
)
def read_task_run_diagnostics(
    task_run_id: str,
    db: DbSession = Depends(get_db),
) -> RunDiagnosticsResponse:
    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TaskRun not found")
    return build_task_run_diagnostics(db, task_run)


@router.post("/task-runs/{task_run_id}/interrupt", response_model=TaskRunResponse)
def interrupt_existing_task_run(
    task_run_id: str,
    db: DbSession = Depends(get_db),
) -> TaskRunResponse:
    try:
        asyncio.run(interrupt_supervised_task_run(task_run_id))
        task_run = interrupt_task_run(db, task_run_id)
    except TaskRunLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return task_run_response(db, task_run)


@router.post(
    "/task-runs/{task_run_id}/retry",
    response_model=TaskRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def retry_existing_task_run(
    task_run_id: str,
    background_tasks: BackgroundTasks,
    db: DbSession = Depends(get_db),
) -> TaskRunResponse:
    try:
        task_run = retry_task_run(db, task_run_id)
    except TaskRunLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    schedule_task_run_execution(background_tasks)
    return task_run_response(db, task_run)


@router.post(
    "/task-runs/{task_run_id}/retry-with-fallback",
    response_model=TaskRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def retry_existing_task_run_with_fallback(
    task_run_id: str,
    background_tasks: BackgroundTasks,
    db: DbSession = Depends(get_db),
) -> TaskRunResponse:
    try:
        task_run = retry_with_scripted_mock(db, task_run_id)
    except TaskRunLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    schedule_task_run_execution(background_tasks)
    return task_run_response(db, task_run)


@router.post("/task-runs/{task_run_id}/approve", response_model=TaskRunResponse)
def approve_existing_task_run(
    task_run_id: str,
    db: DbSession = Depends(get_db),
) -> TaskRunResponse:
    try:
        approve_task_run(db, task_run_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TaskRun not found")
    return task_run_response(db, task_run)


@router.post("/task-runs/{task_run_id}/deny", response_model=TaskRunResponse)
def deny_existing_task_run(
    task_run_id: str,
    request: ApprovalDecisionRequest,
    db: DbSession = Depends(get_db),
) -> TaskRunResponse:
    try:
        deny_task_run(
            db,
            task_run_id,
            reason=request.reason or "User denied approval request.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TaskRun not found")
    return task_run_response(db, task_run)
