from dataclasses import asdict, dataclass
import json
from typing import Any, Optional

from sqlmodel import Session as DbSession

from app.models import Artifact, Task, TaskRun

SUPPORTED_ARTIFACT_REFERENCE_TYPES = {"diff", "review", "preview", "deployment"}


@dataclass(frozen=True)
class ArtifactReference:
    artifact_id: str
    artifact_type: str
    task_run_id: str
    title: str
    status: str
    valid: bool
    reason: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

    def to_context(self) -> dict[str, Any]:
        return asdict(self)


def artifact_reference_for_id(
    db: DbSession,
    *,
    session_id: str,
    artifact_id: str,
) -> ArtifactReference:
    artifact = db.get(Artifact, artifact_id)
    if artifact is None:
        return ArtifactReference(
            artifact_id=artifact_id,
            artifact_type="unknown",
            task_run_id="",
            title="Missing artifact",
            status="missing",
            valid=False,
            reason="Selected artifact was not found.",
            metadata={},
        )

    task_run = db.get(TaskRun, artifact.task_run_id)
    task = db.get(Task, task_run.task_id) if task_run is not None else None
    if task is None or task.session_id != session_id:
        return ArtifactReference(
            artifact_id=artifact.id,
            artifact_type=artifact.artifact_type,
            task_run_id=artifact.task_run_id,
            title=artifact.title,
            status=artifact.status,
            valid=False,
            reason="Selected artifact does not belong to this session.",
            metadata={},
        )

    if artifact.artifact_type not in SUPPORTED_ARTIFACT_REFERENCE_TYPES:
        return ArtifactReference(
            artifact_id=artifact.id,
            artifact_type=artifact.artifact_type,
            task_run_id=artifact.task_run_id,
            title=artifact.title,
            status=artifact.status,
            valid=False,
            reason=(
                f"Artifact references for `{artifact.artifact_type}` are not "
                "supported in P12."
            ),
            metadata={},
        )

    return ArtifactReference(
        artifact_id=artifact.id,
        artifact_type=artifact.artifact_type,
        task_run_id=artifact.task_run_id,
        title=artifact.title,
        status=artifact.status,
        valid=True,
        metadata=_json_dict(artifact.meta_json),
    )


def selected_artifact_reference(
    db: DbSession,
    *,
    session_id: str,
    context: dict[str, Any],
) -> Optional[dict[str, Any]]:
    artifact_id = selected_artifact_id(context)
    if artifact_id is None:
        return None
    return artifact_reference_for_id(
        db,
        session_id=session_id,
        artifact_id=artifact_id,
    ).to_context()


def selected_artifact_id(context: dict[str, Any]) -> Optional[str]:
    value = context.get("selectedArtifactId")
    if isinstance(value, str) and value:
        return value
    selected = context.get("selectedArtifact")
    if isinstance(selected, dict):
        nested = selected.get("artifactId") or selected.get("id")
        if isinstance(nested, str) and nested:
            return nested
    return None


def _json_dict(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
