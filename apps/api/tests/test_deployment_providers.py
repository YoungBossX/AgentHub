from app.deployment_providers import (
    get_deployment_provider,
    list_deployment_providers,
)
from app.main import app
from fastapi.testclient import TestClient


def test_deployment_provider_registry_lists_safe_defaults(
    monkeypatch,
) -> None:
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    monkeypatch.delenv("NETLIFY_AUTH_TOKEN", raising=False)

    providers = list_deployment_providers()

    assert [provider.provider_id for provider in providers] == [
        "local_staging",
        "manual_external",
        "vercel",
        "netlify",
        "custom_static_host",
    ]
    assert providers[0].available is True
    assert providers[0].auth_status == "configured"
    assert providers[2].available is False
    assert providers[2].auth_status == "missing_key"


def test_external_provider_availability_uses_env_presence(monkeypatch) -> None:
    monkeypatch.setenv("VERCEL_TOKEN", "secret-token")

    provider = get_deployment_provider("vercel")

    assert provider is not None
    assert provider.available is True
    assert provider.auth_status == "configured"
    assert provider.secret_env_vars == ("VERCEL_TOKEN",)


def test_deployment_provider_registry_does_not_expose_secret_values(monkeypatch) -> None:
    monkeypatch.setenv("NETLIFY_AUTH_TOKEN", "netlify-secret-token")

    serialized = str([provider.to_payload() for provider in list_deployment_providers()])

    assert "NETLIFY_AUTH_TOKEN" in serialized
    assert "netlify-secret-token" not in serialized


def test_deployment_provider_api_returns_safe_provider_metadata(monkeypatch) -> None:
    monkeypatch.setenv("VERCEL_TOKEN", "secret-token")
    client = TestClient(app)

    response = client.get("/deployment-providers")

    assert response.status_code == 200
    payload = response.json()
    vercel = next(provider for provider in payload["providers"] if provider["providerId"] == "vercel")
    assert vercel["available"] is True
    assert vercel["authStatus"] == "configured"
    assert vercel["secretEnvVars"] == ["VERCEL_TOKEN"]
    assert "secret-token" not in str(payload)
