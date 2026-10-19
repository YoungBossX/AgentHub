import importlib
import threading
import subprocess
from dataclasses import replace
import hashlib

import pytest

from test_container_runtime import request


@pytest.mark.parametrize("paths", [
    ("apps/demo-api/App/a.py", "apps/demo-api/app/b.py"),
    ("apps/demo-api/app/Routes/a.py", "apps/demo-api/app/routes/b.py"),
    ("apps/demo-api/app/a.py", "apps/demo-api/app"),
    ("apps/demo-api/app", "apps/demo-api/app/a.py"),
])
def test_snapshot_rejects_ambiguous_tree_before_creating_input(tmp_path, paths):
    from app.docker_validation import write_snapshot
    from container_fixtures import source_request
    original = source_request()
    contents = {path: b"value = 1\n" for path in paths}
    checksums = {path: hashlib.sha256(raw).hexdigest() for path, raw in contents.items()}
    frozen = replace(original, snapshot=replace(original.snapshot, contents=contents, files=checksums))
    with pytest.raises(ValueError, match="collision"):
        write_snapshot(tmp_path / "operation/input", frozen)
    assert list(tmp_path.iterdir()) == []


def test_explicit_docker_unavailable_never_invokes_native_validation(tmp_path, monkeypatch):
    from app import automatic_validation, backend_validation
    def forbidden(*args, **kwargs): raise AssertionError("Unexpected native fallback")
    monkeypatch.setattr(automatic_validation, "validate_copy", forbidden)
    monkeypatch.setattr(backend_validation, "validate_backend_copy", forbidden)
    module = importlib.import_module("app.docker_validation")
    monkeypatch.setattr(module.shutil, "which", lambda _: None)
    result = module.DockerValidationBackend().execute(request(), threading.Event(), export_dir=tmp_path / "export")
    assert result.status == "unavailable" and result.commands == []
    assert result.execution["backend"] == "docker" and result.execution["commandsBackend"] == "not_run"


def test_unavailable_image_leaves_no_unjournaled_input(tmp_path, monkeypatch):
    from container_fixtures import ControlledDocker, CONTEXT
    from app import container_runtime
    from app.docker_validation import DockerValidationBackend
    fake = ControlledDocker(monkeypatch, tmp_path)
    module = importlib.import_module("app.docker_validation")
    monkeypatch.setattr(module.shutil, "which", lambda _: "/trusted/docker")
    def missing(*args): raise ValueError("image missing")
    monkeypatch.setattr(container_runtime.DockerRuntime, "check_image", missing)
    result = DockerValidationBackend().execute(fake.request, threading.Event(), export_dir=tmp_path / "export")
    assert result.status == "unavailable" and not fake.containers
    assert [p.name for p in (tmp_path / CONTEXT["daemonFingerprint"]).iterdir()] == ["capacity.lock"]


def test_fixed_backend_stages_export_and_cleanup_form_one_operation(tmp_path, monkeypatch):
    from container_fixtures import ControlledDocker, CONTEXT
    from app.docker_validation import DockerValidationBackend
    fake = ControlledDocker(monkeypatch, tmp_path)
    module = importlib.import_module("app.docker_validation")
    monkeypatch.setattr(module.shutil, "which", lambda _: "/trusted/docker")
    result = DockerValidationBackend().execute(fake.request, threading.Event(), export_dir=tmp_path / "export")
    assert result.status == "passed" and result.output_fingerprint
    assert [c["kind"] for c in result.commands] == ["check", "test"]
    assert result.execution["commandsBackend"] == "docker"
    assert [c[-1] for c in fake.calls if c[:2] == ["container", "exec"]] == ["prepare", "check", "test", "export"]
    assert not fake.containers
    assert [p.name for p in (tmp_path / CONTEXT["daemonFingerprint"]).iterdir()] == ["capacity.lock"]


def test_cancelled_exec_terminates_container_and_leaves_no_success(tmp_path, monkeypatch):
    from container_fixtures import ControlledDocker
    from app.docker_validation import DockerValidationBackend
    fake = ControlledDocker(monkeypatch, tmp_path)
    module = importlib.import_module("app.docker_validation")
    monkeypatch.setattr(module.shutil, "which", lambda _: "/trusted/docker")
    fake.cancel_after_stage = "check"
    result = DockerValidationBackend().execute(fake.request, threading.Event(), export_dir=tmp_path / "export")
    assert result.status == "cancelled" and not fake.containers
    assert any(c[:2] == ["container", "kill"] for c in fake.calls)
    assert not (tmp_path / "export").exists()


@pytest.mark.parametrize("error", [KeyError("OSType"), subprocess.TimeoutExpired("docker", 10)])
def test_bad_or_timed_out_daemon_metadata_is_structured_unavailable(tmp_path, monkeypatch, error):
    module = importlib.import_module("app.docker_validation")
    monkeypatch.setattr(module.shutil, "which", lambda _: "/trusted/docker")
    def unavailable(*args): raise error
    monkeypatch.setattr(module.DockerRuntime, "check_context", unavailable)
    result = module.DockerValidationBackend().execute(request(), threading.Event(), export_dir=tmp_path / "export")
    assert result.status == "unavailable" and result.commands == []
    assert result.execution["commandsBackend"] == "not_run"
