"""Source-bound regeneration through existing planning and summary execution."""

import json

from fastapi import HTTPException
from sqlalchemy import update
from sqlmodel import Session as DbSession, select

from app.models import Message, Session, Task, TaskRun
from app.repositories import create_session_message
from app.task_runs import ACTIVE_STATES

SCHEMA = "message_regeneration_v1"


def metadata(message: Message) -> dict:
    try:
        value = json.loads(message.regeneration_json)
        return value if isinstance(value, dict) and value.get("schemaVersion") == SCHEMA else {}
    except (ValueError, TypeError):
        return {}


def attachment_source(db: DbSession, message: Message) -> str:
    source_id = metadata(message).get("attachmentSourceMessageId")
    source = db.get(Message, source_id) if isinstance(source_id, str) else None
    return source.id if source and source.session_id == message.session_id and source.sender_type == "user" else message.id


def source_request(db: DbSession, message: Message, messages: dict | None = None) -> Message | None:
    if message.sender_type not in {"orchestrator", "agent"} or message.message_kind not in {"chat", "plan", "group_summary"}:
        return None
    source = (messages.get(message.parent_message_id) if messages is not None else db.get(Message, message.parent_message_id)) if message.parent_message_id else None
    return source if source and source.session_id == message.session_id and source.sender_type == "user" else None


def regeneration_view(db: DbSession, session_id: str, messages: list[Message] | None = None) -> dict:
    messages = messages if messages is not None else list(db.exec(select(Message).where(Message.session_id == session_id)).all())
    busy = db.exec(select(TaskRun.id).join(Task, Task.id == TaskRun.task_id)
                   .where(Task.session_id == session_id, TaskRun.state.in_(ACTIVE_STATES))).first() is not None
    unfinished = set(db.exec(select(Task.created_by_message_id).where(Task.session_id == session_id,
                     Task.status.notin_({"completed", "failed", "cancelled", "interrupted"}))).all())
    return {"messages": {row.id: row for row in messages}, "busy": busy, "unfinished": unfinished,
            "preparing": any(metadata(row).get("state") == "preparing" for row in messages)}


def _reason(db: DbSession, message: Message, source: Message, view: dict) -> str | None:
    if message.stream_state != "complete":
        return "消息尚未完成；失败运行请使用任务重试。"
    if message.message_kind == "group_summary":
        from app.group_summaries import public_group_summary

        summary = public_group_summary(db, message)
        if not summary or not summary.get("current") or summary.get("state") != "completed":
            return "只能重新生成当前已完成的汇总；失败汇总请使用重试。"
        return None
    if view["busy"]:
        return "本会话还有运行或审批等待，请先完成或中断。"
    if source.id in view["unfinished"]:
        return "原请求仍有未完成任务，请先处理或取消原计划。"
    return None


def public_regeneration(db: DbSession, message: Message, view: dict | None = None) -> tuple[dict | None, dict | None]:
    view = view or regeneration_view(db, message.session_id)
    own = metadata(message)
    if not own and message.sender_type != "user":
        parent = view["messages"].get(message.parent_message_id)
        if parent and parent.session_id == message.session_id:
            own = metadata(parent)
    public = {key: own[key] for key in ("sourceMessageId", "requestMessageId", "operationId", "kind", "state", "errorCode") if key in own} or None
    if public and public.get("kind") == "summary":
        from app.group_summaries import public_group_summary

        summary = public_group_summary(db, message)
        if summary:
            public["state"] = summary.get("state")
    source = source_request(db, message, view["messages"])
    if source is None:
        return public, None
    reason = _reason(db, message, source, view)
    if view["preparing"]:
        reason = "本会话正在准备重新生成，请等待结果。"
    return public, {"kind": "summary" if message.message_kind == "group_summary" else "request",
                    "available": reason is None, "reason": reason}


def prepare_regeneration(db: DbSession, session_id: str, message_id: str, operation_id: str):
    """Claim a durable operation under the Session's SQLite write transaction."""
    # A no-op write obtains SQLite's reservation before any eligibility reads.
    db.execute(update(Session).where(Session.id == session_id).values(updated_at=Session.updated_at))
    db.expire_all()
    session, message = db.get(Session, session_id), db.get(Message, message_id)
    if not session or not message or message.session_id != session_id:
        raise HTTPException(404, "Message not found in this Session")
    existing = db.get(Message, operation_id)
    if existing:
        claim = metadata(existing)
        if existing.session_id != session_id or claim.get("sourceMessageId") != message_id or claim.get("operationId") != operation_id:
            raise HTTPException(409, "操作 ID 已被其他请求使用。")
        db.rollback()
        return existing, None, False
    source = source_request(db, message)
    if source is None:
        raise HTTPException(409, "该消息没有可重新生成的用户请求来源。")
    _, action = public_regeneration(db, message)
    if not action or not action["available"]:
        raise HTTPException(409, action["reason"] if action else "不能重新生成此消息。")
    claim = {"schemaVersion": SCHEMA, "sourceMessageId": message.id, "requestMessageId": source.id,
             "operationId": operation_id, "kind": action["kind"], "state": "preparing"}
    if action["kind"] == "summary":
        from app.group_summaries import prepare_group_summary

        claim["state"] = "calling"
        job = prepare_group_summary(db, source.id, regeneration=claim)
        if not job:
            raise HTTPException(409, "汇总输入或状态已变化，请刷新后重试。")
        return db.get(Message, job.message_id), job, True
    claim["attachmentSourceMessageId"] = attachment_source(db, source)
    created = Message(id=operation_id, session_id=session_id, sender_type="user", sender_id=source.sender_id,
                      content_md=source.content_md, message_kind="chat", parent_message_id=source.parent_message_id,
                      context_json=source.context_json, regeneration_json=json.dumps(claim, separators=(",", ":")))
    return create_session_message(db, session, created), None, True


def finish_request(db: DbSession, message_id: str, *, failed: bool) -> None:
    db.rollback()
    message = db.get(Message, message_id)
    if message is None:
        return
    previous = message.regeneration_json
    claim = metadata(message)
    if claim.get("kind") != "request" or claim.get("state") != "preparing":
        return
    claim["state"] = "failed" if failed else "submitted"
    if failed:
        claim["errorCode"] = "REGENERATION_PREPARATION_FAILED"
    db.execute(update(Message).where(Message.id == message_id, Message.regeneration_json == previous)
               .values(regeneration_json=json.dumps(claim, separators=(",", ":"))))
    db.commit()
    db.expire_all()


def recover_interrupted_requests(bind) -> int:
    """Single local API startup: retain requests, never resume model calls."""
    count = 0
    with DbSession(bind) as db:
        for message in db.exec(select(Message).where(Message.regeneration_json != "{}")).all():
            claim = metadata(message)
            if claim.get("kind") == "request" and claim.get("state") == "preparing":
                claim.update(state="failed", errorCode="REGENERATION_PREPARATION_INTERRUPTED")
                message.regeneration_json = json.dumps(claim, separators=(",", ":"))
                db.add(message)
                count += 1
        db.commit()
    return count
