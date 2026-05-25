from dataclasses import dataclass
from typing import Any, Optional

from app.target_registry import DEMO_BACKEND_TARGET_ID, DEMO_FRONTEND_TARGET_ID


@dataclass(frozen=True)
class TaskGraphTaskSpec:
    title: str
    intent_type: str
    role: str
    priority: int
    plan: dict[str, Any]
    expected_artifact_types: list[str]


def task_key(index: int, spec: TaskGraphTaskSpec) -> str:
    return f"{index + 1}-{spec.role}-{spec.intent_type}"


def task_graph_metadata(
    *,
    goal: str,
    intent: str,
    planner: str,
    task_specs: list[TaskGraphTaskSpec],
) -> dict[str, Any]:
    return {
        "goal": goal,
        "intent": intent,
        "planner": planner,
        "tasks": [
            {
                "key": task_key(index, spec),
                "title": spec.title,
                "assignedAgentRole": spec.role,
                "priority": spec.priority,
                "dependsOn": [task_key(index - 1, task_specs[index - 1])]
                if index > 0
                else [],
                "expectedArtifactTypes": spec.expected_artifact_types,
                "targetId": spec.plan.get("targetId"),
            }
            for index, spec in enumerate(task_specs)
        ],
    }


def dependency_edges(task_specs: list[TaskGraphTaskSpec]) -> list[dict[str, str]]:
    edges: list[dict[str, str]] = []
    for index, spec in enumerate(task_specs):
        if index == 0:
            continue
        edges.append(
            {
                "from": task_key(index - 1, task_specs[index - 1]),
                "to": task_key(index, spec),
            }
        )
    return edges


def planned_files(task_specs: list[TaskGraphTaskSpec]) -> list[str]:
    files: list[str] = []
    for spec in task_specs:
        raw_files = spec.plan.get("files", [])
        if not isinstance(raw_files, list):
            continue
        for file_path in raw_files:
            if isinstance(file_path, str) and file_path and file_path not in files:
                files.append(file_path)
    return files


def primary_agent_role(task_specs: list[TaskGraphTaskSpec]) -> Optional[str]:
    for spec in task_specs:
        if spec.role != "orchestrator":
            return spec.role
    return task_specs[0].role if task_specs else None


def primary_target_id(task_specs: list[TaskGraphTaskSpec]) -> Optional[str]:
    for spec in task_specs:
        for key in ("targetId", "frontendTargetId", "backendTargetId"):
            value = spec.plan.get(key)
            if isinstance(value, str) and value:
                return value

    files = planned_files(task_specs)
    if any(path.startswith("apps/demo-api/") for path in files):
        return DEMO_BACKEND_TARGET_ID
    if any(path.startswith("apps/demo/") for path in files):
        return DEMO_FRONTEND_TARGET_ID
    return None
