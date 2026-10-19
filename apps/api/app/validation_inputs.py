"""Shared bounded source capture, independent of host execution dependencies."""

import hashlib
from pathlib import Path
import stat

from app.native_reviews import _no_link, _read_file
from app.target_registry import protected_repository_path_category
from app.validation_policy import (
    BACKEND_PROFILE, FRONTEND_PROFILE, PROFILES, SourceSnapshot,
    ValidationUnavailable, digest, platform_root,
)

MAX_FILES = 512
MAX_BYTES = 16 * 1024 * 1024
CONFIG_FILES = ("package.json", "vite.config.ts", "tsconfig.json", "tsconfig.app.json")


def capture_profile_inputs(root: Path, profile: str) -> SourceSnapshot:
    if profile not in PROFILES:
        raise ValidationUnavailable("Unsupported automatic validation profile.")
    root = root.absolute()
    for parent in (root, *root.parents):
        _no_link(parent)
    if root.resolve() != root:
        raise ValidationUnavailable("Validation source must be a canonical worktree.")
    frontend = profile == FRONTEND_PROFILE
    project = root / ("apps/demo" if frontend else "apps/demo-api")
    pending, files, contents = [project], {}, {}
    seen, size = 0, 0
    while pending:
        path = pending.pop()
        seen += 1
        if seen > 1024:
            raise ValidationUnavailable("Validation source exceeds entry budget.")
        relative = path.relative_to(root).as_posix()
        if frontend and path.parent == project and path.name in {"node_modules", "dist"}:
            continue
        if protected_repository_path_category(relative) is not None:
            raise ValidationUnavailable("Protected input is not supported by automatic validation.")
        info = _no_link(path)
        if stat.S_ISDIR(info.st_mode):
            if not frontend and path.name in {"__pycache__", ".pytest_cache"}:
                continue
            pending.extend(path.iterdir())
            if seen + len(pending) > 1024:
                raise ValidationUnavailable("Validation source exceeds entry budget.")
            continue
        if not stat.S_ISREG(info.st_mode):
            raise ValidationUnavailable("Validation requires regular source files.")
        receipt = _read_file(root, path, include_bytes=True)
        files[relative], contents[relative] = receipt["sha256"], receipt["content"]
        size += len(receipt["content"])
        if len(files) > MAX_FILES or size > MAX_BYTES:
            raise ValidationUnavailable("Validation source exceeds byte/file budget.")
    platform = platform_root()
    if frontend:
        for name in CONFIG_FILES:
            expected = (platform / "apps/demo" / name).read_bytes()
            actual = contents.get(f"apps/demo/{name}")
            if actual is None or actual.replace(b"\r\n", b"\n") != expected.replace(b"\r\n", b"\n"):
                raise ValidationUnavailable("Build configuration differs from the trusted demo profile.")
        for name in ("pnpm-lock.yaml", "package.json", "pnpm-workspace.yaml"):
            files[name] = _read_file(root, root / name)["sha256"]
        policy_names = ("pnpm-lock.yaml", "package.json", "pnpm-workspace.yaml",
                        "scripts/demo-validation-build.mjs", "scripts/demo-build-smoke.test.mjs")
    else:
        if "apps/demo-api/app/main.py" not in files:
            raise ValidationUnavailable("Backend application entry is missing.")
        if any(Path(path).suffix.lower() in {".pyd", ".so", ".dll", ".pyc", ".pth"} for path in files):
            raise ValidationUnavailable("Executable dependency inputs are unsupported by the backend profile.")
        policy_names = ("scripts/demo-backend-check.py",)
    policy_names += ("apps/api/app/validation_inputs.py", "apps/api/app/validation_policy.py",
                     "apps/api/app/validation_process.py",
                     "apps/api/app/requirement_validation.py", "apps/api/app/validation_browser.py", "scripts/demo-requirement-check.mjs")
    policy = {name: hashlib.sha256((platform / name).read_bytes()).hexdigest() for name in policy_names}
    return SourceSnapshot(PROFILES[profile], profile, files, contents, digest(files), policy)
