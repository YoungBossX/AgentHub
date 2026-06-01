from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Protocol

from app.config import Settings, get_settings

PLANNER_PROVIDER_DISABLED = "disabled"
PLANNER_PROVIDER_FAKE_TEST = "fake_test"
PLANNER_PROVIDER_CLAUDE_CLI = "claude_cli"
PLANNER_PROTOCOL_OPENAI_RESPONSES = "openai_responses"
PLANNER_PROTOCOL_OPENAI_COMPATIBLE_CHAT = "openai_compatible_chat"
PLANNER_PROTOCOL_ANTHROPIC_MESSAGES = "anthropic_messages"
DEFAULT_CLAUDE_PLANNER_BINARY = "claude"
STDERR_LIMIT = 1200


@dataclass(frozen=True)
class PlannerProviderProtocolMetadata:
    protocol: str
    display_name: str
    description: str
    real_provider: bool
    supports_json_schema: bool = False
    supports_json_object: bool = False
    supports_tool_calls: bool = False
    supports_system_prompt: bool = False
    supports_base_url: bool = False
    default_timeout_seconds: int = 60
    default_model: str | None = None

    def to_metadata(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "displayName": self.display_name,
            "description": self.description,
            "realProvider": self.real_provider,
            "supportsJsonSchema": self.supports_json_schema,
            "supportsJsonObject": self.supports_json_object,
            "supportsToolCalls": self.supports_tool_calls,
            "supportsSystemPrompt": self.supports_system_prompt,
            "supportsBaseUrl": self.supports_base_url,
            "defaultTimeoutSeconds": self.default_timeout_seconds,
            "defaultModel": self.default_model,
        }


BUILT_IN_PLANNER_PROVIDER_PROTOCOLS: tuple[PlannerProviderProtocolMetadata, ...] = (
    PlannerProviderProtocolMetadata(
        protocol=PLANNER_PROTOCOL_OPENAI_RESPONSES,
        display_name="OpenAI Responses",
        description="Official OpenAI / ChatGPT Responses API planner protocol.",
        real_provider=True,
        supports_json_schema=True,
        supports_json_object=True,
        supports_system_prompt=True,
    ),
    PlannerProviderProtocolMetadata(
        protocol=PLANNER_PROTOCOL_OPENAI_COMPATIBLE_CHAT,
        display_name="OpenAI-compatible Chat",
        description="DeepSeek, MiMo, OpenRouter, vLLM, and custom compatible chat endpoints.",
        real_provider=True,
        supports_json_object=True,
        supports_system_prompt=True,
        supports_base_url=True,
    ),
    PlannerProviderProtocolMetadata(
        protocol=PLANNER_PROTOCOL_ANTHROPIC_MESSAGES,
        display_name="Anthropic Messages",
        description="Claude / Anthropic Messages API planner protocol.",
        real_provider=True,
        supports_tool_calls=True,
        supports_system_prompt=True,
    ),
    PlannerProviderProtocolMetadata(
        protocol=PLANNER_PROVIDER_CLAUDE_CLI,
        display_name="Claude CLI",
        description="Existing local Claude CLI planner provider.",
        real_provider=True,
        supports_system_prompt=True,
    ),
    PlannerProviderProtocolMetadata(
        protocol=PLANNER_PROVIDER_FAKE_TEST,
        display_name="Fake Test",
        description="Deterministic test-only planner provider.",
        real_provider=False,
    ),
    PlannerProviderProtocolMetadata(
        protocol=PLANNER_PROVIDER_DISABLED,
        display_name="Disabled",
        description="Explicit disabled planner provider.",
        real_provider=False,
    ),
)


def list_planner_provider_protocols() -> list[PlannerProviderProtocolMetadata]:
    return list(BUILT_IN_PLANNER_PROVIDER_PROTOCOLS)


def get_planner_provider_protocol(protocol: str) -> PlannerProviderProtocolMetadata | None:
    normalized = protocol.strip().lower()
    for item in BUILT_IN_PLANNER_PROVIDER_PROTOCOLS:
        if item.protocol == normalized:
            return item
    return None


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


class PlannerCommandRunner(Protocol):
    def run(
        self,
        command: list[str],
        *,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        ...


class SubprocessPlannerCommandRunner:
    def run(
        self,
        command: list[str],
        *,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )


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


class ClaudeCliPlannerProvider:
    provider_id = "claude-cli-planner"
    provider_type = PLANNER_PROVIDER_CLAUDE_CLI
    planner_source = "real_llm"

    def __init__(
        self,
        *,
        command_runner: PlannerCommandRunner | None = None,
        claude_binary: str | None = None,
        timeout_sec: int = 60,
    ) -> None:
        self._command_runner = command_runner or SubprocessPlannerCommandRunner()
        self._claude_binary = (
            claude_binary
            or os.environ.get("AGENTHUB_LLM_PLANNER_CLAUDE_CLI_PATH")
            or DEFAULT_CLAUDE_PLANNER_BINARY
        )
        self._timeout_sec = timeout_sec

    def create_plan(self, planner_input: dict[str, Any]) -> PlannerProviderResult:
        command = self._build_command(planner_input)
        started = time.monotonic()
        try:
            completed = self._command_runner.run(command, timeout=self._timeout_sec)
        except subprocess.TimeoutExpired:
            return self._error_result(
                "PLANNER_TIMEOUT",
                f"Claude CLI planner timed out after {self._timeout_sec} seconds.",
                started,
            )
        except FileNotFoundError:
            return self._error_result(
                "PLANNER_PROVIDER_UNAVAILABLE",
                "Claude CLI planner executable was not found.",
                started,
            )
        except Exception as exc:
            return self._error_result(
                "PLANNER_RUNTIME_ERROR",
                str(exc) or "Claude CLI planner failed before producing output.",
                started,
            )

        duration_ms = _duration_ms(started)
        stderr = _excerpt(completed.stderr or "")
        stdout = completed.stdout or ""
        if completed.returncode != 0:
            code = _planner_error_code_for_text(stderr or stdout)
            return PlannerProviderResult(
                provider_id=self.provider_id,
                provider_type=self.provider_type,
                planner_source=self.planner_source,
                status="failed",
                duration_ms=duration_ms,
                error_code=code,
                error_summary=stderr or f"Claude CLI planner exited with code {completed.returncode}.",
            )
        if not stdout.strip():
            return PlannerProviderResult(
                provider_id=self.provider_id,
                provider_type=self.provider_type,
                planner_source=self.planner_source,
                status="failed",
                duration_ms=duration_ms,
                error_code="PLANNER_EMPTY_OUTPUT",
                error_summary="Claude CLI planner returned no output.",
            )
        return PlannerProviderResult(
            provider_id=self.provider_id,
            provider_type=self.provider_type,
            planner_source=self.planner_source,
            status="succeeded",
            raw_output=stdout.strip(),
            duration_ms=duration_ms,
        )

    def _build_command(self, planner_input: dict[str, Any]) -> list[str]:
        prompt = (
            "You are AgentHub's Conversation Router and llm_v1 planning engine. "
            "Return ONLY one JSON object. Do not include Markdown fences, "
            "analysis text, comments, or a second JSON object. The JSON must "
            "match this ConversationOutcome contract exactly enough to "
            "validate: top-level fields outcomeType, reply, planDraft, "
            "riskLevel, reason, plannerProvider, validationResult, "
            "fallbackMetadata, errorMetadata. outcomeType must be one of "
            "assistant_reply, task_plan, clarification, refusal, "
            "approval_required, unsupported. For normal chat, greetings, or "
            "capability questions, return assistant_reply and do not include "
            "planDraft. For unclear requests, return clarification. For unsafe "
            "requests, return refusal or approval_required. For programming "
            "requests, return task_plan and include planDraft. planDraft must "
            "match this PlannerResponse contract: top-level fields planId, "
            "planner, plannerMode, rationale, tasks, acceptanceCriteria, "
            "validationExpectations, intent, version, guardrailNotes. Each task "
            "must include title, role, targetId, intentType, plannedFiles, "
            "dependsOn, expectedArtifactTypes, acceptanceCriteria, riskLevel, "
            "requiresApproval, validationExpectations, and rationale. planner "
            "and plannerMode must both be llm_v1. version must be an integer. "
            "guardrailNotes must be an array of strings. Create at most 4 tasks. "
            "Use only these roles: orchestrator, frontend, backend, qa. Use only "
            "these intentType values: planning, frontend_change, backend_change, "
            "review. Use only these expectedArtifactTypes values: plan, diff, "
            "review. For a bounded frontend game request, prefer one frontend "
            "implementation task plus one qa review task. If dependsOn is used, "
            "reference dependency keys in the form 1-frontend-frontend_change, "
            "not task titles. Do not invoke coding agents for normal chat. Do "
            "not edit files, run commands, deploy, or call external services. "
            "Use only the provided target registry, roles, capabilities, and "
            "guardrails.\n\n"
            "PlannerRequest JSON:\n"
            f"{json.dumps(planner_input, ensure_ascii=False, sort_keys=True)}"
        )
        return [
            self._claude_binary,
            "--print",
            "--output-format",
            "text",
            "--permission-mode",
            "dontAsk",
            "--allowedTools",
            "Read",
            "--no-session-persistence",
            prompt,
        ]

    def _error_result(
        self,
        code: str,
        summary: str,
        started: float,
    ) -> PlannerProviderResult:
        return PlannerProviderResult(
            provider_id=self.provider_id,
            provider_type=self.provider_type,
            planner_source=self.planner_source,
            status="failed",
            duration_ms=_duration_ms(started),
            error_code=code,
            error_summary=summary,
        )


def resolve_planner_provider(
    settings: Settings | None = None,
    *,
    fake_payload: dict[str, Any] | None = None,
    provider_id: str | None = None,
    adapter_type: str | None = None,
) -> PlannerProvider:
    resolved_settings = settings or get_settings()
    selected_provider_id = (
        provider_id or resolved_settings.llm_planner_provider
    ).strip().lower()
    selected_adapter_type = (adapter_type or "").strip().lower()
    if selected_provider_id == PLANNER_PROVIDER_DISABLED:
        return DisabledPlannerProvider()
    if selected_provider_id == PLANNER_PROVIDER_FAKE_TEST:
        if fake_payload is None:
            raise PlannerProviderError(
                code="FAKE_PLANNER_PAYLOAD_REQUIRED",
                summary="Fake planner provider requires an explicit test payload.",
                provider_id=selected_provider_id,
            )
        return FakePlannerProvider(payload=fake_payload)
    if (
        selected_provider_id in {PLANNER_PROVIDER_CLAUDE_CLI, "claude-cli-planner"}
        or selected_adapter_type == PLANNER_PROVIDER_CLAUDE_CLI
    ):
        return ClaudeCliPlannerProvider(
            timeout_sec=resolved_settings.llm_planner_timeout_sec,
        )
    raise PlannerProviderError(
        code="UNKNOWN_PLANNER_PROVIDER",
        summary=f"Unknown LLM planner provider: {selected_provider_id}",
        provider_id=selected_provider_id,
    )


def _duration_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))


def _excerpt(value: str) -> str:
    if len(value) <= STDERR_LIMIT:
        return value
    return value[:STDERR_LIMIT]


def _planner_error_code_for_text(text: str) -> str:
    normalized = text.lower()
    if "usage limit" in normalized or "rate limit" in normalized or "quota" in normalized:
        return "PLANNER_QUOTA_LIMIT"
    if (
        "auth" in normalized
        or "login" in normalized
        or "not logged in" in normalized
        or "unauthorized" in normalized
        or "api key" in normalized
    ):
        return "PLANNER_AUTH_REQUIRED"
    if "timeout" in normalized or "timed out" in normalized:
        return "PLANNER_TIMEOUT"
    return "PLANNER_RUNTIME_ERROR"
