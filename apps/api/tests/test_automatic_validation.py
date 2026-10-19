import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
from fixture_database import flush_fixture_rows

import pytest
from sqlmodel import select

from app import automatic_validation as validation
from app.models import Artifact, TaskRunEvent
from app.events import append_task_run_event
from app.qa_assessment import build_qa_assessment, current_qa_assessment
from app.reviews import create_scripted_review_for_task_run, list_task_run_reviews
from app.worktrees import repo_root
from test_native_review_artifacts import fixture, SOURCE


def populate(root):
    platform = repo_root()
    for name in validation.CONFIG_FILES:
        shutil.copyfile(platform / "apps/demo" / name, root / "apps/demo" / name)
    for name in ("pnpm-lock.yaml", "package.json", "pnpm-workspace.yaml"):
        shutil.copyfile(platform / name, root / name)
    (root / "apps/demo/index.html").write_text('<div id="root"></div><script type="module" src="/src/App.tsx"></script>')


@pytest.fixture
def source_tree(tmp_path):
    root = tmp_path / "source"
    (root / "apps/demo/src").mkdir(parents=True)
    (root / SOURCE).write_text('export const title = "hello"')
    populate(root)
    return root


def success(argv, cwd, env, cancelled):
    return {"status": "passed", "exitCode": 0, "log": "fixture command", "durationMs": 1}


def test_copy_binds_exact_inputs_without_changing_original(source_tree):
    before, _ = validation.capture_validation_source(source_tree)
    seen = []
    def runner(argv, cwd, env, cancelled):
        assert not cwd.is_relative_to(source_tree)
        assert (cwd / "src/App.tsx").read_bytes() == (source_tree / SOURCE).read_bytes()
        assert (cwd / "node_modules").is_dir()
        seen.append(cwd)
        return success(argv, cwd, env, cancelled)
    receipt = validation.validate_copy(source_tree, threading.Event(), runner=runner)
    assert receipt["status"] == "passed" and len(receipt["commands"]) == 3
    assert validation.capture_validation_source(source_tree)[0] == before
    assert receipt["sourceFingerprint"] == before["sourceFingerprint"]
    assert all(not path.exists() for path in seen)
    assert not (source_tree / "apps/demo/dist").exists()


@pytest.mark.parametrize("mutation", ["config", "protected", "hardlink", "nested_dependency"])
def test_unsafe_inputs_never_launch_commands(source_tree, mutation):
    if mutation == "config": (source_tree / "apps/demo/vite.config.ts").write_text('throw new Error("unsafe")')
    if mutation == "protected": (source_tree / "apps/demo/.env").write_text("TOKEN=private")
    if mutation == "hardlink": os.link(source_tree / SOURCE, source_tree / "apps/demo/src/alias.tsx")
    if mutation == "nested_dependency": (source_tree / "apps/demo/src/node_modules").mkdir()
    def unexpected(*args): pytest.fail("Unsafe input launched command")
    with pytest.raises((ValueError, OSError)):
        validation.validate_copy(source_tree, threading.Event(), runner=unexpected)


@pytest.mark.parametrize("where", ["original", "copy", "added", "policy"])
def test_mutation_during_validation_is_not_accepted(source_tree, where, monkeypatch):
    counter = 0
    def runner(argv, cwd, env, cancelled):
        nonlocal counter
        counter += 1
        if counter == 1:
            if where == "original": (source_tree / SOURCE).write_text("changed")
            if where == "copy": (cwd / "src/App.tsx").write_text("changed")
            if where == "added": (cwd / "src/added.ts").write_text("export {}")
            if where == "policy": monkeypatch.setenv("TZ", "UTC-changed")
        return success(argv, cwd, env, cancelled)
    assert validation.validate_copy(source_tree, threading.Event(), runner=runner)["status"] == "stale"


def test_checkout_line_endings_preserve_trusted_config_but_keep_raw_source_fingerprint(source_tree):
    before, _ = validation.capture_validation_source(source_tree)
    path = source_tree / "apps/demo/package.json"
    raw = path.read_bytes()
    changed = raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    if changed == raw:
        changed = raw.replace(b"\r\n", b"\n")
    path.write_bytes(changed)
    result = validation.validate_copy(source_tree, threading.Event(), runner=success)
    assert result["status"] == "passed"
    assert result["sourceFingerprint"] != before["sourceFingerprint"]
    assert path.read_bytes() == changed


def test_first_failure_prevents_build_or_old_output_test(source_tree):
    def fail(*args): return {"status": "failed", "exitCode": 2, "log": "type error", "durationMs": 1}
    result = validation.validate_copy(source_tree, threading.Event(), runner=fail)
    assert result["status"] == "failed"
    assert [c["kind"] for c in result["commands"]] == ["check"]


@pytest.mark.parametrize("mode", ["timeout", "cancelled"])
def test_real_process_stops_and_drains_bounded_logs(tmp_path, mode):
    cancelled = threading.Event()
    if mode == "cancelled": cancelled.set()
    result = validation.run_command([sys.executable, "-u", "-c", "import time; print('x'*20000); time.sleep(30)"],
                                    tmp_path, os.environ.copy(), cancelled, timeout=0.3)
    assert result["status"] == mode
    assert result["exitCode"] != 0 and len(result["log"]) <= 12000


def make_receipt(db, run, root, *, failed=False):
    populate(root)
    run.state = "collecting_diff"
    db.add(run); db.commit()
    value = {**validation.capture_validation_source(root)[0], "schemaVersion": validation.SCHEMA,
             "profile": validation.PROFILE, "status": "failed" if failed else "passed",
             "taskRunId": run.id, "adapterRunId": run.adapter_run_id,
             "commands": [{"kind": kind, "command": "fixed " + kind, "status": "failed" if failed else "passed",
                           "exitCode": 1 if failed else 0, "log": "fixture"} for kind in ("check", "build", "test")]}
    event = append_task_run_event(db, task_run_id=run.id, event_type="validation.completed", payload_json=json.dumps(value))
    value["eventId"] = event.id
    return value, event


@pytest.mark.parametrize("failure", [False, True])
def test_same_version_commands_combine_with_model_but_never_override_failures(fixture, failure):
    db, run, root, _ = fixture
    make_receipt(db, run, root, failed=failure)
    diff = Artifact(task_run_id=run.id, artifact_type="diff", title="diff", status="ready")
    qa = build_qa_assessment(db, diff, plan={"targetId": "demo-frontend"}, files=[SOURCE], patch="",
                             findings=[], model_status="passed", input_fingerprint="bound-native-input")
    assert qa["status"] == ("blocked" if failure else "passed")
    assert qa["acceptance"] == ("not_established" if failure else "configured_checks_passed")
    assert all(c["versionBound"] for c in qa["commands"])
    (root / SOURCE).write_text("export const changed = true")
    refreshed = current_qa_assessment(db, qa)
    assert refreshed["status"] == "expired" and refreshed["acceptance"] == "not_established"
    assert qa["currentness"] == "current"  # immutable persisted snapshot


def test_freshness_requires_same_execution_and_completed_receipt(fixture):
    db, run, root, _ = fixture
    value, _ = make_receipt(db, run, root)
    assert validation.validation_currentness(db, run.id, value) == "current"
    for state in ("running", "interrupted", "failed"):
        run.state = state
        assert validation.validation_currentness(db, run.id, value) == "unverifiable"
    run.state = "completed"; run.adapter_run_id = "new-generation"
    assert validation.validation_currentness(db, run.id, value) == "unverifiable"


def test_pending_receipt_after_restart_is_never_retried_or_promoted(fixture, monkeypatch):
    db, run, root, _ = fixture
    _, artifact = make_receipt(db, run, root)
    artifact.event_type = "validation.started"
    artifact.payload_json = json.dumps({"schemaVersion": validation.SCHEMA, "status": "running"})
    db.add(artifact); db.commit(); db.expire_all()
    monkeypatch.setattr(validation, "validate_copy", lambda *args: pytest.fail("replayed validation"))
    asyncio.run(validation.run_automatic_validation(db, run))
    receipt = validation.validation_for_run(db, run.id)
    assert receipt["status"] == "running"
    assert validation.validation_currentness(db, run.id, receipt) == "unverifiable"


@pytest.mark.parametrize("loss", ["cancel", "ownership"])
def test_cancel_or_lost_ownership_cannot_publish_success(fixture, monkeypatch, loss):
    db, run, root, _ = fixture
    populate(root); run.state = "collecting_diff"; db.add(run); db.commit()
    entered = threading.Event()
    release = threading.Event()
    owned = True
    def slow(root, cancelled):
        entered.set()
        if loss == "cancel": cancelled.wait(5)
        else: release.wait(5)
        return {"schemaVersion": validation.SCHEMA, "status": "passed", "commands": []}
    monkeypatch.setattr(validation, "validate_copy", slow)
    async def exercise():
        nonlocal owned
        task = asyncio.create_task(validation.run_automatic_validation(db, run, ownership_guard=lambda: owned))
        while not entered.is_set(): await asyncio.sleep(0.01)
        if loss == "cancel":
            task.cancel()
            with pytest.raises(asyncio.CancelledError): await task
        else:
            owned = False
            release.set()
            await task
    asyncio.run(exercise())
    assert validation.validation_for_run(db, run.id)["status"] == "running"
    assert not db.exec(select(TaskRunEvent).where(TaskRunEvent.event_type == "validation.completed")).all()


@pytest.mark.parametrize("mode,expected", [("valid", "passed"), ("typescript", "check"), ("entry", "build"), ("mount", "test")])
def test_real_toolchain_accepts_valid_source_and_rejects_failures(source_tree, mode, expected):
    if mode == "typescript": (source_tree / SOURCE).write_text('const bad: number = "wrong"; export { bad }')
    if mode == "entry": (source_tree / "apps/demo/index.html").write_text('<div id="root"></div><script type="module" src="/missing.ts"></script>')
    if mode == "mount": (source_tree / "apps/demo/index.html").write_text('<div></div><script type="module" src="/src/App.tsx"></script>')
    result = validation.validate_copy(source_tree, threading.Event())
    assert result["status"] == ("passed" if mode == "valid" else "failed")
    if mode != "valid":
        assert result["commands"][-1]["kind"] == expected
        assert result["commands"][-1]["exitCode"] != 0
    else:
        assert len(result["commands"]) == 3 and all(c["exitCode"] == 0 for c in result["commands"])


def test_native_lifecycle_with_real_validation_and_stale_api_overlay(fixture, monkeypatch):
    from app.claude_code_adapter import ClaudeCodeAdapter
    from app.run_engine import execute_task_run
    from app.run_supervisor import RunSupervisor
    from app.routes.task_artifacts import review_response
    import test_native_review_artifacts as native_tests
    db, run, root, source = fixture
    populate(root)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                    "-c", "core.hooksPath=", "commit", "-qm", "validation fixture"], check=True)
    original = native_tests.assessment
    monkeypatch.setattr(native_tests, "assessment", lambda binding: original(binding, status="passed", findings=[], suggestedChanges=[]))
    completed = asyncio.run(execute_task_run(db, run, adapter_type="claude_code",
        adapter=ClaudeCodeAdapter(process_runner=native_tests.ReviewRunner(), read_only=True), supervisor=RunSupervisor()))
    assert completed.state == "completed", completed.error_message
    report = list_task_run_reviews(db, run.id)[0]
    assert report.qa_assessment["status"] == "passed", {
        "receiptStatus": validation.validation_for_run(db, run.id).get("status"),
        "receiptReason": validation.validation_for_run(db, run.id).get("reason"),
        "binding": json.loads(run.metrics_json).get("taskRunExecutionAccessBinding"),
        "startedAt": run.started_at, "runner": run.runner_id,
    }
    assert report.qa_assessment["acceptance"] == "configured_checks_passed"
    snapshot = db.get(Artifact, report.artifact_id).meta_json
    source.write_text('export const title = "changed after validation"')
    db.expire_all()
    response = review_response(list_task_run_reviews(db, run.id)[0]).model_dump(by_alias=True)
    assert response["qaAssessment"]["status"] == "expired"
    assert response["qaAssessment"]["acceptance"] == "not_established"
    assert db.get(Artifact, report.artifact_id).meta_json == snapshot


def test_receipt_survives_sqlite_reopen_and_rechecks_source(fixture, tmp_path):
    from sqlmodel import SQLModel, Session as DbSession
    from app.db_engine import create_runtime_engine as create_engine
    from app.models import Agent, Session, Task, TaskRun, Workspace
    db, run, root, source = fixture
    value, event = make_receipt(db, run, root)
    engine = create_engine(f"sqlite:///{(tmp_path / 'validation.sqlite').as_posix()}")
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as persisted:
        import app.models as models
        for model in vars(models).values():
            if isinstance(model, type) and issubclass(model, SQLModel) and getattr(model, '__table__', None) is not None:
                for row in db.exec(select(model)).all():
                    persisted.add(model(**{c.key: getattr(row, c.key) for c in model.__table__.columns}))
        flush_fixture_rows(persisted)
        persisted.commit()
    engine.dispose()
    engine = create_engine(f"sqlite:///{(tmp_path / 'validation.sqlite').as_posix()}")
    with DbSession(engine) as reopened:
        assert validation.validation_for_run(reopened, run.id)["sourceFingerprint"] == value["sourceFingerprint"]
        assert validation.validation_currentness(reopened, run.id, value) == "current"
        source.write_text("export const changed = 1")
        assert validation.validation_currentness(reopened, run.id, value) == "expired"
        assert reopened.get(TaskRunEvent, event.id).payload_json == event.payload_json
    engine.dispose()


def test_timeout_terminates_spawned_child(tmp_path):
    import time
    marker = tmp_path / "child-survived"
    child = f"import time; from pathlib import Path; time.sleep(1); Path({str(marker)!r}).write_text('unexpected')"
    parent = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child!r}]); time.sleep(30)"
    result = validation.run_command([sys.executable, "-c", parent], tmp_path, os.environ.copy(), threading.Event(), timeout=0.3)
    assert result["status"] == "timeout"
    time.sleep(1)
    assert not marker.exists()
