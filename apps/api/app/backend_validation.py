"""Fixed installed-Python validation of the built-in FastAPI target only."""

import hashlib
import importlib.metadata
import json
from pathlib import Path
import stat
import sys
import tempfile

from app.automatic_validation import (
    BACKEND_PROFILE, SCHEMA, MAX_BYTES, MAX_FILES, ValidationUnavailable,
    digest, run_command, validation_environment,
)
from app.native_reviews import _no_link, _read_file
from app.target_registry import protected_repository_path_category
from app.worktrees import repo_root

RESULT_SCHEMA = "agenthub.backend_contract.v2"
CHECKS = {
    "check": ("python.syntax",),
    "test": ("api.health", "api.contacts_list", "api.create", "api.validation",
             "api.duplicate", "api.cors", "api.openapi", "api.field_boundaries",
             "api.invalid_types", "api.unique_identity", "api.seed_duplicate", "api.method_contract"),
}


def capture_backend_source(root):
    root = root.absolute()
    for parent in (root, *root.parents):
        _no_link(parent)
    if root.resolve() != root:
        raise ValidationUnavailable("Validation source must be a canonical worktree.")
    pending = [root / "apps/demo-api"]
    files, contents = {}, {}
    seen, size = 0, 0
    while pending:
        path = pending.pop()
        seen += 1
        if seen > 1024:
            raise ValidationUnavailable("Backend validation exceeds entry budget.")
        relative = path.relative_to(root).as_posix()
        if protected_repository_path_category(relative) is not None:
            raise ValidationUnavailable("Protected input is not supported by backend validation.")
        info = _no_link(path)
        if stat.S_ISDIR(info.st_mode):
            if path.name in {"__pycache__", ".pytest_cache"}:
                continue
            pending.extend(path.iterdir())
            if seen + len(pending) > 1024:
                raise ValidationUnavailable("Backend validation exceeds entry budget.")
            continue
        if not stat.S_ISREG(info.st_mode):
            raise ValidationUnavailable("Backend validation requires regular files.")
        receipt = _read_file(root, path, include_bytes=True)
        files[relative], contents[relative] = receipt["sha256"], receipt["content"]
        size += len(receipt["content"])
        if len(files) > MAX_FILES or size > MAX_BYTES:
            raise ValidationUnavailable("Backend validation exceeds byte/file budget.")
    if "apps/demo-api/app/main.py" not in files:
        raise ValidationUnavailable("Backend application entry is missing.")
    # Native modules must come from the trusted installed runtime, never the target.
    if any(Path(path).suffix.lower() in {".pyd", ".so", ".dll", ".pyc", ".pth"} for path in files):
        raise ValidationUnavailable("Executable dependency inputs are unsupported by the backend profile.")
    try:
        versions = {name: importlib.metadata.version(name)
                    for name in ("fastapi", "pydantic", "starlette", "httpx", "anyio")}
    except importlib.metadata.PackageNotFoundError as exc:
        raise ValidationUnavailable("Installed FastAPI validation dependencies are unavailable.") from exc
    platform = repo_root()
    policy = {
        "profile": BACKEND_PROFILE, "checks": CHECKS, "python": sys.version,
        "executable": hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
        "dependencies": versions,
        "requirements": hashlib.sha256((platform / "apps/api/requirements.txt").read_bytes()).hexdigest(),
        "harness": hashlib.sha256((platform / "scripts/demo-backend-check.py").read_bytes()).hexdigest(),
        "runner": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "sharedRunner": hashlib.sha256((platform / "apps/api/app/automatic_validation.py").read_bytes()).hexdigest(),
        "environment": digest(validation_environment()),
    }
    return {"files": files, "sourceFingerprint": digest(files), "policyFingerprint": digest(policy)}, contents


def parse_result(result, stage):
    """An exit code alone, missing assertions or target SystemExit(0) cannot pass."""
    try:
        lines = [line.removeprefix("AGENTHUB_BACKEND_RESULT=") for line in result["log"].splitlines()
                 if line.startswith("AGENTHUB_BACKEND_RESULT=")]
        if len(lines) != 1:
            return False
        value = json.loads(lines[0])
        checks = value["checks"]
        return (result["status"] == "passed" and result["exitCode"] == 0
                and value["schemaVersion"] == RESULT_SCHEMA and value["stage"] == stage
                and value.get("error") is None
                and [c["id"] for c in checks] == list(CHECKS[stage])
                and all(c["status"] == "passed" for c in checks))
    except (KeyError, ValueError, TypeError):
        return False


def validate_backend_copy(root, cancelled, *, runner=run_command):
    before, contents = capture_backend_source(root)
    platform = repo_root()
    results = []
    with tempfile.TemporaryDirectory(prefix="agenthub-backend-validation-") as directory:
        temporary = Path(directory).resolve()
        project = temporary / "apps/demo-api"
        data = temporary / "data"
        data.mkdir()
        for relative, raw in contents.items():
            destination = temporary / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
        env = validation_environment()
        for key in list(env):
            if key.upper().startswith(("VITE_", "PUBLIC_", "NEXT_PUBLIC_")):
                del env[key]
        env.update({key: str(data) for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TMP", "TEMP", "TMPDIR")})
        env["PYTHONIOENCODING"] = "utf-8"
        for stage in CHECKS:
            if cancelled.is_set():
                break
            argv = [sys.executable, "-I", "-B", str(platform / "scripts/demo-backend-check.py"),
                    stage, str(project), str(data)]
            result = runner(argv, project, env, cancelled)
            if result["status"] == "passed" and not parse_result(result, stage):
                result.update(status="failed", log=str(result["log"]) + "\nIncomplete backend contract evidence.")
            public = [part.replace(str(temporary), "<validation-copy>").replace(str(platform), "<platform>") for part in argv]
            public[0] = "python"
            result.update(kind=stage, argv=public, command=" ".join(public))
            result["log"] = str(result["log"]).replace(str(temporary), "<validation-copy>").replace(str(platform), "<platform>")
            results.append(result)
            if result["status"] != "passed":
                break
        try:
            after, _ = capture_backend_source(root)
            copied, copied_contents = capture_backend_source(temporary)
            unchanged = before == after and copied == before and copied_contents == contents
        except (OSError, ValueError):
            unchanged = False
    status = ("cancelled" if cancelled.is_set() else "stale" if not unchanged
              else "passed" if len(results) == len(CHECKS) and all(c["status"] == "passed" for c in results)
              else "failed")
    return {"schemaVersion": SCHEMA, **before, "profile": BACKEND_PROFILE, "status": status,
            "commands": results, "functional": {"status": "not_configured", "contract": None, "checks": []}}
