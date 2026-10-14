from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session as DbSession

from app.dependencies import get_db
from app.repositories import get_workspace
from app.skills import SkillError, catalog, save_package

router = APIRouter()


class SkillSaveRequest(BaseModel):
    markdown: str = Field(max_length=16000)
    references: dict[str, str] = Field(default_factory=dict, max_length=8)
    roles: list[str] = Field(min_length=1, max_length=4)
    default_agents: list[str] = Field(default_factory=list, alias="defaultAgents", max_length=16)
    enabled: bool = True
    expected_revision: int = Field(default=0, alias="expectedRevision", ge=0)
    model_config = ConfigDict(extra="forbid")


def require_workspace(db, workspace_id):
    if get_workspace(db, workspace_id) is None:
        raise HTTPException(404, "Workspace not found")


@router.get("/workspaces/{workspace_id}/skills")
def read_skills(workspace_id: str, db: DbSession = Depends(get_db)):
    require_workspace(db, workspace_id)
    return catalog(db, workspace_id)


@router.put("/workspaces/{workspace_id}/skills")
def write_skill(workspace_id: str, request: SkillSaveRequest, db: DbSession = Depends(get_db)):
    require_workspace(db, workspace_id)
    try:
        return save_package(db, workspace_id, request, request.expected_revision)
    except SkillError as exc:
        raise HTTPException(409 if "changed" in str(exc) else 400, str(exc)) from exc
