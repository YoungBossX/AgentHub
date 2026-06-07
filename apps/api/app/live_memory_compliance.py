from __future__ import annotations

import posixpath
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sqlmodel import Session as DbSession

from app.external_workspaces import (
    ExternalWorkspaceRegistration,
    get_external_project_target,
    register_external_project_target,
)
from app.memory_evals import snapshot_consistency_rate
from app.memory_snapshots import ensure_session_memory_snapshot, memory_snapshot_metadata
from app.memory_store import (
    MemoryFilter,
    MemoryItemInput,
    create_memory_item,
    list_memory_items,
)
from app.models import ExternalProjectTarget, MemoryItem, Workspace
from app.models import Session as AgentHubSession

P18C_LIBRARY_APP_USER_PROMPT = (
    "帮我在桌面开发一个简单的图书管理系统。有登录页面，初始账户和密码是 "
    "18088888888 / 888888。登录后进入管理页面，只需要有图书管理功能："
    "加入图书、删除图书、修改图书、查询图书。"
)
P18C_EXPECTED_PROJECT_ROOT_PREFIX = "~/Desktop/agenthub-rehearsals/"
P18C_REQUIRED_FRONTEND_STACK = ("vite", "react", "typescript")
P18C_REQUIRED_PERSISTENCE = "localStorage"
P18C_MEMORY_SOURCE = "p18c_live_memory_compliance"
P18C_TARGET_ID = "external-p18c-library-app"
P18C_PROJECT_DIRNAME = "p18c-library-app"

ViolationCode = Literal[
    "project_location_memory_violation",
    "frontend_stack_memory_violation",
    "persistence_memory_violation",
    "memory_compliance_violation",
    "target_boundary_violation",
    "provider_evidence_violation",
    "snapshot_consistency_violation",
]


@dataclass(frozen=True)
class P18cMemoryRule:
    key: str
    title: str
    content_md: str
    scope: str = "project"
    memory_type: str = "project_rule"
    trust_level: str = "user_confirmed"
    agent_roles: tuple[str, ...] = ("orchestrator", "frontend", "review")
    importance: int = 90


@dataclass(frozen=True)
class ProviderEvidence:
    provider_id: str | None
    adapter_type: str | None
    task_run_id: str | None
    diff_artifact_id: str | None
    build_or_validation_evidence_id: str | None

    def is_complete(self) -> bool:
        return all(
            (
                self.provider_id,
                self.adapter_type,
                self.task_run_id,
                self.diff_artifact_id,
                self.build_or_validation_evidence_id,
            )
        )

    def to_payload(self) -> dict[str, str | bool | None]:
        return {
            "providerId": self.provider_id,
            "adapterType": self.adapter_type,
            "taskRunId": self.task_run_id,
            "diffArtifactId": self.diff_artifact_id,
            "buildOrValidationEvidenceId": self.build_or_validation_evidence_id,
            "complete": self.is_complete(),
        }


@dataclass(frozen=True)
class LiveMemoryComplianceEvidence:
    memory_snapshot_id: str
    active_memory_rule_ids: tuple[str, ...]
    changed_files: tuple[str, ...]
    project_root: str
    frontend_stack: tuple[str, ...]
    persistence: str
    provider_evidence: ProviderEvidence
    snapshot_ids_by_source: dict[str, str | None]
    user_requested_backend_or_database: bool = False
    platform_maintenance_mode: bool = False
    expected_project_root_prefix: str = P18C_EXPECTED_PROJECT_ROOT_PREFIX


@dataclass(frozen=True)
class LiveMemoryComplianceReport:
    memory_snapshot_id: str
    active_memory_rule_ids: tuple[str, ...]
    changed_files: tuple[str, ...]
    expected_target_path: str
    docs_change_log_updated: bool
    forbidden_platform_paths_touched: bool
    unexpected_backend_or_database_created: bool
    provider_evidence_exists: bool
    snapshot_consistency_rate: float
    violations: tuple[ViolationCode, ...]

    @property
    def passed(self) -> bool:
        return not self.violations

    def to_payload(self) -> dict[str, object]:
        return {
            "memorySnapshotId": self.memory_snapshot_id,
            "activeMemoryRuleIds": list(self.active_memory_rule_ids),
            "changedFiles": list(self.changed_files),
            "expectedTargetPath": self.expected_target_path,
            "docsChangeLogUpdated": self.docs_change_log_updated,
            "forbiddenPlatformPathsTouched": self.forbidden_platform_paths_touched,
            "unexpectedBackendOrDatabaseCreated": (
                self.unexpected_backend_or_database_created
            ),
            "providerEvidenceExists": self.provider_evidence_exists,
            "snapshotConsistencyRate": self.snapshot_consistency_rate,
            "violations": list(self.violations),
            "summary": "passed" if self.passed else "failed",
        }


@dataclass(frozen=True)
class P18cSessionSetupEvidence:
    rehearsal_root: str
    project_root: str
    target_id: str
    external_target_db_id: str
    session_id: str
    memory_snapshot_id: str
    active_memory_rule_ids: tuple[str, ...]
    allowed_paths: tuple[str, ...]
    agents_md_hash: str
    claude_md_hash: str
    target_registry_version: str
    runtime_config_version: str
    context_pack_hash: str

    def to_payload(self) -> dict[str, object]:
        return {
            "rehearsalRoot": self.rehearsal_root,
            "projectRoot": self.project_root,
            "targetId": self.target_id,
            "externalTargetDbId": self.external_target_db_id,
            "sessionId": self.session_id,
            "memorySnapshotId": self.memory_snapshot_id,
            "activeMemoryRuleIds": list(self.active_memory_rule_ids),
            "allowedPaths": list(self.allowed_paths),
            "agentsMdHash": self.agents_md_hash,
            "claudeMdHash": self.claude_md_hash,
            "targetRegistryVersion": self.target_registry_version,
            "runtimeConfigVersion": self.runtime_config_version,
            "contextPackHash": self.context_pack_hash,
        }


P18C_MEMORY_RULES: tuple[P18cMemoryRule, ...] = (
    P18cMemoryRule(
        key="p18c-project-location",
        title="P18c desktop rehearsal project location",
        content_md=(
            "New demo frontend projects should be created under "
            "~/Desktop/agenthub-rehearsals/ unless the user says otherwise."
        ),
    ),
    P18cMemoryRule(
        key="p18c-frontend-stack",
        title="P18c frontend stack default",
        content_md=(
            "New frontend demo projects should use Vite + React + TypeScript "
            "by default."
        ),
    ),
    P18cMemoryRule(
        key="p18c-localstorage-persistence",
        title="P18c simple demo persistence default",
        content_md=(
            "Simple demo apps should use localStorage persistence by default, "
            "not backend/database, unless explicitly requested."
        ),
    ),
    P18cMemoryRule(
        key="p18c-change-log-required",
        title="P18c change-log evidence required",
        content_md="Code changes must update docs/change-log.md when applicable.",
    ),
    P18cMemoryRule(
        key="p18c-platform-boundary",
        title="P18c platform boundary",
        content_md=(
            "Do not modify AgentHub platform code unless platform maintenance "
            "mode is explicit."
        ),
    ),
    P18cMemoryRule(
        key="p18c-provider-evidence-required",
        title="P18c provider success evidence required",
        content_md=(
            "Real provider success must not be claimed without TaskRun / diff / "
            "build evidence."
        ),
    ),
)


def ensure_p18c_memory_rules(
    db: DbSession,
    *,
    workspace_id: str,
) -> tuple[MemoryItem, ...]:
    existing = list_memory_items(
        db,
        MemoryFilter(workspace_id=workspace_id, status="active"),
    )
    existing_by_hash = {
        (item.title, item.content_md): item
        for item in existing
        if item.source == P18C_MEMORY_SOURCE
    }
    items: list[MemoryItem] = []
    for rule in P18C_MEMORY_RULES:
        existing_item = existing_by_hash.get((rule.title, rule.content_md))
        if existing_item is not None:
            items.append(existing_item)
            continue
        items.append(
            create_memory_item(
                db,
                MemoryItemInput(
                    workspace_id=workspace_id,
                    scope=rule.scope,
                    memory_type=rule.memory_type,
                    source=P18C_MEMORY_SOURCE,
                    title=rule.title,
                    content_md=rule.content_md,
                    status="active",
                    trust_level=rule.trust_level,
                    agent_roles=rule.agent_roles,
                    importance=rule.importance,
                ),
            )
        )
    return tuple(items)


def prepare_p18c_session_setup(
    db: DbSession,
    *,
    workspace: Workspace,
    rehearsal_root: Path | None = None,
    session_title: str = "P18c Library Management Live Memory Smoke",
) -> P18cSessionSetupEvidence:
    root = (rehearsal_root or Path.home() / "Desktop" / "agenthub-rehearsals").expanduser()
    root.mkdir(parents=True, exist_ok=True)
    project_root = root / P18C_PROJECT_DIRNAME
    (project_root / "src").mkdir(parents=True, exist_ok=True)

    active_memory = ensure_p18c_memory_rules(db, workspace_id=workspace.id)
    target = _ensure_p18c_external_target(db, workspace, project_root)
    session = AgentHubSession(
        workspace_id=workspace.id,
        title=session_title,
        session_type="p18c_live_memory_compliance",
        bound_branch=workspace.default_branch,
        worktree_path=f".worktrees/p18c-{session_title.lower().replace(' ', '-')}",
        active_frontend_target_id=target.target_id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    snapshot = ensure_session_memory_snapshot(db, session)
    metadata = memory_snapshot_metadata(snapshot)
    return P18cSessionSetupEvidence(
        rehearsal_root=str(root.resolve(strict=False)),
        project_root=str(project_root.resolve(strict=False)),
        target_id=target.target_id,
        external_target_db_id=target.id,
        session_id=session.id,
        memory_snapshot_id=snapshot.id,
        active_memory_rule_ids=tuple(rule.key for rule in P18C_MEMORY_RULES),
        allowed_paths=("src",),
        agents_md_hash=str(metadata["agentsMdHash"]),
        claude_md_hash=str(metadata["claudeMdHash"]),
        target_registry_version=str(metadata["targetRegistryVersion"]),
        runtime_config_version=str(metadata["runtimeConfigVersion"]),
        context_pack_hash=str(metadata["contextPackHash"]),
    )


def check_live_memory_compliance(
    evidence: LiveMemoryComplianceEvidence,
) -> LiveMemoryComplianceReport:
    docs_change_log_updated = _has_change_log_update(evidence.changed_files)
    forbidden_platform_paths_touched = _touches_forbidden_platform_path(
        evidence.changed_files,
        platform_maintenance_mode=evidence.platform_maintenance_mode,
    )
    unexpected_backend_or_database_created = (
        not evidence.user_requested_backend_or_database
        and (
            evidence.persistence != P18C_REQUIRED_PERSISTENCE
            or _creates_backend_or_database(evidence.changed_files)
        )
    )
    provider_evidence_exists = evidence.provider_evidence.is_complete()
    current_snapshot_consistency_rate = snapshot_consistency_rate(
        evidence.snapshot_ids_by_source.values()
    )
    violations: list[ViolationCode] = []

    if not _is_under_expected_root(
        evidence.project_root,
        evidence.expected_project_root_prefix,
    ):
        violations.append("project_location_memory_violation")
    if not _has_required_frontend_stack(evidence.frontend_stack):
        violations.append("frontend_stack_memory_violation")
    if unexpected_backend_or_database_created:
        violations.append("persistence_memory_violation")
    if _has_frontend_code_changes(evidence.changed_files) and not docs_change_log_updated:
        violations.append("memory_compliance_violation")
    if forbidden_platform_paths_touched:
        violations.append("target_boundary_violation")
    if not provider_evidence_exists:
        violations.append("provider_evidence_violation")
    if (
        current_snapshot_consistency_rate < 1.0
        or evidence.memory_snapshot_id
        not in set(evidence.snapshot_ids_by_source.values())
    ):
        violations.append("snapshot_consistency_violation")

    return LiveMemoryComplianceReport(
        memory_snapshot_id=evidence.memory_snapshot_id,
        active_memory_rule_ids=evidence.active_memory_rule_ids,
        changed_files=evidence.changed_files,
        expected_target_path=evidence.expected_project_root_prefix,
        docs_change_log_updated=docs_change_log_updated,
        forbidden_platform_paths_touched=forbidden_platform_paths_touched,
        unexpected_backend_or_database_created=unexpected_backend_or_database_created,
        provider_evidence_exists=provider_evidence_exists,
        snapshot_consistency_rate=current_snapshot_consistency_rate,
        violations=tuple(dict.fromkeys(violations)),
    )


def _ensure_p18c_external_target(
    db: DbSession,
    workspace: Workspace,
    project_root: Path,
) -> ExternalProjectTarget:
    existing = get_external_project_target(db, workspace.id, P18C_TARGET_ID)
    if existing is not None:
        return existing
    return register_external_project_target(
        db,
        workspace,
        ExternalWorkspaceRegistration(
            target_id=P18C_TARGET_ID,
            name="P18c Library Management App",
            root_path=str(project_root),
            project_type="vite-react",
            allowed_paths=["src"],
            dev_command="pnpm dev --host 127.0.0.1 --port <port>",
            test_command="pnpm test",
            check_command="pnpm check",
            build_command="pnpm build",
            preview_command="pnpm dev --host 127.0.0.1 --port <port>",
            staging_output_dir="dist",
            staging_serve_command=(
                "python -m http.server <port> --bind 127.0.0.1 --directory dist"
            ),
            deploy_provider_ids=["local_staging"],
            package_manager="pnpm",
            detected_framework="vite-react",
        ),
    )


def _has_change_log_update(changed_files: tuple[str, ...]) -> bool:
    return any(_normalize_path(path) == "docs/change-log.md" for path in changed_files)


def _touches_forbidden_platform_path(
    changed_files: tuple[str, ...],
    *,
    platform_maintenance_mode: bool,
) -> bool:
    if platform_maintenance_mode:
        return False
    return any(
        normalized.startswith(prefix)
        for normalized in (_normalize_path(path) for path in changed_files)
        for prefix in (
            "apps/api/",
            "apps/web/",
            "scripts/",
            "packages/",
            "pnpm-workspace.yaml",
            "package.json",
        )
    )


def _creates_backend_or_database(changed_files: tuple[str, ...]) -> bool:
    backend_markers = (
        "/server/",
        "/backend/",
        "/api/",
        "/database/",
        "/db/",
        "/prisma/",
    )
    backend_suffixes = (
        "schema.prisma",
        ".sqlite",
        ".sqlite3",
        ".db",
    )
    normalized_files = [_normalize_path(path) for path in changed_files]
    return any(
        any(marker in path for marker in backend_markers)
        or path.endswith(backend_suffixes)
        for path in normalized_files
    )


def _has_frontend_code_changes(changed_files: tuple[str, ...]) -> bool:
    frontend_suffixes = (
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".css",
        ".html",
        ".json",
    )
    return any(
        path.endswith(frontend_suffixes)
        and _normalize_path(path) != "docs/change-log.md"
        for path in changed_files
    )


def _is_under_expected_root(project_root: str, expected_prefix: str) -> bool:
    normalized_root = _normalize_path(project_root)
    normalized_prefix = _normalize_path(expected_prefix).rstrip("/") + "/"
    return normalized_root == normalized_prefix.rstrip("/") or normalized_root.startswith(
        normalized_prefix
    )


def _has_required_frontend_stack(frontend_stack: tuple[str, ...]) -> bool:
    normalized = {item.lower() for item in frontend_stack}
    return set(P18C_REQUIRED_FRONTEND_STACK).issubset(normalized)


def _normalize_path(path: str) -> str:
    return posixpath.normpath(path.replace("\\", "/"))
