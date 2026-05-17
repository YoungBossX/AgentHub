import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Optional

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine

from app.adapters import AgentRunRequest, run_adapter_event_stream
from app.claude_code_adapter import ClaudeCodeAdapter
from app.main import adapter_for_type
from app.models import Agent, Session, Task, TaskRun, Workspace


class FakeClaudeCodeProcess:
    def __init__(
        self,
        stdout: str = "",
        stderr: str = "",
        returncode: int = 0,
        line_delay_sec: float = 0,
    ) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.line_delay_sec = line_delay_sec
        self.terminated = False
        self.waited = False

    async def stdout_lines(self) -> AsyncIterator[str]:
        for line in self.stdout.splitlines(keepends=True):
            if self.line_delay_sec:
                await asyncio.sleep(self.line_delay_sec)
            yield line

    async def wait(self) -> int:
        self.waited = True
        return self.returncode

    async def stderr_text(self) -> str:
        return self.stderr

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 1


class FakeClaudeCodeRunner:
    def __init__(
        self,
        process: Optional[FakeClaudeCodeProcess] = None,
        error: Optional[Exception] = None,
    ) -> None:
        self.process = process or FakeClaudeCodeProcess()
        self.error = error
        self.command: Optional[list[str]] = None
        self.cwd: Optional[Path] = None

    def start(self, command: list[str], cwd: Path) -> FakeClaudeCodeProcess:
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
        title="Claude Code adapter session",
        bound_branch="main",
        worktree_path=worktree_path,
    )
    agent = Agent(
        name="Frontend Agent",
        role="frontend",
        adapter_type="claude_code",
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
        adapterType="claude_code",
        instruction="Change only the primary button text to Sign in.",
    )


@pytest.mark.anyio
async def test_claude_code_adapter_builds_documented_command_shape(
    tmp_path: Path,
) -> None:
    process = FakeClaudeCodeProcess(stdout='{"type":"result"}\n')
    runner = FakeClaudeCodeRunner(process)
    adapter = ClaudeCodeAdapter(
        process_runner=runner,
        claude_binary="claude",
        max_budget_usd="0.25",
    )
    request = AgentRunRequest(
        taskRunId="task-run-1",
        sessionId="session-1",
        workspaceId="workspace-1",
        worktreePath=str(tmp_path),
        agentId="agent-1",
        adapterType="claude_code",
        instruction="Make the button text more friendly.",
    )

    await adapter.createRun(request)

    assert runner.command == [
        "claude",
        "--print",
        "--verbose",
        "--output-format",
        "stream-json",
        "--include-partial-messages",
        "--permission-mode",
        "dontAsk",
        "--allowedTools",
        "Read,Edit,MultiEdit",
        "--no-session-persistence",
        "--max-budget-usd",
        "0.25",
        "Make the button text more friendly.",
    ]
    assert runner.cwd == tmp_path


@pytest.mark.anyio
async def test_claude_code_stream_json_events_persist_with_sequence_order(
    db: DbSession,
    tmp_path: Path,
) -> None:
    session, task_run = create_task_run(db, str(tmp_path))
    stdout = "\n".join(
        [
            json.dumps({"type": "system", "session_id": "claude-session"}),
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "text", "text": "Applying focused change."}
                        ]
                    },
                }
            ),
            json.dumps({"type": "result", "subtype": "success"}),
            "",
        ]
    )
    adapter = ClaudeCodeAdapter(
        process_runner=FakeClaudeCodeRunner(FakeClaudeCodeProcess(stdout=stdout)),
        claude_binary="claude",
    )

    persisted = await run_adapter_event_stream(db, adapter, request_for(task_run, session))

    assert [event.event_type for event in persisted] == [
        "task.state",
        "message.delta",
        "completed",
    ]
    assert [event.sequence for event in persisted] == [1, 2, 3]
    assert json.loads(persisted[0].payload_json)["claudeEventType"] == "system"
    assert json.loads(persisted[1].payload_json)["text"] == "Applying focused change."

    db.refresh(task_run)
    assert task_run.state == "completed"
    assert task_run.error_code is None


@pytest.mark.anyio
async def test_claude_code_yields_incrementally_before_process_completion(
    tmp_path: Path,
) -> None:
    stdout = "\n".join(
        [
            json.dumps({"type": "assistant", "text": "first"}),
            json.dumps({"type": "assistant", "text": "second"}),
            json.dumps({"type": "result"}),
            "",
        ]
    )
    process = FakeClaudeCodeProcess(stdout=stdout, line_delay_sec=0.01)
    adapter = ClaudeCodeAdapter(
        process_runner=FakeClaudeCodeRunner(process),
        claude_binary="claude",
    )
    run = await adapter.createRun(
        AgentRunRequest(
            taskRunId="task-run-1",
            sessionId="session-1",
            workspaceId="workspace-1",
            worktreePath=str(tmp_path),
            agentId="agent-1",
            adapterType="claude_code",
            instruction="Make a small edit.",
        )
    )

    stream = adapter.streamEvents(run.adapter_run_id)
    first_event = await stream.__anext__()
    await stream.aclose()

    assert first_event.type == "message.delta"
    assert first_event.payload["text"] == "first"
    assert process.waited is False


@pytest.mark.anyio
async def test_claude_code_nonzero_exit_maps_usage_limit_and_captures_stderr(
    db: DbSession,
    tmp_path: Path,
) -> None:
    session, task_run = create_task_run(db, str(tmp_path))
    stderr = "diagnostic line\n" + ("usage limit reached\n" * 100)
    adapter = ClaudeCodeAdapter(
        process_runner=FakeClaudeCodeRunner(
            FakeClaudeCodeProcess(stdout="", stderr=stderr, returncode=1)
        ),
        claude_binary="claude",
    )

    persisted = await run_adapter_event_stream(db, adapter, request_for(task_run, session))

    assert [event.event_type for event in persisted] == ["error"]
    payload = json.loads(persisted[0].payload_json)
    assert payload["code"] == "CLAUDE_CODE_USAGE_LIMIT"
    assert "usage" in payload["message"].lower()
    assert payload["exitCode"] == 1
    assert "diagnostic line" in payload["stderr"]
    assert len(payload["stderr"]) <= 1200

    db.refresh(task_run)
    assert task_run.state == "failed"
    assert task_run.error_code == "CLAUDE_CODE_USAGE_LIMIT"


@pytest.mark.anyio
async def test_claude_code_stream_event_text_delta_filters_thinking_delta(
    db: DbSession,
    tmp_path: Path,
) -> None:
    session, task_run = create_task_run(db, str(tmp_path))
    stdout = "\n".join(
        [
            json.dumps({"type": "system", "session_id": "claude-session"}),
            json.dumps(
                {
                    "type": "stream_event",
                    "session_id": "claude-session",
                    "event": {
                        "type": "message_start",
                        "message": {"id": "message-1"},
                    },
                }
            ),
            json.dumps(
                {
                    "type": "stream_event",
                    "session_id": "claude-session",
                    "event": {
                        "type": "content_block_delta",
                        "delta": {"type": "thinking_delta", "thinking": "hidden"},
                    },
                }
            ),
            json.dumps(
                {
                    "type": "stream_event",
                    "session_id": "claude-session",
                    "event": {
                        "type": "content_block_delta",
                        "delta": {"type": "text_delta", "text": "Done"},
                    },
                }
            ),
            json.dumps({"type": "result", "subtype": "success"}),
            "",
        ]
    )
    adapter = ClaudeCodeAdapter(
        process_runner=FakeClaudeCodeRunner(FakeClaudeCodeProcess(stdout=stdout)),
        claude_binary="claude",
    )

    persisted = await run_adapter_event_stream(db, adapter, request_for(task_run, session))

    payloads = [json.loads(event.payload_json) for event in persisted]
    assert [event.event_type for event in persisted] == [
        "task.state",
        "task.state",
        "message.delta",
        "completed",
    ]
    assert payloads[2]["text"] == "Done"
    assert "hidden" not in json.dumps(payloads)


@pytest.mark.anyio
async def test_claude_code_auth_required_event_is_normalized(
    db: DbSession,
    tmp_path: Path,
) -> None:
    session, task_run = create_task_run(db, str(tmp_path))
    stdout = json.dumps(
        {"type": "error", "message": "Not logged in. Run claude auth login."}
    )
    adapter = ClaudeCodeAdapter(
        process_runner=FakeClaudeCodeRunner(FakeClaudeCodeProcess(stdout=f"{stdout}\n")),
        claude_binary="claude",
    )

    persisted = await run_adapter_event_stream(db, adapter, request_for(task_run, session))

    payload = json.loads(persisted[0].payload_json)
    assert payload["code"] == "CLAUDE_CODE_AUTH_REQUIRED"
    assert "not logged in" in payload["message"].lower()
    db.refresh(task_run)
    assert task_run.state == "failed"


@pytest.mark.anyio
async def test_claude_code_cli_unavailable_is_normalized(
    db: DbSession,
    tmp_path: Path,
) -> None:
    session, task_run = create_task_run(db, str(tmp_path))
    adapter = ClaudeCodeAdapter(
        process_runner=FakeClaudeCodeRunner(error=FileNotFoundError("claude")),
        claude_binary="claude",
    )

    persisted = await run_adapter_event_stream(db, adapter, request_for(task_run, session))

    payload = json.loads(persisted[0].payload_json)
    assert payload["code"] == "CLAUDE_CODE_NOT_FOUND"
    assert "not found" in payload["message"].lower()


@pytest.mark.anyio
async def test_claude_code_malformed_jsonl_is_parse_error(
    db: DbSession,
    tmp_path: Path,
) -> None:
    session, task_run = create_task_run(db, str(tmp_path))
    process = FakeClaudeCodeProcess(stdout="{not json}\n")
    adapter = ClaudeCodeAdapter(
        process_runner=FakeClaudeCodeRunner(process),
        claude_binary="claude",
    )

    persisted = await run_adapter_event_stream(db, adapter, request_for(task_run, session))

    assert process.terminated is True
    payload = json.loads(persisted[0].payload_json)
    assert payload["code"] == "CLAUDE_CODE_STDOUT_PARSE_ERROR"
    assert "{not json}" in payload["rawLine"]


@pytest.mark.anyio
async def test_claude_code_interrupt_terminates_process_and_marks_interrupted(
    db: DbSession,
    tmp_path: Path,
) -> None:
    session, task_run = create_task_run(db, str(tmp_path))
    process = FakeClaudeCodeProcess(stdout="")
    adapter = ClaudeCodeAdapter(
        process_runner=FakeClaudeCodeRunner(process),
        claude_binary="claude",
    )
    run = await adapter.createRun(request_for(task_run, session))

    await adapter.interrupt(run.adapter_run_id)
    persisted = [
        event async for event in adapter.streamEvents(run.adapter_run_id)
    ]

    assert process.terminated is True
    assert persisted[0].type == "error"
    assert persisted[0].payload["code"] == "CLAUDE_CODE_INTERRUPTED"


@pytest.mark.anyio
async def test_claude_code_timeout_startup_is_normalized(
    db: DbSession,
    tmp_path: Path,
) -> None:
    session, task_run = create_task_run(db, str(tmp_path))
    adapter = ClaudeCodeAdapter(
        process_runner=FakeClaudeCodeRunner(error=TimeoutError("startup timed out")),
        claude_binary="claude",
    )

    persisted = await run_adapter_event_stream(db, adapter, request_for(task_run, session))

    payload = json.loads(persisted[0].payload_json)
    assert payload["code"] == "CLAUDE_CODE_TIMEOUT"
    assert "timed out" in payload["message"].lower()


def test_claude_code_adapter_type_is_dispatchable() -> None:
    adapter = ClaudeCodeAdapter(
        process_runner=FakeClaudeCodeRunner(),
        claude_binary="claude",
    )

    assert (
        adapter_for_type(
            "claude_code",
            codex_adapter=adapter,
            claude_code_adapter=adapter,
            scripted_mock_adapter=adapter,
        )
        is adapter
    )
