import importlib
from pathlib import Path
import sys
import threading
import time

import pytest


@pytest.mark.parametrize("runner", ["native", "docker_client"])
def test_descendant_is_stopped_even_when_its_launcher_already_exited(tmp_path, runner):
    marker = tmp_path / "orphan-wrote"
    child = f"import time; from pathlib import Path; time.sleep(1); Path({str(marker)!r}).write_text('bad')"
    parent = f"import subprocess,sys; subprocess.Popen([sys.executable,'-c',{child!r}])"
    if runner == "native":
        from app.automatic_validation import run_command, validation_environment
        result = run_command([sys.executable, "-c", parent], tmp_path, validation_environment(), threading.Event(), timeout=3)
    else:
        from app.container_runtime import run_cli
        result = run_cli([sys.executable, "-c", parent], threading.Event(), timeout=3)
    time.sleep(1.1)
    assert result["status"] == "passed"
    assert not marker.exists()
