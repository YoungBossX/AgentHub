import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


FRONTEND = "vite-build-smoke-v1"
BACKEND = "fastapi-contract-v1"
IMAGE_IDS = {FRONTEND: "sha256:" + "a" * 64, BACKEND: "sha256:" + "b" * 64}


def cli():
    return importlib.import_module("app.sandbox_cli")


def fake_cli(monkeypatch, *, endpoint="unix:///var/run/docker.sock", os_type="linux", arch="x86_64", bad_image=False):
    module = cli()
    calls = []
    monkeypatch.setattr(module.shutil, "which", lambda name: "/trusted/docker")
    monkeypatch.setattr(module, "recipe_fingerprint", lambda profile: "c" * 64)
    def run(argv, **kwargs):
        calls.append(argv)
        assert argv[0] == "/trusted/docker" and kwargs["shell"] is False and kwargs["timeout"] == 10
        assert not any(k.startswith(("AGENTHUB_", "OPENAI_", "ANTHROPIC_", "DOCKER_")) for k in kwargs["env"])
        if "context" in argv:
            assert argv[1:3] == ["--context", "local-test"]
            command = argv[3:]
        else:
            assert argv[1] == "--config" and argv[3:5] == ["--host", endpoint]
            assert json.loads((Path(argv[2]) / "config.json").read_text()) == {}
            command = argv[5:]
        if command == ["context", "inspect", "local-test"]:
            value = [{"Name": "local-test", "Metadata": {}, "Endpoints": {"docker": {
                "Host": endpoint, "SkipTLSVerify": False}}, "TLSMaterial": {}, "Storage": {}}]
        elif command == ["version", "--format", "{{json .}}"]:
            value = {"Client": {"Version": "28.0.0", "ApiVersion": "1.48", "Os": "linux", "Arch": "amd64"},
                     "Server": {"Version": "28.0.0", "ApiVersion": "1.48", "Os": "linux", "Arch": "amd64"}}
        elif command == ["info", "--format", "{{json .}}"]:
            value = {"ID": "trusted-local-daemon", "OSType": os_type, "Architecture": arch,
                     "SecurityOptions": ["name=seccomp,profile=builtin"], "CgroupVersion": "2",
                     "MemoryLimit": True, "SwapLimit": True, "PidsLimit": True, "NCPU": 4, "MemTotal": 8 * 1024**3}
        elif command[:2] == ["image", "inspect"] and command[2] in IMAGE_IDS.values():
            image_id = command[2]
            profile = FRONTEND if image_id == IMAGE_IDS[FRONTEND] else BACKEND
            value = [{"Id": image_id, "Os": "linux", "Architecture": "amd64", "Config": {
                "User": "10001:10001", "Labels": {"io.agenthub.validation.profile": profile,
                "io.agenthub.validation.recipe": "d" * 64 if bad_image else "c" * 64},
                "Entrypoint": ["/opt/agenthub/control"], "Cmd": ["hold"], "Env": []}}]
        else:
            pytest.fail(f"Doctor attempted non-read-only/unknown operation: {command}")
        return subprocess.CompletedProcess(argv, 0, json.dumps(value).encode(), b"")
    monkeypatch.setattr(module.subprocess, "run", run)
    return calls


@pytest.mark.parametrize("endpoint", ["unix:///var/run/docker.sock", "npipe:////./pipe/dockerDesktopLinuxEngine"])
def test_metadata_ready_is_not_runtime_isolation_verified(monkeypatch, endpoint):
    fake_cli(monkeypatch, endpoint=endpoint)
    report = cli().doctor(context_name="local-test", image_ids=IMAGE_IDS)
    assert report["schemaVersion"] == "agenthub.container_doctor.v1"
    assert report["status"] == "metadata_ready" and report["reasonCodes"] == []
    assert report["runtimeIsolationVerified"] is False
    assert all(set(c) == {"id", "status"} and c["status"] == "passed" for c in report["checks"])


@pytest.mark.parametrize("endpoint,override", [
    ("tcp://127.0.0.1:2375", None), ("ssh://localhost", None),
    ("unix:///var/run/docker.sock", "DOCKER_HOST"), ("unix:///var/run/docker.sock", "DOCKER_API_VERSION"),
    ("unix:///var/run/docker.sock", "DOCKER_CONTEXT"), ("unix://remote/var/run/docker.sock", None),
])
def test_remote_or_overridden_context_refused(monkeypatch, endpoint, override):
    calls = fake_cli(monkeypatch, endpoint=endpoint)
    if override: monkeypatch.setenv(override, "unsafe")
    report = cli().doctor(context_name="local-test", image_ids=IMAGE_IDS)
    assert report["status"] == "unsupported"
    assert "context_refused" in report["reasonCodes"]
    assert len(calls) <= 1  # no daemon or image query after an unsafe context


@pytest.mark.parametrize("os_type,arch", [("windows", "x86_64"), ("linux", "arm64"), ("other", "mystery")])
def test_unsupported_platform_cannot_claim_ready(monkeypatch, os_type, arch):
    fake_cli(monkeypatch, os_type=os_type, arch=arch)
    report = cli().doctor(context_name="local-test", image_ids=IMAGE_IDS)
    assert report["status"] == "unsupported" and "platform_unsupported" in report["reasonCodes"]


def test_unapproved_image_cannot_claim_ready(monkeypatch):
    fake_cli(monkeypatch, bad_image=True)
    report = cli().doctor(context_name="local-test", image_ids=IMAGE_IDS)
    assert report["status"] == "unsupported" and "image_refused" in report["reasonCodes"]


def test_missing_context_or_images_never_queries_daemon(monkeypatch):
    calls = fake_cli(monkeypatch)
    assert cli().doctor(context_name=None, image_ids=IMAGE_IDS)["status"] == "unavailable"
    assert cli().doctor(context_name="local-test", image_ids={})["status"] == "unavailable"
    assert calls == []


def test_doctor_does_not_import_db_or_mutate_daemon(tmp_path):
    database = tmp_path / "must-not-exist.sqlite3"
    env = {k: v for k, v in os.environ.items() if not k.startswith("AGENTHUB_VALIDATION_")}
    env.update(AGENTHUB_DATABASE_URL="sqlite:///" + database.as_posix(), PYTHONIOENCODING="utf-8")
    code = """
import json, sys
from app.sandbox_cli import doctor, main
report = doctor(context_name=None, image_ids={})
assert 'app.db' not in sys.modules
print(json.dumps(report))
raise SystemExit(main(['doctor']))
"""
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, timeout=15)
    assert result.returncode == 1, result.stderr.decode(errors="replace")
    assert not database.exists()
    reports = [json.loads(line) for line in result.stdout.decode().splitlines()]
    assert len(reports) == 2 and all(r["status"] == "unavailable" for r in reports)
    assert all(r["runtimeIsolationVerified"] is False for r in reports)
