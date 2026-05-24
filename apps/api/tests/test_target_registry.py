import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine

from app.external_workspaces import ExternalWorkspaceRegistration, register_external_project_target
from app.models import Workspace
from app.target_registry import (
    AGENTHUB_PLATFORM_TARGET_ID,
    DEMO_BACKEND_BASE_URL,
    DEMO_BACKEND_TARGET_ID,
    DEMO_FRONTEND_TARGET_ID,
    TargetRegistryError,
    resolve_deploy_config,
    get_related_backend_target,
    get_related_targets,
    get_target,
    get_target_for_workspace,
    list_targets,
    list_targets_for_workspace,
    maybe_get_target,
    maybe_get_target_for_workspace,
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
    assert frontend.build_command == "pnpm --filter @agenthub/demo build"
    assert frontend.preview_command == "pnpm dev --host 127.0.0.1 --port <port>"
    assert frontend.staging_output_dir == "dist"
    assert frontend.staging_serve_command == (
        "python -m http.server <port> --bind 127.0.0.1 --directory dist"
    )
    assert frontend.deploy_provider_ids == ("mock", "local_staging")
    assert frontend.allowed_agents == ("frontend", "qa", "review")

    backend = targets[DEMO_BACKEND_TARGET_ID]
    assert backend.name == "Demo Backend"
    assert backend.type == "backend"
    assert backend.root == "apps/demo-api"
    assert backend.allowed_paths == ("apps/demo-api",)
    assert backend.dev_command == "pnpm demo:api:dev"
    assert backend.test_command == "pnpm demo:api:test"
    assert backend.base_url == DEMO_BACKEND_BASE_URL
    assert backend.deploy_provider_ids == ()
    assert backend.allowed_agents == ("backend", "qa", "review")

    platform = targets[AGENTHUB_PLATFORM_TARGET_ID]
    assert platform.name == "AgentHub Platform"
    assert platform.type == "platform"
    assert platform.root == "."
    assert platform.test_command == "pnpm check && pnpm test"
    assert platform.requires_platform_mode is True
    assert platform.requires_approval is True


def test_demo_frontend_resolves_deploy_config_from_registry() -> None:
    config = resolve_deploy_config(get_target(DEMO_FRONTEND_TARGET_ID))

    assert config.target_id == DEMO_FRONTEND_TARGET_ID
    assert config.provider_ids == ("mock", "local_staging")
    assert config.build_command == "pnpm --filter @agenthub/demo build"
    assert config.output_dir == "dist"
    assert config.serve_command == (
        "python -m http.server <port> --bind 127.0.0.1 --directory dist"
    )


def test_non_frontend_target_without_deploy_config_fails_honestly() -> None:
    with pytest.raises(TargetRegistryError, match="does not have staging deploy config"):
        resolve_deploy_config(get_target(DEMO_BACKEND_TARGET_ID))


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


def test_workspace_registry_merges_builtin_and_external_targets(tmp_path) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    project = tmp_path / "external-app"
    (project / "src").mkdir(parents=True)

    with DbSession(engine) as db:
        workspace = Workspace(
            name="AgentHub Demo",
            repo_url="local://apps/demo",
            root_path="apps/demo",
            default_branch="main",
        )
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
        register_external_project_target(
            db,
            workspace,
            ExternalWorkspaceRegistration(
                target_id="external-vite-app",
                name="External Vite App",
                root_path=str(project),
                project_type="vite-react",
                allowed_paths=["src"],
                dev_command="pnpm dev",
                test_command="pnpm test",
                check_command="pnpm check",
                build_command="pnpm build",
                preview_command="pnpm dev",
                staging_output_dir="dist",
                staging_serve_command="python -m http.server <port> --bind 127.0.0.1 --directory dist",
                deploy_provider_ids=["local_staging"],
                package_manager="pnpm",
                detected_framework="vite-react",
            ),
        )

        targets = {
            target.target_id: target
            for target in list_targets_for_workspace(db, workspace.id)
        }
        external = get_target_for_workspace(db, workspace.id, "external-vite-app")

        assert {
            DEMO_FRONTEND_TARGET_ID,
            DEMO_BACKEND_TARGET_ID,
            AGENTHUB_PLATFORM_TARGET_ID,
            "external-vite-app",
        } == set(targets)
        assert external.target_id == "external-vite-app"
        assert external.type == "frontend"
        assert external.root == str(project.resolve())
        assert external.allowed_paths == ("src",)
        assert external.denied_paths
        assert external.dev_command == "pnpm dev"
        assert external.test_command == "pnpm test"
        assert external.check_command == "pnpm check"
        assert external.build_command == "pnpm build"
        assert external.preview_command == "pnpm dev"
        assert external.staging_output_dir == "dist"
        assert external.staging_serve_command == (
            "python -m http.server <port> --bind 127.0.0.1 --directory dist"
        )
        assert external.deploy_provider_ids == ("local_staging",)
        assert external.package_manager == "pnpm"
        assert external.detected_framework == "vite-react"
        assert external.project_type == "vite-react"
        assert external.allows_agent("frontend") is True
        assert maybe_get_target_for_workspace(db, workspace.id, "external-vite-app") is not None

        deploy_config = resolve_deploy_config(external)
        assert deploy_config.output_dir == "dist"
        assert deploy_config.provider_ids == ("local_staging",)


def test_workspace_registry_maps_external_backend_targets(tmp_path) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    project = tmp_path / "external-api"
    (project / "app").mkdir(parents=True)

    with DbSession(engine) as db:
        workspace = Workspace(
            name="AgentHub Demo",
            repo_url="local://apps/demo",
            root_path="apps/demo",
            default_branch="main",
        )
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
        register_external_project_target(
            db,
            workspace,
            ExternalWorkspaceRegistration(
                target_id="external-fastapi",
                name="External FastAPI",
                root_path=str(project),
                project_type="fastapi",
                allowed_paths=["app"],
                test_command="pytest",
            ),
        )

        external = get_target_for_workspace(db, workspace.id, "external-fastapi")

        assert external.type == "backend"
        assert external.allowed_agents == ("backend", "qa", "review")
        assert external.allows_agent("backend") is True
