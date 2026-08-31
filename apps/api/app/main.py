from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session as DbSession

from app.config import get_settings
from app.db import init_database
from app.dependencies import get_db, get_deploy_service, get_preview_service
from app.diffs import collect_task_run_diff
from app.events import list_session_events
from app.ledger import (
    active_agents_for_ledger,
    changed_files_for_ledger,
    refresh_session_ledger,
)
from app.mission_trace import build_session_mission_trace
from app.models import SessionExecutionLedger
from app.previews import StoredPreviewArtifact
from app.repositories import get_session
from app.reviews import create_scripted_review_for_task_run
from app.routes import session_events as session_event_routes
from app.routes import task_artifacts as task_artifact_routes
from app.routes import task_runs as task_run_routes
from app.routes.agent_settings import router as agent_settings_router
from app.routes.health import router as health_router
from app.routes.messages import router as messages_router
from app.routes.registries import router as registries_router
from app.routes.sessions import router as sessions_router
from app.routes.targets import router as targets_router
from app.routes.workspaces import router as workspaces_router
from app.run_diagnostics import build_session_run_diagnostics_summary
from app.run_engine import (
    adapter_for_type,
    agent_run_request_for,
    interrupt_supervised_task_run,
    schedule_task_run_execution,
    _complete_ready_pipeline_review_tasks,
)
from app.schemas import (
    DeploymentCreateRequest,
    SessionExecutionLedgerResponse,
    SessionMissionTraceResponse,
    SessionRunDiagnosticsSummaryResponse,
)
from app.task_runs import require_task_run_artifact_scope_passed


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_database(seed=True)
    yield


settings = get_settings()
SESSION_EVENT_POLL_INTERVAL_SECONDS = 1.0
SESSION_EVENT_HEARTBEAT_INTERVAL_SECONDS = 15.0
SESSION_EVENT_HEARTBEAT_FRAME = ": keep-alive\n\n"

LOCAL_FRONTEND_ORIGINS = {
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    settings.frontend_origin,
}


# Compatibility bridges keep established app.main monkeypatch/import surfaces
# working while route ownership lives in focused modules.
task_run_routes.schedule_task_run_execution = (
    lambda background_tasks: schedule_task_run_execution(background_tasks)
)
task_run_routes.interrupt_supervised_task_run = (
    lambda task_run_id: interrupt_supervised_task_run(task_run_id)
)
task_artifact_routes.collect_task_run_diff = (
    lambda *args, **kwargs: collect_task_run_diff(*args, **kwargs)
)
task_artifact_routes.create_scripted_review_for_task_run = (
    lambda *args, **kwargs: create_scripted_review_for_task_run(*args, **kwargs)
)
task_artifact_routes.require_task_run_artifact_scope_passed = (
    lambda *args, **kwargs: require_task_run_artifact_scope_passed(*args, **kwargs)
)
session_event_routes.list_session_events = (
    lambda *args, **kwargs: list_session_events(*args, **kwargs)
)
session_event_routes.session_event_poll_interval_seconds = (
    lambda: SESSION_EVENT_POLL_INTERVAL_SECONDS
)
session_event_routes.session_event_heartbeat_interval_seconds = (
    lambda: SESSION_EVENT_HEARTBEAT_INTERVAL_SECONDS
)
session_event_routes.session_event_heartbeat_frame = (
    lambda: SESSION_EVENT_HEARTBEAT_FRAME
)


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(LOCAL_FRONTEND_ORIGINS),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(agent_settings_router)
app.include_router(registries_router)
app.include_router(messages_router)
app.include_router(sessions_router)
app.include_router(targets_router)
app.include_router(workspaces_router)
app.include_router(task_run_routes.router)
app.include_router(task_artifact_routes.router)
app.include_router(session_event_routes.router)


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


# Compatibility exports for tests and existing internal callers.
task_run_response = task_run_routes.task_run_response
latest_approval_request = task_run_routes.latest_approval_request
task_response = task_run_routes.task_response
collect_diff_for_task_run = task_artifact_routes.collect_diff_for_task_run
create_review_for_task_run = task_artifact_routes.create_review_for_task_run
start_preview_for_task_run = task_artifact_routes.start_preview_for_task_run
create_mock_deployment_for_preview = (
    task_artifact_routes.create_mock_deployment_for_preview
)
_require_artifact_scope_passed = task_artifact_routes._require_artifact_scope_passed
stream_session_events = session_event_routes.stream_session_events
