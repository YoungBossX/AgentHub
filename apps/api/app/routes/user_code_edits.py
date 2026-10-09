from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlmodel import Session as DbSession

from app.dependencies import get_db
from app import user_code_edits as service
from app.user_patch import MAX_FILE_BYTES, MAX_PATCH_BYTES, UserPatchConflict, UserPatchError

router = APIRouter(prefix="/sessions/{session_id}/code-edits", tags=["user-code-edits"])


class PrepareEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operationId: str = Field(min_length=36, max_length=36)
    sourceArtifactId: str = Field(min_length=1, max_length=64)
    patch: str | None = Field(default=None, max_length=MAX_PATCH_BYTES)
    path: str | None = Field(default=None, max_length=1024)
    content: str | None = Field(default=None, max_length=MAX_FILE_BYTES)
    expectedSha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    expectedBinding: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def one_mode(self):
        if self.patch is not None:
            if any(value is not None for value in [self.path, self.content, self.expectedSha256, self.expectedBinding]):
                raise ValueError("Use either a patch or a complete-file edit.")
        elif self.path is None or self.content is None or self.expectedBinding is None:
            raise ValueError("Complete-file edits require a loaded source version.")
        return self


class ResolveEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["inspect", "keep_current"] = "inspect"


def _call(db, function, *args, **kwargs):
    try:
        return function(db, *args, **kwargs)
    except (UserPatchError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=409 if isinstance(exc, UserPatchConflict) else 400, detail=str(exc)) from exc


@router.get("/source")
def source(session_id: str, sourceArtifactId: str, path: str, db: DbSession = Depends(get_db)):
    return _call(db, service.read_source, session_id, sourceArtifactId, path)


@router.get("")
def operations(session_id: str, db: DbSession = Depends(get_db)):
    return service.list_operations(db, session_id)


@router.post("")
def prepare(session_id: str, request: PrepareEdit, db: DbSession = Depends(get_db)):
    return _call(db, service.prepare_edit, session_id, request.sourceArtifactId, request.operationId,
                 patch=request.patch, path=request.path, content=request.content,
                 expected_sha256=request.expectedSha256, expected_binding=request.expectedBinding)


@router.post("/{operation_id}/apply")
def apply(session_id: str, operation_id: str, db: DbSession = Depends(get_db)):
    return _call(db, service.apply_edit, session_id, operation_id)


@router.post("/{operation_id}/resolve")
def resolve(session_id: str, operation_id: str, request: ResolveEdit, db: DbSession = Depends(get_db)):
    return _call(db, service.reconcile_edit, session_id, operation_id, keep_current=request.action == "keep_current")
