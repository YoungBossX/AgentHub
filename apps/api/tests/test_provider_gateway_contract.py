from app.provider_configs import list_provider_configs
from app.provider_gateway import (
    CODING_ADAPTER_TYPES,
    PROVIDER_GATEWAY_EVENT_TYPES,
    ProviderCandidateDecision,
    ProviderErrorClassification,
    ProviderFallbackEvidence,
    ProviderGatewayResult,
    ProviderGatewayStatus,
    ProviderHealthResult,
    ProviderResolutionPlan,
    coding_provider_ids_from_configs,
    is_coding_adapter_type,
    redact_provider_evidence,
)


def test_gateway_result_evidence_preserves_failure_and_fallback_chain() -> None:
    resolution = ProviderResolutionPlan(
        selected_provider_id="local-codex-cli",
        selected_adapter_type="codex",
        selection_reason="runtime config selected Codex for frontend write mode",
        selected_is_real_provider=True,
        candidates=(
            ProviderCandidateDecision(
                provider_id="local-codex-cli",
                adapter_type="codex",
                accepted=True,
                reason="compatible",
            ),
        ),
        fallback_candidates=(
            ProviderCandidateDecision(
                provider_id="local-scripted-mock",
                adapter_type="scripted_mock",
                accepted=True,
                reason="demo fallback policy allows scripted mock",
            ),
        ),
    )
    result = ProviderGatewayResult(
        task_run_id="run-1",
        status=ProviderGatewayStatus.FALLBACK_SUCCEEDED,
        resolution=resolution,
        final_provider_id="local-scripted-mock",
        final_adapter_type="scripted_mock",
        health=ProviderHealthResult(
            provider_id="local-codex-cli",
            adapter_type="codex",
            status="unavailable",
            available=False,
            reason="Codex CLI auth failed",
            safe_details={"stderr": "token=secret-value"},
        ),
        error=ProviderErrorClassification(
            provider_id="local-codex-cli",
            category="auth",
            retryable=False,
            fallback_eligible=True,
            circuit_breaker_eligible=True,
            user_message="Codex authentication is not available.",
            safe_evidence={"raw": "api_key=sk-test"},
        ),
        fallback_chain=(
            ProviderFallbackEvidence(
                original_provider_id="local-codex-cli",
                fallback_provider_id="local-scripted-mock",
                trigger_category="auth",
                reason="scripted mock selected after auth failure",
                mock=True,
                completed=True,
            ),
        ),
    )

    evidence = result.to_evidence()

    assert evidence["status"] == "fallback_succeeded"
    assert evidence["selectedProviderId"] == "local-codex-cli"
    assert evidence["finalProviderId"] == "local-scripted-mock"
    assert evidence["finalAdapterType"] == "scripted_mock"
    assert evidence["error"]["category"] == "auth"
    assert evidence["error"]["safeEvidence"]["raw"] == "api_key=[redacted]"
    assert evidence["health"]["safeDetails"]["stderr"] == "token=[redacted]"
    assert evidence["fallbackChain"][0]["fallback"] is True
    assert evidence["fallbackChain"][0]["mock"] is True
    assert "provider.resolved" in evidence["eventTypes"]
    assert PROVIDER_GATEWAY_EVENT_TYPES == result.event_types


def test_provider_gateway_redacts_secrets_and_protected_host_paths() -> None:
    evidence = redact_provider_evidence(
        {
            "apiKey": "sk-should-not-leak",
            "summary": (
                "token=abc123 failed under "
                "/Users/demo/project/.env.local and /tmp/safe/file.txt"
            ),
            "nested": {
                "stderr": "credential:xyz in /Users/demo/project/node_modules/pkg",
            },
        }
    )

    assert evidence["apiKey"] == "[redacted]"
    assert "abc123" not in evidence["summary"]
    assert "/Users/demo/project/.env.local" not in evidence["summary"]
    assert "/tmp/safe/file.txt" not in evidence["summary"]
    assert "xyz" not in evidence["nested"]["stderr"]
    assert "/Users/demo/project/node_modules/pkg" not in evidence["nested"]["stderr"]


def test_coding_gateway_excludes_planner_providers() -> None:
    provider_ids = coding_provider_ids_from_configs(list_provider_configs())

    assert "local-claude-code-cli" in provider_ids
    assert "local-codex-cli" in provider_ids
    assert "local-scripted-mock" in provider_ids
    assert "claude-cli-planner" not in provider_ids
    assert is_coding_adapter_type("claude_cli") is False
    assert is_coding_adapter_type("openai_responses") is False
    assert CODING_ADAPTER_TYPES == frozenset(
        {"claude_code", "codex", "scripted_mock"}
    )
