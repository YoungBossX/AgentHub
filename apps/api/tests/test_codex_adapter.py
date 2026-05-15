import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Optional

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine

from app.adapters import AgentRunRequest, run_adapter_event_stream
from app.codex_adapter import CodexAdapter
from app.models import Agent, Session, Task, TaskRun, Workspace


class FakeCodexProcess:
    def __init__(
        self,
        stdout: str = "",
        stderr: str = "",
        returncode: int = 0,
    ) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.communicated = False
        self.terminated = False

    def communicate(self) -> tuple[str, str]:
        self.communicated = True
        return self.stdout, self.stderr

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 1


class FakeCodexRunner:
    def __init__(
        self,
        process: Optional[FakeCodexProcess] = None,
        error: Optional[Exception] = None,
    ) -> None:
        self.process = process or FakeCodexProcess()
        self.error = error
        self.command: Optional[list[str]] = None
        self.cwd: Optional[Path] = None

    def start(self, command: list[str], cwd: Path) -> FakeCodexProcess:
        self.command = command
        self.cwd = cwd
        if self.error is not None:
            raise self.error
        return self.process


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


def create_task_run(db: DbSession, worktree_path: str) -> tuple[Session, TaskRun]:
    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="Codex adapter session",
        bound_branch="main",
        worktree_path=worktree_path,
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
        status="running",
        assigned_agent_id=agent.id,
    )
    task_run = TaskRun(
        task_id=task.id,
        agent_id=agent.id,
        state="running",
        worktree_path=session.worktree_path,
    )

    db.add(workspace)
    db.add(session)
    db.add(agent)
    db.add(task)
    db.add(task_run)
    db.commit()
    db.refresh(session)
    db.refresh(task_run)
    return session, task_run


def request_for(task_run: TaskRun, session: Session) -> AgentRunRequest:
    return AgentRunRequest(
        taskRunId=task_run.id,
        sessionId=session.id,
        workspaceId=session.workspace_id,
        worktreePath=task_run.worktree_path,
        agentId=task_run.agent_id,
        adapterType="codex",
        instruction="Build the login page for the demo app.",
    )


@pytest.mark.anyio
async def test_codex_adapter_builds_documented_command_shape(tmp_path: Path) -> None:
    process = FakeCodexProcess(stdout='{"type":"turn.completed"}\n')
    runner = FakeCodexRunner(process)
    adapter = CodexAdapter(process_runner=runner, codex_binary="codex")
    request = AgentRunRequest(
        taskRunId="task-run-1",
        sessionId="session-1",
        workspaceId="workspace-1",
        worktreePath=str(tmp_path),
        agentId="agent-1",
        adapterType="codex",
        instruction="Make the button text more friendly.",
    )

    await adapter.createRun(request)

    assert runner.command == [
        "codex",
        "--ask-for-approval",
        "never",
        "exec",
        "--json",
        "--cd",
        str(tmp_path),
        "--sandbox",
        "workspace-write",
        "Make the button text more friendly.",
    ]
    assert runner.command.index("--ask-for-approval") < runner.command.index("exec")
    assert runner.cwd == tmp_path


@pytest.mark.anyio
async def test_codex_stdout_jsonl_events_persist_with_sequence_order(
    db: DbSession,
    tmp_path: Path,
) -> None:
    session, task_run = create_task_run(db, str(tmp_path))
    stdout = "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "codex-thread"}),
            json.dumps({"type": "turn.started"}),
            json.dumps(
                {
                    "type": "message.delta",
                    "delta": "Applying focused demo app change.",
                }
            ),
            json.dumps({"type": "turn.completed"}),
            "",
        ]
    )
    adapter = CodexAdapter(
        process_runner=FakeCodexRunner(FakeCodexProcess(stdout=stdout)),
        codex_binary="codex",
    )

    persisted = await run_adapter_event_stream(db, adapter, request_for(task_run, session))

    assert [event.event_type for event in persisted] == [
        "task.state",
        "task.state",
        "message.delta",
        "completed",
    ]
    assert [event.sequence for event in persisted] == [1, 2, 3, 4]
    assert json.loads(persisted[0].payload_json)["codexEventType"] == "thread.started"
    assert json.loads(persisted[2].payload_json)["text"] == (
        "Applying focused demo app change."
    )

    db.refresh(task_run)
    assert task_run.state == "completed"
    assert task_run.error_code is None
    assert task_run.error_message is None


@pytest.mark.anyio
async def test_codex_nonzero_exit_maps_to_task_run_error_and_captures_stderr(
    db: DbSession,
    tmp_path: Path,
) -> None:
    session, task_run = create_task_run(db, str(tmp_path))
    stderr = "plugin diagnostic line\n" + ("usage limit reached\n" * 100)
    adapter = CodexAdapter(
        process_runner=FakeCodexRunner(
            FakeCodexProcess(stdout="", stderr=stderr, returncode=1)
        ),
        codex_binary="codex",
    )

    persisted = await run_adapter_event_stream(db, adapter, request_for(task_run, session))

    assert [event.event_type for event in persisted] == ["error"]
    payload = json.loads(persisted[0].payload_json)
    assert payload["code"] == "CODEX_USAGE_LIMIT"
    assert "usage limit" in payload["message"].lower()
    assert payload["exitCode"] == 1
    assert "plugin diagnostic line" in payload["stderr"]
    assert len(payload["stderr"]) <= 1200

    db.refresh(task_run)
    assert task_run.state == "failed"
    assert task_run.error_code == "CODEX_USAGE_LIMIT"
    assert "usage limit" in task_run.error_message.lower()


@pytest.mark.anyio
async def test_codex_cli_unavailable_is_normalized_without_raising(
    db: DbSession,
    tmp_path: Path,
) -> None:
    session, task_run = create_task_run(db, str(tmp_path))
    adapter = CodexAdapter(
        process_runner=FakeCodexRunner(error=FileNotFoundError("codex")),
        codex_binary="codex",
    )

    persisted = await run_adapter_event_stream(db, adapter, request_for(task_run, session))

    payload = json.loads(persisted[0].payload_json)
    assert persisted[0].event_type == "error"
    assert payload["code"] == "CODEX_NOT_FOUND"
    assert "Codex CLI" in payload["message"]

    db.refresh(task_run)
    assert task_run.state == "failed"
    assert task_run.error_code == "CODEX_NOT_FOUND"


@pytest.mark.anyio
async def test_codex_malformed_jsonl_is_normalized_as_parse_error(
    db: DbSession,
    tmp_path: Path,
) -> None:
    session, task_run = create_task_run(db, str(tmp_path))
    adapter = CodexAdapter(
        process_runner=FakeCodexRunner(FakeCodexProcess(stdout="{not json}\n")),
        codex_binary="codex",
    )

    persisted = await run_adapter_event_stream(db, adapter, request_for(task_run, session))

    payload = json.loads(persisted[0].payload_json)
    assert persisted[0].event_type == "error"
    assert payload["code"] == "CODEX_STDOUT_PARSE_ERROR"
    assert "line 1" in payload["message"]


@pytest.mark.anyio
async def test_codex_interrupt_terminates_process_and_marks_run_interrupted(
    tmp_path: Path,
) -> None:
    process = FakeCodexProcess(
        stdout=json.dumps({"type": "thread.started", "thread_id": "codex-thread"}),
        returncode=0,
    )
    adapter = CodexAdapter(
        process_runner=FakeCodexRunner(process),
        codex_binary="codex",
    )
    request = AgentRunRequest(
        taskRunId="task-run-1",
        sessionId="session-1",
        workspaceId="workspace-1",
        worktreePath=str(tmp_path),
        agentId="agent-1",
        adapterType="codex",
        instruction="Build the login page.",
    )

    run = await adapter.createRun(request)
    await adapter.interrupt(run.adapter_run_id)
    events = [event async for event in adapter.streamEvents(run.adapter_run_id)]

    assert process.terminated is True
    assert events[-1].type == "error"
    assert events[-1].payload["code"] == "CODEX_INTERRUPTED"
