from app.context_items import (
    MAX_CONTEXT_ITEMS,
    MAX_NOTE_CHARS,
    MAX_SELECTED_TEXT_CHARS,
    normalize_context_items,
)


def test_normalizes_legacy_selected_artifact_and_quoted_message() -> None:
    items = normalize_context_items(
        {
            "selectedArtifactId": "artifact-doc-1",
            "selectedArtifactVersionId": "version-2",
            "selectedArtifact": {
                "kind": "workbench",
                "safeSummary": "Selected section summary",
                "selectedText": "## Important section",
                "title": "Release notes",
                "type": "markdown_document",
            },
            "quotedMessage": {
                "contentMd": "Please keep this requirement.",
                "messageId": "message-1",
                "senderType": "user",
            },
        }
    )

    assert items == [
        {
            "id": "artifact:artifact-doc-1",
            "kind": "artifact",
            "valid": True,
            "redacted": False,
            "source": "legacy_selected_artifact",
            "title": "Release notes",
            "summary": "Selected section summary",
            "artifactId": "artifact-doc-1",
            "artifactVersionId": "version-2",
            "selectedText": "## Important section",
            "type": "markdown_document",
        },
        {
            "id": "message:message-1",
            "kind": "message",
            "valid": True,
            "redacted": False,
            "source": "legacy_quoted_message",
            "title": "user",
            "summary": "Please keep this requirement.",
            "messageId": "message-1",
        },
    ]


def test_redacts_secret_like_context_values() -> None:
    items = normalize_context_items(
        {
            "contextItems": [
                {
                    "id": "deployment:1",
                    "kind": "deployment",
                    "title": "Vercel deploy",
                    "summary": "api_key=sk-secret should not leak",
                    "metadata": {
                        "provider": "vercel",
                        "token": "sk-secret",
                        "logs": ["healthy", "secret=abc"],
                    },
                }
            ]
        }
    )

    item = items[0]
    serialized = str(item)
    assert item["redacted"] is True
    assert item["summary"] == "[redacted]"
    assert item["metadata"] == {"provider": "vercel", "logs": ["healthy", "[redacted]"]}
    assert "sk-secret" not in serialized
    assert "abc" not in serialized


def test_truncates_selected_text_and_note_content() -> None:
    items = normalize_context_items(
        {
            "contextItems": [
                {
                    "kind": "selected_text",
                    "selectedText": "a" * (MAX_SELECTED_TEXT_CHARS + 10),
                },
                {
                    "kind": "note",
                    "content": "b" * (MAX_NOTE_CHARS + 10),
                },
            ]
        }
    )

    assert len(items[0]["selectedText"]) == MAX_SELECTED_TEXT_CHARS
    assert items[0]["selectedText"].endswith("...")
    assert len(items[1]["note"]) == MAX_NOTE_CHARS
    assert items[1]["note"].endswith("...")
    assert items[0]["redacted"] is True
    assert items[1]["redacted"] is True


def test_limits_context_items() -> None:
    items = normalize_context_items(
        {
            "contextItems": [
                {"kind": "note", "content": f"note {index}"}
                for index in range(MAX_CONTEXT_ITEMS + 3)
            ]
        }
    )

    assert len(items) == MAX_CONTEXT_ITEMS
    assert items[-1]["note"] == f"note {MAX_CONTEXT_ITEMS - 1}"


def test_marks_unsupported_context_item_kind_invalid() -> None:
    items = normalize_context_items(
        {
            "contextItems": [
                {
                    "id": "unsafe-upload-1",
                    "kind": "file_upload",
                    "summary": "Do not load this raw file.",
                }
            ]
        }
    )

    assert items == [
        {
            "id": "unsafe-upload-1",
            "kind": "file_upload",
            "valid": False,
            "reason": "Unsupported context item kind `file_upload`.",
            "redacted": False,
            "source": "explicit",
        }
    ]
