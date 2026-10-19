import pytest
from sqlmodel import Session as DbSession

from app import events, guardrails, task_runs
from app.models import Task, TaskRun
from test_event_concurrency import database


def fail_event(*_args, **_kwargs):
    raise events.EventWriteConflict('injected event write conflict')


def test_transition_state_and_event_rollback_together(tmp_path, monkeypatch):
    engine, (_, run_id) = database(tmp_path)
    with DbSession(engine) as db:
        run = db.get(TaskRun, run_id)
        task_id = run.task_id
        before = (run.state, db.get(Task, task_id).status)
        monkeypatch.setattr(task_runs, 'append_task_run_event', fail_event)
        with pytest.raises(events.EventWriteConflict):
            task_runs.transition_task_run(db, run_id, 'streaming')
        db.rollback()
        assert (db.get(TaskRun, run_id).state, db.get(Task, task_id).status) == before
    engine.dispose()


def test_transition_event_keeps_state_pending_for_commit_fence(tmp_path):
    from sqlalchemy import event
    engine, (_, run_id) = database(tmp_path)
    observed = []
    with DbSession(engine) as db:
        def fence(session):
            row = session.connection().exec_driver_sql('SELECT state FROM taskrun WHERE id=?', (run_id,)).scalar_one()
            observed.append(row)
            assert row == 'queued'
        event.listen(db, 'before_commit', fence)
        task_runs.transition_task_run(db, run_id, 'streaming')
        event.remove(db, 'before_commit', fence)
        assert observed == ['queued']
        assert db.get(TaskRun, run_id).state == 'streaming'
    engine.dispose()


@pytest.mark.parametrize('action', ['request', 'approve', 'deny'])
def test_approval_state_and_event_are_atomic_with_foreign_keys(tmp_path, monkeypatch, action):
    engine, (_, run_id) = database(tmp_path)
    payload = guardrails.ApprovalRequestPayload(approval_type='security_approval', reason='test', risk_level='high', requested_action='test')
    with DbSession(engine) as db:
        if action != 'request':
            guardrails.request_task_run_approval(db, run_id, payload)
        run = db.get(TaskRun, run_id)
        task_id = run.task_id
        before = (run.state, db.get(Task, task_id).status)
        monkeypatch.setattr(guardrails, 'append_task_run_event', fail_event)
        with pytest.raises(events.EventWriteConflict):
            if action == 'request':
                guardrails.request_task_run_approval(db, run_id, payload)
            elif action == 'approve':
                guardrails.approve_task_run(db, run_id)
            else:
                guardrails.deny_task_run(db, run_id, 'denied')
        db.rollback()
        assert (db.get(TaskRun, run_id).state, db.get(Task, task_id).status) == before
    engine.dispose()
