from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.external_workspaces import DEFAULT_EXTERNAL_DENIED_PATHS, SYSTEM_ROOTS


class LocalFolderBrowseError(ValueError):
    pass


@dataclass(frozen=True)
class LocalFolderEntry:
    name: str
    path: str


@dataclass(frozen=True)
class LocalFolderStart:
    label: str
    path: str


@dataclass(frozen=True)
class LocalFolderListing:
    current_path: str
    parent_path: Optional[str]
    starts: tuple[LocalFolderStart, ...]
    children: tuple[LocalFolderEntry, ...]


def list_local_folders(
    *,
    workspace_root: str,
    requested_path: Optional[str] = None,
) -> LocalFolderListing:
    starts = _folder_starts(workspace_root)
    current = _resolve_requested_path(requested_path, starts)
    children = tuple(_iter_child_folders(current))
    parent = _parent_path(current)

    return LocalFolderListing(
        current_path=str(current),
        parent_path=parent,
        starts=starts,
        children=children,
    )


def _folder_starts(workspace_root: str) -> tuple[LocalFolderStart, ...]:
    home = Path.home().expanduser().resolve(strict=False)
    workspace = Path(workspace_root).expanduser().resolve(strict=False)
    candidates = [
        ("桌面", home / "Desktop"),
        ("文档", home / "Documents"),
        ("工作区附近", _nearest_existing_parent(workspace)),
    ]

    starts: list[LocalFolderStart] = []
    seen: set[str] = set()
    for label, path in candidates:
        if not path.exists() or not path.is_dir():
            continue
        resolved = path.resolve(strict=False)
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        starts.append(LocalFolderStart(label=label, path=key))
    return tuple(starts)


def _resolve_requested_path(
    requested_path: Optional[str],
    starts: tuple[LocalFolderStart, ...],
) -> Path:
    if requested_path and requested_path.strip():
        path = Path(requested_path).expanduser().resolve(strict=False)
    elif starts:
        path = Path(starts[0].path).expanduser().resolve(strict=False)
    else:
        path = Path.home().expanduser().resolve(strict=False)

    if not path.exists() or not path.is_dir():
        raise LocalFolderBrowseError(f"Folder does not exist: {path}")
    if _is_system_path(path):
        raise LocalFolderBrowseError(f"System directory cannot be browsed: {path}")
    return path


def _nearest_existing_parent(path: Path) -> Path:
    current = path if path.exists() else path.parent
    while current != current.parent and not current.exists():
        current = current.parent
    return current


def _iter_child_folders(path: Path) -> list[LocalFolderEntry]:
    children: list[LocalFolderEntry] = []
    try:
        entries = list(path.iterdir())
    except OSError as exc:
        raise LocalFolderBrowseError(f"Folder cannot be read: {path}") from exc

    for entry in entries:
        if _is_hidden_or_denied(entry):
            continue
        try:
            if not entry.is_dir():
                continue
            resolved = entry.resolve(strict=False)
        except OSError:
            continue
        if _is_system_path(resolved):
            continue
        children.append(LocalFolderEntry(name=entry.name, path=str(resolved)))
    return sorted(children, key=lambda child: child.name.lower())


def _is_hidden_or_denied(path: Path) -> bool:
    name = path.name
    if name.startswith("."):
        return True
    return name in DEFAULT_EXTERNAL_DENIED_PATHS


def _is_system_path(path: Path) -> bool:
    return any(path == root or root in path.parents for root in SYSTEM_ROOTS)


def _parent_path(path: Path) -> Optional[str]:
    parent = path.parent.resolve(strict=False)
    if parent == path or _is_system_path(parent):
        return None
    return str(parent)
