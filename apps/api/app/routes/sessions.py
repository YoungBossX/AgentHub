from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session as DbSession

from app.dependencies import get_db, get_worktree_service
from app.memory_snapshots import (
    MemorySnapshotError,
    create_memory_snapshot,
    ensure_session_memory_snapshot,
    refresh_session_memory_snapshot,
)
from app.models import Session as AgentHubSession
from app.models import utc_now
from app.repositories import (
    get_session,
    get_workspace,
    list_workspace_sessions,
    next_session_title,
    persist_session,
)
from app.schemas import (
    SessionCreateRequest,
    SessionResponse,
    SessionTargetSelectionRequest,
    SessionUpdateRequest,
)
from app.target_registry import TargetRegistryError, get_target_for_workspace
from app.worktrees import WorktreeError, WorktreeService

router = APIRouter()


@router.get(
    "/workspaces/{workspace_id}/sessions",
    response_model=list[SessionResponse],
)
def read_workspace_sessions(
    workspace_id: str,
    db: DbSession = Depends(get_db),
) -> list[AgentHubSession]:
    if get_workspace(db, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return list_workspace_sessions(db, workspace_id)


@router.post(
    "/workspaces/{workspace_id}/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_workspace_session(
    workspace_id: str,
    request: SessionCreateRequest,
    db: DbSession = Depends(get_db),
    worktrees: WorktreeService = Depends(get_worktree_service),
) -> AgentHubSession:
    workspace = get_workspace(db, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    now = utc_now()
    session = AgentHubSession(
        workspace_id=workspace.id,
        title=request.title or next_session_title(db, workspace.id),
        session_type="demo",
        bound_branch=workspace.default_branch,
        memory_snapshot_id=create_memory_snapshot(
            db,
            workspace_id=workspace.id,
            reason="session_create",
        ).id,
        worktree_path=str(worktrees.session_path(workspace.id, "")),
        status="active",
        last_message_at=now,
        created_at=now,
        updated_at=now,
    )
    try:
        worktree_path = worktrees.create_session_worktree(workspace, session.id)
    except WorktreeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not create session worktree: {exc}",
        ) from exc

    session.worktree_path = str(worktree_path)
    return persist_session(db, session)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def read_session(
    session_id: str,
    db: DbSession = Depends(get_db),
) -> AgentHubSession:
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    ensure_session_memory_snapshot(db, session)
    return session


@router.post("/sessions/{session_id}/memory-snapshot/refresh", response_model=SessionResponse)
def refresh_memory_snapshot_for_session(
    session_id: str,
    db: DbSession = Depends(get_db),
) -> AgentHubSession:
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    try:
        refresh_session_memory_snapshot(db, session_id)
    except MemorySnapshotError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    refreshed = get_session(db, session_id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return refreshed


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
def update_session(
    session_id: str,
    request: SessionUpdateRequest,
    db: DbSession = Depends(get_db),
) -> AgentHubSession:
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if request.title is not None:
        session.title = request.title
    if request.status is not None:
        session.status = request.status

    return persist_session(db, session)


@router.patch("/sessions/{session_id}/target-selection", response_model=SessionResponse)
def update_session_target_selection(
    session_id: str,
    request: SessionTargetSelectionRequest,
    db: DbSession = Depends(get_db),
) -> AgentHubSession:
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if request.frontend_target_id is not None:
        _validate_session_target(
            db,
            session.workspace_id,
            request.frontend_target_id,
            expected_type="frontend",
        )
        session.active_frontend_target_id = request.frontend_target_id
    if request.backend_target_id is not None:
        _validate_session_target(
            db,
            session.workspace_id,
            request.backend_target_id,
            expected_type="backend",
        )
        session.active_backend_target_id = request.backend_target_id

    return persist_session(db, session)


def _validate_session_target(
    db: DbSession,
    workspace_id: str,
    target_id: str,
    *,
    expected_type: str,
) -> None:
    try:
        target = get_target_for_workspace(db, workspace_id, target_id)
    except TargetRegistryError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    if target.type != expected_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Target {target_id} is not a {expected_type} target.",
        )
