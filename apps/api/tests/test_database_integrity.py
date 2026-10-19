import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session as DbSession

from app.db import engine
from app.models import Message, Session, Workspace


def valid_session():
    with DbSession(engine) as db:
        workspace = Workspace(name='integrity', repo_url='local://', root_path='.', default_branch='main')
        db.add(workspace)
        db.flush([workspace])
        db.commit()
        session = Session(workspace_id=workspace.id, title='integrity', bound_branch='main', worktree_path='integrity-' + str(uuid.uuid4()))
        db.add(session)
        db.commit()
        return session.id


def test_every_physical_connection_enforces_foreign_keys():
    with engine.connect() as first, engine.connect() as second:
        assert first.connection.driver_connection is not second.connection.driver_connection
        assert first.exec_driver_sql('PRAGMA foreign_keys').scalar_one() == 1
        assert second.exec_driver_sql('PRAGMA foreign_keys').scalar_one() == 1


def test_invalid_child_insert_is_rejected():
    with pytest.raises(IntegrityError), DbSession(engine) as db:
        db.add(Message(session_id='missing-session', sender_type='user', content_md='reject'))
        db.flush()


def test_invalid_child_update_and_referenced_parent_delete_are_rejected():
    session_id = valid_session()
    with DbSession(engine) as db:
        message = Message(session_id=session_id, sender_type='user', content_md='retain')
        db.add(message)
        db.commit()
        message_id = message.id
    with pytest.raises(IntegrityError), DbSession(engine) as db:
        message = db.get(Message, message_id)
        message.session_id = 'missing-session'
        db.add(message)
        db.flush()
    with pytest.raises(IntegrityError), DbSession(engine) as db:
        db.delete(db.get(Session, session_id))
        db.flush()
    with DbSession(engine) as db:
        assert db.get(Message, message_id).session_id == session_id
        assert db.get(Session, session_id) is not None


@pytest.mark.parametrize('module_name', ['app.external_benchmark', 'app.p18b_workflow_rehearsal', 'app.workflow_evaluation'])
def test_business_evaluation_engines_enforce_foreign_keys(module_name):
    import importlib
    from sqlmodel import SQLModel
    module = importlib.import_module(module_name)
    isolated = module.create_engine('sqlite://')
    try:
        SQLModel.metadata.create_all(isolated)
        with isolated.connect() as connection:
            assert connection.exec_driver_sql('PRAGMA foreign_keys').scalar_one() == 1
        with pytest.raises(IntegrityError), DbSession(isolated) as db:
            db.add(Message(session_id='missing-parent', sender_type='user', content_md='reject'))
            db.flush()
    finally:
        isolated.dispose()


def test_fixture_parent_flush_uses_real_constraints_without_synthetic_rows():
    import importlib.util
    from sqlmodel import SQLModel
    from app.db_engine import create_runtime_engine
    assert importlib.util.find_spec('fixture_database') is not None, 'Missing explicit fixture dependency flush'
    from fixture_database import flush_fixture_rows
    isolated = create_runtime_engine('sqlite://')
    SQLModel.metadata.create_all(isolated)
    with DbSession(isolated) as db:
        parent = Workspace(name='parent', repo_url='local://', root_path='.', default_branch='main')
        session = Session(workspace_id=parent.id, title='child', bound_branch='main', worktree_path='fixture')
        child = Message(session_id=session.id, sender_type='user', content_md='child')
        db.add_all([child, session, parent])
        flush_fixture_rows(db)
        assert db.connection().exec_driver_sql('PRAGMA foreign_keys').scalar_one() == 1
        db.commit()
    with pytest.raises(IntegrityError), DbSession(isolated) as db:
        db.add(Message(session_id='absent', sender_type='user', content_md='never repair'))
        flush_fixture_rows(db)
    isolated.dispose()
