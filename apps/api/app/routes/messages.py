import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlmodel import Session as DbSession
from sqlalchemy import func, update

from app.dependencies import get_db
from app.attachments import bind_message_attachments, metadata_for_messages
from app.models import Message, Task, utc_now
from app.models import Session as AgentHubSession
from app.planning import MentionParseError, plan_for_message
from app.repositories import (
    create_session_message,
    get_session,
    list_session_messages,
)
from app.schemas import MessageCreateRequest, MessageResponse, MessagePinRequest, MessageRegenerateRequest
from app.scheduler import (
    complete_synthetic_planning_tasks,
    evaluate_and_apply_scheduler_readiness,
    refresh_session_scheduler_state,
)
from app.target_registry import (
    DEMO_BACKEND_TARGET_ID,
    DEMO_FRONTEND_TARGET_ID,
    TargetProject,
    TargetRegistryError,
    get_target_for_workspace,
)
from app.task_runs import create_task_run
from app.run_engine import complete_ready_session_review_tasks, schedule_task_run_execution
from app.ledger import refresh_session_ledger

router = APIRouter()


def message_response(db: DbSession, message: Message, *, view: dict | None = None, attachments: dict | None = None) -> MessageResponse:
    from app.group_summaries import public_group_summary
    from app.message_regeneration import attachment_source, public_regeneration

    lineage, action = public_regeneration(db, message, view)
    owner = attachment_source(db, message)
    return MessageResponse.model_validate(message).model_copy(update={
        "group_summary": public_group_summary(db, message), "regeneration": lineage,
        "regeneration_action": action,
        "attachments": (attachments if attachments is not None else metadata_for_messages(db, message.session_id, [owner])).get(owner, []),
    })


@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
def read_session_messages(
    session_id: str,
    db: DbSession = Depends(get_db),
) -> list[MessageResponse]:
    if get_session(db, session_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    messages = list_session_messages(db, session_id)
    from app.message_regeneration import attachment_source, regeneration_view

    attachments = metadata_for_messages(db, session_id, list({attachment_source(db, message) for message in messages}))
    view = regeneration_view(db, session_id, messages)
    return [message_response(db, message, view=view, attachments=attachments) for message in messages]


@router.patch("/sessions/{session_id}/messages/{message_id}/pin", response_model=MessageResponse)
def pin_message(session_id: str, message_id: str, request: MessagePinRequest, db: DbSession = Depends(get_db)) -> MessageResponse:
    message = db.get(Message, message_id)
    if get_session(db, session_id) is None or message is None or message.session_id != session_id:
        raise HTTPException(status_code=404, detail="Message not found in this Session")
    value = func.coalesce(Message.pinned_at, utc_now()) if request.pinned else None
    db.execute(update(Message).where(Message.id == message_id, Message.session_id == session_id).values(pinned_at=value).execution_options(synchronize_session=False))
    db.commit()
    db.refresh(message)
    return message_response(db, message)


@router.post("/sessions/{session_id}/messages/{message_id}/regenerate", response_model=MessageResponse, status_code=201)
def regenerate_message(session_id: str, message_id: str, request: MessageRegenerateRequest,
                       background_tasks: BackgroundTasks, db: DbSession = Depends(get_db)) -> MessageResponse:
    from app.message_regeneration import prepare_regeneration, finish_request
    from app.group_summaries import execute_group_summary

    created, summary_job, fresh = prepare_regeneration(db, session_id, message_id, str(request.request_id))
    operation_id = created.id
    if fresh and summary_job:
        background_tasks.add_task(execute_group_summary, db.get_bind(), summary_job)
    elif fresh:
        try:
            dispatch_message(db, created, background_tasks)
        except Exception:
            # Preserve the operation and any partial plan. No raw provider error
            # is returned or retried implicitly after an uncertain client result.
            finish_request(db, operation_id, failed=True)
        else:
            finish_request(db, operation_id, failed=False)
    return message_response(db, db.get(Message, operation_id))


@router.post("/sessions/{session_id}/groups/{group_id}/summary/retry", response_model=MessageResponse, status_code=201)
def retry_group_summary(session_id: str, group_id: str, background_tasks: BackgroundTasks, db: DbSession = Depends(get_db)) -> MessageResponse:
    from app.group_summaries import execute_group_summary, prepare_group_summary, public_group_summary

    original = db.get(Message, group_id)
    if original is None or original.session_id != session_id:
        raise HTTPException(status_code=404, detail="Group not found.")
    job = prepare_group_summary(db, group_id, retry=True)
    if job is None:
        raise HTTPException(status_code=409, detail="Group is running, already summarized, or has a live summary claim.")
    background_tasks.add_task(execute_group_summary, db.get_bind(), job)
    message = db.get(Message, job.message_id)
    return MessageResponse.model_validate(message).model_copy(update={"group_summary": public_group_summary(db, message)})


@router.post(
    "/sessions/{session_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_message(
    session_id: str,
    request: MessageCreateRequest,
    background_tasks: BackgroundTasks,
    db: DbSession = Depends(get_db),
) -> MessageResponse:
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    message = Message(
        session_id=session.id,
        sender_type=request.sender_type,
        sender_id=request.sender_id,
        content_md=request.content_md,
        message_kind=request.message_kind,
        parent_message_id=request.parent_message_id,
        stream_state=request.stream_state,
        context_json=json.dumps(request.context, separators=(",", ":")),
    )
    bind_message_attachments(db, message, request.attachment_ids)
    created = create_session_message(db, session, message)
    dispatch_message(db, created, background_tasks)
    return message_response(db, created)


def dispatch_message(db: DbSession, created: Message, background_tasks: BackgroundTasks) -> None:
    if created.sender_type == "user":
        try:
            # Reconcile persisted advisory reports before planning another change.
            complete_ready_session_review_tasks(db, created.session_id)
            planned_tasks = plan_for_message(db, created, created.content_md)
            complete_synthetic_planning_tasks(db, planned_tasks)
            refresh_session_scheduler_state(db, created.session_id)
            auto_start_safe_tasks(db, planned_tasks, background_tasks)
        except MentionParseError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    refresh_session_ledger(db, created.session_id)


def auto_start_safe_tasks(
    db: DbSession,
    tasks: list[Task],
    background_tasks: BackgroundTasks,
) -> None:
    from app.group_execution import enqueue_ready_group_tasks

    group_sessions = {task.session_id for task in tasks if json.loads(task.plan_json).get("planner") == "explicit_group_v1"}
    for session_id in group_sessions:
        enqueue_ready_group_tasks(db, session_id=session_id)
        schedule_task_run_execution(background_tasks)
    for task in tasks:
        try:
            plan = json.loads(task.plan_json)
        except json.JSONDecodeError:
            continue
        if plan.get("planner") == "explicit_group_v1":
            continue
        if not _should_auto_start_task(db, task, plan):
            continue
        decision = evaluate_and_apply_scheduler_readiness(db, task)
        if not decision.runnable and not (
            plan.get("executionMode") == "isolated_write"
            and decision.state == "waiting_target_lock"
        ):
            continue
        create_task_run(db, task.id)
        schedule_task_run_execution(background_tasks)


def _should_auto_start_task(db: DbSession, task: Task, plan: dict[str, Any]) -> bool:
    if not plan.get("autoStart"):
        return False
    files = plan.get("files", [])
    if not isinstance(files, list) or not files:
        return False
    if task.intent_type not in {"frontend_change", "backend_change"}:
        return False

    target_id = plan.get("targetId")
    if not isinstance(target_id, str):
        target_id = (
            DEMO_FRONTEND_TARGET_ID
            if task.intent_type == "frontend_change"
            else DEMO_BACKEND_TARGET_ID
        )
    session = db.get(AgentHubSession, task.session_id)
    if session is None:
        return False
    try:
        target = get_target_for_workspace(db, session.workspace_id, target_id)
    except TargetRegistryError:
        return False
    if target.requires_platform_mode or target.requires_approval:
        return False
    expected_role = "frontend" if task.intent_type == "frontend_change" else "backend"
    if not target.allows_agent(expected_role):
        return False
    safe_target = plan.get("safeTarget")
    if isinstance(safe_target, str) and safe_target and not target.permits_path(safe_target):
        return False
    return all(_is_safe_target_path(path, target) for path in files)


def _is_safe_target_path(path: object, target: TargetProject) -> bool:
    if not isinstance(path, str) or not path.strip():
        return False
    normalized = path.replace("\\", "/").strip()
    if normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized:
        return False
    return target.permits_path(normalized)
