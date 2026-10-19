"""Opt-in real Docker qualification. Forced runs fail, never skip prerequisites."""
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import threading
import subprocess
import sys
import time
from uuid import uuid4

import pytest

from app.container_lifecycle import acquire_validation_slot
from app.container_lifecycle import OwnedContainer, ValidationSlot, process_identity
from app.container_runtime import DockerRuntime, run_cli
from app.docker_validation import DockerValidationBackend, write_snapshot
from app.sandbox_cli import doctor
from app.validation_inputs import capture_profile_inputs
from app.validation_process import start_process, stop_process
from app.validation_policy import (BACKEND_PROFILE, FRONTEND_PROFILE, FixedValidationRequest, ValidationIdentity,
                                   bind_execution, platform_root, resolve_backend_settings)

FORCED = os.environ.get("AGENTHUB_TEST_CONTAINER_VALIDATION") == "1"
pytestmark = pytest.mark.skipif(not FORCED, reason="Real Docker qualification requires sandbox:verify")


@pytest.fixture(scope="module")
def qualified_settings():
    settings = resolve_backend_settings()
    report = doctor(context_name=settings["contextName"], image_ids=settings["imageIds"])
    assert report["status"] == "metadata_ready", "Required Docker environment is unavailable: " + json.dumps(report)
    return {**settings, "backend": "docker"}


def real_request(tmp_path, profile, settings, *, defective=False):
    root = tmp_path / uuid4().hex
    frontend = profile == FRONTEND_PROFILE
    relative = "apps/demo" if frontend else "apps/demo-api"
    shutil.copytree(platform_root() / relative, root / relative,
                    ignore=shutil.ignore_patterns("node_modules", "dist", "__pycache__", ".pytest_cache"))
    if frontend:
        for name in ("package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml"):
            shutil.copyfile(platform_root() / name, root / name)
    if defective:
        path = root / relative / ("src/App.tsx" if frontend else "app/main.py")
        path.write_bytes(path.read_bytes() + (b'\nconst broken: number = "wrong";\n' if frontend else b'\ninvalid(:\n'))
    snapshot = capture_profile_inputs(root, profile)
    identity = ValidationIdentity(uuid4().hex, uuid4().hex, uuid4().hex, "f" * 64)
    return FixedValidationRequest(snapshot, identity, bind_execution(snapshot, identity, settings))


def test_required_environment_is_real(qualified_settings, record_property):
    record_property("context", qualified_settings["contextName"])
    record_property("images", json.dumps(qualified_settings["imageIds"]))


@pytest.mark.parametrize("profile", [FRONTEND_PROFILE, BACKEND_PROFILE])
@pytest.mark.parametrize("defective", [False, True])
def test_real_fixed_profiles_accept_and_reject_source(tmp_path, qualified_settings, profile, defective, record_property):
    request = real_request(tmp_path, profile, qualified_settings, defective=defective)
    result = DockerValidationBackend().execute(request, threading.Event(), export_dir=tmp_path / "export")
    record_property("execution", json.dumps(result.execution))
    assert result.status == ("failed" if defective else "passed"), result
    assert result.execution["commandsBackend"] == "docker"
    assert result.commands and all(c["exitCode"] == 0 for c in result.commands) == (not defective)
    if not defective: assert result.output_fingerprint


@pytest.fixture
def owned_backend(tmp_path, qualified_settings):
    request = real_request(tmp_path, BACKEND_PROFILE, qualified_settings)
    context = DockerRuntime.check_context(shutil.which("docker"), request.execution.image.context_name)
    with acquire_validation_slot(context["daemonFingerprint"], threading.Event()) as slot:
        runtime = DockerRuntime(slot, request.execution.image.context_name, context)
        runtime.recover()
        input_dir = runtime.reserve(request)
        write_snapshot(input_dir, request)
        owned = runtime.create(request, input_dir)
        runtime.start(owned)
        try:
            assert runtime.exec_stage(owned, "prepare", threading.Event())["status"] == "passed"
            yield runtime, owned, input_dir
        finally:
            runtime.cleanup(owned)


def probe(owned_backend, script, *, timeout=10, output_limit=12000):
    runtime, owned, _ = owned_backend
    runtime.verify(owned)
    # Qualification-only fixed probes of this test's verified container. They
    # are not production stages, commands, configuration or Agent tools.
    result = runtime.call(["container", "exec", "--user", "10001:10001",
                      owned.container_id, "/usr/local/bin/python", "-I", "-B", "-c", script],
                     cancelled=threading.Event(), timeout=timeout, output_limit=output_limit, strict_limit=False)
    runtime.verify(owned)
    return result


def test_real_readonly_input_root_no_credentials_network_or_host_access(owned_backend, tmp_path, monkeypatch):
    sentinel = tmp_path / "host-sentinel"
    sentinel.write_text("must-stay-on-host")
    script = '''
import os,socket
assert os.getuid()==10001
assert not any(k.startswith(('OPENAI_','ANTHROPIC_','AGENTHUB_DATABASE','GITHUB_')) for k in os.environ)
for path in ['/forbidden-write','/input/forbidden-write']:
    try: open(path,'w').write('bad')
    except OSError: pass
    else: raise AssertionError('writable protected root')
for path in ['/var/run/docker.sock','/input/.env',HOST_SENTINEL]:
    try: open(path,'rb').read()
    except OSError: pass
    else: raise AssertionError('host input exposed')
for address in [('1.1.1.1',443),('127.0.0.1',8000)]:
    try: socket.create_connection(address,timeout=.5)
    except OSError: pass
    else: raise AssertionError('network reachable')
print('boundaries_checked')
'''.replace("HOST_SENTINEL", repr(str(sentinel)))
    result = probe(owned_backend, script)
    assert result["status"] == "passed" and b"boundaries_checked" in result["stdout"]
    assert sentinel.read_text() == "must-stay-on-host"


def test_real_pid_memory_and_cpu_cgroup_limits_are_enforced(owned_backend):
    script = '''
from pathlib import Path
import os,time
c=Path('/sys/fs/cgroup')
assert (c/'memory.max').read_text().strip()=='1073741824'
assert (c/'pids.max').read_text().strip()=='128'
quota,period=map(int,(c/'cpu.max').read_text().split()); assert quota/period==1
children=[]
try:
    for _ in range(160):
        try: pid=os.fork()
        except OSError: break
        if pid==0: time.sleep(5); os._exit(0)
        children.append(pid)
    else: raise AssertionError('PID budget not enforced')
    assert len(children)<128
finally:
    import signal
    for pid in children: os.kill(pid,signal.SIGKILL)
    for pid in children: os.waitpid(pid,0)
before=dict(line.split() for line in (c/'cpu.stat').read_text().splitlines())
children=[]
for _ in range(2):
    pid=os.fork()
    if pid==0:
        until=time.monotonic()+2
        while time.monotonic()<until: pass
        os._exit(0)
    children.append(pid)
for pid in children: os.waitpid(pid,0)
after=dict(line.split() for line in (c/'cpu.stat').read_text().splitlines())
assert int(after['nr_throttled'])>int(before['nr_throttled'])
print('resources_checked')
'''
    result = probe(owned_backend, script)
    assert result["status"] == "passed" and b"resources_checked" in result["stdout"]
    # Keep the keeper below OOM priority so the allocating probe is the victim.
    result = probe(owned_backend, "import os; open('/proc/self/oom_score_adj','w').write('1000'); x=bytearray(2*1024**3)")
    assert result["exitCode"] != 0
    evidence = probe(owned_backend, "from pathlib import Path; print(Path('/sys/fs/cgroup/memory.events').read_text(), end='')")
    assert evidence["status"] == "passed"
    counters = dict(line.split() for line in evidence["stdout"].decode().splitlines())
    assert int(counters["oom_kill"]) > 0


def test_real_active_container_excludes_a_second_process_from_capacity(owned_backend):
    from app import container_lifecycle
    runtime, owned, _ = owned_backend
    before = runtime.verify(owned)
    script = '''
import sys,threading
from pathlib import Path
from app import container_lifecycle as lifecycle
lifecycle.state_root=lambda: Path(sys.argv[2])
lifecycle.WAIT_SECONDS=.2
try:
    with lifecycle.acquire_validation_slot(sys.argv[1],threading.Event()):
        raise AssertionError('second process acquired active capacity')
except ValueError as exc:
    assert 'capacity_unavailable' in str(exc), str(exc)
    print('capacity_checked')
'''
    result = run_cli([sys.executable, "-c", script, runtime.context["daemonFingerprint"],
                      str(container_lifecycle.state_root())], threading.Event(), timeout=5)
    assert result["status"] == "passed" and result["stdout"].strip() == b"capacity_checked", result
    assert runtime.verify(owned) == before


def test_real_frontend_export_rejects_oversized_output(tmp_path, qualified_settings):
    request = real_request(tmp_path, FRONTEND_PROFILE, qualified_settings)
    context = DockerRuntime.check_context(shutil.which("docker"), request.execution.image.context_name)
    with acquire_validation_slot(context["daemonFingerprint"], threading.Event()) as slot:
        runtime = DockerRuntime(slot, request.execution.image.context_name, context)
        runtime.recover()
        owned = None
        try:
            input_dir = runtime.reserve(request)
            write_snapshot(input_dir, request)
            owned = runtime.create(request, input_dir)
            runtime.start(owned)
            assert runtime.exec_stage(owned, "prepare", threading.Event())["status"] == "passed"
            assert runtime.exec_stage(owned, "build", threading.Event())["status"] == "passed"
            result = runtime.call(["container", "exec", "--user", "10001:10001", owned.container_id,
                "/usr/local/bin/node", "-e",
                "require('node:fs').writeFileSync('/work/apps/demo/dist/oversized.js',Buffer.alloc(5*1024*1024+1))"])
            assert result["status"] == "passed", result
            with pytest.raises(ValueError, match="Export unavailable"):
                runtime.export_bytes(owned, threading.Event())
        finally:
            if owned is not None: runtime.cleanup(owned)
            else: runtime.cleanup_pending(request.execution.operation_id)
        assert slot.pending_journals() == []


def test_real_logs_deadline_cancellation_and_exact_cleanup(owned_backend):
    runtime, owned, _ = owned_backend
    result = probe(owned_backend, "import sys; sys.stdout.write('x'*200000)")
    assert result["status"] == "passed" and len(result["stdout"]) == 12000
    result = probe(owned_backend, "import time; time.sleep(5)", timeout=.2)
    assert result["status"] == "timeout"
    cancelled = threading.Event(); cancelled.set()
    assert runtime.exec_stage(owned, "check", cancelled)["status"] == "cancelled"
    runtime.deadline = 0
    with pytest.raises(ValueError, match="timeout"):
        runtime.exec_stage(owned, "check", threading.Event())


INTERRUPTED_WORKER = '''
import sys,threading,json,time
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,sys.argv[7])
from app.validation_policy import *
from app.validation_inputs import capture_profile_inputs
from app import container_runtime as runtime, container_lifecycle as lifecycle
from app.docker_validation import DockerValidationBackend
from container_interruption_helpers import CREATE_RELAY,RUNNING_PROBE
source,state,window,mode,gate,release=map(str,sys.argv[1:7])
lifecycle.state_root=lambda: Path(state)
original=runtime.run_cli
def call(argv,cancelled,**kwargs):
    if window=='create' and argv[5:7]==['container','create']:
        return original([sys.executable,'-c',CREATE_RELAY,json.dumps(argv),gate,release],cancelled,**kwargs)
    if argv[5:7]==['container','exec'] and argv[-1]==window:
        argv=argv[:-2]+['/usr/local/bin/python','-I','-B','-c',RUNNING_PROBE,window]
    return original(argv,cancelled,**kwargs)
runtime.run_cli=call
snapshot=capture_profile_inputs(Path(sys.argv[1]),BACKEND_PROFILE)
identity=ValidationIdentity(uuid4().hex,uuid4().hex,uuid4().hex,'f'*64)
request=FixedValidationRequest(snapshot,identity,bind_execution(snapshot,identity,{**resolve_backend_settings(),'backend':'docker'}))
cancelled=threading.Event()
def watch_cancel():
    while not Path(release).exists(): time.sleep(.02)
    cancelled.set()
if mode=='cancel': threading.Thread(target=watch_cancel,daemon=True).start()
result=DockerValidationBackend().execute(request,cancelled,export_dir=Path(state).parent/'export')
(Path(state).parent/'result.json').write_text(json.dumps({'status':result.status,'output':result.output_fingerprint}))
'''


@pytest.mark.parametrize("window,mode", [("create", "crash"), ("check", "crash"), ("export", "crash"),
                                         ("check", "cancel"), ("export", "cancel")])
def test_real_inflight_interruption_recovers_only_owned_resources(
        tmp_path, qualified_settings, owned_backend, monkeypatch, window, mode):
    from app import container_lifecycle
    request = real_request(tmp_path / "source", BACKEND_PROFILE, qualified_settings)
    source = next((tmp_path / "source").iterdir())
    state, gate, release = tmp_path / "state", tmp_path / "create-response", tmp_path / "release"
    context = DockerRuntime.check_context(shutil.which("docker"), request.execution.image.context_name)
    # A separate fixture-owned real container must survive worker recovery.
    foreign_runtime, foreign_owned, foreign_input = owned_backend
    foreign_before = foreign_runtime.verify(foreign_owned)
    worker = start_process([sys.executable, "-c", INTERRUPTED_WORKER, str(source), str(state), window, mode,
                            str(gate), str(release), str(Path(__file__).parent)],
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    slot = ValidationSlot(state / context["daemonFingerprint"])
    observer = DockerRuntime(slot, request.execution.image.context_name, context)
    record = None
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            assert worker.poll() is None, "Worker exited before its in-flight probe"
            journals = list(slot.directory.glob("*.json"))
            if journals:
                record = slot.load(journals[0])
                if window == "create" and gate.exists():
                    assert record["state"] == "creating" and record["containerId"] is None
                    assert observer.matching_ids(record["operationId"]) == [gate.read_bytes().decode().strip()]
                    break
                if window != "create" and record["containerId"]:
                    owned = OwnedContainer(record["containerId"], record["operationId"], record["contextName"], journals[0])
                    observer.verify(owned)
                    probe_result = observer.call(["container", "exec", "--user", "10001:10001", owned.container_id,
                        "/usr/local/bin/python", "-I", "-B", "-c",
                        "from pathlib import Path; print(Path('/work/.agenthub-interruption-probe').read_text())"])
                    if probe_result["status"] == "passed" and probe_result["stdout"].strip() == window.encode():
                        record = slot.load(journals[0])
                        assert record["state"] == ("exporting" if window == "export" else "running")
                        break
            time.sleep(.05)
        else: pytest.fail("Real container did not reach its in-flight probe")
        assert worker.poll() is None and record is not None and not release.exists()
        if mode == "cancel":
            release.touch()  # after a real container exec has confirmed it is running
            _, errors = worker.communicate(timeout=20)
            assert worker.returncode == 0, errors.decode(errors="replace")
            assert json.loads((tmp_path / "result.json").read_text()) == {"status": "cancelled", "output": None}
        else:
            stop_process(worker)
            worker.communicate(timeout=5)
            deadline = time.monotonic() + 5
            while process_identity(record["ownerPid"]) is not None and time.monotonic() < deadline: time.sleep(.02)
            assert process_identity(record["ownerPid"]) is None
            assert not (tmp_path / "result.json").exists()
        monkeypatch.setattr(container_lifecycle, "state_root", lambda: state)
        with acquire_validation_slot(context["daemonFingerprint"], threading.Event()) as recovered_slot:
            DockerRuntime(recovered_slot, request.execution.image.context_name, context).recover()
            assert recovered_slot.pending_journals() == []
            assert [p.name for p in recovered_slot.directory.iterdir()] == ["capacity.lock"]
        assert observer.matching_ids(record["operationId"]) == []
        assert not (tmp_path / "export").exists()
        assert foreign_input.exists() and foreign_runtime.verify(foreign_owned) == foreign_before
    finally:
        stop_process(worker)
        worker.communicate(timeout=5)
        release.touch()  # also lets a create response relay exit after its API worker was killed
        if record is not None:
            monkeypatch.setattr(container_lifecycle, "state_root", lambda: state)
            with acquire_validation_slot(context["daemonFingerprint"], threading.Event()) as cleanup_slot:
                DockerRuntime(cleanup_slot, request.execution.image.context_name, context).recover()


def test_real_scripted_write_diff_docker_validation_and_native_preview(tmp_path, qualified_settings, monkeypatch):
    from sqlmodel import Session as DbSession, select
    from app.db_engine import create_runtime_engine as create_engine
    from sqlalchemy.pool import StaticPool
    from app.models import TaskRun, Diff, SQLModel
    from app.config import get_settings
    from app.previews import PreviewService
    from app.worktrees import WorktreeService
    from test_requirement_validation import copy_app, test_scripted_execution_runs_real_browser_acceptance
    monkeypatch.setenv("AGENTHUB_VALIDATION_BACKEND", "docker")
    get_settings.cache_clear()
    target = tmp_path / "scripted-target"
    copy_app(target)
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    try:
        with DbSession(engine) as db:
            test_scripted_execution_runs_real_browser_acceptance(db, target, monkeypatch)
            run = db.exec(select(TaskRun)).one()
            assert db.exec(select(Diff)).first() is not None
            # This independent fixture repository does not go through normal
            # Session setup. Ignore and link only the already installed setup
            # dependencies before exercising the unchanged native preview.
            WorktreeService(repo_root=target)._ensure_setup_dependency_ignores(target)
            for relative in ("node_modules", "apps/demo/node_modules"):
                (target / relative).symlink_to(platform_root() / relative, target_is_directory=True)
            service = PreviewService()
            try:
                preview = service.start_task_run_preview(db, run.id)
                assert preview.status == "ready", preview.status_reason
                import urllib.request
                with urllib.request.urlopen(preview.url, timeout=5) as response:
                    assert response.status == 200 and b'id="root"' in response.read()
            finally: service.shutdown()
    finally:
        engine.dispose(); get_settings.cache_clear()
