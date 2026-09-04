import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import BackgroundTasks
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.models import Agent, Session, Task, TaskRun, TaskRunEvent, Workspace, utc_now
from app.run_engine import (
    BoundedRunDispatcher,
    DispatchClaim,
    _background_dispatch_queued_task_runs,
    schedule_task_run_execution,
)
from app.session_queue import enqueue_task_run, mark_task_run_running
from app.task_runs import (
    TaskRunLifecycleError,
    claim_task_run_for_worker,
    transition_task_run,
)


def test_shared_background_scheduler_uses_bounded_dispatcher() -> None:
    background_tasks = BackgroundTasks()

    schedule_task_run_execution(background_tasks)

    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].func is _background_dispatch_queued_task_runs


def test_bounded_dispatcher_overlaps_safe_readonly_adapter_intervals(
    tmp_path: Path,
) -> None:
    with dispatcher_db(tmp_path, "readonly-overlap") as (db, _):
        runs = seed_queued_runs(db, access_modes=("readonly", "readonly"))
        adapter = BlockingAdapterExecutor(expected_starts=2)
        dispatcher = BoundedRunDispatcher(
            dispatcher_id="dispatcher:readonly-overlap",
            max_concurrency=2,
            executor=adapter,
        )

        async def exercise() -> list[str]:
            dispatch = asyncio.create_task(dispatcher.run_once(db))
            await asyncio.wait_for(adapter.all_started.wait(), timeout=1)
            await asyncio.sleep(0.02)
            adapter.release.set()
            return await asyncio.wait_for(dispatch, timeout=1)

        dispatched = asyncio.run(exercise())

        assert set(dispatched) == {run.id for run in runs}
        assert len(adapter.intervals) == 2
        starts = [interval[0] for interval in adapter.intervals.values()]
        ends = [interval[1] for interval in adapter.intervals.values()]
        assert max(starts) < min(ends)


def test_bounded_dispatcher_preserves_same_session_write_serial_order(
    tmp_path: Path,
) -> None:
    with dispatcher_db(tmp_path, "write-serial") as (db, _):
        first, second = seed_queued_runs(db, access_modes=("write", "write"))
        adapter = SerialTerminalAdapterExecutor((first.id, second.id))
        dispatcher = BoundedRunDispatcher(
            dispatcher_id="dispatcher:write-serial",
            max_concurrency=2,
            executor=adapter,
        )

        async def exercise() -> tuple[list[str], list[str]]:
            first_dispatch = asyncio.create_task(dispatcher.run_once(db))
            await asyncio.wait_for(adapter.started[first.id].wait(), timeout=1)
            await asyncio.sleep(0)
            assert adapter.started[second.id].is_set() is False
            adapter.release[first.id].set()
            first_batch = await asyncio.wait_for(first_dispatch, timeout=1)

            second_dispatch = asyncio.create_task(dispatcher.run_once(db))
            await asyncio.wait_for(adapter.started[second.id].wait(), timeout=1)
            adapter.release[second.id].set()
            second_batch = await asyncio.wait_for(second_dispatch, timeout=1)
            return first_batch, second_batch

        first_batch, second_batch = asyncio.run(exercise())

        assert first_batch == [first.id]
        assert second_batch == [second.id]
        assert adapter.intervals[first.id][1] <= adapter.intervals[second.id][0]


def test_task_run_claim_has_one_persistent_winner(tmp_path: Path) -> None:
    with dispatcher_db(tmp_path, "atomic-claim") as (db, engine):
        run = seed_queued_runs(db, access_modes=("readonly",))[0]
        run_id = run.id

    def claim(worker_id: str) -> str:
        with DbSession(engine) as claim_db:
            try:
                claimed = claim_task_run_for_worker(
                    claim_db,
                    run_id,
                    worker_id=worker_id,
                )
            except TaskRunLifecycleError:
                return "lost"
            return claimed.runner_id or "missing"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(
            pool.map(claim, ("worker:atomic:first", "worker:atomic:second"))
        )

    winners = [outcome for outcome in outcomes if outcome != "lost"]
    assert len(winners) == 1
    with DbSession(engine) as evidence_db:
        stored = evidence_db.get(TaskRun, run_id)
        claim_events = evidence_db.exec(
            select(TaskRunEvent).where(
                TaskRunEvent.task_run_id == run_id,
                TaskRunEvent.event_type == "run.claimed",
            )
        ).all()
        assert stored is not None
        assert stored.runner_id == winners[0]
        assert len(claim_events) == 1


class BlockingAdapterExecutor:
    def __init__(self, *, expected_starts: int) -> None:
        self.expected_starts = expected_starts
        self.all_started = asyncio.Event()
        self.release = asyncio.Event()
        self.intervals: dict[str, list[float]] = {}

    async def __call__(self, bind, claim: DispatchClaim) -> bool:
        loop = asyncio.get_running_loop()
        self.intervals[claim.task_run_id] = [loop.time(), 0.0]
        if len(self.intervals) == self.expected_starts:
            self.all_started.set()
        await self.release.wait()
        self.intervals[claim.task_run_id][1] = loop.time()
        return True


class SerialTerminalAdapterExecutor:
    def __init__(self, task_run_ids: tuple[str, ...]) -> None:
        self.started = {task_run_id: asyncio.Event() for task_run_id in task_run_ids}
        self.release = {task_run_id: asyncio.Event() for task_run_id in task_run_ids}
        self.intervals: dict[str, list[float]] = {}

    async def __call__(self, bind, claim: DispatchClaim) -> bool:
        started = self.started[claim.task_run_id]
        release = self.release[claim.task_run_id]
        loop = asyncio.get_running_loop()
        with DbSession(bind) as execution_db:
            mark_task_run_running(
                execution_db,
                claim.task_run_id,
                "Blocking test adapter started.",
            )
        self.intervals[claim.task_run_id] = [loop.time(), 0.0]
        started.set()
        await release.wait()
        with DbSession(bind) as execution_db:
            transition_task_run(execution_db, claim.task_run_id, "completed")
        self.intervals[claim.task_run_id][1] = loop.time()
        return True


@contextmanager
def dispatcher_db(tmp_path: Path, name: str):
    database_path = tmp_path / f"{name}.db"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        yield db, engine
    engine.dispose()


def seed_queued_runs(
    db: DbSession,
    *,
    access_modes: tuple[str, ...],
) -> list[TaskRun]:
    workspace = Workspace(
        name=f"Dispatcher workspace {uuid4()}",
        repo_url="local://dispatcher-tests",
        root_path=".",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="Dispatcher session",
        bound_branch="main",
        worktree_path=f".worktrees/dispatcher-{uuid4()}",
    )
    agent = Agent(
        name="Dispatcher Test Agent",
        role=f"dispatcher-test-{uuid4()}",
        adapter_type="scripted_mock",
        provider="local",
    )
    db.add(workspace)
    db.add(session)
    db.add(agent)
    db.commit()

    runs: list[TaskRun] = []
    now = utc_now()
    for index, access_mode in enumerate(access_modes):
        read_only = access_mode == "readonly"
        task = Task(
            session_id=session.id,
            title=f"Dispatcher task {index + 1}",
            intent_type="review" if read_only else "frontend_change",
            status="running",
            priority=index,
            assigned_agent_id=agent.id,
            plan_json=json.dumps(
                {"readOnly": read_only, "writeMode": not read_only},
                separators=(",", ":"),
            ),
        )
        run = TaskRun(
            task_id=task.id,
            agent_id=agent.id,
            state="queued",
            runner_id=f"local:{uuid4()}",
            last_heartbeat_at=now,
            lease_expires_at=now + timedelta(minutes=5),
            worktree_path=session.worktree_path,
            metrics_json=json.dumps(
                {"adapterType": "scripted_mock"},
                separators=(",", ":"),
            ),
        )
        db.add(task)
        db.add(run)
        db.commit()
        db.refresh(task)
        db.refresh(run)
        enqueue_task_run(
            db,
            task=task,
            task_run=run,
            access_mode=access_mode,
            target_id=None,
        )
        runs.append(run)
    return runs
