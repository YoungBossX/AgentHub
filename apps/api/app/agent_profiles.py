from dataclasses import dataclass
from typing import Any

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
        "capabilityTags": ["planning", "task assignment", "coordination"],
        "supportedRoles": ["orchestrator", "manager"],
        "supportedTargets": ["demo-frontend", "demo-backend", "external"],
        "supportedModes": ["direct-chat", "group-workflow", "contract-planning"],
        "safeForWrite": False,
        "safeForReview": True,
        "description": "Plans the local workflow and coordinates role agents.",
    },
    "frontend": {
        "displayName": "Frontend Agent",
        "avatarInitials": "FE",
        "capabilityTags": ["Vite React", "UI changes", "diff artifacts"],
        "supportedRoles": ["frontend"],
        "supportedTargets": ["demo-frontend", "external-frontend"],
        "supportedModes": ["direct-assignment", "scheduled-task"],
        "safeForWrite": True,
        "safeForReview": False,
        "description": "Executes bounded frontend changes inside assigned target paths.",
    },
    "backend": {
        "displayName": "Backend Agent",
        "avatarInitials": "BE",
        "capabilityTags": ["FastAPI", "API changes", "SQLite"],
        "supportedRoles": ["backend"],
        "supportedTargets": ["demo-backend", "external-backend"],
        "supportedModes": ["direct-assignment", "scheduled-task"],
        "safeForWrite": True,
        "safeForReview": False,
        "description": "Works on safe application backend targets, not AgentHub platform backend by default.",
    },
    "qa": {
        "displayName": "QA Agent",
        "avatarInitials": "QA",
        "capabilityTags": ["demo QA", "preview checks", "workflow review"],
        "supportedRoles": ["qa", "review"],
        "supportedTargets": ["demo-frontend", "demo-backend", "external"],
        "supportedModes": ["review", "qa-check"],
        "safeForWrite": False,
        "safeForReview": True,
        "description": "Reviews workflow evidence and validates target outputs without changing dispatch.",
    },
    "review": {
        "displayName": "Review Agent",
        "avatarInitials": "RV",
        "capabilityTags": ["planned", "read-only", "non-blocking review"],
        "supportedRoles": ["review", "qa"],
        "supportedTargets": ["demo-frontend", "demo-backend", "external"],
        "supportedModes": ["review", "read-only"],
        "safeForWrite": False,
        "safeForReview": True,
        "description": "Represents the read-oriented review workflow and scripted review fallback.",
        "status": "planned",
    },
    "fallback": {
        "displayName": "Fallback Agent / ScriptedMock",
        "avatarInitials": "FB",
        "capabilityTags": ["demo recovery", "scripted fallback", "real file changes"],
        "supportedRoles": ["fallback"],
        "supportedTargets": ["demo-frontend"],
        "supportedModes": ["fallback", "scheduled-task"],
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
    return AgentProfile(
        id=agent.id,
        display_name=str(metadata.get("displayName") or agent.name),
        avatar_initials=str(metadata.get("avatarInitials") or agent.role[:2].upper()),
        role=agent.role,
        adapter_type=assignment.adapter_type,
        provider_id=assignment.provider_id,
        capability_tags=list(metadata.get("capabilityTags") or []),
        supported_roles=list(metadata.get("supportedRoles") or [agent.role]),
        supported_targets=list(metadata.get("supportedTargets") or []),
        supported_modes=list(metadata.get("supportedModes") or []),
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
