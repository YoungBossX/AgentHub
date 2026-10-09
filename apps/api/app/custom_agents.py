"""Workspace custom profiles, with native adapter tool policies and no new roles."""

import json
import re
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session as DbSession, select

from app.agent_capabilities import validate_capability_tags
from app.agent_runtime_config import RuntimeRoleConfig, RuntimeRoleResolution, resolve_runtime_role_config
from app.models import AgentProfileDraft, utc_now
from app.provider_configs import ProviderConfig, list_provider_configs
from app.target_registry import get_target_for_workspace, TargetRegistryError


class CustomAgentError(ValueError):
    pass


# These are concrete existing transport policies, not arbitrary tool names.
TOOL_POLICIES = {
    "codex_coding": ("codex", {"frontend", "backend"}, "native_coding"),
    "claude_file_edit": ("claude_code", {"frontend", "backend"}, "Read,Write,Edit,MultiEdit"),
    "claude_read_only": ("claude_code", {"review"}, "Read"),
    "planner_no_tools": ("claude_cli", {"orchestrator"}, ""),
}
ROLE_CAPABILITIES = {
    "frontend": {"code_write", "diff_analysis", "preview"},
    "backend": {"code_write", "diff_analysis"},
    "review": {"code_review", "diff_analysis"},
    "orchestrator": {"code_review", "diff_analysis"},
}
ALIAS_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
MENTION_PATTERN = re.compile(r"@([A-Za-z][A-Za-z0-9_-]*)")
RESERVED_ALIASES = {"frontend", "backend", "qa", "review", "orchestrator", "planner", "manager", "fallback"}


def custom_runtime_resolution(profile: AgentProfileDraft) -> RuntimeRoleResolution:
    return RuntimeRoleResolution(
        role_config=RuntimeRoleConfig(
            role="planner" if profile.role == "orchestrator" else profile.role,
            agent_profile_id=profile.id, provider_id=profile.provider_id,
            adapter_type=profile.adapter_type,
            mode="read_only" if profile.role == "orchestrator" else profile.role, enabled=True,
        ),
        config_source="explicit_profile",
    )


@dataclass(frozen=True)
class CustomAgentInput:
    display_name: str
    mention_alias: str
    role: str
    provider_id: str
    tool_policy: str
    supported_targets: list[str]
    capability_tags: list[str]
    system_prompt: str = ""
    description: str = ""
    avatar_initials: str = ""
    enabled: bool = True


def validate_custom_agent(
    db: DbSession, *, workspace_id: str, value: CustomAgentInput,
    profile_id: str | None = None,
) -> tuple[str, ProviderConfig, list[str]]:
    if profile_id is not None:
        require_custom_agent(db, workspace_id, profile_id, require_enabled=False)
    alias = value.mention_alias.strip().lower()
    if not ALIAS_PATTERN.fullmatch(alias) or alias in RESERVED_ALIASES:
        raise CustomAgentError("Custom Agent alias must be a unique non-reserved ASCII identifier (2-64 characters).")
    if not value.display_name.strip() or len(value.display_name) > 80:
        raise CustomAgentError("Custom Agent displayName must contain 1-80 characters.")
    if len(value.system_prompt) > 8000 or "\x00" in value.system_prompt:
        raise CustomAgentError("Custom Agent systemPrompt must contain at most 8000 characters without NUL.")
    policy = TOOL_POLICIES.get(value.tool_policy)
    if policy is None or value.role not in policy[1]:
        raise CustomAgentError("Custom Agent toolPolicy is incompatible with its role.")
    provider = next((p for p in list_provider_configs() if p.provider_id == value.provider_id), None)
    if provider is None or not provider.available or provider.adapter_type != policy[0]:
        raise CustomAgentError("Custom Agent provider is unavailable or incompatible with its native toolPolicy.")
    capabilities = validate_capability_tags(value.capability_tags, source="CustomAgent")
    if not set(capabilities).issubset(ROLE_CAPABILITIES[value.role]):
        raise CustomAgentError("Custom Agent capabilities exceed the permitted role boundary.")
    required = "code_write" if value.role in {"frontend", "backend"} else "code_review"
    if required not in capabilities:
        raise CustomAgentError(f"Custom Agent requires capability `{required}`.")
    if not value.supported_targets:
        raise CustomAgentError("Custom Agent must declare registered supportedTargets.")
    for target_id in value.supported_targets:
        try:
            target = get_target_for_workspace(db, workspace_id, target_id)
        except TargetRegistryError as exc:
            raise CustomAgentError("Custom Agent target is not registered in this workspace.") from exc
        target_role = "qa" if value.role == "orchestrator" else value.role
        if target.requires_platform_mode or not target.allows_agent(target_role):
            raise CustomAgentError("Custom Agent target is outside its permitted role boundary.")
    duplicate = db.exec(select(AgentProfileDraft).where(
        AgentProfileDraft.workspace_id == workspace_id,
        AgentProfileDraft.mention_alias == alias,
    )).first()
    if duplicate is not None and duplicate.id != profile_id:
        raise CustomAgentError("Custom Agent alias already exists in this workspace.")
    return alias, provider, capabilities


def save_custom_agent(
    db: DbSession, *, workspace_id: str, value: CustomAgentInput,
    profile_id: str | None = None,
) -> AgentProfileDraft:
    alias, provider, capabilities = validate_custom_agent(db, workspace_id=workspace_id, value=value, profile_id=profile_id)
    existing = require_custom_agent(db, workspace_id, profile_id, require_enabled=False) if profile_id else None
    profile = existing or AgentProfileDraft(workspace_id=workspace_id)
    profile.display_name = value.display_name.strip()
    profile.mention_alias = alias
    profile.role = value.role
    profile.adapter_type = provider.adapter_type
    profile.provider_id = value.provider_id
    profile.tool_policy = value.tool_policy
    profile.system_prompt = value.system_prompt
    profile.description = value.description.strip()
    profile.avatar_initials = (value.avatar_initials.strip() or value.display_name.strip()[:2]).upper()[:3]
    profile.capability_tags_json = json.dumps(list(dict.fromkeys(capabilities)))
    profile.supported_targets_json = json.dumps(list(dict.fromkeys(value.supported_targets)))
    profile.supported_modes_json = json.dumps(
        [value.role] if value.role in {"frontend", "backend"} else
        ["review", "qa", "read_only"] if value.role == "review" else ["read_only"]
    )
    profile.safe_for_write = value.role in {"frontend", "backend"}
    profile.safe_for_review = not profile.safe_for_write
    profile.status = "available" if value.enabled else "disabled"
    profile.updated_at = utc_now()
    db.add(profile)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise CustomAgentError("Custom Agent alias already exists in this workspace.") from exc
    db.refresh(profile)
    return profile


def require_custom_agent(
    db: DbSession, workspace_id: str, profile_id: str, *, require_enabled: bool = True,
) -> AgentProfileDraft:
    profile = db.get(AgentProfileDraft, profile_id)
    if profile is None or profile.workspace_id != workspace_id or not profile.tool_policy:
        raise CustomAgentError("Custom Agent is not available in this workspace.")
    if require_enabled and profile.status != "available":
        raise CustomAgentError("Custom Agent is disabled.")
    return profile


def custom_agent_mentions(db: DbSession, workspace_id: str, content: str) -> dict[str, AgentProfileDraft]:
    selected: dict[str, AgentProfileDraft] = {}
    for alias in MENTION_PATTERN.findall(content):
        profile = db.exec(select(AgentProfileDraft).where(
            AgentProfileDraft.workspace_id == workspace_id,
            AgentProfileDraft.mention_alias == alias.lower(),
        )).first()
        if profile is None:
            continue
        profile = require_custom_agent(db, workspace_id, profile.id)
        prior = selected.get(profile.role)
        if prior is not None and prior.id != profile.id:
            raise CustomAgentError("Multiple custom Agents for the same role are ambiguous.")
        selected[profile.role] = profile
    return selected


def selected_custom_planner(db: DbSession, workspace_id: str, content: str) -> AgentProfileDraft | None:
    explicit = custom_agent_mentions(db, workspace_id, content).get("orchestrator")
    if explicit is not None:
        return explicit
    runtime = resolve_runtime_role_config(db, workspace_id, "planner")
    candidate = db.get(AgentProfileDraft, runtime.role_config.agent_profile_id) if runtime and runtime.role_config.agent_profile_id else None
    if candidate is not None:
        return require_custom_agent(db, workspace_id, candidate.id)
    return None


def custom_launch_permissions(db: DbSession, workspace_id: str, metrics: dict, adapter_type: str) -> dict:
    selection = metrics.get("agentSelection")
    custom = selection.get("customProfile") if isinstance(selection, dict) else None
    if custom is None:
        return {"network": "off"}
    if not isinstance(custom, dict) or not isinstance(custom.get("id"), str):
        raise CustomAgentError("Custom Agent execution binding is invalid.")
    profile = db.exec(select(AgentProfileDraft).where(
        AgentProfileDraft.id == custom["id"],
    ).execution_options(populate_existing=True)).first()
    if profile is None or profile.workspace_id != workspace_id or profile.status != "available":
        raise CustomAgentError("Selected custom Agent was disabled or is unavailable before launch.")
    policy = TOOL_POLICIES.get(custom.get("toolPolicy"))
    if policy is None or custom.get("role") not in policy[1]:
        raise CustomAgentError("Frozen custom Agent tool policy is invalid.")
    if adapter_type == "scripted_mock":
        if custom.get("role") != "frontend" or selection.get("targetId") != "demo-frontend":
            raise CustomAgentError("Custom Agent fallback is limited to the demo frontend.")
        return {"network": "off"}
    if policy[0] != adapter_type:
        raise CustomAgentError("Frozen custom Agent tool policy does not match its adapter.")
    return {"network": "off", "toolPolicy": custom["toolPolicy"]}
