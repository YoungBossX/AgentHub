from __future__ import annotations

from typing import Iterable


def supports_target_id(
    supported_targets: Iterable[str],
    target_id: str,
    *,
    role: str | None = None,
) -> bool:
    targets = set(supported_targets)
    if target_id in targets or "*" in targets:
        return True
    if not target_id.startswith("external-"):
        return False
    if "external" in targets:
        return True
    if target_id.startswith("external-frontend"):
        return "external-frontend" in targets and role in {
            None,
            "frontend",
            "qa",
            "review",
            "orchestrator",
        }
    if target_id.startswith("external-backend"):
        return "external-backend" in targets and role in {
            None,
            "backend",
            "qa",
            "review",
            "orchestrator",
        }
    if role == "frontend" and "external-frontend" in targets:
        return True
    if role == "backend" and "external-backend" in targets:
        return True
    return False
