from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session as DbSession

from app.agent_directory import (
    AgentCompatibility,
    AgentDirectoryEntry,
    build_agent_directory,
    check_agent_compatibility,
)
from app.agent_profile_drafts import (
    AgentProfileDraftError,
    AgentProfileDraftInput,
    create_agent_profile_draft,
    list_agent_profile_drafts,
)
from app.agent_profiles import AgentProfile, list_agent_profile_registry, profile_for_agent
from app.agent_runtime_config import (
    RuntimeConfigSnapshot,
    RuntimeConfigValidationResult,
    RuntimeRoleConfig,
    get_effective_runtime_config,
    runtime_role_availability,
    upsert_runtime_config,
    validate_runtime_config,
)
from app.dependencies import get_db
from app.memory_store import (
    MemoryFilter,
    MemoryStoreError,
    list_memory_items,
    memory_agent_roles,
    memory_target_ids,
    transition_memory_item,
)
from app.models import Agent, MemoryItem
from app.provider_configs import ProviderConfig, list_provider_configs
from app.provider_health import ProviderHealthCheckResult, check_runtime_role_provider
from app.repositories import get_enabled_agents, get_workspace
from app.routes.registries import provider_config_response
from app.schemas import (
    AgentContactResponse,
    AgentCompatibilityRequest,
    AgentCompatibilityResponse,
    AgentDirectoryEntryResponse,
    AgentDirectoryResponse,
    AgentProfileDraftCreateRequest,
    AgentProfileResponse,
    MemoryItemResponse,
    MemoryItemStatusUpdateRequest,
    RuntimeConfigResponse,
    RuntimeConfigUpdateRequest,
    RuntimeConfigValidationResponse,
    RuntimeProviderCheckRequest,
    RuntimeProviderCheckResponse,
    RuntimeRoleConfigResponse,
)


router = APIRouter()


VIRTUAL_AGENT_CONTACTS: tuple[AgentContactResponse, ...] = (
    AgentContactResponse(
        id="virtual-review-agent",
        displayName="Review Agent",
        avatarInitials="RV",
        role="review",
        adapterType="claude_code",
        providerId="local-claude-code-cli",
        capabilityTags=["planned", "read-only", "non-blocking review"],
        supportedTargets=["demo-frontend", "demo-backend", "external"],
        supportedModes=["review", "read_only"],
        status="planned",
        safeForWrite=False,
        safeForReview=True,
        description="P5 placeholder for the future non-blocking review workflow.",
        contactType="placeholder",
    ),
    AgentContactResponse(
        id="virtual-fallback-agent",
        displayName="Fallback Agent / ScriptedMock",
        avatarInitials="FB",
        role="fallback",
        adapterType="scripted_mock",
        providerId="local-scripted-mock",
        capabilityTags=["demo recovery", "scripted fallback", "real file changes"],
        supportedTargets=["demo-frontend"],
        supportedModes=["frontend"],
        status="available",
        safeForWrite=True,
        safeForReview=False,
        description="Documents the preserved ScriptedMockAdapter reliability path.",
        contactType="service",
    ),
)

def agent_contact_response(agent: Agent) -> AgentContactResponse:
    profile = profile_for_agent(agent)
    return AgentContactResponse(
        id=profile.id,
        displayName=profile.display_name,
        avatarInitials=profile.avatar_initials,
        role=profile.role,
        adapterType=profile.adapter_type,
        providerId=profile.provider_id,
        capabilityTags=profile.capability_tags,
        supportedTargets=profile.supported_targets,
        supportedModes=profile.supported_modes,
        status=profile.status,
        safeForWrite=profile.safe_for_write,
        safeForReview=profile.safe_for_review,
        description=profile.description,
        contactType="agent",
    )


def agent_profile_response(profile: AgentProfile) -> AgentProfileResponse:
    return AgentProfileResponse(
        id=profile.id,
        displayName=profile.display_name,
        avatarInitials=profile.avatar_initials,
        role=profile.role,
        adapterType=profile.adapter_type,
        providerId=profile.provider_id,
        capabilityTags=profile.capability_tags,
        supportedRoles=profile.supported_roles,
        supportedTargets=profile.supported_targets,
        supportedModes=profile.supported_modes,
        safeForWrite=profile.safe_for_write,
        safeForReview=profile.safe_for_review,
        description=profile.description,
        status=profile.status,
    )


def draft_input_from_request(request: AgentProfileDraftCreateRequest) -> AgentProfileDraftInput:
    return AgentProfileDraftInput(
        display_name=request.display_name,
        avatar_initials=request.avatar_initials,
        role=request.role,
        adapter_type=request.adapter_type,
        provider_id=request.provider_id,
        capability_tags=request.capability_tags,
        supported_targets=request.supported_targets,
        supported_modes=request.supported_modes,
        safe_for_write=request.safe_for_write,
        safe_for_review=request.safe_for_review,
        description=request.description,
        status=request.status,
        shell_commands=request.shell_commands,
        tool_permissions=request.tool_permissions,
        unrestricted_filesystem_access=request.unrestricted_filesystem_access,
    )


def agent_directory_entry_response(entry: AgentDirectoryEntry) -> AgentDirectoryEntryResponse:
    return AgentDirectoryEntryResponse(
        id=entry.id,
        entryType=entry.entry_type,
        displayName=entry.display_name,
        avatarInitials=entry.avatar_initials,
        role=entry.role,
        agentProfileId=entry.agent_profile_id,
        providerId=entry.provider_id,
        adapterType=entry.adapter_type,
        capabilityTags=entry.capability_tags,
        supportedTargets=entry.supported_targets,
        supportedModes=entry.supported_modes,
        safeForWrite=entry.safe_for_write,
        safeForReview=entry.safe_for_review,
        status=entry.status,
        authStatus=entry.auth_status,
        available=entry.available,
        runtimeSelectedForRoles=entry.runtime_selected_for_roles,
        compatibility=agent_compatibility_response(entry.compatibility),
        description=entry.description,
    )


def agent_compatibility_response(
    compatibility: AgentCompatibility,
) -> AgentCompatibilityResponse:
    return AgentCompatibilityResponse(
        compatible=compatibility.compatible,
        reasons=compatibility.reasons,
        warnings=compatibility.warnings,
        role=compatibility.role,
        targetId=compatibility.target_id,
        mode=compatibility.mode,
        requiredCapabilities=compatibility.required_capabilities or [],
    )


def agent_directory_response(
    workspace_id: str,
    *,
    profiles: list[AgentProfile],
    providers: list[ProviderConfig],
    runtime_config: RuntimeConfigSnapshot,
) -> AgentDirectoryResponse:
    directory = build_agent_directory(
        workspace_id=workspace_id,
        profiles=profiles,
        providers=providers,
        runtime_config=runtime_config,
    )
    return AgentDirectoryResponse(
        workspaceId=directory.workspace_id,
        entries=[agent_directory_entry_response(entry) for entry in directory.entries],
    )


def runtime_role_config_response(role_config: RuntimeRoleConfig) -> RuntimeRoleConfigResponse:
    return RuntimeRoleConfigResponse(
        role=role_config.role,
        agentProfileId=role_config.agent_profile_id,
        providerId=role_config.provider_id,
        adapterType=role_config.adapter_type,
        mode=role_config.mode,
        enabled=role_config.enabled,
        fallbackPolicy=role_config.fallback_policy,
        providerPresetId=role_config.provider_preset_id,
        protocol=role_config.protocol,
        model=role_config.model,
        baseUrl=role_config.base_url,
        timeoutSeconds=role_config.timeout_seconds,
        apiKeyEnv=role_config.api_key_env,
        availability=runtime_role_availability(role_config),
    )


def runtime_config_validation_response(
    validation: RuntimeConfigValidationResult,
) -> RuntimeConfigValidationResponse:
    return RuntimeConfigValidationResponse(
        valid=validation.valid,
        errors=validation.errors,
        warnings=validation.warnings,
    )


def runtime_provider_check_response(
    result: ProviderHealthCheckResult,
) -> RuntimeProviderCheckResponse:
    return RuntimeProviderCheckResponse(
        role=result.role,
        providerId=result.provider_id,
        adapterType=result.adapter_type,
        authStatus=result.auth_status,
        availability=result.availability,
        available=result.available,
        message=result.message,
    )


def runtime_role_config_from_request(
    role: str,
    request: Any,
) -> RuntimeRoleConfig:
    return RuntimeRoleConfig(
        role=role,
        agent_profile_id=request.agent_profile_id,
        provider_id=request.provider_id,
        adapter_type=request.adapter_type,
        mode=request.mode,
        enabled=request.enabled,
        fallback_policy=request.fallback_policy,
        provider_preset_id=request.provider_preset_id,
        protocol=request.protocol,
        model=request.model,
        base_url=request.base_url,
        timeout_seconds=request.timeout_seconds,
        api_key_env=request.api_key_env,
    )


def runtime_config_response(
    snapshot: RuntimeConfigSnapshot,
    *,
    profiles: list[AgentProfile],
    providers: list[ProviderConfig],
) -> RuntimeConfigResponse:
    validation = validate_runtime_config(
        snapshot.roles,
        profiles=profiles,
        providers=providers,
    )
    return RuntimeConfigResponse(
        workspaceId=snapshot.workspace_id,
        configSource=snapshot.config_source,
        roles={
            role: runtime_role_config_response(role_config)
            for role, role_config in snapshot.roles.items()
        },
        availableProfiles=[agent_profile_response(profile) for profile in profiles],
        availableProviders=[provider_config_response(provider) for provider in providers],
        validation=runtime_config_validation_response(validation),
    )


def memory_item_response(item: MemoryItem) -> MemoryItemResponse:
    compiled = item.status == "active"
    return MemoryItemResponse(
        id=item.id,
        workspaceId=item.workspace_id,
        scope=item.scope,
        memoryType=item.memory_type,
        source=item.source,
        status=item.status,
        trustLevel=item.trust_level,
        title=item.title,
        contentMd=item.content_md,
        contentHash=item.content_hash,
        version=item.version,
        importance=item.importance,
        targetIds=memory_target_ids(item),
        agentRoles=memory_agent_roles(item),
        lastUsedAt=item.last_used_at,
        supersededBy=item.superseded_by,
        compiledToAgentsMd=compiled,
        compiledToClaudeMd=compiled,
        createdAt=item.created_at,
        updatedAt=item.updated_at,
    )


def runtime_config_profiles_for_workspace(
    db: DbSession,
    workspace_id: str,
) -> list[AgentProfile]:
    return list_agent_profile_registry(
        _ordered_enabled_agents(db),
        drafts=list_agent_profile_drafts(db, workspace_id=workspace_id),
    )


@router.get(
    "/workspaces/{workspace_id}/agents",
    response_model=list[AgentContactResponse],
)
def read_workspace_agents(
    workspace_id: str,
    db: DbSession = Depends(get_db),
) -> list[AgentContactResponse]:
    if get_workspace(db, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    agents = _ordered_enabled_agents(db)
    return [agent_contact_response(agent) for agent in agents] + list(
        VIRTUAL_AGENT_CONTACTS
    )


@router.get(
    "/workspaces/{workspace_id}/agent-profiles",
    response_model=list[AgentProfileResponse],
)
def read_workspace_agent_profiles(
    workspace_id: str,
    db: DbSession = Depends(get_db),
) -> list[AgentProfileResponse]:
    if get_workspace(db, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    return [
        agent_profile_response(profile)
        for profile in list_agent_profile_registry(
            _ordered_enabled_agents(db),
            drafts=list_agent_profile_drafts(db, workspace_id=workspace_id),
        )
    ]


@router.get(
    "/workspaces/{workspace_id}/agent-directory",
    response_model=AgentDirectoryResponse,
)
def read_workspace_agent_directory(
    workspace_id: str,
    db: DbSession = Depends(get_db),
) -> AgentDirectoryResponse:
    if get_workspace(db, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return agent_directory_response(
        workspace_id,
        profiles=runtime_config_profiles_for_workspace(db, workspace_id),
        providers=list_provider_configs(),
        runtime_config=get_effective_runtime_config(db, workspace_id),
    )


@router.post(
    "/workspaces/{workspace_id}/agent-directory/check-compatibility",
    response_model=AgentCompatibilityResponse,
)
def check_workspace_agent_directory_compatibility(
    workspace_id: str,
    request: AgentCompatibilityRequest,
    db: DbSession = Depends(get_db),
) -> AgentCompatibilityResponse:
    if get_workspace(db, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    profiles = runtime_config_profiles_for_workspace(db, workspace_id)
    providers = list_provider_configs()
    profile = next(
        (candidate for candidate in profiles if candidate.id == request.agent_profile_id),
        None,
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent profile not found")
    provider = next(
        (candidate for candidate in providers if candidate.provider_id == request.provider_id),
        None,
    )
    if request.adapter_type != profile.adapter_type:
        return agent_compatibility_response(
            AgentCompatibility(
                compatible=False,
                reasons=[
                    f"adapter `{request.adapter_type}` does not match profile `{profile.adapter_type}`"
                ],
                warnings=[],
                role=request.role,
                target_id=request.target_id,
                mode=request.mode,
                required_capabilities=request.required_capabilities,
            )
        )
    return agent_compatibility_response(
        check_agent_compatibility(
            profile=profile,
            provider=provider,
            role=request.role,
            target_id=request.target_id,
            mode=request.mode,
            required_capabilities=request.required_capabilities,
        )
    )


@router.get(
    "/workspaces/{workspace_id}/runtime-config",
    response_model=RuntimeConfigResponse,
)
def read_runtime_config(
    workspace_id: str,
    db: DbSession = Depends(get_db),
) -> RuntimeConfigResponse:
    if get_workspace(db, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return runtime_config_response(
        get_effective_runtime_config(db, workspace_id),
        profiles=runtime_config_profiles_for_workspace(db, workspace_id),
        providers=list_provider_configs(),
    )


@router.post(
    "/workspaces/{workspace_id}/runtime-config/validate",
    response_model=RuntimeConfigValidationResponse,
)
def validate_runtime_config_endpoint(
    workspace_id: str,
    request: RuntimeConfigUpdateRequest,
    db: DbSession = Depends(get_db),
) -> RuntimeConfigValidationResponse:
    if get_workspace(db, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    roles = {
        role: runtime_role_config_from_request(role, role_request)
        for role, role_request in request.roles.items()
    }
    validation = validate_runtime_config(
        roles,
        profiles=runtime_config_profiles_for_workspace(db, workspace_id),
        providers=list_provider_configs(),
    )
    return runtime_config_validation_response(validation)


@router.post(
    "/workspaces/{workspace_id}/runtime-config/check-provider",
    response_model=RuntimeProviderCheckResponse,
)
def check_runtime_config_provider(
    workspace_id: str,
    request: RuntimeProviderCheckRequest,
    db: DbSession = Depends(get_db),
) -> RuntimeProviderCheckResponse:
    if get_workspace(db, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    role_config = runtime_role_config_from_request(request.role, request.role_config)
    return runtime_provider_check_response(
        check_runtime_role_provider(
            role_config,
            providers=list_provider_configs(),
        )
    )


@router.put(
    "/workspaces/{workspace_id}/runtime-config",
    response_model=RuntimeConfigResponse,
)
def update_runtime_config(
    workspace_id: str,
    request: RuntimeConfigUpdateRequest,
    db: DbSession = Depends(get_db),
) -> RuntimeConfigResponse:
    if get_workspace(db, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    roles = {
        role: runtime_role_config_from_request(role, role_request)
        for role, role_request in request.roles.items()
    }
    profiles = runtime_config_profiles_for_workspace(db, workspace_id)
    providers = list_provider_configs()
    validation = validate_runtime_config(roles, profiles=profiles, providers=providers)
    if not validation.valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": validation.errors, "warnings": validation.warnings},
        )
    upsert_runtime_config(db, workspace_id, roles)
    return runtime_config_response(
        get_effective_runtime_config(db, workspace_id),
        profiles=profiles,
        providers=providers,
    )


@router.get(
    "/workspaces/{workspace_id}/memory",
    response_model=list[MemoryItemResponse],
)
def read_workspace_memory_items(
    workspace_id: str,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    db: DbSession = Depends(get_db),
) -> list[MemoryItemResponse]:
    if get_workspace(db, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return [
        memory_item_response(item)
        for item in list_memory_items(
            db,
            MemoryFilter(workspace_id=workspace_id, status=status_filter),
        )
    ]


@router.patch(
    "/memory/{memory_item_id}/status",
    response_model=MemoryItemResponse,
)
def update_memory_item_status(
    memory_item_id: str,
    request: MemoryItemStatusUpdateRequest,
    db: DbSession = Depends(get_db),
) -> MemoryItemResponse:
    try:
        item = transition_memory_item(db, memory_item_id, request.status)
    except MemoryStoreError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return memory_item_response(item)


@router.get(
    "/workspaces/{workspace_id}/agent-profile-drafts",
    response_model=list[AgentProfileResponse],
)
def read_agent_profile_drafts(
    workspace_id: str,
    db: DbSession = Depends(get_db),
) -> list[AgentProfileResponse]:
    if get_workspace(db, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return [
        agent_profile_response(profile)
        for profile in list_agent_profile_registry(
            [],
            drafts=list_agent_profile_drafts(db, workspace_id=workspace_id),
            include_virtual=False,
        )
    ]


@router.post(
    "/workspaces/{workspace_id}/agent-profile-drafts",
    response_model=AgentProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_profile_draft(
    workspace_id: str,
    request: AgentProfileDraftCreateRequest,
    db: DbSession = Depends(get_db),
) -> AgentProfileResponse:
    if get_workspace(db, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    try:
        draft = create_agent_profile_draft(
            db,
            workspace_id=workspace_id,
            draft_input=draft_input_from_request(request),
        )
    except AgentProfileDraftError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return agent_profile_response(
        list_agent_profile_registry([], drafts=[draft], include_virtual=False)[0]
    )


def _ordered_enabled_agents(db: DbSession) -> list[Agent]:
    role_order = {
        "orchestrator": 0,
        "frontend": 1,
        "backend": 2,
        "qa": 3,
    }
    agents = sorted(
        get_enabled_agents(db),
        key=lambda agent: role_order.get(agent.role, 99),
    )
    return list(agents)
