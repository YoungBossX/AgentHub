from dataclasses import asdict, dataclass
import json
from typing import Any, Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.canonical_context import filter_protected_values
from app.models import Artifact, Deployment, Task, TaskRun

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
    if artifact.artifact_type == "deployment":
        metadata = _deployment_reference_metadata(db, artifact, metadata)
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


def _deployment_reference_metadata(
    db: DbSession,
    artifact: Artifact,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    deployment = db.exec(
        select(Deployment).where(Deployment.artifact_id == artifact.id),
    ).first()
    source = _dict_value(metadata.get("source"))
    return {
        "provider": _safe_text(
            deployment.provider if deployment is not None else metadata.get("provider"),
        ),
        "providerType": _safe_text(metadata.get("providerType")),
        "environment": _safe_text(
            deployment.environment if deployment is not None else metadata.get("environment"),
        ),
        "status": _safe_text(
            deployment.status if deployment is not None else artifact.status,
        ),
        "url": _safe_text(deployment.url if deployment is not None else metadata.get("url")),
        "targetId": _safe_text(metadata.get("targetId")),
        "source": {
            "previewId": _safe_text(source.get("previewId") or metadata.get("previewId")),
            "previewArtifactId": _safe_text(
                source.get("previewArtifactId") or metadata.get("previewArtifactId"),
            ),
            "diffArtifactId": _safe_text(source.get("diffArtifactId")),
            "reviewArtifactId": _safe_text(source.get("reviewArtifactId")),
        },
        "logsSummary": _safe_logs(metadata.get("logs")),
        "statusHistory": _safe_status_history(metadata.get("statusHistory")),
    }


def _safe_summary(artifact: Artifact, metadata: dict[str, Any]) -> str:
    summary = metadata.get("summary") or metadata.get("safeSummary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    if artifact.artifact_type == "deployment":
        provider = metadata.get("provider") or "unknown provider"
        status = metadata.get("status") or artifact.status
        environment = metadata.get("environment") or "unknown environment"
        url = metadata.get("url") or "no URL"
        return f"Deployment {status} via {provider} in {environment}; URL: {url}."
    return f"{artifact.title} ({artifact.artifact_type})"


def _json_dict(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_logs(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    logs: list[str] = []
    for item in value[:5]:
        text = _safe_text(item)
        if isinstance(text, str) and text:
            logs.append(text)
    return logs


def _safe_status_history(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    history: list[dict[str, str]] = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        status = _safe_text(item.get("status"))
        message = _safe_text(item.get("message"))
        entry: dict[str, str] = {}
        if isinstance(status, str) and status:
            entry["status"] = status
        if isinstance(message, str) and message:
            entry["message"] = message
        if entry:
            history.append(entry)
    return history


def _safe_text(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("\\", "/").lower()
    if normalized.startswith("/") or any(
        marker in normalized
        for marker in [
            ".env",
            ".git",
            "node_modules",
            ".venv",
            "secrets/",
            "/secrets",
            "secret",
            "token",
            "password",
            "api_key",
            "apikey",
        ]
    ):
        return "[redacted]"
    return value[:500]
