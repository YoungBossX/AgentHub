import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

from app.validation_policy import platform_root


@pytest.mark.parametrize("args", [["shell"], ["build"], ["test", "/arbitrary/path"], ["export", "../escape"]])
def test_control_rejects_arbitrary_stage_or_path(args):
    path = platform_root() / "containers/validation/backend-control.py"
    result = subprocess.run([sys.executable, "-I", "-B", str(path), *args], capture_output=True, timeout=5)
    assert result.returncode == 2, result.stderr.decode(errors="replace")
    assert b"unsupported_stage" in result.stderr


def load_control():
    path = platform_root() / "containers/validation/backend-control.py"
    spec = importlib.util.spec_from_file_location("trusted_backend_control", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backend_control_uses_only_fixed_trusted_harness():
    command = load_control().stage_command("test")
    assert command == ["/usr/local/bin/python", "-I", "-B", "/opt/agenthub/scripts/demo-backend-check.py",
                       "test", "/work/apps/demo-api", "/work/data"]


@pytest.mark.parametrize("path", ["../bad", "apps/demo-api/.env", "C:/bad", "apps/demo-api/a\\b",
                                  "apps/demo-api/CON.py", "apps/demo-api/a:b", "apps/demo-api/a."])
def test_backend_manifest_refuses_unportable_or_protected_input(path):
    with pytest.raises(ValueError):
        load_control().validate_manifest({"schemaVersion": "agenthub.container_input.v1",
            "profile": "fastapi-contract-v1", "sourceFingerprint": "f" * 64, "sourceFiles": {path: "a" * 64}})
