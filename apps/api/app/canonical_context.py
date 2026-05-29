import copy
from datetime import datetime
from typing import Any, Optional

from app.models import utc_now

CANONICAL_CONTEXT_VERSION = "canonical_shared_context_v1"
PROVIDER_VISIBLE_CONTEXT_VERSION = "provider_visible_context_v1"
PROTECTED_PATH_MARKERS = (
    ".env",
    ".git",
    "node_modules",
    ".venv",
    "secrets/",
    "/secrets",
)
PROTECTED_KEY_MARKERS = (
    "secret",
    "token",
    "password",
    "api_key",
    "apikey",
)


def build_canonical_shared_context(
    session_context_pack: dict[str, Any],
    *,
    created_at: Optional[datetime] = None,
) -> dict[str, Any]:
    timestamp = (created_at or utc_now()).isoformat()
    current_task = _dict_value(session_context_pack.get("currentTask"))
    ledger = _dict_value(session_context_pack.get("ledger"))
    task_plan = _dict_value(current_task.get("plan"))
    task_graph = task_plan.get("taskGraph") or task_plan.get("planDraft", {}).get("taskGraph")
    relevant_artifacts = {
        "selectedArtifact": session_context_pack.get("selectedArtifact"),
        "artifactReferences": session_context_pack.get("artifactReferences", []),
        "latestCommandEvidence": session_context_pack.get("latestCommandEvidence"),
    }

    fields = {
        "session": _field(
            {
                "sessionId": session_context_pack.get("sessionId"),
                "workspaceId": session_context_pack.get("workspaceId"),
            },
            source="session",
            created_at=timestamp,
            trust_level="system",
        ),
        "userGoal": _field(
            session_context_pack.get("currentGoal")
            or session_context_pack.get("originalUserRequest"),
            source="session_ledger",
            created_at=timestamp,
            trust_level="user",
        ),
        "currentTask": _field(
            {
                "id": current_task.get("id"),
                "title": current_task.get("title"),
                "intentType": current_task.get("intentType"),
                "description": current_task.get("description"),
            },
            source="task",
            created_at=timestamp,
            trust_level="system",
        ),
        "taskGraph": _field(
            task_graph,
            source="plan_draft",
            created_at=timestamp,
            trust_level="system",
        ),
        "targetContext": _field(
            {
                "targetProject": session_context_pack.get("targetProject"),
                "relatedTargetProjects": session_context_pack.get("relatedTargetProjects", []),
            },
            source="target_registry",
            created_at=timestamp,
            trust_level="system",
        ),
        "safePaths": _field(
            filter_protected_values(session_context_pack.get("safeTargetPaths", [])),
            source="target_registry",
            created_at=timestamp,
            trust_level="system",
        ),
        "recentMessages": _field(
            filter_protected_values(session_context_pack.get("recentMessages", [])),
            source="messages",
            created_at=timestamp,
            trust_level="user",
        ),
        "relevantArtifacts": _field(
            filter_protected_values(relevant_artifacts),
            source="artifacts",
            created_at=timestamp,
            trust_level="system",
        ),
        "missionTrace": _field(
            filter_protected_values(session_context_pack.get("missionTrace")),
            source="mission_trace",
            created_at=timestamp,
            trust_level="system",
        ),
        "latestDiff": _field(
            filter_protected_values(session_context_pack.get("latestDiff")),
            source="artifact.diff",
            created_at=timestamp,
            trust_level="system",
        ),
        "latestReview": _field(
            filter_protected_values(session_context_pack.get("latestReview")),
            source="artifact.review",
            created_at=timestamp,
            trust_level="system",
        ),
        "latestPreview": _field(
            filter_protected_values(session_context_pack.get("latestPreview")),
            source="artifact.preview",
            created_at=timestamp,
            trust_level="system",
        ),
        "latestDeployment": _field(
            filter_protected_values(session_context_pack.get("latestDeployment")),
            source="artifact.deployment",
            created_at=timestamp,
            trust_level="system",
        ),
        "handoffNotes": _field(
            filter_protected_values(
                session_context_pack.get("handoffNotes")
                or task_plan.get("handoffNotes")
                or []
            ),
            source="handoff",
            created_at=timestamp,
            trust_level="system",
        ),
        "guardrails": _field(
            {
                "protectedPaths": [
                    ".env",
                    ".git",
                    "node_modules",
                    ".venv",
                    "secrets/",
                ],
                "validationExpectations": session_context_pack.get(
                    "validationExpectations",
                    [],
                ),
            },
            source="guardrails",
            created_at=timestamp,
            trust_level="system",
        ),
    }
    return {
        "version": CANONICAL_CONTEXT_VERSION,
        "createdAt": timestamp,
        "fields": fields,
    }


def provider_visible_context(
    session_context_pack: dict[str, Any],
    canonical_context: dict[str, Any],
) -> dict[str, Any]:
    return {
        "version": PROVIDER_VISIBLE_CONTEXT_VERSION,
        "canonicalContext": filter_protected_values(canonical_context),
        "legacyContext": filter_protected_values(_legacy_visible_context(session_context_pack)),
    }


def filter_protected_values(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if _is_protected_key(key):
                continue
            filtered = filter_protected_values(item)
            if filtered is _Redacted:
                continue
            sanitized[key] = filtered
        return sanitized
    if isinstance(value, list):
        filtered_items = []
        for item in value:
            filtered = filter_protected_values(item)
            if filtered is not _Redacted:
                filtered_items.append(filtered)
        return filtered_items
    if isinstance(value, str) and _is_protected_string(value):
        return _Redacted
    return copy.deepcopy(value)


def _field(
    value: Any,
    *,
    source: str,
    created_at: str,
    visibility: str = "provider",
    trust_level: str,
) -> dict[str, Any]:
    return {
        "value": value,
        "source": source,
        "visibility": visibility,
        "createdAt": created_at,
        "trustLevel": trust_level,
    }


def _legacy_visible_context(session_context_pack: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in session_context_pack.items()
        if key not in {"canonicalContext", "providerVisibleContext"}
    }


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _is_protected_key(key: Any) -> bool:
    normalized = str(key).lower()
    return any(marker in normalized for marker in PROTECTED_KEY_MARKERS)


def _is_protected_string(value: str) -> bool:
    normalized = value.replace("\\", "/")
    if normalized.startswith("/"):
        return True
    return any(marker in normalized for marker in PROTECTED_PATH_MARKERS)


class _RedactedType:
    pass


_Redacted = _RedactedType()
