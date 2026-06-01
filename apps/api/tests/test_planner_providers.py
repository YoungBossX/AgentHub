from __future__ import annotations

import json
import subprocess

import pytest

from app.config import Settings
from app.llm_planner import llm_planner_fallback_metadata
from app.planner_providers import (
    ClaudeCliPlannerProvider,
    DisabledPlannerProvider,
    FakePlannerProvider,
    PlannerProviderError,
    get_planner_provider_protocol,
    list_planner_provider_protocols,
    resolve_planner_provider,
)


def test_disabled_planner_provider_records_disabled_source() -> None:
    provider = DisabledPlannerProvider()

    result = provider.create_plan({"originalUserRequest": "Build a game"})

    assert result.status == "disabled"
    assert result.provider_id == "disabled"
    assert result.provider_type == "disabled"
    assert result.planner_source == "disabled"
    assert result.error_code == "PLANNER_DISABLED"
    assert result.to_metadata() == {
        "providerId": "disabled",
        "providerType": "disabled",
        "plannerSource": "disabled",
        "status": "disabled",
        "durationMs": 0,
        "errorCode": "PLANNER_DISABLED",
        "errorSummary": "Real LLM planner provider is disabled.",
        "fallbackReason": "disabled",
    }


def test_planner_provider_protocol_registry_lists_supported_protocols() -> None:
    protocols = {item.protocol: item for item in list_planner_provider_protocols()}

    assert set(protocols) == {
        "openai_responses",
        "openai_compatible_chat",
        "anthropic_messages",
        "claude_cli",
        "fake_test",
        "disabled",
    }
    assert protocols["openai_responses"].real_provider is True
    assert protocols["openai_compatible_chat"].real_provider is True
    assert protocols["anthropic_messages"].real_provider is True
    assert protocols["fake_test"].real_provider is False
    assert protocols["disabled"].real_provider is False
    assert get_planner_provider_protocol("CLAUDE_CLI").protocol == "claude_cli"
    assert get_planner_provider_protocol("mystery") is None


def test_planner_provider_protocol_metadata_exposes_capability_flags() -> None:
    openai = get_planner_provider_protocol("openai_responses").to_metadata()
    compatible = get_planner_provider_protocol("openai_compatible_chat").to_metadata()
    anthropic = get_planner_provider_protocol("anthropic_messages").to_metadata()

    assert openai["supportsJsonSchema"] is True
    assert openai["supportsJsonObject"] is True
    assert openai["supportsSystemPrompt"] is True
    assert openai["supportsBaseUrl"] is False
    assert compatible["supportsJsonObject"] is True
    assert compatible["supportsBaseUrl"] is True
    assert anthropic["supportsToolCalls"] is True
    assert anthropic["supportsSystemPrompt"] is True
    assert isinstance(openai["defaultTimeoutSeconds"], int)
    assert "apiKey" not in openai


def test_fake_planner_provider_returns_test_only_result() -> None:
    provider = FakePlannerProvider(
        payload={
            "plannerMode": "llm_v1",
            "rationale": "Test-only plan.",
            "tasks": [],
        }
    )

    result = provider.create_plan({"originalUserRequest": "Build a game"})

    assert result.status == "succeeded"
    assert result.provider_type == "fake_test"
    assert result.planner_source == "fake_test"
    assert json.loads(result.raw_output)["rationale"] == "Test-only plan."
    assert result.to_metadata()["plannerSource"] == "fake_test"


def test_resolve_planner_provider_uses_explicit_selection() -> None:
    disabled = resolve_planner_provider(
        Settings(llm_planner_provider="disabled"),
    )
    fake = resolve_planner_provider(
        Settings(llm_planner_provider="fake_test"),
        fake_payload={"plannerMode": "llm_v1", "rationale": "Fake", "tasks": []},
    )

    assert isinstance(disabled, DisabledPlannerProvider)
    assert isinstance(fake, FakePlannerProvider)


def test_resolve_planner_provider_supports_claude_cli() -> None:
    provider = resolve_planner_provider(Settings(llm_planner_provider="claude_cli"))

    assert isinstance(provider, ClaudeCliPlannerProvider)
    assert provider.provider_id == "claude-cli-planner"
    assert provider.provider_type == "claude_cli"
    assert provider.planner_source == "real_llm"


def test_resolve_planner_provider_supports_runtime_config_provider_id() -> None:
    provider = resolve_planner_provider(
        Settings(llm_planner_provider="disabled"),
        provider_id="claude-cli-planner",
        adapter_type="claude_cli",
    )

    assert isinstance(provider, ClaudeCliPlannerProvider)
    assert provider.provider_id == "claude-cli-planner"


def test_resolve_planner_provider_rejects_unknown_provider() -> None:
    with pytest.raises(PlannerProviderError) as exc_info:
        resolve_planner_provider(Settings(llm_planner_provider="mystery_ai"))

    assert exc_info.value.code == "UNKNOWN_PLANNER_PROVIDER"
    assert "mystery_ai" in exc_info.value.summary


def test_claude_cli_planner_provider_returns_real_llm_result() -> None:
    runner = FakePlannerCommandRunner(
        subprocess.CompletedProcess(
            args=["claude"],
            returncode=0,
            stdout='{"planner":"llm_v1"}',
            stderr="",
        )
    )
    provider = ClaudeCliPlannerProvider(
        command_runner=runner,
        claude_binary="claude",
        timeout_sec=12,
    )

    result = provider.create_plan({"originalUserRequest": "Build Breakout"})

    assert result.status == "succeeded"
    assert result.raw_output == '{"planner":"llm_v1"}'
    assert result.planner_source == "real_llm"
    assert runner.command[:2] == ["claude", "--print"]
    assert "--allowedTools" in runner.command
    assert "Return ONLY one JSON object" in runner.command[-1]
    assert "ConversationOutcome contract" in runner.command[-1]
    assert "For normal chat, greetings, or capability questions, return assistant_reply" in runner.command[-1]
    assert "planDraft must match this PlannerResponse contract" in runner.command[-1]
    assert "Each task must include title, role, targetId" in runner.command[-1]
    assert "Create at most 4 tasks" in runner.command[-1]
    assert "1-frontend-frontend_change" in runner.command[-1]
    assert runner.timeout == 12


@pytest.mark.parametrize(
    ("stderr", "error_code"),
    [
        ("Please login before using Claude", "PLANNER_AUTH_REQUIRED"),
        ("quota exceeded for current usage", "PLANNER_QUOTA_LIMIT"),
        ("unexpected runtime failure", "PLANNER_RUNTIME_ERROR"),
    ],
)
def test_claude_cli_planner_provider_normalizes_nonzero_errors(
    stderr: str,
    error_code: str,
) -> None:
    provider = ClaudeCliPlannerProvider(
        command_runner=FakePlannerCommandRunner(
            subprocess.CompletedProcess(
                args=["claude"],
                returncode=1,
                stdout="",
                stderr=stderr,
            )
        )
    )

    result = provider.create_plan({"originalUserRequest": "Build Breakout"})

    assert result.status == "failed"
    assert result.error_code == error_code
    assert stderr in result.error_summary


def test_claude_cli_planner_provider_normalizes_timeout() -> None:
    provider = ClaudeCliPlannerProvider(
        command_runner=FakePlannerCommandRunner(
            subprocess.TimeoutExpired(cmd=["claude"], timeout=3)
        ),
        timeout_sec=3,
    )

    result = provider.create_plan({"originalUserRequest": "Build Breakout"})

    assert result.status == "failed"
    assert result.error_code == "PLANNER_TIMEOUT"
    assert "timed out" in result.error_summary


def test_claude_cli_planner_provider_normalizes_missing_binary() -> None:
    provider = ClaudeCliPlannerProvider(
        command_runner=FakePlannerCommandRunner(FileNotFoundError("claude")),
    )

    result = provider.create_plan({"originalUserRequest": "Build Breakout"})

    assert result.status == "failed"
    assert result.error_code == "PLANNER_PROVIDER_UNAVAILABLE"


def test_llm_planner_fallback_metadata_records_selected_provider() -> None:
    metadata = llm_planner_fallback_metadata(
        "disabled",
        provider=DisabledPlannerProvider(),
    )

    assert metadata == {
        "attemptedPlanner": "llm_v1",
        "reason": "disabled",
        "providerId": "disabled",
        "providerType": "disabled",
        "plannerSource": "disabled",
        "status": "disabled",
    }


class FakePlannerCommandRunner:
    def __init__(
        self,
        result: subprocess.CompletedProcess[str] | BaseException,
    ) -> None:
        self.result = result
        self.command: list[str] = []
        self.timeout: int | None = None

    def run(
        self,
        command: list[str],
        *,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        self.command = command
        self.timeout = timeout
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result
