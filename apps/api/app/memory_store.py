from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.models import MemoryItem, utc_now

MEMORY_STATUSES = {
    "active",
    "pending_review",
    "warm",
    "archived",
    "rejected",
    "deleted",
}
MEMORY_TYPES = {
    "project_rule",
    "user_preference",
    "decision",
    "pattern",
    "feedback",
    "session_summary",
    "external_suggestion",
}
MEMORY_SCOPES = {"project", "workspace", "user", "session", "target"}
TRUST_LEVELS = {"user_confirmed", "system", "external", "untrusted"}


class MemoryStoreError(ValueError):
    pass


@dataclass(frozen=True)
class MemoryItemInput:
    workspace_id: Optional[str]
    scope: str
    memory_type: str
    source: str
    title: str
    content_md: str
    status: str = "pending_review"
    trust_level: str = "untrusted"
    target_ids: tuple[str, ...] = ()
    agent_roles: tuple[str, ...] = ()
    importance: int = 50


@dataclass(frozen=True)
class MemoryFilter:
    workspace_id: Optional[str] = None
    scope: Optional[str] = None
    memory_type: Optional[str] = None
    status: Optional[str] = None
    target_id: Optional[str] = None
    agent_role: Optional[str] = None


@dataclass(frozen=True)
class MemoryCollectionVersions:
    project_memory_version: str
    user_preference_version: str


def create_memory_item(db: DbSession, memory_input: MemoryItemInput) -> MemoryItem:
    _validate_memory_input(memory_input)
    now = utc_now()
    item = MemoryItem(
        workspace_id=memory_input.workspace_id,
        scope=memory_input.scope,
        memory_type=memory_input.memory_type,
        source=memory_input.source,
        status=memory_input.status,
        trust_level=memory_input.trust_level,
        title=memory_input.title.strip(),
        content_md=memory_input.content_md.strip(),
        content_hash=memory_content_hash(memory_input.content_md),
        version=1,
        importance=_bounded_importance(memory_input.importance),
        target_ids_json=_json_list(memory_input.target_ids),
        agent_roles_json=_json_list(memory_input.agent_roles),
        created_at=now,
        updated_at=now,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def transition_memory_item(
    db: DbSession,
    memory_item_id: str,
    status: str,
) -> MemoryItem:
    if status not in MEMORY_STATUSES:
        raise MemoryStoreError(f"Unsupported memory status: {status}")
    item = _memory_item_or_raise(db, memory_item_id)
    item.status = status
    item.updated_at = utc_now()
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def supersede_memory_item(
    db: DbSession,
    old_item_id: str,
    new_item_input: MemoryItemInput,
) -> tuple[MemoryItem, MemoryItem]:
    old_item = _memory_item_or_raise(db, old_item_id)
    new_item = create_memory_item(db, new_item_input)
    old_item.status = "archived"
    old_item.superseded_by = new_item.id
    old_item.updated_at = utc_now()
    db.add(old_item)
    db.commit()
    db.refresh(old_item)
    db.refresh(new_item)
    return old_item, new_item


def mark_memory_used(db: DbSession, memory_item_id: str) -> MemoryItem:
    item = _memory_item_or_raise(db, memory_item_id)
    item.last_used_at = utc_now()
    item.updated_at = item.last_used_at
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_memory_items(
    db: DbSession,
    filters: MemoryFilter | None = None,
) -> list[MemoryItem]:
    filters = filters or MemoryFilter()
    statement = select(MemoryItem).order_by(MemoryItem.updated_at.desc(), MemoryItem.id)
    if filters.workspace_id is not None:
        statement = statement.where(MemoryItem.workspace_id == filters.workspace_id)
    if filters.scope is not None:
        statement = statement.where(MemoryItem.scope == filters.scope)
    if filters.memory_type is not None:
        statement = statement.where(MemoryItem.memory_type == filters.memory_type)
    if filters.status is not None:
        statement = statement.where(MemoryItem.status == filters.status)
    items = db.exec(statement).all()
    if filters.target_id is not None:
        items = [
            item
            for item in items
            if filters.target_id in memory_target_ids(item)
        ]
    if filters.agent_role is not None:
        items = [
            item
            for item in items
            if filters.agent_role in memory_agent_roles(item)
        ]
    return items


def memory_collection_versions(
    db: DbSession,
    workspace_id: str | None,
) -> MemoryCollectionVersions:
    active_items = list_memory_items(
        db,
        MemoryFilter(workspace_id=workspace_id, status="active"),
    )
    project_items = [
        item
        for item in active_items
        if item.memory_type
        in {"project_rule", "decision", "pattern", "session_summary"}
    ]
    preference_items = [
        item
        for item in active_items
        if item.memory_type in {"user_preference", "feedback"}
    ]
    return MemoryCollectionVersions(
        project_memory_version=_collection_version(project_items),
        user_preference_version=_collection_version(preference_items),
    )


def memory_target_ids(item: MemoryItem) -> list[str]:
    return _json_string_list(item.target_ids_json)


def memory_agent_roles(item: MemoryItem) -> list[str]:
    return _json_string_list(item.agent_roles_json)


def memory_content_hash(content: str) -> str:
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


def _validate_memory_input(memory_input: MemoryItemInput) -> None:
    if memory_input.scope not in MEMORY_SCOPES:
        raise MemoryStoreError(f"Unsupported memory scope: {memory_input.scope}")
    if memory_input.memory_type not in MEMORY_TYPES:
        raise MemoryStoreError(f"Unsupported memory type: {memory_input.memory_type}")
    if memory_input.status not in MEMORY_STATUSES:
        raise MemoryStoreError(f"Unsupported memory status: {memory_input.status}")
    if memory_input.trust_level not in TRUST_LEVELS:
        raise MemoryStoreError(f"Unsupported memory trust level: {memory_input.trust_level}")
    if not memory_input.title.strip():
        raise MemoryStoreError("Memory title is required.")
    if not memory_input.content_md.strip():
        raise MemoryStoreError("Memory content is required.")


def _memory_item_or_raise(db: DbSession, memory_item_id: str) -> MemoryItem:
    item = db.get(MemoryItem, memory_item_id)
    if item is None:
        raise MemoryStoreError(f"Memory item not found: {memory_item_id}")
    return item


def _collection_version(items: Iterable[MemoryItem]) -> str:
    payload = [
        {
            "id": item.id,
            "contentHash": item.content_hash,
            "status": item.status,
            "type": item.memory_type,
            "version": item.version,
        }
        for item in sorted(items, key=lambda item: item.id)
    ]
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _json_list(values: Iterable[str]) -> str:
    return json.dumps(list(values), separators=(",", ":"))


def _json_string_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str)]


def _bounded_importance(value: int) -> int:
    return min(100, max(0, int(value)))
