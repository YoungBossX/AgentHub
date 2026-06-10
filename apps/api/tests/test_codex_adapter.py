import asyncio
import json
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Optional

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.adapters import AgentRunRequest, run_adapter_event_stream
from app.codex_adapter import CodexAdapter
from app.models import Agent, Session, Task, TaskRun, TaskRunEvent, Workspace


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
        self.waited = False

    async def stdout_lines(self) -> AsyncIterator[str]:
        for line in self.stdout.splitlines(keepends=True):
            yield line

    async def wait(self) -> int:
        self.waited = True
        return self.returncode

    async def stderr_text(self) -> str:
        return self.stderr

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
        "--skip-git-repo-check",
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
async def test_codex_transient_reconnecting_error_does_not_fail_completed_run(
    db: DbSession,
    tmp_path: Path,
) -> None:
    session, task_run = create_task_run(db, str(tmp_path))
    stdout = "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "codex-thread"}),
            json.dumps(
                {
                    "type": "error",
                    "message": "Reconnecting... 2/5 (timeout waiting for child process to exit)",
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
        "message.delta",
        "completed",
    ]
    reconnect_payload = json.loads(persisted[1].payload_json)
    assert reconnect_payload["transient"] is True
    assert reconnect_payload["text"].startswith("Reconnecting... 2/5")

    db.refresh(task_run)
    assert task_run.state == "completed"
    assert task_run.error_code is None
    assert task_run.error_message is None


@pytest.mark.anyio
async def test_codex_final_reconnecting_error_is_not_terminal_by_itself(
    db: DbSession,
    tmp_path: Path,
) -> None:
    session, task_run = create_task_run(db, str(tmp_path))
    stdout = "\n".join(
        [
            json.dumps(
                {
                    "type": "error",
                    "message": "Reconnecting... 5/5 (timeout waiting for child process to exit)",
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

    assert [event.event_type for event in persisted] == ["message.delta", "completed"]
    payload = json.loads(persisted[0].payload_json)
    assert payload["transient"] is True
    assert payload["text"].startswith("Reconnecting... 5/5")

    db.refresh(task_run)
    assert task_run.state == "completed"
    assert task_run.error_code is None


@pytest.mark.anyio
async def test_codex_reconnecting_then_nonzero_exit_maps_to_exit_failure(
    db: DbSession,
    tmp_path: Path,
) -> None:
    session, task_run = create_task_run(db, str(tmp_path))
    stdout = json.dumps(
        {
            "type": "error",
            "message": "Reconnecting... 5/5 (timeout waiting for child process to exit)",
        }
    )
    adapter = CodexAdapter(
        process_runner=FakeCodexRunner(
            FakeCodexProcess(
                stdout=f"{stdout}\n",
                stderr="usage limit reached after reconnect\n",
                returncode=1,
            )
        ),
        codex_binary="codex",
    )

    persisted = await run_adapter_event_stream(db, adapter, request_for(task_run, session))

    assert [event.event_type for event in persisted] == ["message.delta", "error"]
    payload = json.loads(persisted[1].payload_json)
    assert payload["code"] == "CODEX_USAGE_LIMIT"
    assert payload["exitCode"] == 1

    db.refresh(task_run)
    assert task_run.state == "failed"
    assert task_run.error_code == "CODEX_USAGE_LIMIT"


@pytest.mark.anyio
async def test_codex_specific_error_is_not_overwritten_by_generic_turn_failed(
    db: DbSession,
    tmp_path: Path,
) -> None:
    session, task_run = create_task_run(db, str(tmp_path))
    stdout = "\n".join(
        [
            json.dumps(
                {
                    "type": "error",
                    "message": (
                        "You've hit your usage limit. To get more access now, "
                        "send a request to your admin."
                    ),
                }
            ),
            json.dumps({"type": "turn.failed"}),
            "",
        ]
    )
    adapter = CodexAdapter(
        process_runner=FakeCodexRunner(FakeCodexProcess(stdout=stdout)),
        codex_binary="codex",
    )

    persisted = await run_adapter_event_stream(db, adapter, request_for(task_run, session))

    assert [event.event_type for event in persisted] == ["error"]
    payload = json.loads(persisted[0].payload_json)
    assert payload["code"] == "CODEX_USAGE_LIMIT"

    db.refresh(task_run)
    assert task_run.state == "failed"
    assert task_run.error_code == "CODEX_USAGE_LIMIT"
    assert "usage limit" in task_run.error_message


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
async def test_codex_forced_demo_failure_does_not_start_process(
    db: DbSession,
    tmp_path: Path,
) -> None:
    session, task_run = create_task_run(db, str(tmp_path))
    runner = FakeCodexRunner(FakeCodexProcess(stdout='{"type":"turn.completed"}\n'))
    adapter = CodexAdapter(process_runner=runner, codex_binary="codex")
    request = request_for(task_run, session)
    request.plan_context["forceFailure"] = True

    persisted = await run_adapter_event_stream(db, adapter, request)

    payload = json.loads(persisted[0].payload_json)
    assert runner.command is None
    assert persisted[0].event_type == "error"
    assert payload["code"] == "CODEX_DEMO_FORCED_FAILURE"
    assert "forced" in payload["message"].lower()

    db.refresh(task_run)
    assert task_run.state == "failed"
    assert task_run.error_code == "CODEX_DEMO_FORCED_FAILURE"


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


def test_codex_adapter_default_binary_is_macos_codex_app_path() -> None:
    from app.codex_adapter import DEFAULT_CODEX_BINARY

    assert DEFAULT_CODEX_BINARY == "/Applications/Codex.app/Contents/Resources/codex"


def test_codex_adapter_respects_codex_cli_path_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODEX_CLI_PATH", "/usr/local/bin/custom-codex")
    adapter = CodexAdapter()
    assert adapter._codex_binary == "/usr/local/bin/custom-codex"


def test_codex_adapter_falls_back_to_default_when_env_var_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CODEX_CLI_PATH", raising=False)
    adapter = CodexAdapter()
    assert adapter._codex_binary == "/Applications/Codex.app/Contents/Resources/codex"


def test_codex_adapter_constructor_binary_override_takes_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODEX_CLI_PATH", "/should/ignore/this")
    adapter = CodexAdapter(codex_binary="/explicit/path/codex")
    assert adapter._codex_binary == "/explicit/path/codex"


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


class DelayedFakeCodexProcess(FakeCodexProcess):
    def __init__(
        self,
        delay_sec: float = 0.2,
        stdout: str = '{"type":"turn.completed"}\n',
        stderr: str = "",
        returncode: int = 0,
    ) -> None:
        super().__init__(stdout=stdout, stderr=stderr, returncode=returncode)
        self.delay_sec = delay_sec

    async def stdout_lines(self) -> AsyncIterator[str]:
        for line in self.stdout.splitlines(keepends=True):
            await asyncio.sleep(self.delay_sec)
            yield line


class StepwiseFakeCodexProcess(FakeCodexProcess):
    def __init__(self) -> None:
        super().__init__(
            stdout="\n".join(
                [
                    json.dumps({"type": "thread.started", "thread_id": "thread-1"}),
                    json.dumps({"type": "message.delta", "delta": "still working"}),
                    json.dumps({"type": "turn.completed"}),
                    "",
                ]
            ),
        )
        self.first_line_yielded = asyncio.Event()
        self.resume_after_first_line = asyncio.Event()

    async def stdout_lines(self) -> AsyncIterator[str]:
        lines = self.stdout.splitlines(keepends=True)
        for index, line in enumerate(lines):
            if index == 0:
                self.first_line_yielded.set()
                yield line
                await self.resume_after_first_line.wait()
            else:
                yield line


@pytest.mark.anyio
async def test_codex_adapter_streams_jsonl_before_process_completion(
    tmp_path: Path,
) -> None:
    process = StepwiseFakeCodexProcess()
    adapter = CodexAdapter(
        process_runner=FakeCodexRunner(process),
        codex_binary="codex",
    )
    request = AgentRunRequest(
        taskRunId="task-run-stream",
        sessionId="session-1",
        workspaceId="workspace-1",
        worktreePath=str(tmp_path),
        agentId="agent-1",
        adapterType="codex",
        instruction="Stream test instruction.",
    )

    run = await adapter.createRun(request)
    stream = adapter.streamEvents(run.adapter_run_id)

    first_event = await asyncio.wait_for(stream.__anext__(), timeout=0.2)

    assert first_event.type == "task.state"
    assert first_event.payload["codexEventType"] == "thread.started"
    assert process.first_line_yielded.is_set()
    assert process.waited is False

    process.resume_after_first_line.set()
    remaining_events = [event async for event in stream]

    assert [event.type for event in remaining_events] == ["message.delta", "completed"]
    assert process.waited is True


@pytest.mark.anyio
async def test_codex_streamed_events_persist_before_process_completion(
    db: DbSession,
    tmp_path: Path,
) -> None:
    session, task_run = create_task_run(db, str(tmp_path))
    process = StepwiseFakeCodexProcess()
    adapter = CodexAdapter(
        process_runner=FakeCodexRunner(process),
        codex_binary="codex",
    )

    stream_task = asyncio.ensure_future(
        run_adapter_event_stream(db, adapter, request_for(task_run, session))
    )
    await asyncio.wait_for(process.first_line_yielded.wait(), timeout=0.2)
    await asyncio.sleep(0)

    early_events = db.exec(
        select(TaskRunEvent)
        .where(TaskRunEvent.task_run_id == task_run.id)
        .order_by(TaskRunEvent.sequence)
    ).all()

    assert process.waited is False
    assert [event.event_type for event in early_events] == ["task.state"]
    assert json.loads(early_events[0].payload_json)["codexEventType"] == "thread.started"

    process.resume_after_first_line.set()
    persisted = await stream_task

    assert [event.event_type for event in persisted] == [
        "task.state",
        "message.delta",
        "completed",
    ]
    assert process.waited is True


@pytest.mark.anyio
async def test_codex_adapter_does_not_block_event_loop_while_waiting_for_jsonl(
    tmp_path: Path,
) -> None:
    """Prove a long Codex process does not block other async tasks."""
    process = DelayedFakeCodexProcess(
        delay_sec=0.3,
        stdout='{"type":"thread.started","thread_id":"thread-1"}\n'
               '{"type":"turn.completed"}\n',
        returncode=0,
    )
    adapter = CodexAdapter(
        process_runner=FakeCodexRunner(process),
        codex_binary="codex",
    )
    request = AgentRunRequest(
        taskRunId="task-run-nb",
        sessionId="session-1",
        workspaceId="workspace-1",
        worktreePath=str(tmp_path),
        agentId="agent-1",
        adapterType="codex",
        instruction="Non-blocking test instruction.",
    )

    run = await adapter.createRun(request)

    stream_task = asyncio.ensure_future(_drain_events(adapter, run.adapter_run_id))

    # A concurrent task should complete BEFORE the delayed first line arrives.
    t0 = time.monotonic()
    await asyncio.sleep(0.05)
    t1 = time.monotonic()
    concurrent_elapsed = t1 - t0

    events = await stream_task
    t2 = time.monotonic()
    total_elapsed = t2 - t0

    # Concurrent sleep completed promptly (not blocked by stdout.readline)
    assert concurrent_elapsed < 0.2, (
        f"Event loop was blocked for {concurrent_elapsed:.2f}s"
    )
    # Total time confirms the adapter ran (delay was 0.3s)
    assert total_elapsed >= 0.25, (
        f"Adapter completed too quickly: {total_elapsed:.2f}s"
    )
    assert len(events) >= 1


async def _drain_events(
    adapter: CodexAdapter, run_id: str
) -> list[object]:
    return [event async for event in adapter.streamEvents(run_id)]
