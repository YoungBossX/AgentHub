from __future__ import annotations

from dataclasses import dataclass

from app.agent_profiles import AgentProfile
from app.agent_runtime_config import RuntimeConfigSnapshot
from app.provider_configs import ProviderConfig


@dataclass(frozen=True)
class AgentDirectoryEntry:
    id: str
    entry_type: str
    display_name: str
    avatar_initials: str
    role: str
    agent_profile_id: str
    provider_id: str
    adapter_type: str
    capability_tags: list[str]
    supported_targets: list[str]
    supported_modes: list[str]
    safe_for_write: bool
    safe_for_review: bool
    status: str
    auth_status: str
    available: bool
    runtime_selected_for_roles: list[str]
    description: str


@dataclass(frozen=True)
class AgentDirectory:
    workspace_id: str
    entries: list[AgentDirectoryEntry]


def build_agent_directory(
    *,
    workspace_id: str,
    profiles: list[AgentProfile],
    providers: list[ProviderConfig],
    runtime_config: RuntimeConfigSnapshot,
) -> AgentDirectory:
    providers_by_id = {provider.provider_id: provider for provider in providers}
    selected_roles = _runtime_selected_roles(runtime_config)
    entries = [
        _entry_for_profile(
            profile,
            provider=providers_by_id.get(profile.provider_id),
            selected_roles=selected_roles.get(profile.id, []),
        )
        for profile in profiles
    ]
    return AgentDirectory(workspace_id=workspace_id, entries=entries)


def _runtime_selected_roles(
    runtime_config: RuntimeConfigSnapshot,
) -> dict[str, list[str]]:
    selected: dict[str, list[str]] = {}
    for role, role_config in runtime_config.roles.items():
        if not role_config.enabled or not role_config.agent_profile_id:
            continue
        selected.setdefault(role_config.agent_profile_id, []).append(role)
    return selected


def _entry_for_profile(
    profile: AgentProfile,
    *,
    provider: ProviderConfig | None,
    selected_roles: list[str],
) -> AgentDirectoryEntry:
    entry_type = "draft" if profile.status == "draft_only" else "built_in"
    provider_available = provider.available if provider is not None else False
    auth_status = provider.auth_status if provider is not None else "unavailable"
    available = (
        provider_available
        and profile.status not in {"disabled", "draft_only", "rejected", "archived"}
    )
    return AgentDirectoryEntry(
        id=profile.id,
        entry_type=entry_type,
        display_name=profile.display_name,
        avatar_initials=profile.avatar_initials,
        role=profile.role,
        agent_profile_id=profile.id,
        provider_id=profile.provider_id,
        adapter_type=profile.adapter_type,
        capability_tags=profile.capability_tags,
        supported_targets=profile.supported_targets,
        supported_modes=profile.supported_modes,
        safe_for_write=profile.safe_for_write,
        safe_for_review=profile.safe_for_review,
        status=profile.status,
        auth_status=auth_status,
        available=available,
        runtime_selected_for_roles=sorted(selected_roles),
        description=profile.description,
    )
