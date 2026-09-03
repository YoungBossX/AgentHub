from app.process_environment import (
    adapter_process_env,
    project_process_env,
    redact_process_evidence,
)


def test_project_process_env_excludes_control_plane_secrets_and_keeps_runtime() -> None:
    env = project_process_env(
        {
            "Path": "C:/tools",
            "SystemRoot": "C:/Windows",
            "TEMP": "C:/Temp",
            "LANG": "en_US.UTF-8",
            "CI": "1",
            "VITE_PUBLIC_API": "http://127.0.0.1:5174",
            "NEXT_PUBLIC_MODE": "demo",
            "OPENAI_API_KEY": "openai-secret-value",
            "anthropic_api_key": "claude-secret-value",
            "AGENTHUB_DATABASE_URL": "sqlite:///private.sqlite3",
            "CUSTOM_SERVICE_TOKEN": "custom-secret-value",
        }
    )

    assert env == {
        "Path": "C:/tools",
        "SystemRoot": "C:/Windows",
        "TEMP": "C:/Temp",
        "LANG": "en_US.UTF-8",
        "CI": "1",
        "VITE_PUBLIC_API": "http://127.0.0.1:5174",
        "NEXT_PUBLIC_MODE": "demo",
    }


def test_adapter_process_env_keeps_only_selected_provider_credentials() -> None:
    base = {
        "PATH": "/usr/local/bin:/usr/bin",
        "HOME": "/Users/demo",
        "TMPDIR": "/tmp",
        "OPENAI_API_KEY": "openai-secret-value",
        "CODEX_HOME": "/Users/demo/.codex",
        "ANTHROPIC_API_KEY": "claude-secret-value",
        "ANTHROPIC_AUTH_TOKEN": "claude-gateway-token",
        "CLAUDE_CONFIG_DIR": "/Users/demo/.claude",
        "NODE_EXTRA_CA_CERTS": "/etc/company-ca.pem",
        "CUSTOM_OPENAI_COMPATIBLE_API_KEY": "planner-secret-value",
        "AGENTHUB_DATABASE_URL": "sqlite:///private.sqlite3",
    }

    codex_env = adapter_process_env("codex", base)
    claude_env = adapter_process_env("claude_code", base)

    assert codex_env["OPENAI_API_KEY"] == "openai-secret-value"
    assert codex_env["CODEX_HOME"] == "/Users/demo/.codex"
    assert "ANTHROPIC_API_KEY" not in codex_env
    assert "CLAUDE_CONFIG_DIR" not in codex_env
    assert "CUSTOM_OPENAI_COMPATIBLE_API_KEY" not in codex_env

    assert claude_env["ANTHROPIC_API_KEY"] == "claude-secret-value"
    assert claude_env["ANTHROPIC_AUTH_TOKEN"] == "claude-gateway-token"
    assert claude_env["CLAUDE_CONFIG_DIR"] == "/Users/demo/.claude"
    assert claude_env["NODE_EXTRA_CA_CERTS"] == "/etc/company-ca.pem"
    assert "OPENAI_API_KEY" not in claude_env
    assert "CODEX_HOME" not in claude_env
    assert "CUSTOM_OPENAI_COMPATIBLE_API_KEY" not in claude_env

    assert codex_env["PATH"] == claude_env["PATH"] == base["PATH"]
    assert codex_env["HOME"] == claude_env["HOME"] == base["HOME"]
    assert "AGENTHUB_DATABASE_URL" not in codex_env
    assert "AGENTHUB_DATABASE_URL" not in claude_env


def test_environment_key_matching_is_case_insensitive_without_renaming_keys() -> None:
    env = adapter_process_env(
        "codex",
        {
            "path": "C:/tools",
            "openai_api_key": "openai-secret-value",
            "Anthropic_Api_Key": "claude-secret-value",
        },
    )

    assert env == {
        "path": "C:/tools",
        "openai_api_key": "openai-secret-value",
    }


def test_redact_process_evidence_removes_exact_values_and_assignments() -> None:
    source_env = {
        "OPENAI_API_KEY": "openai-secret-value",
        "CUSTOM_SERVICE_TOKEN": "custom-secret-value",
        "PATH": "/usr/local/bin:/usr/bin",
    }

    redacted = redact_process_evidence(
        {
            "message": "failed token=inline-secret",
            "nested": [
                "openai-secret-value",
                "prefix custom-secret-value suffix",
                "ordinary diagnostic",
            ],
        },
        source_env,
    )

    assert redacted == {
        "message": "failed token=[redacted]",
        "nested": [
            "[redacted]",
            "prefix [redacted] suffix",
            "ordinary diagnostic",
        ],
    }


def test_redaction_covers_short_values_and_base_url_credentials() -> None:
    redacted = redact_process_evidence(
        "short xabcx and user api-user password p%40ss authorization: Bearer stray-token",
        {
            "CUSTOM_SERVICE_TOKEN": "abc",
            "OPENAI_BASE_URL": "https://api-user:p%40ss@example.test/v1",
        },
    )

    assert redacted == (
        "short x[redacted]x and user [redacted] password [redacted] "
        "authorization: [redacted]"
    )
