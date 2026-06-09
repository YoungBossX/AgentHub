from __future__ import annotations

import re
import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Literal, Optional

from sqlmodel import Session as DbSession

from app.events import append_task_run_event
from app.models import utc_now
from app.models import TaskRun
from app.provider_configs import ProviderConfig, list_provider_configs

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
NON_CODING_ROLES: frozenset[str] = frozenset({"planner", "orchestrator", "fallback"})
DEFAULT_CODING_PROVIDER_BY_ROLE: dict[str, str] = {
    "frontend": "local-codex-cli",
    "backend": "local-codex-cli",
    "qa": "local-scripted-mock",
    "review": "local-scripted-mock",
}
SAFE_LAUNCH_SUMMARY_BY_ADAPTER: dict[str, str] = {
    "claude_code": "local Claude Code CLI launch path",
    "codex": "local Codex CLI launch path",
    "scripted_mock": "local scripted mock demo boundary",
}
CLI_ENV_BY_ADAPTER: dict[str, str] = {
    "claude_code": "CLAUDE_CODE_CLI_PATH",
    "codex": "CODEX_CLI_PATH",
}
DEFAULT_CLI_COMMAND_BY_ADAPTER: dict[str, str] = {
    "claude_code": "claude",
    "codex": "/Applications/Codex.app/Contents/Resources/codex",
}
CAPABILITIES_BY_ADAPTER: dict[str, tuple[str, ...]] = {
    "claude_code": ("file_edit", "shell_command", "diff_artifact", "preview_artifact"),
    "codex": ("file_edit", "shell_command", "diff_artifact", "preview_artifact"),
    "scripted_mock": ("file_edit", "diff_artifact", "preview_artifact", "review"),
}
FALLBACK_DISABLED_POLICIES: frozenset[str] = frozenset(
    {"none", "explicit_only", "disabled"}
)

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


class ProviderResolutionError(ValueError):
    pass


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
    worktree_path: Optional[str] = None
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
                "worktreePath": self.worktree_path,
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


class ProviderRegistry:
    def __init__(
        self,
        providers: Optional[list[CodingProviderMetadata]] = None,
    ) -> None:
        self._providers = tuple(providers) if providers is not None else tuple(
            _coding_provider_from_config(provider)
            for provider in list_provider_configs()
            if is_coding_adapter_type(provider.adapter_type)
        )

    def list_providers(self) -> list[CodingProviderMetadata]:
        return list(self._providers)

    def get(self, provider_id: str) -> Optional[CodingProviderMetadata]:
        return next(
            (
                provider
                for provider in self._providers
                if provider.provider_id == provider_id
            ),
            None,
        )

    def coding_provider_ids(self) -> list[str]:
        return [provider.provider_id for provider in self._providers]

    def default_provider_for_role(
        self,
        role: str,
    ) -> Optional[CodingProviderMetadata]:
        preferred_id = DEFAULT_CODING_PROVIDER_BY_ROLE.get(role)
        if preferred_id:
            preferred = self.get(preferred_id)
            if preferred is not None:
                return preferred
        return next(
            (
                provider
                for provider in self._providers
                if role in provider.supported_roles and provider.is_real_provider
            ),
            None,
        )

    def fallback_providers_for(
        self,
        context: CodingRunContext,
    ) -> list[CodingProviderMetadata]:
        return [
            provider
            for provider in self._providers
            if provider.is_fallback_provider
            and provider.availability == "available"
            and _provider_matches_context(provider, context)
        ]


class ProviderResolver:
    def __init__(self, registry: Optional[ProviderRegistry] = None) -> None:
        self.registry = registry or ProviderRegistry()

    def resolve(self, context: CodingRunContext) -> ProviderResolutionPlan:
        ordered = self._ordered_candidates(context)
        fallback_providers = self.registry.fallback_providers_for(context)
        candidates: list[ProviderCandidateDecision] = []
        rejected: list[ProviderCandidateDecision] = []
        fallback_decisions: list[ProviderCandidateDecision] = []
        selected: Optional[CodingProviderMetadata] = None
        selection_reason = "No compatible coding provider was available."

        for provider in ordered:
            decision = _candidate_decision(provider, context)
            candidates.append(decision)
            if not decision.accepted:
                rejected.append(decision)
                continue
            if provider.is_fallback_provider:
                fallback_decisions.append(decision)
                continue
            if selected is None:
                selected = provider
                selection_reason = decision.reason
                break

        for provider in fallback_providers:
            if selected is not None and provider.provider_id == selected.provider_id:
                continue
            decision = _candidate_decision(provider, context)
            if decision not in fallback_decisions:
                fallback_decisions.append(decision)
            if not decision.accepted:
                rejected.append(decision)

        if selected is None and _fallback_allowed(context.fallback_policy):
            fallback_selected = next(
                (
                    self.registry.get(decision.provider_id)
                    for decision in fallback_decisions
                    if decision.accepted
                ),
                None,
            )
            if fallback_selected is not None:
                selected = fallback_selected
                selection_reason = (
                    "Fallback coding provider selected because no real provider "
                    "was available."
                )

        should_fail = selected is None
        return ProviderResolutionPlan(
            selected_provider_id=selected.provider_id if selected is not None else None,
            selected_adapter_type=selected.adapter_type if selected is not None else None,
            selection_reason=selection_reason,
            candidates=tuple(candidates),
            fallback_candidates=tuple(fallback_decisions),
            rejected_candidates=tuple(_dedupe_decisions(rejected)),
            selected_is_real_provider=(
                selected.is_real_provider if selected is not None else False
            ),
            should_fail=should_fail,
        )

    def _ordered_candidates(
        self,
        context: CodingRunContext,
    ) -> list[CodingProviderMetadata]:
        providers: list[CodingProviderMetadata] = []

        for provider_id in [
            context.requested_provider_id,
            context.runtime_provider_id,
            DEFAULT_CODING_PROVIDER_BY_ROLE.get(context.role),
        ]:
            if not provider_id:
                continue
            provider = self.registry.get(provider_id)
            if provider is not None and provider not in providers:
                providers.append(provider)

        if context.runtime_adapter_type and is_coding_adapter_type(
            context.runtime_adapter_type
        ):
            for provider in self.registry.list_providers():
                if (
                    provider.adapter_type == context.runtime_adapter_type
                    and provider not in providers
                ):
                    providers.append(provider)

        for provider in self.registry.list_providers():
            if provider.is_real_provider and provider not in providers:
                providers.append(provider)
        return providers


class ProviderHealthProbe:
    def __init__(
        self,
        *,
        command_lookup: Optional[Callable[[str], Optional[str]]] = None,
        version_runner: Optional[Callable[[str], tuple[bool, dict[str, Any]]]] = None,
    ) -> None:
        self._command_lookup = command_lookup or _default_command_lookup
        self._version_runner = version_runner or _run_version_probe

    def check_provider(
        self,
        provider: CodingProviderMetadata,
        *,
        context: Optional[CodingRunContext] = None,
    ) -> ProviderHealthResult:
        if provider.adapter_type == "scripted_mock":
            return self._check_scripted_mock(provider, context=context)
        if provider.adapter_type in {"claude_code", "codex"}:
            return self._check_cli_provider(provider)
        return ProviderHealthResult(
            provider_id=provider.provider_id,
            adapter_type=provider.adapter_type,
            status="unknown",
            available=False,
            reason="Provider has no coding health probe.",
        )

    def _check_cli_provider(
        self,
        provider: CodingProviderMetadata,
    ) -> ProviderHealthResult:
        command = _configured_cli_command(provider.adapter_type)
        executable = self._command_lookup(command)
        safe_command = _safe_command_summary(command)
        if executable is None:
            return ProviderHealthResult(
                provider_id=provider.provider_id,
                adapter_type=provider.adapter_type,
                status="unavailable",
                available=False,
                reason="CLI executable was not found on the configured launch path.",
                safe_details={
                    "command": safe_command,
                    "probe": "which",
                    "fallbackDoesNotImplyHealthy": True,
                },
            )

        ok, details = self._version_runner(executable)
        safe_details = {
            "command": safe_command,
            "probe": "version",
            "executable": _safe_command_summary(executable),
            **details,
        }
        if not ok:
            return ProviderHealthResult(
                provider_id=provider.provider_id,
                adapter_type=provider.adapter_type,
                status="unavailable",
                available=False,
                reason="CLI executable was found but the startup probe failed.",
                safe_details=safe_details,
            )
        return ProviderHealthResult(
            provider_id=provider.provider_id,
            adapter_type=provider.adapter_type,
            status="healthy",
            available=True,
            reason="CLI executable and startup probe are available.",
            safe_details=safe_details,
        )

    def _check_scripted_mock(
        self,
        provider: CodingProviderMetadata,
        *,
        context: Optional[CodingRunContext],
    ) -> ProviderHealthResult:
        if context is None or not context.worktree_path:
            return ProviderHealthResult(
                provider_id=provider.provider_id,
                adapter_type=provider.adapter_type,
                status="unknown",
                available=False,
                reason="ScriptedMock health requires a session worktree path.",
                safe_details={
                    "demoBoundary": "apps/demo/src/App.tsx",
                    "mock": True,
                },
            )
        app_path = Path(context.worktree_path) / "apps/demo/src/App.tsx"
        exists = app_path.exists()
        return ProviderHealthResult(
            provider_id=provider.provider_id,
            adapter_type=provider.adapter_type,
            status="healthy" if exists else "unavailable",
            available=exists,
            reason=(
                "ScriptedMock demo app boundary is available."
                if exists
                else "ScriptedMock demo app boundary is missing."
            ),
            safe_details={
                "demoBoundary": "apps/demo/src/App.tsx",
                "mock": True,
                "path": str(app_path),
            },
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


def record_provider_resolution(
    db: DbSession,
    *,
    task_run_id: str,
    plan: ProviderResolutionPlan,
) -> None:
    evidence = plan.to_evidence()
    append_task_run_event(
        db,
        task_run_id=task_run_id,
        event_type="provider.resolved",
        payload_json=json.dumps(evidence, separators=(",", ":")),
    )
    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        return
    metrics = _json_dict(task_run.metrics_json)
    provider_gateway = metrics.get("providerGateway")
    if not isinstance(provider_gateway, dict):
        provider_gateway = {}
    provider_gateway["resolution"] = evidence
    metrics["providerGateway"] = provider_gateway
    task_run.metrics_json = json.dumps(metrics, separators=(",", ":"))
    task_run.updated_at = utc_now()
    db.add(task_run)
    db.commit()


def record_provider_health_check(
    db: DbSession,
    *,
    task_run_id: str,
    health: ProviderHealthResult,
) -> None:
    evidence = health.to_evidence()
    append_task_run_event(
        db,
        task_run_id=task_run_id,
        event_type="provider.health_checked",
        payload_json=json.dumps(evidence, separators=(",", ":")),
    )
    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        return
    metrics = _json_dict(task_run.metrics_json)
    provider_gateway = metrics.get("providerGateway")
    if not isinstance(provider_gateway, dict):
        provider_gateway = {}
    provider_gateway["health"] = evidence
    metrics["providerGateway"] = provider_gateway
    task_run.metrics_json = json.dumps(metrics, separators=(",", ":"))
    task_run.updated_at = utc_now()
    db.add(task_run)
    db.commit()


def _coding_provider_from_config(
    provider: ProviderConfig,
) -> CodingProviderMetadata:
    roles = tuple(
        role
        for role in provider.default_for_roles
        if role not in NON_CODING_ROLES
    )
    adapter_type = _coding_adapter_type_or_raise(provider.adapter_type)
    return CodingProviderMetadata(
        provider_id=provider.provider_id,
        display_name=provider.display_name,
        adapter_type=adapter_type,
        supported_roles=roles or ("frontend", "backend", "review"),
        supported_targets=("*",),
        supported_modes=_normalized_supported_modes(provider),
        capabilities=CAPABILITIES_BY_ADAPTER.get(provider.adapter_type, ()),
        auth_status=provider.auth_status,
        availability="available" if provider.available else "unavailable",
        is_real_provider=provider.adapter_type in REAL_CODING_ADAPTER_TYPES,
        is_mock_provider=provider.adapter_type in MOCK_CODING_ADAPTER_TYPES,
        is_fallback_provider=provider.adapter_type in MOCK_CODING_ADAPTER_TYPES,
        safe_launch_summary=SAFE_LAUNCH_SUMMARY_BY_ADAPTER.get(
            provider.adapter_type,
            "local coding provider launch path",
        ),
    )


def _coding_adapter_type_or_raise(adapter_type: str) -> CodingAdapterType:
    if adapter_type == "claude_code":
        return "claude_code"
    if adapter_type == "codex":
        return "codex"
    if adapter_type == "scripted_mock":
        return "scripted_mock"
    raise ProviderResolutionError(f"Not a coding adapter type: {adapter_type}")


def _normalized_supported_modes(provider: ProviderConfig) -> tuple[str, ...]:
    modes = set(provider.supported_modes)
    normalized: set[str] = set()
    if modes.intersection({"frontend", "backend"}):
        normalized.add("write")
    if modes.intersection({"qa", "review", "read_only"}):
        normalized.add("review")
    if "debug" in modes:
        normalized.add("debug")
    if provider.adapter_type == "scripted_mock":
        normalized.add("write")
    return tuple(sorted(normalized or modes))


def _candidate_decision(
    provider: CodingProviderMetadata,
    context: CodingRunContext,
) -> ProviderCandidateDecision:
    if not _provider_matches_context(provider, context):
        return ProviderCandidateDecision(
            provider_id=provider.provider_id,
            adapter_type=provider.adapter_type,
            accepted=False,
            reason=_context_rejection_reason(provider, context),
        )
    if provider.availability != "available":
        return ProviderCandidateDecision(
            provider_id=provider.provider_id,
            adapter_type=provider.adapter_type,
            accepted=False,
            reason=f"Provider availability is {provider.availability}.",
        )
    return ProviderCandidateDecision(
        provider_id=provider.provider_id,
        adapter_type=provider.adapter_type,
        accepted=True,
        reason=_selection_reason(provider, context),
    )


def _provider_matches_context(
    provider: CodingProviderMetadata,
    context: CodingRunContext,
) -> bool:
    return (
        _provider_supports_role(provider, context.role)
        and _provider_supports_target(provider, context.target_id)
        and _provider_supports_mode(provider, context)
        and _provider_supports_capabilities(provider, context.required_capabilities)
    )


def _provider_supports_role(
    provider: CodingProviderMetadata,
    role: str,
) -> bool:
    if role in NON_CODING_ROLES:
        return False
    return role in provider.supported_roles or "*" in provider.supported_roles


def _provider_supports_target(
    provider: CodingProviderMetadata,
    target_id: Optional[str],
) -> bool:
    if target_id is None:
        return True
    return "*" in provider.supported_targets or target_id in provider.supported_targets


def _provider_supports_mode(
    provider: CodingProviderMetadata,
    context: CodingRunContext,
) -> bool:
    if context.mode in provider.supported_modes:
        return True
    if context.mode == "write" and context.role in {"frontend", "backend"}:
        return "write" in provider.supported_modes
    if context.mode == "review" and context.role in {"qa", "review"}:
        return "review" in provider.supported_modes
    return False


def _provider_supports_capabilities(
    provider: CodingProviderMetadata,
    required_capabilities: tuple[str, ...],
) -> bool:
    capabilities = set(provider.capabilities)
    return all(capability in capabilities for capability in required_capabilities)


def _context_rejection_reason(
    provider: CodingProviderMetadata,
    context: CodingRunContext,
) -> str:
    if not _provider_supports_role(provider, context.role):
        return f"Provider does not support role {context.role}."
    if not _provider_supports_target(provider, context.target_id):
        return f"Provider does not support target {context.target_id}."
    if not _provider_supports_mode(provider, context):
        return f"Provider does not support mode {context.mode}."
    if not _provider_supports_capabilities(provider, context.required_capabilities):
        return "Provider is missing required coding capabilities."
    return "Provider is not compatible with this coding run."


def _selection_reason(
    provider: CodingProviderMetadata,
    context: CodingRunContext,
) -> str:
    if context.requested_provider_id == provider.provider_id:
        return "Explicit provider request is compatible."
    if context.runtime_provider_id == provider.provider_id:
        return "Runtime coding provider configuration is compatible."
    return "Default coding provider is compatible."


def _fallback_allowed(fallback_policy: str) -> bool:
    return fallback_policy not in FALLBACK_DISABLED_POLICIES


def _dedupe_decisions(
    decisions: list[ProviderCandidateDecision],
) -> list[ProviderCandidateDecision]:
    deduped: list[ProviderCandidateDecision] = []
    seen: set[tuple[str, str]] = set()
    for decision in decisions:
        key = (decision.provider_id, decision.reason)
        if key in seen:
            continue
        deduped.append(decision)
        seen.add(key)
    return deduped


def _json_dict(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _configured_cli_command(adapter_type: str) -> str:
    env_name = CLI_ENV_BY_ADAPTER.get(adapter_type)
    if env_name:
        configured = os.environ.get(env_name, "").strip()
        if configured:
            return configured
    return DEFAULT_CLI_COMMAND_BY_ADAPTER.get(adapter_type, adapter_type)


def _default_command_lookup(command: str) -> Optional[str]:
    path = Path(command)
    if path.is_absolute():
        return str(path) if path.exists() else None
    return shutil.which(command)


def _run_version_probe(executable: str) -> tuple[bool, dict[str, Any]]:
    try:
        completed = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            check=False,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return (
            False,
            {
                "error": str(exc),
                "rawRedacted": True,
            },
        )
    output = (completed.stdout or completed.stderr or "").strip()
    return (
        completed.returncode == 0,
        {
            "exitCode": completed.returncode,
            "output": output[:200],
            "rawRedacted": True,
        },
    )


def _safe_command_summary(command: str) -> str:
    if "/" not in command and "\\" not in command:
        return command
    return Path(command).name or "[command]"


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
