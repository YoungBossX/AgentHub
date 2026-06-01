from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine

from app.agent_runtime_config import (
    AgentRuntimeConfigError,
    RuntimeRoleConfig,
    default_runtime_config,
    get_effective_runtime_config,
    upsert_runtime_config,
)
from app.main import app, get_db
from app.models import Agent, Workspace


@pytest.fixture
def db() -> Iterator[DbSession]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as session:
        yield session


def test_default_runtime_config_preserves_existing_behavior(db: DbSession) -> None:
    workspace = _workspace(db)

    config = get_effective_runtime_config(db, workspace.id)
    payload = config.to_payload()

    assert config.config_source == "default"
    assert payload["workspaceId"] == workspace.id
    assert set(payload["roles"]) == {"planner", "frontend", "backend", "review"}
    assert payload["roles"]["planner"] == {
        "role": "planner",
        "agentProfileId": None,
        "providerId": None,
        "adapterType": None,
        "mode": "read_only",
        "enabled": False,
        "fallbackPolicy": "environment_default",
        "apiKeyEnv": None,
    }
    assert payload["roles"]["frontend"]["enabled"] is False
    assert payload["roles"]["backend"]["mode"] == "backend"


def test_runtime_config_round_trips_workspace_role_defaults(db: DbSession) -> None:
    workspace = _workspace(db)

    upsert_runtime_config(
        db,
        workspace.id,
        {
            "planner": RuntimeRoleConfig(
                role="planner",
                agent_profile_id="orchestrator-profile",
                provider_id="claude-cli-planner",
                adapter_type="claude_cli",
                mode="read_only",
                enabled=True,
                fallback_policy="deterministic",
                api_key_env="DEEPSEEK_API_KEY",
            ),
            "frontend": RuntimeRoleConfig(
                role="frontend",
                agent_profile_id="frontend-profile",
                provider_id="local-claude-code-cli",
                adapter_type="claude_code",
                mode="frontend",
                enabled=True,
                fallback_policy="explicit_only",
            ),
        },
    )

    config = get_effective_runtime_config(db, workspace.id)
    payload = config.to_payload()

    assert config.config_source == "workspace"
    assert payload["roles"]["planner"]["providerId"] == "claude-cli-planner"
    assert payload["roles"]["planner"]["fallbackPolicy"] == "deterministic"
    assert payload["roles"]["planner"]["apiKeyEnv"] == "DEEPSEEK_API_KEY"
    assert payload["roles"]["frontend"]["agentProfileId"] == "frontend-profile"
    assert payload["roles"]["backend"]["enabled"] is False
    assert payload["roles"]["review"]["mode"] == "read_only"


def test_runtime_config_rejects_unknown_role(db: DbSession) -> None:
    workspace = _workspace(db)

    with pytest.raises(AgentRuntimeConfigError, match="Unsupported runtime config role"):
        upsert_runtime_config(
            db,
            workspace.id,
            {
                "shell": RuntimeRoleConfig(
                    role="shell",
                    agent_profile_id="unsafe",
                    provider_id="local-shell",
                    adapter_type="shell",
                    mode="debug",
                    enabled=True,
                )
            },
        )


def test_runtime_config_rejects_raw_or_invalid_api_key_env(db: DbSession) -> None:
    workspace = _workspace(db)

    with pytest.raises(AgentRuntimeConfigError, match="apiKeyEnv"):
        upsert_runtime_config(
            db,
            workspace.id,
            {
                "planner": RuntimeRoleConfig(
                    role="planner",
                    agent_profile_id="orchestrator-profile",
                    provider_id="deepseek_api",
                    adapter_type="openai_compatible_chat",
                    mode="read_only",
                    enabled=True,
                    api_key_env="raw-secret-value",
                )
            },
        )


def test_default_runtime_config_payload_is_serializable() -> None:
    payload = default_runtime_config("workspace-1").to_payload()

    assert payload["configSource"] == "default"
    assert payload["roles"]["review"]["fallbackPolicy"] == "environment_default"
    assert payload["roles"]["planner"]["apiKeyEnv"] is None


def test_runtime_config_api_returns_default_and_safe_options() -> None:
    with _client() as client:
        workspace_id = _workspace_id(client)

        response = client.get(f"/workspaces/{workspace_id}/runtime-config")

        assert response.status_code == 200
        payload = response.json()
        assert payload["configSource"] == "default"
        assert set(payload["roles"]) == {"planner", "frontend", "backend", "review"}
        assert payload["validation"]["valid"] is True
        assert any(
            provider["providerId"] == "claude-cli-planner"
            and provider["adapterType"] == "claude_cli"
            for provider in payload["availableProviders"]
        )
        assert any(
            profile["role"] == "frontend" and profile["safeForWrite"] is True
            for profile in payload["availableProfiles"]
        )


def test_runtime_config_validate_does_not_persist_candidate() -> None:
    with _client() as client:
        workspace_id = _workspace_id(client)
        profiles = _profiles_by_role(client, workspace_id)

        response = client.post(
            f"/workspaces/{workspace_id}/runtime-config/validate",
            json={
                "roles": {
                    "frontend": {
                        "agentProfileId": profiles["frontend"]["id"],
                        "providerId": "local-claude-code-cli",
                        "adapterType": "claude_code",
                        "mode": "frontend",
                        "enabled": True,
                    }
                }
            },
        )
        persisted = client.get(f"/workspaces/{workspace_id}/runtime-config")

        assert response.status_code == 200
        assert response.json()["valid"] is True
        assert persisted.json()["configSource"] == "default"
        assert persisted.json()["roles"]["frontend"]["enabled"] is False


def test_runtime_config_api_persists_valid_workspace_config() -> None:
    with _client() as client:
        workspace_id = _workspace_id(client)
        profiles = _profiles_by_role(client, workspace_id)

        response = client.put(
            f"/workspaces/{workspace_id}/runtime-config",
            json={
                "roles": {
                    "planner": {
                        "agentProfileId": profiles["orchestrator"]["id"],
                        "providerId": "claude-cli-planner",
                        "adapterType": "claude_cli",
                        "mode": "read_only",
                        "enabled": True,
                        "fallbackPolicy": "deterministic",
                        "apiKeyEnv": "DEEPSEEK_API_KEY",
                    },
                    "frontend": {
                        "agentProfileId": profiles["frontend"]["id"],
                        "providerId": "local-claude-code-cli",
                        "adapterType": "claude_code",
                        "mode": "frontend",
                        "enabled": True,
                        "fallbackPolicy": "explicit_only",
                    },
                    "backend": {
                        "agentProfileId": profiles["backend"]["id"],
                        "providerId": "local-codex-cli",
                        "adapterType": "codex",
                        "mode": "backend",
                        "enabled": True,
                    },
                    "review": {
                        "agentProfileId": profiles["review"]["id"],
                        "providerId": "local-scripted-mock",
                        "adapterType": "scripted_mock",
                        "mode": "review",
                        "enabled": True,
                    },
                }
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["configSource"] == "workspace"
        assert payload["validation"]["valid"] is True
        assert payload["roles"]["planner"]["providerId"] == "claude-cli-planner"
        assert payload["roles"]["planner"]["apiKeyEnv"] == "DEEPSEEK_API_KEY"
        assert payload["roles"]["frontend"]["providerId"] == "local-claude-code-cli"
        assert payload["roles"]["backend"]["providerId"] == "local-codex-cli"


def test_runtime_config_api_ignores_raw_api_key_field() -> None:
    with _client() as client:
        workspace_id = _workspace_id(client)
        profiles = _profiles_by_role(client, workspace_id)

        response = client.post(
            f"/workspaces/{workspace_id}/runtime-config/validate",
            json={
                "roles": {
                    "planner": {
                        "agentProfileId": profiles["orchestrator"]["id"],
                        "providerId": "claude-cli-planner",
                        "adapterType": "claude_cli",
                        "mode": "read_only",
                        "enabled": True,
                        "apiKey": "raw-secret-value",
                    }
                }
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["valid"] is True
        assert "raw-secret-value" not in response.text


def test_runtime_config_responses_do_not_expose_raw_secret_fields() -> None:
    with _client() as client:
        workspace_id = _workspace_id(client)
        profiles = _profiles_by_role(client, workspace_id)

        response = client.put(
            f"/workspaces/{workspace_id}/runtime-config",
            json={
                "roles": {
                    "planner": {
                        "agentProfileId": profiles["orchestrator"]["id"],
                        "providerId": "claude-cli-planner",
                        "adapterType": "claude_cli",
                        "mode": "read_only",
                        "enabled": True,
                        "apiKeyEnv": "DEEPSEEK_API_KEY",
                        "apiKey": "raw-secret-value",
                        "authorization": "Bearer raw-secret-value",
                        "authorizationHeader": "Bearer raw-secret-value",
                    }
                }
            },
        )
        fetched = client.get(f"/workspaces/{workspace_id}/runtime-config")

        assert response.status_code == 200
        assert fetched.status_code == 200
        combined = response.text + fetched.text
        assert "raw-secret-value" not in combined
        assert "Bearer" not in combined
        assert response.json()["roles"]["planner"]["apiKeyEnv"] == "DEEPSEEK_API_KEY"
        assert fetched.json()["roles"]["planner"]["apiKeyEnv"] == "DEEPSEEK_API_KEY"


def test_runtime_config_api_rejects_invalid_profile_provider_role_combo() -> None:
    with _client() as client:
        workspace_id = _workspace_id(client)
        profiles = _profiles_by_role(client, workspace_id)

        response = client.put(
            f"/workspaces/{workspace_id}/runtime-config",
            json={
                "roles": {
                    "frontend": {
                        "agentProfileId": profiles["qa"]["id"],
                        "providerId": "local-scripted-mock",
                        "adapterType": "scripted_mock",
                        "mode": "review",
                        "enabled": True,
                    }
                }
            },
        )

        assert response.status_code == 400
        errors = response.json()["detail"]["errors"]
        assert any("not supported by agent profile" in error for error in errors)
        assert any("write-safe" in error for error in errors)


def test_runtime_config_api_rejects_backend_platform_maintenance_mode() -> None:
    with _client() as client:
        workspace_id = _workspace_id(client)
        profiles = _profiles_by_role(client, workspace_id)

        response = client.post(
            f"/workspaces/{workspace_id}/runtime-config/validate",
            json={
                "roles": {
                    "backend": {
                        "agentProfileId": profiles["backend"]["id"],
                        "providerId": "local-codex-cli",
                        "adapterType": "codex",
                        "mode": "platform_maintenance",
                        "enabled": True,
                    }
                }
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["valid"] is False
        assert any(
            "cannot use mode `platform_maintenance`" in error
            for error in payload["errors"]
        )


def _workspace(db: DbSession) -> Workspace:
    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


@contextmanager
def _client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        _workspace(db)
        db.add_all(
            [
                Agent(
                    name="Manager / Orchestrator",
                    role="orchestrator",
                    adapter_type="scripted_mock",
                    provider="local-scripted-mock",
                ),
                Agent(
                    name="Frontend Agent",
                    role="frontend",
                    adapter_type="codex",
                    provider="local-codex-cli",
                ),
                Agent(
                    name="Backend Agent",
                    role="backend",
                    adapter_type="codex",
                    provider="local-codex-cli",
                ),
                Agent(
                    name="QA Agent",
                    role="qa",
                    adapter_type="scripted_mock",
                    provider="local-scripted-mock",
                ),
            ]
        )
        db.commit()

    def override_db() -> Iterator[DbSession]:
        with DbSession(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _workspace_id(client: TestClient) -> str:
    response = client.get("/workspaces/demo")
    assert response.status_code == 200
    return response.json()["id"]


def _profiles_by_role(
    client: TestClient,
    workspace_id: str,
) -> dict[str, dict[str, object]]:
    response = client.get(f"/workspaces/{workspace_id}/agent-profiles")
    assert response.status_code == 200
    profiles: dict[str, dict[str, object]] = {}
    for profile in response.json():
        profiles.setdefault(profile["role"], profile)
    return profiles
