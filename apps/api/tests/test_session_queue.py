import json
from collections.abc import Iterator
from contextlib import contextmanager

import app.session_queue as session_queue_module
import app.task_runs as task_runs_module
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.models import (
    Agent,
    Session,
    SessionQueueEntry,
    Task,
    TaskRun,
    TaskRunEvent,
    Workspace,
)
from app.scheduler import SCHEDULER_READY
from app.session_queue import entry_for_task_run, queue_gate_for_task_run, recover_queue_entries
from app.task_runs import create_task_run, transition_task_run
from app.target_registry import DEMO_FRONTEND_TARGET_ID


def test_write_task_runs_enqueue_with_fifo_positions() -> None:
    with queue_db() as db:
        _, _, first, second = seed_queue_tasks(db)

        first_run = create_task_run(db, first.id)
        second_run = create_task_run(db, second.id)

        first_entry = entry_for_task_run(db, first_run.id)
        second_entry = entry_for_task_run(db, second_run.id)

        assert first_entry.position == 1
        assert first_entry.access_mode == "write"
        assert first_entry.target_id == DEMO_FRONTEND_TARGET_ID
        assert first_entry.target_lock_key == f"target:{DEMO_FRONTEND_TARGET_ID}:write"
        assert second_entry.position == 2
        assert second_entry.state == "waiting_lock"


def test_same_session_write_queue_blocks_until_prior_write_terminal() -> None:
    with queue_db() as db:
        _, _, first, second = seed_queue_tasks(db)
        first_run = create_task_run(db, first.id)
        second_run = create_task_run(db, second.id)

        blocked = queue_gate_for_task_run(db, second_run.id)
        assert blocked.runnable is False
        assert blocked.blocking_task_run_ids == [first_run.id]

        transition_task_run(db, first_run.id, "completed")

        ready = queue_gate_for_task_run(db, second_run.id)
        stored_second = db.get(Task, second.id)
        scheduler = json.loads(stored_second.plan_json)["scheduler"]
        assert ready.runnable is True
        assert scheduler["state"] == SCHEDULER_READY


def test_readonly_task_can_run_while_same_session_write_is_queued(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_runs_module,
        "CAPABILITIES_BY_ADAPTER",
        {
            **task_runs_module.CAPABILITIES_BY_ADAPTER,
            "scripted_mock": ("review",),
        },
    )
    with queue_db() as db:
        workspace, session, first, unused_second = seed_queue_tasks(db)
        db.delete(unused_second)
        db.commit()
        qa = Agent(name="QA Agent", role="qa", adapter_type="scripted_mock", provider="local")
        review = Task(
            session_id=session.id,
            title="Review diff",
            intent_type="review",
            status="pending",
            assigned_agent_id=qa.id,
            plan_json=json.dumps(
                {"targetId": DEMO_FRONTEND_TARGET_ID, "readOnly": True},
                separators=(",", ":"),
            ),
        )
        db.add(qa)
        db.add(review)
        db.commit()
        db.refresh(review)

        create_task_run(db, first.id)
        review_run = create_task_run(db, review.id)

        review_entry = entry_for_task_run(db, review_run.id)
        gate = queue_gate_for_task_run(db, review_run.id)
        assert workspace.id == session.workspace_id
        assert review_entry.access_mode == "readonly"
        assert gate.runnable is True


def test_recovery_keeps_terminal_task_run_from_becoming_runnable() -> None:
    with queue_db() as db:
        run_id = seed_terminal_queue_run(db)

        recovered = recover_queue_entries(db)
        gate = queue_gate_for_task_run(db, run_id)
        stored_entry = entry_for_task_run(db, run_id)
        stored_run = db.get(TaskRun, run_id)

        assert [entry.task_run_id for entry in recovered] == [run_id]
        assert stored_run.state == "completed"
        assert stored_entry.state == "completed"
        assert gate.runnable is False


def test_queue_recovery_event_failure_rolls_back_before_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with queue_db() as db:
        run_id = seed_terminal_queue_run(db)
        failure_injected = False
        original_flush = db.flush

        def fail_advanced_event_once(objects=None) -> None:
            nonlocal failure_injected
            has_advanced_event = any(
                isinstance(item, TaskRunEvent)
                and item.event_type == "session_queue.advanced"
                for item in db.new
            )
            if has_advanced_event and not failure_injected:
                failure_injected = True
                raise RuntimeError("injected queue event insertion failure")
            original_flush(objects)

        monkeypatch.setattr(db, "flush", fail_advanced_event_once)
        with pytest.raises(
            RuntimeError,
            match="injected queue event insertion failure",
        ):
            recover_queue_entries(db)

        rolled_back_entry = entry_for_task_run(db, run_id)
        rolled_back_events = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == run_id)
            .where(TaskRunEvent.event_type == "session_queue.advanced")
        ).all()
        rolled_back_state = rolled_back_entry.state
        rolled_back_event_count = len(rolled_back_events)
        recovered = recover_queue_entries(db)
        durable_entry = entry_for_task_run(db, run_id)
        durable_events = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == run_id)
            .where(TaskRunEvent.event_type == "session_queue.advanced")
        ).all()

        assert failure_injected is True
        assert rolled_back_state == "running"
        assert rolled_back_event_count == 0
        assert [entry.task_run_id for entry in recovered] == [run_id]
        assert durable_entry.state == "completed"
        assert len(durable_events) == 1


def test_queue_recovery_publication_failure_is_noncritical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with queue_db() as db:
        run_id = seed_terminal_queue_run(db)
        publication_attempts: list[str] = []

        def fail_publication(db_arg, event) -> None:
            publication_attempts.append(event.event_type)
            raise RuntimeError("injected queue event publication failure")

        monkeypatch.setattr(
            session_queue_module,
            "publish_task_run_event",
            fail_publication,
        )
        recovered = recover_queue_entries(db)
        durable_entry = entry_for_task_run(db, run_id)
        durable_events = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == run_id)
            .where(TaskRunEvent.event_type == "session_queue.advanced")
        ).all()

        assert publication_attempts == ["session_queue.advanced"]
        assert [entry.task_run_id for entry in recovered] == [run_id]
        assert durable_entry.state == "completed"
        assert len(durable_events) == 1


@contextmanager
def queue_db() -> Iterator[DbSession]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        yield db


def seed_terminal_queue_run(db: DbSession) -> str:
    _, session, first, _ = seed_queue_tasks(db)
    task_run = TaskRun(
        task_id=first.id,
        agent_id=first.assigned_agent_id,
        state="completed",
        worktree_path=session.worktree_path,
    )
    entry = SessionQueueEntry(
        session_id=session.id,
        task_id=first.id,
        task_run_id=task_run.id,
        access_mode="write",
        target_id=DEMO_FRONTEND_TARGET_ID,
        target_lock_key=f"target:{DEMO_FRONTEND_TARGET_ID}:write",
        position=1,
        state="running",
    )
    db.add(entry)
    db.add(task_run)
    db.commit()
    return task_run.id


def seed_queue_tasks(db: DbSession) -> tuple[Workspace, Session, Task, Task]:
    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="Queue session",
        bound_branch="main",
        worktree_path=".worktrees/queue-session",
    )
    frontend = Agent(
        name="Frontend Agent",
        role="frontend",
        adapter_type="codex",
        provider="local",
    )
    plan = {
        "targetId": DEMO_FRONTEND_TARGET_ID,
        "safeTarget": "apps/demo/src",
        "autoStart": True,
        "files": ["apps/demo/src/App.tsx"],
    }
    first = Task(
        session_id=session.id,
        title="First write",
        intent_type="frontend_change",
        status="pending",
        priority=0,
        assigned_agent_id=frontend.id,
        plan_json=json.dumps(plan, separators=(",", ":")),
    )
    second = Task(
        session_id=session.id,
        title="Second write",
        intent_type="frontend_change",
        status="pending",
        priority=1,
        assigned_agent_id=frontend.id,
        plan_json=json.dumps(plan, separators=(",", ":")),
    )
    db.add(workspace)
    db.add(session)
    db.add(frontend)
    db.add(first)
    db.add(second)
    db.commit()
    db.refresh(first)
    db.refresh(second)
    return workspace, session, first, second
