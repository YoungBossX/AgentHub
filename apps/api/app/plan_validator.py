from __future__ import annotations

from app.agent_profiles import AgentProfile
from app.agent_target_compatibility import supports_target_id
from app.project_command_policy import allowed_validation_commands
from app.target_registry import TargetProject
from app.task_graph_builder import TaskGraphTaskSpec


GRAPH_AGENT_ROLES = {"orchestrator", "backend", "frontend", "qa"}
GRAPH_EXPECTED_ARTIFACTS = {"plan", "diff", "review"}
GRAPH_ALLOWED_FILES = {
    "apps/demo-api/app/main.py",
    "apps/demo-api/tests/test_contacts.py",
    "apps/demo/src/App.tsx",
    "apps/demo/src/styles.css",
}


class PlanValidationError(ValueError):
    pass


def validate_task_graph(
    task_specs: list[TaskGraphTaskSpec],
    *,
    allowed_targets: dict[str, TargetProject] | None = None,
    agent_profiles: dict[str, AgentProfile] | None = None,
    max_tasks: int = 4,
) -> None:
    if not 1 <= len(task_specs) <= max_tasks:
        raise PlanValidationError("Manager planner generated too many tasks.")

    for spec in task_specs:
        if spec.role not in GRAPH_AGENT_ROLES:
            raise PlanValidationError(f"Unsupported planner role: {spec.role}.")
        expected = set(spec.expected_artifact_types)
        if not expected.issubset(GRAPH_EXPECTED_ARTIFACTS):
            raise PlanValidationError("Manager planner generated unsupported artifacts.")
        files = spec.plan.get("files", [])
        if not isinstance(files, list):
            continue
        if allowed_targets is not None:
            _validate_registered_target_files(spec, files, allowed_targets)
            _validate_registered_target_policy(spec, allowed_targets)
        elif not set(files).issubset(GRAPH_ALLOWED_FILES):
            raise PlanValidationError("Manager planner generated unsupported target files.")
        if agent_profiles is not None:
            _validate_agent_profile_policy(spec, agent_profiles)

    _validate_dependency_keys(task_specs)


def _validate_registered_target_files(
    spec: TaskGraphTaskSpec,
    files: list[object],
    allowed_targets: dict[str, TargetProject],
) -> None:
    target_id = spec.plan.get("targetId")
    if not isinstance(target_id, str) or target_id not in allowed_targets:
        raise PlanValidationError("Manager planner generated an unknown target.")

    target = allowed_targets[target_id]
    for file_path in files:
        if not isinstance(file_path, str) or not file_path:
            raise PlanValidationError("Manager planner generated unsupported target files.")
        if not target.permits_path(file_path):
            raise PlanValidationError("Manager planner generated unsupported target files.")


def _validate_registered_target_policy(
    spec: TaskGraphTaskSpec,
    allowed_targets: dict[str, TargetProject],
) -> None:
    target_id = spec.plan.get("targetId")
    if not isinstance(target_id, str) or target_id not in allowed_targets:
        raise PlanValidationError("Manager planner generated an unknown target.")
    target = allowed_targets[target_id]
    if target.requires_platform_mode and (
        spec.plan.get("platformMode") is not True
        or spec.plan.get("requiresApproval") is not True
    ):
        raise PlanValidationError(
            "Manager planner generated platform work without platform mode approval."
        )
    _validate_command_policy(spec, target)


def _validate_agent_profile_policy(
    spec: TaskGraphTaskSpec,
    agent_profiles: dict[str, AgentProfile],
) -> None:
    profile = agent_profiles.get(spec.role)
    if profile is None:
        raise PlanValidationError(f"Planner selected unavailable agent profile: {spec.role}.")
    target_id = spec.plan.get("targetId")
    if isinstance(target_id, str) and target_id and not _profile_supports_target(profile, target_id):
        raise PlanValidationError(
            f"Planner selected role {spec.role} for unsupported target {target_id}."
        )
    mode = _mode_for_spec(spec)
    if mode and mode not in profile.supported_modes:
        raise PlanValidationError(
            f"Planner selected role {spec.role} for unsupported mode {mode}."
        )
    expected = set(spec.expected_artifact_types)
    if "diff" in expected and not profile.safe_for_write:
        raise PlanValidationError(f"Planner selected role {spec.role} that is not safe for write.")
    if spec.intent_type == "review" and not profile.safe_for_review:
        raise PlanValidationError(f"Planner selected role {spec.role} that is not safe for review.")


def _validate_command_policy(spec: TaskGraphTaskSpec, target: TargetProject) -> None:
    allowed_commands = set(allowed_validation_commands(target).values())
    validation_entries = _string_list(spec.plan.get("validationExpectations"))
    validation_entries.extend(_string_list(spec.plan.get("validationCommands")))
    for entry in validation_entries:
        if not _looks_like_command(entry):
            continue
        if entry not in allowed_commands and not _starts_with_allowed_command_note(
            entry,
            allowed_commands,
        ):
            raise PlanValidationError(
                f"Manager planner generated unsupported validation command for {target.target_id}: {entry}"
            )


def _validate_dependency_keys(task_specs: list[TaskGraphTaskSpec]) -> None:
    keys = {
        f"{index + 1}-{spec.role}-{spec.intent_type}"
        for index, spec in enumerate(task_specs)
    }
    for spec in task_specs:
        for dependency in _string_list(spec.plan.get("dependsOn")):
            if dependency not in keys:
                raise PlanValidationError(
                    f"Manager planner generated unknown dependency: {dependency}"
                )


def _profile_supports_target(profile: AgentProfile, target_id: str) -> bool:
    return supports_target_id(
        profile.supported_targets,
        target_id,
        role=profile.role,
    )


def _mode_for_spec(spec: TaskGraphTaskSpec) -> str:
    if spec.role in {"qa", "review"} or spec.intent_type == "review":
        return "review"
    if spec.role == "frontend":
        return "frontend"
    if spec.role == "backend":
        return "backend"
    return "read_only"


def _looks_like_command(value: str) -> bool:
    return value.startswith(("pnpm ", "npm ", "pytest", "python -m pytest"))


def _starts_with_allowed_command_note(value: str, allowed_commands: set[str]) -> bool:
    normalized = value.lower()
    safe_suffixes = (" succeeds", " passes", " success", " without errors")
    return any(
        normalized.startswith(command.lower() + suffix)
        for command in allowed_commands
        for suffix in safe_suffixes
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]
