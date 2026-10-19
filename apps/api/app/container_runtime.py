"""Fixed Docker argv and ownership checks. Never exposed as an Agent tool."""

import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import threading
import time

from app.validation_process import start_process, stop_process
from app.container_exports import MAX_TRANSPORT, assert_canonical_directory
from app.container_lifecycle import OwnedContainer, owner_reclaimable, process_identity
from app.sandbox_cli import docker_client_environment, docker_endpoint_arguments, inspect_context
from app.validation_policy import (PROFILES, RUNTIME_POLICY, RUNTIME_POLICY_ID, ValidationUnavailable,
                                   ImageBinding, digest, valid_image_id)

CID = re.compile(r"[0-9a-f]{64}\Z")


def run_cli(argv, cancelled, *, timeout, output_limit=12000, strict_limit=False):
    """Drain both pipes even after the public budget; export overrun terminates."""
    started = time.monotonic()
    if cancelled.is_set():
        return {"status": "cancelled", "exitCode": None, "stdout": b"", "stderr": b"", "durationMs": 0}
    process = start_process(argv, shell=False, env=docker_client_environment(), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=os.name != "nt")
    output, errors = bytearray(), bytearray()
    exceeded, read_error = threading.Event(), threading.Event()
    def drain(pipe, buffer, limit, enforce):
        seen = 0
        try:
            while chunk := pipe.read(4096):
                seen += len(chunk)
                if len(buffer) < limit: buffer.extend(chunk[:limit - len(buffer)])
                if enforce and seen > limit: exceeded.set()
        except OSError: read_error.set()
        finally: pipe.close()
    readers = [threading.Thread(target=drain, args=(process.stdout, output, output_limit, strict_limit), daemon=True),
               threading.Thread(target=drain, args=(process.stderr, errors, 12000, False), daemon=True)]
    for reader in readers: reader.start()
    reason = None
    try:
        while process.poll() is None:
            if cancelled.is_set(): reason = "cancelled"; break
            if exceeded.is_set(): reason = "output_limit"; break
            if time.monotonic() - started >= timeout: reason = "timeout"; break
            cancelled.wait(0.02)
    finally:
        stop_process(process)
        for reader in readers: reader.join(timeout=2)
    reason = reason or ("output_limit" if exceeded.is_set() else "failed" if read_error.is_set()
                        or any(r.is_alive() for r in readers) else None)
    return {"status": reason or ("passed" if process.returncode == 0 else "failed"), "exitCode": process.returncode,
            "stdout": bytes(output), "stderr": bytes(errors), "durationMs": int((time.monotonic() - started) * 1000)}


def create_arguments(request, input_dir, labels):
    image = request.execution.image
    if (request.execution.backend != "docker" or image is None or not valid_image_id(image.image_id)
            or request.snapshot.profile not in PROFILES or request.execution.profile != request.snapshot.profile):
        raise ValidationUnavailable("Unsupported Docker request.")
    if any(c in str(input_dir) for c in ",\"'\r\n"):
        raise ValidationUnavailable("Docker mount source contains ambiguous CSV characters.")
    directory = assert_canonical_directory(input_dir)
    args = ["container", "create", "--pull", "never", "--platform", "linux/amd64", "--user", "10001:10001",
            "--init", "--read-only", "--network", "none", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--cpus", "1", "--memory", "1073741824", "--memory-swap", "1073741824", "--pids-limit", "128",
            "--ipc", "private", "--cgroupns", "private", "--log-driver", "none", "--restart", "no", "--no-healthcheck",
            "--workdir", "/work", "--entrypoint", "/opt/agenthub/control",
            "--tmpfs", "/work:rw,nosuid,nodev,noexec,size=536870912,uid=10001,gid=10001,mode=0700",
            "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=67108864,uid=10001,gid=10001,mode=0700",
            "--mount", f"type=bind,source={directory},destination=/input,readonly"]
    for key, value in RUNTIME_POLICY["environment"].items(): args.extend(["--env", key + "=" + value])
    for key, value in sorted(labels.items()): args.extend(["--label", key + "=" + value])
    return [*args, image.image_id, "hold"]


def execution_reason(result, state):
    if result["status"] in {"cancelled", "timeout", "output_limit"}: return result["status"]
    if state.get("OOMKilled") is True: return "oom_confirmed"
    if result["exitCode"] == 137: return "process_killed"
    return "command_failed" if result["status"] != "passed" else None


def labels_for(record):
    fields = {"operation": "operationId", "profile": "profile", "recipe": "recipeFingerprint",
              "task": "taskRunId", "adapter": "adapterRunId", "attempt": "executionAttemptId",
              "generation": "generationFingerprint", "context": "contextFingerprint",
              "owner-pid": "ownerPid", "owner-start": "ownerStart", "policy": "runtimePolicyId"}
    return {"io.agenthub.validation." + key: str(record[value]) for key, value in fields.items()}


def _mount_sources(path):
    sources = {str(path), path.as_posix()}
    if os.name == "nt" and path.drive:
        tail = path.as_posix()[2:].lstrip("/")
        sources.update({f"/run/desktop/mnt/host/{path.drive[0].lower()}/{tail}",
                        f"/host_mnt/{path.drive[0].lower()}/{tail}"})
    return sources


class DockerRuntime:
    def __init__(self, slot, context_name, context, *, executable=None):
        self.slot, self.context_name, self.context = slot, context_name, dict(context)
        self.executable = executable or shutil.which("docker")
        if not self.executable: raise ValidationUnavailable("docker_missing")
        self.deadline = time.monotonic() + 180
        self.image_environments = {}

    @staticmethod
    def check_context(executable, context_name):
        return inspect_context(executable, context_name)

    def ensure_context(self):
        current = self.check_context(self.executable, self.context_name)
        if any(current.get(k) != self.context.get(k) for k in ("contextFingerprint", "daemonFingerprint", "endpoint")):
            raise ValidationUnavailable("cleanup_required: Docker context changed.")

    def call(self, args, *, cancelled=None, timeout=10, output_limit=1024 * 1024, strict_limit=True, cleanup=False):
        remaining = self.deadline - time.monotonic()
        if not cleanup and remaining <= 0: raise ValidationUnavailable("timeout: profile deadline exceeded.")
        with docker_endpoint_arguments(self.executable, self.context.get("endpoint")) as prefix:
            return run_cli([*prefix, *args], cancelled or threading.Event(),
                           timeout=timeout if cleanup else min(timeout, remaining),
                           output_limit=output_limit, strict_limit=strict_limit)

    def metadata(self, args, *, cleanup=False):
        result = self.call(args, cleanup=cleanup)
        if result["status"] != "passed": raise ValidationUnavailable("Docker metadata unavailable.")
        try: return json.loads(result["stdout"])
        except (ValueError, TypeError) as exc: raise ValidationUnavailable("Invalid Docker metadata.") from exc

    def check_image(self, image, profile):
        values = self.metadata(["image", "inspect", image.image_id])
        try:
            value = values[0]
            config = value["Config"]
            if (len(values) != 1 or value["Id"] != image.image_id or value["Os"] != "linux" or value["Architecture"] != "amd64"
                    or config["User"] != "10001:10001" or config["Entrypoint"] != ["/opt/agenthub/control"]
                    or config["Cmd"] != ["hold"] or config.get("Volumes") or config.get("ExposedPorts")
                    or config["Labels"].get("io.agenthub.validation.profile") != profile
                    or config["Labels"].get("io.agenthub.validation.recipe") != image.recipe_fingerprint):
                raise ValidationUnavailable("image_refused")
            environment = self.parse_environment(config.get("Env"))
            allowed = {"PATH", "LANG", "NODE_VERSION", "YARN_VERSION", "GPG_KEY", "PYTHON_VERSION", "PYTHON_SHA256"}
            if set(environment) - allowed:
                raise ValidationUnavailable("image_refused: unexpected image environment.")
            self.image_environments[image.image_id] = {**environment, **RUNTIME_POLICY["environment"]}
        except (KeyError, TypeError, IndexError) as exc: raise ValidationUnavailable("image_refused") from exc

    @staticmethod
    def parse_environment(values):
        if not isinstance(values, list) or len(values) > 64:
            raise ValidationUnavailable("cleanup_required: invalid container environment.")
        result = {}
        for value in values:
            if not isinstance(value, str) or len(value) > 4096 or "=" not in value or "\0" in value:
                raise ValidationUnavailable("cleanup_required: invalid container environment.")
            key, content = value.split("=", 1)
            if not key or key in result:
                raise ValidationUnavailable("cleanup_required: duplicate container environment.")
            result[key] = content
        return result

    def reserve(self, request):
        operation = request.execution.operation_id
        path = self.slot.journal_path(operation)
        if path.exists(): raise ValidationUnavailable("cleanup_required: operation already reserved.")
        input_dir = self.slot.directory / operation / "input"
        identity, image = request.identity, request.execution.image
        record = {"schemaVersion": "agenthub.container_journal.v1", "operationId": operation,
            "contextName": self.context_name, **self.context, "imageId": image.image_id, "recipeFingerprint": image.recipe_fingerprint,
            "profile": request.snapshot.profile, "taskRunId": identity.task_run_id, "adapterRunId": identity.adapter_run_id,
            "executionAttemptId": identity.execution_attempt_id, "generationFingerprint": identity.generation_fingerprint,
            "inputDir": str(input_dir), "ownerPid": os.getpid(), "ownerStart": process_identity(os.getpid()),
            "expiresAt": time.time() + 190, "containerId": None, "state": "reserved", "createAttempted": False,
            "runtimePolicyId": RUNTIME_POLICY_ID}
        self.slot.save(record)  # before input allocation and before container creation
        return input_dir

    def create(self, request, input_dir):
        operation = request.execution.operation_id
        path = self.slot.journal_path(operation)
        if not path.exists(): self.reserve(request)
        record = self.slot.load(path)
        if (input_dir != Path(record["inputDir"]) or record["containerId"] is not None
                or record["state"] != "reserved" or record["ownerPid"] != os.getpid()
                or record["ownerStart"] != process_identity(os.getpid())
                or record["imageId"] != request.execution.image.image_id
                or record["generationFingerprint"] != request.identity.generation_fingerprint):
            raise ValidationUnavailable("cleanup_required: operation reservation mismatch.")
        self.ensure_context()
        self.check_image(request.execution.image, request.snapshot.profile)
        record.update(state="creating", createAttempted=True)
        self.slot.save(record)  # failure after dispatch has an unknown daemon outcome
        result = self.call(create_arguments(request, input_dir, labels_for(record)))
        container_id = result["stdout"].decode("ascii", errors="replace").strip()
        if result["status"] != "passed" or not CID.fullmatch(container_id):
            raise ValidationUnavailable("Container creation did not produce an owned ID.")
        record.update(containerId=container_id, state="created")
        self.slot.save(record)
        owned = OwnedContainer(container_id, operation, self.context_name, path)
        self.verify(owned)
        return owned

    def verify(self, owned, *, cleanup=False):
        self.ensure_context()
        record = self.slot.load(owned.journal_path)
        if (record["containerId"] != owned.container_id or record["operationId"] != owned.operation_id
                or record["contextName"] != owned.context_name or record["contextName"] != self.context_name
                or any(record[k] != self.context[k] for k in ("contextFingerprint", "daemonFingerprint", "endpoint"))):
            raise ValidationUnavailable("cleanup_required: journal ownership mismatch.")
        values = self.metadata(["container", "inspect", owned.container_id], cleanup=cleanup)
        try:
            value = values[0]
            config, host = value["Config"], value["HostConfig"]
            labels = config.get("Labels") or {}
            if record["imageId"] not in self.image_environments:
                self.check_image(ImageBinding(record["imageId"], record["recipeFingerprint"], "linux/amd64", self.context_name),
                                 record["profile"])
            if self.parse_environment(config.get("Env")) != self.image_environments[record["imageId"]]:
                raise ValidationUnavailable("cleanup_required: container environment mismatch.")
            if (len(values) != 1 or value["Id"] != owned.container_id or value["Image"] != record["imageId"]
                    or any(labels.get(k) != v for k, v in labels_for(record).items())
                    or config["User"] != "10001:10001" or config["Entrypoint"] != ["/opt/agenthub/control"]
                    or config["Cmd"] != ["hold"] or config.get("ExposedPorts") or config.get("Volumes")
                    or host["ReadonlyRootfs"] is not True or host["Init"] is not True
                    or host["NetworkMode"] != "none" or host["Privileged"] is not False or host.get("CapAdd")
                    or set(host["CapDrop"]) not in ({"ALL"}, {"all"})
                    or host["SecurityOpt"] not in (["no-new-privileges"], ["no-new-privileges:true"])
                    or host["Memory"] != 1073741824 or host["MemorySwap"] != 1073741824
                    or host["NanoCpus"] != 1000000000 or host["PidsLimit"] != 128
                    or host.get("PidMode") not in {None, ""} or host.get("UTSMode") not in {None, ""}
                    or host["IpcMode"] != "private" or host["CgroupnsMode"] != "private"
                    or any(host.get(k) for k in ("Devices", "DeviceRequests", "PortBindings", "ExtraHosts", "VolumesFrom", "Binds"))
                    or host.get("AutoRemove") is True or host["LogConfig"]["Type"] != "none"
                    or host["RestartPolicy"]["Name"] != "no"):
                raise ValidationUnavailable("cleanup_required: container ownership/policy mismatch.")
            expected_tmpfs = {"/work": "rw,nosuid,nodev,noexec,size=536870912,uid=10001,gid=10001,mode=0700",
                              "/tmp": "rw,nosuid,nodev,noexec,size=67108864,uid=10001,gid=10001,mode=0700"}
            if host["Tmpfs"] != expected_tmpfs: raise ValidationUnavailable("cleanup_required: tmpfs mismatch.")
            mounts = value["Mounts"]
            inputs = [m for m in mounts if m["Destination"] == "/input"]
            if (len(inputs) != 1 or inputs[0]["Type"] != "bind" or inputs[0]["RW"] is not False
                    or inputs[0]["Source"] not in _mount_sources(Path(record["inputDir"]))
                    or any(m["Destination"] not in {"/input", "/work", "/tmp"} for m in mounts)
                    or any(m["Type"] != "tmpfs" for m in mounts if m["Destination"] != "/input")):
                raise ValidationUnavailable("cleanup_required: input mount mismatch.")
            return value
        except (KeyError, IndexError, TypeError) as exc:
            raise ValidationUnavailable("cleanup_required: incomplete ownership metadata.") from exc

    def start(self, owned):
        self.verify(owned)
        result = self.call(["container", "start", owned.container_id])
        if result["status"] != "passed": raise ValidationUnavailable("Container start unavailable.")
        value = self.verify(owned)
        if value["State"].get("Running") is not True: raise ValidationUnavailable("Container keeper is not running.")
        record = self.slot.load(owned.journal_path)
        record["state"] = "running"; self.slot.save(record)

    def exec_stage(self, owned, stage, cancelled):
        record = self.slot.load(owned.journal_path)
        stages = {"prepare", "check", "test"} | ({"build"} if record["profile"] == "vite-build-smoke-v1" else set())
        if stage not in stages: raise ValidationUnavailable("Unsupported fixed validation stage.")
        before = self.verify(owned)
        if before["State"].get("Running") is not True: raise ValidationUnavailable("Container keeper stopped.")
        result = self.call(["container", "exec", "--user", "10001:10001", owned.container_id,
                            "/opt/agenthub/control", stage], cancelled=cancelled, timeout=60,
                           output_limit=12000, strict_limit=False)
        after = self.verify(owned)
        reason = execution_reason(result, after["State"])
        if after["State"].get("Running") is not True and result["status"] == "passed":
            result["status"], reason = "failed", "keeper_stopped"
        log = (result["stdout"] + result["stderr"])[:12000].decode("utf-8", errors="replace")
        log = log.replace(record["inputDir"], "<validation-input>")
        log = log.encode("utf-8")[:12000].decode("utf-8", errors="ignore")
        return {"kind": stage, "command": "fixed docker " + stage, "argv": ["fixed-profile", stage],
                "status": result["status"], "exitCode": result["exitCode"], "durationMs": result["durationMs"],
                "log": log, "reasonCode": reason}

    def export_bytes(self, owned, cancelled):
        before = self.verify(owned)
        if before["State"].get("Running") is not True: raise ValidationUnavailable("Container keeper stopped.")
        record = self.slot.load(owned.journal_path)
        record["state"] = "exporting"; self.slot.save(record)
        result = self.call(["container", "exec", "--user", "10001:10001", owned.container_id,
                           "/opt/agenthub/control", "export"], cancelled=cancelled, timeout=60,
                           output_limit=MAX_TRANSPORT, strict_limit=True)
        after = self.verify(owned)
        if result["status"] != "passed" or after["State"].get("Running") is not True:
            raise ValidationUnavailable("Export unavailable: " + (execution_reason(result, after["State"]) or "keeper_stopped"))
        return result["stdout"]

    def matching_ids(self, operation):
        self.ensure_context()
        result = self.call(["container", "ls", "--all", "--quiet", "--no-trunc", "--filter",
                            "label=io.agenthub.validation.operation=" + operation], cleanup=True)
        if result["status"] != "passed": raise ValidationUnavailable("cleanup_required: discovery unavailable.")
        ids = result["stdout"].decode("ascii", errors="replace").splitlines()
        if len(ids) > 1 or any(not CID.fullmatch(value) for value in ids):
            raise ValidationUnavailable("cleanup_required: ambiguous container discovery.")
        return ids

    def cleanup(self, owned):
        try:
            value = self.verify(owned, cleanup=True)
            if value["State"].get("Running"):
                result = self.call(["container", "kill", owned.container_id], cleanup=True)
                if result["status"] != "passed": raise ValidationUnavailable("cleanup_required: kill unavailable.")
            self.verify(owned, cleanup=True)
            result = self.call(["container", "rm", "--force", owned.container_id], cleanup=True)
            if result["status"] != "passed" or self.matching_ids(owned.operation_id):
                raise ValidationUnavailable("cleanup_required: removal unconfirmed.")
            self.remove_private_state(owned.journal_path)
        except (OSError, ValueError, subprocess.SubprocessError):
            record = self.slot.load(owned.journal_path)
            record["state"] = "cleanup_required"; self.slot.save(record)
            raise

    def remove_private_state(self, journal_path):
        record = self.slot.load(journal_path)
        directory = self.slot.directory / record["operationId"]
        if directory.exists():
            assert_canonical_directory(directory)
            pending, count = [directory], 0
            while pending:
                path = pending.pop(); count += 1
                if count > 2048: raise ValidationUnavailable("cleanup_required: input cleanup budget.")
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                    raise ValidationUnavailable("cleanup_required: linked input directory.")
                if stat.S_ISDIR(info.st_mode): pending.extend(path.iterdir())
                elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValidationUnavailable("cleanup_required: invalid input file.")
                elif os.name == "nt":
                    # Only after exact ownership and disappearance checks: clear
                    # our snapshot's Windows read-only bit so it can be removed.
                    path.chmod(0o600)
            # Absolute target was verified inside the exact private slot above.
            shutil.rmtree(directory)
        journal_path.unlink()

    def cleanup_pending(self, operation):
        path = self.slot.journal_path(operation)
        if not path.exists(): return
        record = self.slot.load(path)
        if record["ownerPid"] != os.getpid() or record["ownerStart"] != process_identity(os.getpid()):
            raise ValidationUnavailable("cleanup_required: pending operation is not current-owned.")
        self.cleanup_record(path, record)

    def cleanup_record(self, path, record):
        self.slot.discard_interrupted_update(path)
        ids = self.matching_ids(record["operationId"])
        if not ids:
            if record["containerId"] is None and record["createAttempted"]:
                record["state"] = "cleanup_required"; self.slot.save(record)
                raise ValidationUnavailable("cleanup_required: container create outcome is still unknown.")
            self.remove_private_state(path); return
        if record["containerId"] is not None and ids != [record["containerId"]]:
            raise ValidationUnavailable("cleanup_required: discovered ID mismatch.")
        if record["containerId"] is None:
            record["containerId"] = ids[0]; self.slot.save(record)
        self.cleanup(OwnedContainer(ids[0], record["operationId"], record["contextName"], path))

    def recover(self):
        for path, record in self.slot.pending_journals():
            if not owner_reclaimable(record): raise ValidationUnavailable("cleanup_required: owner may still be active.")
            context = {k: record[k] for k in ("contextFingerprint", "daemonFingerprint", "endpoint")}
            previous = DockerRuntime(self.slot, record["contextName"], context, executable=self.executable)
            previous.cleanup_record(path, record)
