import hashlib
import io
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfWriter
from sqlmodel import SQLModel, Session as DbSession, create_engine, select

from app import attachments
from app.attachment_context import ATTACHMENT_JSON_LIMIT, resolve_image_inputs, select_attachment_context
from app.attachment_inputs import PlannerPayload, claude_input
from app.attachments import bind_message_attachments, create_attachment, parse_upload
from app.canonical_context import build_canonical_shared_context
from app.main import app, get_db
from app.models import Message, MessageAttachment, Session, Workspace, utc_now


@pytest.fixture
def storage(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'attachments.db'}", connect_args={"check_same_thread": False, "timeout": 30})
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        workspace = Workspace(name="Files", repo_url="local://demo", root_path="apps/demo", default_branch="main")
        sessions = [Session(workspace_id=workspace.id, title=str(i), bound_branch="main", worktree_path=str(tmp_path / str(i))) for i in range(2)]
        db.add_all([workspace, *sessions]); db.commit()
        ids = [row.id for row in sessions]
    def provide():
        with DbSession(engine) as db: yield db
    app.dependency_overrides[get_db] = provide
    monkeypatch.setattr("app.routes.messages.plan_for_message", lambda *args: [])
    monkeypatch.setattr("app.routes.messages.complete_ready_session_review_tasks", lambda *args: None)
    try: yield TestClient(app), engine, ids
    finally: app.dependency_overrides.clear(); engine.dispose()


def upload(client, sid, name="需求.md", data="附件里的独有文字".encode()):
    response = client.post(f"/sessions/{sid}/attachments", params={"filename": name}, content=data)
    assert response.status_code == 201, response.text
    return response.json()


def png():
    out = io.BytesIO(); Image.new("RGBA", (80, 50), (20, 100, 190, 0)).save(out, "PNG")
    return out.getvalue()


def test_upload_send_download_pin_and_reload(storage):
    client, engine, (sid, other) = storage
    data = "附件内容不应在历史 metadata 中重复".encode()
    item = upload(client, sid, data=data)
    assert item["sha256"] == hashlib.sha256(data).hexdigest()
    assert "payload" not in item and "textContent" not in item
    response = client.post(f"/sessions/{sid}/messages", json={"contentMd": "请参考附件", "attachmentIds": [item["id"]]})
    assert response.status_code == 201, response.text
    mid = response.json()["id"]
    assert response.json()["attachments"][0]["messageId"] == mid
    assert client.get(f"/sessions/{other}/attachments/{item['id']}/content").status_code == 404
    content = client.get(f"/sessions/{sid}/attachments/{item['id']}/content")
    assert content.content == data and content.headers["x-content-type-options"] == "nosniff"
    assert content.headers["content-disposition"].startswith("attachment;")
    assert client.delete(f"/sessions/{sid}/attachments/{item['id']}").status_code == 409
    assert client.patch(f"/sessions/{sid}/messages/{mid}/pin", json={"pinned": True}).json()["attachments"][0]["id"] == item["id"]
    engine.dispose(); SQLModel.metadata.create_all(engine)
    assert client.get(f"/sessions/{sid}/messages").json()[0]["attachments"][0]["sha256"] == item["sha256"]


@pytest.mark.parametrize("name,data,status", [
    ("../file.txt", b"a", 422), ("C:\\file.txt", b"a", 422), (".env.txt", b"a", 422),
    ("file.exe", b"MZ", 415), ("file.svg", b"<svg/>", 415), ("file.zip", b"PK", 415),
    ("file.txt", b"", 413), ("file.txt", b"\xff", 422), ("file.txt", b"abc\x00", 422),
    ("file.txt", b"a" * (512 * 1024 + 1), 422), ("file.pdf", b"not pdf", 422),
    ("file.png", b"not png", 422), ("file.jpg", png(), 422),
], ids=lambda value: f"bytes-{len(value)}" if isinstance(value, bytes) else str(value))
def test_rejected_uploads_leave_no_rows(storage, name, data, status):
    client, engine, (sid, _) = storage
    assert client.post(f"/sessions/{sid}/attachments", params={"filename": name}, content=data).status_code == status
    with DbSession(engine) as db: assert not db.exec(select(MessageAttachment)).all()


def test_hard_stream_size_limit_and_missing_session(storage):
    client, _, (sid, _) = storage
    assert client.post(f"/sessions/{sid}/attachments?filename=a.txt", content=b"a", headers={"content-length": "99999999"}).status_code == 413
    assert client.post(f"/sessions/{sid}/attachments?filename=a.txt", content=(b"a" * (1024 * 1024) for _ in range(9))).status_code == 413
    assert client.post("/sessions/missing/attachments?filename=a.txt", content=b"hello").status_code == 404


def test_raster_normalization_pdf_states_and_download(storage):
    client, engine, (sid, _) = storage
    item = upload(client, sid, "shot.png", png())
    assert (item["imageWidth"], item["imageHeight"]) == (80, 50)
    image = client.get(f"/sessions/{sid}/attachments/{item['id']}/content?preview=true")
    assert image.headers["content-type"] == "image/jpeg"
    assert Image.open(io.BytesIO(image.content)).getpixel((0, 0)) == (255, 255, 255)
    assert client.get(f"/sessions/{sid}/attachments/{item['id']}/content").content == png()
    writer = PdfWriter(); writer.add_blank_page(width=100, height=100)
    output = io.BytesIO(); writer.write(output)
    pdf = upload(client, sid, "scan.pdf", output.getvalue())
    assert pdf["extractionStatus"] == "no_text"
    assert client.get(f"/sessions/{sid}/attachments/{pdf['id']}/content?preview=true").status_code == 415
    writer.encrypt("password"); output = io.BytesIO(); writer.write(output)
    assert client.post(f"/sessions/{sid}/attachments?filename=locked.pdf", content=output.getvalue()).status_code == 422


def test_pending_remove_and_atomic_binding_rejections(storage):
    client, engine, (sid, foreign) = storage
    own, other = upload(client, sid), upload(client, foreign)
    for ids, status in [([own["id"], other["id"]], 409), ([own["id"], own["id"]], 422), (["missing"], 409)]:
        response = client.post(f"/sessions/{sid}/messages", json={"contentMd": "invalid", "attachmentIds": ids})
        assert response.status_code == status, response.text
        with DbSession(engine) as db:
            assert not db.exec(select(Message)).all()
            assert db.get(MessageAttachment, own["id"]).message_id is None
    assert client.delete(f"/sessions/{foreign}/attachments/{own['id']}").status_code == 404
    assert client.delete(f"/sessions/{sid}/attachments/{own['id']}").status_code == 204
    assert client.post(f"/sessions/{sid}/messages", json={"contentMd": "deleted", "attachmentIds": [own["id"]]}).status_code == 409


def test_concurrent_quota_and_binding_have_one_winner(storage, monkeypatch):
    _, engine, (sid, _) = storage
    monkeypatch.setattr(attachments, "MAX_SESSION_ATTACHMENTS", 1)
    parsed = parse_upload("one.txt", b"one")
    def insert(_):
        with DbSession(engine) as db:
            try: return create_attachment(db, sid, "one.txt", b"one", parsed).id
            except HTTPException as exc: return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(insert, range(2)))
    assert results.count(413) == 1
    aid = next(value for value in results if isinstance(value, str))
    def bind(_):
        with DbSession(engine) as db:
            message = Message(session_id=sid, sender_type="user", content_md="race")
            try: bind_message_attachments(db, message, [aid]); db.commit(); return message.id
            except HTTPException as exc: return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(bind, range(2)))
    assert results.count(409) == 1
    with DbSession(engine) as db: assert len(db.exec(select(Message)).all()) == 1


def test_context_is_authoritative_bounded_filtered_and_binary_private(storage):
    client, engine, (sid, other) = storage
    current = upload(client, sid, "current.md", ("中" * 15000 + " api_key=hidden-value").encode())
    pic = upload(client, sid, "shot.png", png())
    foreign = upload(client, other)
    def send(session, ids, **kwargs):
        response = client.post(f"/sessions/{session}/messages", json={"contentMd": "读取附件", "attachmentIds": ids, **kwargs})
        assert response.status_code == 201, response.text
        return response.json()["id"]
    foreign_mid = send(other, [foreign["id"]])
    mid = send(sid, [current["id"], pic["id"]], context={"attachmentContext": {"items": [foreign]}, "quotedMessage": {"messageId": foreign_mid}})
    with DbSession(engine) as db:
        context = select_attachment_context(db, sid, mid, pinned={"messages": []}, recent=[])
        serialized = json.dumps(context, ensure_ascii=True, indent=2)
        assert len(serialized) <= ATTACHMENT_JSON_LIMIT and "hidden-value" not in serialized
        assert foreign["id"] not in serialized and context["selection"]["total"] == 2
        images = resolve_image_inputs(db, sid, context)
        # A long text must not consume the metadata space needed by current images.
        assert len(images) == 1
        assert images[0].data.startswith(b"\xff\xd8")
        payload = PlannerPayload({"canonicalSharedContext": build_canonical_shared_context({"attachmentContext": context})}, images)
        assert "base64" not in json.dumps(payload)
        assert "data" not in images[0].model_dump() and "data=" not in repr(images[0])
        wire = json.loads(claude_input("read", images))
        assert wire["message"]["content"][-1]["source"]["media_type"] == "image/jpeg"


def test_expired_pending_upload_does_not_remove_bound_inputs(storage, monkeypatch):
    client, engine, (sid, _) = storage
    old, bound = upload(client, sid), upload(client, sid)
    client.post(f"/sessions/{sid}/messages", json={"contentMd": "saved", "attachmentIds": [bound["id"]]})
    with DbSession(engine) as db:
        for aid in [old["id"], bound["id"]]:
            row = db.get(MessageAttachment, aid); row.created_at = utc_now() - timedelta(days=2); db.add(row)
        db.commit()
    upload(client, sid)
    with DbSession(engine) as db:
        assert db.get(MessageAttachment, old["id"]) is None
        assert db.get(MessageAttachment, bound["id"]).message_id


def test_pdf_extracts_real_page_text_and_limits_page_count():
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter(); page = writer.add_blank_page(width=400, height=300)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject(); stream.set_data(b"BT /F1 16 Tf 30 200 Td (PDF_ATTACHMENT_73) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    out = io.BytesIO(); writer.write(out)
    assert "PDF_ATTACHMENT_73" in parse_upload("requirements.pdf", out.getvalue())["text_content"]
    for _ in range(100): writer.add_blank_page(width=400, height=300)
    out = io.BytesIO(); writer.write(out)
    with pytest.raises(HTTPException, match="100"):
        parse_upload("requirements.pdf", out.getvalue())


def test_text_budget_retains_current_image_and_quoted_sources(storage):
    client, engine, (sid, other) = storage
    note = upload(client, sid, "note.txt", b"quoted reference")
    quoted = client.post(f"/sessions/{sid}/messages", json={"contentMd": "old", "attachmentIds": [note["id"]]}).json()["id"]
    image = upload(client, sid, "image.png", png())
    long = upload(client, sid, "long.txt", ("参考文字" * 15000).encode())
    mid = client.post(f"/sessions/{sid}/messages", json={"contentMd": "current", "attachmentIds": [long["id"], image["id"]], "context": {"quotedMessage": {"messageId": quoted}}}).json()["id"]
    with DbSession(engine) as db:
        result = select_attachment_context(db, sid, mid, pinned={"messages": []}, recent=[])
        assert len(json.dumps(result, ensure_ascii=True, indent=2)) <= ATTACHMENT_JSON_LIMIT
        assert len(resolve_image_inputs(db, sid, result)) == 1
        assert next(entry for entry in result["items"] if entry["id"] == long["id"])["truncated"]
        assert result["selection"]["omitted"] >= 1  # Older references yield to current inputs.
        # Selecting only the quoted file resolves bytes from its actual message.
        result = select_attachment_context(db, sid, quoted, pinned={"messages": []}, recent=[])
        assert result["items"][0]["text"] == "quoted reference"


def test_parser_timeout_and_environment_do_not_leak_credentials(monkeypatch):
    import subprocess

    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-enter-parser")
    def timeout(command, **kwargs):
        assert "ANTHROPIC_API_KEY" not in kwargs["env"]
        assert command[1] == "-I" and kwargs["timeout"] == 15
        assert kwargs["stderr"] == subprocess.DEVNULL
        raise subprocess.TimeoutExpired(command, 15)
    monkeypatch.setattr(attachments.subprocess, "run", timeout)
    with pytest.raises(HTTPException, match="解析超时"):
        parse_upload("a.txt", b"hello")
