from contextlib import asynccontextmanager
import asyncio
import json
from typing import Any, AsyncIterator, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlmodel import Session as DbSession
from sqlmodel import select

from app.adapters import AgentAdapter, AgentRunRequest
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
from app.artifact_versions import (
    ArtifactVersionError,
    StoredArtifactVersion,
    list_artifact_versions,
)
from app.artifact_workbench import (
    ArtifactVersionWorkbenchMetadata,
    ArtifactWorkbenchError,
    ArtifactWorkbenchMetadata,
    artifact_workbench_metadata_for_id,
    artifact_workbench_version_for_id,
    list_artifact_workbench_versions,
    list_session_artifact_workbench,
    save_artifact_workbench_edit,
)
from app.config import get_settings
from app.claude_code_adapter import ClaudeCodeAdapter
from app.context_pack import build_session_context_pack
from app.db import init_database
from app.dependencies import (
    get_db,
    get_deploy_service,
    get_preview_service,
)
from app.deployments import DeployError, DeployService, StoredDeploymentArtifact
from app.diffs import (
    DiffCollectionError,
    StoredDiffArtifact,
    collect_task_run_diff,
    list_task_run_diffs,
    record_diff_collection_failure,
)
from app.events import encode_sse_event, list_session_events, subscribe_session_events
from app.external_evidence import (
    ExternalEvidenceError,
    StoredCommandEvidence,
    list_task_run_command_evidence,
    record_command_evidence,
)
from app.guardrails import approve_task_run, deny_task_run
from app.instruction_builder import build_role_instruction
from app.ledger import (
    active_agents_for_ledger,
    changed_files_for_ledger,
    refresh_session_ledger,
    refresh_session_ledger_for_task_run,
)
from app.memory_store import (
    MemoryFilter,
    MemoryStoreError,
    list_memory_items,
    memory_agent_roles,
    memory_target_ids,
    transition_memory_item,
)
from app.mission_trace import build_session_mission_trace
from app.models import Agent, MemoryItem, Task, TaskRun
from app.models import Session as AgentHubSession
from app.models import SessionExecutionLedger
from app.models import TaskRunEvent
from app.models import utc_now
from app.pmo_decisions import PmoDecisionError, apply_pmo_decision, require_supported_decision_payload
from app.previews import PreviewError, PreviewService, StoredPreviewArtifact
from app.provider_configs import ProviderConfig, list_provider_configs
from app.provider_health import ProviderHealthCheckResult, check_runtime_role_provider
from app.repositories import (
    get_enabled_agents,
    get_session,
    get_workspace,
    list_session_tasks,
)
from app.reviews import (
    ReviewError,
    StoredReviewArtifact,
    create_scripted_review_for_task_run,
    list_task_run_reviews,
    record_review_collection_failure,
)
from app.run_diagnostics import (
    build_session_run_diagnostics_summary,
    build_task_run_diagnostics,
)
from app.routes.health import router as health_router
from app.routes.registries import (
    provider_config_response,
    router as registries_router,
)
from app.routes.messages import router as messages_router
from app.routes.sessions import router as sessions_router
from app.routes.targets import router as targets_router
from app.routes.workspaces import router as workspaces_router
from app.run_engine import (
    adapter_for_type,
    agent_run_request_for,
    execute_task_run,
    interrupt_supervised_task_run,
    plan_json_for_task,
    schedule_task_run_execution,
    _background_execute_task_run,
    _complete_ready_pipeline_review_tasks,
)
from app.schemas import (
    AgentContactResponse,
    AgentCompatibilityRequest,
    AgentCompatibilityResponse,
    AgentDirectoryEntryResponse,
    AgentDirectoryResponse,
    AgentProfileDraftCreateRequest,
    AgentProfileResponse,
    ApprovalDecisionRequest,
    ApprovalRequestResponse,
    CommandEvidenceCreateRequest,
    CommandEvidenceResponse,
    DeploymentCreateRequest,
    DeploymentResponse,
    DiffArtifactResponse,
    ArtifactWorkbenchArtifactResponse,
    ArtifactWorkbenchEditRequest,
    ArtifactWorkbenchSessionResponse,
    ArtifactWorkbenchVersionResponse,
    ArtifactVersionResponse,
    MemoryItemResponse,
    MemoryItemStatusUpdateRequest,
    PMOPlanDecisionRequest,
    PreviewResponse,
    ProviderConfigResponse,
    ReviewArtifactResponse,
    RuntimeConfigResponse,
    RuntimeConfigUpdateRequest,
    RuntimeConfigValidationResponse,
    RuntimeProviderCheckRequest,
    RuntimeProviderCheckResponse,
    RuntimeRoleConfigResponse,
    RunDiagnosticsResponse,
    SessionExecutionLedgerResponse,
    SessionMissionTraceResponse,
    SessionRunDiagnosticsSummaryResponse,
    SessionResponse,
    TaskResponse,
    TaskRunResponse,
)
from app.task_runs import (
    TaskRunLifecycleError,
    adapter_type_for_run,
    create_task_run,
    interrupt_task_run,
    list_task_runs,
    metrics_for_run,
    retry_task_run,
    retry_with_scripted_mock,
    transition_task_run,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_database(seed=True)
    yield


settings = get_settings()

LOCAL_FRONTEND_ORIGINS = {
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    settings.frontend_origin,
}

app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(LOCAL_FRONTEND_ORIGINS),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(registries_router)
app.include_router(messages_router)
app.include_router(sessions_router)
app.include_router(targets_router)
app.include_router(workspaces_router)


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


@app.get(
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


@app.get(
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


@app.get(
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


@app.post(
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


@app.get(
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


@app.post(
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


@app.post(
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


@app.put(
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


@app.get(
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


@app.patch(
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


@app.get(
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


@app.post(
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


def ledger_response(
    ledger: SessionExecutionLedger,
) -> SessionExecutionLedgerResponse:
    return SessionExecutionLedgerResponse(
        id=ledger.id,
        sessionId=ledger.session_id,
        currentGoal=ledger.current_goal,
        activeAgents=active_agents_for_ledger(ledger),
        latestTaskId=ledger.latest_task_id,
        latestTaskRunId=ledger.latest_task_run_id,
        latestDiffArtifactId=ledger.latest_diff_artifact_id,
        latestChangedFiles=changed_files_for_ledger(ledger),
        latestPreviewId=ledger.latest_preview_id,
        latestPreviewUrl=ledger.latest_preview_url,
        latestPreviewHealth=ledger.latest_preview_health,
        latestDeploymentId=ledger.latest_deployment_id,
        latestDeploymentProvider=ledger.latest_deployment_provider,
        latestDeploymentStatus=ledger.latest_deployment_status,
        lastSuccessfulAdapter=ledger.last_successful_adapter,
        summaryMd=ledger.summary_md,
        updatedAt=ledger.updated_at,
    )


@app.get(
    "/sessions/{session_id}/ledger",
    response_model=SessionExecutionLedgerResponse,
)
def read_session_execution_ledger(
    session_id: str,
    db: DbSession = Depends(get_db),
) -> SessionExecutionLedgerResponse:
    if get_session(db, session_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return ledger_response(refresh_session_ledger(db, session_id))


@app.get(
    "/sessions/{session_id}/mission-trace",
    response_model=SessionMissionTraceResponse,
)
def read_session_mission_trace(
    session_id: str,
    db: DbSession = Depends(get_db),
) -> SessionMissionTraceResponse:
    if get_session(db, session_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return build_session_mission_trace(db, session_id)


@app.get(
    "/sessions/{session_id}/run-diagnostics-summary",
    response_model=SessionRunDiagnosticsSummaryResponse,
)
def read_session_run_diagnostics_summary(
    session_id: str,
    db: DbSession = Depends(get_db),
) -> SessionRunDiagnosticsSummaryResponse:
    if get_session(db, session_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return build_session_run_diagnostics_summary(db, session_id)


def task_run_response(db: DbSession, task_run: TaskRun) -> TaskRunResponse:
    from app.preview_deploy_jobs import job_diagnostics_for_task_run
    from app.session_queue import queue_diagnostics_for_task_run
    from app.target_locks import lock_diagnostics_for_task_run

    task = db.get(Task, task_run.task_id)
    metrics = metrics_for_run(task_run)
    return TaskRunResponse(
        id=task_run.id,
        taskId=task_run.task_id,
        sessionId=task.session_id if task is not None else "",
        agentId=task_run.agent_id,
        adapterType=adapter_type_for_run(db, task_run),
        adapterRunId=task_run.adapter_run_id,
        state=task_run.state,
        startedAt=task_run.started_at,
        endedAt=task_run.ended_at,
        runnerId=task_run.runner_id,
        lastHeartbeatAt=task_run.last_heartbeat_at,
        leaseExpiresAt=task_run.lease_expires_at,
        staleDetectedAt=task_run.stale_detected_at,
        staleReason=task_run.stale_reason,
        worktreePath=task_run.worktree_path,
        baseRef=task_run.base_ref,
        headRef=task_run.head_ref,
        errorCode=task_run.error_code,
        errorMessage=task_run.error_message,
        metricsJson=metrics,
        providerAssignment=metrics.get("providerAssignment"),
        runtimeConfigResolution=metrics.get("runtimeConfigResolution"),
        memorySnapshot=metrics.get("memorySnapshot"),
        sessionQueue=queue_diagnostics_for_task_run(db, task_run.id),
        targetLock=lock_diagnostics_for_task_run(db, task_run.id),
        previewDeployJobs=job_diagnostics_for_task_run(db, task_run.id),
        approvalRequest=latest_approval_request(db, task_run),
        createdAt=task_run.created_at,
        updatedAt=task_run.updated_at,
    )


def latest_approval_request(
    db: DbSession,
    task_run: TaskRun,
) -> Optional[ApprovalRequestResponse]:
    if task_run.state != "waiting_approval":
        return None

    event = db.exec(
        select(TaskRunEvent)
        .where(TaskRunEvent.task_run_id == task_run.id)
        .where(TaskRunEvent.event_type == "approval.requested")
        .order_by(TaskRunEvent.sequence.desc())
    ).first()
    if event is None:
        return None

    try:
        return ApprovalRequestResponse.model_validate(json.loads(event.payload_json))
    except (json.JSONDecodeError, ValueError):
        return None


def diff_artifact_response(diff_artifact: StoredDiffArtifact) -> DiffArtifactResponse:
    return DiffArtifactResponse(
        id=diff_artifact.id,
        artifactId=diff_artifact.artifact_id,
        taskRunId=diff_artifact.task_run_id,
        artifactType=diff_artifact.artifact_type,
        title=diff_artifact.title,
        status=diff_artifact.status,
        baseRef=diff_artifact.base_ref,
        headRef=diff_artifact.head_ref,
        patchText=diff_artifact.patch_text,
        changedFiles=diff_artifact.changed_files,
        stats=diff_artifact.stats,
    )


def artifact_version_response(version: StoredArtifactVersion) -> ArtifactVersionResponse:
    return ArtifactVersionResponse(
        id=version.id,
        artifactId=version.artifact_id,
        version=version.version,
        sourceTaskRunId=version.source_task_run_id,
        parentArtifactId=version.parent_artifact_id,
        gitBaseRef=version.git_base_ref,
        gitHeadRef=version.git_head_ref,
        changedFiles=version.changed_files,
        summary=version.summary,
        createdAt=version.created_at,
    )


def artifact_workbench_version_response(
    version: ArtifactVersionWorkbenchMetadata,
) -> ArtifactWorkbenchVersionResponse:
    return ArtifactWorkbenchVersionResponse(
        id=version.id,
        artifactId=version.artifact_id,
        version=version.version,
        parentVersionId=version.parent_version_id,
        sourceTaskRunId=version.source_task_run_id,
        parentArtifactId=version.parent_artifact_id,
        gitBaseRef=version.git_base_ref,
        gitHeadRef=version.git_head_ref,
        changedFiles=version.changed_files,
        summary=version.summary,
        contentMd=version.content_md,
        contentHash=version.content_hash,
        editorSource=version.editor_source,
        createdAt=version.created_at,
    )


def artifact_workbench_response(
    metadata: ArtifactWorkbenchMetadata,
) -> ArtifactWorkbenchArtifactResponse:
    return ArtifactWorkbenchArtifactResponse(
        artifactId=metadata.artifact_id,
        taskRunId=metadata.task_run_id,
        artifactType=metadata.artifact_type,
        title=metadata.title,
        status=metadata.status,
        version=metadata.version,
        rendererKind=metadata.renderer_kind,
        editable=metadata.editable,
        contentHash=metadata.content_hash,
        safeMeta=metadata.safe_meta,
        versions=[
            artifact_workbench_version_response(version)
            for version in metadata.versions
        ],
        createdAt=metadata.created_at,
        updatedAt=metadata.updated_at,
    )


def review_response(review: StoredReviewArtifact) -> ReviewArtifactResponse:
    return ReviewArtifactResponse(
        id=review.id,
        artifactId=review.artifact_id,
        taskRunId=review.task_run_id,
        reviewedDiffArtifactId=review.reviewed_diff_artifact_id,
        artifactType=review.artifact_type,
        title=review.title,
        status=review.status,
        riskLevel=review.risk_level,
        summary=review.summary,
        filesReviewed=review.files_reviewed,
        findings=review.findings,
        suggestedChanges=review.suggested_changes,
        adapterType=review.adapter_type,
    )


def preview_response(preview: StoredPreviewArtifact) -> PreviewResponse:
    return PreviewResponse(
        id=preview.id,
        artifactId=preview.artifact_id,
        taskRunId=preview.task_run_id,
        artifactType=preview.artifact_type,
        title=preview.title,
        status=preview.status,
        port=preview.port,
        url=preview.url,
        command=preview.command,
        processId=preview.process_id,
        healthStatus=preview.health_status,
        statusReason=preview.status_reason,
        expiresAt=preview.expires_at,
        lastCheckedAt=preview.last_checked_at,
    )


def deployment_response(deployment: StoredDeploymentArtifact) -> DeploymentResponse:
    return DeploymentResponse(
        id=deployment.id,
        artifactId=deployment.artifact_id,
        taskRunId=deployment.task_run_id,
        artifactType=deployment.artifact_type,
        title=deployment.title,
        status=deployment.status,
        provider=deployment.provider,
        environment=deployment.environment,
        commitSha=deployment.commit_sha,
        url=deployment.url,
        deployLogUri=deployment.deploy_log_uri,
        providerType=deployment.provider_type,
        targetId=deployment.target_id,
        sourcePreviewId=deployment.source_preview_id,
        sourceDiffArtifactId=deployment.source_diff_artifact_id,
        sourceReviewArtifactId=deployment.source_review_artifact_id,
        logs=list(deployment.logs),
        statusHistory=list(deployment.status_history),
        createdAt=deployment.created_at,
        updatedAt=deployment.updated_at,
    )


def command_evidence_response(evidence: StoredCommandEvidence) -> CommandEvidenceResponse:
    return CommandEvidenceResponse(
        id=evidence.id,
        artifactId=evidence.artifact_id,
        taskRunId=evidence.task_run_id,
        artifactType=evidence.artifact_type,
        title=evidence.title,
        status=evidence.status,
        commandType=evidence.command_type,
        command=evidence.command,
        exitCode=evidence.exit_code,
        stdout=evidence.stdout,
        stderr=evidence.stderr,
        targetId=evidence.target_id,
        createdAt=evidence.created_at,
    )


def task_response(db: DbSession, task: Task) -> TaskResponse:
    assigned_role = None
    if task.assigned_agent_id is not None:
        agent = db.get(Agent, task.assigned_agent_id)
        assigned_role = agent.role if agent is not None else None
    plan = plan_json_for_task(task)
    dependency_ids = json.loads(task.depends_on_task_ids)

    return TaskResponse(
        id=task.id,
        sessionId=task.session_id,
        createdByMessageId=task.created_by_message_id,
        title=task.title,
        intentType=task.intent_type,
        status=task.status,
        priority=task.priority,
        planJson=plan,
        planReviewMetadata=plan_review_metadata_for_task(
            task,
            plan=plan,
            dependency_ids=dependency_ids,
        ),
        dependsOnTaskIds=dependency_ids,
        assignedAgentId=task.assigned_agent_id,
        assignedAgentRole=assigned_role,
        taskRuns=[task_run_response(db, task_run) for task_run in list_task_runs(db, task.id)],
        createdAt=task.created_at,
        updatedAt=task.updated_at,
    )


def plan_review_metadata_for_task(
    task: Task,
    *,
    plan: dict[str, Any],
    dependency_ids: list[str],
) -> dict[str, Any]:
    plan_draft = _dict_value(plan.get("planDraft"))
    task_graph = _dict_value(plan.get("taskGraph"))
    return {
        "plannerMode": _first_string(
            plan.get("plannerMode"),
            plan.get("planner"),
            plan_draft.get("plannerMode"),
            plan_draft.get("planner"),
        ),
        "rationale": _first_string(plan.get("rationale"), plan_draft.get("rationale")),
        "assignedRole": _first_string(plan.get("assignedRole")),
        "targetId": _first_string(
            plan.get("targetId"),
            plan.get("frontendTargetId"),
            plan.get("backendTargetId"),
            plan_draft.get("targetId"),
        ),
        "dependencies": dependency_ids,
        "plannedFiles": _string_list(
            plan.get("plannedFiles"),
            plan.get("files"),
            plan_draft.get("plannedFiles"),
        ),
        "acceptanceCriteria": _string_list(
            plan.get("acceptanceCriteria"),
            plan_draft.get("acceptanceCriteria"),
        ),
        "validationExpectations": _string_list(
            plan.get("validationExpectations"),
            plan_draft.get("validationExpectations"),
        ),
        "taskBreakdown": _task_breakdown(task_graph.get("tasks")),
        "readOnly": True,
        "sourceTaskId": task.id,
    }


def _task_breakdown(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "title": _first_string(item.get("title"), item.get("name")),
                "role": _first_string(item.get("role"), item.get("assignedRole")),
                "targetId": _first_string(item.get("targetId")),
                "dependsOn": _string_list(item.get("dependsOn")),
                "plannedFiles": _string_list(item.get("plannedFiles"), item.get("files")),
            }
        )
    return items


def _dict_value(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_string(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _string_list(*values: object) -> list[str]:
    for value in values:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, str) and item]
    return []


@app.get("/sessions/{session_id}/tasks", response_model=list[TaskResponse])
def read_session_tasks(
    session_id: str,
    db: DbSession = Depends(get_db),
) -> list[TaskResponse]:
    if get_session(db, session_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return [task_response(db, task) for task in list_session_tasks(db, session_id)]


@app.post("/tasks/{task_id}/plan-decision/approve", response_model=TaskResponse)
def approve_task_plan_decision(
    task_id: str,
    request: PMOPlanDecisionRequest,
    db: DbSession = Depends(get_db),
) -> TaskResponse:
    return _apply_task_plan_decision(
        db,
        task_id,
        state="approved",
        request=request,
    )


@app.post("/tasks/{task_id}/plan-decision/reject", response_model=TaskResponse)
def reject_task_plan_decision(
    task_id: str,
    request: PMOPlanDecisionRequest,
    db: DbSession = Depends(get_db),
) -> TaskResponse:
    return _apply_task_plan_decision(
        db,
        task_id,
        state="rejected",
        request=request,
    )


@app.post("/tasks/{task_id}/plan-decision/clarification", response_model=TaskResponse)
def request_task_plan_clarification(
    task_id: str,
    request: PMOPlanDecisionRequest,
    db: DbSession = Depends(get_db),
) -> TaskResponse:
    return _apply_task_plan_decision(
        db,
        task_id,
        state="clarification_needed",
        request=request,
    )


def _apply_task_plan_decision(
    db: DbSession,
    task_id: str,
    *,
    state: str,
    request: PMOPlanDecisionRequest,
) -> TaskResponse:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    try:
        payload = request.model_dump(exclude_none=True)
        require_supported_decision_payload(payload)
        plan = plan_json_for_task(task)
        task.plan_json = json.dumps(
            apply_pmo_decision(
                plan,
                state=state,
                actor="user",
                reason=request.reason,
            ),
            separators=(",", ":"),
        )
    except PmoDecisionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if state in {"rejected", "clarification_needed"}:
        task.status = "blocked"
    task.updated_at = utc_now()
    db.add(task)
    db.commit()
    db.refresh(task)
    refresh_session_ledger(db, task.session_id)
    return task_response(db, task)


@app.post(
    "/tasks/{task_id}/runs",
    response_model=TaskRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task_run_for_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    db: DbSession = Depends(get_db),
) -> TaskRunResponse:
    try:
        task_run = create_task_run(db, task_id)
    except TaskRunLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    schedule_task_run_execution(background_tasks)
    return task_run_response(db, task_run)


@app.post(
    "/tasks/{task_id}/runs/force-codex-failure",
    response_model=TaskRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def force_codex_failure_for_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    db: DbSession = Depends(get_db),
) -> TaskRunResponse:
    try:
        task_run = create_task_run(
            db,
            task_id,
            adapter_type="codex",
            retry_metadata={"forceFailure": True},
        )
    except TaskRunLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    schedule_task_run_execution(background_tasks)
    return task_run_response(db, task_run)


@app.get(
    "/task-runs/{task_run_id}/diagnostics",
    response_model=RunDiagnosticsResponse,
)
def read_task_run_diagnostics(
    task_run_id: str,
    db: DbSession = Depends(get_db),
) -> RunDiagnosticsResponse:
    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TaskRun not found")
    return build_task_run_diagnostics(db, task_run)


@app.post("/task-runs/{task_run_id}/interrupt", response_model=TaskRunResponse)
def interrupt_existing_task_run(
    task_run_id: str,
    db: DbSession = Depends(get_db),
) -> TaskRunResponse:
    try:
        asyncio.run(interrupt_supervised_task_run(task_run_id))
        task_run = interrupt_task_run(db, task_run_id)
    except TaskRunLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return task_run_response(db, task_run)


@app.post(
    "/task-runs/{task_run_id}/retry",
    response_model=TaskRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def retry_existing_task_run(
    task_run_id: str,
    background_tasks: BackgroundTasks,
    db: DbSession = Depends(get_db),
) -> TaskRunResponse:
    try:
        task_run = retry_task_run(db, task_run_id)
    except TaskRunLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    schedule_task_run_execution(background_tasks)
    return task_run_response(db, task_run)


@app.post(
    "/task-runs/{task_run_id}/retry-with-fallback",
    response_model=TaskRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def retry_existing_task_run_with_fallback(
    task_run_id: str,
    background_tasks: BackgroundTasks,
    db: DbSession = Depends(get_db),
) -> TaskRunResponse:
    try:
        task_run = retry_with_scripted_mock(db, task_run_id)
    except TaskRunLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    schedule_task_run_execution(background_tasks)
    return task_run_response(db, task_run)


@app.post("/task-runs/{task_run_id}/approve", response_model=TaskRunResponse)
def approve_existing_task_run(
    task_run_id: str,
    db: DbSession = Depends(get_db),
) -> TaskRunResponse:
    try:
        approve_task_run(db, task_run_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TaskRun not found")
    return task_run_response(db, task_run)


@app.post("/task-runs/{task_run_id}/deny", response_model=TaskRunResponse)
def deny_existing_task_run(
    task_run_id: str,
    request: ApprovalDecisionRequest,
    db: DbSession = Depends(get_db),
) -> TaskRunResponse:
    try:
        deny_task_run(
            db,
            task_run_id,
            reason=request.reason or "User denied approval request.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TaskRun not found")
    return task_run_response(db, task_run)


@app.post(
    "/task-runs/{task_run_id}/diff",
    response_model=DiffArtifactResponse,
    status_code=status.HTTP_201_CREATED,
)
def collect_diff_for_task_run(
    task_run_id: str,
    db: DbSession = Depends(get_db),
) -> DiffArtifactResponse:
    if db.get(TaskRun, task_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TaskRun not found")
    try:
        diff_artifact = collect_task_run_diff(db, task_run_id)
        create_scripted_review_for_task_run(db, task_run_id)
        refresh_session_ledger_for_task_run(db, task_run_id)
    except DiffCollectionError as exc:
        record_diff_collection_failure(db, task_run_id, exc)
        record_review_collection_failure(db, task_run_id, ReviewError("No diff artifact found for review."), skipped=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ReviewError as exc:
        record_review_collection_failure(db, task_run_id, exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return diff_artifact_response(diff_artifact)


@app.get("/task-runs/{task_run_id}/diffs", response_model=list[DiffArtifactResponse])
def read_task_run_diffs(
    task_run_id: str,
    db: DbSession = Depends(get_db),
) -> list[DiffArtifactResponse]:
    if db.get(TaskRun, task_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TaskRun not found")
    return [diff_artifact_response(diff) for diff in list_task_run_diffs(db, task_run_id)]


@app.get(
    "/sessions/{session_id}/artifact-workbench",
    response_model=ArtifactWorkbenchSessionResponse,
)
def read_session_artifact_workbench(
    session_id: str,
    db: DbSession = Depends(get_db),
) -> ArtifactWorkbenchSessionResponse:
    if db.get(AgentHubSession, session_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    try:
        artifacts = list_session_artifact_workbench(db, session_id)
    except ArtifactWorkbenchError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ArtifactWorkbenchSessionResponse(
        sessionId=session_id,
        artifacts=[artifact_workbench_response(artifact) for artifact in artifacts],
    )


@app.get(
    "/artifacts/{artifact_id}/workbench",
    response_model=ArtifactWorkbenchArtifactResponse,
)
def read_artifact_workbench(
    artifact_id: str,
    db: DbSession = Depends(get_db),
) -> ArtifactWorkbenchArtifactResponse:
    try:
        metadata = artifact_workbench_metadata_for_id(db, artifact_id)
    except ArtifactWorkbenchError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return artifact_workbench_response(metadata)


@app.get(
    "/artifacts/{artifact_id}/workbench/versions",
    response_model=list[ArtifactWorkbenchVersionResponse],
)
def read_artifact_workbench_versions(
    artifact_id: str,
    db: DbSession = Depends(get_db),
) -> list[ArtifactWorkbenchVersionResponse]:
    try:
        versions = list_artifact_workbench_versions(db, artifact_id)
        artifact = artifact_workbench_metadata_for_id(db, artifact_id)
    except ArtifactWorkbenchError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    version_metadata = {version.id: version for version in artifact.versions}
    return [
        artifact_workbench_version_response(version_metadata[version.id])
        for version in versions
        if version.id in version_metadata
    ]


@app.get(
    "/artifacts/{artifact_id}/workbench/versions/{version_id}",
    response_model=ArtifactWorkbenchVersionResponse,
)
def read_artifact_workbench_version(
    artifact_id: str,
    version_id: str,
    db: DbSession = Depends(get_db),
) -> ArtifactWorkbenchVersionResponse:
    try:
        version = artifact_workbench_version_for_id(db, artifact_id, version_id)
    except ArtifactWorkbenchError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return artifact_workbench_version_response(version)


@app.post(
    "/artifacts/{artifact_id}/workbench/edits",
    response_model=ArtifactWorkbenchVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_artifact_workbench_edit_route(
    artifact_id: str,
    request: ArtifactWorkbenchEditRequest,
    db: DbSession = Depends(get_db),
) -> ArtifactWorkbenchVersionResponse:
    try:
        version = save_artifact_workbench_edit(
            db,
            artifact_id,
            content_md=request.content_md,
            summary=request.summary,
            editor_source=request.editor_source,
        )
    except ArtifactWorkbenchError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if str(exc).startswith("Artifact not found")
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return artifact_workbench_version_response(version)


@app.get("/artifacts/{artifact_id}/versions", response_model=list[ArtifactVersionResponse])
def read_artifact_versions(
    artifact_id: str,
    db: DbSession = Depends(get_db),
) -> list[ArtifactVersionResponse]:
    try:
        versions = list_artifact_versions(db, artifact_id)
    except ArtifactVersionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [artifact_version_response(version) for version in versions]


@app.post(
    "/task-runs/{task_run_id}/review",
    response_model=ReviewArtifactResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_review_for_task_run(
    task_run_id: str,
    db: DbSession = Depends(get_db),
) -> ReviewArtifactResponse:
    if db.get(TaskRun, task_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TaskRun not found")
    try:
        review = create_scripted_review_for_task_run(db, task_run_id)
        refresh_session_ledger_for_task_run(db, task_run_id)
    except ReviewError as exc:
        record_review_collection_failure(db, task_run_id, exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return review_response(review)


@app.get("/task-runs/{task_run_id}/reviews", response_model=list[ReviewArtifactResponse])
def read_task_run_reviews(
    task_run_id: str,
    db: DbSession = Depends(get_db),
) -> list[ReviewArtifactResponse]:
    if db.get(TaskRun, task_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TaskRun not found")
    return [review_response(review) for review in list_task_run_reviews(db, task_run_id)]


@app.post(
    "/task-runs/{task_run_id}/command-evidence",
    response_model=CommandEvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_command_evidence_for_task_run(
    task_run_id: str,
    request: CommandEvidenceCreateRequest,
    db: DbSession = Depends(get_db),
) -> CommandEvidenceResponse:
    try:
        evidence = record_command_evidence(
            db,
            task_run_id,
            command_type=request.command_type,
            command=request.command,
            exit_code=request.exit_code,
            stdout=request.stdout,
            stderr=request.stderr,
            target_id=request.target_id,
        )
    except ExternalEvidenceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return command_evidence_response(evidence)


@app.get(
    "/task-runs/{task_run_id}/command-evidence",
    response_model=list[CommandEvidenceResponse],
)
def read_task_run_command_evidence(
    task_run_id: str,
    db: DbSession = Depends(get_db),
) -> list[CommandEvidenceResponse]:
    if db.get(TaskRun, task_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TaskRun not found")
    return [
        command_evidence_response(evidence)
        for evidence in list_task_run_command_evidence(db, task_run_id)
    ]


@app.post(
    "/task-runs/{task_run_id}/preview",
    response_model=PreviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_preview_for_task_run(
    task_run_id: str,
    db: DbSession = Depends(get_db),
    previews: PreviewService = Depends(get_preview_service),
) -> PreviewResponse:
    try:
        preview = previews.start_task_run_preview(db, task_run_id)
        if preview.health_status == "healthy":
            refresh_session_ledger_for_task_run(db, task_run_id)
    except PreviewError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return preview_response(preview)


@app.get("/task-runs/{task_run_id}/previews", response_model=list[PreviewResponse])
def read_task_run_previews(
    task_run_id: str,
    db: DbSession = Depends(get_db),
    previews: PreviewService = Depends(get_preview_service),
) -> list[PreviewResponse]:
    if db.get(TaskRun, task_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TaskRun not found")
    stored_previews = previews.list_task_run_previews(db, task_run_id)
    if any(preview.health_status == "healthy" for preview in stored_previews):
        refresh_session_ledger_for_task_run(db, task_run_id)
    return [
        preview_response(preview)
        for preview in stored_previews
    ]


@app.post("/previews/{preview_id}/stop", response_model=PreviewResponse)
def stop_existing_preview(
    preview_id: str,
    db: DbSession = Depends(get_db),
    previews: PreviewService = Depends(get_preview_service),
) -> PreviewResponse:
    try:
        preview = previews.stop_preview(db, preview_id)
    except PreviewError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return preview_response(preview)


@app.post(
    "/previews/{preview_id}/deploy",
    response_model=DeploymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_mock_deployment_for_preview(
    preview_id: str,
    request: DeploymentCreateRequest = DeploymentCreateRequest(),
    db: DbSession = Depends(get_db),
    deployments: DeployService = Depends(get_deploy_service),
) -> DeploymentResponse:
    try:
        deployment = deployments.create_deployment(
            db,
            preview_id,
            provider_id=request.provider_id,
            environment=request.environment,
        )
        refresh_session_ledger_for_task_run(db, deployment.task_run_id)
    except DeployError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return deployment_response(deployment)


@app.get("/task-runs/{task_run_id}/deployments", response_model=list[DeploymentResponse])
def read_task_run_deployments(
    task_run_id: str,
    db: DbSession = Depends(get_db),
    deployments: DeployService = Depends(get_deploy_service),
) -> list[DeploymentResponse]:
    if db.get(TaskRun, task_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TaskRun not found")
    return [
        deployment_response(deployment)
        for deployment in deployments.list_task_run_deployments(db, task_run_id)
    ]


@app.get("/sessions/{session_id}/events")
async def stream_session_events(
    session_id: str,
    after: int = Query(default=0, ge=0),
    stream: bool = False,
    db: DbSession = Depends(get_db),
) -> StreamingResponse:
    if get_session(db, session_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    async def event_generator() -> AsyncIterator[str]:
        for event in list_session_events(db, session_id=session_id, after_sequence=after):
            yield encode_sse_event(event)

        if stream:
            async for event in subscribe_session_events(session_id):
                if event.sequence > after:
                    yield encode_sse_event(event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )
