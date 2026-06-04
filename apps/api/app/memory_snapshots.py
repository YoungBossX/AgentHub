from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.agent_runtime_config import get_effective_runtime_config
from app.memory_instructions import compile_instruction_artifacts
from app.models import MemorySnapshot, Task, TaskRun
from app.models import Session as AgentHubSession
from app.models import utc_now
from app.target_registry import TargetProject, list_targets_for_workspace

MEMORY_SNAPSHOT_SCHEMA_VERSION = "memory_snapshot_v1"
PROJECT_MEMORY_VERSION = "project-memory-v1"
USER_PREFERENCE_VERSION = "user-preferences-v1"
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


def create_memory_snapshot(
    db: DbSession,
    *,
    workspace_id: str | None,
    reason: str = "created",
) -> MemorySnapshot:
    targets = list_targets_for_workspace(db, workspace_id) if workspace_id else ()
    artifacts = compile_instruction_artifacts(targets=targets)
    target_registry_payload = _target_registry_payload(targets)
    runtime_config_payload = get_effective_runtime_config(db, workspace_id).to_payload()
    target_registry_version = _stable_hash(target_registry_payload)
    runtime_config_version = _stable_hash(runtime_config_payload)
    context_pack_hash = _stable_hash(
        {
            "schemaVersion": MEMORY_SNAPSHOT_SCHEMA_VERSION,
            "agentsMdHash": artifacts.agents_md_hash,
            "claudeMdHash": artifacts.claude_md_hash,
            "projectMemoryVersion": PROJECT_MEMORY_VERSION,
            "userPreferenceVersion": USER_PREFERENCE_VERSION,
            "targetRegistryVersion": target_registry_version,
            "runtimeConfigVersion": runtime_config_version,
        }
    )
    snapshot = MemorySnapshot(
        workspace_id=workspace_id,
        schema_version=MEMORY_SNAPSHOT_SCHEMA_VERSION,
        agents_md_hash=artifacts.agents_md_hash,
        claude_md_hash=artifacts.claude_md_hash,
        project_memory_version=PROJECT_MEMORY_VERSION,
        user_preference_version=USER_PREFERENCE_VERSION,
        target_registry_version=target_registry_version,
        runtime_config_version=runtime_config_version,
        context_pack_hash=context_pack_hash,
        meta_json=json.dumps(
            {
                "reason": reason,
                "targetIds": [target.target_id for target in targets],
                "targetRegistryVersion": target_registry_version,
                "runtimeConfigSource": runtime_config_payload.get("configSource"),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        created_at=utc_now(),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def ensure_session_memory_snapshot(
    db: DbSession,
    session: AgentHubSession,
) -> MemorySnapshot:
    if session.memory_snapshot_id:
        existing = db.get(MemorySnapshot, session.memory_snapshot_id)
        if existing is not None:
            return existing
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
    session = db.get(AgentHubSession, session_id)
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
    )
    session.memory_snapshot_id = snapshot.id
    session.updated_at = utc_now()
    db.add(session)
    db.commit()
    db.refresh(session)
    return snapshot


def memory_snapshot_for_session(
    db: DbSession,
    session: AgentHubSession,
) -> MemorySnapshot | None:
    if not session.memory_snapshot_id:
        return None
    return db.get(MemorySnapshot, session.memory_snapshot_id)


def memory_snapshot_metadata(snapshot: MemorySnapshot | None) -> dict[str, Any]:
    if snapshot is None:
        return {}
    return {
        "memorySnapshotId": snapshot.id,
        "schemaVersion": snapshot.schema_version,
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
