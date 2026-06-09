from app.project_profiles import (
    build_project_profile,
    preview_strategy_for_project_type,
    profile_id_for_project_type,
)


def test_project_profile_maps_known_project_types() -> None:
    assert profile_id_for_project_type("vite-react") == "vite-react"
    assert profile_id_for_project_type("nextjs") == "nextjs-react"
    assert profile_id_for_project_type("fastapi") == "fastapi-python"


def test_project_profile_maps_unknown_to_generic_repo() -> None:
    profile = build_project_profile(
        project_type="unknown",
        detected_framework="unknown",
        package_manager="unknown",
        allowed_paths=(),
        dev_command=None,
        test_command=None,
        check_command=None,
        build_command=None,
        preview_command=None,
        analysis_status="needs_confirmation",
        analysis_warnings=("Project type could not be inferred.",),
        confidence="low",
    )

    assert profile.profile_id == "generic-repo"
    assert profile.display_name == "Generic Repo"
    assert profile.status == "needs_confirmation"
    assert profile.commands.as_dict() == {}
    assert profile.preview_strategy == "none"
    assert ".git" in profile.denied_paths


def test_project_profile_summary_is_api_safe() -> None:
    profile = build_project_profile(
        project_type="vite-react",
        detected_framework="vite-react",
        package_manager="pnpm",
        allowed_paths=("src", "tests"),
        dev_command="pnpm dev",
        test_command="pnpm test",
        check_command="pnpm check",
        build_command="pnpm build",
        preview_command="pnpm dev",
        analysis_status="ready",
        analysis_warnings=(),
        confidence="high",
    )

    summary = profile.summary()

    assert summary["profileId"] == "vite-react"
    assert summary["displayName"] == "Vite / React"
    assert summary["commands"] == {
        "dev": "pnpm dev",
        "test": "pnpm test",
        "check": "pnpm check",
        "build": "pnpm build",
        "preview": "pnpm dev",
    }
    assert summary["allowedPaths"] == ["src", "tests"]
    assert ".env" in summary["deniedPaths"]
    assert "apiKey" not in summary


def test_project_profile_preview_strategy_is_conservative() -> None:
    assert preview_strategy_for_project_type("vite-react") == "vite-dev-server"
    assert preview_strategy_for_project_type("nextjs") == "next-dev-server"
    assert preview_strategy_for_project_type("fastapi") == "python-api"
    assert preview_strategy_for_project_type("node-api") == "none"
