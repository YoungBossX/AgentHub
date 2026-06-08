from __future__ import annotations

from typing import Any, Optional

SUPPORTED_CONTEXT_ITEM_KINDS = {
    "artifact",
    "deployment",
    "message",
    "note",
    "selected_text",
}

MAX_CONTEXT_ITEMS = 8
MAX_TITLE_CHARS = 160
MAX_SUMMARY_CHARS = 700
MAX_SELECTED_TEXT_CHARS = 2400
MAX_NOTE_CHARS = 1000
MAX_METADATA_ITEMS = 20

PROTECTED_KEY_MARKERS = (
    "secret",
    "token",
    "password",
    "api_key",
    "apikey",
)
PROTECTED_STRING_MARKERS = (
    ".env",
    ".git",
    "node_modules",
    ".venv",
    "secrets/",
    "/secrets",
) + PROTECTED_KEY_MARKERS


def normalize_context_items(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize v1 follow-up context into bounded, provider-safe items."""

    raw_items = _explicit_context_items(context)
    raw_items.extend(_legacy_context_items(context))
    normalized = [
        _normalize_context_item(item, index=index)
        for index, item in enumerate(raw_items[:MAX_CONTEXT_ITEMS])
    ]
    return normalized


def _explicit_context_items(context: dict[str, Any]) -> list[dict[str, Any]]:
    raw_items = context.get("contextItems")
    if not isinstance(raw_items, list):
        return []
    return [item for item in raw_items if isinstance(item, dict)]


def _legacy_context_items(context: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    selected_artifact_id = _string_value(context.get("selectedArtifactId"))
    selected_artifact = context.get("selectedArtifact")
    if selected_artifact_id:
        selected = selected_artifact if isinstance(selected_artifact, dict) else {}
        kind = _string_value(selected.get("kind")) or "artifact"
        if kind == "workbench":
            kind = "artifact"
        items.append(
            {
                "kind": kind,
                "artifactId": selected_artifact_id,
                "artifactVersionId": _string_value(
                    context.get("selectedArtifactVersionId"),
                )
                or _string_value(selected.get("versionId")),
                "selectedText": selected.get("selectedText") or selected.get("sectionText"),
                "source": "legacy_selected_artifact",
                "summary": selected.get("safeSummary"),
                "title": selected.get("title"),
                "type": selected.get("type"),
            }
        )

    quoted_message = context.get("quotedMessage")
    if isinstance(quoted_message, dict):
        items.append(
            {
                "kind": "message",
                "messageId": quoted_message.get("messageId"),
                "source": "legacy_quoted_message",
                "summary": quoted_message.get("contentMd"),
                "title": quoted_message.get("senderType") or "Quoted message",
            }
        )
    return items


def _normalize_context_item(item: dict[str, Any], *, index: int) -> dict[str, Any]:
    kind = _string_value(item.get("kind")) or "unknown"
    if kind not in SUPPORTED_CONTEXT_ITEM_KINDS:
        return {
            "id": _item_id(item, index),
            "kind": kind,
            "valid": False,
            "reason": f"Unsupported context item kind `{kind}`.",
            "redacted": False,
            "source": _string_value(item.get("source")) or "explicit",
        }

    redacted = False
    title, title_redacted = _safe_text(item.get("title"), MAX_TITLE_CHARS)
    summary, summary_redacted = _safe_text(
        item.get("summary") or item.get("safeSummary"),
        MAX_SUMMARY_CHARS,
    )
    selected_text, selected_redacted = _safe_text(
        item.get("selectedText") or item.get("sectionText"),
        MAX_SELECTED_TEXT_CHARS,
    )
    note, note_redacted = _safe_text(
        item.get("note") or item.get("content"),
        MAX_NOTE_CHARS,
    )
    metadata, metadata_redacted = _safe_value(item.get("metadata"))
    redacted = any(
        [
            title_redacted,
            summary_redacted,
            selected_redacted,
            note_redacted,
            metadata_redacted,
        ]
    )

    normalized = {
        "id": _item_id(item, index),
        "kind": kind,
        "valid": True,
        "redacted": redacted,
        "source": _string_value(item.get("source")) or "explicit",
    }
    _put(normalized, "title", title)
    _put(normalized, "summary", summary)
    _put(normalized, "artifactId", _safe_identifier(item.get("artifactId")))
    _put(
        normalized,
        "artifactVersionId",
        _safe_identifier(item.get("artifactVersionId") or item.get("versionId")),
    )
    _put(normalized, "selectedText", selected_text)
    _put(normalized, "messageId", _safe_identifier(item.get("messageId")))
    _put(normalized, "deploymentId", _safe_identifier(item.get("deploymentId")))
    _put(normalized, "note", note)
    _put(normalized, "type", _safe_identifier(item.get("type")))
    if isinstance(metadata, dict) and metadata:
        normalized["metadata"] = metadata
    return normalized


def _safe_value(value: Any) -> tuple[Any, bool]:
    if isinstance(value, dict):
        redacted = False
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= MAX_METADATA_ITEMS:
                redacted = True
                break
            if _is_protected_key(key):
                redacted = True
                continue
            safe, item_redacted = _safe_value(item)
            redacted = redacted or item_redacted
            if safe is not None:
                result[str(key)] = safe
        return result, redacted
    if isinstance(value, list):
        redacted = False
        result = []
        for item in value[:MAX_METADATA_ITEMS]:
            safe, item_redacted = _safe_value(item)
            redacted = redacted or item_redacted
            if safe is not None:
                result.append(safe)
        if len(value) > MAX_METADATA_ITEMS:
            redacted = True
        return result, redacted
    if isinstance(value, str):
        return _safe_text(value, MAX_SUMMARY_CHARS)
    if isinstance(value, (bool, int, float)) or value is None:
        return value, False
    return str(value)[:MAX_SUMMARY_CHARS], True


def _safe_text(value: Any, limit: int) -> tuple[Optional[str], bool]:
    if not isinstance(value, str) or not value:
        return None, False
    normalized = value.replace("\\", "/").lower()
    if normalized.startswith("/") or any(
        marker in normalized for marker in PROTECTED_STRING_MARKERS
    ):
        return "[redacted]", True
    if len(value) > limit:
        return f"{value[: max(limit - 3, 0)].rstrip()}...", True
    return value, False


def _safe_identifier(value: Any) -> Optional[str]:
    safe, _ = _safe_text(value, MAX_TITLE_CHARS)
    return safe


def _item_id(item: dict[str, Any], index: int) -> str:
    raw_id = _safe_identifier(item.get("id"))
    if raw_id:
        return raw_id
    kind = _string_value(item.get("kind")) or "context"
    artifact_id = _safe_identifier(item.get("artifactId"))
    message_id = _safe_identifier(item.get("messageId"))
    deployment_id = _safe_identifier(item.get("deploymentId"))
    suffix = artifact_id or message_id or deployment_id or str(index + 1)
    return f"{kind}:{suffix}"


def _string_value(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _is_protected_key(key: Any) -> bool:
    normalized = str(key).lower()
    return any(marker in normalized for marker in PROTECTED_KEY_MARKERS)


def _put(target: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        target[key] = value
