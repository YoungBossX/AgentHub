"""Optional identity-bound execution backend, separate from every AgentAdapter."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading

from app.container_exports import materialize_export, parse_export, validate_portable_paths
from app.container_lifecycle import acquire_validation_slot
from app.container_runtime import DockerRuntime
from app.validation_policy import BACKEND_PROFILE, ProfileExecutionResult, ValidationUnavailable, execution_receipt


def execution_metadata(request):
    return execution_receipt(request.execution, request.identity)


def write_snapshot(directory, request):
    contents = request.snapshot.contents
    if not contents or len(contents) > 512 or sum(len(raw) for raw in contents.values()) > 16 * 1024 * 1024:
        raise ValidationUnavailable("Invalid source snapshot budget.")
    validate_portable_paths(contents)
    files = {}
    prefix = "apps/demo-api/" if request.snapshot.profile == BACKEND_PROFILE else "apps/demo/"
    for relative, raw in contents.items():
        checksum = hashlib.sha256(raw).hexdigest()
        if (not relative.startswith(prefix) or len(raw) > 512 * 1024
                or request.snapshot.files.get(relative) != checksum):
            raise ValidationUnavailable("Invalid frozen source input.")
        files[relative] = checksum
    # Validate the complete tree and bytes before creating any input directory.
    directory.parent.mkdir(mode=0o700)  # new operation only, never reuse another owner's files
    directory.mkdir(mode=0o755)
    for relative, raw in contents.items():
        file = directory / relative
        file.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        fd = os.open(file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
        with os.fdopen(fd, "wb") as stream: stream.write(raw)
    manifest = {"schemaVersion": "agenthub.container_input.v1", "profile": request.snapshot.profile,
                "sourceFingerprint": request.snapshot.source_fingerprint, "sourceFiles": files}
    fd = os.open(directory / "manifest.json", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
    with os.fdopen(fd, "w", encoding="utf-8") as stream: json.dump(manifest, stream, separators=(",", ":"))
    return files


class DockerValidationBackend:
    def execute(self, request, cancelled: threading.Event, *, export_dir: Path) -> ProfileExecutionResult:
        execution, commands = execution_metadata(request), []
        if cancelled.is_set(): return ProfileExecutionResult("cancelled", commands, execution)
        executable = shutil.which("docker")
        if not executable:
            execution["reasonCode"] = "docker_missing"
            return ProfileExecutionResult("unavailable", commands, execution)
        image = request.execution.image
        if image is None or request.execution.backend != "docker":
            raise ValidationUnavailable("Docker backend requires its immutable execution binding.")
        status, fingerprint = "unavailable", None
        try:
            context = DockerRuntime.check_context(executable, image.context_name)
            execution["contextFingerprint"] = context["contextFingerprint"]
            # Same daemon under two context aliases still consumes the same slot.
            with acquire_validation_slot(context["daemonFingerprint"], cancelled) as slot:
                runtime = DockerRuntime(slot, image.context_name, context, executable=executable)
                runtime.recover()
                owned = None
                try:
                    input_dir = runtime.reserve(request)
                    expected_files = write_snapshot(input_dir, request)
                    owned = runtime.create(request, input_dir)
                    runtime.start(owned)
                    prepared = runtime.exec_stage(owned, "prepare", cancelled)
                    if prepared["status"] != "passed":
                        execution["reasonCode"] = prepared.get("reasonCode") or "prepare_failed"
                        status = "cancelled" if cancelled.is_set() else "failed"
                    else:
                        stages = ("check", "test") if request.snapshot.profile == BACKEND_PROFILE else ("check", "build", "test")
                        for stage in stages:
                            result = runtime.exec_stage(owned, stage, cancelled)
                            execution["commandsBackend"] = "docker"
                            if request.snapshot.profile == BACKEND_PROFILE and result["status"] == "passed":
                                from app.backend_validation import parse_result
                                if not parse_result(result, stage):
                                    result.update(status="failed", reasonCode="contract_evidence_incomplete")
                            commands.append(result)
                            if result["status"] != "passed":
                                execution["reasonCode"] = result.get("reasonCode") or "command_failed"
                                break
                        status = "cancelled" if cancelled.is_set() else "failed"
                        if len(commands) == len(stages) and all(c["status"] == "passed" for c in commands) and not cancelled.is_set():
                            raw = runtime.export_bytes(owned, cancelled)
                            decoded, _ = parse_export(raw, request.snapshot.source_fingerprint, expected_files)
                            if (request.snapshot.profile == BACKEND_PROFILE and decoded
                                    or request.snapshot.profile != BACKEND_PROFILE and not decoded):
                                raise ValidationUnavailable("Invalid output for the selected profile.")
                            fingerprint = materialize_export(raw, export_dir, request.snapshot.source_fingerprint,
                                                             expected_files=expected_files)
                            status = "passed"
                finally:
                    if owned is not None: runtime.cleanup(owned)
                    else: runtime.cleanup_pending(request.execution.operation_id)
        except (OSError, ValueError, KeyError, IndexError, TypeError, subprocess.SubprocessError) as exc:
            status = "cancelled" if cancelled.is_set() else "unavailable"
            text = str(exc)
            execution["reasonCode"] = ("cleanup_required" if "cleanup_required" in text else
                                       "timeout" if "timeout" in text else
                                       "capacity_unavailable" if "capacity" in text else "execution_unavailable")
        return ProfileExecutionResult(status, commands, execution, fingerprint)
