import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import SQLModel, Session as DbSession, create_engine, select

from app.main import app, get_db
from app.models import Message, MessageAttachment, Session, Task, TaskRun, Workspace
from app.message_regeneration import finish_request, metadata, prepare_regeneration, recover_interrupted_requests
from app.routes import messages as routes


@pytest.fixture
def regeneration(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'regeneration.sqlite3'}", connect_args={"check_same_thread": False, "timeout": 20})
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        workspace = Workspace(name="Regeneration", root_path=str(tmp_path), repo_url="local://demo", default_branch="main")
        session = Session(workspace_id=workspace.id, title="Main", bound_branch="main", worktree_path=str(tmp_path / 'main'))
        other = Session(workspace_id=workspace.id, title="Other", bound_branch="main", worktree_path=str(tmp_path / 'other'))
        quoted = Message(session_id=session.id, sender_type="user", content_md="Original quoted context")
        request = Message(session_id=session.id, sender_type="user", content_md="@orchestrator Explain this file", parent_message_id=quoted.id,
                          context_json=json.dumps({"contextItems": [{"kind": "message", "messageId": quoted.id, "summary": "quoted"}]}))
        reply = Message(session_id=session.id, sender_type="orchestrator", message_kind="chat", content_md="Original reply", parent_message_id=request.id)
        attachment = MessageAttachment(session_id=session.id, message_id=request.id, filename="reference.txt", kind="text", media_type="text/plain",
            byte_size=9, sha256="fixture-hash", extraction_status="ready", text_content="FILE_ONLY", payload=b"FILE_ONLY")
        db.add_all([workspace, session, other, quoted, request, reply, attachment]); db.commit()
        ids = dict(session=session.id, other=other.id, request=request.id, reply=reply.id, quoted=quoted.id, attachment=attachment.id)
    calls = []
    def dispatch(db, created, background_tasks):
        calls.append(created.id)
        db.add(Message(session_id=created.session_id, sender_type="orchestrator", content_md="New reply", parent_message_id=created.id))
        db.commit()
    monkeypatch.setattr(routes, "dispatch_message", dispatch)
    def provide():
        with DbSession(engine) as db: yield db
    app.dependency_overrides[get_db] = provide
    try: yield TestClient(app), engine, ids, calls
    finally: app.dependency_overrides.clear(); engine.dispose()


def post(client, ids, operation=None, **kwargs):
    return client.post(f"/sessions/{ids['session']}/messages/{ids['reply']}/regenerate", json={"requestId": operation or str(uuid4()), **kwargs})


def test_regeneration_preserves_original_context_attachment_ownership_and_lineage(regeneration):
    from app.attachment_context import select_attachment_context

    client, engine, ids, calls = regeneration
    with DbSession(engine) as db:
        before = {m.id: m.model_dump() for m in db.exec(select(Message)).all()}
    response = post(client, ids)
    assert response.status_code == 201, response.text
    value = response.json()
    assert value['regeneration']['state'] == 'submitted' and value['contentMd'] == '@orchestrator Explain this file'
    assert value['regeneration']['sourceMessageId'] == ids['reply'] and value['parentMessageId'] == ids['quoted']
    assert value['attachments'][0]['id'] == ids['attachment']
    with DbSession(engine) as db:
        created = db.get(Message, value['id'])
        assert created.context_json == before[ids['request']]['context_json']
        assert all(db.get(Message, mid).model_dump() == row for mid, row in before.items())
        assert db.get(MessageAttachment, ids['attachment']).message_id == ids['request']
        context = select_attachment_context(db, ids['session'], created.id, pinned={}, recent=[])
        assert context['items'][0]['text'] == 'FILE_ONLY'
        assert context['items'][0]['messageId'] == ids['request']
        # A pinned regenerated request must still carry original file inputs.
        context = select_attachment_context(db, ids['session'], None, pinned={'messages':[{'id':created.id}]}, recent=[])
        assert context['items'][0]['id'] == ids['attachment']
    history = client.get(f"/sessions/{ids['session']}/messages").json()
    new_reply = next(m for m in history if m['contentMd'] == 'New reply')
    assert new_reply['regeneration']['operationId'] == value['id']
    assert calls == [value['id']]
    again = post(client, {**ids, 'reply':new_reply['id']}).json()
    assert again['attachments'][0]['id'] == ids['attachment']
    with DbSession(engine) as db:
        assert len(db.exec(select(MessageAttachment)).all()) == 1


def test_duplicate_operation_is_returned_and_mismatched_source_or_session_is_rejected(regeneration):
    client, engine, ids, calls = regeneration; operation = str(uuid4())
    first = post(client, ids, operation).json()
    second = post(client, ids, operation).json()
    assert first == second and calls == [operation]
    assert post(client, {**ids, 'reply':ids['request']}, operation).status_code == 409
    assert post(client, {**ids, 'session':ids['other']}, operation).status_code == 404
    assert post(client, ids, ids['request']).status_code == 409


@pytest.mark.parametrize('change', ['user','diagnostic','streaming','foreign_parent','missing_parent'])
def test_ineligible_messages_are_not_dispatchable(regeneration, change):
    client, engine, ids, calls = regeneration
    with DbSession(engine) as db:
        reply = db.get(Message, ids['reply'])
        if change == 'user': reply.sender_type = 'user'
        if change == 'diagnostic': reply.message_kind = 'group_execution_error'
        if change == 'streaming': reply.stream_state = 'streaming'
        if change == 'missing_parent': reply.parent_message_id = 'missing'
        if change == 'foreign_parent':
            source = db.get(Message, ids['request']); source.session_id = ids['other']; db.add(source)
        db.add(reply); db.commit()
    assert post(client, ids).status_code == 409 and not calls


@pytest.mark.parametrize('state', ['pending','waiting_approval','waiting_dependency','blocked'])
def test_unfinished_original_tasks_require_existing_task_actions(regeneration, state):
    client, engine, ids, calls = regeneration
    with DbSession(engine) as db:
        db.add(Task(session_id=ids['session'], created_by_message_id=ids['request'], title='Unfinished', intent_type='frontend_change', status=state))
        db.commit()
    assert post(client, ids).status_code == 409 and not calls


def test_running_work_in_session_blocks_request_regeneration(regeneration):
    client, engine, ids, calls = regeneration
    with DbSession(engine) as db:
        task = Task(session_id=ids['session'], title='Other live request', intent_type='frontend_change', status='completed')
        run = TaskRun(task_id=task.id, agent_id='fixture', worktree_path='unused', state='waiting_approval')
        db.add_all([task, run]); db.commit()
    assert post(client, ids).status_code == 409 and not calls


def test_concurrent_preparations_and_transport_replay_do_not_duplicate_work(regeneration, monkeypatch):
    client, engine, ids, calls = regeneration; entered, release = Event(), Event(); operation = str(uuid4())
    def dispatch(db, created, background_tasks):
        calls.append(created.id); entered.set(); assert release.wait(10)
    monkeypatch.setattr(routes, 'dispatch_message', dispatch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(post, client, ids, operation)
        try:
            assert entered.wait(5)
            replay = post(client, ids, operation)
            assert replay.status_code == 201 and replay.json()['regeneration']['state'] == 'preparing'
            assert post(client, ids).status_code == 409
            assert calls == [operation]
        finally: release.set()
        assert first.result().json()['regeneration']['state'] == 'submitted'


def test_failed_preparation_keeps_identity_partial_evidence_and_safe_error(regeneration, monkeypatch):
    client, engine, ids, calls = regeneration; operation = str(uuid4())
    def dispatch(db, created, background_tasks):
        calls.append(created.id)
        db.add(Message(session_id=created.session_id, sender_type='orchestrator', content_md='Partial plan', parent_message_id=created.id)); db.commit()
        raise ValueError('SECRET_TEST_MUST_NOT_LEAK')
    monkeypatch.setattr(routes, 'dispatch_message', dispatch)
    response = post(client, ids, operation)
    assert response.status_code == 201 and response.json()['regeneration']['state'] == 'failed'
    assert 'SECRET_TEST_MUST_NOT_LEAK' not in response.text
    assert post(client, ids, operation).json()['id'] == operation and calls == [operation]
    history = client.get(f"/sessions/{ids['session']}/messages").json()
    assert any(m['contentMd'] == 'Partial plan' for m in history)


def test_restart_marks_preparation_failed_without_dispatch_and_late_finish_cannot_rewrite(regeneration):
    client, engine, ids, calls = regeneration; operation = str(uuid4())
    with DbSession(engine) as db:
        created, job, fresh = prepare_regeneration(db, ids['session'], ids['reply'], operation)
        assert fresh and job is None and metadata(created)['state'] == 'preparing'
    assert recover_interrupted_requests(engine) == 1
    assert recover_interrupted_requests(engine) == 0
    with DbSession(engine) as db: finish_request(db, operation, failed=False)
    response = post(client, ids, operation)
    assert response.json()['regeneration']['errorCode'] == 'REGENERATION_PREPARATION_INTERRUPTED' and not calls


def test_request_shape_cannot_override_content_sender_or_metadata(regeneration):
    client, _, ids, calls = regeneration
    assert post(client, ids, contentMd='tampered').status_code == 422
    assert post(client, ids, 'not-uuid').status_code == 422
    assert not calls


def test_legacy_message_column_upgrade_is_idempotent(tmp_path):
    from app.db import _ensure_sqlite_demo_schema_columns

    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.sqlite3'}")
    with engine.begin() as db:
        db.execute(text("CREATE TABLE message (id TEXT PRIMARY KEY, content_md TEXT)"))
        db.execute(text("INSERT INTO message VALUES ('legacy','unchanged')"))
    _ensure_sqlite_demo_schema_columns(engine); _ensure_sqlite_demo_schema_columns(engine)
    with engine.connect() as db:
        assert db.execute(text('SELECT content_md,regeneration_json FROM message')).one() == ('unchanged','{}')
    engine.dispose()
