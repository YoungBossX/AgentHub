from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from app.models import utc_now

CodingAdapterType = Literal["claude_code", "codex", "scripted_mock"]
ProviderAvailability = Literal["available", "unavailable", "unknown"]
ProviderHealthStatus = Literal["healthy", "unavailable", "unknown"]
CapacityStatus = Literal["available", "exhausted"]
CircuitState = Literal["closed", "open", "half_open"]
ProviderErrorCategory = Literal[
    "auth",
    "quota",
    "rate_limit",
    "timeout",
    "format",
    "tool",
    "guardrail",
    "dirty_worktree",
    "unavailable",
    "unknown",
]

CODING_ADAPTER_TYPES: frozenset[str] = frozenset(
    {"claude_code", "codex", "scripted_mock"}
)
REAL_CODING_ADAPTER_TYPES: frozenset[str] = frozenset({"claude_code", "codex"})
MOCK_CODING_ADAPTER_TYPES: frozenset[str] = frozenset({"scripted_mock"})

PROVIDER_GATEWAY_EVENT_TYPES: tuple[str, ...] = (
    "provider.resolution_started",
    "provider.resolved",
    "provider.health_checked",
    "provider.capacity_acquired",
    "provider.capacity_released",
    "provider.circuit_opened",
    "provider.circuit_blocked",
    "provider.error_classified",
    "provider.fallback_selected",
    "provider.fallback_completed",
    "provider.gateway_completed",
)

PROTECTED_PATH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(^|[/\\])\.git($|[/\\])"),
    re.compile(r"(?i)(^|[/\\])\.env(?:\.[^/\\\s]+)?($|[/\\\s])"),
    re.compile(r"(?i)(^|[/\\])secrets($|[/\\])"),
    re.compile(r"(?i)(^|[/\\])node_modules($|[/\\])"),
    re.compile(r"(?i)(^|[/\\])\.venv($|[/\\])"),
)
SECRET_KEY_PATTERN = re.compile(
    r"(?i)(api[_-]?key|token|secret|credential|password|authorization)"
)
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|token|secret|credential|password|authorization)"
    r"\b\s*[:=]\s*[^,\s;]+"
)
HOST_PATH_PATTERN = re.compile(
    r"(?P<path>(?:/Users|/Volumes|/private|/var|/tmp|/home)/[^\s,;]+)"
)
REDACTED = "[redacted]"


class ProviderGatewayStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    FALLBACK_SUCCEEDED = "fallback_succeeded"


@dataclass(frozen=True)
class CodingRunContext:
    workspace_id: str
    session_id: str
    task_id: str
    task_run_id: str
    role: str
    target_id: Optional[str] = None
    mode: str = "write"
    required_capabilities: tuple[str, ...] = ("file_edit",)
    requested_provider_id: Optional[str] = None
    runtime_provider_id: Optional[str] = None
    runtime_adapter_type: Optional[str] = None
    fallback_policy: str = "environment_default"

    def to_evidence(self) -> dict[str, Any]:
        return redact_provider_evidence(
            {
                "workspaceId": self.workspace_id,
                "sessionId": self.session_id,
                "taskId": self.task_id,
                "taskRunId": self.task_run_id,
                "role": self.role,
                "targetId": self.target_id,
                "mode": self.mode,
                "requiredCapabilities": list(self.required_capabilities),
                "requestedProviderId": self.requested_provider_id,
                "runtimeProviderId": self.runtime_provider_id,
                "runtimeAdapterType": self.runtime_adapter_type,
                "fallbackPolicy": self.fallback_policy,
            }
        )


@dataclass(frozen=True)
class CodingProviderMetadata:
    provider_id: str
    display_name: str
    adapter_type: CodingAdapterType
    supported_roles: tuple[str, ...]
    supported_targets: tuple[str, ...]
    supported_modes: tuple[str, ...]
    capabilities: tuple[str, ...]
    auth_status: str = "unchecked"
    availability: ProviderAvailability = "unknown"
    is_real_provider: bool = True
    is_mock_provider: bool = False
    is_fallback_provider: bool = False
    safe_launch_summary: Optional[str] = None

    def to_evidence(self) -> dict[str, Any]:
        return redact_provider_evidence(
            {
                "providerId": self.provider_id,
                "displayName": self.display_name,
                "adapterType": self.adapter_type,
                "supportedRoles": list(self.supported_roles),
                "supportedTargets": list(self.supported_targets),
                "supportedModes": list(self.supported_modes),
                "capabilities": list(self.capabilities),
                "authStatus": self.auth_status,
                "availability": self.availability,
                "realProvider": self.is_real_provider,
                "mockProvider": self.is_mock_provider,
                "fallbackProvider": self.is_fallback_provider,
                "safeLaunchSummary": self.safe_launch_summary,
            }
        )


@dataclass(frozen=True)
class ProviderCandidateDecision:
    provider_id: str
    adapter_type: str
    accepted: bool
    reason: str

    def to_evidence(self) -> dict[str, Any]:
        return redact_provider_evidence(
            {
                "providerId": self.provider_id,
                "adapterType": self.adapter_type,
                "accepted": self.accepted,
                "reason": self.reason,
            }
        )


@dataclass(frozen=True)
class ProviderResolutionPlan:
    selected_provider_id: Optional[str]
    selected_adapter_type: Optional[str]
    selection_reason: str
    candidates: tuple[ProviderCandidateDecision, ...] = ()
    fallback_candidates: tuple[ProviderCandidateDecision, ...] = ()
    rejected_candidates: tuple[ProviderCandidateDecision, ...] = ()
    selected_is_real_provider: bool = False
    should_wait: bool = False
    should_fail: bool = False

    def to_evidence(self) -> dict[str, Any]:
        return redact_provider_evidence(
            {
                "selectedProviderId": self.selected_provider_id,
                "selectedAdapterType": self.selected_adapter_type,
                "selectionReason": self.selection_reason,
                "selectedIsRealProvider": self.selected_is_real_provider,
                "shouldWait": self.should_wait,
                "shouldFail": self.should_fail,
                "candidates": [item.to_evidence() for item in self.candidates],
                "fallbackCandidates": [
                    item.to_evidence() for item in self.fallback_candidates
                ],
                "rejectedCandidates": [
                    item.to_evidence() for item in self.rejected_candidates
                ],
            }
        )


@dataclass(frozen=True)
class ProviderHealthResult:
    provider_id: str
    adapter_type: str
    status: ProviderHealthStatus
    available: bool
    reason: str
    checked_at: datetime = field(default_factory=utc_now)
    safe_details: dict[str, Any] = field(default_factory=dict)

    def to_evidence(self) -> dict[str, Any]:
        return redact_provider_evidence(
            {
                "providerId": self.provider_id,
                "adapterType": self.adapter_type,
                "status": self.status,
                "available": self.available,
                "reason": self.reason,
                "checkedAt": self.checked_at.isoformat(),
                "safeDetails": self.safe_details,
            }
        )


@dataclass(frozen=True)
class ProviderCapacityDecision:
    provider_id: str
    status: CapacityStatus
    acquired: bool
    provider_running: int
    provider_limit: int
    global_running: int
    global_limit: int
    lease_id: Optional[str] = None
    reason: Optional[str] = None

    def to_evidence(self) -> dict[str, Any]:
        return redact_provider_evidence(
            {
                "providerId": self.provider_id,
                "status": self.status,
                "acquired": self.acquired,
                "providerRunning": self.provider_running,
                "providerLimit": self.provider_limit,
                "globalRunning": self.global_running,
                "globalLimit": self.global_limit,
                "leaseId": self.lease_id,
                "reason": self.reason,
            }
        )


@dataclass(frozen=True)
class ProviderRateLimitStatus:
    provider_id: str
    limited: bool = False
    window_summary: str = "unknown"
    next_eligible_at: Optional[datetime] = None
    reason: Optional[str] = None

    def to_evidence(self) -> dict[str, Any]:
        return redact_provider_evidence(
            {
                "providerId": self.provider_id,
                "limited": self.limited,
                "windowSummary": self.window_summary,
                "nextEligibleAt": self.next_eligible_at.isoformat()
                if self.next_eligible_at is not None
                else None,
                "reason": self.reason,
            }
        )


@dataclass(frozen=True)
class ProviderCircuitSnapshot:
    provider_id: str
    state: CircuitState = "closed"
    reason: Optional[str] = None
    failure_count: int = 0
    opened_at: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None

    def to_evidence(self) -> dict[str, Any]:
        return redact_provider_evidence(
            {
                "providerId": self.provider_id,
                "state": self.state,
                "reason": self.reason,
                "failureCount": self.failure_count,
                "openedAt": self.opened_at.isoformat()
                if self.opened_at is not None
                else None,
                "cooldownUntil": self.cooldown_until.isoformat()
                if self.cooldown_until is not None
                else None,
            }
        )


@dataclass(frozen=True)
class ProviderErrorClassification:
    provider_id: str
    category: ProviderErrorCategory
    retryable: bool
    fallback_eligible: bool
    circuit_breaker_eligible: bool
    user_message: str
    safe_evidence: dict[str, Any] = field(default_factory=dict)
    raw_error_redacted: bool = True

    def to_evidence(self) -> dict[str, Any]:
        return redact_provider_evidence(
            {
                "providerId": self.provider_id,
                "category": self.category,
                "retryable": self.retryable,
                "fallbackEligible": self.fallback_eligible,
                "circuitBreakerEligible": self.circuit_breaker_eligible,
                "userMessage": self.user_message,
                "safeEvidence": self.safe_evidence,
                "rawErrorRedacted": self.raw_error_redacted,
            }
        )


@dataclass(frozen=True)
class ProviderFallbackEvidence:
    original_provider_id: str
    fallback_provider_id: str
    trigger_category: Optional[ProviderErrorCategory]
    reason: str
    fallback: bool = True
    mock: bool = False
    completed: bool = False

    def to_evidence(self) -> dict[str, Any]:
        return redact_provider_evidence(
            {
                "originalProviderId": self.original_provider_id,
                "fallbackProviderId": self.fallback_provider_id,
                "triggerCategory": self.trigger_category,
                "reason": self.reason,
                "fallback": self.fallback,
                "mock": self.mock,
                "completed": self.completed,
            }
        )


@dataclass(frozen=True)
class ProviderGatewayResult:
    task_run_id: str
    status: ProviderGatewayStatus
    resolution: ProviderResolutionPlan
    final_provider_id: Optional[str] = None
    final_adapter_type: Optional[str] = None
    health: Optional[ProviderHealthResult] = None
    capacity: Optional[ProviderCapacityDecision] = None
    rate_limit: Optional[ProviderRateLimitStatus] = None
    circuit: Optional[ProviderCircuitSnapshot] = None
    error: Optional[ProviderErrorClassification] = None
    fallback_chain: tuple[ProviderFallbackEvidence, ...] = ()
    event_types: tuple[str, ...] = PROVIDER_GATEWAY_EVENT_TYPES

    def to_evidence(self) -> dict[str, Any]:
        return redact_provider_evidence(
            {
                "taskRunId": self.task_run_id,
                "status": self.status.value,
                "selectedProviderId": self.resolution.selected_provider_id,
                "finalProviderId": self.final_provider_id,
                "finalAdapterType": self.final_adapter_type,
                "resolution": self.resolution.to_evidence(),
                "health": self.health.to_evidence()
                if self.health is not None
                else None,
                "capacity": self.capacity.to_evidence()
                if self.capacity is not None
                else None,
                "rateLimit": self.rate_limit.to_evidence()
                if self.rate_limit is not None
                else None,
                "circuit": self.circuit.to_evidence()
                if self.circuit is not None
                else None,
                "error": self.error.to_evidence() if self.error is not None else None,
                "fallbackChain": [
                    item.to_evidence() for item in self.fallback_chain
                ],
                "eventTypes": list(self.event_types),
            }
        )


def is_coding_adapter_type(adapter_type: Optional[str]) -> bool:
    return adapter_type in CODING_ADAPTER_TYPES


def is_mock_adapter_type(adapter_type: Optional[str]) -> bool:
    return adapter_type in MOCK_CODING_ADAPTER_TYPES


def coding_provider_ids_from_configs(provider_configs: list[Any]) -> list[str]:
    provider_ids: list[str] = []
    for provider_config in provider_configs:
        adapter_type = getattr(provider_config, "adapter_type", None)
        provider_id = getattr(provider_config, "provider_id", None)
        if is_coding_adapter_type(adapter_type) and isinstance(provider_id, str):
            provider_ids.append(provider_id)
    return provider_ids


def redact_provider_evidence(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, nested in value.items():
            key_text = str(key)
            if SECRET_KEY_PATTERN.search(key_text):
                redacted[key] = REDACTED
            else:
                redacted[key] = redact_provider_evidence(nested)
        return redacted
    if isinstance(value, list):
        return [redact_provider_evidence(item) for item in value]
    if isinstance(value, tuple):
        return [redact_provider_evidence(item) for item in value]
    if isinstance(value, str):
        return _redact_string(value)
    return value


def _redact_string(value: str) -> str:
    redacted = SECRET_ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}={REDACTED}",
        value,
    )
    redacted = HOST_PATH_PATTERN.sub(_redact_path_match, redacted)
    for pattern in PROTECTED_PATH_PATTERNS:
        if pattern.search(redacted):
            return REDACTED
    return redacted


def _redact_path_match(match: re.Match[str]) -> str:
    path = match.group("path")
    if any(pattern.search(path) for pattern in PROTECTED_PATH_PATTERNS):
        return REDACTED
    return "[host-path]"
