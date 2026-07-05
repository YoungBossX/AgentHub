from fastapi import APIRouter, Depends
from sqlmodel import Session as DbSession

from app.dependencies import get_db
from app.repositories import get_demo_workspace
from app.schemas import WorkspaceResponse

router = APIRouter()


@router.get("/workspaces/demo", response_model=WorkspaceResponse)
def read_demo_workspace(db: DbSession = Depends(get_db)) -> WorkspaceResponse:
    return get_demo_workspace(db)
