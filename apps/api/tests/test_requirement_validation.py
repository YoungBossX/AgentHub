import asyncio
import json
import shutil
import threading

import pytest

from app.automatic_validation import validate_copy, validation_for_run, validation_currentness, digest
from app.requirement_validation import VERSION, requirement_contract, check_ids, parse_browser_result
from app.scripted_mock import _replace_login_slot, _replace_demo_heading_text, _replace_primary_button_text
from app.worktrees import repo_root
from app.models import Artifact, Task, TaskRun
from app.events import append_task_run_event
from app.qa_assessment import build_qa_assessment, current_qa_assessment
from test_native_review_artifacts import fixture
from test_scripted_mock_adapter import db as mock_db


@pytest.fixture
def app_copy(tmp_path):
    root = tmp_path / "source"
    copy_app(root)
    return root


def copy_app(root):
    platform = repo_root()
    shutil.copytree(platform / "apps/demo", root / "apps/demo", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("node_modules", "dist"))
    for name in ("package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml"):
        shutil.copyfile(platform / name, root / name)


def contract(target="login_page", text=None):
    return requirement_contract({"targetId": "demo-frontend", "target": target, "targetText": text})


@pytest.mark.parametrize("plan", [{}, {"targetId": "external", "target": "login_page"},
    {"targetId": "demo-frontend", "target": {"target": "login_page"}},
    {"targetId": "demo-frontend", "target": "arbitrary"},
    {"targetId": "demo-frontend", "target": "demo_heading_text", "targetText": " "},
    {"targetId": "demo-frontend", "target": "demo_heading_text", "targetText": "x" * 257}])
def test_unsupported_contracts_are_not_guessed(plan):
    assert requirement_contract(plan) is None


def test_contract_is_frozen_and_never_uses_plan_scripts():
    plan = {"targetId": "demo-frontend", "target": "demo_heading_text", "targetText": "Hello", "script": "unsafe", "selector": "body"}
    frozen = requirement_contract(plan)
    plan["targetText"] = "Changed"
    assert frozen == {"schemaVersion": VERSION, "target": "demo_heading_text", "expectedText": "Hello"}


@pytest.mark.parametrize("tamper", ["exit", "omitted", "duplicate", "contract", "malformed", "timeout"])
def test_browser_receipts_require_exact_coverage_and_successful_process(tamper):
    frozen = contract()
    report = {"schemaVersion": VERSION, "contract": frozen, "status": "passed",
              "checks": [{"id": key, "status": "passed"} for key in check_ids(frozen)]}
    result = {"status": "passed", "exitCode": 0, "durationMs": 1}
    if tamper == "exit": result["exitCode"] = 1
    if tamper == "omitted": report["checks"].pop()
    if tamper == "duplicate": report["checks"][-1] = report["checks"][0]
    if tamper == "contract": report["contract"] = contract("demo_heading_text", "wrong")
    if tamper == "timeout": result["status"] = "timeout"
    result["log"] = "console says passed" if tamper == "malformed" else json.dumps(report)
    assert parse_browser_result(result, frozen)["status"] == "unavailable"


@pytest.mark.parametrize("case", ["login", "heading", "button", "wrong_text", "disabled", "missing_required", "runtime_error", "network"])
def test_real_browser_requirement_checks(app_copy, case):
    path = app_copy / "apps/demo/src/App.tsx"
    source = path.read_text(encoding="utf-8")
    text = '继续 <review> & {demo} "ok"'
    if case in {"login", "missing_required"}:
        source = _replace_login_slot(source)
        frozen = contract()
        if case == "missing_required": source = source.replace(" required", "")
    elif case == "heading":
        source = _replace_demo_heading_text(source, text)
        frozen = contract("demo_heading_text", text)
    else:
        source = _replace_primary_button_text(source, text)
        frozen = contract("primary_action_button_text", "wrong" if case == "wrong_text" else text)
        if case == "disabled": source = source.replace('type="button"', 'type="button" disabled')
        if case == "runtime_error": source = 'throw new Error("runtime fixture");\n' + source
        if case == "network": source = 'void fetch("https://example.invalid/blocked").catch(() => {});\n' + source
    path.write_text(source, encoding="utf-8")
    before = path.read_bytes()
    result = validate_copy(app_copy, threading.Event(), requirement_contract=frozen)
    assert all(command["status"] == "passed" for command in result["commands"]), result["commands"]
    expected = "passed" if case in {"login", "heading", "button"} else "failed"
    assert result["status"] == expected, result["functional"]
    assert result["functional"]["status"] == expected
    assert len(result["functional"]["checks"]) == len(check_ids(frozen))
    assert result["functional"]["browserVersion"] != "unknown"
    assert path.read_bytes() == before


def test_missing_browser_does_not_downgrade_to_smoke_success(app_copy, monkeypatch):
    monkeypatch.setenv("AGENTHUB_VALIDATION_BROWSER_CHANNEL", "unsupported-browser")
    result = validate_copy(app_copy, threading.Event(), requirement_contract=contract())
    assert result["status"] == "incomplete" and result["functional"]["status"] == "unavailable"
    assert result["functional"]["diagnosticCode"] == "browser_configuration_failed"
    assert all(command["status"] == "passed" for command in result["commands"])


@pytest.mark.parametrize("code", ["browser_sandbox_unavailable", "browser_missing", "browser_launch_failed",
    "browser_configuration_failed", "browser_execution_failed", "contract_failed", "private host path", {}])
def test_unavailable_browser_exposes_only_known_diagnostics(code):
    frozen = contract()
    report = {"schemaVersion": VERSION, "contract": frozen, "status": "unavailable",
              "diagnosticCode": code, "reason": "private host path", "checks": []}
    result = parse_browser_result({"status": "failed", "exitCode": 2, "log": json.dumps(report)}, frozen)
    assert result["status"] == "unavailable" and result["checks"] == []
    assert "private host path" not in json.dumps(result)
    if isinstance(code, str) and (code.startswith("browser_") or code == "contract_failed"):
        assert result["diagnosticCode"] == code
    else:
        assert "diagnosticCode" not in result


def test_browser_is_not_started_after_build_failure(app_copy):
    calls = []
    def runner(argv, *_args):
        calls.append(argv)
        return {"status": "failed", "exitCode": 1, "log": "failure", "durationMs": 0}
    result = validate_copy(app_copy, threading.Event(), runner=runner, requirement_contract=contract())
    assert len(calls) == 1 and result["functional"]["status"] == "not_run"


def test_cancellation_during_browser_phase_cannot_pass(app_copy):
    cancelled = threading.Event()
    calls = []
    def runner(argv, *_args):
        calls.append(argv)
        if len(calls) == 4:
            cancelled.set()
            return {"status": "cancelled", "exitCode": -1, "log": "", "durationMs": 1}
        return {"status": "passed", "exitCode": 0, "log": "", "durationMs": 1}
    result = validate_copy(app_copy, cancelled, runner=runner, requirement_contract=contract())
    assert len(calls) == 4 and result["status"] == "cancelled"
    assert result["functional"]["status"] != "passed"


@pytest.mark.parametrize("status", ["passed", "failed", "unavailable"])
def test_requirement_results_bind_plan_and_do_not_rewrite_snapshot(fixture, status):
    from app.automatic_validation import capture_validation_source
    db, run, root, _ = fixture
    copy_app(root)
    task = db.get(Task, run.task_id)
    plan = {"targetId": "demo-frontend", "target": "demo_heading_text", "targetText": "Hello"}
    task.plan_json = json.dumps(plan); run.state = "completed"
    db.add_all([task, run]); db.commit()
    frozen = requirement_contract(plan)
    value = {**capture_validation_source(root)[0], "schemaVersion": "agenthub.validation.v1", "status": "incomplete" if status == "unavailable" else status,
             "taskRunId": run.id, "adapterRunId": run.adapter_run_id, "requirementFingerprint": digest(frozen),
             "functional": {"status": status, "contract": frozen, "checks": []},
             "commands": [{"kind": kind, "command": kind, "exitCode": 0, "status": "passed"} for kind in ("check", "test", "build")]}
    append_task_run_event(db, task_run_id=run.id, event_type="validation.completed", payload_json=json.dumps(value))
    diff = Artifact(task_run_id=run.id, artifact_type="diff", title="diff", status="ready")
    qa = build_qa_assessment(db, diff, plan=plan, files=["apps/demo/src/App.tsx"], patch="", findings=[], model_status="passed", input_fingerprint="native-bound")
    assert qa["acceptance"] == ("requirement_checks_passed" if status == "passed" else "not_established")
    assert qa["status"] == {"passed": "passed", "failed": "blocked", "unavailable": "incomplete"}[status]
    plan["targetText"] = "Changed"; task.plan_json = json.dumps(plan); db.add(task); db.commit()
    assert validation_currentness(db, run.id, validation_for_run(db, run.id)) == "expired"
    current = current_qa_assessment(db, qa)
    assert current["status"] == "expired"
    assert current["functional"]["status"] == ("unavailable" if status == "unavailable" else "expired")
    assert qa["functional"]["status"] == status


def test_scripted_execution_runs_real_browser_acceptance(mock_db, app_copy, monkeypatch):
    import subprocess
    from app.models import Agent, Session, Workspace
    from app.task_runs import create_task_run
    from app.scripted_mock import ScriptedMockAdapter
    from app.run_engine import execute_task_run
    from app.run_supervisor import RunSupervisor
    from app.reviews import list_task_run_reviews
    import app.run_engine as engine
    # Only preview/deploy side effects are excluded; actual adapter writes, scope,
    # Diff, build, browser and stored QA run through the production lifecycle.
    monkeypatch.setattr(engine, "_maybe_auto_preview_and_mock_deploy", lambda *args: None)
    subprocess.run(["git", "init", "-q", str(app_copy)], check=True)
    subprocess.run(["git", "-C", str(app_copy), "add", "."], check=True)
    subprocess.run(["git", "-C", str(app_copy), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                    "-c", "core.hooksPath=", "commit", "-qm", "requirement fixture"], check=True)
    workspace = Workspace(name="Requirements", root_path="apps/demo", repo_url="local://apps/demo", default_branch="main")
    session = Session(workspace_id=workspace.id, title="Requirements", bound_branch="main", worktree_path=str(app_copy))
    agent = Agent(name="Frontend", role="frontend", adapter_type="scripted_mock", provider="local")
    task = Task(session_id=session.id, title="Build login page", intent_type="frontend_change", assigned_agent_id=agent.id,
                plan_json=json.dumps({"targetId": "demo-frontend", "target": "login_page", "files": ["apps/demo/src/App.tsx", "apps/demo/src/styles.css"]}))
    mock_db.add_all([workspace, session, agent, task]); mock_db.commit()
    run = create_task_run(mock_db, task.id)
    assert engine._prepare_claimed_task_run_for_adapter(mock_db, run, run.runner_id)
    completed = asyncio.run(execute_task_run(mock_db, run, adapter_type="scripted_mock", adapter=ScriptedMockAdapter(), supervisor=RunSupervisor()))
    assert completed.state == "completed", completed.error_message
    report = list_task_run_reviews(mock_db, run.id)[0]
    assert report.qa_assessment["functional"]["status"] == "passed"
    assert report.qa_assessment["functional"]["contract"] == contract()
    assert report.qa_assessment["model"]["status"] == "not_run"
    assert report.qa_assessment["acceptance"] == "not_established"
