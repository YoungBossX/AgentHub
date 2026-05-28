from fastapi.testclient import TestClient

from app.main import app


def test_provider_config_registry_returns_current_non_secret_providers() -> None:
    client = TestClient(app)

    response = client.get("/provider-configs")

    assert response.status_code == 200
    configs = response.json()
    assert [config["adapterType"] for config in configs] == [
        "claude_code",
        "codex",
        "scripted_mock",
    ]

    claude = configs[0]
    assert claude["providerId"] == "local-claude-code-cli"
    assert claude["displayName"] == "Claude Code CLI"
    assert claude["authStatus"] == "unchecked"
    assert claude["available"] is True
    assert "frontend" in claude["defaultForRoles"]
    assert "backend" in claude["supportedModes"]

    scripted = configs[-1]
    assert scripted["providerId"] == "local-scripted-mock"
    assert scripted["authStatus"] == "not_required"
    assert scripted["available"] is True
    assert "review" in scripted["defaultForRoles"]

    forbidden_keys = {"token", "secret", "apiKey", "api_key", "credential"}
    for config in configs:
        assert forbidden_keys.isdisjoint(config.keys())
