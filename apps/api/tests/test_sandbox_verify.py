import os
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

from app.validation_policy import platform_root


def test_forced_qualification_without_environment_fails_instead_of_skipping(tmp_path):
    report = tmp_path / "forced-results.xml"
    env = dict(os.environ)
    for name in ("FRONTEND_IMAGE_ID", "BACKEND_IMAGE_ID", "DOCKER_CONTEXT"):
        env.pop("AGENTHUB_VALIDATION_" + name, None)
    env["AGENTHUB_VALIDATION_DOCKER_CONTEXT"] = ""
    result = subprocess.run([shutil.which("bash") or "bash", "scripts/sandbox.sh", "verify", "-k", "required_environment_is_real",
                             "--junitxml", str(report)], cwd=platform_root(), env=env, capture_output=True, timeout=60,
                            shell=False)
    assert result.returncode != 0
    assert report.is_file(), result.stdout.decode(errors="replace") + result.stderr.decode(errors="replace")
    cases = ET.parse(report).findall(".//testcase")
    assert cases and not any(c.find("skipped") is not None for c in cases)
    assert any(c.find("failure") is not None or c.find("error") is not None for c in cases)
    assert "Required Docker environment is unavailable" in report.read_text(encoding="utf-8")
