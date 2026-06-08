import json

from app.artifact_versions import StoredArtifactVersion
from app.artifact_workbench import (
    artifact_workbench_metadata,
    classify_artifact_renderer,
    is_artifact_editable,
)
from app.models import Artifact, utc_now


def test_artifact_renderer_classification_covers_supported_and_unknown_types() -> None:
    assert classify_artifact_renderer("preview") == "web_preview"
    assert classify_artifact_renderer("markdown_document") == "markdown_document"
    assert classify_artifact_renderer("text_document") == "text_document"
    assert classify_artifact_renderer("command_evidence") == "text_document"
    assert classify_artifact_renderer("code_snippet") == "code_snippet"
    assert classify_artifact_renderer("diff") == "diff"
    assert classify_artifact_renderer("review") == "review"
    assert classify_artifact_renderer("deployment") == "deployment"
    assert classify_artifact_renderer("mystery") == "unknown"


def test_artifact_editable_flag_is_limited_to_text_like_authoring_artifacts() -> None:
    assert is_artifact_editable("markdown_document") is True
    assert is_artifact_editable("text_document") is True
    assert is_artifact_editable("code_snippet") is True
    assert is_artifact_editable("command_evidence") is False
    assert is_artifact_editable("diff") is False
    assert is_artifact_editable("review") is False
    assert is_artifact_editable("deployment") is False
    assert is_artifact_editable("unknown") is False


def test_artifact_workbench_metadata_redacts_meta_and_records_hash() -> None:
    artifact = Artifact(
        id="artifact-1",
        task_run_id="task-run-1",
        artifact_type="markdown_document",
        title="Release Notes",
        status="ready",
        version=2,
        storage_uri="/Users/example/project/.env",
        meta_json=json.dumps(
            {
                "apiToken": "sk-secret",
                "safePath": "docs/change-log.md",
                "unsafePath": "/Users/example/project/secrets/key.txt",
                "nested": ["src/App.tsx", "node_modules/pkg/index.js"],
            }
        ),
    )

    metadata = artifact_workbench_metadata(
        artifact,
        versions=[
            StoredArtifactVersion(
                id="version-2",
                artifact_id="artifact-1",
                version=2,
                source_task_run_id="task-run-1",
                parent_artifact_id="artifact-0",
                git_base_ref=None,
                git_head_ref=None,
                changed_files=["docs/change-log.md"],
                summary="Edited release notes.",
                created_at=utc_now(),
            )
        ],
    )

    payload = metadata.to_payload()
    serialized = json.dumps(payload)
    assert payload["artifactId"] == "artifact-1"
    assert payload["rendererKind"] == "markdown_document"
    assert payload["editable"] is True
    assert payload["contentHash"].startswith("sha256:")
    assert payload["safeMeta"]["safePath"] == "docs/change-log.md"
    assert "apiToken" not in payload["safeMeta"]
    assert "sk-secret" not in serialized
    assert ".env" not in serialized
    assert "secrets/key" not in serialized
    assert "node_modules" not in serialized
    assert payload["versions"][0]["parentArtifactId"] == "artifact-0"
    assert payload["versions"][0]["contentHash"].startswith("sha256:")


def test_artifact_workbench_metadata_preserves_legacy_artifact_without_versions() -> None:
    artifact = Artifact(
        id="artifact-legacy",
        task_run_id="task-run-legacy",
        artifact_type="diff",
        title="Legacy diff",
        status="ready",
        version=1,
        meta_json="not-json",
    )

    metadata = artifact_workbench_metadata(artifact)
    payload = metadata.to_payload()

    assert payload["rendererKind"] == "diff"
    assert payload["editable"] is False
    assert payload["safeMeta"] == {}
    assert payload["versions"] == []
