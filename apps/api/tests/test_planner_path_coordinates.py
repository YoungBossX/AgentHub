import pytest

from app.plan_validator import PlanValidationError, validate_task_graph
from app.target_registry import get_target
from app.task_graph_builder import TaskGraphTaskSpec


@pytest.mark.parametrize("path,valid", [("apps/demo-api/app/main.py", True), ("app/main.py", False),
                                       ("../apps/demo-api/app/main.py", False), ("apps/api/app/main.py", False)])
def test_backend_planning_keeps_registered_worktree_path_coordinate(path, valid):
    spec = TaskGraphTaskSpec(title="Fix backend health", intent_type="backend_change", role="backend", priority=0,
        plan={"targetId": "demo-backend", "files": [path], "dependsOn": []}, expected_artifact_types=["diff"])
    if valid:
        validate_task_graph([spec], allowed_targets={"demo-backend": get_target("demo-backend")})
    else:
        with pytest.raises(PlanValidationError):
            validate_task_graph([spec], allowed_targets={"demo-backend": get_target("demo-backend")})
