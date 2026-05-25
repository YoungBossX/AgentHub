from contextlib import asynccontextmanager
import json
from pathlib import Path
from typing import Any, AsyncIterator, Iterator, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlmodel import Session as DbSession
from sqlmodel import select

from app.adapters import AgentAdapter, AgentRunRequest, run_adapter_event_stream
from app.config import get_settings
from app.claude_code_adapter import ClaudeCodeAdapter
from app.codex_adapter import CodexAdapter
from app.context_pack import build_session_context_pack
from app.db import engine, init_database
from app.deployments import DeployError, DeployService, StoredDeploymentArtifact
from app.diffs import DiffCollectionError, StoredDiffArtifact, collect_task_run_diff, list_task_run_diffs
from app.events import encode_sse_event, list_session_events, subscribe_session_events
from app.external_workspaces import (
    ExternalWorkspaceRegistration,
    ExternalWorkspaceRegistrationError,
    allowed_paths_for,
    denied_paths_for,
    deploy_provider_ids_for,
    get_external_project_target,
    list_external_project_targets,
    register_external_project_target,
)
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
from app.mission_trace import build_session_mission_trace
from app.models import Agent, Message, Task, TaskRun
from app.models import Session as AgentHubSession
from app.models import SessionExecutionLedger
from app.models import TaskRunEvent
from app.models import utc_now
from app.planning import MentionParseError, plan_for_message
from app.project_analyzer import ProjectAnalysisResult, analyze_external_project
from app.previews import PreviewError, PreviewService, StoredPreviewArtifact
from app.repositories import (
    create_session_message,
    get_demo_workspace,
    get_enabled_agents,
    get_session,
    get_workspace,
    list_session_messages,
    list_session_tasks,
    list_workspace_sessions,
    next_session_title,
    persist_session,
)
from app.reviews import (
    ReviewError,
    StoredReviewArtifact,
    create_scripted_review_for_task_run,
    list_task_run_reviews,
)
from app.scheduler import complete_synthetic_planning_tasks
from app.scheduler import evaluate_and_apply_scheduler_readiness
from app.scheduler import refresh_session_scheduler_state
from app.target_registry import DEMO_BACKEND_TARGET_ID, DEMO_FRONTEND_TARGET_ID
from app.target_registry import (
    TargetProject,
    TargetRegistryError,
    get_target_for_workspace,
    list_targets_for_workspace,
)
from app.schemas import (
    AgentContactResponse,
    ApprovalDecisionRequest,
    ApprovalRequestResponse,
    CommandEvidenceCreateRequest,
    CommandEvidenceResponse,
    DeploymentCreateRequest,
    HealthResponse,
    DeploymentResponse,
    DiffArtifactResponse,
    ExternalProjectAnalysisRequest,
    ExternalProjectAnalysisResponse,
    ExternalProjectTargetCreateRequest,
    ExternalProjectTargetResponse,
    MessageCreateRequest,
    MessageResponse,
    PreviewResponse,
    ReviewArtifactResponse,
    SessionCreateRequest,
    SessionExecutionLedgerResponse,
    SessionMissionTraceResponse,
    SessionResponse,
    SessionTargetSelectionRequest,
    SessionUpdateRequest,
    TargetProjectResponse,
    TaskResponse,
    TaskRunResponse,
    WorkspaceResponse,
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
from app.scripted_mock import ScriptedMockAdapter
from app.worktrees import WorktreeError, WorktreeService


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
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)


def get_db() -> Iterator[DbSession]:
    with DbSession(engine) as session:
        yield session


def get_worktree_service() -> WorktreeService:
    return WorktreeService()


_preview_service = PreviewService()
_deploy_service = DeployService()

AGENT_CONTACT_METADATA: dict[str, dict[str, Any]] = {
    "orchestrator": {
        "displayName": "Manager / Orchestrator",
        "avatarInitials": "MO",
        "capabilityTags": ["planning", "task assignment", "coordination"],
        "status": "available",
        "safeForWrite": False,
        "safeForReview": True,
        "description": "Plans the local demo workflow and coordinates role agents.",
        "contactType": "agent",
    },
    "frontend": {
        "displayName": "Frontend Agent",
        "avatarInitials": "FE",
        "capabilityTags": ["Vite React", "UI changes", "diff artifacts"],
        "status": "available",
        "safeForWrite": True,
        "safeForReview": False,
        "description": "Executes bounded frontend changes inside the session worktree.",
        "contactType": "agent",
    },
    "backend": {
        "displayName": "Backend Agent",
        "avatarInitials": "BE",
        "capabilityTags": ["FastAPI", "API changes", "SQLite"],
        "status": "available",
        "safeForWrite": True,
        "safeForReview": False,
        "description": "Represents backend coding work while preserving demo guardrails.",
        "contactType": "agent",
    },
    "qa": {
        "displayName": "QA Agent",
        "avatarInitials": "QA",
        "capabilityTags": ["demo QA", "preview checks", "workflow review"],
        "status": "available",
        "safeForWrite": False,
        "safeForReview": True,
        "description": "Reviews the demo path and expected evidence without changing dispatch.",
        "contactType": "agent",
    },
}

VIRTUAL_AGENT_CONTACTS: tuple[AgentContactResponse, ...] = (
    AgentContactResponse(
        id="virtual-review-agent",
        displayName="Review Agent",
        avatarInitials="RV",
        role="review",
        adapterType="claude_code",
        capabilityTags=["planned", "read-only", "non-blocking review"],
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
        capabilityTags=["demo recovery", "scripted fallback", "real file changes"],
        status="available",
        safeForWrite=True,
        safeForReview=False,
        description="Documents the preserved ScriptedMockAdapter reliability path.",
        contactType="service",
    ),
)


def get_preview_service() -> PreviewService:
    return _preview_service


def get_deploy_service() -> DeployService:
    return _deploy_service



@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="agenthub-api",
        database="ready",
    )


@app.get("/workspaces/demo", response_model=WorkspaceResponse)
def read_demo_workspace(db: DbSession = Depends(get_db)) -> WorkspaceResponse:
    return get_demo_workspace(db)


def external_target_response(
    target: "ExternalProjectTarget",
) -> ExternalProjectTargetResponse:
    return ExternalProjectTargetResponse(
        id=target.id,
        workspaceId=target.workspace_id,
        targetId=target.target_id,
        name=target.name,
        rootPath=target.root_path,
        projectType=target.project_type,
        allowedPaths=allowed_paths_for(target),
        deniedPaths=denied_paths_for(target),
        devCommand=target.dev_command,
        testCommand=target.test_command,
        checkCommand=target.check_command,
        buildCommand=target.build_command,
        previewCommand=target.preview_command,
        stagingOutputDir=target.staging_output_dir,
        stagingServeCommand=target.staging_serve_command,
        deployProviderIds=deploy_provider_ids_for(target),
        packageManager=target.package_manager,
        detectedFramework=target.detected_framework,
        analysisStatus=target.analysis_status,
        createdAt=target.created_at,
        updatedAt=target.updated_at,
    )


def external_project_analysis_response(
    analysis: ProjectAnalysisResult,
) -> ExternalProjectAnalysisResponse:
    return ExternalProjectAnalysisResponse(
        rootPath=analysis.root_path,
        projectType=analysis.project_type,
        detectedFramework=analysis.detected_framework,
        packageManager=analysis.package_manager,
        allowedPaths=list(analysis.allowed_paths),
        deniedPaths=list(analysis.denied_paths),
        devCommand=analysis.dev_command,
        testCommand=analysis.test_command,
        checkCommand=analysis.check_command,
        buildCommand=analysis.build_command,
        previewCommand=analysis.preview_command,
        analysisStatus=analysis.analysis_status,
        analysisWarnings=list(analysis.analysis_warnings),
        confidence=analysis.confidence,
    )


def target_project_response(target: TargetProject) -> TargetProjectResponse:
    return TargetProjectResponse(
        targetId=target.target_id,
        name=target.name,
        type=target.type,
        root=target.root,
        allowedPaths=list(target.allowed_paths),
        deniedPaths=list(target.denied_paths),
        devCommand=target.dev_command,
        testCommand=target.test_command,
        checkCommand=target.check_command,
        buildCommand=target.build_command,
        previewCommand=target.preview_command,
        stagingOutputDir=target.staging_output_dir,
        stagingServeCommand=target.staging_serve_command,
        deployProviderIds=list(target.deploy_provider_ids),
        baseUrl=target.base_url,
        packageManager=target.package_manager,
        detectedFramework=target.detected_framework,
        projectType=target.project_type,
        analysisStatus=target.analysis_status,
        allowedAgents=list(target.allowed_agents),
        requiresPlatformMode=target.requires_platform_mode,
        requiresApproval=target.requires_approval,
        relatedTargetIds=list(target.related_target_ids),
    )


@app.get(
    "/workspaces/{workspace_id}/targets",
    response_model=list[TargetProjectResponse],
)
def read_workspace_targets(
    workspace_id: str,
    db: DbSession = Depends(get_db),
) -> list[TargetProjectResponse]:
    if get_workspace(db, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return [
        target_project_response(target)
        for target in list_targets_for_workspace(db, workspace_id)
    ]


@app.post(
    "/workspaces/{workspace_id}/external-targets/analyze",
    response_model=ExternalProjectAnalysisResponse,
)
def analyze_external_target(
    workspace_id: str,
    request: ExternalProjectAnalysisRequest,
    db: DbSession = Depends(get_db),
) -> ExternalProjectAnalysisResponse:
    if get_workspace(db, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return external_project_analysis_response(
        analyze_external_project(request.root_path)
    )


@app.post(
    "/workspaces/{workspace_id}/external-targets",
    response_model=ExternalProjectTargetResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_external_target(
    workspace_id: str,
    request: ExternalProjectTargetCreateRequest,
    db: DbSession = Depends(get_db),
) -> ExternalProjectTargetResponse:
    workspace = get_workspace(db, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    try:
        target = register_external_project_target(
            db,
            workspace,
            ExternalWorkspaceRegistration(
                target_id=request.target_id,
                name=request.name,
                root_path=request.root_path,
                project_type=request.project_type,
                allowed_paths=request.allowed_paths,
                denied_paths=request.denied_paths,
                dev_command=request.dev_command,
                test_command=request.test_command,
                check_command=request.check_command,
                build_command=request.build_command,
                preview_command=request.preview_command,
                staging_output_dir=request.staging_output_dir,
                staging_serve_command=request.staging_serve_command,
                deploy_provider_ids=request.deploy_provider_ids,
                package_manager=request.package_manager,
                detected_framework=request.detected_framework,
            ),
        )
    except ExternalWorkspaceRegistrationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return external_target_response(target)


@app.get(
    "/workspaces/{workspace_id}/external-targets",
    response_model=list[ExternalProjectTargetResponse],
)
def read_external_targets(
    workspace_id: str,
    db: DbSession = Depends(get_db),
) -> list[ExternalProjectTargetResponse]:
    if get_workspace(db, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return [
        external_target_response(target)
        for target in list_external_project_targets(db, workspace_id)
    ]


@app.get(
    "/workspaces/{workspace_id}/external-targets/{target_id}",
    response_model=ExternalProjectTargetResponse,
)
def read_external_target(
    workspace_id: str,
    target_id: str,
    db: DbSession = Depends(get_db),
) -> ExternalProjectTargetResponse:
    if get_workspace(db, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    target = get_external_project_target(db, workspace_id, target_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="External target not found",
        )
    return external_target_response(target)


def agent_contact_response(agent: Agent) -> AgentContactResponse:
    metadata = AGENT_CONTACT_METADATA.get(agent.role, {})
    return AgentContactResponse(
        id=agent.id,
        displayName=str(metadata.get("displayName") or agent.name),
        avatarInitials=str(metadata.get("avatarInitials") or agent.role[:2].upper()),
        role=agent.role,
        adapterType=agent.adapter_type,
        capabilityTags=list(metadata.get("capabilityTags") or []),
        status=str(metadata.get("status") or "available"),
        safeForWrite=bool(metadata.get("safeForWrite", False)),
        safeForReview=bool(metadata.get("safeForReview", False)),
        description=str(metadata.get("description") or agent.system_prompt),
        contactType=str(metadata.get("contactType") or "agent"),
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
    return [agent_contact_response(agent) for agent in agents] + list(
        VIRTUAL_AGENT_CONTACTS
    )


@app.get(
    "/workspaces/{workspace_id}/sessions",
    response_model=list[SessionResponse],
)
def read_workspace_sessions(
    workspace_id: str,
    db: DbSession = Depends(get_db),
) -> list[AgentHubSession]:
    if get_workspace(db, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return list_workspace_sessions(db, workspace_id)


@app.post(
    "/workspaces/{workspace_id}/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_workspace_session(
    workspace_id: str,
    request: SessionCreateRequest,
    db: DbSession = Depends(get_db),
    worktrees: WorktreeService = Depends(get_worktree_service),
) -> AgentHubSession:
    workspace = get_workspace(db, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    now = utc_now()
    session = AgentHubSession(
        workspace_id=workspace.id,
        title=request.title or next_session_title(db, workspace.id),
        session_type="demo",
        bound_branch=workspace.default_branch,
        worktree_path=str(worktrees.session_path(workspace.id, "")),
        status="active",
        last_message_at=now,
        created_at=now,
        updated_at=now,
    )
    try:
        worktree_path = worktrees.create_session_worktree(workspace, session.id)
    except WorktreeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not create session worktree: {exc}",
        ) from exc

    session.worktree_path = str(worktree_path)
    return persist_session(db, session)


@app.get("/sessions/{session_id}", response_model=SessionResponse)
def read_session(
    session_id: str,
    db: DbSession = Depends(get_db),
) -> AgentHubSession:
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


@app.patch("/sessions/{session_id}", response_model=SessionResponse)
def update_session(
    session_id: str,
    request: SessionUpdateRequest,
    db: DbSession = Depends(get_db),
) -> AgentHubSession:
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if request.title is not None:
        session.title = request.title
    if request.status is not None:
        session.status = request.status

    return persist_session(db, session)


@app.patch("/sessions/{session_id}/target-selection", response_model=SessionResponse)
def update_session_target_selection(
    session_id: str,
    request: SessionTargetSelectionRequest,
    db: DbSession = Depends(get_db),
) -> AgentHubSession:
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if request.frontend_target_id is not None:
        _validate_session_target(
            db,
            session.workspace_id,
            request.frontend_target_id,
            expected_type="frontend",
        )
        session.active_frontend_target_id = request.frontend_target_id
    if request.backend_target_id is not None:
        _validate_session_target(
            db,
            session.workspace_id,
            request.backend_target_id,
            expected_type="backend",
        )
        session.active_backend_target_id = request.backend_target_id

    return persist_session(db, session)


def _validate_session_target(
    db: DbSession,
    workspace_id: str,
    target_id: str,
    *,
    expected_type: str,
) -> None:
    try:
        target = get_target_for_workspace(db, workspace_id, target_id)
    except TargetRegistryError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    if target.type != expected_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Target {target_id} is not a {expected_type} target.",
        )


@app.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
def read_session_messages(
    session_id: str,
    db: DbSession = Depends(get_db),
) -> list[Message]:
    if get_session(db, session_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return list_session_messages(db, session_id)


@app.post(
    "/sessions/{session_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_message(
    session_id: str,
    request: MessageCreateRequest,
    background_tasks: BackgroundTasks,
    db: DbSession = Depends(get_db),
) -> Message:
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    message = Message(
        session_id=session.id,
        sender_type=request.sender_type,
        sender_id=request.sender_id,
        content_md=request.content_md,
        message_kind=request.message_kind,
        parent_message_id=request.parent_message_id,
        stream_state=request.stream_state,
    )
    created = create_session_message(db, session, message)
    if created.sender_type == "user":
        try:
            planned_tasks = plan_for_message(db, created, created.content_md)
            complete_synthetic_planning_tasks(db, planned_tasks)
            refresh_session_scheduler_state(db, session.id)
            auto_start_safe_tasks(db, planned_tasks, background_tasks)
        except MentionParseError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    refresh_session_ledger(db, session.id)
    return created


def auto_start_safe_tasks(
    db: DbSession,
    tasks: list[Task],
    background_tasks: BackgroundTasks,
) -> None:
    for task in tasks:
        try:
            plan = json.loads(task.plan_json)
        except json.JSONDecodeError:
            continue
        if not _should_auto_start_task(task, plan):
            continue
        decision = evaluate_and_apply_scheduler_readiness(db, task)
        if not decision.runnable:
            continue
        task_run = create_task_run(db, task.id)
        adapter_type = adapter_type_for_run(db, task_run)
        background_tasks.add_task(
            _background_execute_task_run,
            task_run.id,
            adapter_type,
        )


def _should_auto_start_task(task: Task, plan: dict[str, Any]) -> bool:
    if not plan.get("autoStart"):
        return False
    files = plan.get("files", [])
    if not isinstance(files, list) or not files:
        return False
    if task.intent_type == "frontend_change":
        target_id = plan.get("targetId")
        if isinstance(target_id, str) and target_id.startswith("external-"):
            safe_target = plan.get("safeTarget")
            return (
                isinstance(safe_target, str)
                and bool(safe_target)
                and all(_is_safe_relative_external_path(path) for path in files)
            )
        if plan.get("targetId") not in {None, DEMO_FRONTEND_TARGET_ID}:
            return False
        if plan.get("safeTarget") != "apps/demo/src":
            return False
        return all(
            isinstance(path, str) and path.startswith("apps/demo/src/")
            for path in files
        )
    if task.intent_type == "backend_change":
        if plan.get("targetId") != DEMO_BACKEND_TARGET_ID:
            return False
        if plan.get("safeTarget") != "apps/demo-api":
            return False
        return all(
            isinstance(path, str) and path.startswith("apps/demo-api/")
            for path in files
        )
    return False


def _is_safe_relative_external_path(path: object) -> bool:
    if not isinstance(path, str) or not path.strip():
        return False
    normalized = path.replace("\\", "/").strip()
    if normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized:
        return False
    return not any(
        part in {".git", "node_modules", ".venv", "venv", "secrets"}
        for part in normalized.split("/")
    )


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


def task_run_response(db: DbSession, task_run: TaskRun) -> TaskRunResponse:
    task = db.get(Task, task_run.task_id)
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
        metricsJson=metrics_for_run(task_run),
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


def agent_run_request_for(
    db: DbSession,
    task_run: TaskRun,
    *,
    adapter_type: str,
    plan_context: Optional[dict[str, Any]] = None,
) -> AgentRunRequest:
    task = db.get(Task, task_run.task_id)
    if task is None:
        raise TaskRunLifecycleError(f"Task not found: {task_run.task_id}")
    session = db.get(AgentHubSession, task.session_id)
    if session is None:
        raise TaskRunLifecycleError(f"Session not found: {task.session_id}")
    agent = db.get(Agent, task_run.agent_id)
    if agent is None:
        raise TaskRunLifecycleError(f"Agent not found: {task_run.agent_id}")
    task_plan = plan_json_for_task(task)
    merged_plan_context = dict(task_plan)
    if plan_context:
        merged_plan_context.update(plan_context)
    context_pack = build_session_context_pack(
        db,
        task,
        plan_context=merged_plan_context,
    )
    _persist_context_snapshot(db, task_run, context_pack)
    merged_plan_context["sessionContext"] = context_pack
    return AgentRunRequest(
        taskRunId=task_run.id,
        sessionId=session.id,
        workspaceId=session.workspace_id,
        worktreePath=task_run.worktree_path,
        agentId=task_run.agent_id,
        adapterType=adapter_type,
        instruction=build_role_instruction(
            task,
            agent,
            context_pack,
            adapter_type=adapter_type,
        ),
        planContext=merged_plan_context,
        permissionProfile={"network": "off"},
        demoMode=True,
        fallbackPolicy="scripted_mock" if adapter_type == "scripted_mock" else "none",
    )


def _persist_context_snapshot(
    db: DbSession,
    task_run: TaskRun,
    context_pack: dict[str, Any],
) -> None:
    canonical_context = context_pack.get("canonicalContext")
    if not isinstance(canonical_context, dict):
        return
    metrics = metrics_for_run(task_run)
    metrics["canonicalContextSnapshot"] = canonical_context
    task_run.metrics_json = json.dumps(metrics, separators=(",", ":"))
    task_run.updated_at = utc_now()
    db.add(task_run)
    expire_on_commit = getattr(db, "expire_on_commit", True)
    db.expire_on_commit = False
    try:
        db.commit()
        db.refresh(task_run)
    finally:
        db.expire_on_commit = expire_on_commit


def plan_json_for_task(task: Task) -> dict[str, Any]:
    try:
        plan = json.loads(task.plan_json)
    except json.JSONDecodeError:
        return {}
    return plan if isinstance(plan, dict) else {}


def adapter_for_type(
    adapter_type: str,
    *,
    codex_adapter: AgentAdapter,
    claude_code_adapter: AgentAdapter,
    scripted_mock_adapter: AgentAdapter,
) -> AgentAdapter:
    if adapter_type == "codex":
        return codex_adapter
    if adapter_type == "claude_code":
        return claude_code_adapter
    if adapter_type == "scripted_mock":
        return scripted_mock_adapter
    raise TaskRunLifecycleError(f"Unsupported adapter type: {adapter_type}")


async def execute_task_run(
    db: DbSession,
    task_run: TaskRun,
    *,
    adapter_type: str,
    adapter: AgentAdapter,
    plan_context: Optional[dict[str, Any]] = None,
) -> TaskRun:
    request = agent_run_request_for(
        db,
        task_run,
        adapter_type=adapter_type,
        plan_context=plan_context,
    )
    await run_adapter_event_stream(db, adapter, request)
    db.refresh(task_run)
    if task_run.state == "completed":
        collect_task_run_diff(db, task_run.id)
        create_scripted_review_for_task_run(db, task_run.id)
        refresh_session_ledger_for_task_run(db, task_run.id)
        _complete_ready_pipeline_review_tasks(db, task_run.task_id)
        _maybe_auto_preview_and_mock_deploy(db, task_run)
        await _auto_start_next_pipeline_task(db, task_run.task_id)
        db.refresh(task_run)
    return task_run


async def _auto_start_next_pipeline_task(
    db: DbSession,
    completed_task_id: str,
) -> Optional[TaskRun]:
    completed_task = db.get(Task, completed_task_id)
    if completed_task is None:
        return None
    for task in list_session_tasks(db, completed_task.session_id):
        if not _is_auto_pipeline_task(task):
            continue
        if _has_task_run(db, task.id):
            continue
        decision = evaluate_and_apply_scheduler_readiness(db, task)
        if not decision.runnable:
            continue
        task_run = create_task_run(db, task.id)
        adapter_type = adapter_type_for_run(db, task_run)
        adapter = adapter_for_type(
            adapter_type,
            codex_adapter=CodexAdapter(),
            claude_code_adapter=ClaudeCodeAdapter(),
            scripted_mock_adapter=ScriptedMockAdapter(),
        )
        return await execute_task_run(
            db,
            task_run,
            adapter_type=adapter_type,
            adapter=adapter,
        )
    return None


def _complete_ready_pipeline_review_tasks(
    db: DbSession,
    completed_task_id: str,
) -> list[Task]:
    completed_task = db.get(Task, completed_task_id)
    if completed_task is None:
        return []

    completed: list[Task] = []
    for task in list_session_tasks(db, completed_task.session_id):
        if task.intent_type not in {"review", "qa_review"}:
            continue
        if task.status not in {"pending", "waiting_dependency"}:
            continue
        plan = plan_json_for_task(task)
        if plan.get("planner") != "contract_first_v1":
            continue
        decision = evaluate_and_apply_scheduler_readiness(db, task)
        if not decision.runnable:
            continue
        plan = plan_json_for_task(task)
        scheduler = dict(plan.get("scheduler") or {})
        scheduler.update(
            {
                "state": "completed",
                "runnable": False,
                "reason": "Contract review was satisfied by the generated review artifact.",
            }
        )
        plan["scheduler"] = scheduler
        task.plan_json = json.dumps(plan, separators=(",", ":"))
        task.status = "completed"
        task.updated_at = utc_now()
        db.add(task)
        db.commit()
        db.refresh(task)
        completed.append(task)
    return completed


def _maybe_auto_preview_and_mock_deploy(db: DbSession, task_run: TaskRun) -> None:
    task = db.get(Task, task_run.task_id)
    if task is None or task.intent_type != "frontend_change":
        return
    plan = plan_json_for_task(task)
    if plan.get("planner") != "contract_first_v1":
        return
    demo_root = Path(task_run.worktree_path) / "apps/demo"
    if not demo_root.exists():
        return
    try:
        preview = _preview_service.start_task_run_preview(db, task_run.id)
        if preview.health_status != "healthy":
            return
        _deploy_service.create_mock_deployment(db, preview.id)
        refresh_session_ledger_for_task_run(db, task_run.id)
    except (PreviewError, DeployError):
        return


def _is_auto_pipeline_task(task: Task) -> bool:
    plan = plan_json_for_task(task)
    return (
        plan.get("planner") == "contract_first_v1"
        and plan.get("autoStart") is True
        and task.intent_type in {"backend_change", "frontend_change"}
    )


def _has_task_run(db: DbSession, task_id: str) -> bool:
    return bool(list_task_runs(db, task_id))


async def _background_execute_task_run(
    task_run_id: str,
    adapter_type: str,
) -> None:
    from app.db import engine as db_engine

    adapter = adapter_for_type(
        adapter_type,
        codex_adapter=CodexAdapter(),
        claude_code_adapter=ClaudeCodeAdapter(),
        scripted_mock_adapter=ScriptedMockAdapter(),
    )
    with DbSession(db_engine) as db:
        task_run = db.get(TaskRun, task_run_id)
        if task_run is None:
            return
        try:
            await execute_task_run(
                db,
                task_run,
                adapter_type=adapter_type,
                adapter=adapter,
            )
        except Exception:
            db.refresh(task_run)
            if task_run.state not in {"completed", "failed", "interrupted"}:
                try:
                    transition_task_run(
                        db,
                        task_run_id,
                        "failed",
                        error_code="ADAPTER_EXECUTION_ERROR",
                        error_message="Adapter execution failed unexpectedly.",
                    )
                except Exception:
                    pass


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
        createdAt=evidence.created_at,
    )


def task_response(db: DbSession, task: Task) -> TaskResponse:
    assigned_role = None
    if task.assigned_agent_id is not None:
        agent = db.get(Agent, task.assigned_agent_id)
        assigned_role = agent.role if agent is not None else None

    return TaskResponse(
        id=task.id,
        sessionId=task.session_id,
        createdByMessageId=task.created_by_message_id,
        title=task.title,
        intentType=task.intent_type,
        status=task.status,
        priority=task.priority,
        planJson=json.loads(task.plan_json),
        dependsOnTaskIds=json.loads(task.depends_on_task_ids),
        assignedAgentId=task.assigned_agent_id,
        assignedAgentRole=assigned_role,
        taskRuns=[task_run_response(db, task_run) for task_run in list_task_runs(db, task.id)],
        createdAt=task.created_at,
        updatedAt=task.updated_at,
    )


@app.get("/sessions/{session_id}/tasks", response_model=list[TaskResponse])
def read_session_tasks(
    session_id: str,
    db: DbSession = Depends(get_db),
) -> list[TaskResponse]:
    if get_session(db, session_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return [task_response(db, task) for task in list_session_tasks(db, session_id)]


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
        adapter_type = adapter_type_for_run(db, task_run)
    except TaskRunLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    background_tasks.add_task(
        _background_execute_task_run,
        task_run.id,
        adapter_type,
    )
    return task_run_response(db, task_run)


@app.post(
    "/tasks/{task_id}/runs/force-codex-failure",
    response_model=TaskRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def force_codex_failure_for_task(
    task_id: str,
    db: DbSession = Depends(get_db),
) -> TaskRunResponse:
    try:
        task_run = create_task_run(db, task_id, adapter_type="codex")
        request = agent_run_request_for(
            db,
            task_run,
            adapter_type="codex",
            plan_context={"forceFailure": True},
        )
        await run_adapter_event_stream(db, CodexAdapter(), request)
        db.refresh(task_run)
    except TaskRunLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return task_run_response(db, task_run)


@app.post("/task-runs/{task_run_id}/interrupt", response_model=TaskRunResponse)
def interrupt_existing_task_run(
    task_run_id: str,
    db: DbSession = Depends(get_db),
) -> TaskRunResponse:
    try:
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
    db: DbSession = Depends(get_db),
) -> TaskRunResponse:
    try:
        task_run = retry_task_run(db, task_run_id)
    except TaskRunLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return task_run_response(db, task_run)


@app.post(
    "/task-runs/{task_run_id}/retry-with-fallback",
    response_model=TaskRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def retry_existing_task_run_with_fallback(
    task_run_id: str,
    db: DbSession = Depends(get_db),
) -> TaskRunResponse:
    try:
        task_run = retry_with_scripted_mock(db, task_run_id)
        request = agent_run_request_for(db, task_run, adapter_type="scripted_mock")
        await run_adapter_event_stream(db, ScriptedMockAdapter(), request)
        db.refresh(task_run)
        if task_run.state == "completed":
            collect_task_run_diff(db, task_run.id)
            create_scripted_review_for_task_run(db, task_run.id)
            refresh_session_ledger_for_task_run(db, task_run.id)
            db.refresh(task_run)
    except TaskRunLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DiffCollectionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ReviewError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
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
    try:
        diff_artifact = collect_task_run_diff(db, task_run_id)
        create_scripted_review_for_task_run(db, task_run_id)
        refresh_session_ledger_for_task_run(db, task_run_id)
    except DiffCollectionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ReviewError as exc:
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
