import importlib
import json
from pathlib import Path
import subprocess

import pytest

from app.validation_policy import BACKEND_PROFILE, FRONTEND_PROFILE, platform_root
from app.config import get_settings


@pytest.fixture(autouse=True)
def isolated_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def module():
    return importlib.import_module("app.sandbox_prepare")


@pytest.mark.parametrize("profile", [FRONTEND_PROFILE, BACKEND_PROFILE])
def test_build_context_contains_only_trusted_inputs(tmp_path, profile):
    destination = tmp_path / "context"
    manifest = module().build_context(destination, profile)
    paths = {p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()}
    assert paths == set(manifest)
    assert any(name.endswith("Dockerfile") for name in paths)
    assert any(name.startswith("scripts/demo-") for name in paths)
    assert all(not any(part in {".git", "node_modules", "data", "src", "app", "dist"}
                       for part in Path(name).parts) for name in paths)
    assert all(not p.is_symlink() for p in destination.rglob("*"))


@pytest.mark.parametrize("case", ["existing", "managed", "relative", "linked_parent"])
def test_prepare_refuses_existing_or_managed_output(tmp_path, case):
    output = tmp_path / "new"
    if case == "existing": output.mkdir()
    if case == "managed": output = platform_root() / "must-not-create-sandbox-output"
    if case == "relative": output = Path("relative-output")
    if case == "linked_parent":
        link = tmp_path / "linked"
        link.symlink_to(tmp_path, target_is_directory=True)
        output = link / "new"
    with pytest.raises(ValueError):
        module().prepare_images(output)
    if case != "existing": assert not output.exists()


def test_prepare_uses_private_endpoint_and_minimal_context(tmp_path, monkeypatch):
    p = module()
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-inherit")
    monkeypatch.setenv("AGENTHUB_VALIDATION_DOCKER_CONTEXT", "local-test")
    monkeypatch.setattr(p, "inspect_context", lambda *args: {"contextFingerprint": "c" * 64,
                                                           "endpoint": "unix:///var/run/docker.sock"})
    monkeypatch.setattr(p.shutil, "which", lambda _: "/trusted/docker")
    ids = {FRONTEND_PROFILE: "sha256:" + "a" * 64, BACKEND_PROFILE: "sha256:" + "b" * 64}
    seen = []
    def run(argv, cancelled, **kwargs):
        assert argv[1] == "--config" and argv[3:5] == ["--host", "unix:///var/run/docker.sock"]
        assert json.loads((Path(argv[2]) / "config.json").read_text()) == {}
        # Explicit BuildKit supports the controller COPY --chmod instructions;
        # --load makes the resulting immutable ID inspectable on this daemon.
        assert argv[5:7] == ["buildx", "build"]
        assert "--load" in argv
        context = Path(argv[-1])
        paths = [p.relative_to(context).as_posix() for p in context.rglob("*") if p.is_file()]
        assert not any("src/" in path or ".env" in path or "main.py" in path for path in paths)
        profile = FRONTEND_PROFILE if "frontend.Dockerfile" in argv[argv.index("--file") + 1] else BACKEND_PROFILE
        Path(argv[argv.index("--iidfile") + 1]).write_text(ids[profile], encoding="utf-8")
        seen.append(profile)
        return {"status": "passed", "exitCode": 0, "stdout": b"build complete", "stderr": b"", "durationMs": 1}
    monkeypatch.setattr(p, "run_cli", run)
    monkeypatch.setattr(p, "inspect_built_image", lambda exe, context, image_id, profile, recipe, **kwargs: {
        "imageId": image_id, "recipeFingerprint": recipe, "platform": "linux/amd64", "contextName": context})
    output = tmp_path / "operator-receipt"
    result = p.prepare_images(output)
    assert set(seen) == {FRONTEND_PROFILE, BACKEND_PROFILE}
    assert result["schemaVersion"] == "agenthub.container_images.v1"
    assert result["profiles"][FRONTEND_PROFILE]["imageId"] == ids[FRONTEND_PROFILE]
    assert result["profiles"][BACKEND_PROFILE]["imageId"] == ids[BACKEND_PROFILE]
    assert json.loads((output / "images.json").read_text(encoding="utf-8")) == result
    assert not (output / ".env").exists()


def test_image_binding_uses_built_id_not_tag(monkeypatch):
    p = module()
    def inspect(*args, **kwargs):
        return [{"Id": "sha256:" + "d" * 64, "Os": "linux", "Architecture": "amd64", "Config": {
            "User": "10001:10001", "Entrypoint": ["/opt/agenthub/control"], "Cmd": ["hold"],
            "Labels": {"io.agenthub.validation.profile": BACKEND_PROFILE,
                       "io.agenthub.validation.recipe": "c" * 64}}}]
    monkeypatch.setattr(p, "docker_json", inspect)
    with pytest.raises(ValueError):
        p.inspect_built_image("docker", "local", "sha256:" + "e" * 64, BACKEND_PROFILE, "c" * 64,
                              endpoint="unix:///var/run/docker.sock")


@pytest.mark.parametrize("outcome", ["failed", "timeout"])
def test_unsuccessful_build_retains_bounded_diagnostics_without_success_receipt(tmp_path, monkeypatch, outcome):
    p = module()
    monkeypatch.setenv("AGENTHUB_VALIDATION_DOCKER_CONTEXT", "local-test")
    monkeypatch.setattr(p, "inspect_context", lambda *args: {
        "contextFingerprint": "c" * 64, "endpoint": "unix:///var/run/docker.sock"})
    monkeypatch.setattr(p.shutil, "which", lambda _: "/trusted/docker")
    diagnostic = b"download stalled\n" + b"x" * 20000
    def legacy_run(argv, **kwargs):
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(argv, 900, output=diagnostic)
        return subprocess.CompletedProcess(argv, 1, diagnostic)
    monkeypatch.setattr(subprocess, "run", legacy_run)
    monkeypatch.setattr(p, "run_cli", lambda *args, **kwargs: {
        "status": outcome, "exitCode": None if outcome == "timeout" else 1,
        "stdout": b"", "stderr": diagnostic, "durationMs": 900000}, raising=False)
    output = tmp_path / "failed-preparation"
    with pytest.raises(ValueError):
        p.prepare_images(output)
    assert not (output / "images.json").exists()
    assert not (output / BACKEND_PROFILE).exists()
    assert (output / (FRONTEND_PROFILE + ".build.log")).read_bytes() == diagnostic[-12000:]


def test_host_dependency_symlink_is_never_mounted(tmp_path):
    # Source selection enumerates fixed files; the installed host dependency
    # junctions are intentionally present in the real development checkout.
    context = tmp_path / "context"
    module().build_context(context, FRONTEND_PROFILE)
    assert not (context / "node_modules").exists()
    assert not (context / "apps/demo/node_modules").exists()
