import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading

import pytest
from sqlmodel import Session as DbSession, select

from app import automatic_validation as validation
from app import backend_validation as backend
from app.events import append_task_run_event
from app.models import Agent, Artifact, Session, Task, TaskRunEvent, Workspace
from app.qa_assessment import build_qa_assessment, current_qa_assessment
from app.routes.task_artifacts import review_response
from app.reviews import list_task_run_reviews
from app.worktrees import repo_root
from test_native_review_artifacts import fixture
from test_scripted_mock_adapter import db as mock_db


SOURCE = "apps/demo-api/app/main.py"


def populate(root):
    shutil.copytree(repo_root() / "apps/demo-api", root / "apps/demo-api",
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))


@pytest.fixture
def backend_tree(tmp_path):
    root = tmp_path / "source"
    populate(root)
    return root


def receipt(stage):
    return {"status": "passed", "exitCode": 0, "durationMs": 1,
            "log": "AGENTHUB_BACKEND_RESULT=" + json.dumps({"schemaVersion": backend.RESULT_SCHEMA,
                "stage": stage, "checks": [{"id": name, "status": "passed"} for name in backend.CHECKS[stage]]})}


def success(argv, *args):
    return receipt(argv[-3])


def prepare_run(fixture):
    db, run, root, _ = fixture
    populate(root)
    task = db.get(Task, run.task_id)
    task.plan_json = json.dumps({"targetId": "demo-backend", "files": [SOURCE], "assignedRole": "review"})
    run.state = "collecting_diff"
    db.add(task); db.add(run); db.commit()
    return db, run, root


def test_real_python_contracts_use_copy_and_preserve_original(backend_tree):
    before, _ = backend.capture_backend_source(backend_tree)
    result = backend.validate_backend_copy(backend_tree, threading.Event())
    assert result["status"] == "passed", result
    assert [c["kind"] for c in result["commands"]] == ["check", "test"]
    assert [c["exitCode"] for c in result["commands"]] == [0, 0]
    assert all(backend.parse_result(c, c["kind"]) for c in result["commands"])
    assert backend.capture_backend_source(backend_tree)[0] == before
    assert not (backend_tree / "data").exists()


@pytest.mark.parametrize("mutation,stage", [
    ("syntax", "check"), ("health", "test"), ("create", "test"),
    ("validation", "test"), ("duplicate", "test"), ("cors", "test"), ("exit_zero", "test"),
])
def test_real_backend_failures_cannot_pass(backend_tree, mutation, stage):
    path = backend_tree / SOURCE
    text = path.read_text(encoding="utf-8")
    changes = {
        "syntax": lambda t: t + "\ndef invalid(:\n",
        "health": lambda t: t.replace('status="ok"', 'status="wrong"'),
        "create": lambda t: t.replace("_contacts.append(contact)", "pass"),
        "validation": lambda t: t.replace("min_length=1", "min_length=0"),
        "duplicate": lambda t: t.replace("if any(contact.email == payload.email for contact in _contacts):", "if False:"),
        "cors": lambda t: t.replace('allow_methods=["GET", "POST", "OPTIONS"]', 'allow_methods=["POST"]'),
        "exit_zero": lambda t: "raise SystemExit(0)\n" + t,
    }
    path.write_text(changes[mutation](text), encoding="utf-8")
    result = backend.validate_backend_copy(backend_tree, threading.Event())
    assert result["status"] == "failed", result
    assert result["commands"][-1]["kind"] == stage
    assert result["commands"][-1]["status"] == "failed"
    if mutation == "exit_zero":
        assert result["commands"][-1]["exitCode"] == 0
        assert "Incomplete backend contract evidence" in result["commands"][-1]["log"]


@pytest.mark.parametrize("payload", [
    "import socket; socket.create_connection(('127.0.0.1', 1))",
    "import socket; socket.socket().bind(('127.0.0.1', 0))",
    "import socket; socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b'test', ('127.0.0.1', 1))",
    "import subprocess; subprocess.run(['unexpected-command'])",
    "import ctypes; ctypes.CDLL('unexpected-library')",
    "open(__file__, 'w').write('changed')",
])
def test_target_import_cannot_use_network_process_loader_or_edit_copy(backend_tree, payload):
    path = backend_tree / SOURCE
    path.write_text(payload + "\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    result = backend.validate_backend_copy(backend_tree, threading.Event())
    assert result["status"] == "failed", result
    assert "PermissionError" in result["commands"][-1]["log"]


@pytest.mark.parametrize("mode", ["read", "write"])
def test_host_file_access_rejected_and_private_content_not_logged(backend_tree, tmp_path, mode):
    private = tmp_path / "unassigned.txt"
    private.write_text("private sentinel", encoding="utf-8")
    path = backend_tree / SOURCE
    action = f"print(open({str(private)!r}).read())" if mode == "read" else f"open({str(private)!r}, 'w').write('changed')"
    path.write_text(action + "\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    result = backend.validate_backend_copy(backend_tree, threading.Event())
    assert result["status"] == "failed"
    assert "private sentinel" not in str(result)
    assert private.read_text(encoding="utf-8") == "private sentinel"


def test_target_tests_are_not_executed_and_credentials_are_not_inherited(backend_tree, tmp_path, monkeypatch):
    marker = tmp_path / "target-tests-executed"
    (backend_tree / "apps/demo-api/tests/test_contacts.py").write_text(
        f"from pathlib import Path; Path({str(marker)!r}).write_text('bad')", encoding="utf-8")
    path = backend_tree / SOURCE
    path.write_text("import os\nassert 'OPENAI_API_KEY' not in os.environ\nassert 'VITE_SECRET' not in os.environ\n"
                    + path.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "private-test-key")
    monkeypatch.setenv("VITE_SECRET", "private-public-key")
    result = backend.validate_backend_copy(backend_tree, threading.Event())
    assert result["status"] == "passed", result
    assert not marker.exists()


@pytest.mark.parametrize("mutation", ["protected", "hardlink", "symlink", "native", "missing_entry"])
def test_unsafe_inputs_never_start_commands(backend_tree, mutation):
    source = backend_tree / SOURCE
    if mutation == "protected": (backend_tree / "apps/demo-api/.env").write_text("SECRET=value")
    if mutation == "hardlink": os.link(source, source.with_name("alias.py"))
    if mutation == "symlink": source.with_name("alias.py").symlink_to(source)
    if mutation == "native": source.with_name("extension.pyd").write_bytes(b"native")
    if mutation == "missing_entry": source.unlink()
    def unexpected(*args):
        pytest.fail("Unsafe backend input launched a command")
    with pytest.raises((ValueError, OSError)):
        backend.validate_backend_copy(backend_tree, threading.Event(), runner=unexpected)


@pytest.mark.parametrize("mode", ["source", "copy", "added", "policy"])
def test_source_copy_or_policy_drift_cannot_pass(backend_tree, monkeypatch, mode):
    def runner(argv, cwd, env, cancelled):
        if argv[-3] == "check":
            if mode == "source": (backend_tree / SOURCE).write_text("# changed")
            if mode == "copy": (cwd / "app/main.py").write_text("# changed")
            if mode == "added": (cwd / "app/extra.py").write_text("# new")
            if mode == "policy": monkeypatch.setenv("TZ", "changed-policy")
        return success(argv)
    assert backend.validate_backend_copy(backend_tree, threading.Event(), runner=runner)["status"] == "stale"


@pytest.mark.parametrize("mode", ["missing", "partial", "duplicate", "status", "stage", "exit"])
def test_structured_coverage_required_even_for_zero_exit(mode):
    value = receipt("test")
    parsed = json.loads(value["log"].split("=", 1)[1])
    if mode == "missing": value["log"] = "done"
    if mode == "partial": parsed["checks"].pop()
    if mode == "duplicate": parsed["checks"][0] = parsed["checks"][1]
    if mode == "status": parsed["checks"][0]["status"] = "failed"
    if mode == "stage": parsed["stage"] = "check"
    if mode == "exit": value["exitCode"] = 1
    if mode != "missing": value["log"] = "AGENTHUB_BACKEND_RESULT=" + json.dumps(parsed)
    assert not backend.parse_result(value, "test")


def test_backend_run_receipt_qa_and_source_expiry(fixture):
    db, run, root = prepare_run(fixture)
    asyncio.run(validation.run_automatic_validation(db, run))
    value = validation.validation_for_run(db, run.id)
    assert value["status"] == "passed"
    assert value["profile"] == validation.BACKEND_PROFILE
    assert validation.validation_currentness(db, run.id, value) == "current"
    diff = Artifact(task_run_id=run.id, artifact_type="diff", title="backend diff", status="ready")
    qa = build_qa_assessment(db, diff, plan={"targetId": "demo-backend"}, files=[SOURCE], patch="",
                             findings=[], model_status="passed", input_fingerprint="bound-native-input")
    assert qa["status"] == "passed"
    assert qa["acceptance"] == "configured_checks_passed"
    assert [(c["kind"], c["status"], c["versionBound"]) for c in qa["commands"]] == [
        ("check", "passed", True), ("test", "passed", True), ("build", "not_applicable", False)]
    (root / SOURCE).write_text("# changed", encoding="utf-8")
    assert current_qa_assessment(db, qa)["status"] == "expired"
    assert qa["status"] == "passed"  # historical result was not rewritten


def test_failed_backend_contract_blocks_even_passed_model(fixture):
    db, run, root = prepare_run(fixture)
    path = root / SOURCE
    path.write_text(path.read_text(encoding="utf-8").replace('status="ok"', 'status="wrong"'), encoding="utf-8")
    asyncio.run(validation.run_automatic_validation(db, run))
    diff = Artifact(task_run_id=run.id, artifact_type="diff", title="diff", status="ready")
    qa = build_qa_assessment(db, diff, plan={"targetId": "demo-backend"}, files=[SOURCE], patch="",
                             findings=[], model_status="passed", input_fingerprint="native")
    assert qa["status"] == "blocked" and qa["commands"][1]["status"] == "failed"


def test_backend_receipt_cannot_be_rebound_to_frontend_or_another_generation(fixture):
    db, run, root = prepare_run(fixture)
    asyncio.run(validation.run_automatic_validation(db, run))
    value = validation.validation_for_run(db, run.id)
    task = db.get(Task, run.task_id)
    original = task.plan_json
    task.plan_json = json.dumps({"targetId": "demo-frontend"})
    db.add(task); db.commit()
    assert validation.validation_currentness(db, run.id, value) == "unverifiable"
    task.plan_json = original
    run.adapter_run_id = "new-generation"
    db.add(task); db.add(run); db.commit()
    assert validation.validation_currentness(db, run.id, value) == "unverifiable"


@pytest.mark.parametrize("loss", ["cancel", "ownership"])
def test_backend_cancel_or_ownership_loss_cannot_publish_completed(fixture, monkeypatch, loss):
    db, run, root = prepare_run(fixture)
    entered, release = threading.Event(), threading.Event()
    owned = True
    def slow(root, cancelled):
        entered.set()
        (cancelled if loss == "cancel" else release).wait(5)
        return {"schemaVersion": validation.SCHEMA, "status": "passed", "commands": []}
    monkeypatch.setattr(backend, "validate_backend_copy", slow)
    async def exercise():
        nonlocal owned
        operation = asyncio.create_task(validation.run_automatic_validation(db, run, ownership_guard=lambda: owned))
        while not entered.is_set(): await asyncio.sleep(0.01)
        if loss == "cancel":
            operation.cancel()
            with pytest.raises(asyncio.CancelledError): await operation
        else:
            owned = False; release.set(); await operation
    asyncio.run(exercise())
    assert validation.validation_for_run(db, run.id)["status"] == "running"
    assert not db.exec(select(TaskRunEvent).where(TaskRunEvent.event_type == "validation.completed")).all()


def test_restart_preserves_completed_receipt_and_never_replays_pending(fixture, monkeypatch):
    db, run, root = prepare_run(fixture)
    asyncio.run(validation.run_automatic_validation(db, run))
    value = validation.validation_for_run(db, run.id)
    with DbSession(db.get_bind()) as reopened:
        assert validation.validation_currentness(reopened, run.id, value) == "current"
    append_task_run_event(db, task_run_id=run.id, event_type="validation.started", payload_json=json.dumps({
        "schemaVersion": validation.SCHEMA, "profile": validation.BACKEND_PROFILE, "status": "running"}))
    monkeypatch.setattr(backend, "validate_backend_copy", lambda *args: pytest.fail("Unexpected replay"))
    asyncio.run(validation.run_automatic_validation(db, run))
    assert validation.validation_for_run(db, run.id)["status"] == "running"


def test_backend_write_lifecycle_records_real_validation_diff_and_persistent_review(mock_db, backend_tree):
    from app.adapters import AgentEvent
    from app.scripted_mock import ScriptedMockAdapter
    from app.run_engine import execute_task_run, _prepare_claimed_task_run_for_adapter
    from app.run_supervisor import RunSupervisor
    from app.task_runs import create_task_run

    # Test-only writer: proves lifecycle integration, not real Provider coding.
    class BackendWriter(ScriptedMockAdapter):
        async def streamEvents(self, run_id):
            request = self._request_for(run_id)
            yield AgentEvent(type="task.state", taskRunId=request.task_run_id, sequence=1, payload={"state": "streaming"})
            path = Path(request.worktree_path) / SOURCE
            path.write_bytes(path.read_bytes() + b"\n# lifecycle validation change\n")
            yield AgentEvent(type="completed", taskRunId=request.task_run_id, sequence=2, payload={"changedFiles": [SOURCE]})

    subprocess.run(["git", "init", "-q", str(backend_tree)], check=True)
    subprocess.run(["git", "-C", str(backend_tree), "add", "."], check=True)
    subprocess.run(["git", "-C", str(backend_tree), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                    "-c", "core.hooksPath=", "commit", "-qm", "backend fixture"], check=True)
    workspace = Workspace(name="Backend", root_path="apps/demo-api", repo_url="local://apps/demo-api", default_branch="main")
    session = Session(workspace_id=workspace.id, title="Backend", bound_branch="main", worktree_path=str(backend_tree))
    agent = Agent(name="Backend", role="backend", adapter_type="scripted_mock", provider="local")
    task = Task(session_id=session.id, title="Backend validation", intent_type="backend_change", assigned_agent_id=agent.id,
                plan_json=json.dumps({"targetId": "demo-backend", "assignedRole": "backend", "files": [SOURCE]}))
    mock_db.add_all([workspace, session, agent, task]); mock_db.commit()
    run = create_task_run(mock_db, task.id)
    assert _prepare_claimed_task_run_for_adapter(mock_db, run, run.runner_id)
    completed = asyncio.run(execute_task_run(mock_db, run, adapter_type="scripted_mock", adapter=BackendWriter(), supervisor=RunSupervisor()))
    assert completed.state == "completed", completed.error_message
    value = validation.validation_for_run(mock_db, run.id)
    assert value["status"] == "passed" and value["adapterRunId"] == completed.adapter_run_id
    assert validation.validation_currentness(mock_db, run.id, value) == "current"
    report = list_task_run_reviews(mock_db, run.id)[0]
    qa = report.qa_assessment
    assert qa["status"] == "incomplete" and qa["model"]["status"] == "not_run"
    assert qa["commands"][1]["status"] == "passed" and qa["commands"][1]["versionBound"]
    assert review_response(report).model_dump(by_alias=True)["qaAssessment"] == qa
    with DbSession(mock_db.get_bind()) as reopened:
        assert list_task_run_reviews(reopened, run.id)[0].qa_assessment == qa


def test_real_backend_timeout_stops_before_test_acceptance(backend_tree):
    path = backend_tree / SOURCE
    path.write_text("import time; time.sleep(30)\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    def bounded(argv, cwd, env, cancelled):
        return validation.run_command(argv, cwd, env, cancelled, timeout=1)
    value = backend.validate_backend_copy(backend_tree, threading.Event(), runner=bounded)
    assert value["status"] == "failed" and value["commands"][-1]["status"] == "timeout"


def test_unavailable_dependency_produces_honest_durable_receipt(fixture, monkeypatch):
    db, run, root = prepare_run(fixture)
    def missing(name):
        raise backend.importlib.metadata.PackageNotFoundError(name)
    monkeypatch.setattr(backend.importlib.metadata, "version", missing)
    asyncio.run(validation.run_automatic_validation(db, run))
    value = validation.validation_for_run(db, run.id)
    assert value["status"] == "unavailable" and "dependencies are unavailable" in value["reason"]
    assert validation.validation_currentness(db, run.id, value) == "unverifiable"
