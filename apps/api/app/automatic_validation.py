"""Fixed, server-owned validation profiles. No scripts from Agent output."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
from uuid import uuid4

from sqlmodel import Session as DbSession, select

from app.validation_process import start_process, stop_process
from app.events import append_task_run_event
from app.models import Task, TaskRun, TaskRunEvent
from app.native_reviews import _no_link, _read_file
from app.process_environment import project_process_env, redact_process_evidence
from app.validation_inputs import capture_profile_inputs
from app.validation_policy import (ValidationUnavailable, bind_execution, digest, identity_for_run,
                                   resolve_backend_settings, execution_receipt, FixedValidationRequest)
from app.worktrees import repo_root
from app.requirement_validation import requirement_contract as contract_for_plan

SCHEMA = "agenthub.validation.v1"
PROFILE = "vite-build-smoke-v1"
BACKEND_PROFILE = "fastapi-contract-v1"
MAX_FILES = 512
MAX_BYTES = 16 * 1024 * 1024
COMMAND_TIMEOUT = 60
CONFIG_FILES = ("package.json", "vite.config.ts", "tsconfig.json", "tsconfig.app.json")


def profile_for_target(target_id):
    return {"demo-frontend": PROFILE, "demo-backend": BACKEND_PROFILE}.get(target_id)


def required_command_kinds(profile):
    return {PROFILE: ("check", "build", "test"), BACKEND_PROFILE: ("check", "test")}.get(profile, ())


def capture_profile_source(root, profile):
    if profile == BACKEND_PROFILE:
        from app.backend_validation import capture_backend_source
        return capture_backend_source(root)
    if profile != PROFILE:
        raise ValidationUnavailable("Unsupported automatic validation profile.")
    return capture_validation_source(root)


def capture_validation_source(root: Path):
    snapshot = capture_profile_inputs(root, PROFILE)
    files, contents = dict(snapshot.files), dict(snapshot.contents)
    platform = repo_root()
    policy = {
        "profile": PROFILE,
        "inputPolicy": dict(snapshot.policy_inputs),
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


def run_command(argv, cwd, env, cancelled, timeout=COMMAND_TIMEOUT):
    process = start_process(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
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
        stop_process(process)
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
                from app.validation_browser import run_browser_validation
                functional = run_browser_validation(project / "dist", requirement_contract, cancelled, runner=runner)
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


def _docker_profile_receipt(request, cancelled, requirement_contract):
    from app.docker_validation import DockerValidationBackend
    from app.validation_browser import run_browser_validation
    with tempfile.TemporaryDirectory(prefix="agenthub-container-output-") as directory:
        output = Path(directory).resolve() / "verified"
        result = DockerValidationBackend().execute(request, cancelled, export_dir=output)
        status = result.status
        functional = {"status": "not_configured", "contract": None, "checks": []}
        if requirement_contract:
            functional.update(status="not_run", contract=requirement_contract)
            if status == "passed" and not cancelled.is_set():
                functional = run_browser_validation(output, requirement_contract, cancelled)
                if functional.get("execution", {}).get("inputArtifactFingerprint") != result.output_fingerprint:
                    status = "stale"
                elif functional["status"] == "failed": status = "failed"
                elif functional["status"] != "passed": status = "incomplete"
        if cancelled.is_set(): status = "cancelled"
        return {"schemaVersion": SCHEMA, "profile": request.snapshot.profile,
                "files": dict(request.snapshot.files), "sourceFingerprint": request.snapshot.source_fingerprint,
                "policyFingerprint": request.execution.policy_fingerprint,
                "status": status, "commands": result.commands, "execution": result.execution,
                "functional": functional, "outputFingerprint": result.output_fingerprint,
                "requirementFingerprint": digest(requirement_contract)}


async def run_automatic_validation(db: DbSession, run: TaskRun, *, ownership_guard=lambda: True, requirement_contract=None):
    task = db.get(Task, run.task_id)
    plan = json.loads(task.plan_json) if task else {}
    profile = profile_for_target(plan.get("targetId"))
    if profile is None or validation_for_run(db, run.id) is not None or not ownership_guard():
        return  # no interrupted validation is replayed under the same TaskRun
    adapter_run_id = run.adapter_run_id
    launch_metrics = run.metrics_json
    snapshot = identity = binding = execution = preparation_error = None
    settings = None
    try:
        settings = resolve_backend_settings()
        identity = identity_for_run(run, task, launching=True)
        snapshot = capture_profile_inputs(Path(run.worktree_path), profile)
        if settings["backend"] == "docker" and identity is None:
            raise ValidationUnavailable("Docker validation requires a frozen launch identity.")
        if identity is not None:
            binding = bind_execution(snapshot, identity, settings)
            execution = execution_receipt(binding, identity)
    except (OSError, ValueError) as exc:
        preparation_error = exc
        execution = {"backend": settings["backend"] if settings else "native", "commandsBackend": "not_run",
                     "operationId": uuid4().hex,
                     "runtimePolicyId": "container-validation-v1" if settings and settings["backend"] == "docker" else "native-fixed-validation-v1",
                     "generationFingerprint": identity.generation_fingerprint if identity else None,
                     "reasonCode": "preparation_unavailable"}
    started = {"schemaVersion": SCHEMA, "profile": profile, "status": "running",
               "taskRunId": run.id, "adapterRunId": adapter_run_id}
    if snapshot is not None: started["sourceFingerprint"] = snapshot.source_fingerprint
    if execution is not None: started["execution"] = execution
    append_task_run_event(db, task_run_id=run.id, event_type="validation.started", payload_json=json.dumps(started))
    cancelled = threading.Event()
    try:
        if preparation_error is not None: raise preparation_error
        if settings["backend"] == "docker":
            request = FixedValidationRequest(snapshot, identity, binding)
            operation = asyncio.create_task(asyncio.to_thread(_docker_profile_receipt, request, cancelled, requirement_contract))
        else:
            kwargs = {"requirement_contract": requirement_contract} if requirement_contract else {}
            validator = validate_copy
            if profile == BACKEND_PROFILE:
                from app.backend_validation import validate_backend_copy
                validator, kwargs = validate_backend_copy, {}
            operation = asyncio.create_task(asyncio.to_thread(validator, Path(run.worktree_path), cancelled, **kwargs))
        try:
            while not operation.done():
                await asyncio.wait({operation}, timeout=0.1)
                if not ownership_guard():
                    cancelled.set()
                    await asyncio.gather(operation, return_exceptions=True)
                    return
            result = await asyncio.shield(operation)
        except asyncio.CancelledError:
            cancelled.set()
            await asyncio.gather(operation, return_exceptions=True)
            raise
        if execution is not None and settings["backend"] == "native":
            result["execution"] = {**execution, "commandsBackend": "native" if result.get("commands") else "not_run"}
            result["nativePolicyFingerprint"] = result.get("policyFingerprint")
            result["policyFingerprint"] = digest({"nativePolicy": result.get("policyFingerprint"), "executionPolicy": binding.policy_fingerprint})
            result["outputFingerprint"] = result.get("functional", {}).get("execution", {}).get("inputArtifactFingerprint")
        # Re-capture policy/source on the main thread; workers hold no DB session.
        current = capture_profile_inputs(Path(run.worktree_path), profile)
        if (current.files != snapshot.files or current.policy_inputs != snapshot.policy_inputs
                or binding and bind_execution(current, identity, resolve_backend_settings()).policy_fingerprint != binding.policy_fingerprint):
            result["status"] = "stale"
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        result = {"schemaVersion": SCHEMA, "profile": profile, "status": "unavailable", "commands": [],
                  "reason": str(exc) if isinstance(exc, ValidationUnavailable) else "Source capture or command execution was unavailable."}
        if execution is not None: result["execution"] = execution
    if not ownership_guard(): return
    db.refresh(run)
    if run.state != "collecting_diff" or run.adapter_run_id != adapter_run_id: return
    try:
        current_identity = identity_for_run(run, task)
        if current_identity != identity: return
    except ValueError:
        if preparation_error is None or run.metrics_json != launch_metrics:
            return
    result.update(taskRunId=run.id, adapterRunId=adapter_run_id)
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
    stored = validation_for_run(db, run_id)
    if not receipt.get("eventId") or stored is None or any(stored.get(key) != receipt.get(key) for key in (
            "eventId", "taskRunId", "adapterRunId", "profile", "status", "sourceFingerprint", "policyFingerprint",
            "requirementFingerprint", "execution", "outputFingerprint", "nativePolicyFingerprint")):
        return "unverifiable"
    try:
        settings = resolve_backend_settings()
        task = db.get(Task, run.task_id)
        plan = json.loads(task.plan_json) if task else {}
        profile = profile_for_target(plan.get("targetId"))
        if profile is None or receipt.get("profile") != profile: return "unverifiable"
        if "requirementFingerprint" in receipt and digest(contract_for_plan(plan)) != receipt["requirementFingerprint"]:
            return "expired"
        execution = receipt.get("execution")
        if execution is None:
            if settings["backend"] != "native": return "expired"
            current, _ = capture_profile_source(Path(run.worktree_path), profile)
            return "current" if all(current[key] == receipt.get(key) for key in ("sourceFingerprint", "policyFingerprint")) else "expired"
        if not isinstance(execution, dict): return "unverifiable"
        identity = identity_for_run(run, task)
        if identity is None or identity.generation_fingerprint != execution.get("generationFingerprint"):
            return "unverifiable"
        if execution.get("backend") != settings["backend"]: return "expired"
        snapshot = capture_profile_inputs(Path(run.worktree_path), profile)
        binding = bind_execution(snapshot, identity, settings)
        expected = execution_receipt(binding, identity)
        if any(execution.get(k) != expected[k] for k in ("backend", "imageId", "recipeFingerprint", "runtimePolicyId")):
            return "expired"
        if not isinstance(execution.get("operationId"), str) or len(execution["operationId"]) != 32:
            return "unverifiable"
        if execution.get("commandsBackend") not in {execution["backend"], "not_run"}:
            return "unverifiable"
        if receipt["status"] == "passed" and execution.get("commandsBackend") != execution["backend"]:
            return "unverifiable"
        start = db.exec(select(TaskRunEvent).where(TaskRunEvent.task_run_id == run_id,
            TaskRunEvent.event_type == "validation.started").order_by(TaskRunEvent.sequence.desc())).first()
        if start is None: return "unverifiable"
        began = json.loads(start.payload_json)
        if (began.get("taskRunId") != run_id or began.get("adapterRunId") != run.adapter_run_id
                or began.get("sourceFingerprint") != receipt.get("sourceFingerprint")
                or any(began.get("execution", {}).get(k) != execution.get(k) for k in (
                    "operationId", "backend", "imageId", "recipeFingerprint", "runtimePolicyId", "generationFingerprint"))):
            return "unverifiable"
        if execution["backend"] == "native":
            current, _ = capture_profile_source(Path(run.worktree_path), profile)
            if receipt.get("nativePolicyFingerprint") != current["policyFingerprint"]:
                return "expired"
            policy = digest({"nativePolicy": current["policyFingerprint"], "executionPolicy": binding.policy_fingerprint})
        else:
            policy = binding.policy_fingerprint
        functional = stored.get("functional", {})
        if functional.get("execution") and (functional["execution"].get("backend") != "native"
                or functional["execution"].get("inputArtifactFingerprint") != stored.get("outputFingerprint")):
            return "unverifiable"
        return "current" if snapshot.source_fingerprint == receipt.get("sourceFingerprint") and policy == receipt.get("policyFingerprint") else "expired"
    except (OSError, ValueError, TypeError, KeyError):
        return "unverifiable"
