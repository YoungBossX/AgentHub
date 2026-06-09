import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta

from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.models import Agent, Session, Task, TaskRun, TaskRunEvent, Workspace
from app.models import utc_now
from app.recovery import (
    mark_stale_task_failed,
    release_stale_lock,
    resume_downstream_pipeline,
    retry_from_checkpoint,
    retry_from_current_state,
    stop_downstream_pipeline,
)
from app.task_runs import create_task_run, transition_task_run
from app.target_locks import acquire_target_lock
from app.target_registry import DEMO_FRONTEND_TARGET_ID


def test_recovery_mark_stale_task_failed_records_audit_event() -> None:
    with recovery_db() as db:
        _, _, task, _ = seed_recovery_tasks(db)
        task_run = create_task_run(db, task.id)
        task_run.lease_expires_at = utc_now() - timedelta(minutes=1)
        db.add(task_run)
        db.commit()

        recovered = mark_stale_task_failed(
            db,
            task_run.id,
            actor="test",
            reason="stale rehearsal",
        )

        event = latest_recovery_event(db, recovered.id)
        payload = json.loads(event.payload_json)

        assert recovered.state == "failed"
        assert recovered.error_code == "TASK_RUN_STALE"
        assert payload["action"] == "mark_stale_task_failed"
        assert payload["actor"] == "test"
        assert payload["reason"] == "stale rehearsal"


def test_recovery_release_stale_lock_records_audit_event_and_unblocks_waiter() -> None:
    with recovery_db() as db:
        _, _, first, second = seed_recovery_tasks(db)
        second.depends_on_task_ids = "[]"
        db.add(second)
        db.commit()
        first_run = create_task_run(db, first.id)
        first_run.lease_expires_at = utc_now() - timedelta(minutes=1)
        db.add(first_run)
        db.commit()
        acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=first.session_id,
            task_run_id=first_run.id,
            worker_id="worker:recovery-test",
            lease_expires_at=first_run.lease_expires_at,
        )
        try:
            create_task_run(db, second.id)
        except ValueError:
            pass

        released = release_stale_lock(
            db,
            first_run.id,
            actor="test",
            reason="release stale lock",
        )

        event = latest_recovery_event(db, first_run.id)
        payload = json.loads(event.payload_json)

        assert released["taskRunId"] == first_run.id
        assert payload["action"] == "release_stale_lock"
        assert payload["targetId"] == DEMO_FRONTEND_TARGET_ID


def test_recovery_retry_actions_create_traceable_runs() -> None:
    with recovery_db() as db:
        _, _, task, _ = seed_recovery_tasks(db)
        task_run = create_task_run(db, task.id)
        transition_task_run(
            db,
            task_run.id,
            "failed",
            error_code="CODEX_TEST_FAILURE",
            error_message="Codex failed.",
        )

        current_retry = retry_from_current_state(db, task_run.id, actor="test")
        transition_task_run(db, current_retry.id, "failed", error_code="RETRY_FAILED")
        checkpoint_retry = retry_from_checkpoint(db, current_retry.id, actor="test")

        current_event = latest_recovery_event(db, current_retry.id)
        checkpoint_event = latest_recovery_event(db, checkpoint_retry.id)

        assert json.loads(current_retry.metrics_json)["retryMode"] == "current_state"
        assert json.loads(checkpoint_retry.metrics_json)["retryMode"] == "checkpoint"
        assert json.loads(current_event.payload_json)["action"] == "retry_from_current_state"
        assert json.loads(checkpoint_event.payload_json)["action"] == "retry_from_checkpoint"


def test_recovery_stop_and_resume_downstream_pipeline_records_events() -> None:
    with recovery_db() as db:
        _, _, upstream, downstream = seed_recovery_tasks(db)
        upstream_run = create_task_run(db, upstream.id)

        stopped = stop_downstream_pipeline(
            db,
            upstream.id,
            actor="test",
            reason="pause downstream",
        )

        stopped_downstream = db.get(Task, downstream.id)
        stop_event = latest_recovery_event(db, upstream_run.id)
        stop_payload = json.loads(stop_event.payload_json)

        assert [task.id for task in stopped] == [downstream.id]
        assert stopped_downstream.status == "blocked"
        assert stop_payload["action"] == "stop_downstream_pipeline"

        transition_task_run(db, upstream_run.id, "completed")
        resumed = resume_downstream_pipeline(
            db,
            upstream.id,
            actor="test",
            reason="resume downstream",
        )

        resumed_downstream = db.get(Task, downstream.id)
        resume_event = latest_recovery_event(db, upstream_run.id)
        resume_payload = json.loads(resume_event.payload_json)

        assert [task.id for task in resumed] == [downstream.id]
        assert resumed_downstream.status == "pending"
        assert resume_payload["action"] == "resume_downstream_pipeline"


def latest_recovery_event(db: DbSession, task_run_id: str) -> TaskRunEvent:
    return db.exec(
        select(TaskRunEvent)
        .where(TaskRunEvent.task_run_id == task_run_id)
        .where(TaskRunEvent.event_type == "recovery.action")
        .order_by(TaskRunEvent.sequence.desc())
    ).first()


@contextmanager
def recovery_db() -> Iterator[DbSession]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        yield db


def seed_recovery_tasks(db: DbSession) -> tuple[Workspace, Session, Task, Task]:
    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="Recovery session",
        bound_branch="main",
        worktree_path=".worktrees/recovery-session",
    )
    agent = Agent(
        name="Frontend Agent",
        role="frontend",
        adapter_type="codex",
        provider="local",
    )
    plan = {
        "targetId": DEMO_FRONTEND_TARGET_ID,
        "safeTarget": "apps/demo/src",
        "files": ["apps/demo/src/App.tsx"],
    }
    upstream = Task(
        session_id=session.id,
        title="Upstream write",
        intent_type="frontend_change",
        status="pending",
        assigned_agent_id=agent.id,
        plan_json=json.dumps(plan, separators=(",", ":")),
    )
    downstream = Task(
        session_id=session.id,
        title="Downstream write",
        intent_type="frontend_change",
        status="pending",
        assigned_agent_id=agent.id,
        plan_json=json.dumps(plan, separators=(",", ":")),
        depends_on_task_ids=json.dumps([upstream.id], separators=(",", ":")),
    )
    db.add(workspace)
    db.add(session)
    db.add(agent)
    db.add(upstream)
    db.add(downstream)
    db.commit()
    db.refresh(upstream)
    db.refresh(downstream)
    return workspace, session, upstream, downstream
