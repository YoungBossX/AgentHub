from contextlib import asynccontextmanager
import json
from typing import Any, AsyncIterator, Iterator, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlmodel import Session as DbSession

from app.adapters import AgentAdapter, AgentRunRequest, run_adapter_event_stream
from app.config import get_settings
from app.codex_adapter import CodexAdapter
from app.db import engine, init_database
from app.deployments import DeployError, DeployService, StoredDeploymentArtifact
from app.diffs import DiffCollectionError, StoredDiffArtifact, collect_task_run_diff, list_task_run_diffs
from app.events import encode_sse_event, list_session_events, subscribe_session_events
from app.models import Agent, Message, Task, TaskRun
from app.models import Session as AgentHubSession
from app.models import utc_now
from app.planning import MentionParseError, plan_for_message
from app.previews import PreviewError, PreviewService, StoredPreviewArtifact
from app.repositories import (
    create_session_message,
    get_demo_workspace,
    get_session,
    get_workspace,
    list_session_messages,
    list_session_tasks,
    list_workspace_sessions,
    next_session_title,
    persist_session,
)
from app.schemas import (
    HealthResponse,
    DeploymentResponse,
    DiffArtifactResponse,
    MessageCreateRequest,
    MessageResponse,
    PreviewResponse,
    SessionCreateRequest,
    SessionResponse,
    SessionUpdateRequest,
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

app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
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
            plan_for_message(db, created, created.content_md)
        except MentionParseError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    return created


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
        worktreePath=task_run.worktree_path,
        baseRef=task_run.base_ref,
        headRef=task_run.head_ref,
        errorCode=task_run.error_code,
        errorMessage=task_run.error_message,
        metricsJson=metrics_for_run(task_run),
        createdAt=task_run.created_at,
        updatedAt=task_run.updated_at,
    )


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
    return AgentRunRequest(
        taskRunId=task_run.id,
        sessionId=session.id,
        workspaceId=session.workspace_id,
        worktreePath=session.worktree_path,
        agentId=task_run.agent_id,
        adapterType=adapter_type,
        instruction=instruction_for_task(task),
        planContext=plan_context or {},
        permissionProfile={"network": "off"},
        demoMode=True,
        fallbackPolicy="scripted_mock" if adapter_type == "scripted_mock" else "none",
    )


def instruction_for_task(task: Task) -> str:
    try:
        plan = json.loads(task.plan_json)
    except json.JSONDecodeError:
        plan = {}

    if (
        task.intent_type == "frontend_change"
        and isinstance(plan, dict)
        and plan.get("target") == "login_page"
    ):
        return (
            "In apps/demo/src/App.tsx, find the element with "
            'data-agenthub-target="login-page-slot" and replace only that slot '
            "content with a compact login form containing email and password "
            "fields. Keep the existing deterministic data-agenthub-target "
            "attributes intact, do not edit unrelated files, do not read the "
            "OpenSpec change, and do not run setup or dependency install "
            "commands."
        )

    return task.title


def adapter_for_type(
    adapter_type: str,
    *,
    codex_adapter: AgentAdapter,
    scripted_mock_adapter: AgentAdapter,
) -> AgentAdapter:
    if adapter_type == "codex":
        return codex_adapter
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
        db.refresh(task_run)
    return task_run


async def _background_execute_task_run(
    task_run_id: str,
    adapter_type: str,
) -> None:
    from app.db import engine as db_engine

    adapter = adapter_for_type(
        adapter_type,
        codex_adapter=CodexAdapter(),
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
        createdAt=deployment.created_at,
        updatedAt=deployment.updated_at,
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
            db.refresh(task_run)
    except TaskRunLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DiffCollectionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
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
    except DiffCollectionError as exc:
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
    return [
        preview_response(preview)
        for preview in previews.list_task_run_previews(db, task_run_id)
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
    db: DbSession = Depends(get_db),
    deployments: DeployService = Depends(get_deploy_service),
) -> DeploymentResponse:
    try:
        deployment = deployments.create_mock_deployment(db, preview_id)
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
