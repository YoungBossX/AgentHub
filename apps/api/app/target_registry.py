import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Literal, Optional

from sqlmodel import Session as DbSession

from app.external_workspaces import (
    allowed_paths_for,
    denied_paths_for,
    deploy_provider_ids_for,
    get_external_project_target,
    list_external_project_targets,
)
from app.models import ExternalProjectTarget
from app.project_profiles import ProjectProfile, build_project_profile

TargetType = Literal["frontend", "backend", "platform"]
AgentRole = Literal["orchestrator", "frontend", "backend", "qa", "review"]

DEMO_FRONTEND_TARGET_ID = "demo-frontend"
DEMO_BACKEND_TARGET_ID = "demo-backend"
AGENTHUB_PLATFORM_TARGET_ID = "agenthub-platform"
DEMO_BACKEND_BASE_URL = "http://127.0.0.1:5174"

GLOBAL_DENIED_PATHS = (".env*", "node_modules", ".git", "secrets")
EFFECTIVE_WRITE_SCOPE_SCHEMA_VERSION = "agenthub.effective_write_scope.v1"


class TargetRegistryError(KeyError):
    pass


@dataclass(frozen=True)
class TargetProject:
    target_id: str
    name: str
    type: TargetType
    root: str
    allowed_paths: tuple[str, ...]
    denied_paths: tuple[str, ...]
    allowed_agents: tuple[AgentRole, ...]
    dev_command: Optional[str] = None
    test_command: Optional[str] = None
    check_command: Optional[str] = None
    build_command: Optional[str] = None
    preview_command: Optional[str] = None
    staging_output_dir: Optional[str] = None
    staging_serve_command: Optional[str] = None
    deploy_provider_ids: tuple[str, ...] = ()
    base_url: Optional[str] = None
    package_manager: Optional[str] = None
    detected_framework: Optional[str] = None
    project_type: Optional[str] = None
    analysis_status: Optional[str] = None
    project_profile: Optional[ProjectProfile] = None
    requires_platform_mode: bool = False
    requires_approval: bool = False
    related_target_ids: tuple[str, ...] = ()

    def allows_agent(self, role: str) -> bool:
        return role in self.allowed_agents

    def allows_path(self, path: str) -> bool:
        if not is_canonical_repository_path(path):
            return False
        try:
            allowed_patterns = tuple(
                canonical_write_scope_pattern(allowed) for allowed in self.allowed_paths
            )
        except (TargetRegistryError, TypeError):
            return False
        return any(
            _matches_path_pattern(path, allowed)
            for allowed in allowed_patterns
        )

    def denies_path(self, path: str) -> bool:
        if not is_canonical_repository_path(path):
            return True
        if protected_repository_path_category(path) is not None:
            return True
        try:
            denied_patterns = tuple(
                canonical_write_scope_pattern(denied)
                for denied in (*self.denied_paths, *GLOBAL_DENIED_PATHS)
            )
        except (TargetRegistryError, TypeError):
            return True
        return any(
            _matches_path_pattern(path, denied)
            for denied in denied_patterns
        )

    def permits_path(self, path: str) -> bool:
        return self.allows_path(path) and not self.denies_path(path)


@dataclass(frozen=True)
class DeployTargetConfig:
    target_id: str
    provider_ids: tuple[str, ...]
    build_command: str
    output_dir: str
    serve_command: Optional[str]


TARGET_REGISTRY: dict[str, TargetProject] = {
    DEMO_FRONTEND_TARGET_ID: TargetProject(
        target_id=DEMO_FRONTEND_TARGET_ID,
        name="Demo Frontend",
        type="frontend",
        root="apps/demo",
        allowed_paths=("apps/demo/src",),
        denied_paths=("apps/api", "apps/demo-api", *GLOBAL_DENIED_PATHS),
        dev_command="pnpm demo:dev",
        build_command="pnpm build",
        preview_command="pnpm dev --host 127.0.0.1 --port <port>",
        staging_output_dir="dist",
        staging_serve_command="python -m http.server <port> --bind 127.0.0.1 --directory dist",
        deploy_provider_ids=("mock", "local_staging"),
        allowed_agents=("frontend", "qa", "review"),
        related_target_ids=(DEMO_BACKEND_TARGET_ID,),
    ),
    DEMO_BACKEND_TARGET_ID: TargetProject(
        target_id=DEMO_BACKEND_TARGET_ID,
        name="Demo Backend",
        type="backend",
        root="apps/demo-api",
        allowed_paths=("apps/demo-api",),
        denied_paths=("apps/api", "apps/demo", *GLOBAL_DENIED_PATHS),
        dev_command="pnpm demo:api:dev",
        test_command="pnpm demo:api:test",
        base_url=DEMO_BACKEND_BASE_URL,
        allowed_agents=("backend", "qa", "review"),
    ),
    AGENTHUB_PLATFORM_TARGET_ID: TargetProject(
        target_id=AGENTHUB_PLATFORM_TARGET_ID,
        name="AgentHub Platform",
        type="platform",
        root=".",
        allowed_paths=(
            "apps/api",
            "apps/web",
            "scripts",
            "docs",
            "openspec",
            "package.json",
            "pnpm-lock.yaml",
            "pnpm-workspace.yaml",
        ),
        denied_paths=GLOBAL_DENIED_PATHS,
        test_command="pnpm check && pnpm test",
        allowed_agents=("orchestrator", "backend", "frontend", "qa", "review"),
        requires_platform_mode=True,
        requires_approval=True,
    ),
}


def list_targets() -> tuple[TargetProject, ...]:
    return tuple(TARGET_REGISTRY.values())


def list_targets_for_workspace(
    db: DbSession,
    workspace_id: str,
) -> tuple[TargetProject, ...]:
    external_targets = tuple(
        external_target_to_project(target)
        for target in list_external_project_targets(db, workspace_id)
    )
    return (*list_targets(), *external_targets)


def get_target(target_id: str) -> TargetProject:
    try:
        return TARGET_REGISTRY[target_id]
    except KeyError as exc:
        raise TargetRegistryError(f"Unknown target project: {target_id}") from exc


def maybe_get_target(target_id: str) -> Optional[TargetProject]:
    return TARGET_REGISTRY.get(target_id)


def get_target_for_workspace(
    db: DbSession,
    workspace_id: str,
    target_id: str,
) -> TargetProject:
    builtin = maybe_get_target(target_id)
    if builtin is not None:
        return builtin

    external = get_external_project_target(db, workspace_id, target_id)
    if external is not None:
        return external_target_to_project(external)

    raise TargetRegistryError(f"Unknown target project: {target_id}")


def maybe_get_target_for_workspace(
    db: DbSession,
    workspace_id: str,
    target_id: str,
) -> Optional[TargetProject]:
    try:
        return get_target_for_workspace(db, workspace_id, target_id)
    except TargetRegistryError:
        return None


def effective_write_scope_identity(target: TargetProject) -> str:
    """Return a stable identity for the target's effective path policy."""
    target_id = target.target_id
    if not isinstance(target_id, str) or not target_id.strip():
        raise TargetRegistryError("Target write-scope policy is invalid")
    try:
        allowed_paths = tuple(
            canonical_write_scope_pattern(pattern) for pattern in target.allowed_paths
        )
        denied_paths = tuple(
            canonical_write_scope_pattern(pattern)
            for pattern in (*target.denied_paths, *GLOBAL_DENIED_PATHS)
        )
    except TypeError as exc:
        raise TargetRegistryError("Target write-scope policy is invalid") from exc

    payload = {
        "schemaVersion": EFFECTIVE_WRITE_SCOPE_SCHEMA_VERSION,
        "targetId": target_id,
        "allowedPaths": sorted(set(allowed_paths)),
        "deniedPaths": sorted(set(denied_paths)),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def external_target_to_project(target: ExternalProjectTarget) -> TargetProject:
    target_type = _target_type_for_external_project(target.project_type)
    allowed_paths = tuple(allowed_paths_for(target))
    denied_paths = tuple(denied_paths_for(target))
    return TargetProject(
        target_id=target.target_id,
        name=target.name,
        type=target_type,
        root=target.root_path,
        allowed_paths=allowed_paths,
        denied_paths=denied_paths,
        dev_command=target.dev_command,
        test_command=target.test_command,
        check_command=target.check_command,
        build_command=target.build_command,
        preview_command=target.preview_command,
        staging_output_dir=target.staging_output_dir,
        staging_serve_command=target.staging_serve_command,
        deploy_provider_ids=tuple(deploy_provider_ids_for(target)),
        package_manager=target.package_manager,
        detected_framework=target.detected_framework,
        project_type=target.project_type,
        analysis_status=target.analysis_status,
        project_profile=build_project_profile(
            project_type=target.project_type,
            detected_framework=target.detected_framework or target.project_type or "unknown",
            package_manager=target.package_manager or "unknown",
            allowed_paths=allowed_paths,
            denied_paths=denied_paths,
            dev_command=target.dev_command,
            test_command=target.test_command,
            check_command=target.check_command,
            build_command=target.build_command,
            preview_command=target.preview_command,
            analysis_status=target.analysis_status,
            analysis_warnings=(),
            confidence="high" if target.analysis_status in {"manual", "ready"} else "low",
        ),
        allowed_agents=_allowed_agents_for_external_type(target_type),
        requires_platform_mode=False,
        requires_approval=False,
    )


def get_related_targets(target_id: str) -> tuple[TargetProject, ...]:
    target = get_target(target_id)
    return tuple(get_target(related_id) for related_id in target.related_target_ids)


def get_related_backend_target(frontend_target_id: str) -> TargetProject:
    frontend_target = get_target(frontend_target_id)
    for related_target in get_related_targets(frontend_target.target_id):
        if related_target.type == "backend":
            return related_target
    raise TargetRegistryError(f"No related backend target for: {frontend_target_id}")


def resolve_deploy_config(target: TargetProject) -> DeployTargetConfig:
    if (
        target.type != "frontend"
        or not target.build_command
        or not target.staging_output_dir
        or not target.deploy_provider_ids
    ):
        raise TargetRegistryError(
            f"Target {target.target_id} does not have staging deploy config"
        )
    return DeployTargetConfig(
        target_id=target.target_id,
        provider_ids=target.deploy_provider_ids,
        build_command=target.build_command,
        output_dir=target.staging_output_dir,
        serve_command=target.staging_serve_command,
    )


def _normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.rstrip("/")


def is_canonical_repository_path(path: object) -> bool:
    if (
        not isinstance(path, str)
        or not path
        or path != path.strip()
        or "\\" in path
        or path.startswith("/")
        or "*" in path
        or "?" in path
        or any(ord(character) < 32 or ord(character) == 127 for character in path)
    ):
        return False
    components = path.split("/")
    return all(
        component not in {"", ".", ".."} and ":" not in component
        for component in components
    )


def protected_repository_path_category(
    path: object,
    *,
    case_sensitive: bool | None = None,
) -> str | None:
    """Classify a repository path for the rootless policy API.

    This helper has no filesystem root and therefore cannot observe a mounted
    volume's case rule.  ``case_sensitive`` is available to callers that have
    an assigned-root observation, while the default keeps the existing
    platform policy fallback (sensitive on POSIX, insensitive on Windows).
    Snapshot collection supplies its own root-bound resolver and does not rely
    on this fallback for protected aliases.
    """
    if not isinstance(path, str):
        return None
    if case_sensitive is None:
        case_sensitive = os.name != "nt"
    for component in path.split("/"):
        normalized = component if case_sensitive else component.casefold()
        if normalized == (".git" if case_sensitive else ".git"):
            return ".git"
        if normalized == ("node_modules" if case_sensitive else "node_modules"):
            return "node_modules"
        if normalized == ("secrets" if case_sensitive else "secrets"):
            return "secrets"
        if normalized.startswith(".env"):
            return ".env"
    return None


def canonical_write_scope_pattern(pattern: object) -> str:
    if not isinstance(pattern, str) or any(
        ord(character) < 32 or ord(character) == 127 for character in pattern
    ):
        raise TargetRegistryError("Target write-scope policy is invalid")
    normalized = pattern.replace("\\", "/").strip()
    if (
        not normalized
        or normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized)
    ):
        raise TargetRegistryError("Target write-scope policy is invalid")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.rstrip("/")
    if (
        not normalized
        or "?" in normalized
        or (
            "*" in normalized
            and (normalized.count("*") != 1 or not normalized.endswith("*"))
        )
    ):
        raise TargetRegistryError("Target write-scope policy is invalid")
    if normalized == "*":
        return normalized

    path_part = normalized[:-1] if normalized.endswith("*") else normalized
    path_part = path_part.rstrip("/")
    components = path_part.split("/")
    if not path_part or any(
        component in {"", ".", ".."} or ":" in component
        for component in components
    ):
        raise TargetRegistryError("Target write-scope policy is invalid")
    return normalized


def _matches_path_pattern(path: str, pattern: str) -> bool:
    normalized_pattern = _normalize_path(pattern)
    if normalized_pattern.endswith("*"):
        prefix = normalized_pattern[:-1]
        if "/" not in normalized_pattern:
            return any(segment.startswith(prefix) for segment in path.split("/"))
        return path.startswith(prefix)

    if "/" not in normalized_pattern:
        return normalized_pattern in path.split("/")

    return path == normalized_pattern or path.startswith(f"{normalized_pattern}/")


def _target_type_for_external_project(project_type: str) -> TargetType:
    if project_type in {"vite-react", "nextjs", "external-frontend"}:
        return "frontend"
    if project_type in {"fastapi", "node-api", "python-package", "external-backend"}:
        return "backend"
    return "frontend"


def _allowed_agents_for_external_type(target_type: TargetType) -> tuple[AgentRole, ...]:
    if target_type == "frontend":
        return ("frontend", "qa", "review")
    if target_type == "backend":
        return ("backend", "qa", "review")
    return ("orchestrator", "backend", "frontend", "qa", "review")
