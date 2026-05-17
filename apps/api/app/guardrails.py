import json
import shlex
from pathlib import Path
from typing import Literal, Optional, Sequence, Union

from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session as DbSession

from app.events import append_task_run_event
from app.models import Task, TaskRun
from app.models import utc_now

ApprovalType = Literal["product_confirmation", "security_approval"]
RiskLevel = Literal["low", "medium", "high"]

PROJECT_COMMANDS = {
    ("pnpm", "check"),
    ("pnpm", "test"),
    ("pnpm", "db:init"),
    ("pnpm", "dev:api"),
    ("pnpm", "dev:web"),
    ("pnpm", "demo:setup"),
    ("pnpm", "demo:dev"),
}
GIT_ALLOWLIST = {"rev-parse", "worktree", "diff", "status"}
PROTECTED_PATH_NAMES = {".git", "secrets", "node_modules"}
PROTECTED_FILE_NAMES = {".env"}
SYSTEM_PATH_PREFIXES = (
    Path("/bin"),
    Path("/dev"),
    Path("/etc"),
    Path("/private"),
    Path("/sbin"),
    Path("/System"),
    Path("/usr"),
    Path("/var"),
)


class GuardrailModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class ApprovalRequestPayload(GuardrailModel):
    approval_type: ApprovalType = Field(alias="approvalType")
    reason: str
    requested_action: str = Field(alias="requestedAction")
    risk_level: RiskLevel = Field(alias="riskLevel")
    command: Optional[str] = None
    path: Optional[str] = None
    expires_at: Optional[str] = Field(default=None, alias="expiresAt")


class GuardrailDecision(GuardrailModel):
    allowed: bool
    approval: Optional[ApprovalRequestPayload] = None


CommandInput = Union[str, Sequence[str]]


def evaluate_command(command: CommandInput) -> GuardrailDecision:
    parts = _command_parts(command)
    display = shlex.join(parts)
    if not parts:
        return _approval_decision(
            reason="Empty commands are not executable in P0.",
            requested_action=display,
            command=display,
        )

    if _is_allowed_project_command(parts) or _is_allowed_runtime_command(parts):
        return GuardrailDecision(allowed=True)

    return _approval_decision(
        reason="Command is outside the P0 allowlist.",
        requested_action=display,
        command=display,
    )


def evaluate_path(path: Union[str, Path], worktree_path: Union[str, Path]) -> GuardrailDecision:
    candidate = Path(path).expanduser()
    worktree = Path(worktree_path).expanduser().resolve(strict=False)
    if not candidate.is_absolute():
        candidate = worktree / candidate
    candidate = candidate.resolve(strict=False)

    try:
        candidate.relative_to(worktree)
    except ValueError:
        if _is_system_path(candidate):
            return _path_approval(
                candidate,
                "System paths are outside the assigned session worktree.",
            )
        return _path_approval(
            candidate,
            "Path is outside the assigned session worktree.",
        )

    if _is_protected_path(candidate, worktree):
        return _path_approval(candidate, "Path is protected by P0 guardrails.")

    return GuardrailDecision(allowed=True)


def evaluate_network_access(network_approved: bool = False) -> GuardrailDecision:
    if network_approved:
        return GuardrailDecision(allowed=True)

    return _approval_decision(
        reason="Network access is disabled by default for P0 agent execution.",
        requested_action="network access",
    )


def request_task_run_approval(
    db: DbSession,
    task_run_id: str,
    payload: ApprovalRequestPayload,
):
    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        raise ValueError(f"TaskRun not found: {task_run_id}")

    task = db.get(Task, task_run.task_id)
    if task is None:
        raise ValueError(f"Task not found for TaskRun: {task_run_id}")

    now = utc_now()
    task.status = "waiting_approval"
    task.updated_at = now
    task_run.state = "waiting_approval"
    task_run.updated_at = now
    db.add(task)
    db.add(task_run)
    db.commit()

    return append_task_run_event(
        db,
        task_run_id=task_run.id,
        event_type="approval.requested",
        payload_json=_payload_json(payload),
    )


def approve_task_run(db: DbSession, task_run_id: str) -> None:
    _resolve_task_run_approval(
        db,
        task_run_id=task_run_id,
        task_status="running",
        run_state="queued",
        event_payload={"approved": True},
    )


def deny_task_run(db: DbSession, task_run_id: str, reason: str) -> None:
    _resolve_task_run_approval(
        db,
        task_run_id=task_run_id,
        task_status="failed",
        run_state="failed",
        event_payload={"approved": False, "reason": reason},
        error_code="APPROVAL_DENIED",
        error_message=reason,
    )


def _command_parts(command: CommandInput) -> list[str]:
    if isinstance(command, str):
        return shlex.split(command)
    return [str(part) for part in command]


def _is_allowed_project_command(parts: list[str]) -> bool:
    return tuple(parts) in PROJECT_COMMANDS


def _is_allowed_runtime_command(parts: list[str]) -> bool:
    git_subcommand = _git_subcommand(parts)
    if git_subcommand is not None:
        if git_subcommand == "apply":
            return "--check" in parts
        return git_subcommand in GIT_ALLOWLIST

    if _is_vite_preview_command(parts):
        return True

    if Path(parts[0]).name == "codex":
        return True

    if _is_claude_code_command(parts):
        return True

    return False


def _git_subcommand(parts: list[str]) -> Optional[str]:
    if not parts or parts[0] != "git":
        return None

    index = 1
    while index < len(parts):
        if parts[index] == "-C" and index + 1 < len(parts):
            index += 2
            continue
        if parts[index].startswith("-"):
            index += 1
            continue
        return parts[index]
    return None


def _is_vite_preview_command(parts: list[str]) -> bool:
    return (
        len(parts) == 6
        and parts[:4] == ["pnpm", "dev", "--host", "127.0.0.1"]
        and parts[4] == "--port"
        and parts[5].isdigit()
    )


def _is_claude_code_command(parts: list[str]) -> bool:
    return (
        len(parts) >= 13
        and Path(parts[0]).name == "claude"
        and "--print" in parts
        and "--verbose" in parts
        and _option_value(parts, "--output-format") == "stream-json"
        and "--include-partial-messages" in parts
        and _option_value(parts, "--permission-mode") == "dontAsk"
        and _option_value(parts, "--allowedTools") == "Read,Edit,MultiEdit"
        and "--no-session-persistence" in parts
        and _option_value(parts, "--max-budget-usd") is not None
    )


def _option_value(parts: list[str], option: str) -> Optional[str]:
    try:
        index = parts.index(option)
    except ValueError:
        return None
    if index + 1 >= len(parts):
        return None
    return parts[index + 1]


def _is_system_path(path: Path) -> bool:
    return any(path == prefix or prefix in path.parents for prefix in SYSTEM_PATH_PREFIXES)


def _is_protected_path(path: Path, worktree: Path) -> bool:
    try:
        relative = path.relative_to(worktree)
    except ValueError:
        return True

    parts = relative.parts
    if any(part in PROTECTED_PATH_NAMES for part in parts):
        return True

    name = relative.name
    return name in PROTECTED_FILE_NAMES or name.startswith(".env.")


def _approval_decision(
    reason: str,
    requested_action: str,
    command: Optional[str] = None,
) -> GuardrailDecision:
    return GuardrailDecision(
        allowed=False,
        approval=ApprovalRequestPayload(
            approvalType="security_approval",
            reason=reason,
            requestedAction=requested_action,
            riskLevel="high",
            command=command,
        ),
    )


def _path_approval(path: Path, reason: str) -> GuardrailDecision:
    return GuardrailDecision(
        allowed=False,
        approval=ApprovalRequestPayload(
            approvalType="security_approval",
            reason=reason,
            requestedAction=f"edit {path}",
            riskLevel="high",
            path=str(path),
        ),
    )


def _payload_json(payload: ApprovalRequestPayload) -> str:
    return json.dumps(
        payload.model_dump(by_alias=True, exclude_none=True),
        separators=(",", ":"),
    )


def _resolve_task_run_approval(
    db: DbSession,
    task_run_id: str,
    task_status: str,
    run_state: str,
    event_payload: dict,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        raise ValueError(f"TaskRun not found: {task_run_id}")

    task = db.get(Task, task_run.task_id)
    if task is None:
        raise ValueError(f"Task not found for TaskRun: {task_run_id}")

    now = utc_now()
    task.status = task_status
    task.updated_at = now
    task_run.state = run_state
    task_run.error_code = error_code
    task_run.error_message = error_message
    task_run.updated_at = now
    db.add(task)
    db.add(task_run)
    db.commit()

    append_task_run_event(
        db,
        task_run_id=task_run.id,
        event_type="task.state",
        payload_json=json.dumps(event_payload, separators=(",", ":")),
    )
