from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlmodel import Field, SQLModel


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.utcnow()


class User(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    email: str = Field(index=True, unique=True)
    name: str
    avatar_url: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)


class Workspace(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    name: str = Field(index=True)
    repo_url: str
    root_path: str
    default_branch: str
    created_at: datetime = Field(default_factory=utc_now)


class ExternalProjectTarget(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    workspace_id: str = Field(foreign_key="workspace.id", index=True)
    target_id: str = Field(index=True, unique=True)
    name: str
    root_path: str
    project_type: str = "unknown"
    allowed_paths_json: str = "[]"
    denied_paths_json: str = "[]"
    dev_command: Optional[str] = None
    test_command: Optional[str] = None
    check_command: Optional[str] = None
    build_command: Optional[str] = None
    preview_command: Optional[str] = None
    staging_output_dir: Optional[str] = None
    staging_serve_command: Optional[str] = None
    deploy_provider_ids_json: str = "[]"
    package_manager: Optional[str] = None
    detected_framework: Optional[str] = None
    analysis_status: str = "manual"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Session(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    workspace_id: str = Field(foreign_key="workspace.id", index=True)
    title: str
    session_type: str = "demo"
    bound_branch: str
    worktree_path: str = Field(index=True, unique=True)
    active_frontend_target_id: Optional[str] = None
    active_backend_target_id: Optional[str] = None
    status: str = "active"
    last_message_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Message(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    session_id: str = Field(foreign_key="session.id", index=True)
    sender_type: str
    sender_id: Optional[str] = None
    content_md: str
    message_kind: str = "chat"
    parent_message_id: Optional[str] = Field(default=None, foreign_key="message.id")
    stream_state: str = "complete"
    created_at: datetime = Field(default_factory=utc_now)


class Agent(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    name: str
    role: str = Field(index=True, unique=True)
    adapter_type: str
    provider: str
    default_model: Optional[str] = None
    system_prompt: str = ""
    capabilities_json: str = "{}"
    permission_profile_json: str = "{}"
    enabled: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Task(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    session_id: str = Field(foreign_key="session.id", index=True)
    created_by_message_id: Optional[str] = Field(default=None, foreign_key="message.id")
    title: str
    intent_type: str
    status: str = "pending"
    priority: int = 0
    plan_json: str = "{}"
    depends_on_task_ids: str = "[]"
    assigned_agent_id: Optional[str] = Field(default=None, foreign_key="agent.id")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class TaskRun(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    task_id: str = Field(foreign_key="task.id", index=True)
    agent_id: str = Field(foreign_key="agent.id", index=True)
    adapter_run_id: Optional[str] = None
    state: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    runner_id: Optional[str] = None
    last_heartbeat_at: Optional[datetime] = None
    lease_expires_at: Optional[datetime] = None
    stale_detected_at: Optional[datetime] = None
    stale_reason: Optional[str] = None
    worktree_path: str
    base_ref: Optional[str] = None
    head_ref: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metrics_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class TaskRunEvent(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    task_run_id: str = Field(foreign_key="taskrun.id", index=True)
    event_type: str
    payload_json: str = "{}"
    sequence: int
    created_at: datetime = Field(default_factory=utc_now)


class Artifact(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    task_run_id: str = Field(foreign_key="taskrun.id", index=True)
    artifact_type: str
    title: str
    status: str
    version: int = 1
    storage_uri: Optional[str] = None
    meta_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ArtifactVersion(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    artifact_id: str = Field(foreign_key="artifact.id", index=True)
    version: int = 1
    source_task_run_id: Optional[str] = Field(default=None, foreign_key="taskrun.id")
    parent_artifact_id: Optional[str] = Field(default=None, foreign_key="artifact.id")
    git_base_ref: Optional[str] = None
    git_head_ref: Optional[str] = None
    changed_files_json: str = "[]"
    summary: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class Diff(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    artifact_id: str = Field(foreign_key="artifact.id", index=True)
    base_ref: str
    head_ref: str
    patch_text: str
    changed_files_json: str = "[]"
    stats_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now)


class Review(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    artifact_id: str = Field(foreign_key="artifact.id", index=True)
    reviewed_diff_artifact_id: str = Field(foreign_key="artifact.id", index=True)
    reviewer_agent_id: Optional[str] = Field(default=None, foreign_key="agent.id")
    adapter_type: str
    status: str
    risk_level: str
    summary: str
    files_reviewed_json: str = "[]"
    findings_json: str = "[]"
    suggested_changes_json: str = "[]"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Preview(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    artifact_id: str = Field(foreign_key="artifact.id", index=True)
    port: int
    url: str
    command: str
    process_id: Optional[int] = None
    health_status: str
    status_reason: Optional[str] = None
    expires_at: Optional[datetime] = None
    last_checked_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Deployment(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    artifact_id: str = Field(foreign_key="artifact.id", index=True)
    provider: str
    environment: str
    commit_sha: Optional[str] = None
    url: Optional[str] = None
    status: str
    deploy_log_uri: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SessionExecutionLedger(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    session_id: str = Field(foreign_key="session.id", index=True, unique=True)
    current_goal: Optional[str] = None
    active_agents_json: str = "[]"
    latest_task_id: Optional[str] = Field(default=None, foreign_key="task.id")
    latest_task_run_id: Optional[str] = Field(default=None, foreign_key="taskrun.id")
    latest_diff_artifact_id: Optional[str] = Field(default=None, foreign_key="artifact.id")
    latest_changed_files_json: str = "[]"
    latest_preview_id: Optional[str] = Field(default=None, foreign_key="preview.id")
    latest_preview_url: Optional[str] = None
    latest_preview_health: Optional[str] = None
    latest_deployment_id: Optional[str] = Field(default=None, foreign_key="deployment.id")
    latest_deployment_provider: Optional[str] = None
    latest_deployment_status: Optional[str] = None
    last_successful_adapter: Optional[str] = None
    summary_md: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
