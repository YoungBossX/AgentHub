import pytest
from typing import Optional

from app.agent_profiles import AgentProfile
from app.plan_validator import PlanValidationError, validate_task_graph
from app.target_registry import TargetProject
from app.task_graph_builder import TaskGraphTaskSpec


def test_plan_validator_accepts_external_backend_prefix_for_backend_profile() -> None:
    validate_task_graph(
        [
            TaskGraphTaskSpec(
                title="Build backend API",
                intent_type="backend_change",
                role="backend",
                priority=0,
                plan={
                    "targetId": "external-backend-agenthub-rehearsals",
                    "files": ["app/main.py"],
                },
                expected_artifact_types=["diff"],
            )
        ],
        allowed_targets={
            "external-backend-agenthub-rehearsals": _target(
                "external-backend-agenthub-rehearsals",
                "backend",
                ("app", "tests"),
                ("backend", "qa", "review"),
            )
        },
        agent_profiles={
            "backend": _profile(
                role="backend",
                supported_targets=["demo-backend", "external-backend"],
                supported_modes=["backend"],
                safe_for_write=True,
                safe_for_review=False,
            )
        },
    )


def test_plan_validator_rejects_frontend_profile_for_external_backend_target() -> None:
    with pytest.raises(PlanValidationError, match="unsupported target"):
        validate_task_graph(
            [
                TaskGraphTaskSpec(
                    title="Wrong role",
                    intent_type="frontend_change",
                    role="frontend",
                    priority=0,
                    plan={
                        "targetId": "external-backend-agenthub-rehearsals",
                        "files": ["app/main.py"],
                    },
                    expected_artifact_types=["diff"],
                )
            ],
            allowed_targets={
                "external-backend-agenthub-rehearsals": _target(
                    "external-backend-agenthub-rehearsals",
                    "backend",
                    ("app", "tests"),
                    ("backend", "qa", "review"),
                )
            },
            agent_profiles={
                "frontend": _profile(
                    role="frontend",
                    supported_targets=["demo-frontend", "external-frontend"],
                    supported_modes=["frontend"],
                    safe_for_write=True,
                    safe_for_review=False,
                )
            },
        )


def test_plan_validator_accepts_provisioned_frontend_and_backend_targets() -> None:
    validate_task_graph(
        [
            TaskGraphTaskSpec(
                title="Build frontend",
                intent_type="frontend_change",
                role="frontend",
                priority=0,
                plan={
                    "targetId": "external-frontend-notes-app",
                    "files": ["src/App.tsx", "package.json", "vite.config.ts"],
                    "validationExpectations": ["pnpm build"],
                },
                expected_artifact_types=["diff"],
            ),
            TaskGraphTaskSpec(
                title="Build backend",
                intent_type="backend_change",
                role="backend",
                priority=1,
                plan={
                    "targetId": "external-backend-notes-app",
                    "files": ["app/main.py", "requirements.txt"],
                    "validationExpectations": ["python -m compileall ."],
                },
                expected_artifact_types=["diff"],
            ),
        ],
        allowed_targets={
            "external-frontend-notes-app": _target(
                "external-frontend-notes-app",
                "frontend",
                ("src", "package.json", "vite.config.ts"),
                ("frontend", "qa", "review"),
                check_command="pnpm check",
                build_command="pnpm build",
            ),
            "external-backend-notes-app": _target(
                "external-backend-notes-app",
                "backend",
                ("app", "tests", "requirements.txt"),
                ("backend", "qa", "review"),
                check_command="python -m compileall .",
                test_command="pytest",
            ),
        },
        agent_profiles={
            "frontend": _profile(
                role="frontend",
                supported_targets=["external-frontend"],
                supported_modes=["frontend"],
                safe_for_write=True,
                safe_for_review=False,
            ),
            "backend": _profile(
                role="backend",
                supported_targets=["external-backend"],
                supported_modes=["backend"],
                safe_for_write=True,
                safe_for_review=False,
            ),
        },
    )


def test_plan_validator_rejects_provisioned_target_protected_path_and_unknown_command() -> None:
    target = _target(
        "external-frontend-notes-app",
        "frontend",
        ("src", "package.json", "vite.config.ts"),
        ("frontend", "qa", "review"),
        build_command="pnpm build",
    )

    with pytest.raises(PlanValidationError, match="unsupported target files"):
        validate_task_graph(
            [
                TaskGraphTaskSpec(
                    title="Unsafe env edit",
                    intent_type="frontend_change",
                    role="frontend",
                    priority=0,
                    plan={
                        "targetId": "external-frontend-notes-app",
                        "files": [".env"],
                    },
                    expected_artifact_types=["diff"],
                )
            ],
            allowed_targets={"external-frontend-notes-app": target},
        )

    with pytest.raises(PlanValidationError, match="unsupported validation command"):
        validate_task_graph(
            [
                TaskGraphTaskSpec(
                    title="Install dependency",
                    intent_type="frontend_change",
                    role="frontend",
                    priority=0,
                    plan={
                        "targetId": "external-frontend-notes-app",
                        "files": ["package.json"],
                        "validationExpectations": ["pnpm install"],
                    },
                    expected_artifact_types=["diff"],
                )
            ],
            allowed_targets={"external-frontend-notes-app": target},
        )


def _target(
    target_id: str,
    target_type: str,
    allowed_paths: tuple[str, ...],
    allowed_agents: tuple[str, ...],
    *,
    check_command: Optional[str] = None,
    test_command: Optional[str] = None,
    build_command: Optional[str] = None,
) -> TargetProject:
    return TargetProject(
        target_id=target_id,
        name=target_id,
        type=target_type,  # type: ignore[arg-type]
        root="/tmp/example",
        allowed_paths=allowed_paths,
        denied_paths=(".git", ".env", "node_modules", "secrets"),
        allowed_agents=allowed_agents,  # type: ignore[arg-type]
        check_command=check_command,
        test_command=test_command,
        build_command=build_command,
    )


def _profile(
    *,
    role: str,
    supported_targets: list[str],
    supported_modes: list[str],
    safe_for_write: bool,
    safe_for_review: bool,
) -> AgentProfile:
    return AgentProfile(
        id=f"profile-{role}",
        display_name=role,
        avatar_initials=role[:2].upper(),
        role=role,
        adapter_type="codex",
        provider_id="local-codex-cli",
        capability_tags=["code_write"] if safe_for_write else ["code_review"],
        supported_roles=[role],
        supported_targets=supported_targets,
        supported_modes=supported_modes,
        safe_for_write=safe_for_write,
        safe_for_review=safe_for_review,
        description="test profile",
        status="available",
    )
