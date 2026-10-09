from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import delete
from sqlmodel import Session as DbSession
from starlette.concurrency import run_in_threadpool

from app.attachments import MAX_UPLOAD_BYTES, attachment_metadata, create_attachment, parse_upload, validated_filename
from app.dependencies import get_db
from app.models import MessageAttachment, Session

router = APIRouter()


@router.post("/sessions/{session_id}/attachments", status_code=201)
async def upload_attachment(session_id: str, request: Request, filename: str = Query(max_length=180), db: DbSession = Depends(get_db)) -> dict:
    validated_filename(filename)
    content_length = request.headers.get("content-length")
    if content_length and (not content_length.isdigit() or int(content_length) > MAX_UPLOAD_BYTES):
        raise HTTPException(413, "附件不能超过 8 MiB。")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "附件不能超过 8 MiB。")
        data.extend(chunk)
    payload = bytes(data)
    parsed = await run_in_threadpool(parse_upload, filename, payload)
    row = await run_in_threadpool(create_attachment, db, session_id, filename, payload, parsed)
    return attachment_metadata(row)


@router.get("/sessions/{session_id}/attachments/{attachment_id}/content")
def download_attachment(session_id: str, attachment_id: str, preview: bool = False, db: DbSession = Depends(get_db)) -> Response:
    row = db.get(MessageAttachment, attachment_id)
    if db.get(Session, session_id) is None or row is None or row.session_id != session_id:
        raise HTTPException(404, "Attachment not found in this Session")
    data, media, disposition = row.payload, "application/octet-stream", "attachment"
    if preview:
        if row.kind != "image" or not row.image_payload:
            raise HTTPException(415, "此附件不支持图片预览。")
        data, media, disposition = row.image_payload, row.image_media_type, "inline"
    return Response(data, media_type=media, headers={
        "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(row.filename, safe='')}",
        "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store",
        "Content-Security-Policy": "default-src 'none'; sandbox",
    })


@router.delete("/sessions/{session_id}/attachments/{attachment_id}", status_code=204)
def remove_pending_attachment(session_id: str, attachment_id: str, db: DbSession = Depends(get_db)) -> Response:
    row = db.get(MessageAttachment, attachment_id)
    if row is None or row.session_id != session_id:
        raise HTTPException(404, "Attachment not found in this Session")
    removed = db.execute(delete(MessageAttachment).where(MessageAttachment.id == attachment_id,
        MessageAttachment.session_id == session_id, MessageAttachment.message_id.is_(None)))
    if removed.rowcount != 1:
        raise HTTPException(409, "已发送附件不能删除，以保留消息和运行来源。")
    db.commit()
    return Response(status_code=204)
