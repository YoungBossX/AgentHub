from __future__ import annotations

import copy
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


SECRET_VALUE_PATTERN = re.compile(
    r"(?i)(secret|token|password|api[_-]?key)\s*=\s*[^\s]+"
)
PROTECTED_ABSOLUTE_PATH_PATTERN = re.compile(
    r"/[^\s]*?(?:\.env|/\.git|/node_modules|/\.venv|/secrets)(?:[^\s]*)?"
)


class PlannerRequest(BaseModel):
    planner_mode: str = Field(alias="plannerMode")
    version: int
    original_user_request: str = Field(alias="originalUserRequest")
    canonical_shared_context: dict[str, Any] = Field(alias="canonicalSharedContext")
    target_registry: list[dict[str, Any]] = Field(alias="targetRegistry")
    project_analyzer: list[dict[str, Any]] = Field(alias="projectAnalyzer")
    recent_messages: list[dict[str, Any]] = Field(alias="recentMessages")
    artifact_references: list[dict[str, Any]] = Field(alias="artifactReferences")
    supported_roles: list[str] = Field(alias="supportedRoles")
    supported_modes: list[str] = Field(alias="supportedModes")
    supported_capabilities: list[str] = Field(alias="supportedCapabilities")
    guardrails: dict[str, Any]

    model_config = ConfigDict(populate_by_name=True)

    def to_provider_payload(self) -> dict[str, Any]:
        return _redact_provider_visible_value(self.model_dump(by_alias=True))


class PlannerTaskResponse(BaseModel):
    title: str
    role: str
    target_id: str = Field(alias="targetId")
    intent_type: str = Field(alias="intentType")
    planned_files: list[str] = Field(alias="plannedFiles")
    depends_on: list[str] = Field(default_factory=list, alias="dependsOn")
    expected_artifact_types: list[str] = Field(alias="expectedArtifactTypes")
    acceptance_criteria: list[str] = Field(alias="acceptanceCriteria")
    risk_level: str = Field(alias="riskLevel")
    requires_approval: bool = Field(alias="requiresApproval")
    validation_expectations: list[str] = Field(
        default_factory=list,
        alias="validationExpectations",
    )
    rationale: str = ""

    model_config = ConfigDict(populate_by_name=True)


class PlannerResponse(BaseModel):
    plan_id: str = Field(alias="planId")
    planner: str
    planner_mode: str = Field(alias="plannerMode")
    rationale: str
    tasks: list[PlannerTaskResponse]
    acceptance_criteria: list[str] = Field(alias="acceptanceCriteria")
    validation_expectations: list[str] = Field(alias="validationExpectations")
    intent: str = "real_coding_request"
    version: int = 1
    guardrail_notes: list[str] = Field(default_factory=list, alias="guardrailNotes")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("version", mode="before")
    @classmethod
    def normalize_version(cls, value: Any) -> int:
        if isinstance(value, str):
            head = value.split(".", 1)[0]
            if head.isdigit():
                return int(head)
        return value

    @field_validator("guardrail_notes", mode="before")
    @classmethod
    def normalize_guardrail_notes(cls, value: Any) -> list[str]:
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return value

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


def _redact_provider_visible_value(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _is_secret_key(key):
                redacted[key] = "[protected]"
            else:
                redacted[key] = _redact_provider_visible_value(item)
        return redacted
    if isinstance(value, list):
        return [_redact_provider_visible_value(item) for item in value]
    if isinstance(value, str):
        return _redact_string(value)
    return copy.deepcopy(value)


def _is_secret_key(key: Any) -> bool:
    normalized = str(key).lower()
    return any(marker in normalized for marker in ("secret", "token", "password", "api_key", "apikey"))


def _redact_string(value: str) -> str:
    redacted = SECRET_VALUE_PATTERN.sub("[protected]", value)
    return PROTECTED_ABSOLUTE_PATH_PATTERN.sub("[protected]", redacted)
