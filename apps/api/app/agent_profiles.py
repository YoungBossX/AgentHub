from dataclasses import dataclass
from typing import Any

from app.agent_capabilities import validate_capability_tags, validate_supported_modes
from app.models import Agent
from app.provider_assignments import resolve_profile_provider_assignment


@dataclass(frozen=True)
class AgentProfile:
    id: str
    display_name: str
    avatar_initials: str
    role: str
    adapter_type: str
    provider_id: str
    capability_tags: list[str]
    supported_roles: list[str]
    supported_targets: list[str]
    supported_modes: list[str]
    safe_for_write: bool
    safe_for_review: bool
    description: str
    status: str


BUILT_IN_AGENT_PROFILE_METADATA: dict[str, dict[str, Any]] = {
    "orchestrator": {
        "displayName": "Manager / Orchestrator",
        "avatarInitials": "MO",
        "capabilityTags": ["diff_analysis", "code_review"],
        "supportedRoles": ["orchestrator", "manager"],
        "supportedTargets": ["demo-frontend", "demo-backend", "external"],
        "supportedModes": ["read_only", "debug"],
        "safeForWrite": False,
        "safeForReview": True,
        "description": "Plans the local workflow and coordinates role agents.",
    },
    "frontend": {
        "displayName": "Frontend Agent",
        "avatarInitials": "FE",
        "capabilityTags": ["code_write", "diff_analysis", "preview"],
        "supportedRoles": ["frontend"],
        "supportedTargets": ["demo-frontend", "external-frontend"],
        "supportedModes": ["frontend"],
        "safeForWrite": True,
        "safeForReview": False,
        "description": "Executes bounded frontend changes inside assigned target paths.",
    },
    "backend": {
        "displayName": "Backend Agent",
        "avatarInitials": "BE",
        "capabilityTags": ["code_write", "test_run", "diff_analysis"],
        "supportedRoles": ["backend"],
        "supportedTargets": ["demo-backend", "external-backend"],
        "supportedModes": ["backend"],
        "safeForWrite": True,
        "safeForReview": False,
        "description": "Works on safe application backend targets, not AgentHub platform backend by default.",
    },
    "qa": {
        "displayName": "QA Agent",
        "avatarInitials": "QA",
        "capabilityTags": ["code_review", "test_run", "diff_analysis", "preview"],
        "supportedRoles": ["qa", "review"],
        "supportedTargets": ["demo-frontend", "demo-backend", "external"],
        "supportedModes": ["qa", "review", "read_only"],
        "safeForWrite": False,
        "safeForReview": True,
        "description": "Reviews workflow evidence and validates target outputs without changing dispatch.",
    },
    "review": {
        "displayName": "Review Agent",
        "avatarInitials": "RV",
        "capabilityTags": ["code_review", "diff_analysis"],
        "supportedRoles": ["review", "qa"],
        "supportedTargets": ["demo-frontend", "demo-backend", "external"],
        "supportedModes": ["review", "read_only"],
        "safeForWrite": False,
        "safeForReview": True,
        "description": "Represents the read-oriented review workflow and scripted review fallback.",
        "status": "planned",
    },
    "fallback": {
        "displayName": "Fallback Agent / ScriptedMock",
        "avatarInitials": "FB",
        "capabilityTags": ["code_write", "diff_analysis"],
        "supportedRoles": ["fallback"],
        "supportedTargets": ["demo-frontend"],
        "supportedModes": ["frontend"],
        "safeForWrite": True,
        "safeForReview": False,
        "description": "Documents the preserved ScriptedMockAdapter reliability path.",
        "status": "available",
    },
}

VIRTUAL_AGENT_PROFILE_AGENTS: tuple[Agent, ...] = (
    Agent(
        id="virtual-review-agent",
        name="Review Agent",
        role="review",
        adapter_type="scripted_mock",
        provider="local-scripted-review",
        enabled=True,
    ),
    Agent(
        id="virtual-fallback-agent",
        name="Fallback Agent / ScriptedMock",
        role="fallback",
        adapter_type="scripted_mock",
        provider="local-scripted-mock",
        enabled=True,
    ),
)


def list_agent_profile_registry(
    agents: list[Agent],
    *,
    include_virtual: bool = True,
) -> list[AgentProfile]:
    profiles = [profile_for_agent(agent) for agent in agents]
    if include_virtual:
        profiles.extend(profile_for_agent(agent) for agent in VIRTUAL_AGENT_PROFILE_AGENTS)
    return profiles


def profile_for_agent(agent: Agent) -> AgentProfile:
    metadata = BUILT_IN_AGENT_PROFILE_METADATA.get(agent.role, {})
    assignment = resolve_profile_provider_assignment(agent.role, agent)
    capability_tags = validate_capability_tags(
        list(metadata.get("capabilityTags") or []),
        source=f"AgentProfile:{agent.role}",
    )
    supported_modes = validate_supported_modes(
        list(metadata.get("supportedModes") or []),
        source=f"AgentProfile:{agent.role}",
    )
    return AgentProfile(
        id=agent.id,
        display_name=str(metadata.get("displayName") or agent.name),
        avatar_initials=str(metadata.get("avatarInitials") or agent.role[:2].upper()),
        role=agent.role,
        adapter_type=assignment.adapter_type,
        provider_id=assignment.provider_id,
        capability_tags=capability_tags,
        supported_roles=list(metadata.get("supportedRoles") or [agent.role]),
        supported_targets=list(metadata.get("supportedTargets") or []),
        supported_modes=supported_modes,
        safe_for_write=bool(metadata.get("safeForWrite", False)),
        safe_for_review=bool(metadata.get("safeForReview", False)),
        description=str(metadata.get("description") or agent.system_prompt),
        status=_status_for_agent(agent, metadata),
    )


def _status_for_agent(agent: Agent, metadata: dict[str, Any]) -> str:
    metadata_status = metadata.get("status")
    if isinstance(metadata_status, str) and metadata_status:
        return metadata_status
    return "available" if agent.enabled else "disabled"
