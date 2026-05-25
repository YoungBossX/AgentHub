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


def validate_task_graph(task_specs: list[TaskGraphTaskSpec]) -> None:
    if not 1 <= len(task_specs) <= 4:
        raise PlanValidationError("Manager planner generated too many tasks.")

    for spec in task_specs:
        if spec.role not in GRAPH_AGENT_ROLES:
            raise PlanValidationError(f"Unsupported planner role: {spec.role}.")
        expected = set(spec.expected_artifact_types)
        if not expected.issubset(GRAPH_EXPECTED_ARTIFACTS):
            raise PlanValidationError("Manager planner generated unsupported artifacts.")
        files = spec.plan.get("files", [])
        if isinstance(files, list) and not set(files).issubset(GRAPH_ALLOWED_FILES):
            raise PlanValidationError("Manager planner generated unsupported target files.")
