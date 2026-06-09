from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select
from uuid import uuid4

from app.db import create_db_and_tables, engine, _ensure_sqlite_demo_schema_columns
from app.external_workspaces import list_external_project_targets
from app.models import (
    Agent,
    AgentProfileDraft,
    AgentRuntimeConfig,
    Artifact,
    ArtifactVersion,
    Deployment,
    Diff,
    ExternalProjectTarget,
    MemoryItem,
    MemorySnapshot,
    Message,
    Preview,
    PreviewDeployJob,
    Review,
    Session,
    SessionExecutionLedger,
    SessionQueueEntry,
    Task,
    TargetLock,
    TaskRun,
    TaskRunEvent,
    User,
    Workspace,
)
from app.repositories import get_demo_workspace, get_enabled_agents
from app.seed import seed_demo_data


EXPECTED_TABLES = {
    "agent",
    "agentprofiledraft",
    "agentruntimeconfig",
    "artifact",
    "artifactversion",
    "deployment",
    "diff",
    "externalprojecttarget",
    "memoryitem",
    "memorysnapshot",
    "message",
    "preview",
    "previewdeployjob",
    "review",
    "session",
    "sessionexecutionledger",
    "sessionqueueentry",
    "task",
    "targetlock",
    "taskrun",
    "taskrunevent",
    "user",
    "workspace",
}


def test_p0_model_boundary_and_required_fields() -> None:
    assert set(SQLModel.metadata.tables) == EXPECTED_TABLES

    expected_fields = {
        User: {"id", "email", "name", "avatar_url", "created_at"},
        Workspace: {"id", "name", "repo_url", "root_path", "default_branch", "created_at"},
        ExternalProjectTarget: {
            "id",
            "workspace_id",
            "target_id",
            "name",
            "root_path",
            "project_type",
            "allowed_paths_json",
            "denied_paths_json",
            "dev_command",
            "test_command",
            "check_command",
            "build_command",
            "preview_command",
            "staging_output_dir",
            "staging_serve_command",
            "deploy_provider_ids_json",
            "package_manager",
            "detected_framework",
            "analysis_status",
            "created_at",
            "updated_at",
        },
        Session: {
            "id",
            "workspace_id",
            "title",
            "session_type",
            "bound_branch",
            "worktree_path",
            "active_frontend_target_id",
            "active_backend_target_id",
            "memory_snapshot_id",
            "status",
            "last_message_at",
            "created_at",
            "updated_at",
        },
        MemorySnapshot: {
            "id",
            "workspace_id",
            "schema_version",
            "agents_md_hash",
            "claude_md_hash",
            "project_memory_version",
            "user_preference_version",
            "target_registry_version",
            "runtime_config_version",
            "context_pack_hash",
            "meta_json",
            "created_at",
        },
        MemoryItem: {
            "id",
            "workspace_id",
            "scope",
            "memory_type",
            "source",
            "status",
            "trust_level",
            "title",
            "content_md",
            "content_hash",
            "version",
            "importance",
            "target_ids_json",
            "agent_roles_json",
            "last_used_at",
            "superseded_by",
            "created_at",
            "updated_at",
        },
        Message: {
            "id",
            "session_id",
            "sender_type",
            "sender_id",
            "content_md",
            "message_kind",
            "parent_message_id",
            "stream_state",
            "context_json",
            "created_at",
        },
        Agent: {
            "id",
            "name",
            "role",
            "adapter_type",
            "provider",
            "default_model",
            "system_prompt",
            "capabilities_json",
            "permission_profile_json",
            "enabled",
            "created_at",
            "updated_at",
        },
        AgentProfileDraft: {
            "id",
            "workspace_id",
            "display_name",
            "avatar_initials",
            "role",
            "adapter_type",
            "provider_id",
            "capability_tags_json",
            "supported_targets_json",
            "supported_modes_json",
            "safe_for_write",
            "safe_for_review",
            "description",
            "status",
            "created_at",
            "updated_at",
        },
        AgentRuntimeConfig: {
            "id",
            "workspace_id",
            "scope",
            "roles_json",
            "created_at",
            "updated_at",
        },
        Task: {
            "id",
            "session_id",
            "created_by_message_id",
            "title",
            "intent_type",
            "status",
            "priority",
            "plan_json",
            "depends_on_task_ids",
            "assigned_agent_id",
            "created_at",
            "updated_at",
        },
        TaskRun: {
            "id",
            "task_id",
            "agent_id",
            "adapter_run_id",
            "state",
            "started_at",
            "ended_at",
            "runner_id",
            "last_heartbeat_at",
            "lease_expires_at",
            "stale_detected_at",
            "stale_reason",
            "worktree_path",
            "base_ref",
            "head_ref",
            "error_code",
            "error_message",
            "metrics_json",
            "created_at",
            "updated_at",
        },
        TaskRunEvent: {
            "id",
            "task_run_id",
            "event_type",
            "payload_json",
            "sequence",
            "created_at",
        },
        SessionQueueEntry: {
            "id",
            "session_id",
            "task_id",
            "task_run_id",
            "queue_kind",
            "access_mode",
            "target_id",
            "target_lock_key",
            "position",
            "state",
            "blocked_reason",
            "created_at",
            "started_at",
            "finished_at",
            "updated_at",
        },
        TargetLock: {
            "id",
            "lock_key",
            "target_id",
            "session_id",
            "task_run_id",
            "worker_id",
            "mode",
            "state",
            "lease_expires_at",
            "acquired_at",
            "released_at",
            "release_reason",
            "created_at",
            "updated_at",
        },
        PreviewDeployJob: {
            "id",
            "session_id",
            "source_task_run_id",
            "job_type",
            "state",
            "attempt",
            "port",
            "error_code",
            "evidence_json",
            "created_at",
            "started_at",
            "finished_at",
            "updated_at",
        },
        Artifact: {
            "id",
            "task_run_id",
            "artifact_type",
            "title",
            "status",
            "version",
            "storage_uri",
            "meta_json",
            "created_at",
            "updated_at",
        },
        ArtifactVersion: {
            "id",
            "artifact_id",
            "version",
            "parent_version_id",
            "source_task_run_id",
            "parent_artifact_id",
            "git_base_ref",
            "git_head_ref",
            "changed_files_json",
            "summary",
            "content_md",
            "content_hash",
            "editor_source",
            "created_at",
        },
        Diff: {
            "id",
            "artifact_id",
            "base_ref",
            "head_ref",
            "patch_text",
            "changed_files_json",
            "stats_json",
            "created_at",
        },
        Preview: {
            "id",
            "artifact_id",
            "port",
            "url",
            "command",
            "process_id",
            "health_status",
            "status_reason",
            "expires_at",
            "last_checked_at",
            "created_at",
            "updated_at",
        },
        Review: {
            "id",
            "artifact_id",
            "reviewed_diff_artifact_id",
            "reviewer_agent_id",
            "adapter_type",
            "status",
            "risk_level",
            "summary",
            "files_reviewed_json",
            "findings_json",
            "suggested_changes_json",
            "created_at",
            "updated_at",
        },
        Deployment: {
            "id",
            "artifact_id",
            "provider",
            "environment",
            "commit_sha",
            "url",
            "status",
            "deploy_log_uri",
            "created_at",
            "updated_at",
        },
        SessionExecutionLedger: {
            "id",
            "session_id",
            "current_goal",
            "active_agents_json",
            "latest_task_id",
            "latest_task_run_id",
            "latest_diff_artifact_id",
            "latest_changed_files_json",
            "latest_preview_id",
            "latest_preview_url",
            "latest_preview_health",
            "latest_deployment_id",
            "latest_deployment_provider",
            "latest_deployment_status",
            "last_successful_adapter",
            "summary_md",
            "created_at",
            "updated_at",
        },
    }

    for model, fields in expected_fields.items():
        assert set(model.model_fields) == fields


def test_sqlite_schema_compatibility_adds_external_target_staging_columns() -> None:
    legacy_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with legacy_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE externalprojecttarget (
                    id VARCHAR NOT NULL PRIMARY KEY,
                    workspace_id VARCHAR NOT NULL,
                    target_id VARCHAR NOT NULL,
                    name VARCHAR NOT NULL,
                    root_path VARCHAR NOT NULL,
                    project_type VARCHAR NOT NULL,
                    allowed_paths_json VARCHAR NOT NULL,
                    denied_paths_json VARCHAR NOT NULL,
                    dev_command VARCHAR,
                    test_command VARCHAR,
                    check_command VARCHAR,
                    build_command VARCHAR,
                    preview_command VARCHAR,
                    package_manager VARCHAR,
                    detected_framework VARCHAR,
                    analysis_status VARCHAR NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO externalprojecttarget (
                    id,
                    workspace_id,
                    target_id,
                    name,
                    root_path,
                    project_type,
                    allowed_paths_json,
                    denied_paths_json,
                    analysis_status,
                    created_at,
                    updated_at
                ) VALUES (
                    'legacy-target-row',
                    'workspace-1',
                    'external-legacy-target',
                    'Legacy Target',
                    '/tmp/legacy-target',
                    'vite-react',
                    '["src"]',
                    '[".env"]',
                    'manual',
                    '2026-05-31 00:00:00.000000',
                    '2026-05-31 00:00:00.000000'
                )
                """
            )
        )

    _ensure_sqlite_demo_schema_columns(legacy_engine)

    with DbSession(legacy_engine) as db:
        targets = list_external_project_targets(db, "workspace-1")

    assert len(targets) == 1
    assert targets[0].staging_output_dir is None
    assert targets[0].staging_serve_command is None
    assert targets[0].deploy_provider_ids_json == "[]"


def test_sqlite_schema_compatibility_adds_artifact_version_edit_columns() -> None:
    legacy_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with legacy_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE artifactversion (
                    id VARCHAR NOT NULL PRIMARY KEY,
                    artifact_id VARCHAR NOT NULL,
                    version INTEGER NOT NULL,
                    source_task_run_id VARCHAR,
                    parent_artifact_id VARCHAR,
                    git_base_ref VARCHAR,
                    git_head_ref VARCHAR,
                    changed_files_json VARCHAR NOT NULL,
                    summary VARCHAR NOT NULL,
                    created_at DATETIME NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO artifactversion (
                    id,
                    artifact_id,
                    version,
                    changed_files_json,
                    summary,
                    created_at
                ) VALUES (
                    'legacy-version-row',
                    'artifact-1',
                    1,
                    '[]',
                    'Legacy version',
                    '2026-06-08 00:00:00.000000'
                )
                """
            )
        )

    _ensure_sqlite_demo_schema_columns(legacy_engine)

    with legacy_engine.connect() as connection:
        columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(artifactversion)"))
        }
        row = connection.execute(
            text(
                """
                SELECT parent_version_id, content_md, content_hash, editor_source
                FROM artifactversion
                WHERE id = 'legacy-version-row'
                """
            )
        ).one()

    assert {"parent_version_id", "content_md", "content_hash", "editor_source"} <= columns
    assert row == (None, "", "", "system")


def test_seed_records_are_queryable() -> None:
    create_db_and_tables()
    with DbSession(engine) as db:
        seed_demo_data(db)

        workspace = get_demo_workspace(db)
        assert workspace.root_path == "apps/demo"

        agents = get_enabled_agents(db)
        assert {agent.role for agent in agents} == {
            "orchestrator",
            "frontend",
            "backend",
            "qa",
        }


def test_repository_smoke_creates_p0_run_chain() -> None:
    create_db_and_tables()
    with DbSession(engine) as db:
        seed_demo_data(db)
        workspace = db.exec(select(Workspace).where(Workspace.name == "AgentHub Demo")).one()
        agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        suffix = uuid4()

        session = Session(
            workspace_id=workspace.id,
            title="Smoke session",
            session_type="demo",
            bound_branch="main",
            worktree_path=f".worktrees/smoke-session-{suffix}",
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        message = Message(
            session_id=session.id,
            sender_type="user",
            content_md="@frontend create a card",
        )
        db.add(message)
        db.commit()
        db.refresh(message)

        task = Task(
            session_id=session.id,
            created_by_message_id=message.id,
            title="Create card",
            intent_type="frontend_change",
            assigned_agent_id=agent.id,
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        task_run = TaskRun(
            task_id=task.id,
            agent_id=agent.id,
            state="created",
            worktree_path=session.worktree_path,
            base_ref="HEAD",
            head_ref="working-tree",
        )
        db.add(task_run)
        db.commit()
        db.refresh(task_run)

        event = TaskRunEvent(
            task_run_id=task_run.id,
            event_type="task.state",
            payload_json='{"state":"created"}',
            sequence=1,
        )
        artifact = Artifact(
            task_run_id=task_run.id,
            artifact_type="diff",
            title="Smoke diff",
            status="ready",
        )
        db.add(event)
        db.add(artifact)
        db.commit()
        db.refresh(event)
        db.refresh(artifact)

        assert event.task_run_id == task_run.id
        assert artifact.task_run_id == task_run.id


def test_workspace_response_aliases_serialize_correctly() -> None:
    from datetime import datetime, timezone
    from app.schemas import WorkspaceResponse

    now = datetime(2026, 5, 17, 0, 0, 0, tzinfo=timezone.utc)
    ws = WorkspaceResponse(
        id="ws-1",
        name="Demo",
        repoUrl="local://demo",
        rootPath="apps/demo",
        defaultBranch="main",
        createdAt=now,
    )
    data = ws.model_dump(by_alias=True, mode="json")
    assert data["repoUrl"] == "local://demo"
    assert data["rootPath"] == "apps/demo"
    assert data["defaultBranch"] == "main"
    assert data["createdAt"] == "2026-05-17T00:00:00Z"
    assert "repo_url" not in data
    assert "root_path" not in data


def test_message_create_request_populates_by_alias() -> None:
    from app.schemas import MessageCreateRequest

    req = MessageCreateRequest(contentMd="@orchestrator build a login page")
    assert req.content_md == "@orchestrator build a login page"

    data = req.model_dump(by_alias=True)
    assert data["contentMd"] == "@orchestrator build a login page"
    assert data["senderType"] == "user"
    assert data["context"] == {}


def test_message_create_request_defaults_are_preserved() -> None:
    from app.schemas import MessageCreateRequest

    req = MessageCreateRequest(contentMd="hello")
    assert req.sender_type == "user"
    assert req.message_kind == "chat"
    assert req.stream_state == "complete"
    assert req.context == {}


def test_task_run_response_uses_camelcase_aliases() -> None:
    from datetime import datetime, timezone
    from app.schemas import TaskRunResponse

    now = datetime(2026, 5, 17, 0, 0, 0, tzinfo=timezone.utc)
    tr = TaskRunResponse.model_construct(
        id="run-1",
        taskId="task-1",
        sessionId="session-1",
        agentId="agent-1",
        adapterType="codex",
        state="queued",
        worktreePath="/tmp/wt",
        metricsJson={},
        createdAt=now,
        updatedAt=now,
    )
    data = tr.model_dump(by_alias=True, mode="json")
    assert data["taskId"] == "task-1"
    assert data["adapterType"] == "codex"
    assert data["worktreePath"] == "/tmp/wt"
    assert "runnerId" in data
    assert "lastHeartbeatAt" in data
    assert "leaseExpiresAt" in data
    assert "staleDetectedAt" in data
    assert "staleReason" in data
    assert data["createdAt"] == "2026-05-17T00:00:00Z"
    assert "task_id" not in data
    assert "created_at" not in data
