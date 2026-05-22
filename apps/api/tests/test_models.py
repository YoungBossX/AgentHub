from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, select
from uuid import uuid4

from app.db import create_db_and_tables, engine
from app.models import (
    Agent,
    Artifact,
    Deployment,
    Diff,
    Message,
    Preview,
    Review,
    Session,
    SessionExecutionLedger,
    Task,
    TaskRun,
    TaskRunEvent,
    User,
    Workspace,
)
from app.repositories import get_demo_workspace, get_enabled_agents
from app.seed import seed_demo_data


EXPECTED_TABLES = {
    "agent",
    "artifact",
    "deployment",
    "diff",
    "message",
    "preview",
    "review",
    "session",
    "sessionexecutionledger",
    "task",
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
        Session: {
            "id",
            "workspace_id",
            "title",
            "session_type",
            "bound_branch",
            "worktree_path",
            "status",
            "last_message_at",
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


def test_message_create_request_defaults_are_preserved() -> None:
    from app.schemas import MessageCreateRequest

    req = MessageCreateRequest(contentMd="hello")
    assert req.sender_type == "user"
    assert req.message_kind == "chat"
    assert req.stream_state == "complete"


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
    assert data["createdAt"] == "2026-05-17T00:00:00Z"
    assert "task_id" not in data
    assert "created_at" not in data
