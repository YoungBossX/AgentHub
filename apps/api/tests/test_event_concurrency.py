"""Real independent SQLite writers, rollback and durable cursor replay."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import multiprocessing
from threading import Barrier

import pytest
from sqlalchemy import event
from sqlmodel import Session as DbSession, SQLModel, select

from app import events
from app.db_engine import create_runtime_engine
from app.models import Agent, Session, Task, TaskRun, TaskRunEvent, Workspace


def database(tmp_path, **connect_args):
    url = 'sqlite:///' + (tmp_path / 'events.sqlite3').as_posix()
    engine = create_runtime_engine(url, connect_args=connect_args)
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        workspace = Workspace(name='events', repo_url='local://', root_path='.', default_branch='main')
        agent = Agent(name='events', role='frontend', adapter_type='scripted_mock', provider='local')
        db.add(workspace)
        db.flush([workspace])
        db.add(agent)
        db.flush()
        session = Session(workspace_id=workspace.id, title='events', bound_branch='main', worktree_path='events-worktree')
        db.add(session)
        db.flush()
        task = Task(session_id=session.id, title='events', intent_type='frontend_change', assigned_agent_id=agent.id)
        db.add(task)
        db.flush()
        run = TaskRun(task_id=task.id, agent_id=agent.id, state='queued', worktree_path=session.worktree_path)
        db.add(run)
        db.flush()
        identifiers = session.id, run.id
        db.commit()
    return engine, identifiers


def test_independent_connections_append_unique_sequences(tmp_path):
    engine, (_, run_id) = database(tmp_path)
    entry, unlocked_reads = Barrier(2), Barrier(2)

    def force_old_race(connection, cursor, sql, *args):
        if sql.lower().startswith('select max(taskrunevent.sequence)') and not connection.connection.driver_connection.in_transaction:
            unlocked_reads.wait(timeout=3)

    event.listen(engine, 'after_cursor_execute', force_old_race)

    def append():
        with DbSession(engine) as db:
            entry.wait(timeout=3)
            return events.append_task_run_event(db, run_id, 'test').sequence

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(append) for _ in range(2)]
        assert sorted(f.result(timeout=10) for f in futures) == [1, 2]
    engine.dispose()


def _append_process(url, run_id, barrier, output):
    engine = create_runtime_engine(url)
    try:
        with DbSession(engine) as db:
            barrier.wait(timeout=10)
            output.put(('ok', events.append_task_run_event(db, run_id, 'process').sequence))
    except BaseException as exc:
        output.put(('error', type(exc).__name__))
    finally:
        engine.dispose()


def test_spawned_processes_append_without_shared_python_lock(tmp_path):
    engine, (_, run_id) = database(tmp_path)
    context = multiprocessing.get_context('spawn')
    barrier, output = context.Barrier(2), context.Queue()
    processes = [context.Process(target=_append_process, args=(str(engine.url), run_id, barrier, output)) for _ in range(2)]
    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=20)
        assert all(p.exitcode == 0 for p in processes)
        assert sorted(output.get(timeout=2) for _ in processes) == [('ok', 1), ('ok', 2)]
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        output.close()
        engine.dispose()


def test_staged_state_and_events_rollback_together(tmp_path, monkeypatch):
    engine, (_, run_id) = database(tmp_path)
    notifications = []
    monkeypatch.setattr(events, 'publish_event', lambda *args: notifications.append(args))
    with DbSession(engine) as db:
        run = db.get(TaskRun, run_id)
        run.state = 'running'
        db.add(run)
        events.stage_task_run_event(db, run_id, 'state')
        db.rollback()
    with DbSession(engine) as db:
        assert db.get(TaskRun, run_id).state == 'queued'
        assert db.exec(select(TaskRunEvent)).all() == []
    assert notifications == []
    engine.dispose()


def test_guard_does_not_change_run_fields(tmp_path):
    engine, (_, run_id) = database(tmp_path)
    with DbSession(engine) as db:
        before = db.get(TaskRun, run_id).model_dump()
        events.append_task_run_event(db, run_id, 'first')
        events.append_task_run_event(db, run_id, 'second')
        assert db.get(TaskRun, run_id).model_dump() == before
    engine.dispose()


def test_wal_read_snapshot_conflict_preserves_transaction_ownership(tmp_path):
    engine, (_, run_id) = database(tmp_path, timeout=0.1)
    with engine.connect() as connection:
        assert connection.exec_driver_sql('PRAGMA journal_mode=WAL').scalar_one() == 'wal'
    assert hasattr(events, 'EventWriteConflict'), 'Missing bounded event write conflict'
    with DbSession(engine) as reader:
        reader.connection().exec_driver_sql('BEGIN')
        run = reader.get(TaskRun, run_id)
        transaction = reader.get_transaction()
        with DbSession(engine) as writer:
            events.append_task_run_event(writer, run_id, 'other-writer')
        run.state = 'running'
        reader.add(run)
        with pytest.raises(events.EventWriteConflict) as failure:
            events.stage_task_run_event(reader, run_id, 'stale')
        assert failure.value.code == 'EVENT_WRITE_CONFLICT'
        assert reader.get_transaction() is transaction
        reader.rollback()
        assert reader.get(TaskRun, run_id).state == 'queued'
        assert events.append_task_run_event(reader, run_id, 'retry').sequence == 2
    engine.dispose()


def test_lock_timeout_is_bounded_and_does_not_leave_partial_state(tmp_path):
    import time
    engine, (_, run_id) = database(tmp_path, timeout=0.1)
    assert hasattr(events, 'EventWriteConflict'), 'Missing bounded event write conflict'
    with DbSession(engine) as owner, DbSession(engine) as contender:
        owner.connection().exec_driver_sql('BEGIN IMMEDIATE')
        started = time.monotonic()
        with pytest.raises(events.EventWriteConflict):
            events.stage_task_run_event(contender, run_id, 'locked')
        assert time.monotonic() - started < 2
        contender.rollback()
        owner.rollback()
        assert contender.exec(select(TaskRunEvent)).all() == []
        assert events.append_task_run_event(contender, run_id, 'retry').sequence == 1
    engine.dispose()


def test_interleaved_runs_replay_all_pages_with_existing_cursor(tmp_path, monkeypatch):
    engine, (session_id, run_id) = database(tmp_path)
    monkeypatch.setattr(events, '_naive_utc_now', lambda: datetime(2026, 1, 1))
    with DbSession(engine) as db:
        first = db.get(TaskRun, run_id)
        second = TaskRun(task_id=first.task_id, agent_id=first.agent_id, state='queued', worktree_path=first.worktree_path)
        db.add(second)
        db.commit()
        expected = []
        for identifier in (run_id, second.id, run_id, second.id):
            expected.append(events.append_task_run_event(db, identifier, 'state').id)
        cursor, replayed = None, []
        while page := events.list_session_events(db, session_id, after=cursor, limit=1):
            replayed.extend(e.id for e in page)
            cursor = events.format_session_cursor(page[-1])
        assert replayed == expected
        assert len(set(replayed)) == 4
        assert events.parse_session_cursor(cursor)
    engine.dispose()


def test_event_conflict_never_repeats_provider_or_file_side_effect(tmp_path):
    from fastapi import Depends
    from fastapi.routing import APIRoute
    from fastapi.testclient import TestClient
    from app.main import app
    engine, (_, run_id) = database(tmp_path, timeout=0.1)
    effects = []

    def connection():
        with DbSession(engine) as db:
            yield db

    def endpoint(db: DbSession = Depends(connection)):
        run = db.get(TaskRun, run_id)
        run.state = 'running'
        db.add(run)
        effects.append('external-work-already-performed')
        events.stage_task_run_event(db, run_id, 'state')
        db.commit()
        return {'ok': True}

    route = APIRoute('/__integrity_conflict_test', endpoint, methods=['POST'])
    app.router.routes.append(route)
    try:
        with DbSession(engine) as owner:
            owner.connection().exec_driver_sql('BEGIN IMMEDIATE')
            response = TestClient(app, raise_server_exceptions=False).post('/__integrity_conflict_test')
            assert response.status_code == 409
            assert response.json()['code'] == 'EVENT_WRITE_CONFLICT'
            owner.rollback()
        assert effects == ['external-work-already-performed']
        with DbSession(engine) as db:
            assert db.get(TaskRun, run_id).state == 'queued'
            assert db.exec(select(TaskRunEvent)).all() == []
    finally:
        app.router.routes.remove(route)
        engine.dispose()


@pytest.mark.parametrize('action', ['create', 'retry'])
def test_real_run_request_classifies_lock_before_event_guard(tmp_path, monkeypatch, action):
    from fastapi.testclient import TestClient
    from sqlalchemy import event
    from app import dependencies
    import app.main as main
    from app.main import app
    from app.memory_snapshots import ensure_session_memory_snapshot
    from app.models import Session

    engine, (session_id, run_id) = database(tmp_path, timeout=.1)
    with DbSession(engine) as db:
        run = db.get(TaskRun, run_id)
        task_id = run.task_id
        run.state = 'failed'
        task = db.get(Task, task_id)
        task.status = 'failed'
        db.add_all([run, task])
        db.commit()
        ensure_session_memory_snapshot(db, db.get(Session, session_id))
    scheduled = []
    writes = []
    event.listen(engine, 'before_cursor_execute',
                 lambda _c, _cur, statement, _params, _ctx, _many: writes.append(statement)
                 if statement.startswith('UPDATE session ') else None)
    monkeypatch.setattr(dependencies, 'engine', engine)
    monkeypatch.setattr(main, 'schedule_task_run_execution', lambda _tasks: scheduled.append('scheduled'))
    path = f'/tasks/{task_id}/runs' if action == 'create' else f'/task-runs/{run_id}/retry'
    try:
        with DbSession(engine) as owner:
            owner.connection().exec_driver_sql('BEGIN IMMEDIATE')
            response = TestClient(app, raise_server_exceptions=False).post(path)
            assert writes, 'Request did not reach the real pre-event Session write guard'
            assert response.status_code == 409, response.text
            assert response.json()['code'] == 'EVENT_WRITE_CONFLICT'
            owner.rollback()
        assert scheduled == []
        with DbSession(engine) as db:
            assert db.get(TaskRun, run_id).state == 'failed'
            assert len(db.exec(select(TaskRun)).all()) == 1
            assert db.exec(select(TaskRunEvent)).all() == []
    finally:
        engine.dispose()


def test_request_transaction_does_not_misclassify_other_sqlite_errors(tmp_path, monkeypatch):
    from app import dependencies
    from sqlalchemy.exc import OperationalError
    engine, _ = database(tmp_path)
    monkeypatch.setattr(dependencies, 'engine', engine)
    provider = dependencies.get_db()
    db = next(provider)
    try:
        with pytest.raises(OperationalError) as failure:
            db.connection().exec_driver_sql('SELECT * FROM no_such_integrity_test_table')
        with pytest.raises(OperationalError) as propagated:
            provider.throw(failure.value)
        assert propagated.value is failure.value
    finally:
        provider.close()
        engine.dispose()
