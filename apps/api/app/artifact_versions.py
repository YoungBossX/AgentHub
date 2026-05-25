import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.models import Artifact, ArtifactVersion


class ArtifactVersionError(ValueError):
    pass


@dataclass(frozen=True)
class StoredArtifactVersion:
    id: str
    artifact_id: str
    version: int
    source_task_run_id: Optional[str]
    parent_artifact_id: Optional[str]
    git_base_ref: Optional[str]
    git_head_ref: Optional[str]
    changed_files: list[str]
    summary: str
    created_at: datetime


def record_artifact_version(
    db: DbSession,
    artifact: Artifact,
    *,
    source_task_run_id: Optional[str] = None,
    parent_artifact_id: Optional[str] = None,
    git_base_ref: Optional[str] = None,
    git_head_ref: Optional[str] = None,
    changed_files: Optional[list[str]] = None,
    summary: str = "",
    version: Optional[int] = None,
) -> StoredArtifactVersion:
    existing = db.exec(
        select(ArtifactVersion).where(
            ArtifactVersion.artifact_id == artifact.id,
            ArtifactVersion.version == (version or artifact.version),
        )
    ).first()
    if existing is not None:
        return _to_stored_artifact_version(existing)

    record = ArtifactVersion(
        artifact_id=artifact.id,
        version=version or artifact.version,
        source_task_run_id=source_task_run_id or artifact.task_run_id,
        parent_artifact_id=parent_artifact_id,
        git_base_ref=git_base_ref,
        git_head_ref=git_head_ref,
        changed_files_json=json.dumps(changed_files or [], separators=(",", ":")),
        summary=summary,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _to_stored_artifact_version(record)


def list_artifact_versions(
    db: DbSession,
    artifact_id: str,
) -> list[StoredArtifactVersion]:
    artifact = db.get(Artifact, artifact_id)
    if artifact is None:
        raise ArtifactVersionError(f"Artifact not found: {artifact_id}")
    records = db.exec(
        select(ArtifactVersion)
        .where(ArtifactVersion.artifact_id == artifact_id)
        .order_by(ArtifactVersion.version, ArtifactVersion.created_at, ArtifactVersion.id)
    ).all()
    return [_to_stored_artifact_version(record) for record in records]


def _to_stored_artifact_version(record: ArtifactVersion) -> StoredArtifactVersion:
    return StoredArtifactVersion(
        id=record.id,
        artifact_id=record.artifact_id,
        version=record.version,
        source_task_run_id=record.source_task_run_id,
        parent_artifact_id=record.parent_artifact_id,
        git_base_ref=record.git_base_ref,
        git_head_ref=record.git_head_ref,
        changed_files=_json_list(record.changed_files_json),
        summary=record.summary,
        created_at=record.created_at,
    )


def _json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str)]
