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
    Session,
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
    "session",
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
