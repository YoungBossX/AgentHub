"""Fixed, server-owned Vite validation. No package scripts from Agent output."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import tempfile
import threading
import time

from sqlmodel import Session as DbSession, select

from app.events import append_task_run_event
from app.models import Task, TaskRun, TaskRunEvent
from app.native_reviews import _no_link, _read_file
from app.process_environment import project_process_env, redact_process_evidence
from app.target_registry import protected_repository_path_category
from app.worktrees import repo_root
from app.requirement_validation import requirement_contract as contract_for_plan, parse_browser_result

SCHEMA = "agenthub.validation.v1"
PROFILE = "vite-build-smoke-v1"
MAX_FILES = 512
MAX_BYTES = 16 * 1024 * 1024
COMMAND_TIMEOUT = 60
CONFIG_FILES = ("package.json", "vite.config.ts", "tsconfig.json", "tsconfig.app.json")


class ValidationUnavailable(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def capture_validation_source(root: Path):
    """Hash inputs, never build caches/dependencies; reject links and secret inputs."""
    root = root.absolute()
    for parent in [root, *root.parents]:
        _no_link(parent)
    if root.resolve() != root:
        raise ValidationUnavailable("Validation source must be a canonical worktree.")
    project = root / "apps/demo"
    files, contents = {}, {}
    pending = [project]
    seen = 0
    while pending:
        path = pending.pop()
        seen += 1
        if seen > 1024:
            raise ValidationUnavailable("Validation source exceeds entry budget.")
        relative = path.relative_to(root).as_posix()
        if path.parent == project and path.name in {"node_modules", "dist"}:
            continue
        if protected_repository_path_category(relative) is not None:
            raise ValidationUnavailable("Protected input is not supported by automatic validation.")
        info = _no_link(path)
        if stat.S_ISDIR(info.st_mode):
            for child in path.iterdir():
                pending.append(child)
                if len(pending) + seen > 1024:
                    raise ValidationUnavailable("Validation source exceeds entry budget.")
            continue
        if not stat.S_ISREG(info.st_mode):
            raise ValidationUnavailable("Validation requires regular source files.")
        receipt = _read_file(root, path, include_bytes=True)
        raw = receipt["content"]
        files[relative] = receipt["sha256"]
        contents[relative] = raw
        if len(files) > MAX_FILES or sum(len(value) for value in contents.values()) > MAX_BYTES:
            raise ValidationUnavailable("Validation source exceeds byte/file budget.")
    platform = repo_root()
    # Agent-editable source cannot replace executable build configuration.
    for name in CONFIG_FILES:
        expected = (platform / "apps/demo" / name).read_bytes()
        if contents.get(f"apps/demo/{name}") != expected:
            raise ValidationUnavailable("Build configuration differs from the trusted demo profile.")
    for name in ("pnpm-lock.yaml", "package.json", "pnpm-workspace.yaml"):
        # Record both worktree and actually used dependency-policy inputs.
        source = root / name
        if not source.exists():
            raise ValidationUnavailable("Dependency policy input is missing.")
        files[name] = _read_file(root, source)["sha256"]
    policy = {
        "profile": PROFILE,
        "lock": hashlib.sha256((platform / "pnpm-lock.yaml").read_bytes()).hexdigest(),
        "smoke": hashlib.sha256((platform / "scripts/demo-build-smoke.test.mjs").read_bytes()).hexdigest(),
        "build": hashlib.sha256((platform / "scripts/demo-validation-build.mjs").read_bytes()).hexdigest(),
        "runner": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "requirements": hashlib.sha256((platform / "scripts/demo-requirement-check.mjs").read_bytes()).hexdigest(),
        "contractPolicy": hashlib.sha256((platform / "apps/api/app/requirement_validation.py").read_bytes()).hexdigest(),
        "environment": digest(validation_environment()),
    }
    return {"files": files, "sourceFingerprint": digest(files), "policyFingerprint": digest(policy)}, contents


def validation_environment():
    # Build-time public values are intentionally excluded from this fixed profile.
    env = {key: value for key, value in project_process_env().items()
           if not key.upper().startswith(("VITE_", "PUBLIC_", "NEXT_PUBLIC_"))}
    env.update(CI="1", NODE_ENV="production")
    if os.environ.get("AGENTHUB_VALIDATION_BROWSER_CHANNEL"):
        env["AGENTHUB_VALIDATION_BROWSER_CHANNEL"] = os.environ["AGENTHUB_VALIDATION_BROWSER_CHANNEL"]
    return env


def _kill_tree(process):
    if os.name == "nt":
        if process.poll() is None:
            subprocess.run([str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/taskkill.exe"),
                            "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=10, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()
    process.wait(timeout=10)


def run_command(argv, cwd, env, cancelled, timeout=COMMAND_TIMEOUT):
    process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               start_new_session=os.name != "nt")
    output = bytearray()
    def drain():
        while chunk := process.stdout.read(4096):
            if len(output) < 12000:
                output.extend(chunk[:12000 - len(output)])
    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    started = time.monotonic()
    reason = None
    try:
        while process.poll() is None:
            if cancelled.is_set() or time.monotonic() - started > timeout:
                reason = "cancelled" if cancelled.is_set() else "timeout"
                break
            cancelled.wait(0.05)
    finally:
        _kill_tree(process)
        reader.join(timeout=2)
        if not reader.is_alive():
            process.stdout.close()
    return {"exitCode": process.returncode, "status": reason or ("passed" if process.returncode == 0 else "failed"),
            "log": redact_process_evidence(output.decode("utf-8", errors="replace"), env),
            "durationMs": int((time.monotonic() - started) * 1000)}


def validate_copy(root: Path, cancelled: threading.Event, *, runner=run_command, requirement_contract=None):
    before, contents = capture_validation_source(root)
    platform = repo_root()
    node = shutil.which("node")
    dependencies = platform / "apps/demo/node_modules"
    tsc = dependencies / "typescript/bin/tsc"
    vite = dependencies / "vite/bin/vite.js"
    if not node or not tsc.is_file() or not vite.is_file():
        raise ValidationUnavailable("Installed Node/TypeScript/Vite dependencies are unavailable.")
    results = []
    functional = {"status": "not_configured", "contract": None, "checks": []}
    if requirement_contract:
        functional = {"status": "not_run", "contract": requirement_contract, "checks": []}
    with tempfile.TemporaryDirectory(prefix="agenthub-validation-") as directory:
        temporary = Path(directory).resolve()
        project = temporary / "apps/demo"
        for relative, raw in contents.items():
            destination = temporary / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
        link = project / "node_modules"
        link.symlink_to(dependencies.resolve(), target_is_directory=True)
        try:
            env = validation_environment()
            env.update({"CI": "1", "AGENTHUB_VALIDATION_OUTPUT": str(project / "dist")})
            commands = [
                ("check", [node, str(tsc.resolve()), "--project", "tsconfig.app.json", "--incremental",
                           "--tsBuildInfoFile", str(temporary / "check.tsbuildinfo")]),
                ("build", [node, str(platform / "scripts/demo-validation-build.mjs")]),
                ("test", [node, "--test", str(platform / "scripts/demo-build-smoke.test.mjs")]),
            ]
            for kind, argv in commands:
                if cancelled.is_set():
                    break
                result = runner(argv, project, env, cancelled)
                public_argv = [part.replace(str(temporary), "<validation-copy>").replace(str(platform), "<platform>") for part in argv]
                public_argv[0] = "node"
                result.update({"kind": kind, "argv": public_argv, "command": " ".join(public_argv)})
                # Absolute temporary/dependency paths are not useful in public logs.
                result["log"] = str(result["log"]).replace(str(temporary), "<validation-copy>").replace(str(platform), "<platform>")
                results.append(result)
                if result["status"] != "passed":
                    break
            if requirement_contract and len(results) == 3 and all(r["status"] == "passed" for r in results) and not cancelled.is_set():
                env["AGENTHUB_REQUIREMENT_CONTRACT"] = json.dumps(requirement_contract, ensure_ascii=True)
                browser_result = runner([node, str(platform / "scripts/demo-requirement-check.mjs")], project, env, cancelled)
                functional = parse_browser_result(browser_result, requirement_contract)
        finally:
            # Remove the known link before temporary recursive cleanup; never follow dependencies.
            if link.is_symlink():
                link.unlink()
        try:
            after, _ = capture_validation_source(root)
            unchanged = after == before and capture_validation_source_copy(temporary, contents)
        except (OSError, ValueError):
            unchanged = False
    status = ("cancelled" if cancelled.is_set() else "stale" if not unchanged
              else "failed" if functional["status"] == "failed"
              else "incomplete" if functional["status"] == "unavailable"
              else "passed" if len(results) == 3 and all(r["status"] == "passed" for r in results)
              else "failed")
    return {"schemaVersion": SCHEMA, **before, "profile": PROFILE, "status": status, "commands": results,
            "functional": functional, "requirementFingerprint": digest(requirement_contract)}


def capture_validation_source_copy(root, contents):
    # Detect command-side edits to the copied inputs. Generated output is separate.
    for relative, raw in contents.items():
        path = root / relative
        try:
            if _read_file(root, path)["sha256"] != hashlib.sha256(raw).hexdigest():
                return False
        except (OSError, ValueError):
            return False
    project = root / "apps/demo"
    actual = {p.relative_to(root).as_posix() for p in project.rglob("*")
              if p.is_file() and not p.is_relative_to(project / "dist")}
    return actual == set(contents)


async def run_automatic_validation(db: DbSession, run: TaskRun, *, ownership_guard=lambda: True, requirement_contract=None):
    task = db.get(Task, run.task_id)
    plan = json.loads(task.plan_json) if task else {}
    if plan.get("targetId") != "demo-frontend":
        return
    existing = validation_for_run(db, run.id)
    if existing is not None:
        return  # an interrupted receipt is never retried under the same run
    if not ownership_guard():
        return
    adapter_run_id = run.adapter_run_id
    append_task_run_event(db, task_run_id=run.id, event_type="validation.started", payload_json=json.dumps({
        "schemaVersion": SCHEMA, "profile": PROFILE, "status": "running",
        "taskRunId": run.id, "adapterRunId": adapter_run_id,
    }))
    cancelled = threading.Event()
    kwargs = {"requirement_contract": requirement_contract} if requirement_contract else {}
    operation = asyncio.create_task(asyncio.to_thread(validate_copy, Path(run.worktree_path), cancelled, **kwargs))
    try:
        result = await asyncio.shield(operation)
    except asyncio.CancelledError:
        cancelled.set()
        await asyncio.gather(operation, return_exceptions=True)
        raise
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        result = {"schemaVersion": SCHEMA, "profile": PROFILE, "status": "unavailable",
                  "reason": str(exc) if isinstance(exc, ValidationUnavailable) else "Source capture or command execution was unavailable."}
    if not ownership_guard():
        return
    db.refresh(run)
    if run.state != "collecting_diff":
        return
    result["taskRunId"] = run.id
    result["adapterRunId"] = adapter_run_id
    append_task_run_event(db, task_run_id=run.id, event_type="validation.completed", payload_json=json.dumps(result, separators=(",", ":")))


def validation_for_run(db, run_id):
    event = db.exec(select(TaskRunEvent).where(
        TaskRunEvent.task_run_id == run_id,
        TaskRunEvent.event_type.in_(["validation.started", "validation.completed"]),
    ).order_by(TaskRunEvent.sequence.desc())).first()
    if event is None:
        return None
    try:
        data = json.loads(event.payload_json)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("schemaVersion") != SCHEMA:
        return None
    return {**data, "eventId": event.id}


def validation_currentness(db, run_id, receipt):
    run = db.get(TaskRun, run_id)
    if (run is None or run.state not in {"collecting_diff", "completed"}
            or receipt.get("taskRunId") != run_id or receipt.get("schemaVersion") != SCHEMA
            or receipt.get("adapterRunId") != run.adapter_run_id
            or receipt.get("status") not in {"passed", "failed", "incomplete"}):
        return "unverifiable"
    # The embedded review receipt must still refer to the original server event.
    stored = validation_for_run(db, run_id)
    if not receipt.get("eventId") or stored is None or any(stored.get(key) != receipt.get(key) for key in (
            "eventId", "taskRunId", "adapterRunId", "status", "sourceFingerprint", "policyFingerprint", "requirementFingerprint")):
        return "unverifiable"
    try:
        if "requirementFingerprint" in receipt:
            task = db.get(Task, run.task_id)
            plan = json.loads(task.plan_json) if task else {}
            if digest(contract_for_plan(plan)) != receipt["requirementFingerprint"]:
                return "expired"
        current, _ = capture_validation_source(Path(run.worktree_path))
        return "current" if all(current[key] == receipt.get(key) for key in ("sourceFingerprint", "policyFingerprint")) else "expired"
    except (OSError, ValueError):
        return "unverifiable"
