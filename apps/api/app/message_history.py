"""Bounded read models; stored Messages and provider context remain untouched."""
from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select

from app.models import Message, Session

PREVIEW_CHARACTERS = 12000
PIN_LIMIT = 16


def _order(row, *, before):
    comparison = Message.created_at < row.created_at if before else Message.created_at > row.created_at
    tie = Message.id < row.id if before else Message.id > row.id
    return or_(comparison, and_(Message.created_at == row.created_at, tie))


def _preview_rows(db, session_id, *, where=None, limit=80, descending=True, pins=False):
    # Do not hydrate a full long body, or substitute preview content into the ORM
    # identity map: later planning/regeneration must still read the original.
    columns = [func.substr(Message.content_md, 1, PREVIEW_CHARACTERS).label(key)
               if key == "content_md" else getattr(Message, key) for key in Message.model_fields]
    query = select(*columns, func.length(Message.content_md).label("_characters"),
        (func.instr(Message.content_md, "\0") > 0).label("_unsupported")).where(Message.session_id == session_id)
    if where is not None:
        query = query.where(where)
    ordering = (Message.created_at.desc(), Message.id.desc()) if descending else (Message.created_at, Message.id)
    if pins:
        ordering = (Message.pinned_at.desc(), *ordering)
    mappings = db.execute(query.order_by(*ordering).limit(limit)).mappings().all()
    return [(Message.model_validate({key: row[key] for key in Message.model_fields}), None if row["_unsupported"] else row["_characters"]) for row in mappings]


def _anchor(db, session_id, message_id):
    value = db.execute(select(Message.id, Message.created_at).where(Message.id == message_id, Message.session_id == session_id)).first()
    if value is None:
        raise HTTPException(404, "Message cursor not found in this Session.")
    return value


def _response_rows(db, session_id, rows):
    from app.attachments import metadata_for_messages
    from app.message_regeneration import attachment_source, regeneration_view
    from app.routes.messages import message_response

    messages = [row[0] for row in rows]
    known = {row.id for row in messages}
    parents = {row.parent_message_id for row in messages if row.parent_message_id and row.parent_message_id not in known}
    extra = _preview_rows(db, session_id, where=Message.id.in_(parents), limit=len(parents)) if parents else []
    view = regeneration_view(db, session_id, [*messages, *(row[0] for row in extra)])
    owners = list({attachment_source(db, message) for message in messages})
    attachments = metadata_for_messages(db, session_id, owners)
    return [message_response(db, message, view=view, attachments=attachments).model_copy(update={
        "content_characters": count, "content_truncated": count is None or count > PREVIEW_CHARACTERS,
    }).model_dump(mode="json", by_alias=True) for message, count in rows]


def message_page(db, session_id, *, limit=80, before=None, after=None, around=None):
    if db.get(Session, session_id) is None:
        raise HTTPException(404, "Session not found")
    if not 1 <= limit <= 200 or sum(value is not None for value in (before, after, around)) > 1:
        raise HTTPException(400, "Choose one bounded history direction.")
    if any(value is not None and (not isinstance(value, str) or not 1 <= len(value) <= 80) for value in (before, after, around)):
        raise HTTPException(400, "Invalid history cursor.")
    anchor = _anchor(db, session_id, before or after or around) if before or after or around else None
    if around:
        lower = _preview_rows(db, session_id, where=_order(anchor, before=True), limit=limit // 2)
        middle = _preview_rows(db, session_id, where=Message.id == around, limit=1)
        upper = _preview_rows(db, session_id, where=_order(anchor, before=False), limit=limit - len(lower) - 1, descending=False)
        rows = [*reversed(lower), *middle, *upper]
    else:
        rows = _preview_rows(db, session_id, where=_order(anchor, before=bool(before)) if anchor else None, limit=limit, descending=not bool(after))
        if not after:
            rows.reverse()
    latest = db.execute(select(Message.id).where(Message.session_id == session_id).order_by(Message.created_at.desc(), Message.id.desc()).limit(1)).scalar_one_or_none()
    total = db.execute(select(func.count()).select_from(Message).where(Message.session_id == session_id)).scalar_one()
    pinned_total = db.execute(select(func.count()).select_from(Message).where(Message.session_id == session_id, Message.pinned_at.is_not(None))).scalar_one()
    pinned = _preview_rows(db, session_id, where=Message.pinned_at.is_not(None), limit=PIN_LIMIT, pins=True)
    def exists(condition):
        return db.execute(select(Message.id).where(Message.session_id == session_id, condition).limit(1)).first() is not None
    has_older = exists(_order(rows[0][0], before=True)) if rows else False
    has_newer = exists(_order(rows[-1][0], before=False)) if rows else bool(latest and before)
    return {"messages": _response_rows(db, session_id, rows), "pinnedMessages": _response_rows(db, session_id, pinned),
        "pinnedTotal": pinned_total, "total": total, "hasOlder": has_older, "hasNewer": has_newer,
        "olderCursor": rows[0][0].id if rows else None, "newerCursor": rows[-1][0].id if rows else None,
        "latestMessageId": latest, "previewCharacterLimit": PREVIEW_CHARACTERS}


def single_message(db, session_id, message_id):
    _anchor(db, session_id, message_id)
    return _response_rows(db, session_id, _preview_rows(db, session_id, where=Message.id == message_id, limit=1))[0]


def message_content(db, session_id, message_id, *, offset=0, limit=12000):
    if offset < 0 or not 1 <= limit <= PREVIEW_CHARACTERS:
        raise HTTPException(400, "Choose a bounded content segment.")
    row = db.execute(select(func.substr(Message.content_md, offset + 1, limit), func.length(Message.content_md), func.instr(Message.content_md, "\0"))
        .where(Message.session_id == session_id, Message.id == message_id)).first()
    if row is None:
        raise HTTPException(404, "Message not found in this Session.")
    text, count, unsupported = row
    if unsupported:
        raise HTTPException(409, "消息含 NUL 控制字符，不支持文本分段；原始内容仍完整保存在数据库中。")
    if offset > count:
        raise HTTPException(400, "Content offset exceeds this message.")
    return {"messageId": message_id, "text": text, "offset": offset, "totalCharacters": count,
        "nextOffset": offset + len(text) if offset + len(text) < count else None,
        "previousOffset": max(0, offset - limit) if offset else None, "unit": "Unicode code points"}
