from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from app.artifact_versions import StoredArtifactVersion
from app.canonical_context import filter_protected_values
from app.models import Artifact

ArtifactRendererKind = str

WEB_PREVIEW_TYPES = {"preview", "web_preview", "staging_preview"}
MARKDOWN_DOCUMENT_TYPES = {"markdown", "markdown_document", "document"}
TEXT_DOCUMENT_TYPES = {"text", "text_document", "command_evidence", "handoff"}
CODE_SNIPPET_TYPES = {"code", "code_snippet"}
EDITABLE_ARTIFACT_TYPES = {"markdown_document", "text_document", "code_snippet"}


@dataclass(frozen=True)
class ArtifactVersionWorkbenchMetadata:
    id: str
    artifact_id: str
    version: int
    source_task_run_id: Optional[str]
    parent_artifact_id: Optional[str]
    git_base_ref: Optional[str]
    git_head_ref: Optional[str]
    changed_files: list[str]
    summary: str
    content_hash: str
    created_at: datetime

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "artifactId": self.artifact_id,
            "version": self.version,
            "sourceTaskRunId": self.source_task_run_id,
            "parentArtifactId": self.parent_artifact_id,
            "gitBaseRef": self.git_base_ref,
            "gitHeadRef": self.git_head_ref,
            "changedFiles": self.changed_files,
            "summary": self.summary,
            "contentHash": self.content_hash,
            "createdAt": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class ArtifactWorkbenchMetadata:
    artifact_id: str
    task_run_id: str
    artifact_type: str
    title: str
    status: str
    version: int
    renderer_kind: ArtifactRendererKind
    editable: bool
    content_hash: str
    safe_meta: dict[str, Any]
    versions: list[ArtifactVersionWorkbenchMetadata]
    created_at: datetime
    updated_at: datetime

    def to_payload(self) -> dict[str, Any]:
        return {
            "artifactId": self.artifact_id,
            "taskRunId": self.task_run_id,
            "artifactType": self.artifact_type,
            "title": self.title,
            "status": self.status,
            "version": self.version,
            "rendererKind": self.renderer_kind,
            "editable": self.editable,
            "contentHash": self.content_hash,
            "safeMeta": self.safe_meta,
            "versions": [version.to_payload() for version in self.versions],
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }


def artifact_workbench_metadata(
    artifact: Artifact,
    *,
    versions: Optional[list[StoredArtifactVersion]] = None,
) -> ArtifactWorkbenchMetadata:
    safe_meta = safe_artifact_meta(artifact)
    renderer_kind = classify_artifact_renderer(artifact.artifact_type)
    return ArtifactWorkbenchMetadata(
        artifact_id=artifact.id,
        task_run_id=artifact.task_run_id,
        artifact_type=artifact.artifact_type,
        title=artifact.title,
        status=artifact.status,
        version=artifact.version,
        renderer_kind=renderer_kind,
        editable=is_artifact_editable(artifact.artifact_type),
        content_hash=_artifact_content_hash(
            artifact,
            safe_meta=safe_meta,
            renderer_kind=renderer_kind,
        ),
        safe_meta=safe_meta,
        versions=[
            _version_metadata(version, artifact=artifact, safe_meta=safe_meta)
            for version in (versions or [])
        ],
        created_at=artifact.created_at,
        updated_at=artifact.updated_at,
    )


def classify_artifact_renderer(artifact_type: str) -> ArtifactRendererKind:
    normalized = artifact_type.strip().lower()
    if normalized in WEB_PREVIEW_TYPES:
        return "web_preview"
    if normalized in MARKDOWN_DOCUMENT_TYPES:
        return "markdown_document"
    if normalized in TEXT_DOCUMENT_TYPES:
        return "text_document"
    if normalized in CODE_SNIPPET_TYPES:
        return "code_snippet"
    if normalized in {"diff", "review", "deployment"}:
        return normalized
    return "unknown"


def is_artifact_editable(artifact_type: str) -> bool:
    return classify_artifact_renderer(artifact_type) in EDITABLE_ARTIFACT_TYPES and (
        artifact_type.strip().lower() in EDITABLE_ARTIFACT_TYPES
    )


def safe_artifact_meta(artifact: Artifact) -> dict[str, Any]:
    try:
        parsed = json.loads(artifact.meta_json)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    filtered = filter_protected_values(parsed)
    return filtered if isinstance(filtered, dict) else {}


def _version_metadata(
    version: StoredArtifactVersion,
    *,
    artifact: Artifact,
    safe_meta: dict[str, Any],
) -> ArtifactVersionWorkbenchMetadata:
    return ArtifactVersionWorkbenchMetadata(
        id=version.id,
        artifact_id=version.artifact_id,
        version=version.version,
        source_task_run_id=version.source_task_run_id,
        parent_artifact_id=version.parent_artifact_id,
        git_base_ref=version.git_base_ref,
        git_head_ref=version.git_head_ref,
        changed_files=version.changed_files,
        summary=version.summary,
        content_hash=_hash_payload(
            {
                "artifactId": version.artifact_id,
                "version": version.version,
                "summary": version.summary,
                "changedFiles": version.changed_files,
                "artifactContentHash": _artifact_content_hash(
                    artifact,
                    safe_meta=safe_meta,
                    renderer_kind=classify_artifact_renderer(artifact.artifact_type),
                ),
            }
        ),
        created_at=version.created_at,
    )


def _artifact_content_hash(
    artifact: Artifact,
    *,
    safe_meta: dict[str, Any],
    renderer_kind: ArtifactRendererKind,
) -> str:
    return _hash_payload(
        {
            "artifactType": artifact.artifact_type,
            "title": artifact.title,
            "status": artifact.status,
            "version": artifact.version,
            "rendererKind": renderer_kind,
            "safeMeta": safe_meta,
        }
    )


def _hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
