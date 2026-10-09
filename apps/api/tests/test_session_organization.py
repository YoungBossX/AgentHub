import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import SQLModel, Session as DbSession, create_engine, select

from app.db import _ensure_sqlite_demo_schema_columns
from app.main import app, get_db
from app.models import Message, Session, Task, TaskRun, Workspace
from app.repositories import next_session_title
from app.routes.sessions import organize_session
from app.schemas import SessionOrganizationRequest


@pytest.fixture
def organization(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'organization.sqlite3'}", connect_args={"check_same_thread": False, "timeout": 30})
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        workspace = Workspace(name="Organization", repo_url="local://demo", root_path="apps/demo", default_branch="main")
        other = Workspace(name="Other", repo_url="local://other", root_path="apps/demo", default_branch="main")
        now = datetime(2026, 10, 8, 0, 0)
        sessions = [Session(workspace_id=workspace.id, title=f"Session {index}", bound_branch="main", worktree_path=str(tmp_path / str(index)), created_at=now, updated_at=now, last_message_at=now+timedelta(minutes=index)) for index in range(3)]
        foreign = Session(workspace_id=other.id, title="Foreign", bound_branch="main", worktree_path=str(tmp_path / "other"))
        messages = [Message(session_id=session.id, sender_type="user", content_md=f"Key {index}", context_json=json.dumps({"lineage": index}), created_at=now+timedelta(minutes=index)) for index, session in enumerate(sessions)]
        db.add_all([workspace, other, *sessions, foreign, *messages]); db.commit()
        ids = {"workspace": workspace.id, "sessions": [s.id for s in sessions], "messages": [m.id for m in messages]}
    def provide():
        with DbSession(engine) as db: yield db
    app.dependency_overrides[get_db] = provide
    try: yield TestClient(app), engine, ids
    finally: app.dependency_overrides.clear(); engine.dispose()


def test_pins_and_archive_views_are_reversible_idempotent_and_preserve_identity(organization):
    client, engine, ids = organization; sid = ids["sessions"][0]
    with DbSession(engine) as db: before = db.get(Session, sid).model_dump()
    first = client.patch(f"/sessions/{sid}/organization", json={"pinned": True}).json()
    assert first["pinnedAt"] and first["archivedAt"] is None
    assert client.patch(f"/sessions/{sid}/organization", json={"pinned": True}).json()["pinnedAt"] == first["pinnedAt"]
    url = f"/workspaces/{ids['workspace']}/sessions"
    assert [s["id"] for s in client.get(url).json()] == [sid, ids["sessions"][2], ids["sessions"][1]]
    archive = client.patch(f"/sessions/{sid}/organization", json={"archived": True}).json()
    assert archive["archivedAt"] and archive["pinnedAt"] == first["pinnedAt"]
    assert client.patch(f"/sessions/{sid}/organization", json={"archived": True}).json()["archivedAt"] == archive["archivedAt"]
    assert sid not in [s["id"] for s in client.get(url).json()]
    assert [s["id"] for s in client.get(url+"?view=archived").json()] == [sid]
    assert len(client.get(url+"?view=all").json()) == 3
    assert client.get(url+"?view=wrong").status_code == 422
    with DbSession(engine) as db:
        assert next_session_title(db, ids["workspace"]) == "Session 4"
        after = db.get(Session, sid).model_dump()
        assert {k: v for k, v in after.items() if k not in {"pinned_at", "archived_at"}} == {k: v for k, v in before.items() if k not in {"pinned_at", "archived_at"}}
    restored = client.patch(f"/sessions/{sid}/organization", json={"archived": False}).json()
    assert restored["archivedAt"] is None and restored["pinnedAt"] == first["pinnedAt"]
    assert client.get(url).json()[0]["id"] == sid
    assert client.patch(f"/sessions/{sid}/organization", json={"pinned": False}).json()["pinnedAt"] is None


@pytest.mark.parametrize("body", [{}, {"pinned": None}, {"archived": None}, {"pinned": "true"}, {"archived": 1}, {"status": "archived"}, {"pinned": True, "worktreePath": "other"}])
def test_invalid_organization_request_changes_nothing(organization, body):
    client, engine, ids = organization; sid = ids["sessions"][0]
    with DbSession(engine) as db: before = db.get(Session, sid).model_dump()
    assert client.patch(f"/sessions/{sid}/organization", json=body).status_code == 422
    with DbSession(engine) as db: assert db.get(Session, sid).model_dump() == before


@pytest.mark.parametrize("body", [{}, {"pinned": None}, {"pinned": "false"}, {"pinned": 1}, {"pinned": True, "contentMd": "tamper"}])
def test_invalid_pin_request_preserves_message(organization, body):
    client, engine, ids = organization; sid, mid = ids["sessions"][0], ids["messages"][0]
    assert client.patch(f"/sessions/{sid}/messages/{mid}/pin", json=body).status_code == 422
    with DbSession(engine) as db: assert db.get(Message, mid).pinned_at is None


def test_key_message_pinning_preserves_content_order_context_and_session_times(organization):
    client, engine, ids = organization; sid, mid = ids["sessions"][0], ids["messages"][0]
    with DbSession(engine) as db:
        before = db.get(Message, mid).model_dump(); session_before = db.get(Session, sid).model_dump()
    url = f"/sessions/{sid}/messages/{mid}/pin"
    response = client.patch(url, json={"pinned": True})
    assert response.status_code == 200 and response.json()["pinnedAt"]
    assert client.patch(url, json={"pinned": True}).json()["pinnedAt"] == response.json()["pinnedAt"]
    assert client.get(f"/sessions/{sid}/messages").json()[0]["pinnedAt"] == response.json()["pinnedAt"]
    with DbSession(engine) as db:
        after = db.get(Message, mid).model_dump()
        assert {k: v for k, v in after.items() if k != "pinned_at"} == {k: v for k, v in before.items() if k != "pinned_at"}
        assert db.get(Session, sid).model_dump() == session_before
    assert client.patch(url, json={"pinned": False}).json()["pinnedAt"] is None


def test_missing_and_foreign_message_boundaries(organization):
    client, engine, ids = organization; sid, mid = ids["sessions"][0], ids["messages"][1]
    assert client.patch("/sessions/missing/organization", json={"pinned": True}).status_code == 404
    assert client.patch(f"/sessions/{sid}/messages/{mid}/pin", json={"pinned": True}).status_code == 404
    assert client.patch(f"/sessions/{sid}/messages/missing/pin", json={"pinned": True}).status_code == 404
    assert client.patch(f"/sessions/missing/messages/{mid}/pin", json={"pinned": True}).status_code == 404
    with DbSession(engine) as db: assert db.get(Message, mid).pinned_at is None


def test_concurrent_column_edits_merge_and_leave_running_task_unchanged(organization):
    client, engine, ids = organization; sid = ids["sessions"][0]
    with DbSession(engine) as db:
        task = Task(session_id=sid, title="Live", intent_type="frontend_change", assigned_agent_id="agent", plan_json='{"targetId":"demo-frontend"}')
        run = TaskRun(task_id=task.id, agent_id="agent", state="streaming", worktree_path=db.get(Session, sid).worktree_path)
        db.add_all([task, run]); db.commit(); run_id = run.id; before = run.model_dump()
    def organize(field):
        with DbSession(engine) as db: return organize_session(sid, SessionOrganizationRequest(**{field: True}), db).id
    with ThreadPoolExecutor(max_workers=2) as pool: assert list(pool.map(organize, ["pinned", "archived"])) == [sid, sid]
    with DbSession(engine) as db:
        session = db.get(Session, sid)
        assert session.pinned_at and session.archived_at
        assert db.get(TaskRun, run_id).model_dump() == before
    assert client.get(f"/sessions/{sid}/messages").status_code == 200


def test_old_sqlite_upgrade_preserves_rows_and_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.sqlite3'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE session (id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, title TEXT NOT NULL, session_type TEXT NOT NULL, bound_branch TEXT NOT NULL, worktree_path TEXT NOT NULL, status TEXT NOT NULL, last_message_at DATETIME, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL)"))
        conn.execute(text("CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, sender_type TEXT NOT NULL, sender_id TEXT, content_md TEXT NOT NULL, message_kind TEXT NOT NULL, parent_message_id TEXT, stream_state TEXT NOT NULL, created_at DATETIME NOT NULL)"))
        conn.execute(text("INSERT INTO session VALUES ('s','ws','Legacy','demo','main','original-worktree','active',NULL,'2026-01-01','2026-01-01')"))
        conn.execute(text("INSERT INTO message VALUES ('m','s','user',NULL,'Original content','chat',NULL,'complete','2026-01-01')"))
    _ensure_sqlite_demo_schema_columns(engine); _ensure_sqlite_demo_schema_columns(engine)
    with DbSession(engine) as db:
        session, message = db.get(Session, "s"), db.get(Message, "m")
        assert session.title == "Legacy" and session.worktree_path == "original-worktree"
        assert session.pinned_at is None and session.archived_at is None
        assert message.content_md == "Original content" and message.pinned_at is None and message.context_json == "{}"
    engine.dispose()
