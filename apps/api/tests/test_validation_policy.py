import importlib
import importlib.metadata
import shutil
import subprocess
from dataclasses import FrozenInstanceError

import pytest

from app.config import get_settings
from app.worktrees import repo_root


@pytest.fixture(autouse=True)
def fresh_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def policy():
    return importlib.import_module("app.validation_policy")


def backend_tree(tmp_path):
    root = tmp_path / "source"
    shutil.copytree(repo_root() / "apps/demo-api", root / "apps/demo-api",
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    return root


def test_native_without_docker_never_spawns_cli(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Native policy must never probe Docker")
    monkeypatch.delenv("AGENTHUB_VALIDATION_BACKEND", raising=False)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    p = policy()
    snapshot = importlib.import_module("app.validation_inputs").capture_profile_inputs(
        backend_tree(tmp_path), "fastapi-contract-v1")
    identity = p.ValidationIdentity("run", "adapter", "attempt", "f" * 64)
    binding = p.bind_execution(snapshot, identity, p.resolve_backend_settings())
    assert binding.backend == "native" and binding.image is None
    assert binding.policy_fingerprint and binding.operation_id


@pytest.mark.parametrize("backend", ["", "Docker", "auto", "typo"])
def test_invalid_backend_is_not_native(backend, monkeypatch):
    monkeypatch.setenv("AGENTHUB_VALIDATION_BACKEND", backend)
    with pytest.raises(ValueError):
        policy().resolve_backend_settings()


@pytest.mark.parametrize("image", ["node:22", "sha256:abc", "a" * 64, "sha256:" + "G" * 64])
def test_mutable_or_malformed_image_is_not_an_execution_binding(image, tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTHUB_VALIDATION_BACKEND", "docker")
    monkeypatch.setenv("AGENTHUB_VALIDATION_DOCKER_CONTEXT", "local-test")
    monkeypatch.setenv("AGENTHUB_VALIDATION_BACKEND_IMAGE_ID", image)
    p = policy()
    snapshot = importlib.import_module("app.validation_inputs").capture_profile_inputs(
        backend_tree(tmp_path), "fastapi-contract-v1")
    with pytest.raises(ValueError):
        p.bind_execution(snapshot, p.ValidationIdentity("r", "a", "e", "f" * 64), p.resolve_backend_settings())


def test_docker_requires_explicit_context_before_execution(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTHUB_VALIDATION_BACKEND", "docker")
    monkeypatch.delenv("AGENTHUB_VALIDATION_DOCKER_CONTEXT", raising=False)
    monkeypatch.setenv("AGENTHUB_VALIDATION_BACKEND_IMAGE_ID", "sha256:" + "a" * 64)
    p = policy()
    snapshot = importlib.import_module("app.validation_inputs").capture_profile_inputs(
        backend_tree(tmp_path), "fastapi-contract-v1")
    with pytest.raises(ValueError, match="context"):
        p.bind_execution(snapshot, p.ValidationIdentity("r", "a", "e", "f" * 64), p.resolve_backend_settings())


def test_docker_capture_does_not_require_host_node_or_host_python_package_metadata(tmp_path, monkeypatch):
    root = backend_tree(tmp_path)
    def forbidden(*args, **kwargs):
        pytest.fail("Pure input capture cannot depend on host runtime availability")
    monkeypatch.setattr(importlib.metadata, "version", forbidden)
    monkeypatch.setattr(shutil, "which", forbidden)
    capture = importlib.import_module("app.validation_inputs").capture_profile_inputs
    backend = capture(root, "fastapi-contract-v1")
    assert backend.target_id == "demo-backend"
    assert "apps/demo-api/app/main.py" in backend.contents
    project = root / "apps/demo"
    shutil.copytree(repo_root() / "apps/demo", project,
                    ignore=shutil.ignore_patterns("node_modules", "dist"))
    for name in ("package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml"):
        shutil.copyfile(repo_root() / name, root / name)
    frontend = capture(root, "vite-build-smoke-v1")
    assert frontend.target_id == "demo-frontend"
    assert "pnpm-lock.yaml" in frontend.files and "pnpm-lock.yaml" not in frontend.contents


def test_snapshot_defensively_copies_and_freezes_source():
    p = policy()
    contents, files, inputs = {"a": b"original"}, {"a": "hash"}, {"policy": "frozen"}
    snapshot = p.SourceSnapshot("demo-backend", "fastapi-contract-v1", files, contents, "source", inputs)
    contents["a"] = b"changed"
    files.clear()
    inputs.clear()
    assert snapshot.contents["a"] == b"original" and snapshot.files["a"] == "hash"
    assert snapshot.policy_inputs["policy"] == "frozen"
    with pytest.raises(TypeError):
        snapshot.contents["new"] = b"bad"
    with pytest.raises(FrozenInstanceError):
        snapshot.profile = "other"


@pytest.mark.parametrize("mutation", ["secret", "hardlink", "native_module"])
def test_pure_capture_keeps_existing_backend_input_boundary(tmp_path, mutation):
    import os
    root = backend_tree(tmp_path)
    app = root / "apps/demo-api/app"
    if mutation == "secret": (app / ".env").write_text("SECRET=hidden")
    if mutation == "hardlink": os.link(app / "main.py", app / "alias.py")
    if mutation == "native_module": (app / "plugin.so").write_bytes(b"untrusted")
    capture = importlib.import_module("app.validation_inputs").capture_profile_inputs
    with pytest.raises((ValueError, OSError)):
        capture(root, "fastapi-contract-v1")
