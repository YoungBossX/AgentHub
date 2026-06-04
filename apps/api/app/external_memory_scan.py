from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from sqlmodel import Session as DbSession

from app.memory_store import MemoryFilter, list_memory_items
from app.memory_write_policy import create_external_memory_suggestion
from app.models import MemoryItem
from app.models import Session as AgentHubSession

SCAN_FILE_LIMIT_CHARS = 12000
REPO_MEMORY_FILES = ("AGENTS.md", "CLAUDE.md")


@dataclass(frozen=True)
class ExternalMemoryScanResult:
    suggestions: tuple[MemoryItem, ...]
    conflicts: tuple[dict[str, str], ...]
    planned_sources: tuple[dict[str, str], ...]


def scan_repo_external_memory(
    db: DbSession,
    *,
    session: AgentHubSession,
    repo_root: Path,
) -> ExternalMemoryScanResult:
    suggestions: list[MemoryItem] = []
    for file_name in REPO_MEMORY_FILES:
        path = repo_root / file_name
        if not path.exists() or not path.is_file():
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        if not content.strip():
            continue
        suggestion = create_external_memory_suggestion(
            db,
            session=session,
            source="external_memory",
            title=f"{file_name} external memory suggestion",
            content=_bounded_content(content),
        )
        suggestions.append(suggestion)
    conflicts = detect_external_memory_conflicts(
        db,
        session=session,
        suggestions=suggestions,
    )
    return ExternalMemoryScanResult(
        suggestions=tuple(suggestions),
        conflicts=tuple(conflicts),
        planned_sources=tuple(planned_external_memory_sources()),
    )


def planned_external_memory_sources() -> list[dict[str, str]]:
    return [
        {
            "source": "repo_AGENTS.md",
            "status": "implemented",
            "policy": "scan_as_pending_suggestion",
        },
        {
            "source": "repo_CLAUDE.md",
            "status": "implemented",
            "policy": "scan_as_pending_suggestion",
        },
        {
            "source": "claude_code_local_auto_memory",
            "status": "planned",
            "policy": "scan_as_pending_suggestion_after_user_confirmation",
        },
        {
            "source": "codex_global_or_repo_instructions",
            "status": "planned",
            "policy": "scan_as_pending_suggestion_after_user_confirmation",
        },
    ]


def detect_external_memory_conflicts(
    db: DbSession,
    *,
    session: AgentHubSession,
    suggestions: Iterable[MemoryItem],
) -> list[dict[str, str]]:
    active_items = list_memory_items(
        db,
        MemoryFilter(
            workspace_id=session.workspace_id,
            status="active",
        ),
    )
    conflicts: list[dict[str, str]] = []
    for suggestion in suggestions:
        for active in active_items:
            reason = _conflict_reason(active.content_md, suggestion.content_md)
            if not reason:
                continue
            conflicts.append(
                {
                    "activeMemoryId": active.id,
                    "suggestionMemoryId": suggestion.id,
                    "reason": reason,
                }
            )
    return conflicts


def _bounded_content(content: str) -> str:
    stripped = content.strip()
    if len(stripped) <= SCAN_FILE_LIMIT_CHARS:
        return stripped
    return stripped[:SCAN_FILE_LIMIT_CHARS] + "\n\n[AgentHub truncated external memory scan]"


def _conflict_reason(active_content: str, suggestion_content: str) -> str | None:
    active = active_content.lower()
    suggestion = suggestion_content.lower()
    if "中文" in active and (
        "不要使用中文" in suggestion
        or "禁止中文" in suggestion
        or "english only" in suggestion
    ):
        return "external suggestion conflicts with active Chinese-language preference"
    if (
        "do not production deploy" in active
        or "禁止生产部署" in active
        or "不要生产部署" in active
    ) and (
        "production deploy allowed" in suggestion
        or "允许生产部署" in suggestion
        or "可以生产部署" in suggestion
    ):
        return "external suggestion conflicts with active production-deploy guard preference"
    return None
