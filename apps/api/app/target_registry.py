from dataclasses import dataclass
from typing import Literal, Optional

from sqlmodel import Session as DbSession

from app.external_workspaces import (
    allowed_paths_for,
    denied_paths_for,
    get_external_project_target,
    list_external_project_targets,
)
from app.models import ExternalProjectTarget

TargetType = Literal["frontend", "backend", "platform"]
AgentRole = Literal["orchestrator", "frontend", "backend", "qa", "review"]

DEMO_FRONTEND_TARGET_ID = "demo-frontend"
DEMO_BACKEND_TARGET_ID = "demo-backend"
AGENTHUB_PLATFORM_TARGET_ID = "agenthub-platform"
DEMO_BACKEND_BASE_URL = "http://127.0.0.1:5174"

GLOBAL_DENIED_PATHS = (".env*", "node_modules", ".git", "secrets")


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
    base_url: Optional[str] = None
    package_manager: Optional[str] = None
    detected_framework: Optional[str] = None
    project_type: Optional[str] = None
    analysis_status: Optional[str] = None
    requires_platform_mode: bool = False
    requires_approval: bool = False
    related_target_ids: tuple[str, ...] = ()

    def allows_agent(self, role: str) -> bool:
        return role in self.allowed_agents

    def allows_path(self, path: str) -> bool:
        normalized = _normalize_path(path)
        return any(_matches_path_pattern(normalized, allowed) for allowed in self.allowed_paths)

    def denies_path(self, path: str) -> bool:
        normalized = _normalize_path(path)
        return any(_matches_path_pattern(normalized, denied) for denied in self.denied_paths)

    def permits_path(self, path: str) -> bool:
        return self.allows_path(path) and not self.denies_path(path)


TARGET_REGISTRY: dict[str, TargetProject] = {
    DEMO_FRONTEND_TARGET_ID: TargetProject(
        target_id=DEMO_FRONTEND_TARGET_ID,
        name="Demo Frontend",
        type="frontend",
        root="apps/demo",
        allowed_paths=("apps/demo/src",),
        denied_paths=("apps/api", "apps/demo-api", *GLOBAL_DENIED_PATHS),
        dev_command="pnpm demo:dev",
        preview_command="pnpm dev --host 127.0.0.1 --port <port>",
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


def external_target_to_project(target: ExternalProjectTarget) -> TargetProject:
    target_type = _target_type_for_external_project(target.project_type)
    return TargetProject(
        target_id=target.target_id,
        name=target.name,
        type=target_type,
        root=target.root_path,
        allowed_paths=tuple(allowed_paths_for(target)),
        denied_paths=tuple(denied_paths_for(target)),
        dev_command=target.dev_command,
        test_command=target.test_command,
        check_command=target.check_command,
        build_command=target.build_command,
        preview_command=target.preview_command,
        package_manager=target.package_manager,
        detected_framework=target.detected_framework,
        project_type=target.project_type,
        analysis_status=target.analysis_status,
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


def _normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.rstrip("/")


def _matches_path_pattern(path: str, pattern: str) -> bool:
    normalized_pattern = _normalize_path(pattern)
    if normalized_pattern.endswith("*"):
        return path.startswith(normalized_pattern[:-1])

    if "/" not in normalized_pattern:
        return normalized_pattern in path.split("/")

    return path == normalized_pattern or path.startswith(f"{normalized_pattern}/")


def _target_type_for_external_project(project_type: str) -> TargetType:
    if project_type in {"vite-react", "nextjs"}:
        return "frontend"
    if project_type in {"fastapi", "node-api", "python-package"}:
        return "backend"
    return "frontend"


def _allowed_agents_for_external_type(target_type: TargetType) -> tuple[AgentRole, ...]:
    if target_type == "frontend":
        return ("frontend", "qa", "review")
    if target_type == "backend":
        return ("backend", "qa", "review")
    return ("orchestrator", "backend", "frontend", "qa", "review")
