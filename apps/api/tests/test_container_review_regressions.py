"""Review regressions at the Docker CLI boundary; no daemon is contacted."""
import json
from pathlib import Path
import subprocess
import threading

import pytest

from app import container_lifecycle, container_runtime, sandbox_cli
from container_fixtures import CONTEXT, ControlledDocker


ENDPOINT = "unix:///var/run/docker.sock"


def test_context_resolution_pins_endpoint_before_any_daemon_query(monkeypatch):
    seen = []
    def run(argv, **kwargs):
        seen.append(argv)
        if "context" in argv:
            value = [{"Name": "local", "Endpoints": {"docker": {"Host": ENDPOINT}}}]
        elif "version" in argv:
            value = {}
        else:
            value = {"ID": "local-daemon", "OSType": "linux", "Architecture": "amd64",
                     "MemoryLimit": True, "SwapLimit": True, "PidsLimit": True,
                     "SecurityOptions": ["name=seccomp,profile=builtin"]}
        return subprocess.CompletedProcess(argv, 0, json.dumps(value).encode(), b"")
    monkeypatch.setattr(sandbox_cli.subprocess, "run", run)
    binding = sandbox_cli.inspect_context("/trusted/docker", "local")
    assert binding["endpoint"] == ENDPOINT
    for argv in seen[1:]:
        assert "--context" not in argv
        assert argv[argv.index("--host") + 1] == ENDPOINT


def test_last_moment_context_change_cannot_redirect_runtime_call(tmp_path, monkeypatch):
    fake = ControlledDocker(monkeypatch, tmp_path)
    captured = []
    def call(argv, cancelled, **kwargs):
        # Simulate the named context changing AFTER ensure_context returned.
        fake.context["endpoint"] = "ssh://untrusted.example"
        captured.append(argv)
        return fake.response()
    monkeypatch.setattr(container_runtime, "run_cli", call)
    with container_lifecycle.acquire_validation_slot(CONTEXT["daemonFingerprint"], threading.Event()) as slot:
        worker, _ = fake.opened(slot)
        worker.ensure_context()
        worker.call(["container", "ls"])
    assert "--context" not in captured[0]
    assert captured[0][captured[0].index("--host") + 1] == ENDPOINT


def test_runtime_cli_uses_empty_private_config_instead_of_user_proxies(tmp_path, monkeypatch):
    user = tmp_path / "fake-home"
    (user / ".docker").mkdir(parents=True)
    user_config = {"proxies": {"default": {"httpProxy": "http://fake-user:fake-password@proxy.invalid:8080"}},
                   "auths": {"registry.invalid": {"auth": "synthetic-only"}}}
    (user / ".docker/config.json").write_text(json.dumps(user_config), encoding="utf-8")
    monkeypatch.setenv("HOME", str(user))
    monkeypatch.setenv("USERPROFILE", str(user))
    fake = ControlledDocker(monkeypatch, tmp_path / "state")
    selected = []
    def call(argv, cancelled, **kwargs):
        directory = Path(argv[argv.index("--config") + 1]) if "--config" in argv else user / ".docker"
        selected.append(directory)
        assert directory != user / ".docker"
        assert json.loads((directory / "config.json").read_text(encoding="utf-8")) == {}
        return fake.response()
    monkeypatch.setattr(container_runtime, "run_cli", call)
    with container_lifecycle.acquire_validation_slot(CONTEXT["daemonFingerprint"], threading.Event()) as slot:
        worker = container_runtime.DockerRuntime(slot, "local", CONTEXT, executable="/trusted/docker")
        worker.call(["container", "ls"])
    assert selected and all(not p.exists() for p in selected)
    assert json.loads((user / ".docker/config.json").read_text(encoding="utf-8")) == user_config


@pytest.mark.parametrize("extra", ["HTTP_PROXY=http://fake:secret@proxy.invalid", "AGENTHUB_SECRET=synthetic"])
def test_unexpected_container_environment_is_refused_before_start(tmp_path, monkeypatch, extra):
    fake = ControlledDocker(monkeypatch, tmp_path)
    with container_lifecycle.acquire_validation_slot(CONTEXT["daemonFingerprint"], threading.Event()) as slot:
        worker, directory = fake.opened(slot)
        owned = worker.create(fake.request, directory)
        fake.containers[owned.container_id]["Config"]["Env"].append(extra)
        with pytest.raises(ValueError, match="environment"):
            worker.start(owned)
        assert not any(c[:2] == ["container", "start"] for c in fake.calls)


def test_unknown_create_retains_journal_until_delayed_container_is_discovered(tmp_path, monkeypatch):
    fake = ControlledDocker(monkeypatch, tmp_path)
    original_call = fake.call
    delayed = {}
    def call(argv, cancelled, **kwargs):
        if "create" in argv:
            result = original_call(argv, cancelled, **kwargs)
            delayed.update(fake.containers)
            fake.containers.clear()  # daemon has not made the object visible yet
            return {**result, "status": "timeout", "stdout": b""}
        return original_call(argv, cancelled, **kwargs)
    monkeypatch.setattr(container_runtime, "run_cli", call)
    with container_lifecycle.acquire_validation_slot(CONTEXT["daemonFingerprint"], threading.Event()) as slot:
        worker, directory = fake.opened(slot)
        with pytest.raises(ValueError): worker.create(fake.request, directory)
        path = slot.journal_path(fake.request.execution.operation_id)
        with pytest.raises(ValueError, match="cleanup_required"):
            worker.cleanup_pending(fake.request.execution.operation_id)
        assert path.exists() and directory.exists()
        assert slot.load(path)["state"] == "cleanup_required"
        fake.containers.update(delayed)
        monkeypatch.setattr(container_runtime, "owner_reclaimable", lambda _: True)
        worker.recover()
        assert not fake.containers and not path.exists() and not directory.exists()
