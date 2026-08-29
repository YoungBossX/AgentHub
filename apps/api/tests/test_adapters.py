import asyncio
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app import task_run_scope
from app.adapters import (
    AdapterCapabilities,
    AdapterRun,
    AgentAdapter,
    AgentEvent,
    AgentRunRequest,
    run_adapter_event_stream as _run_adapter_event_stream,
)
from app.events import list_session_events
from app.models import Agent, Session, Task, TaskRun, TaskRunEvent, Workspace
from app.task_runs import interrupt_task_run


def _allow_test_execution_ownership(_: DbSession) -> bool:
    return True


async def run_adapter_event_stream(db, adapter, request, **kwargs):
    kwargs.setdefault("ownership_guard", _allow_test_execution_ownership)
    return await _run_adapter_event_stream(db, adapter, request, **kwargs)


class FakeAdapter(AgentAdapter):
    def __init__(self) -> None:
        self.cleaned_run_id: str | None = None

    def getCapabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supportsStreaming=True,
            supportsInterrupt=True,
            supportsApproval=False,
            supportsFileEdit=True,
            supportsShellCommand=False,
            supportsDiffArtifact=False,
            supportsPreviewArtifact=False,
            supportsNetwork=False,
            maxRuntimeSec=30,
        )

    async def createRun(self, request: AgentRunRequest) -> AdapterRun:
        return AdapterRun(adapterRunId=f"fake-{request.task_run_id}")

    async def streamEvents(self, run_id: str) -> AsyncIterator[AgentEvent]:
        yield AgentEvent(
            type="task.state",
            taskRunId=run_id.replace("fake-", ""),
            sequence=10,
            payload={"state": "streaming"},
        )
        yield {
            "type": "message.delta",
            "taskRunId": run_id.replace("fake-", ""),
            "sequence": 11,
            "payload": {"text": "working"},
        }
        yield AgentEvent(
            type="completed",
            taskRunId=run_id.replace("fake-", ""),
            sequence=12,
            payload={"ok": True},
        )

    async def interrupt(self, run_id: str) -> None:
        return None

    async def approve(self, run_id: str, approval: dict) -> None:
        return None

    async def collectArtifacts(self, run_id: str) -> list[dict]:
        return []

    async def cleanup(self, run_id: str) -> None:
        self.cleaned_run_id = run_id


@pytest.fixture
def db() -> DbSession:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with DbSession(engine) as session:
        yield session


def create_task_run(db: DbSession) -> tuple[Session, TaskRun]:
    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="Adapter session",
        bound_branch="main",
        worktree_path=".worktrees/adapter-session",
    )
    agent = Agent(
        name="Frontend Agent",
        role="frontend",
        adapter_type="codex",
        provider="local",
    )
    task = Task(
        session_id=session.id,
        title="Build login page",
        intent_type="frontend_change",
        assigned_agent_id=agent.id,
    )
    task_run = TaskRun(
        task_id=task.id,
        agent_id=agent.id,
        state="created",
        worktree_path=session.worktree_path,
    )

    db.add(workspace)
    db.add(session)
    db.add(agent)
    db.add(task)
    db.add(task_run)
    db.commit()
    db.refresh(task_run)
    return session, task_run


def invalidate_session_relationship(
    db: DbSession,
    task_run_id: str,
    invalid_session_state: str,
) -> None:
    task_run = db.get(TaskRun, task_run_id)
    task = db.get(Task, task_run.task_id)
    session = db.get(Session, task.session_id)
    assert session is not None
    if invalid_session_state == "missing_session":
        db.delete(session)
    else:
        other_session = Session(
            workspace_id=session.workspace_id,
            title="Adapter relationship mismatch",
            bound_branch=session.bound_branch,
            worktree_path=f"{session.worktree_path}-{task_run.id[:8]}",
        )
        task.session_id = other_session.id
        db.add(other_session)
        db.add(task)
    db.commit()


@pytest.mark.anyio
async def test_adapter_stream_rejects_missing_ownership_guard_before_create_run(
    db: DbSession,
) -> None:
    _, task_run = create_task_run(db)
    task = db.get(Task, task_run.task_id)
    assert task is not None
    create_run_calls: list[str] = []

    class GuardRequiredAdapter(FakeAdapter):
        async def createRun(self, request: AgentRunRequest) -> AdapterRun:
            create_run_calls.append(request.task_run_id)
            return await super().createRun(request)

    request = AgentRunRequest(
        taskRunId=task_run.id,
        sessionId=task.session_id,
        workspaceId="workspace-id",
        worktreePath=task_run.worktree_path,
        agentId=task_run.agent_id,
        adapterType="codex",
        instruction="Do not launch without an ownership fence.",
    )

    with pytest.raises(ValueError, match="ownership guard"):
        await run_adapter_event_stream(
            db,
            GuardRequiredAdapter(),
            request,
            ownership_guard=None,
        )

    assert create_run_calls == []


@pytest.mark.parametrize(
    "invalid_session_state",
    ["missing_session", "task_session_relationship_mismatch"],
)
@pytest.mark.anyio
async def test_adapter_run_bind_revalidates_real_session(
    db: DbSession,
    invalid_session_state: str,
) -> None:
    session, task_run = create_task_run(db)
    request = AgentRunRequest(
        taskRunId=task_run.id,
        sessionId=session.id,
        workspaceId=session.workspace_id,
        worktreePath=task_run.worktree_path,
        agentId=task_run.agent_id,
        adapterType="codex",
        instruction="Bind only while the persisted Session relationship is current.",
    )
    invalidate_session_relationship(db, task_run.id, invalid_session_state)

    adapter = FakeAdapter()
    with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
        await run_adapter_event_stream(db, adapter, request)

    db.expire_all()
    stored = db.get(TaskRun, task_run.id)
    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert adapter.cleaned_run_id == f"fake-{task_run.id}"
    assert stored.adapter_run_id is None
    assert stored.started_at is None
    assert db.exec(
        select(TaskRunEvent).where(TaskRunEvent.task_run_id == task_run.id)
    ).all() == []


@pytest.mark.parametrize(
    "invalid_session_state",
    ["missing_session", "task_session_relationship_mismatch"],
)
@pytest.mark.anyio
async def test_adapter_event_fence_revalidates_real_session(
    db: DbSession,
    invalid_session_state: str,
) -> None:
    session, task_run = create_task_run(db)
    stream_started = asyncio.Event()
    release_event = asyncio.Event()

    class DelayedCompletedAdapter(FakeAdapter):
        async def streamEvents(self, run_id: str) -> AsyncIterator[AgentEvent]:
            stream_started.set()
            await release_event.wait()
            yield AgentEvent(
                type="completed",
                taskRunId=task_run.id,
                sequence=1,
                payload={"ok": True},
            )

    request = AgentRunRequest(
        taskRunId=task_run.id,
        sessionId=session.id,
        workspaceId=session.workspace_id,
        worktreePath=task_run.worktree_path,
        agentId=task_run.agent_id,
        adapterType="codex",
        instruction="Fence the event on the current persisted Session relationship.",
    )
    adapter = DelayedCompletedAdapter()
    stream_task = asyncio.create_task(run_adapter_event_stream(db, adapter, request))
    try:
        await asyncio.wait_for(stream_started.wait(), timeout=1)
        with DbSession(db.get_bind()) as mutation_db:
            invalidate_session_relationship(
                mutation_db,
                task_run.id,
                invalid_session_state,
        )
        release_event.set()
        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            await asyncio.wait_for(stream_task, timeout=1)
    finally:
        release_event.set()
        if not stream_task.done():
            stream_task.cancel()
        await asyncio.gather(stream_task, return_exceptions=True)

    db.expire_all()
    stored = db.get(TaskRun, task_run.id)
    completed_events = db.exec(
        select(TaskRunEvent)
        .where(TaskRunEvent.task_run_id == task_run.id)
        .where(TaskRunEvent.event_type == "completed")
    ).all()
    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert adapter.cleaned_run_id == f"fake-{task_run.id}"
    assert completed_events == []
    assert stored.adapter_run_id == f"fake-{task_run.id}"
    assert stored.state == "created"


@pytest.mark.parametrize("interrupt_raises", [False, True])
@pytest.mark.anyio
async def test_post_bind_event_fence_rejection_interrupts_exact_run_before_cleanup(
    db: DbSession,
    interrupt_raises: bool,
) -> None:
    session, task_run = create_task_run(db)
    adapter_run_id = f"fenced-{task_run.id}"
    lifecycle: list[tuple[str, str]] = []
    ownership_checks = 0

    def lose_ownership_after_bind(_: DbSession) -> bool:
        nonlocal ownership_checks
        ownership_checks += 1
        return ownership_checks == 1

    class PostBindFenceAdapter(FakeAdapter):
        async def createRun(self, request: AgentRunRequest) -> AdapterRun:
            return AdapterRun(adapterRunId=adapter_run_id)

        async def streamEvents(self, run_id: str) -> AsyncIterator[AgentEvent]:
            yield AgentEvent(
                type="completed",
                taskRunId=task_run.id,
                sequence=1,
                payload={"ok": True},
            )

        async def interrupt(self, run_id: str) -> None:
            lifecycle.append(("interrupt", run_id))
            if interrupt_raises:
                raise RuntimeError("injected adapter interrupt failure")

        async def cleanup(self, run_id: str) -> None:
            lifecycle.append(("cleanup", run_id))

    request = AgentRunRequest(
        taskRunId=task_run.id,
        sessionId=session.id,
        workspaceId=session.workspace_id,
        worktreePath=task_run.worktree_path,
        agentId=task_run.agent_id,
        adapterType="codex",
        instruction="Stop the exact bound run when its event fence rejects ownership.",
    )

    with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
        await run_adapter_event_stream(
            db,
            PostBindFenceAdapter(),
            request,
            ownership_guard=lose_ownership_after_bind,
        )

    db.expire_all()
    stored = db.get(TaskRun, task_run.id)
    assert stored is not None
    assert stored.adapter_run_id == adapter_run_id
    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert db.exec(
        select(TaskRunEvent).where(TaskRunEvent.task_run_id == task_run.id)
    ).all() == []
    assert lifecycle == [
        ("interrupt", adapter_run_id),
        ("cleanup", adapter_run_id),
    ]


@pytest.mark.parametrize("interrupt_raises", [False, True])
@pytest.mark.anyio
async def test_adapter_bind_fence_rejection_preserves_scope_error_after_interrupt(
    db: DbSession,
    interrupt_raises: bool,
) -> None:
    session, task_run = create_task_run(db)
    adapter_run_id = f"bind-fenced-{task_run.id}"
    lifecycle: list[tuple[str, str]] = []

    class BindFenceAdapter(FakeAdapter):
        async def createRun(self, request: AgentRunRequest) -> AdapterRun:
            return AdapterRun(adapterRunId=adapter_run_id)

        async def interrupt(self, run_id: str) -> None:
            lifecycle.append(("interrupt", run_id))
            if interrupt_raises:
                raise RuntimeError("injected adapter interrupt failure")

        async def cleanup(self, run_id: str) -> None:
            lifecycle.append(("cleanup", run_id))

    request = AgentRunRequest(
        taskRunId=task_run.id,
        sessionId=session.id,
        workspaceId=session.workspace_id,
        worktreePath=task_run.worktree_path,
        agentId=task_run.agent_id,
        adapterType="codex",
        instruction="Fail closed when durable adapter binding loses ownership.",
    )

    with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
        await run_adapter_event_stream(
            db,
            BindFenceAdapter(),
            request,
            ownership_guard=lambda _: False,
        )

    db.expire_all()
    stored = db.get(TaskRun, task_run.id)
    assert stored is not None
    assert stored.adapter_run_id is None
    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert lifecycle == [
        ("interrupt", adapter_run_id),
        ("cleanup", adapter_run_id),
    ]


@pytest.mark.anyio
async def test_adapter_bind_fence_runtime_error_is_normalized_despite_cleanup_failure(
    db: DbSession,
) -> None:
    session, task_run = create_task_run(db)
    adapter_run_id = f"bind-exception-fenced-{task_run.id}"
    fence_error = RuntimeError("injected bind fence failure")
    lifecycle: list[tuple[str, str]] = []

    class ExceptionalBindFenceAdapter(FakeAdapter):
        async def createRun(self, request: AgentRunRequest) -> AdapterRun:
            return AdapterRun(adapterRunId=adapter_run_id)

        async def interrupt(self, run_id: str) -> None:
            lifecycle.append(("interrupt", run_id))
            raise RuntimeError("injected adapter interrupt failure")

        async def cleanup(self, run_id: str) -> None:
            lifecycle.append(("cleanup", run_id))
            raise RuntimeError("injected adapter cleanup failure")

    request = AgentRunRequest(
        taskRunId=task_run.id,
        sessionId=session.id,
        workspaceId=session.workspace_id,
        worktreePath=task_run.worktree_path,
        agentId=task_run.agent_id,
        adapterType="codex",
        instruction="Normalize an unexpected durable adapter binding failure.",
    )

    def raise_bind_fence_error(_: DbSession) -> bool:
        raise fence_error

    with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
        await run_adapter_event_stream(
            db,
            ExceptionalBindFenceAdapter(),
            request,
            ownership_guard=raise_bind_fence_error,
        )

    db.expire_all()
    stored = db.get(TaskRun, task_run.id)
    assert stored is not None
    assert stored.adapter_run_id is None
    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert exc_info.value.__cause__ is fence_error
    assert lifecycle == [
        ("interrupt", adapter_run_id),
        ("cleanup", adapter_run_id),
    ]


@pytest.mark.anyio
async def test_adapter_event_fence_runtime_error_is_normalized_despite_cleanup_failure(
    db: DbSession,
) -> None:
    session, task_run = create_task_run(db)
    adapter_run_id = f"event-exception-fenced-{task_run.id}"
    fence_error = RuntimeError("injected event fence failure")
    lifecycle: list[tuple[str, str]] = []
    ownership_checks = 0

    class ExceptionalEventFenceAdapter(FakeAdapter):
        async def createRun(self, request: AgentRunRequest) -> AdapterRun:
            return AdapterRun(adapterRunId=adapter_run_id)

        async def streamEvents(self, run_id: str) -> AsyncIterator[AgentEvent]:
            yield AgentEvent(
                type="completed",
                taskRunId=task_run.id,
                sequence=1,
                payload={"ok": True},
            )

        async def interrupt(self, run_id: str) -> None:
            lifecycle.append(("interrupt", run_id))
            raise RuntimeError("injected adapter interrupt failure")

        async def cleanup(self, run_id: str) -> None:
            lifecycle.append(("cleanup", run_id))
            raise RuntimeError("injected adapter cleanup failure")

    request = AgentRunRequest(
        taskRunId=task_run.id,
        sessionId=session.id,
        workspaceId=session.workspace_id,
        worktreePath=task_run.worktree_path,
        agentId=task_run.agent_id,
        adapterType="codex",
        instruction="Normalize an unexpected adapter event fence failure.",
    )

    def raise_event_fence_error(_: DbSession) -> bool:
        nonlocal ownership_checks
        ownership_checks += 1
        if ownership_checks == 2:
            raise fence_error
        return True

    with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
        await run_adapter_event_stream(
            db,
            ExceptionalEventFenceAdapter(),
            request,
            ownership_guard=raise_event_fence_error,
        )

    db.expire_all()
    stored = db.get(TaskRun, task_run.id)
    assert stored is not None
    assert stored.adapter_run_id == adapter_run_id
    assert ownership_checks == 2
    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert exc_info.value.__cause__ is fence_error
    assert db.exec(
        select(TaskRunEvent).where(TaskRunEvent.task_run_id == task_run.id)
    ).all() == []
    assert lifecycle == [
        ("interrupt", adapter_run_id),
        ("cleanup", adapter_run_id),
    ]


@pytest.mark.parametrize(
    ("fence_stage", "rollback_failure", "failing_rollback_call"),
    (
        ("bind", "entry", 1),
        ("bind", "normalization", 2),
        ("event", "entry", 2),
        ("event", "normalization", 3),
    ),
    ids=(
        "bind-entry",
        "bind-normalization",
        "event-entry",
        "event-normalization",
    ),
)
@pytest.mark.anyio
async def test_adapter_fence_rollback_failure_is_normalized_without_masking_primary(
    db: DbSession,
    monkeypatch: pytest.MonkeyPatch,
    fence_stage: str,
    rollback_failure: str,
    failing_rollback_call: int,
) -> None:
    session, task_run = create_task_run(db)
    adapter_run_id = f"rollback-fenced-{fence_stage}-{task_run.id}"
    fence_error = RuntimeError(f"injected {fence_stage} fence failure")
    rollback_error = RuntimeError(
        f"injected {fence_stage} {rollback_failure} rollback failure"
    )
    lifecycle: list[tuple[str, str]] = []
    ownership_checks = 0
    rollback_calls = 0

    class RollbackFailingFenceAdapter(FakeAdapter):
        async def createRun(self, request: AgentRunRequest) -> AdapterRun:
            return AdapterRun(adapterRunId=adapter_run_id)

        async def streamEvents(self, run_id: str) -> AsyncIterator[AgentEvent]:
            yield AgentEvent(
                type="completed",
                taskRunId=task_run.id,
                sequence=1,
                payload={"ok": True},
            )

        async def interrupt(self, run_id: str) -> None:
            lifecycle.append(("interrupt", run_id))

        async def cleanup(self, run_id: str) -> None:
            lifecycle.append(("cleanup", run_id))

    def fail_selected_fence(_: DbSession) -> bool:
        nonlocal ownership_checks
        ownership_checks += 1
        failing_ownership_check = 1 if fence_stage == "bind" else 2
        if (
            rollback_failure == "normalization"
            and ownership_checks == failing_ownership_check
        ):
            raise fence_error
        return True

    original_rollback = db.rollback

    def fail_selected_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        if rollback_calls == failing_rollback_call:
            raise rollback_error
        original_rollback()

    monkeypatch.setattr(db, "rollback", fail_selected_rollback)
    request = AgentRunRequest(
        taskRunId=task_run.id,
        sessionId=session.id,
        workspaceId=session.workspace_id,
        worktreePath=task_run.worktree_path,
        agentId=task_run.agent_id,
        adapterType="codex",
        instruction="Normalize rollback failures at every adapter ownership fence.",
    )

    try:
        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            await run_adapter_event_stream(
                db,
                RollbackFailingFenceAdapter(),
                request,
                ownership_guard=fail_selected_fence,
            )
    finally:
        original_rollback()

    expected_cause = fence_error if rollback_failure == "normalization" else rollback_error
    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert exc_info.value is not expected_cause
    assert exc_info.value.__cause__ is expected_cause
    assert rollback_calls == failing_rollback_call
    assert lifecycle == [
        ("interrupt", adapter_run_id),
        ("cleanup", adapter_run_id),
    ]


@pytest.mark.anyio
async def test_adapter_cleanup_cancellation_does_not_mask_scope_error(
    db: DbSession,
) -> None:
    session, task_run = create_task_run(db)
    adapter_run_id = f"cleanup-cancelled-fenced-{task_run.id}"
    lifecycle: list[tuple[str, str]] = []

    class CleanupCancelledAdapter(FakeAdapter):
        async def createRun(self, request: AgentRunRequest) -> AdapterRun:
            return AdapterRun(adapterRunId=adapter_run_id)

        async def interrupt(self, run_id: str) -> None:
            lifecycle.append(("interrupt", run_id))

        async def cleanup(self, run_id: str) -> None:
            lifecycle.append(("cleanup", run_id))
            raise asyncio.CancelledError("injected cleanup cancellation")

    request = AgentRunRequest(
        taskRunId=task_run.id,
        sessionId=session.id,
        workspaceId=session.workspace_id,
        worktreePath=task_run.worktree_path,
        agentId=task_run.agent_id,
        adapterType="codex",
        instruction="Preserve scope failure over cleanup cancellation.",
    )

    with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
        await run_adapter_event_stream(
            db,
            CleanupCancelledAdapter(),
            request,
            ownership_guard=lambda _: False,
        )

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert lifecycle == [
        ("interrupt", adapter_run_id),
        ("cleanup", adapter_run_id),
    ]


@pytest.mark.anyio
async def test_adapter_cleanup_cancellation_propagates_without_primary_error(
    db: DbSession,
) -> None:
    session, task_run = create_task_run(db)
    adapter_run_id = f"cleanup-cancelled-success-{task_run.id}"

    class CleanupCancelledAdapter(FakeAdapter):
        async def createRun(self, request: AgentRunRequest) -> AdapterRun:
            return AdapterRun(adapterRunId=adapter_run_id)

        async def streamEvents(self, run_id: str) -> AsyncIterator[AgentEvent]:
            if False:
                yield AgentEvent(
                    type="completed",
                    taskRunId=task_run.id,
                    sequence=1,
                    payload={"ok": True},
                )

        async def cleanup(self, run_id: str) -> None:
            raise asyncio.CancelledError("injected cleanup cancellation")

    request = AgentRunRequest(
        taskRunId=task_run.id,
        sessionId=session.id,
        workspaceId=session.workspace_id,
        worktreePath=task_run.worktree_path,
        agentId=task_run.agent_id,
        adapterType="codex",
        instruction="Propagate cleanup cancellation without a primary failure.",
    )

    with pytest.raises(asyncio.CancelledError):
        await run_adapter_event_stream(
            db,
            CleanupCancelledAdapter(),
            request,
            ownership_guard=lambda _: True,
        )


@pytest.mark.parametrize("failure_check", [1, 2])
@pytest.mark.anyio
async def test_adapter_fence_exception_interrupts_before_cleanup_without_masking(
    db: DbSession,
    failure_check: int,
) -> None:
    session, task_run = create_task_run(db)
    adapter_run_id = f"exception-fenced-{task_run.id}"
    lifecycle: list[tuple[str, str]] = []
    ownership_checks = 0
    scope_error = task_run_scope.TaskRunScopeError(
        "TASK_RUN_SCOPE_VIOLATION",
        "Injected non-normalized fence scope error.",
    )

    def raise_at_selected_fence(_: DbSession) -> bool:
        nonlocal ownership_checks
        ownership_checks += 1
        if ownership_checks == failure_check:
            raise scope_error
        return True

    class ExceptionalFenceAdapter(FakeAdapter):
        async def createRun(self, request: AgentRunRequest) -> AdapterRun:
            return AdapterRun(adapterRunId=adapter_run_id)

        async def streamEvents(self, run_id: str) -> AsyncIterator[AgentEvent]:
            yield AgentEvent(
                type="completed",
                taskRunId=task_run.id,
                sequence=1,
                payload={"ok": True},
            )

        async def interrupt(self, run_id: str) -> None:
            lifecycle.append(("interrupt", run_id))
            raise RuntimeError("injected adapter interrupt failure")

        async def cleanup(self, run_id: str) -> None:
            lifecycle.append(("cleanup", run_id))

    request = AgentRunRequest(
        taskRunId=task_run.id,
        sessionId=session.id,
        workspaceId=session.workspace_id,
        worktreePath=task_run.worktree_path,
        agentId=task_run.agent_id,
        adapterType="codex",
        instruction="Interrupt the exact run when an ownership fence raises.",
    )

    with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
        await run_adapter_event_stream(
            db,
            ExceptionalFenceAdapter(),
            request,
            ownership_guard=raise_at_selected_fence,
        )

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert exc_info.value is not scope_error
    assert exc_info.value.__cause__ is scope_error
    assert lifecycle == [
        ("interrupt", adapter_run_id),
        ("cleanup", adapter_run_id),
    ]


@pytest.mark.anyio
async def test_fake_adapter_events_persist_with_database_sequence_order(
    db: DbSession,
) -> None:
    session, task_run = create_task_run(db)
    adapter = FakeAdapter()
    request = AgentRunRequest(
        taskRunId=task_run.id,
        sessionId=session.id,
        workspaceId="workspace-id",
        worktreePath=task_run.worktree_path,
        agentId=task_run.agent_id,
        adapterType="codex",
        instruction="Build the login page.",
    )

    persisted = await run_adapter_event_stream(db, adapter, request)

    assert [event.event_type for event in persisted] == [
        "task.state",
        "message.delta",
        "completed",
    ]
    assert [event.sequence for event in persisted] == [1, 2, 3]
    assert [event.task_run_id for event in persisted] == [task_run.id] * 3
    assert persisted[1].payload_json == '{"text":"working"}'
    assert [event.sequence for event in list_session_events(db, session.id, 1)] == [2, 3]
    assert adapter.cleaned_run_id == f"fake-{task_run.id}"
    db.refresh(task_run)
    task = db.get(Task, task_run.task_id)
    assert task_run.state == "collecting_diff"
    assert task_run.ended_at is None
    assert task.status == "running"


@pytest.mark.anyio
async def test_task_state_completed_remains_collecting_diff(
    db: DbSession,
) -> None:
    session, task_run = create_task_run(db)

    class CompletedStateAdapter(FakeAdapter):
        async def streamEvents(self, run_id: str) -> AsyncIterator[AgentEvent]:
            yield AgentEvent(
                type="task.state",
                taskRunId=run_id.replace("fake-", ""),
                sequence=1,
                payload={"state": "completed"},
            )

    request = AgentRunRequest(
        taskRunId=task_run.id,
        sessionId=session.id,
        workspaceId="workspace-id",
        worktreePath=task_run.worktree_path,
        agentId=task_run.agent_id,
        adapterType="codex",
        instruction="Complete the adapter run.",
    )

    await run_adapter_event_stream(db, CompletedStateAdapter(), request)

    db.refresh(task_run)
    task = db.get(Task, task_run.task_id)
    assert task_run.state == "collecting_diff"
    assert task_run.ended_at is None
    assert task.status == "running"


@pytest.mark.parametrize(
    ("error_code", "expected_state"),
    (("TEST_FAILURE", "failed"), ("TEST_INTERRUPTED", "interrupted")),
)
@pytest.mark.anyio
async def test_adapter_terminal_event_retains_scope_runtime_without_decision(
    db: DbSession,
    error_code: str,
    expected_state: str,
) -> None:
    session, task_run = create_task_run(db)
    task_run_scope.store_task_run_scope_runtime_context(
        task_run.id,
        trusted_git_dir="trusted-gitdir",
        workspace_id="workspace-adapter-terminal",
        target_id="target-adapter-terminal",
        policy_identity="b" * 64,
        baseline_identity="baseline-adapter-terminal",
        baseline_captured_at="2026-07-18T00:00:00+00:00",
        execution_attempt_id="attempt-adapter-terminal",
    )

    class TerminalAdapter(FakeAdapter):
        async def streamEvents(self, run_id: str) -> AsyncIterator[AgentEvent]:
            yield AgentEvent(
                type="error",
                taskRunId=run_id.replace("fake-", ""),
                sequence=1,
                payload={"code": error_code, "message": "Adapter stopped."},
            )

    request = AgentRunRequest(
        taskRunId=task_run.id,
        sessionId=session.id,
        workspaceId="workspace-id",
        worktreePath=task_run.worktree_path,
        agentId=task_run.agent_id,
        adapterType="codex",
        instruction="Stop the adapter run.",
    )

    await run_adapter_event_stream(db, TerminalAdapter(), request)

    db.refresh(task_run)
    assert task_run.state == expected_state
    assert task_run_scope.get_task_run_scope_runtime_context(task_run.id) is not None
    task_run_scope.clear_task_run_scope_runtime_context(task_run.id)


@pytest.mark.anyio
async def test_adapter_event_publication_happens_after_persistence(
    db: DbSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, task_run = create_task_run(db)
    published_event_ids: list[str] = []

    def record_publish(session_id: str, event: TaskRunEvent) -> None:
        assert db.get(TaskRunEvent, event.id) is not None
        published_event_ids.append(event.id)

    monkeypatch.setattr("app.events.publish_event", record_publish)

    request = AgentRunRequest(
        taskRunId=task_run.id,
        sessionId=session.id,
        workspaceId="workspace-id",
        worktreePath=task_run.worktree_path,
        agentId=task_run.agent_id,
        adapterType="codex",
        instruction="Build the login page.",
    )
    persisted = await run_adapter_event_stream(db, FakeAdapter(), request)

    assert published_event_ids == [event.id for event in persisted]


@pytest.mark.anyio
async def test_user_interrupted_run_ignores_late_completed_event(
    db: DbSession,
) -> None:
    _, task_run = create_task_run(db)
    stream_started = asyncio.Event()
    release_completed = asyncio.Event()

    class LateCompletedAdapter(FakeAdapter):
        async def streamEvents(self, run_id: str) -> AsyncIterator[AgentEvent]:
            stream_started.set()
            await release_completed.wait()
            yield AgentEvent(
                type="completed",
                taskRunId=task_run.id,
                sequence=1,
                payload={"ok": True},
            )

    request = AgentRunRequest(
        taskRunId=task_run.id,
        sessionId=db.get(Task, task_run.task_id).session_id,
        workspaceId="workspace-id",
        worktreePath=task_run.worktree_path,
        agentId=task_run.agent_id,
        adapterType="codex",
        instruction="Pause before reporting completion.",
    )
    stream_task = asyncio.create_task(
        run_adapter_event_stream(db, LateCompletedAdapter(), request)
    )
    await asyncio.wait_for(stream_started.wait(), timeout=1)
    with DbSession(db.get_bind()) as interrupt_db:
        interrupt_task_run(interrupt_db, task_run.id)
    release_completed.set()
    with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
        await stream_task

    db.expire_all()
    stored = db.get(TaskRun, task_run.id)
    completed_events = db.exec(
        select(TaskRunEvent)
        .where(TaskRunEvent.task_run_id == task_run.id)
        .where(TaskRunEvent.event_type == "completed")
    ).all()
    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert completed_events == []
    assert stored.state == "interrupted"
    assert stored.error_code == "TASK_RUN_INTERRUPTED"
    assert stored.error_message == "Task run was interrupted by the user."


@pytest.mark.anyio
async def test_adapter_event_cannot_target_different_task_run(
    db: DbSession,
) -> None:
    first_session, first_run = create_task_run(db)
    other_run = TaskRun(
        task_id=first_run.task_id,
        agent_id=first_run.agent_id,
        state="created",
        worktree_path=first_run.worktree_path,
    )
    db.add(other_run)
    db.commit()
    db.refresh(other_run)

    class CrossRunAdapter(FakeAdapter):
        async def streamEvents(self, run_id: str) -> AsyncIterator[AgentEvent]:
            yield AgentEvent(
                type="completed",
                taskRunId=other_run.id,
                sequence=1,
                payload={"ok": True},
            )

    request = AgentRunRequest(
        taskRunId=first_run.id,
        sessionId=first_session.id,
        workspaceId=first_session.workspace_id,
        worktreePath=first_run.worktree_path,
        agentId=first_run.agent_id,
        adapterType="codex",
        instruction="Attempt a cross-run event.",
    )
    with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
        await run_adapter_event_stream(db, CrossRunAdapter(), request)

    db.expire_all()
    cross_run_events = db.exec(
        select(TaskRunEvent)
        .where(TaskRunEvent.task_run_id == other_run.id)
        .where(TaskRunEvent.event_type == "completed")
    ).all()
    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert cross_run_events == []
    assert db.get(TaskRun, first_run.id).state == "created"
    assert db.get(TaskRun, other_run.id).state == "created"
