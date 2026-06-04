from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    service: str
    database: str


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class WorkspaceResponse(ApiModel):
    id: str
    name: str
    repo_url: str = Field(alias="repoUrl")
    root_path: str = Field(alias="rootPath")
    default_branch: str = Field(alias="defaultBranch")
    created_at: datetime = Field(alias="createdAt")


class ExternalProjectTargetCreateRequest(BaseModel):
    target_id: Optional[str] = Field(default=None, alias="targetId")
    name: str
    root_path: str = Field(alias="rootPath")
    project_type: str = Field(default="unknown", alias="projectType")
    allowed_paths: list[str] = Field(alias="allowedPaths")
    denied_paths: list[str] = Field(default_factory=list, alias="deniedPaths")
    dev_command: Optional[str] = Field(default=None, alias="devCommand")
    test_command: Optional[str] = Field(default=None, alias="testCommand")
    check_command: Optional[str] = Field(default=None, alias="checkCommand")
    build_command: Optional[str] = Field(default=None, alias="buildCommand")
    preview_command: Optional[str] = Field(default=None, alias="previewCommand")
    staging_output_dir: Optional[str] = Field(default=None, alias="stagingOutputDir")
    staging_serve_command: Optional[str] = Field(default=None, alias="stagingServeCommand")
    deploy_provider_ids: list[str] = Field(default_factory=list, alias="deployProviderIds")
    package_manager: Optional[str] = Field(default=None, alias="packageManager")
    detected_framework: Optional[str] = Field(default=None, alias="detectedFramework")

    model_config = ConfigDict(populate_by_name=True)


class ExternalProjectAnalysisRequest(BaseModel):
    root_path: str = Field(alias="rootPath")

    model_config = ConfigDict(populate_by_name=True)


class ExternalProjectAnalysisResponse(ApiModel):
    root_path: str = Field(alias="rootPath")
    project_type: str = Field(alias="projectType")
    detected_framework: str = Field(alias="detectedFramework")
    package_manager: str = Field(alias="packageManager")
    allowed_paths: list[str] = Field(alias="allowedPaths")
    denied_paths: list[str] = Field(alias="deniedPaths")
    dev_command: Optional[str] = Field(alias="devCommand")
    test_command: Optional[str] = Field(alias="testCommand")
    check_command: Optional[str] = Field(alias="checkCommand")
    build_command: Optional[str] = Field(alias="buildCommand")
    preview_command: Optional[str] = Field(alias="previewCommand")
    analysis_status: str = Field(alias="analysisStatus")
    analysis_warnings: list[str] = Field(alias="analysisWarnings")
    confidence: str


class TargetProjectResponse(ApiModel):
    target_id: str = Field(alias="targetId")
    name: str
    type: str
    root: str
    allowed_paths: list[str] = Field(alias="allowedPaths")
    denied_paths: list[str] = Field(alias="deniedPaths")
    dev_command: Optional[str] = Field(alias="devCommand")
    test_command: Optional[str] = Field(alias="testCommand")
    check_command: Optional[str] = Field(alias="checkCommand")
    build_command: Optional[str] = Field(alias="buildCommand")
    preview_command: Optional[str] = Field(alias="previewCommand")
    staging_output_dir: Optional[str] = Field(alias="stagingOutputDir")
    staging_serve_command: Optional[str] = Field(alias="stagingServeCommand")
    deploy_provider_ids: list[str] = Field(alias="deployProviderIds")
    base_url: Optional[str] = Field(alias="baseUrl")
    package_manager: Optional[str] = Field(alias="packageManager")
    detected_framework: Optional[str] = Field(alias="detectedFramework")
    project_type: Optional[str] = Field(alias="projectType")
    analysis_status: Optional[str] = Field(alias="analysisStatus")
    allowed_agents: list[str] = Field(alias="allowedAgents")
    requires_platform_mode: bool = Field(alias="requiresPlatformMode")
    requires_approval: bool = Field(alias="requiresApproval")
    related_target_ids: list[str] = Field(alias="relatedTargetIds")


class ExternalProjectTargetResponse(ApiModel):
    id: str
    workspace_id: str = Field(alias="workspaceId")
    target_id: str = Field(alias="targetId")
    name: str
    root_path: str = Field(alias="rootPath")
    project_type: str = Field(alias="projectType")
    allowed_paths: list[str] = Field(alias="allowedPaths")
    denied_paths: list[str] = Field(alias="deniedPaths")
    dev_command: Optional[str] = Field(alias="devCommand")
    test_command: Optional[str] = Field(alias="testCommand")
    check_command: Optional[str] = Field(alias="checkCommand")
    build_command: Optional[str] = Field(alias="buildCommand")
    preview_command: Optional[str] = Field(alias="previewCommand")
    staging_output_dir: Optional[str] = Field(alias="stagingOutputDir")
    staging_serve_command: Optional[str] = Field(alias="stagingServeCommand")
    deploy_provider_ids: list[str] = Field(alias="deployProviderIds")
    package_manager: Optional[str] = Field(alias="packageManager")
    detected_framework: Optional[str] = Field(alias="detectedFramework")
    analysis_status: str = Field(alias="analysisStatus")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class AgentContactResponse(ApiModel):
    id: str
    display_name: str = Field(alias="displayName")
    avatar_initials: str = Field(alias="avatarInitials")
    role: str
    adapter_type: str = Field(alias="adapterType")
    provider_id: str = Field(alias="providerId")
    capability_tags: list[str] = Field(alias="capabilityTags")
    supported_targets: list[str] = Field(alias="supportedTargets")
    supported_modes: list[str] = Field(alias="supportedModes")
    status: str
    safe_for_write: bool = Field(alias="safeForWrite")
    safe_for_review: bool = Field(alias="safeForReview")
    description: str
    contact_type: str = Field(alias="contactType")


class AgentProfileResponse(ApiModel):
    id: str
    display_name: str = Field(alias="displayName")
    avatar_initials: str = Field(alias="avatarInitials")
    role: str
    adapter_type: str = Field(alias="adapterType")
    provider_id: str = Field(alias="providerId")
    capability_tags: list[str] = Field(alias="capabilityTags")
    supported_roles: list[str] = Field(alias="supportedRoles")
    supported_targets: list[str] = Field(alias="supportedTargets")
    supported_modes: list[str] = Field(alias="supportedModes")
    safe_for_write: bool = Field(alias="safeForWrite")
    safe_for_review: bool = Field(alias="safeForReview")
    description: str
    status: str


class AgentProfileDraftCreateRequest(BaseModel):
    display_name: str = Field(alias="displayName")
    avatar_initials: Optional[str] = Field(default=None, alias="avatarInitials")
    role: str
    adapter_type: str = Field(alias="adapterType")
    provider_id: str = Field(alias="providerId")
    capability_tags: list[str] = Field(default_factory=list, alias="capabilityTags")
    supported_targets: list[str] = Field(alias="supportedTargets")
    supported_modes: list[str] = Field(default_factory=lambda: ["review"], alias="supportedModes")
    safe_for_write: bool = Field(default=False, alias="safeForWrite")
    safe_for_review: bool = Field(default=True, alias="safeForReview")
    description: str = ""
    status: str = "draft_only"
    shell_commands: list[str] = Field(default_factory=list, alias="shellCommands")
    tool_permissions: list[str] = Field(default_factory=list, alias="toolPermissions")
    unrestricted_filesystem_access: bool = Field(
        default=False,
        alias="unrestrictedFilesystemAccess",
    )

    model_config = ConfigDict(
        extra="forbid",
        hide_input_in_errors=True,
        populate_by_name=True,
    )


class ProviderConfigResponse(ApiModel):
    provider_id: str = Field(alias="providerId")
    display_name: str = Field(alias="displayName")
    adapter_type: str = Field(alias="adapterType")
    auth_status: str = Field(alias="authStatus")
    available: bool
    default_for_roles: list[str] = Field(alias="defaultForRoles")
    supported_modes: list[str] = Field(alias="supportedModes")


class RuntimeRoleConfigRequest(BaseModel):
    role: Optional[str] = None
    agent_profile_id: Optional[str] = Field(default=None, alias="agentProfileId")
    provider_id: Optional[str] = Field(default=None, alias="providerId")
    adapter_type: Optional[str] = Field(default=None, alias="adapterType")
    mode: Optional[str] = None
    enabled: bool = False
    fallback_policy: Optional[str] = Field(default=None, alias="fallbackPolicy")
    provider_preset_id: Optional[str] = Field(default=None, alias="providerPresetId")
    protocol: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = Field(default=None, alias="baseUrl")
    timeout_seconds: Optional[int] = Field(default=None, alias="timeoutSeconds")
    api_key_env: Optional[str] = Field(default=None, alias="apiKeyEnv")
    availability: Optional[str] = None
    api_key: Optional[str] = Field(default=None, alias="apiKey", exclude=True)
    authorization: Optional[str] = Field(default=None, exclude=True)
    authorization_header: Optional[str] = Field(
        default=None,
        alias="authorizationHeader",
        exclude=True,
    )

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class RuntimeConfigUpdateRequest(BaseModel):
    roles: dict[str, RuntimeRoleConfigRequest]

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class RuntimeProviderCheckRequest(BaseModel):
    role: str
    role_config: RuntimeRoleConfigRequest = Field(alias="roleConfig")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class RuntimeProviderCheckResponse(ApiModel):
    role: str
    provider_id: Optional[str] = Field(alias="providerId")
    adapter_type: Optional[str] = Field(alias="adapterType")
    auth_status: str = Field(alias="authStatus")
    availability: str
    available: bool
    message: str


class RuntimeRoleConfigResponse(ApiModel):
    role: str
    agent_profile_id: Optional[str] = Field(alias="agentProfileId")
    provider_id: Optional[str] = Field(alias="providerId")
    adapter_type: Optional[str] = Field(alias="adapterType")
    mode: Optional[str]
    enabled: bool
    fallback_policy: Optional[str] = Field(alias="fallbackPolicy")
    provider_preset_id: Optional[str] = Field(alias="providerPresetId")
    protocol: Optional[str]
    model: Optional[str]
    base_url: Optional[str] = Field(alias="baseUrl")
    timeout_seconds: Optional[int] = Field(alias="timeoutSeconds")
    api_key_env: Optional[str] = Field(alias="apiKeyEnv")
    availability: Optional[str] = None


class RuntimeConfigValidationResponse(ApiModel):
    valid: bool
    errors: list[str]
    warnings: list[str]


class RuntimeConfigResponse(ApiModel):
    workspace_id: Optional[str] = Field(alias="workspaceId")
    config_source: str = Field(alias="configSource")
    roles: dict[str, RuntimeRoleConfigResponse]
    available_profiles: list[AgentProfileResponse] = Field(alias="availableProfiles")
    available_providers: list[ProviderConfigResponse] = Field(alias="availableProviders")
    validation: RuntimeConfigValidationResponse


class SessionResponse(ApiModel):
    id: str
    workspace_id: str = Field(alias="workspaceId")
    title: str
    session_type: str = Field(alias="sessionType")
    bound_branch: str = Field(alias="boundBranch")
    worktree_path: str = Field(alias="worktreePath")
    active_frontend_target_id: Optional[str] = Field(alias="activeFrontendTargetId")
    active_backend_target_id: Optional[str] = Field(alias="activeBackendTargetId")
    memory_snapshot_id: Optional[str] = Field(default=None, alias="memorySnapshotId")
    status: str
    last_message_at: Optional[datetime] = Field(alias="lastMessageAt")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class SessionCreateRequest(BaseModel):
    title: Optional[str] = None


class SessionUpdateRequest(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None


class SessionTargetSelectionRequest(BaseModel):
    frontend_target_id: Optional[str] = Field(default=None, alias="frontendTargetId")
    backend_target_id: Optional[str] = Field(default=None, alias="backendTargetId")

    model_config = ConfigDict(populate_by_name=True)


class MessageResponse(ApiModel):
    id: str
    session_id: str = Field(alias="sessionId")
    sender_type: str = Field(alias="senderType")
    sender_id: Optional[str] = Field(alias="senderId")
    content_md: str = Field(alias="contentMd")
    message_kind: str = Field(alias="messageKind")
    parent_message_id: Optional[str] = Field(alias="parentMessageId")
    stream_state: str = Field(alias="streamState")
    created_at: datetime = Field(alias="createdAt")


class MessageCreateRequest(BaseModel):
    content_md: str = Field(alias="contentMd")
    sender_type: str = Field(default="user", alias="senderType")
    sender_id: Optional[str] = Field(default=None, alias="senderId")
    message_kind: str = Field(default="chat", alias="messageKind")
    parent_message_id: Optional[str] = Field(default=None, alias="parentMessageId")
    stream_state: str = Field(default="complete", alias="streamState")

    model_config = ConfigDict(populate_by_name=True)


class SessionExecutionLedgerResponse(ApiModel):
    id: str
    session_id: str = Field(alias="sessionId")
    current_goal: Optional[str] = Field(alias="currentGoal")
    active_agents: list[str] = Field(alias="activeAgents")
    latest_task_id: Optional[str] = Field(alias="latestTaskId")
    latest_task_run_id: Optional[str] = Field(alias="latestTaskRunId")
    latest_diff_artifact_id: Optional[str] = Field(alias="latestDiffArtifactId")
    latest_changed_files: list[str] = Field(alias="latestChangedFiles")
    latest_preview_id: Optional[str] = Field(alias="latestPreviewId")
    latest_preview_url: Optional[str] = Field(alias="latestPreviewUrl")
    latest_preview_health: Optional[str] = Field(alias="latestPreviewHealth")
    latest_deployment_id: Optional[str] = Field(alias="latestDeploymentId")
    latest_deployment_provider: Optional[str] = Field(alias="latestDeploymentProvider")
    latest_deployment_status: Optional[str] = Field(alias="latestDeploymentStatus")
    last_successful_adapter: Optional[str] = Field(alias="lastSuccessfulAdapter")
    summary_md: str = Field(alias="summaryMd")
    updated_at: datetime = Field(alias="updatedAt")


class SessionMissionTraceResponse(ApiModel):
    current_goal: Optional[str] = Field(alias="currentGoal")
    memory_snapshot: Optional[dict[str, Any]] = Field(default=None, alias="memorySnapshot")
    tasks: list[dict[str, Any]]
    task_runs: list[dict[str, Any]] = Field(alias="taskRuns")
    events: list[dict[str, Any]]
    artifacts: list[dict[str, Any]]
    blockers: list[dict[str, Any]]
    next_actions: list[dict[str, Any]] = Field(alias="nextActions")


class TaskResponse(ApiModel):
    id: str
    session_id: str = Field(alias="sessionId")
    created_by_message_id: Optional[str] = Field(alias="createdByMessageId")
    title: str
    intent_type: str = Field(alias="intentType")
    status: str
    priority: int
    plan_json: dict[str, Any] = Field(alias="planJson")
    plan_review_metadata: dict[str, Any] = Field(alias="planReviewMetadata")
    depends_on_task_ids: list[str] = Field(alias="dependsOnTaskIds")
    assigned_agent_id: Optional[str] = Field(alias="assignedAgentId")
    assigned_agent_role: Optional[str] = Field(alias="assignedAgentRole")
    task_runs: list["TaskRunResponse"] = Field(default_factory=list, alias="taskRuns")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class ApprovalRequestResponse(ApiModel):
    approval_type: str = Field(alias="approvalType")
    reason: str
    requested_action: str = Field(alias="requestedAction")
    risk_level: str = Field(alias="riskLevel")
    command: Optional[str] = None
    path: Optional[str] = None
    expires_at: Optional[str] = Field(default=None, alias="expiresAt")


class ApprovalDecisionRequest(BaseModel):
    reason: Optional[str] = None


class TaskRunResponse(ApiModel):
    id: str
    task_id: str = Field(alias="taskId")
    session_id: str = Field(alias="sessionId")
    agent_id: str = Field(alias="agentId")
    adapter_type: str = Field(alias="adapterType")
    adapter_run_id: Optional[str] = Field(alias="adapterRunId")
    state: str
    started_at: Optional[datetime] = Field(alias="startedAt")
    ended_at: Optional[datetime] = Field(alias="endedAt")
    runner_id: Optional[str] = Field(default=None, alias="runnerId")
    last_heartbeat_at: Optional[datetime] = Field(default=None, alias="lastHeartbeatAt")
    lease_expires_at: Optional[datetime] = Field(default=None, alias="leaseExpiresAt")
    stale_detected_at: Optional[datetime] = Field(default=None, alias="staleDetectedAt")
    stale_reason: Optional[str] = Field(default=None, alias="staleReason")
    worktree_path: str = Field(alias="worktreePath")
    base_ref: Optional[str] = Field(alias="baseRef")
    head_ref: Optional[str] = Field(alias="headRef")
    error_code: Optional[str] = Field(alias="errorCode")
    error_message: Optional[str] = Field(alias="errorMessage")
    metrics_json: dict[str, Any] = Field(alias="metricsJson")
    provider_assignment: Optional[dict[str, Any]] = Field(
        default=None,
        alias="providerAssignment",
    )
    runtime_config_resolution: Optional[dict[str, Any]] = Field(
        default=None,
        alias="runtimeConfigResolution",
    )
    memory_snapshot: Optional[dict[str, Any]] = Field(
        default=None,
        alias="memorySnapshot",
    )
    approval_request: Optional[ApprovalRequestResponse] = Field(
        default=None,
        alias="approvalRequest",
    )
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class DiffArtifactResponse(ApiModel):
    id: str
    artifact_id: str = Field(alias="artifactId")
    task_run_id: str = Field(alias="taskRunId")
    artifact_type: str = Field(alias="artifactType")
    title: str
    status: str
    base_ref: str = Field(alias="baseRef")
    head_ref: str = Field(alias="headRef")
    patch_text: str = Field(alias="patchText")
    changed_files: list[str] = Field(alias="changedFiles")
    stats: dict[str, Any]


class ArtifactVersionResponse(ApiModel):
    id: str
    artifact_id: str = Field(alias="artifactId")
    version: int
    source_task_run_id: Optional[str] = Field(alias="sourceTaskRunId")
    parent_artifact_id: Optional[str] = Field(alias="parentArtifactId")
    git_base_ref: Optional[str] = Field(alias="gitBaseRef")
    git_head_ref: Optional[str] = Field(alias="gitHeadRef")
    changed_files: list[str] = Field(alias="changedFiles")
    summary: str
    created_at: datetime = Field(alias="createdAt")


class ReviewArtifactResponse(ApiModel):
    id: str
    artifact_id: str = Field(alias="artifactId")
    task_run_id: str = Field(alias="taskRunId")
    reviewed_diff_artifact_id: str = Field(alias="reviewedDiffArtifactId")
    artifact_type: str = Field(alias="artifactType")
    title: str
    status: str
    risk_level: str = Field(alias="riskLevel")
    summary: str
    files_reviewed: list[str] = Field(alias="filesReviewed")
    findings: list[dict[str, Any]]
    suggested_changes: list[str] = Field(alias="suggestedChanges")
    adapter_type: str = Field(alias="adapterType")


class PreviewResponse(ApiModel):
    id: str
    artifact_id: str = Field(alias="artifactId")
    task_run_id: str = Field(alias="taskRunId")
    artifact_type: str = Field(alias="artifactType")
    title: str
    status: str
    port: int
    url: str
    command: str
    process_id: Optional[int] = Field(alias="processId")
    health_status: str = Field(alias="healthStatus")
    status_reason: Optional[str] = Field(alias="statusReason")
    expires_at: Optional[datetime] = Field(alias="expiresAt")
    last_checked_at: Optional[datetime] = Field(alias="lastCheckedAt")


class DeploymentResponse(ApiModel):
    id: str
    artifact_id: str = Field(alias="artifactId")
    task_run_id: str = Field(alias="taskRunId")
    artifact_type: str = Field(alias="artifactType")
    title: str
    status: str
    provider: str
    environment: str
    commit_sha: Optional[str] = Field(alias="commitSha")
    url: Optional[str]
    deploy_log_uri: Optional[str] = Field(alias="deployLogUri")
    provider_type: Optional[str] = Field(alias="providerType")
    target_id: Optional[str] = Field(alias="targetId")
    source_preview_id: Optional[str] = Field(alias="sourcePreviewId")
    source_diff_artifact_id: Optional[str] = Field(alias="sourceDiffArtifactId")
    source_review_artifact_id: Optional[str] = Field(alias="sourceReviewArtifactId")
    logs: list[str]
    status_history: list[dict[str, str]] = Field(alias="statusHistory")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class DeploymentCreateRequest(BaseModel):
    provider_id: str = Field(default="mock", alias="providerId")
    environment: str = "preview"

    model_config = ConfigDict(populate_by_name=True)


class CommandEvidenceCreateRequest(BaseModel):
    command_type: str = Field(alias="commandType")
    command: str
    exit_code: int = Field(alias="exitCode")
    stdout: str = ""
    stderr: str = ""
    target_id: Optional[str] = Field(default=None, alias="targetId")

    model_config = ConfigDict(populate_by_name=True)


class CommandEvidenceResponse(ApiModel):
    id: str
    artifact_id: str = Field(alias="artifactId")
    task_run_id: str = Field(alias="taskRunId")
    artifact_type: str = Field(alias="artifactType")
    title: str
    status: str
    command_type: str = Field(alias="commandType")
    command: str
    exit_code: int = Field(alias="exitCode")
    stdout: str
    stderr: str
    target_id: Optional[str] = Field(default=None, alias="targetId")
    created_at: datetime = Field(alias="createdAt")
