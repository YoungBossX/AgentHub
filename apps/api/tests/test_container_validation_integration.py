import asyncio
from copy import deepcopy
import hashlib
import importlib
import json
import threading

import pytest
from sqlmodel import select

from app import automatic_validation as validation
from app.config import get_settings
from app.events import append_task_run_event
from app.models import Task, TaskRunEvent, utc_now
from app.qa_assessment import build_qa_assessment
from app.validation_policy import ProfileExecutionResult
from test_automatic_validation import populate, make_receipt
from test_native_review_artifacts import fixture, SOURCE


@pytest.fixture(autouse=True)
def configuration(monkeypatch):
    monkeypatch.setenv("AGENTHUB_VALIDATION_BACKEND", "native")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def launch(fixture):
    db, run, root, _ = fixture
    populate(root)
    task = db.get(Task, run.task_id)
    run.state, run.runner_id, run.adapter_run_id = "collecting_diff", "original-runner", "adapter-run"
    run.started_at = utc_now()
    binding = {"taskRunId": run.id, "taskId": task.id, "sessionId": task.session_id, "queueEntryId": "launch-queue",
               "accessMode": "readonly", "runnerId": "original-runner", "executionAttemptId": "attempt-1"}
    metrics = json.loads(run.metrics_json)
    metrics["taskRunExecutionAccessBinding"] = binding
    run.metrics_json = json.dumps(metrics)
    db.add(run); db.commit()
    return db, run, root


def native_result(root, cancelled, **kwargs):
    return {"schemaVersion": validation.SCHEMA, **validation.capture_validation_source(root)[0],
            "profile": validation.PROFILE, "status": "passed", "commands": [
                {"kind": kind, "command": "fixed " + kind, "status": "passed", "exitCode": 0, "log": "fixed"}
                for kind in ("check", "build", "test")]}


def docker_settings(monkeypatch):
    monkeypatch.setenv("AGENTHUB_VALIDATION_BACKEND", "docker")
    monkeypatch.setenv("AGENTHUB_VALIDATION_DOCKER_CONTEXT", "local-test")
    monkeypatch.setenv("AGENTHUB_VALIDATION_FRONTEND_IMAGE_ID", "sha256:" + "a" * 64)
    monkeypatch.setenv("AGENTHUB_VALIDATION_BACKEND_IMAGE_ID", "sha256:" + "b" * 64)
    get_settings.cache_clear()


def fake_docker_success(request, cancelled, *, export_dir):
    from app.docker_validation import execution_metadata
    export_dir.mkdir()
    raw = b"<div id='root'></div>"
    (export_dir / "index.html").write_bytes(raw)
    fingerprint = validation.digest({"index.html": hashlib.sha256(raw).hexdigest()})
    return ProfileExecutionResult("passed", [{"kind": kind, "command": "fixed docker " + kind,
        "status": "passed", "exitCode": 0, "log": "fixed"} for kind in ("check", "build", "test")],
        {**execution_metadata(request), "commandsBackend": "docker", "contextFingerprint": "c" * 64}, fingerprint)


def test_default_native_keeps_existing_runner_hooks(fixture, monkeypatch):
    db, run, root = launch(fixture)
    seen = []
    def validator(path, cancelled, **kwargs):
        seen.append(path)
        return native_result(path, cancelled, **kwargs)
    monkeypatch.setattr(validation, "validate_copy", validator)
    asyncio.run(validation.run_automatic_validation(db, run))
    receipt = validation.validation_for_run(db, run.id)
    assert seen == [root] and receipt["status"] == "passed"
    assert receipt["execution"]["backend"] == "native" and receipt["execution"]["commandsBackend"] == "native"
    assert receipt["nativePolicyFingerprint"] == validation.capture_validation_source(root)[0]["policyFingerprint"]
    assert validation.validation_currentness(db, run.id, receipt) == "current"
    forged = {**receipt, "nativePolicyFingerprint": "0" * 64}
    assert validation.validation_currentness(db, run.id, forged) == "unverifiable"


def test_explicit_docker_unavailable_does_not_run_native(fixture, monkeypatch):
    db, run, _ = launch(fixture)
    docker_settings(monkeypatch)
    def forbidden(*args, **kwargs): pytest.fail("Docker must not fall back to native")
    monkeypatch.setattr(validation, "validate_copy", forbidden)
    from app import docker_validation
    monkeypatch.setattr(docker_validation.shutil, "which", lambda _: None)
    asyncio.run(validation.run_automatic_validation(db, run))
    receipt = validation.validation_for_run(db, run.id)
    assert receipt["status"] == "unavailable" and receipt["commands"] == []
    assert receipt["execution"]["backend"] == "docker" and receipt["execution"]["commandsBackend"] == "not_run"


def test_invalid_launch_identity_finishes_as_unavailable_without_running(fixture, monkeypatch):
    db, run, _ = launch(fixture)
    docker_settings(monkeypatch)
    metrics = json.loads(run.metrics_json)
    metrics["taskRunExecutionAccessBinding"]["taskId"] = "another-task"
    run.metrics_json = json.dumps(metrics); db.add(run); db.commit()
    def forbidden(*args, **kwargs): pytest.fail("Invalid launch ran validation")
    monkeypatch.setattr(validation, "validate_copy", forbidden)
    asyncio.run(validation.run_automatic_validation(db, run))
    receipt = validation.validation_for_run(db, run.id)
    assert receipt["status"] == "unavailable" and receipt["commands"] == []
    assert receipt["execution"]["commandsBackend"] == "not_run"


@pytest.mark.parametrize("adapter", ["codex", "claude_code", "scripted_mock"])
def test_all_three_adapters_reach_same_post_execution_boundary(fixture, monkeypatch, adapter):
    from app.models import Agent
    db, run, _ = launch(fixture)
    agent = db.get(Agent, run.agent_id)
    agent.adapter_type = adapter
    db.add(agent); db.commit()
    monkeypatch.setattr(validation, "validate_copy", native_result)
    asyncio.run(validation.run_automatic_validation(db, run))
    assert validation.validation_for_run(db, run.id)["execution"]["commandsBackend"] == "native"


def test_lease_loss_during_container_run_never_publishes_completed(fixture, monkeypatch):
    from app.docker_validation import DockerValidationBackend
    db, run, _ = launch(fixture)
    docker_settings(monkeypatch)
    entered, cancelled_seen = threading.Event(), threading.Event()
    owned = True
    def slow(self, request, cancelled, **kwargs):
        entered.set()
        if cancelled.wait(3): cancelled_seen.set()
        return ProfileExecutionResult("cancelled", [], {})
    monkeypatch.setattr(DockerValidationBackend, "execute", slow)
    async def exercise():
        nonlocal owned
        operation = asyncio.create_task(validation.run_automatic_validation(db, run, ownership_guard=lambda: owned))
        for _ in range(100):
            if entered.is_set(): break
            await asyncio.sleep(0.01)
        assert entered.is_set()
        owned = False
        await asyncio.wait_for(operation, timeout=2)
    asyncio.run(exercise())
    assert cancelled_seen.is_set()
    assert not db.exec(select(TaskRunEvent).where(TaskRunEvent.event_type == "validation.completed")).all()


def test_native_receipt_cannot_be_relabelled_docker(fixture, monkeypatch):
    db, run, _ = launch(fixture)
    monkeypatch.setattr(validation, "validate_copy", native_result)
    asyncio.run(validation.run_automatic_validation(db, run))
    receipt = validation.validation_for_run(db, run.id)
    receipt["execution"]["backend"] = "docker"
    assert validation.validation_currentness(db, run.id, receipt) == "unverifiable"


def test_other_launch_binding_cannot_supply_validation(fixture, monkeypatch):
    db, run, _ = launch(fixture)
    monkeypatch.setattr(validation, "validate_copy", native_result)
    asyncio.run(validation.run_automatic_validation(db, run))
    receipt = validation.validation_for_run(db, run.id)
    metrics = json.loads(run.metrics_json)
    metrics["taskRunExecutionAccessBinding"]["executionAttemptId"] = "different-attempt"
    run.metrics_json = json.dumps(metrics); db.add(run); db.commit()
    assert validation.validation_currentness(db, run.id, receipt) == "unverifiable"


def test_terminal_runner_rotation_does_not_invalidate_matching_frozen_launch_binding(fixture, monkeypatch):
    db, run, _ = launch(fixture)
    monkeypatch.setattr(validation, "validate_copy", native_result)
    asyncio.run(validation.run_automatic_validation(db, run))
    receipt = validation.validation_for_run(db, run.id)
    run.state, run.runner_id = "completed", "rotated-terminal-runner"
    db.add(run); db.commit()
    assert receipt["execution"]["generationFingerprint"]
    assert validation.validation_currentness(db, run.id, receipt) == "current"


def test_image_or_policy_change_expires_receipt_without_writing_old_rows(fixture, monkeypatch):
    from app.docker_validation import DockerValidationBackend
    db, run, _ = launch(fixture)
    docker_settings(monkeypatch)
    monkeypatch.setattr(DockerValidationBackend, "execute", lambda self, *args, **kwargs: fake_docker_success(*args, **kwargs))
    asyncio.run(validation.run_automatic_validation(db, run))
    receipt = validation.validation_for_run(db, run.id)
    event = db.get(TaskRunEvent, receipt["eventId"])
    original = event.payload_json
    assert validation.validation_currentness(db, run.id, receipt) == "current"
    monkeypatch.setenv("AGENTHUB_VALIDATION_FRONTEND_IMAGE_ID", "sha256:" + "d" * 64)
    get_settings.cache_clear()
    assert validation.validation_currentness(db, run.id, receipt) == "expired"
    assert db.get(TaskRunEvent, event.id).payload_json == original


def test_legacy_execution_missing_is_readable_without_docker_probe(fixture, monkeypatch):
    db, run, root, _ = fixture
    receipt, event = make_receipt(db, run, root)
    original = event.payload_json
    def forbidden(*args): pytest.fail("Read-only currentness probed Docker")
    from app import sandbox_cli
    monkeypatch.setattr(sandbox_cli, "docker_json", forbidden)
    assert validation.validation_currentness(db, run.id, receipt) == "current"
    assert "execution" not in receipt and event.payload_json == original


def test_legacy_receipt_under_docker_policy_expires_without_relabeling(fixture, monkeypatch):
    db, run, root, _ = fixture
    receipt, event = make_receipt(db, run, root)
    original = event.payload_json
    docker_settings(monkeypatch)
    assert validation.validation_currentness(db, run.id, receipt) == "expired"
    assert "execution" not in receipt and event.payload_json == original


def test_missing_native_browser_leaves_docker_commands_passed_but_qa_incomplete(fixture, monkeypatch):
    from app.docker_validation import DockerValidationBackend
    from app.models import Artifact
    db, run, _ = launch(fixture)
    task = db.get(Task, run.task_id)
    plan = json.loads(task.plan_json)
    plan.update(target="demo_heading_text", targetText="hello")
    task.plan_json = json.dumps(plan); db.add(task); db.commit()
    docker_settings(monkeypatch)
    monkeypatch.setattr(DockerValidationBackend, "execute", lambda self, *a, **kw: fake_docker_success(*a, **kw))
    browser = importlib.import_module("app.validation_browser")
    monkeypatch.setattr(browser.shutil, "which", lambda _: None)
    asyncio.run(validation.run_automatic_validation(db, run, requirement_contract=validation.contract_for_plan(plan)))
    receipt = validation.validation_for_run(db, run.id)
    assert receipt["status"] == "incomplete" and all(c["status"] == "passed" for c in receipt["commands"])
    assert receipt["functional"]["status"] == "unavailable"
    assert receipt["functional"]["execution"]["backend"] == "native"
    artifact = Artifact(task_run_id=run.id, artifact_type="diff", title="Diff", status="ready")
    qa = build_qa_assessment(db, artifact, plan=plan, files=[SOURCE], patch="", findings=[], model_status="passed", input_fingerprint="bound")
    assert qa["status"] == "incomplete" and qa["acceptance"] == "not_established"


def test_export_fingerprint_binds_native_browser_result(tmp_path):
    browser = importlib.import_module("app.validation_browser")
    output = tmp_path / "dist"
    output.mkdir(); (output / "index.html").write_bytes(b"hello")
    contract = {"schemaVersion": "agenthub.requirement_validation.v1", "target": "demo_heading_text", "expectedText": "hello"}
    def unavailable(argv, cwd, env, cancelled):
        assert env["AGENTHUB_VALIDATION_OUTPUT"] == str(output)
        return {"status": "failed", "exitCode": 1, "log": "", "durationMs": 1}
    result = browser.run_browser_validation(output, contract, threading.Event(), runner=unavailable)
    assert result["execution"] == {"backend": "native", "inputArtifactFingerprint":
        "fcda49694040218a63b93a6933c106cce48b05017965edb15a6098841e6948f9"}
@pytest.mark.parametrize("backend,base_policy,profile,recovered", [
    ("native", "a" * 64, "fastapi-contract-v1", True),
    ("docker", "a" * 64, "fastapi-contract-v1", False),
    ("native", "c" * 64, "fastapi-contract-v1", False),
    ("native", "a" * 64, "vite-build-smoke-v1", False),
])
def test_legacy_repair_policy_recovery_requires_same_native_checks(backend, base_policy, profile, recovered):
    from app import review_repairs
    previous = {"profile": "fastapi-contract-v1", "policyFingerprint": "a" * 64}
    current = {"profile": profile, "policyFingerprint": "b" * 64,
               "nativePolicyFingerprint": base_policy, "execution": {"backend": backend}}
    assert review_repairs.same_validation_policy(previous, current) is recovered
