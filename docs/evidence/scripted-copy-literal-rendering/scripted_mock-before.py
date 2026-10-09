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
SCRIPTED_TARGET_MUTATIONS = {
    "login_page": "login_page",
    "primary_action_button_text": "primary_button_copy",
    "demo_heading_text": "demo_heading_copy",
}
LOGIN_STYLE_START = "/* AgentHub scripted login form: start */"
LOGIN_STYLE_END = "/* AgentHub scripted login form: end */"
LOGIN_FORM_STYLES = """.login-form {
  display: grid;
  gap: 20px;
  margin-top: 22px;
  min-width: 0;
}

.login-form label {
  display: grid;
  gap: 8px;
  min-width: 0;
  color: #31405c;
  font-size: 0.875rem;
  font-weight: 600;
  line-height: 1.5;
}

.login-form input {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  min-height: 48px;
  padding: 12px 14px;
  border: 1px solid #c9d5e6;
  border-radius: 6px;
  background: #ffffff;
  color: #172033;
  font: inherit;
  font-size: 1rem;
  font-weight: 400;
  transition: border-color 120ms ease;
}

.login-form input::placeholder {
  color: #65738b;
  opacity: 1;
}

.login-form input:hover {
  border-color: #93a8c4;
}

.login-form input:focus-visible {
  border-color: #2563eb;
  outline: 2px solid #2563eb;
  outline-offset: 2px;
}
"""


class ScriptedMockAdapter(AgentAdapter):
    def __init__(self, *, read_only: bool = False) -> None:
        self._read_only = read_only
        self._runs: dict[str, AgentRunRequest] = {}
        self._interrupted: set[str] = set()

    def getCapabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supportsStreaming=True,
            supportsInterrupt=True,
            supportsApproval=True,
            supportsFileEdit=not self._read_only,
            supportsShellCommand=False,
            supportsDiffArtifact=False,
            supportsPreviewArtifact=False,
            supportsNetwork=False,
            maxRuntimeSec=30,
        )

    async def createRun(self, request: AgentRunRequest) -> AdapterRun:
        if self._read_only and (
            request.plan_context.get("planner") != "explicit_group_v1"
            or request.plan_context.get("readOnly") is not True
            or request.plan_context.get("assignedRole") not in {"qa", "review"}
        ):
            raise ValueError("Read-only scripted review requires an explicit group review task.")
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

        if self._read_only:
            # The server collects the real target Diff and produces the existing
            # bounded scripted report. This branch never performs a demo mutation.
            yield _event("message.delta", task_run_id, {
                "text": "只读脚本评审：由服务端收集当前目标的真实 Diff 并生成规则报告；未调用模型，也未执行测试命令。",
                "source": "scripted_mock", "readOnly": True,
            })
            yield _event("completed", task_run_id, {"adapter": "scripted_mock", "readOnly": True, "changedFiles": []})
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
            mutation, changed_files = self._apply_mutation(app_path, request)
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
                "changedFiles": changed_files,
                "mutation": mutation,
            },
        )
        yield _event(
            "completed",
            task_run_id,
            {
                "adapter": "scripted_mock",
                "changedFiles": changed_files,
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

    def _apply_mutation(self, app_path: Path, request: AgentRunRequest) -> tuple[str, list[str]]:
        original_app = app_path.read_bytes()
        source = app_path.read_text(encoding="utf-8")
        if "target" in request.plan_context:
            target = request.plan_context["target"]
            if not isinstance(target, str) or target not in SCRIPTED_TARGET_MUTATIONS:
                raise ValueError("Unsupported scripted demo task target.")
            mutation = SCRIPTED_TARGET_MUTATIONS[target]
            target_text = request.plan_context.get("targetText")
            if mutation != "login_page":
                if not isinstance(target_text, str) or not target_text.strip():
                    raise ValueError("Scripted copy changes require nonempty targetText.")
                target_text = target_text.strip()
        else:
            # Compatibility for legacy demo requests without a structured plan.
            instruction = request.instruction.lower()
            script = str(request.plan_context.get("script") or "").lower()
            target_text = _target_text_from(request)
            if "heading" in instruction or "title" in instruction or "heading" in script:
                mutation = "demo_heading_copy"
            elif "button" in instruction or "button" in script:
                mutation = "primary_button_copy"
            else:
                mutation = "login_page"

        if mutation == "demo_heading_copy":
            updated = _replace_demo_heading_text(source, target_text or "Welcome back")
        elif mutation == "primary_button_copy":
            updated = _replace_primary_button_text(source, target_text or "Let's get started")
        else:
            updated = _replace_login_slot(source)

        changes: list[tuple[Path, Optional[bytes], bytes]] = []
        if mutation == "login_page":
            styles_path = app_path.with_name("styles.css")
            if not evaluate_path(styles_path, request.worktree_path).allowed or styles_path.is_symlink():
                raise ValueError("The scripted demo stylesheet is unsafe.")
            try:
                if styles_path.exists() and (not styles_path.is_file() or styles_path.stat().st_nlink > 1):
                    raise ValueError("The scripted demo stylesheet is unsafe.")
                original_styles = styles_path.read_bytes() if styles_path.exists() else None
            except OSError as exc:
                raise ValueError("Could not read the scripted demo stylesheet.") from exc
            updated_styles = _login_form_styles(original_styles or b"")
            if updated_styles != original_styles:
                changes.append((styles_path, original_styles, updated_styles))
        if updated != source:
            newline = "\r\n" if b"\r\n" in original_app else "\n"
            changes.append((app_path, original_app, updated.replace("\n", newline).encode("utf-8")))
        if not changes:
            raise ValueError("The scripted mutation did not change the demo app.")

        _write_demo_mutation(changes)
        return mutation, [path.relative_to(request.worktree_path).as_posix() for path, _, _ in changes]


def _login_form_styles(original: bytes) -> bytes:
    source = original.decode("utf-8")
    newline = "\r\n" if "\r\n" in source else "\n"
    block = (LOGIN_STYLE_START + "\n" + LOGIN_FORM_STYLES + LOGIN_STYLE_END).replace("\n", newline)
    starts, ends = source.count(LOGIN_STYLE_START), source.count(LOGIN_STYLE_END)
    if starts or ends:
        if starts != 1 or ends != 1 or source.index(LOGIN_STYLE_START) >= source.index(LOGIN_STYLE_END):
            raise ValueError("The scripted login stylesheet has ambiguous managed markers.")
        begin = source.index(LOGIN_STYLE_START)
        end = source.index(LOGIN_STYLE_END) + len(LOGIN_STYLE_END)
        return (source[:begin] + block + source[end:]).encode("utf-8")
    separator = newline if not source or source.endswith("\n") else newline * 2
    return original + (separator + block + newline).encode("utf-8")


def _write_demo_mutation(changes: list[tuple[Path, Optional[bytes], bytes]]) -> None:
    attempted: list[tuple[Path, Optional[bytes]]] = []
    try:
        for path, original, updated in changes:
            attempted.append((path, original))
            path.write_bytes(updated)
    except OSError as exc:
        restored = True
        for path, original in reversed(attempted):
            try:
                if original is None:
                    path.unlink(missing_ok=True)
                elif not path.exists() or path.read_bytes() != original:
                    path.write_bytes(original)
            except OSError:
                restored = False
        message = (
            "Could not write the scripted demo mutation; original files restored."
            if restored else "Could not write the scripted demo mutation; file restoration failed."
        )
        raise ValueError(message) from exc


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
        "                <input type=\"email\" name=\"email\" autoComplete=\"username\" placeholder=\"you@example.com\" />\n"
        "              </label>\n"
        "              <label>\n"
        "                Password\n"
        "                <input type=\"password\" name=\"password\" autoComplete=\"current-password\" placeholder=\"Enter your password\" />\n"
        "              </label>\n"
        "            </form>"
        r"\2"
    )
    updated, count = pattern.subn(replacement, source, count=1)
    if count != 1:
        raise ValueError("Could not replace login page deterministic target.")
    return updated


def _replace_primary_button_text(source: str, target_text: str) -> str:
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
    updated, count = pattern.subn(
        rf"\1            {_escape_replacement(target_text)}\2",
        source,
        count=1,
    )
    if count != 1:
        raise ValueError("Could not replace primary action deterministic target.")
    return updated


def _replace_demo_heading_text(source: str, target_text: str) -> str:
    pattern = re.compile(r'(<h1\s+id="demo-heading"\s*>).*?(</h1>)', re.DOTALL)
    updated, count = pattern.subn(
        rf"\1{_escape_replacement(target_text)}\2",
        source,
        count=1,
    )
    if count != 1:
        raise ValueError("Could not replace demo heading.")
    return updated


def _target_text_from(request: AgentRunRequest) -> Optional[str]:
    target_text = request.plan_context.get("targetText")
    if isinstance(target_text, str) and target_text.strip():
        return target_text.strip()

    match = re.search(r'to\s+"([^"]+)"', request.instruction)
    if match:
        return match.group(1).strip()

    return None


def _escape_replacement(value: str) -> str:
    return value.replace("\\", r"\\")


def _event(event_type: str, task_run_id: str, payload: dict) -> AgentEvent:
    return AgentEvent(
        type=event_type,
        taskRunId=task_run_id,
        payload=payload,
    )
