import asyncio
import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session as DbSession

from app.events import (
    append_task_run_event,
    publish_task_run_event,
    stage_task_run_event,
)
from app.models import Session as AgentHubSession
from app.models import Task, TaskRun, TaskRunEvent
from app.models import utc_now
from app.task_run_scope import TaskRunScopeError

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

_CALLER_OWNS_CANCELLATION_INTERRUPT = object()


def _cancel_adapter_stream_after_interrupt_started(task: asyncio.Task[Any]) -> None:
    task.cancel(_CALLER_OWNS_CANCELLATION_INTERRUPT)


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
    *,
    ownership_guard: Callable[[DbSession], bool],
    on_adapter_run_created: Optional[Callable[[AdapterRun], None]] = None,
) -> list[TaskRunEvent]:
    if not callable(ownership_guard):
        raise ValueError("Adapter event ownership guard is required.")
    capabilities = adapter.getCapabilities()
    if not capabilities.supports_streaming:
        raise ValueError("Adapter does not support streaming events.")

    run: Optional[AdapterRun] = None
    persisted: list[TaskRunEvent] = []
    primary_error = False
    try:
        run = await adapter.createRun(request)
        if not _bind_adapter_run(
            db,
            request,
            run,
            ownership_guard=ownership_guard,
        ):
            raise _adapter_event_ownership_error()
        if on_adapter_run_created is not None:
            on_adapter_run_created(run)

        async for raw_event in adapter.streamEvents(run.adapter_run_id):
            event = normalize_agent_event(raw_event, request.task_run_id)
            if event.task_run_id != request.task_run_id:
                raise _adapter_event_ownership_error()
            stored = _persist_guarded_agent_event(
                db,
                request,
                run,
                event,
                ownership_guard=ownership_guard,
            )
            if stored is None:
                raise _adapter_event_ownership_error()
            persisted.append(stored)
    except BaseException as exc:
        primary_error = True
        caller_owns_cancellation_interrupt = bool(
            isinstance(exc, asyncio.CancelledError)
            and len(exc.args) == 1
            and exc.args[0] is _CALLER_OWNS_CANCELLATION_INTERRUPT
        )
        if (
            run is not None
            and capabilities.supports_interrupt
            and not caller_owns_cancellation_interrupt
        ):
            try:
                await adapter.interrupt(run.adapter_run_id)
            except BaseException:
                pass
        raise
    finally:
        if run is not None:
            try:
                await adapter.cleanup(run.adapter_run_id)
            except (Exception, asyncio.CancelledError):
                if not primary_error:
                    raise

    return persisted


def _adapter_event_ownership_error() -> TaskRunScopeError:
    return TaskRunScopeError(
        "TASK_RUN_SCOPE_UNVERIFIABLE",
        "The task run execution lease ownership cannot be verified.",
    )


def _rollback_adapter_event_fence(
    db: DbSession,
    *,
    primary_error: Optional[Exception] = None,
) -> None:
    try:
        db.rollback()
    except Exception as rollback_error:
        if primary_error is None:
            raise _adapter_event_ownership_error() from rollback_error


def _bind_adapter_run(
    db: DbSession,
    request: AgentRunRequest,
    run: AdapterRun,
    *,
    ownership_guard: Callable[[DbSession], bool],
) -> bool:
    _rollback_adapter_event_fence(db)
    try:
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        db.expire_all()
        task_run = db.get(TaskRun, request.task_run_id)
        task = db.get(Task, task_run.task_id) if task_run is not None else None
        session = (
            db.get(AgentHubSession, task.session_id) if task is not None else None
        )
        if (
            task_run is None
            or task is None
            or session is None
            or task_run.state not in _ACTIVE_ADAPTER_EVENT_STATES
            or task_run.adapter_run_id is not None
            or task.session_id != request.session_id
            or session.id != request.session_id
            or not ownership_guard(db)
        ):
            db.rollback()
            return False
        now = utc_now()
        task_run.adapter_run_id = run.adapter_run_id
        task_run.started_at = task_run.started_at or now
        task_run.updated_at = now
        db.add(task_run)
        db.commit()
        return True
    except Exception as exc:
        _rollback_adapter_event_fence(db, primary_error=exc)
        raise _adapter_event_ownership_error() from exc


def _persist_guarded_agent_event(
    db: DbSession,
    request: AgentRunRequest,
    run: AdapterRun,
    event: AgentEvent,
    *,
    ownership_guard: Callable[[DbSession], bool],
) -> Optional[TaskRunEvent]:
    _rollback_adapter_event_fence(db)
    try:
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        db.expire_all()
        task_run = db.get(TaskRun, request.task_run_id)
        task = db.get(Task, task_run.task_id) if task_run is not None else None
        session = (
            db.get(AgentHubSession, task.session_id) if task is not None else None
        )
        if (
            event.task_run_id != request.task_run_id
            or task_run is None
            or task is None
            or session is None
            or task_run.state not in _ACTIVE_ADAPTER_EVENT_STATES
            or task_run.adapter_run_id != run.adapter_run_id
            or task.session_id != request.session_id
            or session.id != request.session_id
            or not ownership_guard(db)
        ):
            db.rollback()
            return None
        stored = stage_task_run_event(
            db,
            task_run_id=event.task_run_id,
            event_type=event.type,
            payload_json=json.dumps(event.payload, separators=(",", ":")),
        )
        terminal_state = _stage_task_run_event_state(db, task_run, task, event)
        db.commit()
        db.refresh(stored)
    except Exception as exc:
        _rollback_adapter_event_fence(db, primary_error=exc)
        raise _adapter_event_ownership_error() from exc
    publish_task_run_event(db, stored)
    if terminal_state is not None:
        from app.task_runs import finalize_terminal_task_run

        finalize_terminal_task_run(db, task, task_run, terminal_state)
    return stored


_ACTIVE_ADAPTER_EVENT_STATES = {
    "created",
    "queued",
    "running",
    "streaming",
    "waiting_approval",
    "applying_changes",
    "collecting_diff",
    "starting_preview",
}


def _stage_task_run_event_state(
    db: DbSession,
    task_run: TaskRun,
    task: Task,
    event: AgentEvent,
) -> Optional[str]:

    now = utc_now()
    if event.type == "task.state":
        state = event.payload.get("state")
        if isinstance(state, str) and state:
            task_run.state = "collecting_diff" if state == "completed" else state
            if state == "completed":
                task_run.error_code = None
                task_run.error_message = None
    elif event.type == "approval.requested":
        task_run.state = "waiting_approval"
    elif event.type == "completed":
        task_run.state = "collecting_diff"
        task_run.error_code = None
        task_run.error_message = None
    elif event.type == "error":
        code = str(event.payload.get("code") or "ADAPTER_ERROR")
        message = str(event.payload.get("message") or "Adapter run failed.")
        task_run.state = "interrupted" if code.endswith("_INTERRUPTED") else "failed"
        task_run.error_code = code
        task_run.error_message = message
        task_run.ended_at = now
    else:
        return None

    task_run.updated_at = now
    task.status = _task_status_for_run_state(task_run.state)
    task.updated_at = now
    db.add(task)
    db.add(task_run)
    return (
        task_run.state
        if task_run.state in {"completed", "failed", "interrupted", "cancelled"}
        else None
    )


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
