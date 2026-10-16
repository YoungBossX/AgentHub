from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session

from app.dependencies import get_db
from app.review_repairs import confirm_issue, prepare_repair, repair_history

router = APIRouter()


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    issueIds: list[str] = Field(min_length=1, max_length=8)


class Confirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messageId: str = Field(max_length=80)
    issueId: str = Field(max_length=80)
    sourceFingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")


@router.get("/sessions/{session_id}/reviews/{artifact_id}/repair")
def read_repair(session_id: str, artifact_id: str, db: Session = Depends(get_db)):
    return repair_history(db, session_id, artifact_id)


@router.post("/sessions/{session_id}/reviews/{artifact_id}/repair/prepare")
def prepare(session_id: str, artifact_id: str, request: Selection, db: Session = Depends(get_db)):
    draft = prepare_repair(db, session_id, artifact_id, request.issueIds)
    return {key: draft[key] for key in ("contentMd", "selection")}


@router.post("/sessions/{session_id}/reviews/{artifact_id}/repair/confirm")
def confirm(session_id: str, artifact_id: str, request: Confirmation, db: Session = Depends(get_db)):
    return confirm_issue(db, session_id, artifact_id, request.messageId, request.issueId, request.sourceFingerprint, request.revision)
