from datetime import datetime
from typing import Any, Optional

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


class MessageResponse(ApiModel):
    id: str
    session_id: str = Field(alias="sessionId")
    sender_type: str = Field(alias="senderType")
    sender_id: Optional[str] = Field(alias="senderId")
    content_md: str = Field(alias="contentMd")
    message_kind: str = Field(alias="messageKind")
    parent_message_id: Optional[str] = Field(alias="parentMessageId")
    stream_state: str = Field(alias="streamState")
    created_at: datetime = Field(alias="createdAt")


class MessageCreateRequest(BaseModel):
    content_md: str = Field(alias="contentMd")
    sender_type: str = Field(default="user", alias="senderType")
    sender_id: Optional[str] = Field(default=None, alias="senderId")
    message_kind: str = Field(default="chat", alias="messageKind")
    parent_message_id: Optional[str] = Field(default=None, alias="parentMessageId")
    stream_state: str = Field(default="complete", alias="streamState")

    model_config = ConfigDict(populate_by_name=True)


class TaskResponse(ApiModel):
    id: str
    session_id: str = Field(alias="sessionId")
    created_by_message_id: Optional[str] = Field(alias="createdByMessageId")
    title: str
    intent_type: str = Field(alias="intentType")
    status: str
    priority: int
    plan_json: dict[str, Any] = Field(alias="planJson")
    depends_on_task_ids: list[str] = Field(alias="dependsOnTaskIds")
    assigned_agent_id: Optional[str] = Field(alias="assignedAgentId")
    assigned_agent_role: Optional[str] = Field(alias="assignedAgentRole")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
