from __future__ import annotations

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
        elif not set(files).issubset(GRAPH_ALLOWED_FILES):
            raise PlanValidationError("Manager planner generated unsupported target files.")


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
