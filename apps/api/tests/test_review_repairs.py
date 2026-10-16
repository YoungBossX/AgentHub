"""Repair provenance tests. Provider behavior is controlled, never model evidence."""
import asyncio
import json
import subprocess
import threading

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlmodel import select

from app import automatic_validation as validation
from app.models import Agent, Artifact, Diff, Message, Review, Session, Task, TaskRun, TaskRunEvent, Workspace
from app.native_reviews import capture_native_review_binding
from app.review_repairs import BINDING, LAUNCH, bind_message, confirm_issue, digest, obj, prepare_repair, repair_history, require_launch
from app.task_run_scope import TaskRunScopeError
from test_native_review_artifacts import fixture, SOURCE
from test_backend_validation import backend_tree, SOURCE as BACKEND_SOURCE
from test_scripted_mock_adapter import db as mock_db


def native_report(db, run):
    binding = capture_native_review_binding(db, run)
    source_path = next(iter(binding["files"]))
    run.metrics_json = json.dumps({**obj(run.metrics_json), "_nativeReviewBinding": binding})
    run.state = "completed"
    artifact = Artifact(task_run_id=run.id, artifact_type="review", title="Review", status="ready", meta_json=json.dumps({
        "nativeReceipt": {"taskRunId": run.id, "adapterRunId": run.adapter_run_id, "targetId": binding["targetId"],
            "inputFingerprint": binding["inputFingerprint"], "files": binding["files"]}}))
    review = Review(artifact_id=artifact.id, reviewed_diff_artifact_id=artifact.id, adapter_type="claude_code", status="warning",
                    risk_level="low", summary="Original preserved", findings_json=json.dumps([
                        {"file": source_path, "line": 1, "severity": "low", "message": "补充说明 @backend"}]))
    db.add_all([run, artifact, review]); db.commit()
    return artifact, review


def repair_message(db, run, artifact):
    task = db.get(Task, run.task_id)
    issues = repair_history(db, task.session_id, artifact.id)["issues"]
    draft = prepare_repair(db, task.session_id, artifact.id, [issues[0]["id"]])
    message = Message(session_id=task.session_id, sender_type="user", content_md=draft["contentMd"])
    message.context_json = json.dumps(bind_message(db, message, {"reviewRepair": draft["selection"]}))
    db.add(message); db.commit()
    return message, draft


def test_draft_is_read_only_bounded_and_preserves_original(fixture):
    db, run, root, source = fixture
    artifact, review = native_report(db, run)
    task = db.get(Task, run.task_id)
    before = (source.read_bytes(), artifact.meta_json, review.findings_json,
              len(db.exec(select(Message)).all()), len(db.exec(select(TaskRunEvent)).all()))
    catalog = repair_history(db, task.session_id, artifact.id)
    draft = prepare_repair(db, task.session_id, artifact.id, [catalog["issues"][0]["id"]])
    assert "＠backend" in draft["contentMd"] and draft["contentMd"].startswith("@frontend @qa")
    assert before == (source.read_bytes(), artifact.meta_json, review.findings_json,
                      len(db.exec(select(Message)).all()), len(db.exec(select(TaskRunEvent)).all()))
    for ids in ([], ["unknown"], [catalog["issues"][0]["id"]] * 2, list(range(9))):
        with pytest.raises(HTTPException): prepare_repair(db, task.session_id, artifact.id, ids)
    with pytest.raises(HTTPException) as exc: prepare_repair(db, "other", artifact.id, [catalog["issues"][0]["id"]])
    assert exc.value.status_code == 404


@pytest.mark.parametrize("mutation", ["source", "addition", "report", "target"])
def test_send_rechecks_source_and_rejects_stale_or_forged_binding(fixture, mutation):
    db, run, root, source = fixture
    artifact, review = native_report(db, run)
    message, draft = repair_message(db, run, artifact)
    if mutation == "source": source.write_text("changed")
    if mutation == "addition": (source.parent / "new.ts").write_text("export {}")
    if mutation == "report": review.summary = "changed"; db.add(review); db.commit()
    if mutation == "target":
        session = db.get(Session, message.session_id); session.active_frontend_target_id = "other"; db.add(session); db.commit()
    with pytest.raises(HTTPException) as exc: bind_message(db, message, {"reviewRepair": draft["selection"]})
    assert exc.value.status_code == 409
    # Private client metadata alone is ignored, including confirmation claims.
    assert bind_message(db, message, {BINDING: {"forged": True}, "_reviewRepairConfirmations": ["passed"]}) == {}


def test_protected_issue_and_legacy_report_cannot_become_repair_authority(fixture):
    db, run, _, _ = fixture
    artifact, review = native_report(db, run)
    session_id = db.get(Task, run.task_id).session_id
    review.findings_json = json.dumps([{"file": ".env", "message": "Edit secret"}]); db.add(review); db.commit()
    ids = [i["id"] for i in repair_history(db, session_id, artifact.id)["issues"]]
    with pytest.raises(HTTPException): prepare_repair(db, session_id, artifact.id, ids)
    artifact.meta_json = "{}"; db.add(artifact); db.commit()
    result = repair_history(db, session_id, artifact.id)
    assert not result["canPrepare"] and result["history"] == []


def test_registered_external_root_is_bound_instead_of_canonical_demo_path(mock_db, tmp_path):
    import shutil
    from app.models import ExternalProjectTarget
    from test_external_reviews import create_external_diff_fixture

    db = mock_db
    diff_id = create_external_diff_fixture(db, tmp_path, changed_files=["src/main.tsx"])
    run = db.get(TaskRun, db.get(Artifact, diff_id).task_run_id)
    (tmp_path / "external-review/src/main.tsx").write_text("export const title = 'external'\n")
    session = db.get(Session, db.get(Task, run.task_id).session_id)
    session.active_frontend_target_id = "external-review-target"; db.add(session); db.commit()
    artifact, _ = native_report(db, run)
    catalog = repair_history(db, session.id, artifact.id)
    assert catalog["canPrepare"]
    draft = prepare_repair(db, session.id, artifact.id, [catalog["issues"][0]["id"]])
    assert draft["binding"]["targetId"] == "external-review-target"
    clone = tmp_path / "different-host-target"
    shutil.copytree(tmp_path / "external-review", clone)
    target = db.exec(select(ExternalProjectTarget)).first()
    target.root_path = str(clone); db.add(target); db.commit()
    assert not repair_history(db, session.id, artifact.id)["canPrepare"]
    with pytest.raises(HTTPException): prepare_repair(db, session.id, artifact.id, draft["selection"]["issueIds"], draft["selection"]["expectedFingerprint"])


def test_launch_rechecks_source_target_and_explicit_retry_keeps_new_base(fixture, monkeypatch):
    db, old, _, source = fixture
    artifact, _ = native_report(db, old)
    message, _ = repair_message(db, old, artifact)
    task = Task(session_id=message.session_id, created_by_message_id=message.id, title="Repair", intent_type="frontend_change",
                assigned_agent_id=old.agent_id, plan_json=json.dumps({"targetId": "demo-frontend"}))
    run = TaskRun(task_id=task.id, agent_id=old.agent_id, state="running", worktree_path=old.worktree_path)
    db.add_all([task, run]); db.commit()
    monkeypatch.setattr("app.task_runs.require_task_run_execution_access_mode", lambda *a, **k: "write")
    source.write_text("changed")
    with pytest.raises(TaskRunScopeError) as exc: require_launch(db, run, task)
    assert exc.value.error_code == "REVIEW_REPAIR_SOURCE_CHANGED" and LAUNCH not in obj(run.metrics_json)
    source.write_text('export const title = "review input"\n')
    require_launch(db, run, task)
    original = obj(run.metrics_json)[LAUNCH]
    source.write_text("partial unsuccessful repair")
    run.state = "failed"; db.add(run); db.commit()
    retry = TaskRun(task_id=task.id, agent_id=old.agent_id, state="running", worktree_path=old.worktree_path,
                    metrics_json=json.dumps({"retryOfRunId": run.id, "retryMode": "current_state"}))
    db.add(retry); db.commit(); require_launch(db, retry, task)
    receipt = obj(retry.metrics_json)[LAUNCH]
    assert receipt["previousRunId"] == run.id and receipt["source"] != original["source"]
    task.plan_json = json.dumps({"targetId": "demo-backend"}); db.add(task); db.commit()
    with pytest.raises(TaskRunScopeError): require_launch(db, retry, task)


def test_unvalidated_retry_cannot_adopt_changed_source_and_readonly_has_no_write_receipt(fixture, monkeypatch):
    db, old, _, source = fixture
    artifact, _ = native_report(db, old)
    message, _ = repair_message(db, old, artifact)
    task = Task(session_id=message.session_id, created_by_message_id=message.id, title="Repair", intent_type="frontend_change",
                assigned_agent_id=old.agent_id, plan_json=json.dumps({"targetId": "demo-frontend"}))
    run = TaskRun(task_id=task.id, agent_id=old.agent_id, state="running", worktree_path=old.worktree_path,
                  metrics_json=json.dumps({"retryOfRunId": old.id, "retryMode": "current_state"}))
    db.add_all([task, run]); db.commit(); source.write_text("changed")
    monkeypatch.setattr("app.task_runs.require_task_run_execution_access_mode", lambda *a, **k: "write")
    with pytest.raises(TaskRunScopeError): require_launch(db, run, task)
    monkeypatch.setattr("app.task_runs.require_task_run_execution_access_mode", lambda *a, **k: "readonly")
    require_launch(db, run, task)
    assert LAUNCH not in obj(run.metrics_json)


def test_regeneration_rebinds_message_but_does_not_reuse_confirmation(fixture):
    from app.review_repairs import rebind_message
    db, old, _, source = fixture
    artifact, _ = native_report(db, old)
    message, _ = repair_message(db, old, artifact)
    created = Message(session_id=message.session_id, sender_type="user", content_md=message.content_md)
    rebind_message(db, message, created)
    assert obj(created.context_json)[BINDING]["messageId"] == created.id
    assert "_reviewRepairConfirmations" not in obj(created.context_json)
    source.write_text("changed")
    with pytest.raises(HTTPException): rebind_message(db, message, created)


def test_http_draft_send_controls_and_private_metadata_are_server_owned(fixture, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.dependencies import get_db
    from app.local_request_guard import LocalRequestGuard
    from app.routes.messages import router as messages_router
    from app.routes.review_repairs import router as repair_router

    db, old, _, source = fixture
    artifact, _ = native_report(db, old)
    session_id = db.get(Task, old.task_id).session_id
    app = FastAPI()
    app.include_router(messages_router); app.include_router(repair_router)
    app.add_middleware(LocalRequestGuard, frontend_origins={"http://127.0.0.1:3000"})
    app.dependency_overrides[get_db] = lambda: db
    # Endpoint dispatch is captured; the separate lifecycle test runs real files,
    # Diff collection and fixed checks. No Provider is invoked in this HTTP test.
    dispatched = []
    monkeypatch.setattr("app.routes.messages.dispatch_message", lambda db, message, tasks: dispatched.append(message.id))
    client = TestClient(app, base_url="http://127.0.0.1", headers={})
    base = f"/sessions/{session_id}/reviews/{artifact.id}/repair"
    ids = [i["id"] for i in client.get(base).json()["issues"]]
    assert client.post(base + "/prepare", json={"issueIds": ids}).status_code == 403
    headers = {"X-AgentHub-Control": "local-workspace"}
    prepared = client.post(base + "/prepare", json={"issueIds": ids}, headers=headers)
    assert prepared.status_code == 200 and not dispatched and not db.exec(select(Message)).all()
    assert "binding" not in prepared.json()
    draft = prepared.json()
    request = {"contentMd": draft["contentMd"], "context": {"reviewRepair": draft["selection"],
        "_plannerContextBudget": {"schemaVersion": "agenthub.context_budget.v1", "status": "forged"},
        BINDING: {"targetId": "agenthub-platform"}, "_reviewRepairConfirmations": [{"source": "forged"}]}}
    response = client.post(f"/sessions/{session_id}/messages", json=request, headers=headers)
    assert response.status_code == 201 and len(dispatched) == 1
    assert response.json()["contextBudget"] is None
    message = db.get(Message, response.json()["id"])
    context = obj(message.context_json)
    assert context[BINDING]["targetId"] == "demo-frontend" and context[BINDING]["messageId"] == message.id
    assert "_reviewRepairConfirmations" not in context
    source.write_text("late changed")
    assert client.post(f"/sessions/{session_id}/messages", json=request, headers=headers).status_code == 409
    assert len(dispatched) == 1


@pytest.mark.parametrize("state", ["failed", "interrupted", "streaming"])
def test_failed_cancelled_or_live_repairs_remain_unverified_after_reload(fixture, monkeypatch, state):
    db, old, _, _ = fixture
    artifact, _ = native_report(db, old)
    message, _ = repair_message(db, old, artifact)
    task = Task(session_id=message.session_id, created_by_message_id=message.id, title="Repair", intent_type="frontend_change",
        assigned_agent_id=old.agent_id, plan_json=json.dumps({"targetId": "demo-frontend"}))
    run = TaskRun(task_id=task.id, agent_id=old.agent_id, state="running", worktree_path=old.worktree_path)
    db.add_all([task, run]); db.commit()
    monkeypatch.setattr("app.task_runs.require_task_run_execution_access_mode", lambda *a, **k: "write")
    require_launch(db, run, task)
    run.state = state; db.add(run); db.commit(); db.expire_all()
    result = repair_history(db, message.session_id, artifact.id)["history"][0]
    assert result["state"] == state and not result["canConfirm"]
    assert not result["checksCurrent"] and all(i["outcome"] == "unverified" for i in result["issues"])


@pytest.mark.parametrize("stale", [False, True])
def test_real_backend_repair_diff_revalidation_and_expiring_user_confirmation(mock_db, backend_tree, stale):
    from app.adapters import AgentEvent
    from app.backend_validation import validate_backend_copy
    from app.events import append_task_run_event
    from app.qa_assessment import build_qa_assessment
    from app.run_engine import execute_task_run, _prepare_claimed_task_run_for_adapter
    from app.run_supervisor import RunSupervisor
    from app.scripted_mock import ScriptedMockAdapter
    from app.task_runs import create_task_run

    db = mock_db
    path = backend_tree / BACKEND_SOURCE
    good = path.read_bytes()
    path.write_bytes(good.replace(b'HealthResponse(status="ok"', b'HealthResponse(status="broken"', 1))
    assert path.read_bytes() != good
    subprocess.run(["git", "init", "-q", str(backend_tree)], check=True)
    subprocess.run(["git", "-C", str(backend_tree), "add", "."], check=True)
    subprocess.run(["git", "-C", str(backend_tree), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                    "-c", "core.hooksPath=", "commit", "-qm", "broken backend fixture"], check=True)
    workspace = Workspace(name="Repair", root_path="apps/demo-api", repo_url="local://apps/demo-api", default_branch="main")
    session = Session(workspace_id=workspace.id, title="Repair", bound_branch="main", worktree_path=str(backend_tree))
    agent = Agent(name="Backend", role="backend", adapter_type="scripted_mock", provider="local")
    original_task = Task(session_id=session.id, title="Original", intent_type="backend_change", status="completed", assigned_agent_id=agent.id,
                         plan_json=json.dumps({"targetId": "demo-backend", "assignedRole": "backend", "files": [BACKEND_SOURCE]}))
    db.add_all([workspace, session, agent, original_task]); db.commit()
    original = TaskRun(task_id=original_task.id, agent_id=agent.id, state="completed", worktree_path=str(backend_tree))
    db.add(original); db.commit()
    failed = validate_backend_copy(backend_tree, threading.Event())
    assert failed["status"] == "failed"
    failed.update(taskRunId=original.id, adapterRunId=original.adapter_run_id)
    append_task_run_event(db, task_run_id=original.id, event_type="validation.completed", payload_json=json.dumps(failed))
    old_diff = Artifact(task_run_id=original.id, artifact_type="diff", title="Old", status="ready")
    qa = build_qa_assessment(db, old_diff, plan={"targetId": "demo-backend"}, files=[BACKEND_SOURCE], patch="", findings=[])
    report = Artifact(task_run_id=original.id, artifact_type="review", title="Old review", status="ready", meta_json=json.dumps({"qaAssessment": qa}))
    review = Review(artifact_id=report.id, reviewed_diff_artifact_id=old_diff.id, adapter_type="scripted_mock", status="warning",
        risk_level="low", summary="Original failure", findings_json=json.dumps([{"file": BACKEND_SOURCE, "message": "人工核对接口说明"}]))
    db.add_all([old_diff, report, review]); db.commit()
    frozen = (report.meta_json, review.findings_json)
    catalog = repair_history(db, session.id, report.id)
    draft = prepare_repair(db, session.id, report.id, [i["id"] for i in catalog["issues"]])
    message = Message(session_id=session.id, sender_type="user", content_md=draft["contentMd"])
    message.context_json = json.dumps(bind_message(db, message, {"reviewRepair": draft["selection"]}))
    task = Task(session_id=session.id, created_by_message_id=message.id, title="Repair health", intent_type="backend_change",
                assigned_agent_id=agent.id, plan_json=original_task.plan_json)
    db.add_all([message, task]); db.commit()
    run = create_task_run(db, task.id)
    assert _prepare_claimed_task_run_for_adapter(db, run, run.runner_id)

    started = []
    class RepairWriter(ScriptedMockAdapter):
        async def createRun(self, request):
            started.append(request.task_run_id)
            return await super().createRun(request)

        async def streamEvents(self, run_id):
            request = self._request_for(run_id)
            yield AgentEvent(type="task.state", taskRunId=request.task_run_id, sequence=1, payload={"state": "streaming"})
            path.write_bytes(good)
            yield AgentEvent(type="completed", taskRunId=request.task_run_id, sequence=2, payload={"changedFiles": [BACKEND_SOURCE]})

    if stale:
        path.write_bytes(path.read_bytes() + b"\n# changed while queued\n")
    completed = asyncio.run(execute_task_run(db, run, adapter_type="scripted_mock", adapter=RepairWriter(), supervisor=RunSupervisor()))
    if stale:
        assert completed.state == "failed" and completed.error_code == "REVIEW_REPAIR_SOURCE_CHANGED"
        assert not started and LAUNCH not in obj(completed.metrics_json)
        assert not repair_history(db, session.id, report.id)["history"][0]["canConfirm"]
        return
    assert completed.state == "completed", (completed.error_code, completed.error_message)
    assert LAUNCH in obj(completed.metrics_json)
    history = repair_history(db, session.id, report.id)
    entry = history["history"][0]
    assert entry["checksCurrent"] and entry["canConfirm"]
    assert any(i["outcome"] == "checks_recovered" for i in entry["issues"])
    advisory = next(i for i in entry["issues"] if i["kind"] == "finding")
    assert advisory["outcome"] == "unverified"
    history = confirm_issue(db, session.id, report.id, message.id, advisory["id"], entry["sourceFingerprint"], entry["revision"])
    assert history["history"][0]["issues"][0]["outcome"] == "user_confirmed"
    with pytest.raises(HTTPException): confirm_issue(db, session.id, report.id, message.id, advisory["id"], entry["sourceFingerprint"], entry["revision"])
    db.expire_all()  # read after persisted/restart boundary
    assert repair_history(db, session.id, report.id)["history"][0]["confirmations"]
    path.write_bytes(good + b"\n# subsequent change\n")
    entry = repair_history(db, session.id, report.id)["history"][0]
    assert not entry["checksCurrent"] and all(i["outcome"] == "unverified" for i in entry["issues"])
    assert entry["confirmations"] and not entry["canConfirm"]
    assert (db.get(Artifact, report.id).meta_json, db.get(Review, review.id).findings_json) == frozen
