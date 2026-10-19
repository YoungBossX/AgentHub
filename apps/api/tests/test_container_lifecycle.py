import importlib
import json
from pathlib import Path
import subprocess
import sys
import threading

import pytest


def lifecycle(): return importlib.import_module("app.container_lifecycle")


def test_capacity_is_cross_process_and_cancellable(tmp_path, monkeypatch):
    module = lifecycle()
    monkeypatch.setattr(module, "state_root", lambda: tmp_path)
    code = """
import sys, threading
from pathlib import Path
from app import container_lifecycle as c
c.state_root = lambda: Path(sys.argv[1])
with c.acquire_validation_slot('a'*64, threading.Event()):
    print('locked', flush=True)
    sys.stdin.readline()
"""
    process = subprocess.Popen([sys.executable, "-c", code, str(tmp_path)], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == "locked"
        monkeypatch.setattr(module, "WAIT_SECONDS", 0.1)
        with pytest.raises(ValueError, match="capacity"):
            with module.acquire_validation_slot("a" * 64, threading.Event()): pytest.fail("capacity exceeded")
        cancelled = threading.Event(); cancelled.set()
        with pytest.raises(ValueError, match="cancelled"):
            with module.acquire_validation_slot("a" * 64, cancelled): pytest.fail("cancelled wait entered")
    finally:
        process.communicate("release\n", timeout=5)
    with module.acquire_validation_slot("a" * 64, threading.Event()) as slot:
        assert slot.directory.parent == tmp_path


def test_crashed_owner_releases_os_slot_but_requires_cleanup(tmp_path, monkeypatch):
    module = lifecycle()
    monkeypatch.setattr(module, "state_root", lambda: tmp_path)
    with module.acquire_validation_slot("a" * 64, threading.Event()) as slot:
        (slot.directory / ("b" * 32 + ".json")).write_text('{"untrusted":"unknown journal"}')
    with module.acquire_validation_slot("a" * 64, threading.Event()) as slot:
        with pytest.raises(ValueError, match="cleanup_required"):
            slot.pending_journals()


def test_reused_pid_or_foreign_labels_never_cleanup(monkeypatch):
    module = lifecycle()
    monkeypatch.setattr(module, "process_identity", lambda pid: "new-process")
    assert module.owner_reclaimable({"ownerPid": 123, "ownerStart": "old-process", "expiresAt": 0}) is False
    monkeypatch.setattr(module, "process_identity", lambda pid: None)
    assert module.owner_reclaimable({"ownerPid": 123, "ownerStart": "old-process", "expiresAt": 0}) is True


def test_current_owner_is_not_reclaimed_before_expiry():
    module = lifecycle()
    import os, time
    assert module.process_identity(os.getpid())
    assert not module.owner_reclaimable({"ownerPid": os.getpid(), "ownerStart": module.process_identity(os.getpid()),
                                        "expiresAt": time.time() + 3600})


def test_cleanup_crash_windows_with_matching_journal(tmp_path, monkeypatch):
    from container_fixtures import ControlledDocker, CONTEXT
    from app.container_runtime import DockerRuntime
    fake = ControlledDocker(monkeypatch, tmp_path)
    module = lifecycle()
    with module.acquire_validation_slot(CONTEXT["daemonFingerprint"], threading.Event()) as slot:
        worker, directory = fake.opened(slot)
        original_save = type(slot).save
        def interrupted_save(self, record):
            if record["state"] == "created": raise OSError("crash before ID persistence")
            return original_save(self, record)
        monkeypatch.setattr(type(slot), "save", interrupted_save)
        with pytest.raises(OSError): worker.create(fake.request, directory)
        assert len(fake.containers) == 1
        journal = slot.load(slot.journal_path(fake.request.execution.operation_id))
        assert journal["containerId"] is None
        monkeypatch.setattr(type(slot), "save", original_save)
        monkeypatch.setattr(module, "process_identity", lambda pid: None)
        DockerRuntime(slot, "local", CONTEXT, executable="/trusted/docker").recover()
        assert not fake.containers and list(slot.directory.iterdir()) == [slot.directory / "capacity.lock"]


@pytest.mark.parametrize("damage", ["label", "image", "mount", "privileged"])
def test_foreign_or_modified_container_never_receives_cleanup_mutations(tmp_path, monkeypatch, damage):
    from container_fixtures import ControlledDocker, CONTEXT
    fake = ControlledDocker(monkeypatch, tmp_path)
    with lifecycle().acquire_validation_slot(CONTEXT["daemonFingerprint"], threading.Event()) as slot:
        worker, directory = fake.opened(slot)
        owned = worker.create(fake.request, directory)
        value = fake.containers[owned.container_id]
        if damage == "label": value["Config"]["Labels"]["io.agenthub.validation.operation"] = "foreign"
        if damage == "image": value["Image"] = "sha256:" + "9" * 64
        if damage == "mount": value["Mounts"][0]["Source"] = "/foreign"
        if damage == "privileged": value["HostConfig"]["Privileged"] = True
        with pytest.raises(ValueError, match="cleanup_required"): worker.cleanup(owned)
        assert not any(c[:2] in [["container", "kill"], ["container", "rm"]] for c in fake.calls)
        assert slot.load(owned.journal_path)["state"] == "cleanup_required"


def test_context_drift_blocks_exec_or_cleanup(tmp_path, monkeypatch):
    from container_fixtures import ControlledDocker, CONTEXT
    fake = ControlledDocker(monkeypatch, tmp_path)
    with lifecycle().acquire_validation_slot(CONTEXT["daemonFingerprint"], threading.Event()) as slot:
        worker, directory = fake.opened(slot)
        owned = worker.create(fake.request, directory)
        worker.start(owned)
        fake.context["contextFingerprint"] = "0" * 64
        with pytest.raises(ValueError, match="context changed"): worker.exec_stage(owned, "test", threading.Event())
        with pytest.raises(ValueError, match="context changed"): worker.cleanup(owned)
        assert not any(c[:2] in [["container", "exec"], ["container", "kill"], ["container", "rm"]] for c in fake.calls)


def test_interrupted_update_recovers_from_valid_prior_journal(tmp_path, monkeypatch):
    from container_fixtures import ControlledDocker, CONTEXT
    fake = ControlledDocker(monkeypatch, tmp_path)
    module = lifecycle()
    with module.acquire_validation_slot(CONTEXT["daemonFingerprint"], threading.Event()) as slot:
        worker, directory = fake.opened(slot)
        owned = worker.create(fake.request, directory)
        pending = owned.journal_path.with_suffix(".pending")
        pending.write_bytes(b'{"incomplete":')
        pending.chmod(0o600)
        monkeypatch.setattr(module, "process_identity", lambda pid: None)
        worker.recover()
        assert not fake.containers
        assert list(slot.directory.iterdir()) == [slot.directory / "capacity.lock"]
