import json
from datetime import datetime

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlmodel import select

from app.dependencies import get_db
from app.message_history import message_content, message_page, single_message, PREVIEW_CHARACTERS
from app.models import Message, Session, Workspace
from app.routes.message_history import router
from test_scripted_mock_adapter import db


@pytest.fixture
def history(db):
    workspace = Workspace(name="Paging", root_path="fixture", repo_url="local://fixture", default_branch="main")
    session = Session(workspace_id=workspace.id, title="Paging", bound_branch="main", worktree_path="fixture-history")
    other = Session(workspace_id=workspace.id, title="Other", bound_branch="main", worktree_path="fixture-other")
    stamp = datetime(2026, 10, 15)
    rows = [Message(id=f"row-{index:04d}", session_id=session.id, sender_type="user", content_md=f"message {index}",
                    pinned_at=stamp if index < 35 else None, created_at=stamp) for index in range(240)]
    alien = Message(session_id=other.id, sender_type="user", content_md="other Session")
    db.add_all([workspace, session, other, alien, *rows]); db.commit()
    return db, session.id, alien.id


def test_stable_before_after_and_around_pages_with_equal_timestamps(history):
    db, sid, _ = history
    latest = message_page(db, sid)
    assert len(latest["messages"]) == 80 and latest["total"] == 240
    assert latest["olderCursor"] == "row-0160" and latest["newerCursor"] == "row-0239"
    assert latest["hasOlder"] and not latest["hasNewer"]
    # New arrivals do not shift the immutable older cursor.
    db.add(Message(id="row-9999", session_id=sid, sender_type="user", content_md="new", created_at=datetime(2026, 10, 15))); db.commit()
    older = message_page(db, sid, before=latest["olderCursor"])
    assert [m["id"] for m in older["messages"]] == [f"row-{i:04d}" for i in range(80, 160)]
    newer = message_page(db, sid, after=older["newerCursor"])
    assert [m["id"] for m in newer["messages"]] == [m["id"] for m in latest["messages"]]
    around = message_page(db, sid, limit=20, around="row-0100")
    assert len(around["messages"]) == 20 and "row-0100" in [m["id"] for m in around["messages"]]
    assert around["hasOlder"] and around["hasNewer"]


def test_pins_are_independent_bounded_and_cursor_owned(history):
    db, sid, alien = history
    value = message_page(db, sid, limit=5)
    assert value["pinnedTotal"] == 35 and len(value["pinnedMessages"]) == 16
    assert value["pinnedMessages"][0]["id"] == "row-0034"
    for kwargs in ({"before": alien}, {"after": alien}, {"around": alien}, {"before": "missing"}):
        with pytest.raises(HTTPException) as exc: message_page(db, sid, **kwargs)
        assert exc.value.status_code == 404
    for kwargs in ({"limit": 201}, {"before": "row-0001", "after": "row-0002"}):
        with pytest.raises(HTTPException): message_page(db, sid, **kwargs)


def test_long_body_projection_and_unicode_segments_do_not_change_persisted_or_loaded_source(history):
    db, sid, _ = history
    original = "中文😀" * 10000
    row = db.get(Message, "row-0239"); row.content_md = original; db.add(row); db.commit()
    assert db.get(Message, row.id).content_md == original
    response = single_message(db, sid, row.id)
    assert response["contentTruncated"] and response["contentCharacters"] == len(original)
    assert len(response["contentMd"]) == PREVIEW_CHARACTERS
    assert db.get(Message, row.id).content_md == original
    parts, offset = [], 0
    while True:
        page = message_content(db, sid, row.id, offset=offset, limit=1100)
        assert len(page["text"]) <= 1100
        parts.append(page["text"])
        if page["nextOffset"] is None: break
        offset = page["nextOffset"]
    assert "".join(parts) == original
    db.expire_all()
    assert db.get(Message, row.id).content_md == original
    row.content_md = "prefix\0full content after control"; db.add(row); db.commit()
    assert single_message(db, sid, row.id)["contentTruncated"]
    assert single_message(db, sid, row.id)["contentCharacters"] is None
    with pytest.raises(HTTPException) as exc: message_content(db, sid, row.id)
    assert exc.value.status_code == 409 and "after control" in db.get(Message, row.id).content_md


def test_source_parent_outside_page_and_global_preparing_regeneration_stay_visible(history):
    db, sid, _ = history
    reply = Message(session_id=sid, sender_type="orchestrator", content_md="reply", parent_message_id="row-0000")
    pending = db.get(Message, "row-0001")
    pending.regeneration_json = json.dumps({"schemaVersion": "message_regeneration_v1", "state": "preparing"})
    db.add_all([reply, pending]); db.commit()
    response = single_message(db, sid, reply.id)
    assert response["regenerationAction"]["available"] is False
    assert "准备重新生成" in response["regenerationAction"]["reason"]
    pending.regeneration_json = "{}"; db.add(pending); db.commit()
    assert single_message(db, sid, reply.id)["regenerationAction"]["available"] is True


def test_http_bounds_unicode_segments_and_wrong_session_content(history):
    db, sid, alien = history
    app = FastAPI(); app.include_router(router); app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    base = f"/sessions/{sid}/messages"
    assert client.get(base + "/page?limit=201").status_code == 422
    assert client.get(base + "/page?before=" + "x" * 81).status_code == 422
    assert client.get(base + f"/{alien}/content").status_code == 404
    assert client.get(base + "/row-0000/content?offset=-1").status_code == 422
    assert client.get(base + "/row-0000/content?limit=12001").status_code == 422
    assert client.get(base + "/row-0000/content?offset=9999").status_code == 400
    assert len(client.get(base + "/page?limit=10").json()["messages"]) == 10


def test_existing_database_history_indexes_upgrade_idempotently(history):
    from migration_fixtures import migrate_engine
    db, sid, _ = history
    engine = db.get_bind()
    with engine.begin() as connection:
        connection.execute(text("DROP INDEX ix_message_session_order"))
        connection.execute(text("DROP INDEX ix_message_session_pins"))
    migrate_engine(engine); migrate_engine(engine)
    assert {"ix_message_session_order", "ix_message_session_pins"}.issubset({row["name"] for row in inspect(engine).get_indexes("message")})
    plan = db.execute(text("EXPLAIN QUERY PLAN SELECT id FROM message WHERE session_id=:sid ORDER BY created_at DESC, id DESC LIMIT 80"), {"sid": sid}).all()
    assert "ix_message_session_order" in str(plan) and "TEMP B-TREE" not in str(plan)
    assert len(db.exec(select(Message).where(Message.session_id == sid)).all()) == 240
