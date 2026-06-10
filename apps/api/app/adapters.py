import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session as DbSession

from app.events import append_task_run_event
from app.models import Task, TaskRun, TaskRunEvent
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
    on_adapter_run_created: Optional[Callable[[AdapterRun], None]] = None,
) -> list[TaskRunEvent]:
    capabilities = adapter.getCapabilities()
    if not capabilities.supports_streaming:
        raise ValueError("Adapter does not support streaming events.")

    run: Optional[AdapterRun] = None
    persisted: list[TaskRunEvent] = []
    try:
        run = await adapter.createRun(request)
        if on_adapter_run_created is not None:
            on_adapter_run_created(run)
        task_run = db.get(TaskRun, request.task_run_id)
        if task_run is not None:
            task_run.adapter_run_id = run.adapter_run_id
            task_run.updated_at = utc_now()
            db.add(task_run)
            db.commit()

        async for raw_event in adapter.streamEvents(run.adapter_run_id):
            event = normalize_agent_event(raw_event, request.task_run_id)
            persisted.append(persist_agent_event(db, event))
            _apply_task_run_event_state(db, event)
    finally:
        if run is not None:
            await adapter.cleanup(run.adapter_run_id)

    return persisted


def _apply_task_run_event_state(db: DbSession, event: AgentEvent) -> None:
    task_run = db.get(TaskRun, event.task_run_id)
    if task_run is None:
        return

    now = utc_now()
    if event.type == "task.state":
        state = event.payload.get("state")
        if isinstance(state, str) and state:
            task_run.state = state
    elif event.type == "approval.requested":
        task_run.state = "waiting_approval"
    elif event.type == "completed":
        task_run.state = "completed"
        task_run.error_code = None
        task_run.error_message = None
        task_run.ended_at = now
    elif event.type == "error":
        code = str(event.payload.get("code") or "ADAPTER_ERROR")
        message = str(event.payload.get("message") or "Adapter run failed.")
        task_run.state = "interrupted" if code.endswith("_INTERRUPTED") else "failed"
        task_run.error_code = code
        task_run.error_message = message
        task_run.ended_at = now
    else:
        return

    task_run.updated_at = now
    task = db.get(Task, task_run.task_id)
    if task is not None:
        task.status = _task_status_for_run_state(task_run.state)
        task.updated_at = now
        db.add(task)
    db.add(task_run)
    db.commit()

    if task is not None and task_run.state in {"completed", "failed", "interrupted", "cancelled"}:
        from app.task_runs import finalize_terminal_task_run

        finalize_terminal_task_run(db, task, task_run, task_run.state)


def _task_status_for_run_state(state: str) -> str:
    if state == "waiting_approval":
        return "waiting_approval"
    if state == "completed":
        return "completed"
    if state == "failed":
        return "failed"
    if state == "interrupted":
        return "interrupted"
    return "running"
