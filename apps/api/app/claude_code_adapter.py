import asyncio
import json
import os
import subprocess
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Protocol
from uuid import uuid4

from app.adapters import (
    AdapterApproval,
    AdapterArtifact,
    AdapterCapabilities,
    AdapterRun,
    AgentAdapter,
    AgentEvent,
    AgentRunRequest,
)
from app.guardrails import evaluate_command

DEFAULT_CLAUDE_BINARY = "claude"
STDERR_LIMIT = 1200


class ClaudeCodeProcess(Protocol):
    returncode: int

    def stdout_lines(self) -> AsyncIterator[str]:
        ...

    async def wait(self) -> int:
        ...

    async def stderr_text(self) -> str:
        ...

    def terminate(self) -> None:
        ...


class ClaudeCodeProcessRunner(Protocol):
    def start(self, command: list[str], cwd: Path) -> ClaudeCodeProcess:
        ...


class SubprocessClaudeCodeProcess:
    def __init__(self, process: subprocess.Popen[str]) -> None:
        self._process = process

    @property
    def returncode(self) -> int:
        return int(self._process.returncode or 0)

    async def stdout_lines(self) -> AsyncIterator[str]:
        if self._process.stdout is None:
            return

        while True:
            line = await asyncio.to_thread(self._process.stdout.readline)
            if line == "":
                break
            yield line

    async def wait(self) -> int:
        return int(await asyncio.to_thread(self._process.wait))

    async def stderr_text(self) -> str:
        if self._process.stderr is None:
            return ""
        return await asyncio.to_thread(self._process.stderr.read)

    def terminate(self) -> None:
        self._process.terminate()


class SubprocessClaudeCodeRunner:
    def start(self, command: list[str], cwd: Path) -> ClaudeCodeProcess:
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return SubprocessClaudeCodeProcess(process)


@dataclass
class ClaudeCodeRunState:
    request: AgentRunRequest
    command: list[str]
    cwd: Path
    process: Optional[ClaudeCodeProcess] = None
    start_error: Optional[Exception] = None
    interrupted: bool = False


class ClaudeCodeAdapter(AgentAdapter):
    def __init__(
        self,
        process_runner: Optional[ClaudeCodeProcessRunner] = None,
        claude_binary: Optional[str] = None,
        max_budget_usd: str = "1.00",
    ) -> None:
        self._process_runner = process_runner or SubprocessClaudeCodeRunner()
        self._claude_binary = claude_binary or os.environ.get(
            "CLAUDE_CODE_CLI_PATH",
            DEFAULT_CLAUDE_BINARY,
        )
        self._max_budget_usd = max_budget_usd
        self._runs: dict[str, ClaudeCodeRunState] = {}

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
            maxRuntimeSec=600,
        )

    async def createRun(self, request: AgentRunRequest) -> AdapterRun:
        run_id = f"claude-code-{uuid4()}"
        cwd = Path(request.worktree_path).expanduser().resolve(strict=False)
        command = self._build_command(request)
        state = ClaudeCodeRunState(request=request, command=command, cwd=cwd)

        guardrail_decision = evaluate_command(command)
        if not guardrail_decision.allowed:
            state.start_error = PermissionError(
                guardrail_decision.approval.reason
                if guardrail_decision.approval
                else "Claude Code command blocked by guardrails."
            )
            self._runs[run_id] = state
            return AdapterRun(adapterRunId=run_id)

        try:
            state.process = self._process_runner.start(command, cwd)
        except Exception as exc:
            state.start_error = exc

        self._runs[run_id] = state
        return AdapterRun(adapterRunId=run_id)

    async def streamEvents(self, run_id: str) -> AsyncIterator[AgentEvent]:
        state = self._state_for(run_id)
        request = state.request

        if state.start_error is not None:
            yield _error_event(
                request.task_run_id,
                _error_code_for_exception(state.start_error),
                _message_for_exception(state.start_error),
                command=state.command,
            )
            return

        if state.process is None:
            yield _error_event(
                request.task_run_id,
                "CLAUDE_CODE_PROCESS_NOT_STARTED",
                "Claude Code process was not started.",
                command=state.command,
            )
            return

        stderr_task = asyncio.create_task(state.process.stderr_text())
        stderr_excerpt = ""
        terminal_event_seen = False

        index = 0
        async for line in state.process.stdout_lines():
            if not line.strip():
                continue

            index += 1
            try:
                raw_event = json.loads(line)
            except json.JSONDecodeError:
                state.process.terminate()
                stderr_excerpt = await _finish_process(state.process, stderr_task)
                terminal_event_seen = True
                yield _error_event(
                    request.task_run_id,
                    "CLAUDE_CODE_STDOUT_PARSE_ERROR",
                    f"Could not parse Claude Code stream-json stdout line {index}.",
                    command=state.command,
                    stderr=stderr_excerpt,
                    rawLine=line,
                )
                return

            event = _map_claude_json_event(
                raw_event,
                request.task_run_id,
                stderr_excerpt,
                state.command,
            )
            if event is None:
                continue
            if event.type in {"completed", "error"}:
                terminal_event_seen = True
            yield event

        stderr_excerpt = await _finish_process(state.process, stderr_task)

        if state.interrupted:
            yield _error_event(
                request.task_run_id,
                "CLAUDE_CODE_INTERRUPTED",
                "Claude Code run was interrupted by AgentHub.",
                command=state.command,
                exitCode=state.process.returncode,
                stderr=stderr_excerpt,
            )
            return

        if state.process.returncode != 0 and not terminal_event_seen:
            code = _error_code_for_text(stderr_excerpt)
            yield _error_event(
                request.task_run_id,
                code,
                _message_for_exit(code, state.process.returncode, stderr_excerpt),
                command=state.command,
                exitCode=state.process.returncode,
                stderr=stderr_excerpt,
            )
            return

        if state.process.returncode == 0 and not terminal_event_seen:
            yield _event(
                "completed",
                request.task_run_id,
                {
                    "adapter": "claude_code",
                    "exitCode": 0,
                    "stderr": stderr_excerpt,
                },
            )

    async def interrupt(self, run_id: str) -> None:
        state = self._state_for(run_id)
        state.interrupted = True
        if state.process is not None:
            state.process.terminate()

    async def approve(self, run_id: str, approval: AdapterApproval) -> None:
        return None

    async def collectArtifacts(self, run_id: str) -> list[AdapterArtifact]:
        return []

    async def cleanup(self, run_id: str) -> None:
        self._runs.pop(run_id, None)

    def _build_command(self, request: AgentRunRequest) -> list[str]:
        return [
            self._claude_binary,
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
            self._max_budget_usd,
            request.instruction,
        ]

    def _state_for(self, run_id: str) -> ClaudeCodeRunState:
        state = self._runs.get(run_id)
        if state is None:
            raise ValueError(f"Unknown Claude Code run: {run_id}")
        return state


async def _finish_process(
    process: ClaudeCodeProcess,
    stderr_task: "asyncio.Task[str]",
) -> str:
    await process.wait()
    stderr = await stderr_task
    return _stderr_excerpt(stderr)


def _map_claude_json_event(
    raw_event: dict[str, Any],
    task_run_id: str,
    stderr_excerpt: str,
    command: list[str],
) -> Optional[AgentEvent]:
    event_type = str(raw_event.get("type") or "")

    if event_type in {"system", "session.started", "thread.started"}:
        return _event(
            "task.state",
            task_run_id,
            {
                "state": "streaming",
                "adapter": "claude_code",
                "claudeEventType": event_type,
                "sessionId": raw_event.get("session_id") or raw_event.get("sessionId"),
            },
        )

    if event_type in {
        "assistant",
        "message",
        "message.delta",
        "content_block_delta",
    }:
        return _event(
            "message.delta",
            task_run_id,
            {
                "text": _text_from_event(raw_event),
                "adapter": "claude_code",
                "claudeEventType": event_type,
            },
        )

    if event_type in {"result", "completed", "turn.completed"}:
        if _result_is_error(raw_event):
            message = _claude_error_message(raw_event)
            return _error_event(
                task_run_id,
                _error_code_for_text(message),
                message,
                command=command,
                stderr=stderr_excerpt,
                claudeEventType=event_type,
            )

        return _event(
            "completed",
            task_run_id,
            {
                "adapter": "claude_code",
                "claudeEventType": event_type,
                "stderr": stderr_excerpt,
            },
        )

    if event_type in {"error", "turn.failed"}:
        message = _claude_error_message(raw_event)
        return _error_event(
            task_run_id,
            _error_code_for_text(message),
            message,
            command=command,
            stderr=stderr_excerpt,
            claudeEventType=event_type,
        )

    if event_type == "stream_event":
        return _map_claude_stream_event(raw_event, task_run_id)

    if event_type:
        return _event(
            "message.delta",
            task_run_id,
            {
                "text": json.dumps(raw_event, separators=(",", ":")),
                "adapter": "claude_code",
                "claudeEventType": event_type,
            },
        )

    return None


def _map_claude_stream_event(
    raw_event: dict[str, Any],
    task_run_id: str,
) -> Optional[AgentEvent]:
    nested = raw_event.get("event")
    if not isinstance(nested, dict):
        return None

    nested_type = str(nested.get("type") or "")
    session_id = raw_event.get("session_id") or raw_event.get("sessionId")

    if nested_type == "message_start":
        return _event(
            "task.state",
            task_run_id,
            {
                "state": "streaming",
                "adapter": "claude_code",
                "claudeEventType": "stream_event",
                "claudeStreamEventType": nested_type,
                "sessionId": session_id,
            },
        )

    if nested_type == "content_block_start":
        content_block = nested.get("content_block")
        if isinstance(content_block, dict) and isinstance(content_block.get("text"), str):
            text = content_block["text"]
            if text:
                return _claude_stream_text_event(
                    task_run_id,
                    text,
                    nested_type,
                    session_id,
                )
        return None

    if nested_type == "content_block_delta":
        delta = nested.get("delta")
        if not isinstance(delta, dict):
            return None
        if delta.get("type") == "text_delta" and isinstance(delta.get("text"), str):
            return _claude_stream_text_event(
                task_run_id,
                delta["text"],
                nested_type,
                session_id,
            )
        return None

    return None


def _claude_stream_text_event(
    task_run_id: str,
    text: str,
    nested_type: str,
    session_id: Any,
) -> AgentEvent:
    return _event(
        "message.delta",
        task_run_id,
        {
            "text": text,
            "adapter": "claude_code",
            "claudeEventType": "stream_event",
            "claudeStreamEventType": nested_type,
            "sessionId": session_id,
        },
    )


def _text_from_event(raw_event: dict[str, Any]) -> str:
    delta = raw_event.get("delta")
    if isinstance(delta, dict):
        text = delta.get("text")
        if isinstance(text, str):
            return text
    if isinstance(delta, str):
        return delta

    for key in ("text", "message", "result"):
        value = raw_event.get(key)
        if isinstance(value, str):
            return value

    message = raw_event.get("message")
    if isinstance(message, dict):
        return _text_from_content(message.get("content"))

    return _text_from_content(raw_event.get("content"))


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return ""


def _result_is_error(raw_event: dict[str, Any]) -> bool:
    subtype = str(raw_event.get("subtype") or "").lower()
    if raw_event.get("is_error") is True:
        return True
    return subtype.startswith("error") or subtype in {"failed", "failure"}


def _event(event_type: str, task_run_id: str, payload: dict[str, Any]) -> AgentEvent:
    return AgentEvent(type=event_type, taskRunId=task_run_id, payload=payload)


def _error_event(
    task_run_id: str,
    code: str,
    message: str,
    **payload: Any,
) -> AgentEvent:
    normalized_payload = {
        "code": code,
        "message": message,
        "adapter": "claude_code",
    }
    normalized_payload.update(
        {key: value for key, value in payload.items() if value is not None}
    )
    return _event("error", task_run_id, normalized_payload)


def _claude_error_message(raw_event: dict[str, Any]) -> str:
    for key in ("message", "error", "reason", "result"):
        value = raw_event.get(key)
        if isinstance(value, str) and value:
            return value
        if isinstance(value, dict):
            nested = value.get("message") or value.get("text")
            if isinstance(nested, str) and nested:
                return nested
    return "Claude Code run failed."


def _stderr_excerpt(stderr: str) -> str:
    if len(stderr) <= STDERR_LIMIT:
        return stderr
    return stderr[:STDERR_LIMIT]


def _error_code_for_exception(exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        return "CLAUDE_CODE_NOT_FOUND"
    if isinstance(exc, PermissionError):
        return "CLAUDE_CODE_GUARDRAIL_BLOCKED"
    if isinstance(exc, TimeoutError):
        return "CLAUDE_CODE_TIMEOUT"
    return _error_code_for_text(str(exc))


def _message_for_exception(exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        return "Claude Code CLI executable was not found."
    if isinstance(exc, TimeoutError):
        return "Claude Code process timed out before startup completed."
    return str(exc) or "Claude Code process could not be started."


def _error_code_for_text(text: str) -> str:
    normalized = text.lower()
    if "usage limit" in normalized or "rate limit" in normalized or "quota" in normalized:
        return "CLAUDE_CODE_USAGE_LIMIT"
    if (
        "auth" in normalized
        or "login" in normalized
        or "not logged in" in normalized
        or "unauthorized" in normalized
        or "api key" in normalized
    ):
        return "CLAUDE_CODE_AUTH_REQUIRED"
    if "interrupted" in normalized or "sigint" in normalized:
        return "CLAUDE_CODE_INTERRUPTED"
    if "timeout" in normalized or "timed out" in normalized:
        return "CLAUDE_CODE_TIMEOUT"
    return "CLAUDE_CODE_EXIT_ERROR"


def _message_for_exit(code: str, exit_code: int, stderr: str) -> str:
    if code == "CLAUDE_CODE_USAGE_LIMIT":
        return "Claude Code exited because local usage or rate limits were reached."
    if code == "CLAUDE_CODE_AUTH_REQUIRED":
        return "Claude Code requires authentication or a valid login state."
    if code == "CLAUDE_CODE_TIMEOUT":
        return "Claude Code execution timed out."
    if stderr.strip():
        return stderr.strip().splitlines()[0]
    return f"Claude Code exited with status {exit_code}."
