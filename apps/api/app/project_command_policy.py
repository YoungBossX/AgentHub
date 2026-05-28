import shlex
from dataclasses import dataclass
from typing import Optional

from app.target_registry import TargetProject

COMMAND_TYPE_FIELDS = {
    "check": "check_command",
    "test": "test_command",
    "build": "build_command",
}


@dataclass(frozen=True)
class ProjectCommandDecision:
    allowed: bool
    reason: str
    target_id: Optional[str]
    command_type: str
    command: str


def evaluate_project_command(
    *,
    target: TargetProject,
    command_type: str,
    command: str,
) -> ProjectCommandDecision:
    normalized_type = command_type.strip().lower()
    normalized_command = _normalize_command(command)
    configured_command = _configured_command_for_type(target, normalized_type)
    if configured_command is None:
        return ProjectCommandDecision(
            allowed=False,
            reason=(
                f"Target {target.target_id} does not configure a "
                f"{normalized_type} command."
            ),
            target_id=target.target_id,
            command_type=normalized_type,
            command=normalized_command,
        )
    if _commands_equal(normalized_command, configured_command):
        return ProjectCommandDecision(
            allowed=True,
            reason="Command matches the registered target command policy.",
            target_id=target.target_id,
            command_type=normalized_type,
            command=normalized_command,
        )
    return ProjectCommandDecision(
        allowed=False,
        reason=(
            f"Command is not allowed for target {target.target_id}; expected "
            f"{configured_command!r} for {normalized_type} evidence."
        ),
        target_id=target.target_id,
        command_type=normalized_type,
        command=normalized_command,
    )


def allowed_validation_commands(target: TargetProject) -> dict[str, str]:
    commands: dict[str, str] = {}
    for command_type in COMMAND_TYPE_FIELDS:
        configured = _configured_command_for_type(target, command_type)
        if configured:
            commands[command_type] = configured
    return commands


def _configured_command_for_type(
    target: TargetProject,
    command_type: str,
) -> Optional[str]:
    field_name = COMMAND_TYPE_FIELDS.get(command_type)
    if field_name is None:
        return None
    configured = getattr(target, field_name)
    if not isinstance(configured, str) or not configured.strip():
        return None
    return _normalize_command(configured)


def _commands_equal(left: str, right: str) -> bool:
    return _command_parts(left) == _command_parts(right)


def _normalize_command(command: str) -> str:
    parts = _command_parts(command)
    return shlex.join(parts) if parts else command.strip()


def _command_parts(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return []
