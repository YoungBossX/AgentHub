import json
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
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
    SCHEDULER_WAITING_TARGET_LOCK,
    evaluate_and_apply_dependency_readiness,
    evaluate_dependency_readiness,
)
from app.task_runs import TaskRunLifecycleError, create_task_run, transition_task_run
from app.target_registry import (
    AGENTHUB_PLATFORM_TARGET_ID,
    DEMO_BACKEND_TARGET_ID,
    DEMO_FRONTEND_TARGET_ID,
)


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


def test_same_frontend_target_write_task_waits_for_active_lock() -> None:
    with scheduler_db() as db:
        _, session, first, second = seed_same_target_write_tasks(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            intent_type="frontend_change",
            safe_target="apps/demo/src",
        )
        first_run = create_task_run(db, first.id)

        auto_start_safe_tasks(db, [second], BackgroundTasks())

        runs = db.exec(select(TaskRun).where(TaskRun.task_id == second.id)).all()
        stored = db.get(Task, second.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]

        assert session.id == stored.session_id
        assert runs == []
        assert stored.status == "waiting_target_lock"
        assert scheduler["state"] == SCHEDULER_WAITING_TARGET_LOCK
        assert scheduler["targetId"] == DEMO_FRONTEND_TARGET_ID
        assert scheduler["lockHolderTaskRunIds"] == [first_run.id]


def test_manual_start_fails_honestly_when_same_backend_target_lock_is_active() -> None:
    with scheduler_db() as db:
        _, _, first, second = seed_same_target_write_tasks(
            db,
            target_id=DEMO_BACKEND_TARGET_ID,
            intent_type="backend_change",
            safe_target="apps/demo-api",
        )
        first_run = create_task_run(db, first.id)

        with pytest.raises(TaskRunLifecycleError, match=DEMO_BACKEND_TARGET_ID):
            create_task_run(db, second.id)

        stored = db.get(Task, second.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]

        assert stored.status == "waiting_target_lock"
        assert scheduler["state"] == SCHEDULER_WAITING_TARGET_LOCK
        assert scheduler["targetId"] == DEMO_BACKEND_TARGET_ID
        assert scheduler["lockHolderTaskRunIds"] == [first_run.id]


def test_terminal_run_releases_target_lock_for_waiting_task() -> None:
    with scheduler_db() as db:
        _, _, first, second = seed_same_target_write_tasks(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            intent_type="frontend_change",
            safe_target="apps/demo/src",
        )
        first_run = create_task_run(db, first.id)
        auto_start_safe_tasks(db, [second], BackgroundTasks())

        transition_task_run(db, first_run.id, "completed")

        stored = db.get(Task, second.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]

        assert stored.status == "pending"
        assert scheduler["state"] == "ready"
        assert scheduler["targetId"] == DEMO_FRONTEND_TARGET_ID
        assert scheduler["lockHolderTaskRunIds"] == []


def test_read_only_review_task_does_not_acquire_target_write_lock() -> None:
    with scheduler_db() as db:
        _, session, first, _ = seed_same_target_write_tasks(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            intent_type="frontend_change",
            safe_target="apps/demo/src",
        )
        qa = Agent(name="QA Agent", role="qa", adapter_type="scripted_mock", provider="local")
        review = Task(
            session_id=session.id,
            title="Review frontend diff",
            intent_type="review",
            status="pending",
            assigned_agent_id=qa.id,
            plan_json=json.dumps(
                {
                    "targetId": DEMO_FRONTEND_TARGET_ID,
                    "safeTarget": "apps/demo/src",
                    "readOnly": True,
                },
                separators=(",", ":"),
            ),
        )
        db.add(qa)
        db.add(review)
        db.commit()
        db.refresh(review)
        create_task_run(db, first.id)

        review_run = create_task_run(db, review.id)

        assert review_run.state == "queued"


def test_ordinary_backend_task_cannot_acquire_platform_write_lock() -> None:
    with scheduler_db() as db:
        _, session, _, _ = seed_same_target_write_tasks(
            db,
            target_id=DEMO_BACKEND_TARGET_ID,
            intent_type="backend_change",
            safe_target="apps/demo-api",
        )
        backend = db.exec(select(Agent).where(Agent.role == "backend")).one()
        platform_task = Task(
            session_id=session.id,
            title="Unsafe platform write",
            intent_type="backend_change",
            status="pending",
            assigned_agent_id=backend.id,
            plan_json=json.dumps(
                {
                    "targetId": AGENTHUB_PLATFORM_TARGET_ID,
                    "safeTarget": "apps/api",
                },
                separators=(",", ":"),
            ),
        )
        db.add(platform_task)
        db.commit()
        db.refresh(platform_task)

        with pytest.raises(TaskRunLifecycleError, match="platform mode"):
            create_task_run(db, platform_task.id)

        stored = db.get(Task, platform_task.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]

        assert stored.status == "blocked"
        assert scheduler["state"] == "blocked"
        assert scheduler["targetId"] == AGENTHUB_PLATFORM_TARGET_ID


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


def seed_same_target_write_tasks(
    db: DbSession,
    *,
    target_id: str,
    intent_type: str,
    safe_target: str,
) -> tuple[Workspace, Session, Task, Task]:
    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="Lock session",
        bound_branch="main",
        worktree_path=".worktrees/lock-session",
    )
    role = "backend" if intent_type == "backend_change" else "frontend"
    agent = Agent(
        name=f"{role.title()} Agent",
        role=role,
        adapter_type="codex",
        provider="local",
    )
    files = (
        ["apps/demo/src/App.tsx"]
        if safe_target == "apps/demo/src"
        else ["apps/demo-api/app/main.py"]
    )
    plan = {
        "targetId": target_id,
        "safeTarget": safe_target,
        "autoStart": True,
        "files": files,
    }
    first = Task(
        session_id=session.id,
        title="First write",
        intent_type=intent_type,
        status="pending",
        assigned_agent_id=agent.id,
        plan_json=json.dumps(plan, separators=(",", ":")),
    )
    second = Task(
        session_id=session.id,
        title="Second write",
        intent_type=intent_type,
        status="pending",
        assigned_agent_id=agent.id,
        plan_json=json.dumps(plan, separators=(",", ":")),
    )
    db.add(workspace)
    db.add(session)
    db.add(agent)
    db.add(first)
    db.add(second)
    db.commit()
    db.refresh(first)
    db.refresh(second)
    return workspace, session, first, second
