from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.dependencies import get_db
from app.message_history import message_content, message_page, single_message

router = APIRouter()
Cursor = Annotated[str | None, Query(min_length=1, max_length=80)]


@router.get("/sessions/{session_id}/messages/page")
def read_message_page(session_id: str, limit: Annotated[int, Query(ge=1, le=200)] = 80,
                      before: Cursor = None, after: Cursor = None, around: Cursor = None, db: Session = Depends(get_db)):
    return message_page(db, session_id, limit=limit, before=before, after=after, around=around)


@router.get("/sessions/{session_id}/messages/{message_id}")
def read_single_message(session_id: str, message_id: str, db: Session = Depends(get_db)):
    return single_message(db, session_id, message_id)


@router.get("/sessions/{session_id}/messages/{message_id}/content")
def read_message_content(session_id: str, message_id: str, offset: Annotated[int, Query(ge=0)] = 0,
                         limit: Annotated[int, Query(ge=1, le=12000)] = 12000, db: Session = Depends(get_db)):
    return message_content(db, session_id, message_id, offset=offset, limit=limit)
