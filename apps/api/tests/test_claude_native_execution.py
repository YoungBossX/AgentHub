import io
import json
from pathlib import Path

import pytest

from app.claude_executable import resolve_claude_executable
from app.claude_code_adapter import ClaudeCodeAdapter, SubprocessClaudeCodeRunner
from app.adapters import AgentRunRequest
from app.process_environment import adapter_process_env, redact_process_evidence
from app.process_environment import ProcessTextRedactor
from app.provider_gateway import ProviderHealthProbe, ProviderRegistry


def write_settings(directory: Path, payload: object) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "settings.json").write_text(json.dumps(payload), encoding="utf-8")


def test_windows_native_resolution_preserves_explicit_override(tmp_path):
    native = tmp_path / "node_modules/@anthropic-ai/claude-code/bin/claude.exe"
    native.parent.mkdir(parents=True)
    native.write_bytes(b"fixture")
    lookup = lambda command: str(tmp_path / command)
    assert resolve_claude_executable("claude.cmd", windows=True, lookup=lookup) == str(native)
    assert resolve_claude_executable("custom.exe", windows=True, lookup=lookup) == str(tmp_path / "custom.exe")
    assert resolve_claude_executable("missing.cmd", windows=True, lookup=lambda _: None) == "missing.cmd"
    assert resolve_claude_executable("claude", windows=False, lookup=lookup) == "claude"


def test_settings_import_is_provider_only_and_does_not_execute_helpers(tmp_path):
    directory = tmp_path / ".claude"
    write_settings(directory, {
        "env": {"ANTHROPIC_AUTH_TOKEN": "settings-secret", "ANTHROPIC_BASE_URL": "https://gateway.test",
                "ANTHROPIC_MODEL": "native-model", "ANTHROPIC_DEFAULT_SONNET_MODEL": "alias-model",
                "OPENAI_API_KEY": "other-secret", "AGENTHUB_DATABASE_URL": "private",
                "NODE_OPTIONS": "--require hostile.js", "CLAUDE_CONFIG_DIR": "hostile",
                "ANTHROPIC_API_KEY": 42},
        "apiKeyHelper": "execute-hostile-command", "hooks": {"Stop": "hostile"},
        "permissions": {"defaultMode": "bypassPermissions"}, "enabledPlugins": {"hostile": True},
    })
    source = {"HOME": str(tmp_path), "PATH": "runtime", "OPENAI_API_KEY": "parent-other-secret"}
    env = adapter_process_env("claude_code", source)
    assert env == {"HOME": str(tmp_path), "PATH": "runtime", "ANTHROPIC_AUTH_TOKEN": "settings-secret",
                   "ANTHROPIC_BASE_URL": "https://gateway.test", "ANTHROPIC_MODEL": "native-model",
                   "ANTHROPIC_DEFAULT_SONNET_MODEL": "alias-model"}
    assert "ANTHROPIC_AUTH_TOKEN" not in adapter_process_env("codex", source)
    evidence = redact_process_evidence({"message": "settings-secret https://gateway.test parent-other-secret"}, source)
    assert evidence["message"] == "[redacted] [redacted] [redacted]"


def test_explicit_environment_overrides_settings_and_suppresses_other_credential(tmp_path):
    write_settings(tmp_path, {"env": {"ANTHROPIC_AUTH_TOKEN": "settings-token",
                                    "ANTHROPIC_API_KEY": "settings-key", "ANTHROPIC_MODEL": "settings-model"}})
    env = adapter_process_env("claude_code", {"CLAUDE_CONFIG_DIR": str(tmp_path),
                                             "anthropic_api_key": "explicit-key", "ANTHROPIC_MODEL": "explicit-model"})
    assert env["anthropic_api_key"] == "explicit-key"
    assert env["ANTHROPIC_MODEL"] == "explicit-model"
    assert "ANTHROPIC_AUTH_TOKEN" not in env
    assert "ANTHROPIC_API_KEY" not in env
    disabled = adapter_process_env("claude_code", {"CLAUDE_CONFIG_DIR": str(tmp_path), "ANTHROPIC_AUTH_TOKEN": ""})
    assert disabled["ANTHROPIC_AUTH_TOKEN"] == ""
    assert "ANTHROPIC_API_KEY" not in disabled


@pytest.mark.parametrize("content", [b"not json", b"[]", b'{"env":[]}', b"\xff", b"x" * (256 * 1024 + 1)],
                         ids=["malformed", "array", "invalid-env", "invalid-utf8", "oversized"])
def test_invalid_settings_are_ignored_without_weakening_execution(tmp_path, content):
    (tmp_path / "settings.json").write_bytes(content)
    source = {"CLAUDE_CONFIG_DIR": str(tmp_path), "ANTHROPIC_API_KEY": "explicit"}
    assert adapter_process_env("claude_code", source) == source


def test_relative_config_does_not_import_project_settings(tmp_path, monkeypatch):
    write_settings(tmp_path / "project", {"env": {"ANTHROPIC_AUTH_TOKEN": "project-secret"}})
    monkeypatch.chdir(tmp_path)
    assert adapter_process_env("claude_code", {"CLAUDE_CONFIG_DIR": "project"}) == {"CLAUDE_CONFIG_DIR": "project"}
    assert adapter_process_env("claude_code", {"CLAUDE_CONFIG_DIR": str(tmp_path / "missing")}) == {
        "CLAUDE_CONFIG_DIR": str(tmp_path / "missing")}


def test_changed_settings_refresh_import_and_redaction(tmp_path):
    source = {"CLAUDE_CONFIG_DIR": str(tmp_path)}
    write_settings(tmp_path, {"env": {"ANTHROPIC_AUTH_TOKEN": "first-secret"}})
    assert adapter_process_env("claude_code", source)["ANTHROPIC_AUTH_TOKEN"] == "first-secret"
    write_settings(tmp_path, {"env": {"ANTHROPIC_AUTH_TOKEN": "replacement-secret-longer"}})
    assert adapter_process_env("claude_code", source)["ANTHROPIC_AUTH_TOKEN"] == "replacement-secret-longer"
    assert redact_process_evidence("replacement-secret-longer", source) == "[redacted]"


def test_stream_redaction_handles_credentials_split_between_deltas():
    redactor = ProcessTextRedactor({"ANTHROPIC_AUTH_TOKEN": "split-secret"})
    parts = [redactor.append(part) for part in ["before spl", "it-", "secret after"]]
    assert "".join(parts) + redactor.finish() == "before [redacted] after"
    assert all("spl" not in part for part in parts)
    assert redactor.append("ordinary sp") == "ordinary "
    assert redactor.append("elling") == "spelling"
    assert redactor.finish() == ""
    assert redactor.append("end split-") == "end "
    assert redactor.finish() == "[redacted]"


def test_snapshots_do_not_duplicate_streamed_blocks_or_identical_later_messages():
    from app.claude_code_adapter import _ClaudeTextReconciler
    reconciler = _ClaudeTextReconciler()
    parts = []
    for message_id in ("one", "two"):
        reconciler.observe({"type": "stream_event", "event": {"type": "message_start", "message": {"id": message_id}}})
        for index, text in [(0, "中文"), (1, "中文")]:
            parts.append(reconciler.reconcile({"type": "stream_event", "event": {"index": index}}, text))
            snapshot = {"type": "assistant", "message": {"id": message_id, "content": [{"type": "text", "text": text}]}}
            assert reconciler.reconcile(snapshot, text) == ""
        assert reconciler.reconcile({"type": "assistant", "message": {"id": message_id,
            "content": [{"type": "text", "text": "中文"}, {"type": "text", "text": "中文"}]}}, "中文中文") == ""
    assert "".join(parts) == "中文中文中文中文"


def test_snapshot_preserves_unstreamed_suffix_and_nonstreamed_text():
    from app.claude_code_adapter import _ClaudeTextReconciler
    reconciler = _ClaudeTextReconciler()
    reconciler.observe({"type": "stream_event", "event": {"type": "message_start", "message": {"id": "id"}}})
    assert reconciler.reconcile({"type": "stream_event", "event": {"index": 0}}, "partial") == "partial"
    snapshot = {"type": "assistant", "message": {"id": "id", "content": [{"text": "partial suffix"}]}}
    assert reconciler.reconcile(snapshot, "partial suffix") == " suffix"
    assert reconciler.reconcile({"type": "assistant", "text": "standalone"}, "standalone") == "standalone"


@pytest.mark.anyio
async def test_native_stream_uses_utf8_and_redacts_launch_credentials_after_config_changes(tmp_path, monkeypatch):
    write_settings(tmp_path, {"env": {"ANTHROPIC_AUTH_TOKEN": "launch-secret"}})
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    captured = {}

    class Process:
        returncode = 0
        stdout = io.StringIO(json.dumps({"type": "assistant", "text": "中文 launch-secret"}) + "\n" + json.dumps({"type": "result"}) + "\n")
        stderr = io.StringIO("launch-secret")
        def wait(self):
            return 0

    def popen(command, **kwargs):
        captured.update(kwargs)
        write_settings(tmp_path, {"env": {"ANTHROPIC_AUTH_TOKEN": "changed-secret"}})
        return Process()

    monkeypatch.setattr("app.claude_code_adapter.subprocess.Popen", popen)
    adapter = ClaudeCodeAdapter(claude_binary="claude.exe")
    request = AgentRunRequest(taskRunId="run", sessionId="session", workspaceId="workspace", agentId="agent",
                              worktreePath=str(tmp_path), adapterType="claude_code", instruction="中文 & %PATH%")
    run = await adapter.createRun(request)
    events = [event async for event in adapter.streamEvents(run.adapter_run_id)]
    assert captured["encoding"] == "utf-8"
    assert not captured.get("shell", False)
    assert captured["env"]["ANTHROPIC_AUTH_TOKEN"] == "launch-secret"
    assert events[0].payload["text"] == "中文 [redacted]"
    assert "launch-secret" not in json.dumps([event.model_dump(mode="json") for event in events])


def test_claude_health_normalizes_windows_shim(tmp_path, monkeypatch):
    native = tmp_path / "node_modules/@anthropic-ai/claude-code/bin/claude.exe"
    native.parent.mkdir(parents=True)
    native.write_bytes(b"fixture")
    monkeypatch.setattr("app.provider_gateway.resolve_claude_executable", lambda command: resolve_claude_executable(
        command, windows=True, lookup=lambda _: str(tmp_path / "claude.cmd")))
    probes = []
    health = ProviderHealthProbe(command_lookup=lambda _: str(tmp_path / "claude.cmd"),
                                 version_runner=lambda exe: (probes.append(exe) is None, {}))
    provider = ProviderRegistry().get("local-claude-code-cli")
    assert provider is not None
    result = health.check_provider(provider)
    assert result.available is True
    assert probes == [str(native)]


def test_runtime_settings_health_respects_claude_override_without_shell(tmp_path, monkeypatch):
    import subprocess
    from app.agent_runtime_config import RuntimeRoleConfig
    from app.provider_configs import list_provider_configs
    from app.provider_health import check_runtime_role_provider
    native = tmp_path / "claude.exe"
    native.write_bytes(b"fixture")
    monkeypatch.setenv("CLAUDE_CODE_CLI_PATH", str(native))
    monkeypatch.setattr("app.provider_health.shutil.which", lambda command: command if command == str(native) else None)
    captured = {}
    def run(command, **kwargs):
        captured.update(kwargs)
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout="version", stderr="")
    monkeypatch.setattr("app.provider_health.subprocess.run", run)
    config = RuntimeRoleConfig(role="frontend", provider_id="local-claude-code-cli", adapter_type="claude_code", mode="frontend",
                               agent_profile_id=None, enabled=True)
    result = check_runtime_role_provider(config, providers=list_provider_configs())
    assert result.available is True
    assert captured["command"] == [str(native), "--version"]
    assert captured["encoding"] == "utf-8"
    assert not captured.get("shell", False)
