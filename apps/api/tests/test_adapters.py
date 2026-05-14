from collections.abc import AsyncIterator

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine

from app.adapters import (
    AdapterCapabilities,
    AdapterRun,
    AgentAdapter,
    AgentEvent,
    AgentRunRequest,
    run_adapter_event_stream,
)
from app.events import list_session_events
from app.models import Agent, Session, Task, TaskRun, TaskRunEvent, Workspace


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


@pytest.mark.anyio
async def test_fake_adapter_events_persist_with_database_sequence_order(
    db: DbSession,
) -> None:
    session, task_run = create_task_run(db)
    adapter = FakeAdapter()
    request = AgentRunRequest(
        taskRunId=task_run.id,
        sessionId="session-id",
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


@pytest.mark.anyio
async def test_adapter_event_publication_happens_after_persistence(
    db: DbSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, task_run = create_task_run(db)
    published_event_ids: list[str] = []

    def record_publish(session_id: str, event: TaskRunEvent) -> None:
        assert db.get(TaskRunEvent, event.id) is not None
        published_event_ids.append(event.id)

    monkeypatch.setattr("app.events.publish_event", record_publish)

    request = AgentRunRequest(
        taskRunId=task_run.id,
        sessionId="session-id",
        workspaceId="workspace-id",
        worktreePath=task_run.worktree_path,
        agentId=task_run.agent_id,
        adapterType="codex",
        instruction="Build the login page.",
    )
    persisted = await run_adapter_event_stream(db, FakeAdapter(), request)

    assert published_event_ids == [event.id for event in persisted]
