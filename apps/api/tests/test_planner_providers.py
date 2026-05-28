import json

import pytest

from app.config import Settings
from app.llm_planner import llm_planner_fallback_metadata
from app.planner_providers import (
    DisabledPlannerProvider,
    FakePlannerProvider,
    PlannerProviderError,
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


def test_resolve_planner_provider_rejects_unknown_provider() -> None:
    with pytest.raises(PlannerProviderError) as exc_info:
        resolve_planner_provider(Settings(llm_planner_provider="mystery_ai"))

    assert exc_info.value.code == "UNKNOWN_PLANNER_PROVIDER"
    assert "mystery_ai" in exc_info.value.summary


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
