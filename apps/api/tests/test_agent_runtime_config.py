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
from app.provider_configs import ProviderConfig
from app.provider_health import check_runtime_role_provider


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
        "providerPresetId": None,
        "protocol": None,
        "model": None,
        "baseUrl": None,
        "timeoutSeconds": None,
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
                provider_preset_id="deepseek_api",
                protocol="openai_compatible_chat",
                model="deepseek-chat",
                base_url="https://api.deepseek.com",
                timeout_seconds=45,
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
    assert payload["roles"]["planner"]["providerPresetId"] == "deepseek_api"
    assert payload["roles"]["planner"]["protocol"] == "openai_compatible_chat"
    assert payload["roles"]["planner"]["model"] == "deepseek-chat"
    assert payload["roles"]["planner"]["baseUrl"] == "https://api.deepseek.com"
    assert payload["roles"]["planner"]["timeoutSeconds"] == 45
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
    assert payload["roles"]["planner"]["providerPresetId"] is None


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
                        "providerId": "local-codex-cli",
                        "adapterType": "codex",
                        "mode": "frontend",
                        "enabled": True,
                    }
                }
            },
        )
        persisted = client.get(f"/workspaces/{workspace_id}/runtime-config")

        assert response.status_code == 200
        assert response.json()["valid"] is True
        assert response.json()["warnings"] == []
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
                        "providerPresetId": "deepseek_api",
                        "protocol": "openai_compatible_chat",
                        "model": "deepseek-chat",
                        "baseUrl": "https://api.deepseek.com",
                        "timeoutSeconds": 45,
                        "apiKeyEnv": "DEEPSEEK_API_KEY",
                    },
                    "frontend": {
                        "agentProfileId": profiles["frontend"]["id"],
                        "providerId": "local-codex-cli",
                        "adapterType": "codex",
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
        assert payload["roles"]["planner"]["providerPresetId"] == "deepseek_api"
        assert payload["roles"]["planner"]["protocol"] == "openai_compatible_chat"
        assert payload["roles"]["planner"]["model"] == "deepseek-chat"
        assert payload["roles"]["planner"]["baseUrl"] == "https://api.deepseek.com"
        assert payload["roles"]["planner"]["timeoutSeconds"] == 45
        assert payload["roles"]["planner"]["apiKeyEnv"] == "DEEPSEEK_API_KEY"
        assert payload["roles"]["planner"]["availability"] == "missing_key"
        assert payload["roles"]["frontend"]["providerId"] == "local-codex-cli"
        assert payload["roles"]["backend"]["providerId"] == "local-codex-cli"


def test_runtime_config_put_allows_browser_cors_preflight() -> None:
    with _client() as client:
        workspace_id = _workspace_id(client)

        response = client.options(
            f"/workspaces/{workspace_id}/runtime-config",
            headers={
                "Origin": "http://127.0.0.1:3000",
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"
        assert "PUT" in response.headers["access-control-allow-methods"]


def test_runtime_config_api_validates_planner_provider_preset() -> None:
    with _client() as client:
        workspace_id = _workspace_id(client)

        response = client.post(
            f"/workspaces/{workspace_id}/runtime-config/validate",
            json={
                "roles": {
                    "planner": {
                        "providerPresetId": "deepseek_api",
                        "protocol": "openai_compatible_chat",
                        "model": "deepseek-chat",
                        "baseUrl": "https://api.deepseek.com",
                        "apiKeyEnv": "DEEPSEEK_API_KEY",
                        "mode": "read_only",
                        "enabled": True,
                    }
                }
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["valid"] is True
        assert payload["errors"] == []
        assert any("missing_key" in warning for warning in payload["warnings"])


def test_runtime_config_api_rejects_invalid_planner_provider_preset() -> None:
    with _client() as client:
        workspace_id = _workspace_id(client)

        response = client.post(
            f"/workspaces/{workspace_id}/runtime-config/validate",
            json={
                "roles": {
                    "planner": {
                        "providerPresetId": "mystery_api",
                        "protocol": "openai_compatible_chat",
                        "model": "model",
                        "baseUrl": "https://api.example.test/v1",
                        "apiKeyEnv": "CUSTOM_API_KEY",
                        "mode": "read_only",
                        "enabled": True,
                    }
                }
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["valid"] is False
        assert any("unknown planner provider preset" in error for error in payload["errors"])


def test_runtime_config_api_rejects_invalid_planner_base_url() -> None:
    with _client() as client:
        workspace_id = _workspace_id(client)

        response = client.post(
            f"/workspaces/{workspace_id}/runtime-config/validate",
            json={
                "roles": {
                    "planner": {
                        "providerPresetId": "custom_openai_compatible",
                        "protocol": "openai_compatible_chat",
                        "model": "custom-model",
                        "baseUrl": "https://user:pass@example.test/v1",
                        "apiKeyEnv": "CUSTOM_API_KEY",
                        "mode": "read_only",
                        "enabled": True,
                    }
                }
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["valid"] is False
        assert any("baseUrl is invalid" in error for error in payload["errors"])


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
        assert any("is incompatible: role `frontend` is not supported" in error for error in errors)
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


def test_runtime_config_api_rejects_draft_directory_entry_until_validated() -> None:
    with _client() as client:
        workspace_id = _workspace_id(client)
        create_response = client.post(
            f"/workspaces/{workspace_id}/agent-profile-drafts",
            json={
                "displayName": "Draft Reviewer",
                "role": "review",
                "adapterType": "scripted_mock",
                "providerId": "local-scripted-mock",
                "capabilityTags": ["code_review"],
                "supportedTargets": ["demo-frontend"],
                "supportedModes": ["review", "read_only"],
                "description": "Review-only draft.",
            },
        )
        assert create_response.status_code == 201
        draft_profile = create_response.json()

        response = client.put(
            f"/workspaces/{workspace_id}/runtime-config",
            json={
                "roles": {
                    "review": {
                        "agentProfileId": draft_profile["id"],
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
        assert any("draft profile is disabled until validated" in error for error in errors)


def test_runtime_config_validate_uses_directory_compatibility_without_persisting() -> None:
    with _client() as client:
        workspace_id = _workspace_id(client)
        create_response = client.post(
            f"/workspaces/{workspace_id}/agent-profile-drafts",
            json={
                "displayName": "Draft Reviewer",
                "role": "review",
                "adapterType": "scripted_mock",
                "providerId": "local-scripted-mock",
                "capabilityTags": ["code_review"],
                "supportedTargets": ["demo-frontend"],
                "supportedModes": ["review", "read_only"],
                "description": "Review-only draft.",
            },
        )
        draft_profile = create_response.json()

        response = client.post(
            f"/workspaces/{workspace_id}/runtime-config/validate",
            json={
                "roles": {
                    "review": {
                        "agentProfileId": draft_profile["id"],
                        "providerId": "local-scripted-mock",
                        "adapterType": "scripted_mock",
                        "mode": "review",
                        "enabled": True,
                    }
                }
            },
        )
        persisted = client.get(f"/workspaces/{workspace_id}/runtime-config")

        assert response.status_code == 200
        assert response.json()["valid"] is False
        assert any(
            "draft profile is disabled until validated" in error
            for error in response.json()["errors"]
        )
        assert persisted.json()["configSource"] == "default"
        assert persisted.json()["roles"]["review"]["enabled"] is False


def test_runtime_config_provider_check_reports_missing_planner_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with _client() as client:
        workspace_id = _workspace_id(client)

        response = client.post(
            f"/workspaces/{workspace_id}/runtime-config/check-provider",
            json={
                "role": "planner",
                "roleConfig": {
                    "providerPresetId": "deepseek_api",
                    "protocol": "openai_compatible_chat",
                    "model": "deepseek-chat",
                    "baseUrl": "https://api.deepseek.com",
                    "apiKeyEnv": "DEEPSEEK_API_KEY",
                    "mode": "read_only",
                    "enabled": True,
                },
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["authStatus"] == "missing_key"
        assert payload["availability"] == "missing_key"
        assert payload["available"] is False
        assert "DEEPSEEK_API_KEY" in payload["message"]


def test_runtime_config_provider_check_accepts_ui_role_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with _client() as client:
        workspace_id = _workspace_id(client)

        response = client.post(
            f"/workspaces/{workspace_id}/runtime-config/check-provider",
            json={
                "role": "planner",
                "roleConfig": {
                    "role": "planner",
                    "agentProfileId": None,
                    "providerId": None,
                    "adapterType": "openai_compatible_chat",
                    "mode": "read_only",
                    "enabled": True,
                    "fallbackPolicy": "environment_default",
                    "providerPresetId": "deepseek_api",
                    "protocol": "openai_compatible_chat",
                    "model": "deepseek-chat",
                    "baseUrl": "https://api.deepseek.com",
                    "timeoutSeconds": None,
                    "apiKeyEnv": "DEEPSEEK_API_KEY",
                    "availability": "missing_key",
                },
            },
        )

        assert response.status_code == 200
        assert response.json()["availability"] == "missing_key"


def test_runtime_config_provider_check_reports_mock_as_available_without_auth() -> None:
    with _client() as client:
        workspace_id = _workspace_id(client)
        profiles = _profiles_by_role(client, workspace_id)

        response = client.post(
            f"/workspaces/{workspace_id}/runtime-config/check-provider",
            json={
                "role": "review",
                "roleConfig": {
                    "agentProfileId": profiles["qa"]["id"],
                    "providerId": "local-scripted-mock",
                    "adapterType": "scripted_mock",
                    "mode": "review",
                    "enabled": True,
                },
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["providerId"] == "local-scripted-mock"
        assert payload["authStatus"] == "not_required"
        assert payload["availability"] == "not_required"
        assert payload["available"] is True


def test_runtime_provider_health_checks_local_cli_with_version_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr("app.provider_health.shutil.which", lambda command: f"/bin/{command}")

    def fake_run(command: list[str], **_: object) -> object:
        calls.append(command)
        return object()

    monkeypatch.setattr("app.provider_health.subprocess.run", fake_run)

    result = check_runtime_role_provider(
        RuntimeRoleConfig(
            role="frontend",
            agent_profile_id="agent-frontend",
            provider_id="local-codex-cli",
            adapter_type="codex",
            mode="frontend",
            enabled=True,
        ),
        providers=[
            ProviderConfig(
                provider_id="local-codex-cli",
                display_name="Codex CLI",
                adapter_type="codex",
                auth_status="unchecked",
                available=True,
                default_for_roles=["frontend"],
                supported_modes=["frontend"],
            )
        ],
    )

    assert result.available is True
    assert result.auth_status == "available"
    assert result.availability == "available"
    assert calls == [["/bin/codex", "--version"]]


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
