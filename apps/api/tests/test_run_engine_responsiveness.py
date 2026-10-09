import asyncio
from threading import Event, get_ident
from types import SimpleNamespace

import pytest

import app.run_engine as run_engine


@pytest.mark.anyio
async def test_scope_finalization_yields_to_other_requests(monkeypatch) -> None:
    entered, release = Event(), Event()
    loop_thread = get_ident()
    worker_threads = []
    refreshed = []
    task_run = SimpleNamespace(id="run")
    db = SimpleNamespace(refresh=lambda run: refreshed.append(run.id))

    def slow_finalization(current_db, current_run):
        assert current_db is db and current_run is task_run
        worker_threads.append(get_ident())
        entered.set()
        assert release.wait(3), "scope checks blocked the event loop"
        return False

    monkeypatch.setattr(run_engine, "_commit_adapter_completed_task_run", slow_finalization)
    operation = asyncio.create_task(run_engine.finalize_adapter_completed_task_run(db, task_run))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        # A second coroutine runs while the filesystem check remains blocked.
        await asyncio.sleep(0)
        assert not operation.done()
        assert worker_threads != [loop_thread]
        release.set()
        assert await operation is task_run
        assert refreshed == ["run"]
    finally:
        release.set()
        await asyncio.gather(operation, return_exceptions=True)


@pytest.mark.anyio
@pytest.mark.parametrize("worker_fails", [False, True])
async def test_cancelled_scope_step_drains_worker_before_session_reuse(worker_fails) -> None:
    entered, release, finished = Event(), Event(), Event()

    def blocking_session_operation():
        entered.set()
        try:
            assert release.wait(3)
            if worker_fails:
                raise RuntimeError("worker failure after cancellation")
            return "result"
        finally:
            finished.set()

    operation = asyncio.create_task(run_engine._run_sync_execution_step(blocking_session_operation))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        for _ in range(2):
            operation.cancel()
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            assert not operation.done()
            assert not finished.is_set()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await operation
        assert finished.is_set()
    finally:
        release.set()
        await asyncio.gather(operation, return_exceptions=True)


@pytest.mark.anyio
async def test_scope_step_preserves_validation_failure() -> None:
    def rejected():
        raise run_engine.TaskRunScopeError("TASK_RUN_SCOPE_VIOLATION", "blocked")

    with pytest.raises(run_engine.TaskRunScopeError) as exc:
        await run_engine._run_sync_execution_step(rejected)
    assert exc.value.error_code == "TASK_RUN_SCOPE_VIOLATION"
