from typing import Optional

from app.project_command_policy import (
    allowed_validation_commands,
    evaluate_project_command,
)
from app.project_profiles import build_project_profile
from app.target_registry import TargetProject


def test_project_command_policy_allows_configured_profile_command() -> None:
    target = _target(
        target_id="external-vite",
        check_command="pnpm check",
        build_command="pnpm build",
    )

    decision = evaluate_project_command(
        target=target,
        command_type="build",
        command="pnpm build",
    )

    assert decision.allowed is True
    assert decision.target_id == "external-vite"
    assert decision.command_type == "build"
    assert "registered target command policy" in decision.reason


def test_project_command_policy_rejects_missing_command() -> None:
    target = _target(target_id="external-generic")

    decision = evaluate_project_command(
        target=target,
        command_type="test",
        command="pytest",
    )

    assert decision.allowed is False
    assert "does not configure a test command" in decision.reason


def test_project_command_policy_rejects_mismatched_command() -> None:
    target = _target(target_id="external-api", test_command="pytest")

    decision = evaluate_project_command(
        target=target,
        command_type="test",
        command="python -m pytest",
    )

    assert decision.allowed is False
    assert "expected 'pytest'" in decision.reason


def test_project_command_policy_rejects_unknown_command_type() -> None:
    target = _target(target_id="external-app", build_command="pnpm build")

    decision = evaluate_project_command(
        target=target,
        command_type="deploy",
        command="pnpm deploy",
    )

    assert decision.allowed is False
    assert "does not configure a deploy command" in decision.reason


def test_generic_repo_profile_only_allows_explicit_configured_commands() -> None:
    target = _target(
        target_id="external-generic",
        project_type="unknown",
        check_command="make check",
    )

    check = evaluate_project_command(
        target=target,
        command_type="check",
        command="make check",
    )
    build = evaluate_project_command(
        target=target,
        command_type="build",
        command="make build",
    )

    assert target.project_profile is not None
    assert target.project_profile.profile_id == "generic-repo"
    assert check.allowed is True
    assert build.allowed is False


def test_allowed_validation_commands_uses_configured_target_commands() -> None:
    target = _target(
        target_id="external-vite",
        check_command="pnpm check",
        test_command="pnpm test",
    )

    assert allowed_validation_commands(target) == {
        "check": "pnpm check",
        "test": "pnpm test",
    }


def test_planned_vite_target_commands_are_allowed_but_install_is_not() -> None:
    target = _target(
        target_id="external-frontend-health-management",
        check_command="pnpm check",
        test_command="pnpm test",
        build_command="pnpm build",
    )

    build = evaluate_project_command(
        target=target,
        command_type="build",
        command="pnpm build",
    )
    install = evaluate_project_command(
        target=target,
        command_type="build",
        command="pnpm install",
    )

    assert build.allowed is True
    assert install.allowed is False
    assert "expected 'pnpm build'" in install.reason


def test_planned_fastapi_target_commands_are_allowed_but_dependency_install_is_not() -> None:
    target = TargetProject(
        target_id="external-backend-health-management",
        name="Health Backend",
        type="backend",
        root="/tmp/health/backend",
        allowed_paths=("app", "tests", "requirements.txt"),
        denied_paths=(".git", ".env", "node_modules", "secrets"),
        allowed_agents=("backend", "qa", "review"),
        test_command="pytest",
        check_command="python -m compileall .",
        project_type="fastapi",
        detected_framework="fastapi",
        package_manager="pip",
    )

    test = evaluate_project_command(
        target=target,
        command_type="test",
        command="pytest",
    )
    install = evaluate_project_command(
        target=target,
        command_type="test",
        command="pip install -r requirements.txt",
    )

    assert test.allowed is True
    assert install.allowed is False
    assert "expected 'pytest'" in install.reason


def _target(
    *,
    target_id: str,
    project_type: str = "vite-react",
    check_command: Optional[str] = None,
    test_command: Optional[str] = None,
    build_command: Optional[str] = None,
) -> TargetProject:
    profile = build_project_profile(
        project_type=project_type,
        detected_framework=project_type,
        package_manager="pnpm",
        allowed_paths=("src",),
        dev_command="pnpm dev",
        test_command=test_command,
        check_command=check_command,
        build_command=build_command,
        preview_command="pnpm dev",
        analysis_status="manual",
        analysis_warnings=(),
        confidence="high",
    )
    return TargetProject(
        target_id=target_id,
        name=target_id,
        type="frontend",
        root="/tmp/example",
        allowed_paths=("src",),
        denied_paths=(".git", ".env", "node_modules", "secrets"),
        allowed_agents=("frontend", "qa", "review"),
        dev_command="pnpm dev",
        test_command=test_command,
        check_command=check_command,
        build_command=build_command,
        preview_command="pnpm dev",
        package_manager="pnpm",
        detected_framework=project_type,
        project_type=project_type,
        analysis_status="manual",
        project_profile=profile,
    )
