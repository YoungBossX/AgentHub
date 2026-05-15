import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Optional
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
from app.guardrails import evaluate_network_access, evaluate_path

LOGIN_SLOT_TARGET = 'data-agenthub-target="login-page-slot"'
PRIMARY_BUTTON_TARGET = 'data-agenthub-target="primary-action-button"'


class ScriptedMockAdapter(AgentAdapter):
    def __init__(self) -> None:
        self._runs: dict[str, AgentRunRequest] = {}
        self._interrupted: set[str] = set()

    def getCapabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supportsStreaming=True,
            supportsInterrupt=True,
            supportsApproval=True,
            supportsFileEdit=True,
            supportsShellCommand=False,
            supportsDiffArtifact=False,
            supportsPreviewArtifact=False,
            supportsNetwork=False,
            maxRuntimeSec=30,
        )

    async def createRun(self, request: AgentRunRequest) -> AdapterRun:
        run_id = f"scripted-mock-{uuid4()}"
        self._runs[run_id] = request
        return AdapterRun(adapterRunId=run_id)

    async def streamEvents(self, run_id: str) -> AsyncIterator[AgentEvent]:
        request = self._request_for(run_id)
        task_run_id = request.task_run_id

        yield _event(
            "task.state",
            task_run_id,
            {"state": "streaming", "adapter": "scripted_mock"},
        )

        if run_id in self._interrupted:
            yield _event(
                "error",
                task_run_id,
                {
                    "code": "SCRIPTED_MOCK_INTERRUPTED",
                    "message": "Scripted mock run was interrupted before mutation.",
                },
            )
            return

        if request.plan_context.get("simulateApproval"):
            yield _event(
                "approval.requested",
                task_run_id,
                {
                    "approvalType": "product_confirmation",
                    "reason": "Scripted mock approval simulation requested.",
                    "requestedAction": "continue scripted mock mutation",
                    "riskLevel": "low",
                },
            )
            return

        if request.plan_context.get("forceFailure"):
            yield _event(
                "error",
                task_run_id,
                {
                    "code": "SCRIPTED_MOCK_FORCED_FAILURE",
                    "message": "Forced scripted mock failure requested.",
                },
            )
            return

        network_decision = evaluate_network_access()
        if network_decision.allowed:
            yield _event(
                "error",
                task_run_id,
                {
                    "code": "GUARDRAIL_NETWORK_UNEXPECTEDLY_ALLOWED",
                    "message": "Network access must remain disabled by default.",
                },
            )
            return

        target_path = Path(
            request.plan_context.get("targetPath") or "apps/demo/src/App.tsx"
        )
        path_decision = evaluate_path(target_path, request.worktree_path)
        if not path_decision.allowed:
            approval = path_decision.approval
            yield _event(
                "error",
                task_run_id,
                {
                    "code": "GUARDRAIL_BLOCKED_PATH",
                    "message": approval.reason if approval else "Path blocked.",
                    "path": approval.path if approval else str(target_path),
                },
            )
            return

        app_path = Path(request.worktree_path) / "apps/demo/src/App.tsx"
        if not app_path.exists():
            yield _event(
                "error",
                task_run_id,
                {
                    "code": "SCRIPTED_MOCK_DEMO_FILE_MISSING",
                    "message": "Could not find apps/demo/src/App.tsx in the session worktree.",
                },
            )
            return

        yield _event(
            "message.delta",
            task_run_id,
            {"text": "Applying deterministic Vite React demo mutation."},
        )

        try:
            mutation = self._apply_mutation(app_path, request)
        except ValueError as exc:
            yield _event(
                "error",
                task_run_id,
                {"code": "SCRIPTED_MOCK_MUTATION_FAILED", "message": str(exc)},
            )
            return

        yield _event(
            "task.state",
            task_run_id,
            {
                "state": "applying_changes",
                "adapter": "scripted_mock",
                "changedFiles": ["apps/demo/src/App.tsx"],
                "mutation": mutation,
            },
        )
        yield _event(
            "completed",
            task_run_id,
            {
                "adapter": "scripted_mock",
                "changedFiles": ["apps/demo/src/App.tsx"],
                "mutation": mutation,
            },
        )

    async def interrupt(self, run_id: str) -> None:
        self._interrupted.add(run_id)

    async def approve(self, run_id: str, approval: AdapterApproval) -> None:
        return None

    async def collectArtifacts(self, run_id: str) -> list[AdapterArtifact]:
        return []

    async def cleanup(self, run_id: str) -> None:
        self._runs.pop(run_id, None)
        self._interrupted.discard(run_id)

    def _request_for(self, run_id: str) -> AgentRunRequest:
        request = self._runs.get(run_id)
        if request is None:
            raise ValueError(f"Unknown scripted mock run: {run_id}")
        return request

    def _apply_mutation(self, app_path: Path, request: AgentRunRequest) -> str:
        source = app_path.read_text()
        instruction = request.instruction.lower()
        script = str(request.plan_context.get("script") or "").lower()

        if "button" in instruction or "button" in script:
            updated = _replace_primary_button_text(source)
            mutation = "primary_button_copy"
        else:
            updated = _replace_login_slot(source)
            mutation = "login_page"

        if updated == source:
            raise ValueError("The scripted mutation did not change the demo app.")

        app_path.write_text(updated)
        return mutation


def _replace_login_slot(source: str) -> str:
    if LOGIN_SLOT_TARGET not in source:
        raise ValueError("Missing login page deterministic target.")

    pattern = re.compile(
        r'(<div\s+className="login-slot"\s+'
        r'data-agenthub-target="login-page-slot"\s+'
        r'aria-label="Login page insertion target"\s*>\n)'
        r".*?"
        r"(\n\s*</div>)",
        re.DOTALL,
    )
    replacement = (
        r"\1"
        "            <p className=\"slot-label\">Welcome back</p>\n"
        "            <form className=\"login-form\" aria-label=\"Demo login form\">\n"
        "              <label>\n"
        "                Email address\n"
        "                <input type=\"email\" placeholder=\"you@example.com\" />\n"
        "              </label>\n"
        "              <label>\n"
        "                Password\n"
        "                <input type=\"password\" placeholder=\"Enter your password\" />\n"
        "              </label>\n"
        "            </form>"
        r"\2"
    )
    updated, count = pattern.subn(replacement, source, count=1)
    if count != 1:
        raise ValueError("Could not replace login page deterministic target.")
    return updated


def _replace_primary_button_text(source: str) -> str:
    if PRIMARY_BUTTON_TARGET not in source:
        raise ValueError("Missing primary action deterministic target.")

    pattern = re.compile(
        r'(<button\s+className="primary-action"\s+'
        r'data-agenthub-target="primary-action-button"\s+'
        r'type="button"\s*>\n)'
        r"\s*.*?\s*"
        r"(\n\s*</button>)",
        re.DOTALL,
    )
    updated, count = pattern.subn(r"\1            Let's get started\2", source, count=1)
    if count != 1:
        raise ValueError("Could not replace primary action deterministic target.")
    return updated


def _event(event_type: str, task_run_id: str, payload: dict) -> AgentEvent:
    return AgentEvent(
        type=event_type,
        taskRunId=task_run_id,
        payload=payload,
    )
