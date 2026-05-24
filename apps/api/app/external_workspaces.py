import json
import re
from pathlib import Path
from typing import Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.models import ExternalProjectTarget, Workspace, new_id, utc_now


DEFAULT_EXTERNAL_DENIED_PATHS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "secrets",
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    ".next",
    "coverage",
)

SYSTEM_ROOTS: tuple[Path, ...] = tuple(
    Path(path)
    for path in (
        "/System",
        "/Library",
        "/Applications",
        "/bin",
        "/sbin",
        "/usr",
        "/etc",
        "/dev",
        "/proc",
    )
)

TARGET_ID_PATTERN = re.compile(r"^external-[a-z0-9][a-z0-9-]{1,80}$")


class ExternalWorkspaceRegistrationError(ValueError):
    pass


class ExternalWorkspaceRegistration:
    def __init__(
        self,
        *,
        name: str,
        root_path: str,
        allowed_paths: list[str],
        target_id: Optional[str] = None,
        project_type: str = "unknown",
        denied_paths: Optional[list[str]] = None,
        dev_command: Optional[str] = None,
        test_command: Optional[str] = None,
        check_command: Optional[str] = None,
        build_command: Optional[str] = None,
        preview_command: Optional[str] = None,
        staging_output_dir: Optional[str] = None,
        staging_serve_command: Optional[str] = None,
        deploy_provider_ids: Optional[list[str]] = None,
        package_manager: Optional[str] = None,
        detected_framework: Optional[str] = None,
    ) -> None:
        self.name = name
        self.root_path = root_path
        self.allowed_paths = allowed_paths
        self.target_id = target_id
        self.project_type = project_type
        self.denied_paths = denied_paths or []
        self.dev_command = dev_command
        self.test_command = test_command
        self.check_command = check_command
        self.build_command = build_command
        self.preview_command = preview_command
        self.staging_output_dir = staging_output_dir
        self.staging_serve_command = staging_serve_command
        self.deploy_provider_ids = deploy_provider_ids or []
        self.package_manager = package_manager
        self.detected_framework = detected_framework


def register_external_project_target(
    db: DbSession,
    workspace: Workspace,
    registration: ExternalWorkspaceRegistration,
) -> ExternalProjectTarget:
    root_path = _validate_root_path(registration.root_path)
    allowed_paths = _validate_allowed_paths(registration.allowed_paths)
    denied_paths = _merged_denied_paths(registration.denied_paths)
    target_id = _target_id_for(registration)

    existing = db.exec(
        select(ExternalProjectTarget).where(
            ExternalProjectTarget.target_id == target_id,
        )
    ).first()
    if existing is not None:
        raise ExternalWorkspaceRegistrationError(
            f"External target already exists: {target_id}"
        )

    now = utc_now()
    target = ExternalProjectTarget(
        workspace_id=workspace.id,
        target_id=target_id,
        name=_validate_name(registration.name),
        root_path=str(root_path),
        project_type=registration.project_type or "unknown",
        allowed_paths_json=json.dumps(allowed_paths),
        denied_paths_json=json.dumps(denied_paths),
        dev_command=registration.dev_command,
        test_command=registration.test_command,
        check_command=registration.check_command,
        build_command=registration.build_command,
        preview_command=registration.preview_command,
        staging_output_dir=registration.staging_output_dir,
        staging_serve_command=registration.staging_serve_command,
        deploy_provider_ids_json=json.dumps(
            _validate_deploy_provider_ids(registration.deploy_provider_ids),
            separators=(",", ":"),
        ),
        package_manager=registration.package_manager,
        detected_framework=registration.detected_framework,
        analysis_status="manual",
        created_at=now,
        updated_at=now,
    )
    db.add(target)
    db.commit()
    db.refresh(target)
    return target


def list_external_project_targets(
    db: DbSession,
    workspace_id: str,
) -> list[ExternalProjectTarget]:
    return db.exec(
        select(ExternalProjectTarget)
        .where(ExternalProjectTarget.workspace_id == workspace_id)
        .order_by(ExternalProjectTarget.created_at, ExternalProjectTarget.target_id)
    ).all()


def get_external_project_target(
    db: DbSession,
    workspace_id: str,
    target_id: str,
) -> Optional[ExternalProjectTarget]:
    return db.exec(
        select(ExternalProjectTarget)
        .where(ExternalProjectTarget.workspace_id == workspace_id)
        .where(ExternalProjectTarget.target_id == target_id)
    ).first()


def allowed_paths_for(target: ExternalProjectTarget) -> list[str]:
    return _json_string_list(target.allowed_paths_json)


def denied_paths_for(target: ExternalProjectTarget) -> list[str]:
    return _json_string_list(target.denied_paths_json)


def deploy_provider_ids_for(target: ExternalProjectTarget) -> list[str]:
    return _json_string_list(target.deploy_provider_ids_json)


def _validate_name(name: str) -> str:
    clean = name.strip()
    if not clean:
        raise ExternalWorkspaceRegistrationError("External target name is required")
    return clean


def _validate_root_path(root_path: str) -> Path:
    if not root_path.strip():
        raise ExternalWorkspaceRegistrationError("External root path is required")

    path = Path(root_path).expanduser().resolve(strict=False)
    if not path.exists() or not path.is_dir():
        raise ExternalWorkspaceRegistrationError(
            f"External root must be an existing directory: {path}"
        )

    home = Path.home().resolve(strict=False)
    if path == path.parent:
        raise ExternalWorkspaceRegistrationError("Filesystem root cannot be registered")
    if path == home:
        raise ExternalWorkspaceRegistrationError("Home directory cannot be registered")
    if path.parent == home and path.name in {"Desktop", "Documents", "Downloads"}:
        raise ExternalWorkspaceRegistrationError(
            f"Broad home directory parent cannot be registered: {path}"
        )
    for system_root in SYSTEM_ROOTS:
        if path == system_root or system_root in path.parents:
            raise ExternalWorkspaceRegistrationError(
                f"System directory cannot be registered: {path}"
            )
    return path


def _validate_allowed_paths(allowed_paths: list[str]) -> list[str]:
    if not allowed_paths:
        raise ExternalWorkspaceRegistrationError(
            "External targets require explicit allowed paths"
        )

    clean_paths = [_normalize_relative_path(path) for path in allowed_paths]
    if any(path in {".", ""} for path in clean_paths):
        raise ExternalWorkspaceRegistrationError(
            "External target allowed paths cannot grant the whole project root"
        )
    return _dedupe(clean_paths)


def _merged_denied_paths(denied_paths: list[str]) -> list[str]:
    clean_denied = [_normalize_relative_path(path) for path in denied_paths]
    return _dedupe([*DEFAULT_EXTERNAL_DENIED_PATHS, *clean_denied])


def _validate_deploy_provider_ids(provider_ids: list[str]) -> list[str]:
    clean: list[str] = []
    for provider_id in provider_ids:
        value = provider_id.strip()
        if not value:
            continue
        if not re.match(r"^[a-z][a-z0-9_]{1,40}$", value):
            raise ExternalWorkspaceRegistrationError(
                f"Deploy provider ID is invalid: {provider_id}"
            )
        clean.append(value)
    return _dedupe(clean)


def _normalize_relative_path(path: str) -> str:
    clean = path.replace("\\", "/").strip().strip("/")
    if not clean:
        return "."
    parts = clean.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ExternalWorkspaceRegistrationError(
            f"External target paths must be relative project paths: {path}"
        )
    if Path(path).is_absolute():
        raise ExternalWorkspaceRegistrationError(
            f"External target paths must not be absolute: {path}"
        )
    return clean


def _target_id_for(registration: ExternalWorkspaceRegistration) -> str:
    if registration.target_id is not None:
        target_id = registration.target_id.strip()
        if not TARGET_ID_PATTERN.match(target_id):
            raise ExternalWorkspaceRegistrationError(
                "External target ID must start with external- and use lowercase "
                "letters, numbers, or dashes"
            )
        return target_id

    slug = re.sub(r"[^a-z0-9]+", "-", registration.name.lower()).strip("-")
    if not slug:
        slug = "workspace"
    return f"external-{slug[:40]}-{new_id()[:8]}"


def _json_string_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str)]


def _dedupe(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique
