import json
from typing import Any


def context_section(context_pack: dict[str, Any]) -> str:
    provider_context = context_pack.get("providerVisibleContext")
    canonical_context = (
        provider_context.get("canonicalContext")
        if isinstance(provider_context, dict)
        else context_pack.get("canonicalContext")
    )
    if not isinstance(canonical_context, dict):
        canonical_context = {}
    return (
        "Canonical Shared Context:\n"
        "```json\n"
        f"{json.dumps(canonical_context, ensure_ascii=True, sort_keys=True, indent=2)}\n"
        "```"
    )
