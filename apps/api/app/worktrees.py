import re
import subprocess
from pathlib import Path
from typing import Optional

from app.models import Workspace
from app.process_environment import project_process_env


class WorktreeError(RuntimeError):
    pass


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def safe_path_segment(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-") or "session"


class WorktreeService:
    def __init__(
        self,
        repo_root: Optional[Path] = None,
        worktrees_root: Optional[Path] = None,
    ) -> None:
        self.repo_root = (repo_root or globals()["repo_root"]()).resolve()
        self.worktrees_root = (worktrees_root or self.repo_root / ".worktrees").resolve()

    def session_path(self, workspace_id: str, session_id: str) -> Path:
        return (
            self.worktrees_root
            / safe_path_segment(workspace_id)
            / safe_path_segment(session_id)
        )

    def create_session_worktree(self, workspace: Workspace, session_id: str) -> Path:
        path = self.session_path(workspace.id, session_id)
        if path.exists():
            if self._is_git_worktree(path):
                self._link_setup_dependency_dirs(path)
                return path.resolve()
            raise WorktreeError(f"Session worktree path already exists: {path}")

        path.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [
                "git",
                "-C",
                str(self.repo_root),
                "worktree",
                "add",
                "--detach",
                str(path),
                "HEAD",
            ],
            env=project_process_env(),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise WorktreeError(result.stderr.strip() or result.stdout.strip())
        self._link_setup_dependency_dirs(path)
        return path.resolve()

    def _link_setup_dependency_dirs(self, path: Path) -> None:
        self._ensure_setup_dependency_ignores(path)
        for relative_path in ("node_modules", "apps/demo/node_modules"):
            source = self.repo_root / relative_path
            target = path / relative_path
            if not source.exists() or target.exists() or target.is_symlink():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                target.symlink_to(source, target_is_directory=True)
            except OSError as exc:
                raise WorktreeError(
                    f"Could not link setup dependency directory {relative_path}: {exc}"
                ) from exc

    def _git_common_dir(self, path: Path) -> Path:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            env=project_process_env(),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise WorktreeError("Could not verify setup dependency repository ownership.")
        common = Path(result.stdout.strip()).absolute()
        if common.resolve() != common:
            raise WorktreeError("Setup dependency repository metadata must not traverse links.")
        return common

    def _ensure_setup_dependency_ignores(self, path: Path) -> None:
        common = self._git_common_dir(self.repo_root)
        if self._git_common_dir(path) != common:
            raise WorktreeError("Session worktree belongs to a different repository.")
        # Git uses the common repository's exclude file for linked worktrees.
        # These fixed rules also support HEADs with directory-only ignores.
        info = common / "info"
        excludes = info / "exclude"
        if info.resolve() != info or excludes.resolve() != excludes:
            raise WorktreeError("Setup dependency repository metadata must not traverse links.")
        try:
            info.mkdir(exist_ok=True)
            if excludes.exists() and (not excludes.is_file() or excludes.stat().st_nlink != 1):
                raise WorktreeError("Setup dependency repository metadata must be a single regular file.")
            original = excludes.read_bytes() if excludes.exists() else b""
            existing = set(original.splitlines())
            missing = [
                rule for rule in (b"/node_modules", b"/apps/demo/node_modules")
                if rule not in existing
            ]
            if missing:
                with excludes.open("ab") as stream:
                    stream.write(b"\n# AgentHub setup dependency links\n" + b"\n".join(missing) + b"\n")
        except OSError as exc:
            raise WorktreeError("Could not establish setup dependency ignore rules.") from exc

    def _is_git_worktree(self, path: Path) -> bool:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
            env=project_process_env(),
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
