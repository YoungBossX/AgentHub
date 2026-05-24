import json
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import BackgroundTasks
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.main import auto_start_safe_tasks
from app.models import Agent, Session, Task, TaskRun, Workspace
from app.scheduler import (
    SCHEDULER_BLOCKED,
    SCHEDULER_READY,
    SCHEDULER_WAITING_DEPENDENCY,
    evaluate_and_apply_dependency_readiness,
    evaluate_dependency_readiness,
)
from app.task_runs import create_task_run, transition_task_run


def test_dependency_readiness_waits_until_upstream_task_completes() -> None:
    with scheduler_db() as db:
        _, _, upstream, downstream = seed_dependent_tasks(db)

        waiting = evaluate_dependency_readiness(db, downstream)
        assert waiting.state == SCHEDULER_WAITING_DEPENDENCY
        assert waiting.runnable is False
        assert waiting.blocking_dependency_ids == [upstream.id]

        upstream.status = "completed"
        db.add(upstream)
        db.commit()

        ready = evaluate_dependency_readiness(db, downstream)
        assert ready.state == SCHEDULER_READY
        assert ready.runnable is True
        assert ready.blocking_dependency_ids == []


def test_dependency_failure_blocks_downstream_task_with_visible_metadata() -> None:
    with scheduler_db() as db:
        _, _, upstream, downstream = seed_dependent_tasks(db)
        upstream.status = "failed"
        db.add(upstream)
        db.commit()

        decision = evaluate_and_apply_dependency_readiness(db, downstream)

        assert decision.state == SCHEDULER_BLOCKED
        assert decision.runnable is False

        stored = db.get(Task, downstream.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]
        assert stored.status == "blocked"
        assert scheduler["state"] == "blocked"
        assert scheduler["blockingDependencyIds"] == [upstream.id]


def test_auto_start_skips_task_with_incomplete_dependency() -> None:
    with scheduler_db() as db:
        _, _, upstream, downstream = seed_dependent_tasks(db, downstream_auto_start=True)

        auto_start_safe_tasks(db, [downstream], BackgroundTasks())

        runs = db.exec(select(TaskRun).where(TaskRun.task_id == downstream.id)).all()
        stored = db.get(Task, downstream.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]

        assert runs == []
        assert stored.status == "waiting_dependency"
        assert scheduler["state"] == "waiting_dependency"
        assert scheduler["blockingDependencyIds"] == [upstream.id]


def test_auto_start_runs_task_after_dependencies_complete() -> None:
    with scheduler_db() as db:
        _, _, upstream, downstream = seed_dependent_tasks(db, downstream_auto_start=True)
        upstream.status = "completed"
        db.add(upstream)
        db.commit()

        auto_start_safe_tasks(db, [downstream], BackgroundTasks())

        runs = db.exec(select(TaskRun).where(TaskRun.task_id == downstream.id)).all()
        stored = db.get(Task, downstream.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]

        assert len(runs) == 1
        assert runs[0].state == "queued"
        assert stored.status == "running"
        assert scheduler["state"] == "ready"
        assert scheduler["runnable"] is True


def test_terminal_upstream_transition_refreshes_downstream_scheduler_state() -> None:
    with scheduler_db() as db:
        _, _, upstream, downstream = seed_dependent_tasks(db)
        upstream_run = create_task_run(db, upstream.id)

        transition_task_run(
            db,
            upstream_run.id,
            "failed",
            error_code="TEST_FAILURE",
            error_message="Upstream failed in scheduler test.",
        )

        stored = db.get(Task, downstream.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]

        assert stored.status == "blocked"
        assert scheduler["state"] == "blocked"
        assert scheduler["blockingDependencyIds"] == [upstream.id]


@contextmanager
def scheduler_db() -> Iterator[DbSession]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        yield db


def seed_dependent_tasks(
    db: DbSession,
    *,
    downstream_auto_start: bool = False,
) -> tuple[Workspace, Session, Task, Task]:
    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="Scheduler session",
        bound_branch="main",
        worktree_path=".worktrees/scheduler-session",
    )
    frontend = Agent(
        name="Frontend Agent",
        role="frontend",
        adapter_type="codex",
        provider="local",
    )
    upstream = Task(
        session_id=session.id,
        title="Prepare upstream task",
        intent_type="planning",
        status="pending",
        priority=0,
        assigned_agent_id=frontend.id,
        plan_json=json.dumps({"planner": "scheduler_test"}, separators=(",", ":")),
    )
    downstream_plan = {
        "planner": "scheduler_test",
        "autoStart": downstream_auto_start,
        "safeTarget": "apps/demo/src",
        "files": ["apps/demo/src/App.tsx"],
    }
    downstream = Task(
        session_id=session.id,
        title="Run downstream frontend task",
        intent_type="frontend_change",
        status="pending",
        priority=1,
        assigned_agent_id=frontend.id,
        plan_json=json.dumps(downstream_plan, separators=(",", ":")),
        depends_on_task_ids=json.dumps([upstream.id], separators=(",", ":")),
    )
    db.add(workspace)
    db.add(session)
    db.add(frontend)
    db.add(upstream)
    db.add(downstream)
    db.commit()
    db.refresh(upstream)
    db.refresh(downstream)
    return workspace, session, upstream, downstream
