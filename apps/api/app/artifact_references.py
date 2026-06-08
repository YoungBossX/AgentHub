from dataclasses import asdict, dataclass
import json
from typing import Any, Optional

from sqlmodel import Session as DbSession

from app.canonical_context import filter_protected_values
from app.models import Artifact, Task, TaskRun

SUPPORTED_ARTIFACT_REFERENCE_TYPES = {
    "code_snippet",
    "deployment",
    "diff",
    "markdown_document",
    "preview",
    "review",
    "text_document",
}


@dataclass(frozen=True)
class ArtifactReference:
    artifact_id: str
    artifact_type: str
    task_run_id: str
    title: str
    status: str
    valid: bool
    reason: Optional[str] = None
    version_id: Optional[str] = None
    selected_text: Optional[str] = None
    safe_summary: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

    def to_context(self) -> dict[str, Any]:
        return asdict(self)


def artifact_reference_for_id(
    db: DbSession,
    *,
    session_id: str,
    artifact_id: str,
    version_id: Optional[str] = None,
    selected_text: Optional[str] = None,
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
            version_id=version_id,
            selected_text=selected_text,
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
            version_id=version_id,
            selected_text=selected_text,
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
                "supported in P23."
            ),
            version_id=version_id,
            selected_text=selected_text,
            metadata={},
        )

    metadata = _safe_metadata(_json_dict(artifact.meta_json))
    return ArtifactReference(
        artifact_id=artifact.id,
        artifact_type=artifact.artifact_type,
        task_run_id=artifact.task_run_id,
        title=artifact.title,
        status=artifact.status,
        valid=True,
        version_id=version_id,
        selected_text=selected_text,
        safe_summary=_safe_summary(artifact, metadata),
        metadata=metadata,
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
        version_id=selected_artifact_version_id(context),
        selected_text=selected_artifact_text(context),
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


def selected_artifact_version_id(context: dict[str, Any]) -> Optional[str]:
    value = context.get("selectedArtifactVersionId")
    if isinstance(value, str) and value:
        return value
    selected = context.get("selectedArtifact")
    if isinstance(selected, dict):
        nested = selected.get("versionId") or selected.get("artifactVersionId")
        if isinstance(nested, str) and nested:
            return nested
    return None


def selected_artifact_text(context: dict[str, Any]) -> Optional[str]:
    value = context.get("selectedText")
    if isinstance(value, str) and value:
        return value
    selected = context.get("selectedArtifact")
    if isinstance(selected, dict):
        nested = selected.get("selectedText") or selected.get("sectionText")
        if isinstance(nested, str) and nested:
            return nested
    return None


def _safe_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    filtered = filter_protected_values(metadata)
    return filtered if isinstance(filtered, dict) else {}


def _safe_summary(artifact: Artifact, metadata: dict[str, Any]) -> str:
    summary = metadata.get("summary") or metadata.get("safeSummary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    return f"{artifact.title} ({artifact.artifact_type})"


def _json_dict(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
