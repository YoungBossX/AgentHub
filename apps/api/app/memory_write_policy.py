from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from sqlmodel import Session as DbSession

from app.memory_store import (
    MemoryItemInput,
    MemoryStoreError,
    create_memory_item,
)
from app.models import MemoryItem
from app.models import Session as AgentHubSession

USER_MEMORY_PATTERNS = (
    (
        re.compile(r"^\s*(?:记住这个|請記住這個|请记住这个)[:：]?\s*(?P<content>.+)$", re.I | re.S),
        "user_preference",
        "user",
        "User preference",
    ),
    (
        re.compile(r"^\s*(?:以后都这样|以後都這樣)[:：]?\s*(?P<content>.+)$", re.I | re.S),
        "user_preference",
        "user",
        "User preference",
    ),
    (
        re.compile(r"^\s*(?:写入项目规则|寫入專案規則|写进项目规则)[:：]?\s*(?P<content>.+)$", re.I | re.S),
        "project_rule",
        "project",
        "Project rule",
    ),
    (
        re.compile(r"^\s*(?:写进|寫進)\s*user-preferences\.md[:：]?\s*(?P<content>.+)$", re.I | re.S),
        "user_preference",
        "user",
        "User preference",
    ),
)
UNTRUSTED_MEMORY_SOURCES = {
    "file_content",
    "tool_output",
    "provider_output",
    "retrieved_content",
    "claude_suggestion",
    "codex_suggestion",
    "external_memory",
}
SYSTEM_DISCOVERY_SOURCES = {
    "build_failure",
    "review_finding",
    "deploy_failure",
    "repeated_fix",
}


@dataclass(frozen=True)
class MemoryWriteResult:
    memory_item: MemoryItem
    reply: str


def create_explicit_user_memory(
    db: DbSession,
    *,
    session: AgentHubSession,
    content: str,
    memory_type: str,
    scope: str,
    title: str,
) -> MemoryItem:
    return create_memory_item(
        db,
        MemoryItemInput(
            workspace_id=session.workspace_id,
            scope=scope,
            memory_type=memory_type,
            source="user_explicit",
            title=title,
            content_md=content,
            status="active",
            trust_level="user_confirmed",
            importance=80,
        ),
    )


def maybe_create_explicit_user_memory(
    db: DbSession,
    *,
    session: AgentHubSession,
    content: str,
) -> Optional[MemoryWriteResult]:
    parsed = parse_explicit_user_memory_request(content)
    if parsed is None:
        return None
    memory_type, scope, title, memory_content = parsed
    item = create_explicit_user_memory(
        db,
        session=session,
        content=memory_content,
        memory_type=memory_type,
        scope=scope,
        title=title,
    )
    return MemoryWriteResult(
        memory_item=item,
        reply=(
            "已写入 AgentHub canonical memory，并会在新的 memory snapshot 中生效。"
            f"\n\n- memoryId: {item.id}"
            f"\n- type: {item.memory_type}"
            f"\n- scope: {item.scope}"
        ),
    )


def parse_explicit_user_memory_request(
    content: str,
) -> Optional[tuple[str, str, str, str]]:
    for pattern, memory_type, scope, title in USER_MEMORY_PATTERNS:
        match = pattern.match(content)
        if not match:
            continue
        memory_content = match.group("content").strip()
        if not memory_content:
            return None
        return memory_type, scope, title, memory_content
    return None


def create_system_discovery_memory_candidate(
    db: DbSession,
    *,
    session: AgentHubSession,
    source: str,
    title: str,
    content: str,
    memory_type: str = "pattern",
) -> MemoryItem:
    if source not in SYSTEM_DISCOVERY_SOURCES:
        raise MemoryStoreError(f"Unsupported system discovery source: {source}")
    return create_memory_item(
        db,
        MemoryItemInput(
            workspace_id=session.workspace_id,
            scope="project",
            memory_type=memory_type,
            source=source,
            title=title,
            content_md=content,
            status="pending_review",
            trust_level="system",
            importance=60,
        ),
    )


def create_external_memory_suggestion(
    db: DbSession,
    *,
    session: AgentHubSession,
    source: str,
    title: str,
    content: str,
    requested_status: str = "pending_review",
) -> MemoryItem:
    if source not in UNTRUSTED_MEMORY_SOURCES:
        raise MemoryStoreError(f"Unsupported untrusted memory source: {source}")
    if requested_status == "active":
        raise MemoryStoreError(
            "Untrusted memory sources cannot create active memory without user review."
        )
    status = requested_status if requested_status in {"pending_review", "rejected"} else "pending_review"
    return create_memory_item(
        db,
        MemoryItemInput(
            workspace_id=session.workspace_id,
            scope="project",
            memory_type="external_suggestion",
            source=source,
            title=title,
            content_md=content,
            status=status,
            trust_level="external",
            importance=30,
        ),
    )
