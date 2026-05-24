import pytest

from app.target_registry import (
    AGENTHUB_PLATFORM_TARGET_ID,
    DEMO_BACKEND_BASE_URL,
    DEMO_BACKEND_TARGET_ID,
    DEMO_FRONTEND_TARGET_ID,
    TargetRegistryError,
    get_related_backend_target,
    get_related_targets,
    get_target,
    list_targets,
    maybe_get_target,
)


def test_registry_exposes_initial_target_projects() -> None:
    targets = {target.target_id: target for target in list_targets()}

    assert set(targets) == {
        DEMO_FRONTEND_TARGET_ID,
        DEMO_BACKEND_TARGET_ID,
        AGENTHUB_PLATFORM_TARGET_ID,
    }

    frontend = targets[DEMO_FRONTEND_TARGET_ID]
    assert frontend.name == "Demo Frontend"
    assert frontend.type == "frontend"
    assert frontend.root == "apps/demo"
    assert frontend.allowed_paths == ("apps/demo/src",)
    assert frontend.dev_command == "pnpm demo:dev"
    assert frontend.preview_command == "pnpm dev --host 127.0.0.1 --port <port>"
    assert frontend.allowed_agents == ("frontend", "qa", "review")

    backend = targets[DEMO_BACKEND_TARGET_ID]
    assert backend.name == "Demo Backend"
    assert backend.type == "backend"
    assert backend.root == "apps/demo-api"
    assert backend.allowed_paths == ("apps/demo-api",)
    assert backend.dev_command == "pnpm demo:api:dev"
    assert backend.test_command == "pnpm demo:api:test"
    assert backend.base_url == DEMO_BACKEND_BASE_URL
    assert backend.allowed_agents == ("backend", "qa", "review")

    platform = targets[AGENTHUB_PLATFORM_TARGET_ID]
    assert platform.name == "AgentHub Platform"
    assert platform.type == "platform"
    assert platform.root == "."
    assert platform.test_command == "pnpm check && pnpm test"
    assert platform.requires_platform_mode is True
    assert platform.requires_approval is True


def test_demo_backend_base_url_is_registry_metadata() -> None:
    backend = get_target(DEMO_BACKEND_TARGET_ID)

    assert backend.base_url == "http://127.0.0.1:5174"
    assert backend.base_url == DEMO_BACKEND_BASE_URL


def test_demo_frontend_resolves_related_demo_backend() -> None:
    related = get_related_targets(DEMO_FRONTEND_TARGET_ID)
    backend = get_related_backend_target(DEMO_FRONTEND_TARGET_ID)

    assert [target.target_id for target in related] == [DEMO_BACKEND_TARGET_ID]
    assert backend.target_id == DEMO_BACKEND_TARGET_ID
    assert backend.base_url == DEMO_BACKEND_BASE_URL


def test_demo_targets_deny_platform_and_cross_target_paths() -> None:
    frontend = get_target(DEMO_FRONTEND_TARGET_ID)
    backend = get_target(DEMO_BACKEND_TARGET_ID)

    assert frontend.permits_path("apps/demo/src/App.tsx") is True
    assert frontend.denies_path("apps/api/app/main.py") is True
    assert frontend.denies_path("apps/demo-api/app/main.py") is True
    assert frontend.permits_path("apps/api/app/main.py") is False
    assert frontend.permits_path("apps/demo-api/app/main.py") is False

    assert backend.permits_path("apps/demo-api/app/main.py") is True
    assert backend.denies_path("apps/api/app/main.py") is True
    assert backend.denies_path("apps/demo/src/App.tsx") is True
    assert backend.permits_path("apps/api/app/main.py") is False
    assert backend.permits_path("apps/demo/src/App.tsx") is False


def test_protected_paths_are_denied_for_all_targets() -> None:
    protected_paths = [
        ".env",
        ".env.local",
        "apps/demo/node_modules/react/index.js",
        "apps/demo/.git/config",
        "secrets/local.key",
    ]

    for target in list_targets():
        for path in protected_paths:
            assert target.denies_path(path) is True
            assert target.permits_path(path) is False


def test_platform_target_requires_explicit_mode_and_approval() -> None:
    platform = get_target(AGENTHUB_PLATFORM_TARGET_ID)

    assert platform.requires_platform_mode is True
    assert platform.requires_approval is True
    assert platform.allows_agent("orchestrator") is True
    assert platform.allows_agent("backend") is True
    assert platform.permits_path("apps/api/app/main.py") is True
    assert platform.permits_path("apps/web/src/app/page.tsx") is True
    assert platform.permits_path("scripts/test-api.sh") is True
    assert platform.permits_path("docs/project-state.md") is True
    assert platform.permits_path("openspec/changes/example/tasks.md") is True
    assert platform.permits_path("package.json") is True
    assert platform.denies_path(".env.local") is True


def test_unknown_target_helpers_fail_honestly() -> None:
    assert maybe_get_target("missing-target") is None

    with pytest.raises(TargetRegistryError, match="Unknown target project"):
        get_target("missing-target")

    with pytest.raises(TargetRegistryError, match="No related backend target"):
        get_related_backend_target(DEMO_BACKEND_TARGET_ID)
