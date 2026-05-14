from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    service: str
    database: str


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class WorkspaceResponse(ApiModel):
    id: str
    name: str
    repo_url: str = Field(alias="repoUrl")
    root_path: str = Field(alias="rootPath")
    default_branch: str = Field(alias="defaultBranch")
    created_at: datetime = Field(alias="createdAt")


class SessionResponse(ApiModel):
    id: str
    workspace_id: str = Field(alias="workspaceId")
    title: str
    session_type: str = Field(alias="sessionType")
    bound_branch: str = Field(alias="boundBranch")
    worktree_path: str = Field(alias="worktreePath")
    status: str
    last_message_at: Optional[datetime] = Field(alias="lastMessageAt")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class SessionCreateRequest(BaseModel):
    title: Optional[str] = None


class SessionUpdateRequest(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
