from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from app.config import Settings, get_settings

PLANNER_PROVIDER_DISABLED = "disabled"
PLANNER_PROVIDER_FAKE_TEST = "fake_test"


class PlannerProviderError(ValueError):
    def __init__(
        self,
        *,
        code: str,
        summary: str,
        provider_id: str | None = None,
    ) -> None:
        super().__init__(summary)
        self.code = code
        self.summary = summary
        self.provider_id = provider_id

    def to_metadata(self) -> dict[str, Any]:
        return {
            "errorCode": self.code,
            "errorSummary": self.summary,
            "providerId": self.provider_id,
        }


@dataclass(frozen=True)
class PlannerProviderResult:
    provider_id: str
    provider_type: str
    planner_source: str
    status: str
    raw_output: str = ""
    duration_ms: int = 0
    error_code: str | None = None
    error_summary: str | None = None
    fallback_reason: str | None = None

    def to_metadata(self) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "providerId": self.provider_id,
            "providerType": self.provider_type,
            "plannerSource": self.planner_source,
            "status": self.status,
            "durationMs": self.duration_ms,
        }
        if self.error_code:
            metadata["errorCode"] = self.error_code
        if self.error_summary:
            metadata["errorSummary"] = self.error_summary
        if self.fallback_reason:
            metadata["fallbackReason"] = self.fallback_reason
        return metadata


class PlannerProvider(Protocol):
    provider_id: str
    provider_type: str
    planner_source: str

    def create_plan(self, planner_input: dict[str, Any]) -> PlannerProviderResult:
        ...


@dataclass(frozen=True)
class DisabledPlannerProvider:
    provider_id: str = PLANNER_PROVIDER_DISABLED
    provider_type: str = PLANNER_PROVIDER_DISABLED
    planner_source: str = "disabled"

    def create_plan(self, planner_input: dict[str, Any]) -> PlannerProviderResult:
        return PlannerProviderResult(
            provider_id=self.provider_id,
            provider_type=self.provider_type,
            planner_source=self.planner_source,
            status="disabled",
            error_code="PLANNER_DISABLED",
            error_summary="Real LLM planner provider is disabled.",
            fallback_reason="disabled",
        )


@dataclass(frozen=True)
class FakePlannerProvider:
    payload: dict[str, Any]
    provider_id: str = "fake-test-planner"
    provider_type: str = PLANNER_PROVIDER_FAKE_TEST
    planner_source: str = "fake_test"

    def create_plan(self, planner_input: dict[str, Any]) -> PlannerProviderResult:
        return PlannerProviderResult(
            provider_id=self.provider_id,
            provider_type=self.provider_type,
            planner_source=self.planner_source,
            status="succeeded",
            raw_output=json.dumps(self.payload),
        )


def resolve_planner_provider(
    settings: Settings | None = None,
    *,
    fake_payload: dict[str, Any] | None = None,
) -> PlannerProvider:
    resolved_settings = settings or get_settings()
    provider_id = resolved_settings.llm_planner_provider.strip().lower()
    if provider_id == PLANNER_PROVIDER_DISABLED:
        return DisabledPlannerProvider()
    if provider_id == PLANNER_PROVIDER_FAKE_TEST:
        if fake_payload is None:
            raise PlannerProviderError(
                code="FAKE_PLANNER_PAYLOAD_REQUIRED",
                summary="Fake planner provider requires an explicit test payload.",
                provider_id=provider_id,
            )
        return FakePlannerProvider(payload=fake_payload)
    raise PlannerProviderError(
        code="UNKNOWN_PLANNER_PROVIDER",
        summary=f"Unknown LLM planner provider: {provider_id}",
        provider_id=provider_id,
    )
