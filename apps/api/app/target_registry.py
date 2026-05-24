from dataclasses import dataclass
from typing import Literal, Optional

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
    preview_command: Optional[str] = None
    base_url: Optional[str] = None
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


def get_target(target_id: str) -> TargetProject:
    try:
        return TARGET_REGISTRY[target_id]
    except KeyError as exc:
        raise TargetRegistryError(f"Unknown target project: {target_id}") from exc


def maybe_get_target(target_id: str) -> Optional[TargetProject]:
    return TARGET_REGISTRY.get(target_id)


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
