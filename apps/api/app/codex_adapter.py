import asyncio
import json
import os
import re
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

DEFAULT_CODEX_BINARY = "/Applications/Codex.app/Contents/Resources/codex"
STDERR_LIMIT = 1200
RECONNECTING_ERROR_RE = re.compile(r"^Reconnecting\.\.\.\s+(\d+)/(\d+)\b")


class CodexProcess(Protocol):
    returncode: int

    def stdout_lines(self) -> AsyncIterator[str]:
        ...

    async def wait(self) -> int:
        ...

    async def stderr_text(self) -> str:
        ...

    def terminate(self) -> None:
        ...


class CodexProcessRunner(Protocol):
    def start(self, command: list[str], cwd: Path) -> CodexProcess:
        ...


class SubprocessCodexProcess:
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


class SubprocessCodexRunner:
    def start(self, command: list[str], cwd: Path) -> CodexProcess:
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return SubprocessCodexProcess(process)


@dataclass
class CodexRunState:
    request: AgentRunRequest
    command: list[str]
    cwd: Path
    process: Optional[CodexProcess] = None
    start_error: Optional[Exception] = None
    interrupted: bool = False


class CodexForcedFailure(RuntimeError):
    pass


class CodexAdapter(AgentAdapter):
    def __init__(
        self,
        process_runner: Optional[CodexProcessRunner] = None,
        codex_binary: Optional[str] = None,
    ) -> None:
        self._process_runner = process_runner or SubprocessCodexRunner()
        self._codex_binary = codex_binary or os.environ.get(
            "CODEX_CLI_PATH",
            DEFAULT_CODEX_BINARY,
        )
        self._runs: dict[str, CodexRunState] = {}

    def getCapabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supportsStreaming=True,
            supportsInterrupt=True,
            supportsApproval=False,
            supportsFileEdit=True,
            supportsShellCommand=True,
            supportsDiffArtifact=False,
            supportsPreviewArtifact=False,
            supportsNetwork=False,
            maxRuntimeSec=600,
        )

    async def createRun(self, request: AgentRunRequest) -> AdapterRun:
        run_id = f"codex-{uuid4()}"
        cwd = Path(request.worktree_path).expanduser().resolve(strict=False)
        command = self._build_command(request, cwd)
        state = CodexRunState(request=request, command=command, cwd=cwd)

        if request.plan_context.get("forceFailure"):
            state.start_error = CodexForcedFailure(
                "Forced Codex failure requested for demo recovery."
            )
            self._runs[run_id] = state
            return AdapterRun(adapterRunId=run_id)

        guardrail_decision = evaluate_command(command)
        if not guardrail_decision.allowed:
            state.start_error = PermissionError(
                guardrail_decision.approval.reason
                if guardrail_decision.approval
                else "Codex command blocked by guardrails."
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
                "CODEX_PROCESS_NOT_STARTED",
                "Codex process was not started.",
                command=state.command,
            )
            return

        stderr_task = asyncio.create_task(state.process.stderr_text())
        stderr_excerpt = ""
        terminal_event_seen = False
        specific_error_seen = False

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
                    "CODEX_STDOUT_PARSE_ERROR",
                    f"Could not parse Codex JSONL stdout line {index}.",
                    command=state.command,
                    stderr=stderr_excerpt,
                    rawLine=line,
                )
                return

            event = _map_codex_json_event(
                raw_event,
                request.task_run_id,
                stderr_excerpt,
                state.command,
            )
            if event is None:
                continue

            if event.type == "error":
                if _is_generic_failure_event(event) and specific_error_seen:
                    continue
                specific_error_seen = not _is_generic_failure_event(event)
            if event.type in {"completed", "error"}:
                terminal_event_seen = True
            yield event

        stderr_excerpt = await _finish_process(state.process, stderr_task)

        if state.interrupted:
            yield _error_event(
                request.task_run_id,
                "CODEX_INTERRUPTED",
                "Codex run was interrupted by AgentHub.",
                command=state.command,
                exitCode=state.process.returncode,
                stderr=stderr_excerpt,
            )
            return

        if state.process.returncode != 0 and not terminal_event_seen:
            code = _error_code_for_exit(state.process.returncode, stderr_excerpt)
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
                    "adapter": "codex",
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

    def _build_command(self, request: AgentRunRequest, cwd: Path) -> list[str]:
        return [
            self._codex_binary,
            "--ask-for-approval",
            "never",
            "exec",
            "--json",
            "--cd",
            str(cwd),
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            request.instruction,
        ]

    def _state_for(self, run_id: str) -> CodexRunState:
        state = self._runs.get(run_id)
        if state is None:
            raise ValueError(f"Unknown Codex run: {run_id}")
        return state


async def _finish_process(
    process: CodexProcess,
    stderr_task: "asyncio.Task[str]",
) -> str:
    await process.wait()
    stderr = await stderr_task
    return _stderr_excerpt(stderr)


def _map_codex_json_event(
    raw_event: dict[str, Any],
    task_run_id: str,
    stderr_excerpt: str,
    command: list[str],
) -> Optional[AgentEvent]:
    event_type = str(raw_event.get("type") or "")

    if event_type == "thread.started":
        return _event(
            "task.state",
            task_run_id,
            {
                "state": "streaming",
                "adapter": "codex",
                "codexEventType": event_type,
                "threadId": raw_event.get("thread_id") or raw_event.get("threadId"),
            },
        )

    if event_type == "turn.started":
        return _event(
            "task.state",
            task_run_id,
            {
                "state": "streaming",
                "adapter": "codex",
                "codexEventType": event_type,
            },
        )

    if event_type in {"message.delta", "agent_message_delta"}:
        text = raw_event.get("delta") or raw_event.get("text") or raw_event.get("message")
        return _event(
            "message.delta",
            task_run_id,
            {
                "text": str(text or ""),
                "adapter": "codex",
                "codexEventType": event_type,
            },
        )

    if event_type in {"turn.completed", "turn.finished"}:
        return _event(
            "completed",
            task_run_id,
            {
                "adapter": "codex",
                "codexEventType": event_type,
                "stderr": stderr_excerpt,
            },
        )

    if event_type in {"turn.failed", "error"}:
        message = _codex_error_message(raw_event)
        if _is_reconnecting_error(message):
            return _event(
                "message.delta",
                task_run_id,
                {
                    "text": message,
                    "adapter": "codex",
                    "codexEventType": event_type,
                    "transient": True,
                },
            )
        code = _error_code_for_text(message)
        return _error_event(
            task_run_id,
            code,
            message,
            command=command,
            stderr=stderr_excerpt,
            codexEventType=event_type,
        )

    if event_type:
        return _event(
            "message.delta",
            task_run_id,
            {
                "text": json.dumps(raw_event, separators=(",", ":")),
                "adapter": "codex",
                "codexEventType": event_type,
            },
        )

    return None


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
        "adapter": "codex",
    }
    normalized_payload.update(
        {key: value for key, value in payload.items() if value is not None}
    )
    return _event("error", task_run_id, normalized_payload)


def _is_generic_failure_event(event: AgentEvent) -> bool:
    return (
        event.type == "error"
        and event.payload.get("code") == "CODEX_EXIT_ERROR"
        and event.payload.get("message") == "Codex run failed."
    )


def _codex_error_message(raw_event: dict[str, Any]) -> str:
    for key in ("message", "error", "reason"):
        value = raw_event.get(key)
        if isinstance(value, str) and value:
            return value
    return "Codex run failed."


def _is_reconnecting_error(message: str) -> bool:
    return RECONNECTING_ERROR_RE.match(message) is not None


def _stderr_excerpt(stderr: str) -> str:
    if len(stderr) <= STDERR_LIMIT:
        return stderr
    return stderr[:STDERR_LIMIT]


def _error_code_for_exception(exc: Exception) -> str:
    if isinstance(exc, CodexForcedFailure):
        return "CODEX_DEMO_FORCED_FAILURE"
    if isinstance(exc, FileNotFoundError):
        return "CODEX_NOT_FOUND"
    if isinstance(exc, PermissionError):
        return "CODEX_GUARDRAIL_BLOCKED"
    return _error_code_for_text(str(exc))


def _message_for_exception(exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        return "Codex CLI executable was not found."
    return str(exc) or "Codex process could not be started."


def _error_code_for_exit(exit_code: int, text: str) -> str:
    if exit_code == 2:
        return "CODEX_ARGUMENT_ERROR"
    return _error_code_for_text(text)


def _error_code_for_text(text: str) -> str:
    normalized = text.lower()
    if "usage limit" in normalized or "rate limit" in normalized:
        return "CODEX_USAGE_LIMIT"
    if "auth" in normalized or "login" in normalized or "unauthorized" in normalized:
        return "CODEX_AUTH_REQUIRED"
    if "interrupted" in normalized or "sigint" in normalized:
        return "CODEX_INTERRUPTED"
    return "CODEX_EXIT_ERROR"


def _message_for_exit(code: str, exit_code: int, stderr: str) -> str:
    if code == "CODEX_USAGE_LIMIT":
        return "Codex CLI exited because local usage limits were reached."
    if code == "CODEX_AUTH_REQUIRED":
        return "Codex CLI requires authentication or a valid login state."
    if code == "CODEX_ARGUMENT_ERROR":
        return "Codex CLI rejected the invocation arguments."
    if stderr.strip():
        return stderr.strip().splitlines()[0]
    return f"Codex CLI exited with status {exit_code}."
