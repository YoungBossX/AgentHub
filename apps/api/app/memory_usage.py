import hashlib
import json
from typing import Any

from app.memory_retrieval import serialized_memory_chars


def memory_usage_receipt(canonical_context: dict[str, Any]) -> dict[str, Any] | None:
    """Describe the prepared, filtered request, without asserting provider execution."""
    fields = canonical_context.get("fields", {})
    snapshot = fields.get("memorySnapshot", {}).get("value")
    if not isinstance(snapshot, dict) or not snapshot.get("memorySnapshotId"):
        return None
    visible_memories = fields.get("relevantMemories", {}).get("value", [])
    items = []
    for memory in visible_memories:
        content = memory.get("contentMd")
        items.append({
            "id": memory.get("id"),
            "version": memory.get("version"),
            "contentHash": memory.get("contentHash"),
            "rank": memory.get("rank"),
            "score": memory.get("score"),
            "matchedTerms": memory.get("matchedTerms", []),
            "layer": memory.get("layer"),
            "selectionReason": memory.get("selectionReason"),
            "visibleFields": sorted(memory),
            "contentVisible": isinstance(content, str),
            "visibleContentHash": hashlib.sha256(content.encode("utf-8")).hexdigest()
            if isinstance(content, str) else None,
        })
    return {
        "schemaVersion": "memory_usage_v1",
        "evidenceType": "prepared_provider_request",
        "memorySnapshotId": snapshot["memorySnapshotId"],
        "snapshotContentStatus": snapshot.get("contentStatus"),
        "snapshotItemsHash": snapshot.get("snapshotItemsHash"),
        "visibleMemoriesHash": hashlib.sha256(json.dumps(
            visible_memories, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest(),
        "items": items,
        "selection": fields.get("memorySelection", {}).get("value"),
        "visibleChars": serialized_memory_chars(visible_memories),
    }



def planner_memory_evidence(planner_input: dict[str, Any]) -> dict[str, Any]:
    canonical_context = planner_input.get("canonicalSharedContext")
    if not isinstance(canonical_context, dict):
        return {}
    fields = canonical_context.get("fields", {})
    snapshot = fields.get("memorySnapshot", {}).get("value")
    receipt = memory_usage_receipt(canonical_context)
    if not isinstance(snapshot, dict) or receipt is None:
        return {}
    return {"memorySnapshot": snapshot, "memoryUsage": receipt}
