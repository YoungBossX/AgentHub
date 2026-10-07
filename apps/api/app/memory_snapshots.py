from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from sqlalchemy import update
from sqlmodel import Session as DbSession
from sqlmodel import select

from app.agent_runtime_config import get_effective_runtime_config
from app.memory_instructions import compile_instruction_artifacts
from app.memory_store import (
    MEMORY_SCOPES,
    MEMORY_TYPES,
    TRUST_LEVELS,
    MemoryFilter,
    list_memory_items,
    memory_collection_versions_for_items,
    memory_content_hash,
    serialize_memory_item,
)
from app.models import MemoryItem, MemorySnapshot, Task, TaskRun
from app.models import Session as AgentHubSession
from app.models import utc_now
from app.target_registry import TargetProject, list_targets_for_workspace

MEMORY_SNAPSHOT_SCHEMA_VERSION = "memory_snapshot_v2"
ACTIVE_TASK_RUN_STATES = {
    "created",
    "queued",
    "streaming",
    "waiting_approval",
    "applying_changes",
    "collecting_diff",
    "starting_preview",
}


class MemorySnapshotError(ValueError):
    pass


class _FrozenMemoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, alias_generator=to_camel)

    id: str = Field(min_length=1)
    workspace_id: str | None
    version: int = Field(ge=1)
    scope: str
    memory_type: str = Field(alias="type")
    source: str
    status: str
    trust_level: str
    title: str = Field(min_length=1)
    content_md: str = Field(min_length=1)
    content_hash: str
    importance: int = Field(ge=0, le=100)
    target_ids: list[str]
    agent_roles: list[str]
    last_used_at: str | None
    updated_at: str
    created_at: str
    item_hash: str


@dataclass(frozen=True)
class MemorySnapshotContent:
    items: tuple[MemoryItem, ...]
    as_of: datetime
    content_status: str
    items_hash: str | None


def create_memory_snapshot(
    db: DbSession,
    *,
    workspace_id: str | None,
    reason: str = "created",
    commit: bool = True,
) -> MemorySnapshot:
    targets = list_targets_for_workspace(db, workspace_id) if workspace_id else ()
    artifacts = compile_instruction_artifacts(targets=targets)
    as_of = utc_now()
    items = [
        item for item in list_memory_items(db, MemoryFilter(workspace_id=workspace_id))
        if item.status in {"active", "warm"}
    ]
    memory_versions = memory_collection_versions_for_items(items)
    frozen_items = []
    for item in sorted(items, key=lambda item: item.id):
        payload = serialize_memory_item(item)
        frozen_items.append({**payload, "itemHash": _stable_hash(payload)})
    items_hash = _stable_hash(frozen_items)
    target_registry_payload = _target_registry_payload(targets)
    runtime_config_payload = get_effective_runtime_config(db, workspace_id).to_payload()
    target_registry_version = _stable_hash(target_registry_payload)
    runtime_config_version = _stable_hash(runtime_config_payload)
    context_pack_hash = _stable_hash(
        {
            "schemaVersion": MEMORY_SNAPSHOT_SCHEMA_VERSION,
            "workspaceId": workspace_id,
            "retrievalAsOf": as_of.isoformat(),
            "snapshotItemsHash": items_hash,
            "agentsMdHash": artifacts.agents_md_hash,
            "claudeMdHash": artifacts.claude_md_hash,
            "projectMemoryVersion": memory_versions.project_memory_version,
            "userPreferenceVersion": memory_versions.user_preference_version,
            "targetRegistryVersion": target_registry_version,
            "runtimeConfigVersion": runtime_config_version,
        }
    )
    snapshot = MemorySnapshot(
        workspace_id=workspace_id,
        schema_version=MEMORY_SNAPSHOT_SCHEMA_VERSION,
        agents_md_hash=artifacts.agents_md_hash,
        claude_md_hash=artifacts.claude_md_hash,
        project_memory_version=memory_versions.project_memory_version,
        user_preference_version=memory_versions.user_preference_version,
        target_registry_version=target_registry_version,
        runtime_config_version=runtime_config_version,
        context_pack_hash=context_pack_hash,
        meta_json=json.dumps(
            {
                "reason": reason,
                "workspaceId": workspace_id,
                "retrievalAsOf": as_of.isoformat(),
                "memoryItems": frozen_items,
                "snapshotItemsHash": items_hash,
                "targetIds": [target.target_id for target in targets],
                "targetRegistryVersion": target_registry_version,
                "runtimeConfigSource": runtime_config_payload.get("configSource"),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        created_at=as_of,
    )
    read_memory_snapshot_content(snapshot)
    db.add(snapshot)
    if commit:
        db.commit()
        db.refresh(snapshot)
    else:
        db.flush()
    return snapshot


def ensure_session_memory_snapshot(
    db: DbSession,
    session: AgentHubSession,
) -> MemorySnapshot:
    if session.memory_snapshot_id:
        return get_memory_snapshot(
            db, session.memory_snapshot_id, workspace_id=session.workspace_id
        )
    snapshot = create_memory_snapshot(
        db,
        workspace_id=session.workspace_id,
        reason="session_default",
    )
    session.memory_snapshot_id = snapshot.id
    session.updated_at = utc_now()
    db.add(session)
    db.commit()
    db.refresh(session)
    return snapshot


def refresh_session_memory_snapshot(
    db: DbSession,
    session_id: str,
) -> MemorySnapshot:
    try:
        # Serialize the active-run check and pointer update with TaskRun creation.
        db.execute(
            update(AgentHubSession)
            .where(AgentHubSession.id == session_id)
            .values(updated_at=AgentHubSession.updated_at)
            .execution_options(synchronize_session=False)
        )
        session = db.get(AgentHubSession, session_id, populate_existing=True)
        if session is None:
            raise MemorySnapshotError(f"Session not found: {session_id}")
        active_run_ids = _active_task_run_ids(db, session_id)
        if active_run_ids:
            raise MemorySnapshotError(
                "Cannot refresh memory snapshot while TaskRuns are active: "
                + ", ".join(active_run_ids)
            )
        snapshot = create_memory_snapshot(
            db,
            workspace_id=session.workspace_id,
            reason="explicit_session_refresh",
            commit=False,
        )
        session.memory_snapshot_id = snapshot.id
        session.updated_at = utc_now()
        db.add(session)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(session)
    db.refresh(snapshot)
    return snapshot


def memory_snapshot_for_session(
    db: DbSession,
    session: AgentHubSession,
) -> MemorySnapshot | None:
    if not session.memory_snapshot_id:
        return None
    return get_memory_snapshot(
        db, session.memory_snapshot_id, workspace_id=session.workspace_id
    )


def get_memory_snapshot(
    db: DbSession, snapshot_id: str, *, workspace_id: str | None
) -> MemorySnapshot:
    snapshot = db.get(MemorySnapshot, snapshot_id)
    if snapshot is None:
        raise MemorySnapshotError("Bound memory snapshot is missing.")
    if snapshot.workspace_id != workspace_id:
        raise MemorySnapshotError("Memory snapshot workspace mismatch.")
    read_memory_snapshot_content(snapshot)
    return snapshot


def get_bound_memory_snapshot(
    db: DbSession, binding: Any, *, workspace_id: str | None
) -> MemorySnapshot:
    if (
        not isinstance(binding, dict)
        or not isinstance(binding.get("memorySnapshotId"), str)
        or not binding["memorySnapshotId"]
    ):
        raise MemorySnapshotError("TaskRun memory snapshot binding is missing.")
    snapshot = get_memory_snapshot(db, binding["memorySnapshotId"], workspace_id=workspace_id)
    metadata = memory_snapshot_metadata(snapshot)
    legacy_fields = {"contentStatus", "snapshotItemsHash", "retrievalAsOf"}
    for key, value in metadata.items():
        if snapshot.schema_version == "memory_snapshot_v1" and key in legacy_fields:
            continue
        if key not in binding or binding[key] != value:
            raise MemorySnapshotError("TaskRun memory snapshot binding does not match stored content.")
    return snapshot


def read_memory_snapshot_content(snapshot: MemorySnapshot) -> MemorySnapshotContent:
    if snapshot.schema_version == "memory_snapshot_v1":
        return MemorySnapshotContent((), snapshot.created_at, "legacy_unavailable", None)
    if snapshot.schema_version != MEMORY_SNAPSHOT_SCHEMA_VERSION:
        raise MemorySnapshotError("Unsupported memory snapshot content schema.")
    try:
        meta = json.loads(snapshot.meta_json)
        as_of = _snapshot_time(meta["retrievalAsOf"])
        payloads = meta["memoryItems"]
        if (
            not isinstance(payloads, list)
            or meta["workspaceId"] != snapshot.workspace_id
            or as_of != snapshot.created_at
            or meta["snapshotItemsHash"] != _stable_hash(payloads)
            or not all(
                isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest)
                for digest in (
                    snapshot.agents_md_hash, snapshot.claude_md_hash,
                    snapshot.project_memory_version, snapshot.user_preference_version,
                    snapshot.target_registry_version, snapshot.runtime_config_version,
                    snapshot.context_pack_hash,
                )
            )
        ):
            raise ValueError("Invalid content envelope")
        items = []
        for payload in payloads:
            frozen = _FrozenMemoryItem.model_validate(payload)
            if (
                frozen.workspace_id != snapshot.workspace_id
                or frozen.scope not in MEMORY_SCOPES
                or frozen.memory_type not in MEMORY_TYPES
                or frozen.status not in {"active", "warm"}
                or frozen.trust_level not in TRUST_LEVELS
                or frozen.content_hash != memory_content_hash(frozen.content_md)
                or frozen.item_hash != _stable_hash(
                    {key: value for key, value in payload.items() if key != "itemHash"}
                )
            ):
                raise ValueError("Invalid content member")
            values = frozen.model_dump(exclude={
                "item_hash", "target_ids", "agent_roles", "last_used_at", "updated_at", "created_at"
            })
            items.append(MemoryItem(
                **values,
                target_ids_json=json.dumps(frozen.target_ids),
                agent_roles_json=json.dumps(frozen.agent_roles),
                last_used_at=_snapshot_time(frozen.last_used_at) if frozen.last_used_at is not None else None,
                updated_at=_snapshot_time(frozen.updated_at),
                created_at=_snapshot_time(frozen.created_at),
            ))
        if len({item.id for item in items}) != len(items):
            raise ValueError("Duplicate content member")
        versions = memory_collection_versions_for_items(items)
        if (
            snapshot.project_memory_version != versions.project_memory_version
            or snapshot.user_preference_version != versions.user_preference_version
            or snapshot.context_pack_hash != _stable_hash({
                "schemaVersion": snapshot.schema_version,
                "workspaceId": snapshot.workspace_id,
                "retrievalAsOf": meta["retrievalAsOf"],
                "snapshotItemsHash": meta["snapshotItemsHash"],
                "agentsMdHash": snapshot.agents_md_hash,
                "claudeMdHash": snapshot.claude_md_hash,
                "projectMemoryVersion": snapshot.project_memory_version,
                "userPreferenceVersion": snapshot.user_preference_version,
                "targetRegistryVersion": snapshot.target_registry_version,
                "runtimeConfigVersion": snapshot.runtime_config_version,
            })
        ):
            raise ValueError("Invalid content metadata")
        return MemorySnapshotContent(tuple(items), as_of, "frozen", meta["snapshotItemsHash"])
    except (KeyError, TypeError, ValueError):
        # Validation details can contain the original private memory text.
        raise MemorySnapshotError("Memory snapshot content is invalid; explicit refresh is required.") from None


def _snapshot_time(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Invalid snapshot timestamp")
    timestamp = datetime.fromisoformat(value)
    if timestamp.tzinfo is not None:
        raise ValueError("Expected a naive UTC snapshot timestamp")
    return timestamp


def memory_snapshot_metadata(snapshot: MemorySnapshot | None) -> dict[str, Any]:
    if snapshot is None:
        return {}
    content = read_memory_snapshot_content(snapshot)
    return {
        "memorySnapshotId": snapshot.id,
        "schemaVersion": snapshot.schema_version,
        "contentStatus": content.content_status,
        "snapshotItemsHash": content.items_hash,
        "retrievalAsOf": content.as_of.isoformat(),
        "agentsMdHash": snapshot.agents_md_hash,
        "claudeMdHash": snapshot.claude_md_hash,
        "projectMemoryVersion": snapshot.project_memory_version,
        "userPreferenceVersion": snapshot.user_preference_version,
        "targetRegistryVersion": snapshot.target_registry_version,
        "runtimeConfigVersion": snapshot.runtime_config_version,
        "contextPackHash": snapshot.context_pack_hash,
        "createdAt": snapshot.created_at.isoformat(),
    }


def context_pack_hash_for_snapshot(snapshot: MemorySnapshot | None) -> str | None:
    return snapshot.context_pack_hash if snapshot is not None else None


def _active_task_run_ids(db: DbSession, session_id: str) -> list[str]:
    tasks = db.exec(select(Task).where(Task.session_id == session_id)).all()
    task_ids = [task.id for task in tasks]
    if not task_ids:
        return []
    runs = db.exec(
        select(TaskRun)
        .where(TaskRun.task_id.in_(task_ids))
        .where(TaskRun.state.in_(ACTIVE_TASK_RUN_STATES))
        .order_by(TaskRun.created_at, TaskRun.id)
    ).all()
    return [run.id for run in runs]


def _target_registry_payload(targets: tuple[TargetProject, ...]) -> list[dict[str, Any]]:
    return [
        {
            "targetId": target.target_id,
            "type": target.type,
            "root": target.root,
            "allowedPaths": list(target.allowed_paths),
            "deniedPaths": list(target.denied_paths),
            "allowedAgents": list(target.allowed_agents),
            "devCommand": target.dev_command,
            "testCommand": target.test_command,
            "checkCommand": target.check_command,
            "buildCommand": target.build_command,
            "previewCommand": target.preview_command,
            "baseUrl": target.base_url,
            "requiresPlatformMode": target.requires_platform_mode,
            "requiresApproval": target.requires_approval,
        }
        for target in sorted(targets, key=lambda item: item.target_id)
    ]


def _stable_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
