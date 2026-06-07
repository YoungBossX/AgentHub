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
    compatibility: "AgentCompatibility"
    description: str


@dataclass(frozen=True)
class AgentCompatibility:
    compatible: bool
    reasons: list[str]
    warnings: list[str]
    role: str | None = None
    target_id: str | None = None
    mode: str | None = None
    required_capabilities: list[str] | None = None


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
    compatibility = check_agent_compatibility(
        profile=profile,
        provider=provider,
        role=profile.role,
        target_id=None,
        mode=profile.supported_modes[0] if profile.supported_modes else None,
        required_capabilities=[],
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
        compatibility=compatibility,
        description=profile.description,
    )


def check_agent_compatibility(
    *,
    profile: AgentProfile,
    provider: ProviderConfig | None,
    role: str,
    target_id: str | None,
    mode: str | None,
    required_capabilities: list[str],
) -> AgentCompatibility:
    reasons: list[str] = []
    warnings: list[str] = []
    if provider is None:
        reasons.append(f"provider `{profile.provider_id}` is unavailable")
    elif not provider.available:
        reasons.append(f"provider `{provider.provider_id}` is unavailable")
    elif provider.adapter_type != profile.adapter_type:
        reasons.append(
            f"adapter `{profile.adapter_type}` does not match provider `{provider.adapter_type}`"
        )

    if role not in profile.supported_roles and role != profile.role:
        reasons.append(f"role `{role}` is not supported by profile `{profile.id}`")
    if mode and mode not in profile.supported_modes:
        reasons.append(f"mode `{mode}` is not supported by profile `{profile.id}`")
    if provider is not None and mode and mode not in provider.supported_modes:
        reasons.append(f"mode `{mode}` is not supported by provider `{provider.provider_id}`")
    if target_id and not _target_supported(profile.supported_targets, target_id):
        reasons.append(f"target `{target_id}` is not supported by profile `{profile.id}`")

    missing_capabilities = [
        capability
        for capability in required_capabilities
        if capability not in profile.capability_tags
    ]
    if missing_capabilities:
        reasons.append(f"capability missing: {', '.join(missing_capabilities)}")

    requires_write = role in {"frontend", "backend"} or "code_write" in required_capabilities
    requires_review = role in {"planner", "review", "qa"} or "code_review" in required_capabilities
    if requires_write and not profile.safe_for_write:
        reasons.append("profile is not write-safe")
    if requires_review and not profile.safe_for_review:
        warnings.append("profile is not review-safe")
    if profile.status == "draft_only":
        reasons.append("draft profile is disabled until validated")

    return AgentCompatibility(
        compatible=not reasons,
        reasons=reasons,
        warnings=warnings,
        role=role,
        target_id=target_id,
        mode=mode,
        required_capabilities=required_capabilities,
    )


def _target_supported(supported_targets: list[str], target_id: str) -> bool:
    return (
        target_id in supported_targets
        or "external" in supported_targets
        or (target_id.startswith("external-frontend") and "external-frontend" in supported_targets)
        or (target_id.startswith("external-backend") and "external-backend" in supported_targets)
    )
