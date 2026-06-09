import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta

from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine
from sqlmodel import select

from app.models import Agent, Session, Task, TaskRun, Workspace, utc_now
from app.target_locks import (
    acquire_target_lock,
    held_lock_for_target,
    recover_stale_target_locks,
    release_target_lock_for_task_run,
)
from app.task_runs import claim_task_run_for_worker, create_task_run
from app.target_registry import DEMO_BACKEND_TARGET_ID, DEMO_FRONTEND_TARGET_ID


def test_target_lock_allows_different_targets_concurrently() -> None:
    with lock_db() as db:
        first_session, first_run = seed_lock_run(
            db,
            session_title="First session",
            target_id=DEMO_FRONTEND_TARGET_ID,
        )
        second_session, second_run = seed_lock_run(
            db,
            session_title="Second session",
            target_id=DEMO_BACKEND_TARGET_ID,
        )
        first_run = claim_task_run_for_worker(db, first_run.id, worker_id="worker:first")
        second_run = claim_task_run_for_worker(db, second_run.id, worker_id="worker:second")

        first = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=first_session.id,
            task_run_id=first_run.id,
            worker_id="worker:first",
            lease_expires_at=first_run.lease_expires_at,
        )
        second = acquire_target_lock(
            db,
            target_id=DEMO_BACKEND_TARGET_ID,
            session_id=second_session.id,
            task_run_id=second_run.id,
            worker_id="worker:second",
            lease_expires_at=second_run.lease_expires_at,
        )

        assert first.acquired is True
        assert second.acquired is True


def test_target_lock_acquire_blocks_second_holder_until_release() -> None:
    with lock_db() as db:
        first_session, first_run = seed_lock_run(db, session_title="First session")
        second_session, second_run = seed_lock_run(db, session_title="Second session")
        first_run = claim_task_run_for_worker(db, first_run.id, worker_id="worker:first")
        second_run = claim_task_run_for_worker(db, second_run.id, worker_id="worker:second")

        first = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=first_session.id,
            task_run_id=first_run.id,
            worker_id="worker:first",
            lease_expires_at=first_run.lease_expires_at,
        )
        second = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=second_session.id,
            task_run_id=second_run.id,
            worker_id="worker:second",
            lease_expires_at=second_run.lease_expires_at,
        )

        assert first.acquired is True
        assert second.acquired is False
        assert second.holder_task_run_id == first_run.id

        release_target_lock_for_task_run(
            db,
            task_run_id=first_run.id,
            session_id=first_session.id,
            release_reason="test_complete",
        )
        retried = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=second_session.id,
            task_run_id=second_run.id,
            worker_id="worker:second",
            lease_expires_at=second_run.lease_expires_at,
        )
        assert retried.acquired is True


def test_target_lock_release_is_idempotent_and_holder_scoped() -> None:
    with lock_db() as db:
        first_session, first_run = seed_lock_run(db, session_title="First session")
        second_session, second_run = seed_lock_run(db, session_title="Second session")
        first_run = claim_task_run_for_worker(db, first_run.id, worker_id="worker:first")
        second_run = claim_task_run_for_worker(db, second_run.id, worker_id="worker:second")
        acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=first_session.id,
            task_run_id=first_run.id,
            worker_id="worker:first",
            lease_expires_at=first_run.lease_expires_at,
        )

        mismatch = release_target_lock_for_task_run(
            db,
            task_run_id=second_run.id,
            session_id=second_session.id,
            release_reason="wrong_holder",
        )
        held = held_lock_for_target(db, DEMO_FRONTEND_TARGET_ID)
        released = release_target_lock_for_task_run(
            db,
            task_run_id=first_run.id,
            session_id=first_session.id,
            release_reason="owner_complete",
        )
        duplicate = release_target_lock_for_task_run(
            db,
            task_run_id=first_run.id,
            session_id=first_session.id,
            release_reason="duplicate",
        )

        assert mismatch is None
        assert held.task_run_id == first_run.id
        assert released.release_reason == "owner_complete"
        assert duplicate is None


def test_recover_stale_lock_fails_uncertain_holder_without_claiming_success() -> None:
    with lock_db() as db:
        session, run = seed_lock_run(db, session_title="Stale session")
        run = claim_task_run_for_worker(db, run.id, worker_id="worker:stale")
        lock_result = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=session.id,
            task_run_id=run.id,
            worker_id="worker:stale",
            lease_expires_at=run.lease_expires_at,
        )
        run.lease_expires_at = utc_now() - timedelta(minutes=1)
        lock_result.lock.lease_expires_at = run.lease_expires_at
        db.add(run)
        db.add(lock_result.lock)
        db.commit()

        recovered = recover_stale_target_locks(db)

        stored_run = db.get(TaskRun, run.id)
        assert [lock.lock_key for lock in recovered] == [f"target:{DEMO_FRONTEND_TARGET_ID}:write"]
        assert stored_run.state == "failed"
        assert stored_run.error_code == "TASK_RUN_STALE"
        assert stored_run.error_message
        assert "success" not in stored_run.error_message.lower()


@contextmanager
def lock_db() -> Iterator[DbSession]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        yield db


def seed_lock_run(
    db: DbSession,
    *,
    session_title: str,
    target_id: str = DEMO_FRONTEND_TARGET_ID,
) -> tuple[Session, TaskRun]:
    role = "backend" if target_id == DEMO_BACKEND_TARGET_ID else "frontend"
    intent_type = "backend_change" if target_id == DEMO_BACKEND_TARGET_ID else "frontend_change"
    safe_target = "apps/demo-api/app" if target_id == DEMO_BACKEND_TARGET_ID else "apps/demo/src"
    workspace = Workspace(
        name=session_title,
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title=session_title,
        bound_branch="main",
        worktree_path=f".worktrees/{session_title.lower().replace(' ', '-')}",
    )
    agent = db.exec(select(Agent).where(Agent.role == role)).first()
    if agent is None:
        agent = Agent(
            name=f"{role.title()} Agent",
            role=role,
            adapter_type="codex",
            provider="local",
        )
        db.add(agent)
    task = Task(
        session_id=session.id,
        title=f"{session_title} write",
        intent_type=intent_type,
        status="pending",
        assigned_agent_id=agent.id,
        plan_json=json.dumps(
            {
                "targetId": target_id,
                "safeTarget": safe_target,
                "files": [f"{safe_target}/main.py"],
            },
            separators=(",", ":"),
        ),
    )
    db.add(workspace)
    db.add(session)
    db.add(task)
    db.commit()
    db.refresh(session)
    db.refresh(task)
    return session, create_task_run(db, task.id)
