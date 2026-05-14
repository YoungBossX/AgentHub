import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session as DbSession

from app.events import append_task_run_event
from app.models import TaskRun, TaskRunEvent
from app.models import utc_now

AgentEventType = Literal[
    "message.delta",
    "task.state",
    "approval.requested",
    "artifact.diff.ready",
    "artifact.preview.ready",
    "artifact.deploy.ready",
    "error",
    "completed",
]


class AdapterModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class AdapterCapabilities(AdapterModel):
    supports_streaming: bool = Field(alias="supportsStreaming")
    supports_interrupt: bool = Field(alias="supportsInterrupt")
    supports_approval: bool = Field(alias="supportsApproval")
    supports_file_edit: bool = Field(alias="supportsFileEdit")
    supports_shell_command: bool = Field(alias="supportsShellCommand")
    supports_diff_artifact: bool = Field(alias="supportsDiffArtifact")
    supports_preview_artifact: bool = Field(alias="supportsPreviewArtifact")
    supports_network: bool = Field(alias="supportsNetwork")
    max_runtime_sec: Optional[int] = Field(default=None, alias="maxRuntimeSec")


class AgentRunRequest(AdapterModel):
    task_run_id: str = Field(alias="taskRunId")
    session_id: str = Field(alias="sessionId")
    workspace_id: str = Field(alias="workspaceId")
    worktree_path: str = Field(alias="worktreePath")
    agent_id: str = Field(alias="agentId")
    adapter_type: str = Field(alias="adapterType")
    instruction: str
    plan_context: dict[str, Any] = Field(default_factory=dict, alias="planContext")
    permission_profile: dict[str, Any] = Field(
        default_factory=dict,
        alias="permissionProfile",
    )
    demo_mode: bool = Field(default=False, alias="demoMode")
    fallback_policy: str = Field(default="none", alias="fallbackPolicy")


class AdapterRun(AdapterModel):
    adapter_run_id: str = Field(alias="adapterRunId")


class AdapterApproval(AdapterModel):
    approved: bool
    payload: dict[str, Any] = Field(default_factory=dict)


class AdapterArtifact(AdapterModel):
    artifact_type: str = Field(alias="artifactType")
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentEvent(AdapterModel):
    type: AgentEventType
    task_run_id: str = Field(alias="taskRunId")
    sequence: int = 0
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now, alias="createdAt")


RawAgentEvent = Union[AgentEvent, dict[str, Any]]


class AgentAdapter(ABC):
    @abstractmethod
    def getCapabilities(self) -> AdapterCapabilities:
        raise NotImplementedError

    @abstractmethod
    async def createRun(self, request: AgentRunRequest) -> AdapterRun:
        raise NotImplementedError

    @abstractmethod
    def streamEvents(self, run_id: str) -> AsyncIterator[RawAgentEvent]:
        raise NotImplementedError

    @abstractmethod
    async def interrupt(self, run_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def approve(self, run_id: str, approval: AdapterApproval) -> None:
        raise NotImplementedError

    @abstractmethod
    async def collectArtifacts(self, run_id: str) -> list[AdapterArtifact]:
        raise NotImplementedError

    @abstractmethod
    async def cleanup(self, run_id: str) -> None:
        raise NotImplementedError


def normalize_agent_event(
    raw_event: RawAgentEvent,
    default_task_run_id: str,
) -> AgentEvent:
    if isinstance(raw_event, AgentEvent):
        return raw_event

    event_data = dict(raw_event)
    event_data.setdefault("taskRunId", default_task_run_id)
    event_data.setdefault("payload", {})
    event_data.setdefault("sequence", 0)
    return AgentEvent.model_validate(event_data)


def persist_agent_event(db: DbSession, event: AgentEvent) -> TaskRunEvent:
    payload_json = json.dumps(event.payload, separators=(",", ":"))
    return append_task_run_event(
        db,
        task_run_id=event.task_run_id,
        event_type=event.type,
        payload_json=payload_json,
    )


async def run_adapter_event_stream(
    db: DbSession,
    adapter: AgentAdapter,
    request: AgentRunRequest,
) -> list[TaskRunEvent]:
    capabilities = adapter.getCapabilities()
    if not capabilities.supports_streaming:
        raise ValueError("Adapter does not support streaming events.")

    run: Optional[AdapterRun] = None
    persisted: list[TaskRunEvent] = []
    try:
        run = await adapter.createRun(request)
        task_run = db.get(TaskRun, request.task_run_id)
        if task_run is not None:
            task_run.adapter_run_id = run.adapter_run_id
            task_run.updated_at = utc_now()
            db.add(task_run)
            db.commit()

        async for raw_event in adapter.streamEvents(run.adapter_run_id):
            event = normalize_agent_event(raw_event, request.task_run_id)
            persisted.append(persist_agent_event(db, event))
    finally:
        if run is not None:
            await adapter.cleanup(run.adapter_run_id)

    return persisted
