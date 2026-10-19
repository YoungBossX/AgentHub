"""Stateful Docker CLI boundary double; never an OS isolation qualification."""
import hashlib
import json
from dataclasses import replace
import threading

from app import container_lifecycle as lifecycle
from app import container_runtime as runtime
from app.validation_policy import RUNTIME_POLICY, SourceSnapshot
from test_container_runtime import request


CONTEXT = {"contextFingerprint": "a" * 64, "daemonFingerprint": "b" * 64,
           "endpoint": "unix:///var/run/docker.sock"}


def source_request():
    value = request()
    content = b"app = object()\n"
    path = "apps/demo-api/app/main.py"
    return replace(value, snapshot=SourceSnapshot("demo-backend", "fastapi-contract-v1",
        {path: hashlib.sha256(content).hexdigest()}, {path: content}, "f" * 64, {}))


class ControlledDocker:
    def __init__(self, monkeypatch, state_dir):
        self.request = source_request()
        self.calls, self.containers = [], {}
        self.mutate = None
        self.exit_code = 0
        self.cancel_after_stage = None
        self.context = dict(CONTEXT)
        monkeypatch.setattr(lifecycle, "state_root", lambda: state_dir)
        monkeypatch.setattr(runtime, "inspect_context", lambda *args: dict(self.context))
        monkeypatch.setattr(runtime, "run_cli", self.call)

    def response(self, value=b"", code=0):
        if not isinstance(value, bytes): value = json.dumps(value).encode()
        return {"status": "passed" if code == 0 else "failed", "exitCode": code,
                "stdout": value, "stderr": b"", "durationMs": 1}

    def call(self, argv, cancelled, **kwargs):
        assert argv[0:2] == ["/trusted/docker", "--config"]
        from pathlib import Path
        assert json.loads((Path(argv[2]) / "config.json").read_text()) == {}
        assert argv[3:5] == ["--host", CONTEXT["endpoint"]]
        self.calls.append(argv[5:])
        command = argv[5:]
        assert 0 < kwargs["timeout"] <= 60
        if command[:2] == ["image", "inspect"]:
            image = self.request.execution.image
            return self.response([{"Id": image.image_id, "Os": "linux", "Architecture": "amd64", "Config": {
                "User": "10001:10001", "Entrypoint": ["/opt/agenthub/control"], "Cmd": ["hold"], "Env": [],
                "Labels": {"io.agenthub.validation.profile": self.request.snapshot.profile,
                           "io.agenthub.validation.recipe": image.recipe_fingerprint}}}])
        if command[:2] == ["container", "create"]:
            labels = dict(command[i + 1].split("=", 1) for i, v in enumerate(command) if v == "--label")
            source = command[command.index("--mount") + 1].split("source=", 1)[1].split(",destination=", 1)[0]
            value = {"Id": "e" * 64, "Image": command[-2], "Config": {"User": "10001:10001", "Labels": labels,
                "Entrypoint": ["/opt/agenthub/control"], "Cmd": ["hold"],
                "Env": [k + "=" + v for k, v in RUNTIME_POLICY["environment"].items()]},
                "HostConfig": {"ReadonlyRootfs": True, "Init": True, "NetworkMode": "none", "Privileged": False,
                    "CapAdd": [], "CapDrop": ["ALL"], "SecurityOpt": ["no-new-privileges"],
                    "Memory": 1073741824, "MemorySwap": 1073741824, "NanoCpus": 1000000000, "PidsLimit": 128,
                    "PidMode": "", "UTSMode": "", "IpcMode": "private", "CgroupnsMode": "private",
                    "Devices": [], "DeviceRequests": [], "PortBindings": {}, "ExtraHosts": [], "VolumesFrom": [],
                    "Binds": [], "AutoRemove": False, "LogConfig": {"Type": "none", "Config": {}},
                    "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0}, "Tmpfs": {
                        "/work": "rw,nosuid,nodev,noexec,size=536870912,uid=10001,gid=10001,mode=0700",
                        "/tmp": "rw,nosuid,nodev,noexec,size=67108864,uid=10001,gid=10001,mode=0700"}},
                "Mounts": [{"Type": "bind", "Source": source, "Destination": "/input", "RW": False}],
                "State": {"Running": False, "OOMKilled": False, "Status": "created", "ExitCode": 0}}
            self.containers[value["Id"]] = value
            return self.response((value["Id"] + "\n").encode())
        if command[:2] == ["container", "inspect"]:
            value = self.containers.get(command[2])
            return self.response([value]) if value else self.response(b"not found", 1)
        if command[:2] == ["container", "ls"]:
            assert command[2:6] == ["--all", "--quiet", "--no-trunc", "--filter"]
            key, value = command[6].removeprefix("label=").split("=", 1)
            ids = [cid for cid, item in self.containers.items() if item["Config"]["Labels"].get(key) == value]
            return self.response("\n".join(ids).encode())
        if command[:2] == ["container", "start"]:
            self.containers[command[2]]["State"].update(Running=True, Status="running")
            return self.response(command[2].encode())
        if command[:2] == ["container", "exec"]:
            assert command[2:4] == ["--user", "10001:10001"]
            stage = command[-1]
            if self.mutate: self.mutate(self.containers[command[4]])
            if stage == self.cancel_after_stage: cancelled.set()
            if cancelled.is_set(): return {**self.response(b"", 1), "status": "cancelled"}
            if stage == "export":
                return self.response({"schemaVersion": "agenthub.container_export.v1",
                    "sourceFingerprint": self.request.snapshot.source_fingerprint,
                    "sourceFiles": dict(self.request.snapshot.files), "files": []})
            if stage in {"check", "test"} and self.exit_code == 0:
                from app.backend_validation import CHECKS
                return self.response(("AGENTHUB_BACKEND_RESULT=" + json.dumps({"schemaVersion": "agenthub.backend_contract.v2",
                    "stage": stage, "checks": [{"id": name, "status": "passed"} for name in CHECKS[stage]], "error": None})).encode())
            return self.response(b"fixed stage", self.exit_code)
        if command[:2] == ["container", "kill"]:
            self.containers[command[2]]["State"].update(Running=False, Status="exited", ExitCode=137)
            return self.response(command[2].encode())
        if command[:3] == ["container", "rm", "--force"]:
            del self.containers[command[3]]
            return self.response(command[3].encode())
        raise AssertionError(f"Unapproved Docker operation: {command}")

    def opened(self, slot):
        from app.docker_validation import write_snapshot
        worker = runtime.DockerRuntime(slot, "local", CONTEXT, executable="/trusted/docker")
        directory = slot.directory / self.request.execution.operation_id / "input"
        write_snapshot(directory, self.request)
        return worker, directory
