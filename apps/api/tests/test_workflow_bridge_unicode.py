"""The browser bridge consumes UTF-8 JSON regardless of the host pipe locale."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.mark.parametrize("name", ["ASCII contact", "张小明", "协作测试🙂"])
def test_bridge_preserves_utf8_contact_names_with_legacy_stdin(tmp_path, name):
    repo = Path(__file__).resolve().parents[3]
    project = tmp_path / "backend"
    shutil.copytree(repo / "apps/demo-api/app", project / "app", ignore=shutil.ignore_patterns("__pycache__"))
    data = tmp_path / "data"
    data.mkdir()
    # Isolated Python ignores PYTHONIOENCODING. Reproduce a legacy pipe locale
    # explicitly on every host, then execute the actual trusted bridge.
    launcher = "import runpy,sys; sys.stdin.reconfigure(encoding='gb18030'); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')"
    requests = [
        {"id": 1, "method": "POST", "path": "/contacts", "body": {"name": name, "email": "unicode@example.invalid"}},
        {"id": 2, "method": "GET", "path": "/contacts"},
    ]
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", launcher, str(repo / "scripts/workflow-api-bridge.py"), str(project), str(data)],
        input="".join(json.dumps(item, ensure_ascii=False) + "\n" for item in requests).encode("utf-8"),
        capture_output=True, timeout=25,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")[-1500:]
    responses = [json.loads(line) for line in result.stdout.decode("utf-8").splitlines()]
    assert responses[0] == {"ready": True}
    assert responses[1]["status"] == 201
    assert responses[1]["body"]["name"] == name
    assert responses[2]["status"] == 200
    assert any(contact["name"] == name for contact in responses[2]["body"])
