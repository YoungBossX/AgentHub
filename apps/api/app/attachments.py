"""Session-scoped immutable upload storage and public metadata."""

import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, func, update
from sqlalchemy.orm import load_only
from sqlmodel import Session as DbSession, select

from app.models import Message, MessageAttachment, Session, utc_now

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_MESSAGE_ATTACHMENTS = 4
MAX_SESSION_BYTES = 128 * 1024 * 1024
MAX_SESSION_ATTACHMENTS = 256
TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".jsonl", ".yaml", ".yml", ".xml",
                   ".py", ".js", ".jsx", ".ts", ".tsx", ".css", ".html", ".sql", ".java", ".go", ".rs", ".c", ".cpp", ".h", ".log"}
IMAGE_EXTENSIONS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
META_FIELDS = ["id", "session_id", "message_id", "position", "filename", "kind", "media_type", "byte_size", "sha256",
               "extraction_status", "text_truncated", "image_width", "image_height", "image_sha256", "created_at"]


def validated_filename(filename: str) -> tuple[str, str]:
    if not filename or len(filename) > 180 or filename != filename.strip() or any(ord(c) < 32 for c in filename):
        raise HTTPException(422, "附件文件名无效。")
    if any(c in filename for c in '/\\:*?"<>|') or filename in {".", ".."} or filename.endswith((".", " ")):
        raise HTTPException(422, "附件只能使用文件名，不能包含路径。")
    lowered = filename.lower()
    if lowered.startswith(".env") or lowered in {".git", "secrets", "node_modules"}:
        raise HTTPException(422, "不能上传受保护的配置或凭据文件。")
    extension = Path(filename).suffix.lower()
    kind = "text" if extension in TEXT_EXTENSIONS else "image" if extension in IMAGE_EXTENSIONS else "pdf" if extension == ".pdf" else None
    if kind is None:
        raise HTTPException(415, "支持 UTF-8 文本/代码、PDF 和 PNG/JPEG/WebP 图片；不支持此格式。")
    return filename, kind


def parse_upload(filename: str, data: bytes) -> dict[str, Any]:
    _, kind = validated_filename(filename)
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "附件为空或超过 8 MiB。")
    environment = {key: value for key, value in os.environ.items() if key.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "LANG"}}
    try:
        completed = subprocess.run([sys.executable, "-I", str(Path(__file__).with_name("attachment_parser.py")), kind],
            input=data, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15, env=environment, check=False)
        if len(completed.stdout) > 8 * 1024 * 1024:
            raise ValueError("Parser output exceeds limit")
        result = json.loads(completed.stdout)
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(422, "附件解析超时，请缩小文件或重新导出。") from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(422, "附件解析失败，请检查本地依赖和文件格式。") from exc
    if completed.returncode != 0 or result.get("ok") is not True:
        raise HTTPException(422, result.get("error", "附件解析失败。"))
    value = result["value"]
    if kind == "image" and value["media_type"] != IMAGE_EXTENSIONS[Path(filename).suffix.lower()]:
        raise HTTPException(422, "图片扩展名与实际格式不一致。")
    if "image_base64" in value:
        image = base64.b64decode(value.pop("image_base64"), validate=True)
        value.update(image_payload=image, image_sha256=hashlib.sha256(image).hexdigest())
    return value


def attachment_metadata(row: MessageAttachment) -> dict[str, Any]:
    return {"id": row.id, "sessionId": row.session_id, "messageId": row.message_id,
            "filename": row.filename, "kind": row.kind, "mediaType": row.media_type,
            "byteSize": row.byte_size, "sha256": row.sha256, "extractionStatus": row.extraction_status,
            "textTruncated": row.text_truncated, "imageWidth": row.image_width, "imageHeight": row.image_height,
            "imageSha256": row.image_sha256, "createdAt": row.created_at.isoformat() + "Z"}


def create_attachment(db: DbSession, session_id: str, filename: str, data: bytes, parsed: dict) -> MessageAttachment:
    # Serializes quota checking and insertion, including competing uploads.
    db.connection().exec_driver_sql("BEGIN IMMEDIATE")
    if db.get(Session, session_id) is None:
        raise HTTPException(404, "Session not found")
    db.execute(delete(MessageAttachment).where(MessageAttachment.session_id == session_id,
        MessageAttachment.message_id.is_(None), MessageAttachment.created_at < utc_now() - timedelta(hours=24)))
    count, size = db.exec(select(func.count(MessageAttachment.id), func.coalesce(func.sum(MessageAttachment.byte_size), 0))
        .where(MessageAttachment.session_id == session_id)).one()
    if count >= MAX_SESSION_ATTACHMENTS or size + len(data) > MAX_SESSION_BYTES:
        raise HTTPException(413, "当前会话附件已达 256 个或 128 MiB，请移除未发送附件或新建会话。")
    row = MessageAttachment(session_id=session_id, filename=filename, byte_size=len(data),
        sha256=hashlib.sha256(data).hexdigest(), payload=data, **parsed)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def bind_message_attachments(db: DbSession, message: Message, ids: list[str]) -> None:
    if not ids:
        return
    if message.sender_type != "user" or len(ids) > MAX_MESSAGE_ATTACHMENTS or len(ids) != len(set(ids)):
        raise HTTPException(422, "每条用户消息最多绑定 4 个不同附件。")
    db.add(message)
    db.flush()
    for position, attachment_id in enumerate(ids):
        bound = db.execute(update(MessageAttachment).where(MessageAttachment.id == attachment_id,
            MessageAttachment.session_id == message.session_id, MessageAttachment.message_id.is_(None))
            .values(message_id=message.id, position=position).execution_options(synchronize_session=False))
        if bound.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "附件不存在、已被发送或不属于当前会话，请重新选择。")


def metadata_for_messages(db: DbSession, session_id: str, ids: list[str]) -> dict[str, list[dict]]:
    if not ids:
        return {}
    rows = db.exec(select(MessageAttachment).options(load_only(*(getattr(MessageAttachment, name) for name in META_FIELDS)))
        .where(MessageAttachment.session_id == session_id, MessageAttachment.message_id.in_(ids))
        .order_by(MessageAttachment.position, MessageAttachment.created_at, MessageAttachment.id)).all()
    result: dict[str, list[dict]] = {}
    for row in rows:
        result.setdefault(row.message_id, []).append(attachment_metadata(row))
    return result
