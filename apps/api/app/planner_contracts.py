from __future__ import annotations

import copy
import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class PlannerProjectSetupTarget(BaseModel):
    target_id: str = Field(alias="targetId")
    role: str
    root_path: str = Field(alias="rootPath")
    project_type: str = Field(alias="projectType")
    allowed_paths: list[str] = Field(alias="allowedPaths")
    validation_commands: list[str] = Field(default_factory=list, alias="validationCommands")

    model_config = ConfigDict(populate_by_name=True)


class PlannerProjectSetup(BaseModel):
    project_kind: str = Field(alias="projectKind")
    planned_project_root: str = Field(alias="plannedProjectRoot")
    default_frontend_stack: Optional[str] = Field(default=None, alias="defaultFrontendStack")
    default_backend_stack: Optional[str] = Field(default=None, alias="defaultBackendStack")
    provisional_targets: list[PlannerProjectSetupTarget] = Field(
        default_factory=list,
        alias="provisionalTargets",
    )
    approval_required_commands: list[str] = Field(
        default_factory=list,
        alias="approvalRequiredCommands",
    )

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
    project_setup: Optional[PlannerProjectSetup] = Field(default=None, alias="projectSetup")

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


ConversationOutcomeType = Literal[
    "assistant_reply",
    "task_plan",
    "clarification",
    "refusal",
    "approval_required",
    "unsupported",
]


class ConversationOutcome(BaseModel):
    outcome_type: ConversationOutcomeType = Field(alias="outcomeType")
    reply: Optional[str] = None
    plan_draft: Optional[PlannerResponse] = Field(default=None, alias="planDraft")
    risk_level: str = Field(default="low", alias="riskLevel")
    reason: str = ""
    planner_provider: dict[str, Any] = Field(default_factory=dict, alias="plannerProvider")
    coding_agent_provider: Optional[dict[str, Any]] = Field(
        default=None,
        alias="codingAgentProvider",
    )
    validation_result: str = Field(default="not_run", alias="validationResult")
    fallback_metadata: dict[str, Any] = Field(default_factory=dict, alias="fallbackMetadata")
    error_metadata: dict[str, Any] = Field(default_factory=dict, alias="errorMetadata")

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def validate_task_plan_boundary(self) -> "ConversationOutcome":
        if self.outcome_type == "task_plan":
            if self.plan_draft is None:
                raise ValueError("task_plan outcomes must include planDraft.")
            if self.coding_agent_provider is not None:
                raise ValueError(
                    "ConversationOutcome must keep coding agent provider evidence downstream of planning."
                )
            return self
        if self.plan_draft is not None:
            raise ValueError("Non-task conversation outcomes must not include planDraft.")
        return self

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


def planner_conversation_system_prompt() -> str:
    return (
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
        "requests, return refusal or approval_required. For programming, "
        "coding, build, implement, create, develop, modify, add, generate, "
        "scaffold, or fix software requests, return task_plan and include "
        "planDraft when the request can be target-scoped safely. If the user "
        "asks for a new project, include projectSetup so AgentHub can prepare "
        "explicit frontend/backend boundaries before coding; do not pretend an "
        "unprepared project already exists. planDraft must "
        "match this PlannerResponse contract: top-level fields planId, "
        "planner, plannerMode, rationale, tasks, acceptanceCriteria, "
        "validationExpectations, intent, version, guardrailNotes, and optional "
        "projectSetup. planId must "
        "be a stable string. planner and plannerMode must both be llm_v1. "
        "version must be an integer. rationale must explain why the requested "
        "task split is safe and target-scoped. acceptanceCriteria and "
        "validationExpectations must be arrays of strings. guardrailNotes must "
        "be an array of strings. projectSetup, when present, must include "
        "projectKind, plannedProjectRoot, defaultFrontendStack, "
        "defaultBackendStack, provisionalTargets, and approvalRequiredCommands. "
        "Each provisional target must include targetId, role, rootPath, "
        "projectType, allowedPaths, and validationCommands. Each task must "
        "include title, role, targetId, "
        "intentType, plannedFiles, dependsOn, expectedArtifactTypes, "
        "acceptanceCriteria, riskLevel, requiresApproval, "
        "validationExpectations, and rationale. targetId must be one of the "
        "provided Target Registry target ids. plannedFiles must stay inside the "
        "target allowedPaths and avoid deniedPaths. dependsOn must be an array "
        "of dependency keys. expectedArtifactTypes must describe evidence the "
        "task should produce. riskLevel must be low, medium, or high. "
        "requiresApproval must be true for platform maintenance or high-risk "
        "writes. Create at most 4 tasks. Use only these roles: orchestrator, "
        "frontend, backend, qa. Use only these intentType values: planning, "
        "frontend_change, backend_change, review. Use only these "
        "expectedArtifactTypes values: plan, diff, review. For a bounded "
        "frontend game request, prefer one frontend "
        "implementation task plus one qa review task. If dependsOn is used, "
        "reference dependency keys in the form 1-frontend-frontend_change, "
        "not task titles. Do not invoke coding agents for normal chat. Do "
        "not edit files, run commands, deploy, or call external services. "
        "Use only the provided target registry, roles, capabilities, and "
        "guardrails. Never execute code or call agents directly. Every "
        "task_plan will be validated before scheduling. Few-shot examples: "
        "Example user: 你好. Example output: {\"outcomeType\":\"assistant_reply\","
        "\"reply\":\"你好，有什么我可以帮你的？\",\"riskLevel\":\"low\","
        "\"reason\":\"Greeting only.\",\"validationResult\":\"not_required\"}. "
        "Example user: 帮我在桌面开发一个简单的图书管理系统。有登录页面，"
        "登录后可以加入图书、删除图书、修改图书、查询图书。 "
        "Example output: {\"outcomeType\":\"task_plan\",\"reply\":\"我会把它规划成"
        "一个目标范围内的前端实现任务，并保留验证要求。\",\"riskLevel\":\"medium\","
        "\"reason\":\"The user is asking to build a software application, so this "
        "requires an executable task plan.\",\"validationResult\":\"pending\","
        "\"planDraft\":{\"planId\":\"plan-library-management-frontend\","
        "\"planner\":\"llm_v1\",\"plannerMode\":\"llm_v1\","
        "\"rationale\":\"Create one frontend implementation task scoped to the "
        "registered frontend target; do not add backend or database unless "
        "explicitly requested.\",\"tasks\":[{\"title\":\"Build library management "
        "frontend\",\"role\":\"frontend\",\"targetId\":\"<frontend-target-id>\","
        "\"intentType\":\"frontend_change\",\"plannedFiles\":[\"src/App.tsx\","
        "\"src/App.css\"],\"dependsOn\":[],\"expectedArtifactTypes\":[\"diff\","
        "\"review\"],\"acceptanceCriteria\":[\"Login page accepts the requested "
        "demo credentials\",\"Management page supports adding, deleting, editing, "
        "and searching books\",\"Book data persists locally when no backend is "
        "requested\"],\"riskLevel\":\"medium\",\"requiresApproval\":false,"
        "\"validationExpectations\":[\"run configured frontend build or check "
        "command\"],\"rationale\":\"This is a bounded frontend app request inside "
        "the selected target.\"}],\"acceptanceCriteria\":[\"The library management "
        "app is usable in browser\",\"No backend or database is added without "
        "explicit request\"],\"validationExpectations\":[\"configured frontend "
        "build/check passes\"],\"intent\":\"real_coding_request\",\"version\":1,"
        "\"guardrailNotes\":[\"Use the provided target id instead of the literal "
        "<frontend-target-id> placeholder.\"]}}. Treat inventory, book, product, "
        "student, order, or other CRUD-style app requests the same way: if they "
        "ask to build or implement software and a safe frontend target is "
        "available, return task_plan rather than assistant_reply."
    )


def conversation_outcome_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "outcomeType": {
                "type": "string",
                "enum": [
                    "assistant_reply",
                    "task_plan",
                    "clarification",
                    "refusal",
                    "approval_required",
                    "unsupported",
                ],
            },
            "reply": {"type": ["string", "null"]},
            "reason": {"type": ["string", "null"]},
            "riskLevel": {"type": ["string", "null"]},
            "planDraft": {"type": ["object", "null"], "additionalProperties": True},
            "plannerProvider": {"type": ["object", "null"], "additionalProperties": True},
            "codingAgentProvider": {"type": ["object", "null"], "additionalProperties": True},
            "validationResult": {"type": ["string", "null"]},
            "fallbackMetadata": {"type": ["object", "null"], "additionalProperties": True},
            "errorMetadata": {"type": ["object", "null"], "additionalProperties": True},
        },
        "required": ["outcomeType"],
    }


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
