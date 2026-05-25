import json
from typing import Any


def context_section(context_pack: dict[str, Any]) -> str:
    provider_context = context_pack.get("providerVisibleContext")
    if not isinstance(provider_context, dict):
        provider_context = context_pack
    return (
        "Session Context Pack:\n"
        "```json\n"
        f"{json.dumps(provider_context, ensure_ascii=True, sort_keys=True, indent=2)}\n"
        "```"
    )
