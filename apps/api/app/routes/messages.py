import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlmodel import Session as DbSession

from app.dependencies import get_db
from app.models import Message, Task
from app.models import Session as AgentHubSession
from app.planning import MentionParseError, plan_for_message
from app.repositories import (
    create_session_message,
    get_session,
    list_session_messages,
)
from app.schemas import MessageCreateRequest, MessageResponse
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
from app.run_engine import schedule_task_run_execution
from app.ledger import refresh_session_ledger

router = APIRouter()


@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
def read_session_messages(
    session_id: str,
    db: DbSession = Depends(get_db),
) -> list[Message]:
    if get_session(db, session_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return list_session_messages(db, session_id)


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
) -> Message:
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
    created = create_session_message(db, session, message)
    if created.sender_type == "user":
        try:
            planned_tasks = plan_for_message(db, created, created.content_md)
            complete_synthetic_planning_tasks(db, planned_tasks)
            refresh_session_scheduler_state(db, session.id)
            auto_start_safe_tasks(db, planned_tasks, background_tasks)
        except MentionParseError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    refresh_session_ledger(db, session.id)
    return created


def auto_start_safe_tasks(
    db: DbSession,
    tasks: list[Task],
    background_tasks: BackgroundTasks,
) -> None:
    for task in tasks:
        try:
            plan = json.loads(task.plan_json)
        except json.JSONDecodeError:
            continue
        if not _should_auto_start_task(db, task, plan):
            continue
        decision = evaluate_and_apply_scheduler_readiness(db, task)
        if not decision.runnable:
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
