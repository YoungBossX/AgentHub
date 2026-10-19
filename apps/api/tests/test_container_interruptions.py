"""Host process/journal recovery with a Docker boundary double, not OS isolation."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

from app import container_lifecycle, container_runtime
from app.container_runtime import run_cli as REAL_CLI
from app.docker_validation import DockerValidationBackend
from app.validation_process import start_process, stop_process
from container_fixtures import CONTEXT, ControlledDocker
from container_interruption_helpers import CREATE_RELAY


def wait_for_file(path, *, process=None, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists(): return
        if process is not None and process.poll() is not None:
            _, errors = process.communicate(timeout=5)
            pytest.fail("Interruption worker exited before reaching the running boundary: " + errors.decode(errors="replace"))
        time.sleep(.02)
    pytest.fail("Interruption worker did not reach the running boundary")


def assert_processes_exited(pids):
    deadline = time.monotonic() + 5
    while any(container_lifecycle.process_identity(pid) is not None for pid in pids) and time.monotonic() < deadline:
        time.sleep(.02)  # Windows Job termination includes an asynchronous redirector child exit.
    assert all(container_lifecycle.process_identity(pid) is None for pid in pids)


@pytest.mark.parametrize("stage", ["check", "export"])
def test_cancel_while_cli_is_running_cleans_only_owned_container(tmp_path, monkeypatch, stage):
    fake = ControlledDocker(monkeypatch, tmp_path / "state")
    monkeypatch.setattr("app.docker_validation.shutil.which", lambda _: "/trusted/docker")
    cancelled, entered = threading.Event(), tmp_path / "entered"
    original_cli = container_runtime.run_cli
    # ControlledDocker replaced run_cli above; keep its daemon responses, but
    # run a real, blocking host client at the selected boundary.
    real_cli = REAL_CLI
    foreign, foreign_before = {}, {}
    client_finished = tmp_path / "client-finished"
    def call(argv, event, **kwargs):
        command = argv[5:]
        if command[:2] == ["container", "exec"] and command[-1] == stage:
            foreign.update(deepcopy(fake.containers["e" * 64]))
            foreign["Id"] = "9" * 64
            foreign["Config"]["Labels"]["io.agenthub.validation.operation"] = "8" * 32
            fake.containers[foreign["Id"]] = foreign
            foreign_before.update(deepcopy(foreign))
            child = f"import time; from pathlib import Path; time.sleep(30); Path({str(client_finished)!r}).touch()"
            code = ("from pathlib import Path; import time,subprocess,sys,os,json; "
                    f"child=subprocess.Popen([sys.executable,'-c',{child!r}]); "
                    f"marker=Path({str(entered)!r}); pending=marker.with_suffix('.pending'); "
                    "pending.write_text(json.dumps([os.getpid(),child.pid])); pending.replace(marker); time.sleep(30)")
            return real_cli([sys.executable, "-c", code], event, **kwargs)
        return original_cli(argv, event, **kwargs)
    monkeypatch.setattr(container_runtime, "run_cli", call)
    results, errors = [], []
    def execute():
        try: results.append(DockerValidationBackend().execute(fake.request, cancelled, export_dir=tmp_path / "export"))
        except BaseException as exc: errors.append(exc)
    worker = threading.Thread(target=execute)
    worker.start()
    try:
        wait_for_file(entered)
        assert worker.is_alive() and not cancelled.is_set()
        cancelled.set()
        worker.join(timeout=10)
        assert not worker.is_alive() and not errors
        assert results[0].status == "cancelled" and results[0].output_fingerprint is None
        assert not (tmp_path / "export").exists() and not client_finished.exists()
        assert_processes_exited(json.loads(entered.read_text()))
        assert fake.containers == {"9" * 64: foreign_before}
        slot = tmp_path / "state" / CONTEXT["daemonFingerprint"]
        assert [p.name for p in slot.iterdir()] == ["capacity.lock"]
    finally:
        cancelled.set(); worker.join(timeout=10)


def test_qualification_create_relay_keeps_response_inflight_until_released(tmp_path):
    entered, released = tmp_path / "created", tmp_path / "release"
    argv = [sys.executable, "-c", "print('" + "e" * 64 + "')"]
    worker = start_process([sys.executable, "-c", CREATE_RELAY, json.dumps(argv), str(entered), str(released)],
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        wait_for_file(entered, process=worker)
        assert entered.read_bytes().strip() == b"e" * 64 and worker.poll() is None
        released.touch()
        stdout, stderr = worker.communicate(timeout=5)
        assert worker.returncode == 0 and stdout.strip() == b"e" * 64 and not stderr
    finally: stop_process(worker)


@pytest.mark.parametrize("window", ["create", "check", "export"])
def test_killed_worker_releases_slot_and_recovers_inflight_journal(tmp_path, monkeypatch, window):
    state = tmp_path / "state"
    entered, containers = tmp_path / "entered", tmp_path / "containers.json"
    code = '''
import json,sys,threading,time
from pathlib import Path
sys.path.insert(0,sys.argv[5])
import pytest
from app import container_runtime as runtime
from app import container_lifecycle as lifecycle
from app.docker_validation import DockerValidationBackend
from container_fixtures import ControlledDocker
state, entered, stored = map(Path,sys.argv[1:4])
window=sys.argv[4]
patch=pytest.MonkeyPatch()
fake=ControlledDocker(patch,state)
original=runtime.run_cli
def call(argv,cancelled,**kwargs):
    command=argv[5:]
    selected=(command[:2]==['container','create'] if window=='create' else
              command[:2]==['container','exec'] and command[-1]==window)
    if selected:
        if window=='create': original(argv,cancelled,**kwargs)
        stored.write_text(json.dumps(fake.containers),encoding='utf-8')
        entered.write_text('in_flight',encoding='utf-8')
        while True: time.sleep(.1)
    return original(argv,cancelled,**kwargs)
patch.setattr(runtime,'run_cli',call)
patch.setattr('app.docker_validation.shutil.which',lambda _: '/trusted/docker')
DockerValidationBackend().execute(fake.request,threading.Event(),export_dir=state.parent/'export')
raise AssertionError('interrupted validation returned')
'''
    worker = start_process([sys.executable, "-c", code, str(state), str(entered), str(containers), window, str(Path(__file__).parent)],
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        wait_for_file(entered, process=worker)
        journals = list((state / CONTEXT["daemonFingerprint"]).glob("*.json"))
        assert len(journals) == 1
        record = json.loads(journals[0].read_text(encoding="utf-8"))
        assert record["state"] == {"create": "creating", "check": "running", "export": "exporting"}[window]
        assert (record["containerId"] is None) == (window == "create")
        assert container_lifecycle.process_identity(record["ownerPid"]) == record["ownerStart"]
    finally:
        stop_process(worker)
        worker.communicate(timeout=5)
    # Real OS lock and process identity, persisted journal, simulated daemon.
    assert_processes_exited([record["ownerPid"]])
    fake = ControlledDocker(monkeypatch, state)
    fake.containers = json.loads(containers.read_text(encoding="utf-8"))
    foreign = deepcopy(fake.containers["e" * 64])
    foreign["Id"] = "9" * 64
    foreign["Config"]["Labels"]["io.agenthub.validation.operation"] = "8" * 32
    fake.containers[foreign["Id"]] = foreign
    foreign_before = deepcopy(foreign)
    with container_lifecycle.acquire_validation_slot(CONTEXT["daemonFingerprint"], threading.Event()) as slot:
        container_runtime.DockerRuntime(slot, "local", CONTEXT, executable="/trusted/docker").recover()
        assert slot.pending_journals() == []
        assert [p.name for p in slot.directory.iterdir()] == ["capacity.lock"]
    assert fake.containers == {"9" * 64: foreign_before}
    assert not (tmp_path / "export").exists()
