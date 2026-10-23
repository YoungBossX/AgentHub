import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest
from sqlmodel import select

from app import workflow_evaluation as workflow
from app.claude_code_adapter import ClaudeCodeAdapter
from app.models import AgentProfileDraft, TaskRunEvent
from app.run_engine import execute_task_run
from app.run_supervisor import RunSupervisor
from app.workflow_cohort import cohort, invalidate, role_stats
from app.workflow_profiles import bound_scenario, configure_profiles
from app.workflow_review_evidence import attempt_seconds
from app.workflow_suite import select_scenarios
from test_native_review_artifacts import fixture, ReviewRunner, SOURCE
from test_workflow_scoring import valid_phase


@pytest.mark.parametrize("recover", [False, True])
def test_native_qa_profile_routes_through_real_readonly_parser_and_source_bound_artifact(tmp_path, monkeypatch, recover):
    from pathlib import Path
    from app import run_engine
    from app.provider_gateway import ProviderHealthResult
    from test_claude_code_adapter import FakeClaudeCodeProcess
    from test_workflow_evaluation import fake_planner, fake_writer
    scenario = select_scenarios("backend-repair")[0]
    fake_planner(monkeypatch); fake_writer(monkeypatch, scenario)
    calls = []
    class NativeRunner:
        def start(self, command, cwd, *, input_text=None):
            calls.append(True)
            instruction = json.loads(input_text)["message"]["content"][0]["text"] if input_text else command[-1]
            shape = json.loads(instruction.splitlines()[-1])
            name = "apps/demo-api/app/main.py"
            text = (Path(cwd) / name).read_text(encoding="utf-8")
            output = {**shape, "status": "passed", "riskLevel": "low", "summary": "Explicit native transport test double",
                "filesReviewed": [name], "findings": [], "suggestedChanges": [], "validation": "not_run"}
            events = [{"type": "system", "subtype": "init", "session_id": "test-native-qa"},
                {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", "id": "read-main", "input": {"file_path": str(Path(cwd) / name)}}]}},
                {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "read-main", "is_error": False}]},
                 "tool_use_result": {"type": "text", "file": {"filePath": str(Path(cwd) / name), "content": text,
                    "startLine": 1, "numLines": len(text.splitlines()), "totalLines": len(text.splitlines())}}},
                {"type": "result", "subtype": "success", "is_error": False, "result": json.dumps(output), "structured_output": output}]
            return FakeClaudeCodeProcess(stdout="\n".join(json.dumps(event) for event in events), returncode=1 if recover and len(calls) == 1 else 0)
    monkeypatch.setattr(run_engine, "ClaudeCodeAdapter", lambda *args, **kwargs: ClaudeCodeAdapter(*args, process_runner=NativeRunner(), **kwargs))
    monkeypatch.setattr(run_engine._provider_health_probe, "check_provider", lambda provider, **kwargs:
        ProviderHealthResult(provider.provider_id, provider.adapter_type, "healthy", True, "Explicit test double"))
    report = asyncio.run(workflow.run_benchmark(tmp_path / "native-flow", case_id=scenario.id, test_execution=True))
    case = report["cases"][0]
    assert case["verdict"] == "passed", case
    assert case["phases"][0]["requireNativeQa"] is True
    assert report["summary"]["nativeQaVerifiedAttempts"] == 1
    assert report["mode"] == "test_double" and report["summary"]["finalSuccessRate"] is None
    assert case["retryCount"] == int(recover) and case["firstAttemptPassed"] is (not recover)
    assert report["summary"]["roles"]["qa"]["retries"] == int(recover)
    if recover:
        decisions = case["phases"][0]["retryDecisions"]
        assert decisions[0]["reason"] == "natural_execution_failure" and not case["faultInjection"]


def native_phase():
    phase = valid_phase()
    writer = phase["attempts"][0]
    writer.update(taskRunId="write", providerAssignment={"adapterType": "codex"})
    writer["diffs"][0]["files"] = ["apps/demo-api/app/main.py"]
    phase.update(requireNativeQa=True, codingAdapter="codex", sourceHashes={"apps/demo-api/app/main.py": "current"})
    phase["attempts"].append({"taskRunId": "qa", "role": "qa", "targetId": "demo-backend", "state": "completed",
        "providerTurnObserved": True, "reviews": [{"taskRunId": "qa", "adapterType": "claude_code", "verifiedNativeReceipt": True,
            "status": "passed", "qaStatus": "passed", "model": {"source": "native", "status": "passed"},
            "currentness": "current", "filesReviewed": ["apps/demo-api/app/main.py"],
            "boundFiles": {"apps/demo-api/app/main.py": "current"}, "validation": {"sourceFingerprint": "current-source"}}]})
    return phase


@pytest.mark.parametrize("kind,gate", [
    ("missing", "missing"), ("scripted", "native_receipt_unverified"), ("binding", "native_receipt_unverified"),
    ("owner", "owner_mismatch"), ("warning", "assessment_not_passed"), ("expired", "validation_not_current"),
    ("source", "source_mismatch"), ("unread", "changed_files_unread"), ("version", "validation_source_mismatch"),
    ("provider", "provider_turn_unobserved"),
])
def test_native_qa_cannot_pass_on_configuration_prose_or_wrong_evidence(kind, gate):
    phase = native_phase()
    scenario = select_scenarios("backend-repair")[0]
    assert workflow.phase_gates(scenario, phase) == []
    reviewer = phase["attempts"][-1]; review = reviewer["reviews"][0]
    if kind == "missing": phase["attempts"].pop()
    if kind in {"scripted", "binding"}: review["verifiedNativeReceipt"] = False
    if kind == "scripted": review["adapterType"] = "scripted_mock"
    if kind == "owner": review["taskRunId"] = "other"
    if kind == "warning": review["model"]["status"] = "warning"
    if kind == "expired": review["currentness"] = "expired"
    if kind == "source": phase["sourceHashes"]["apps/demo-api/app/main.py"] = "later"
    if kind == "unread": review["filesReviewed"] = []
    if kind == "version": review["validation"]["sourceFingerprint"] = "other"
    if kind == "provider": reviewer["providerTurnObserved"] = False
    assert "demo-backend:qa_" + gate in workflow.phase_gates(scenario, phase)


def test_old_successes_never_establish_native_qa_or_requested_coding_adapter():
    phase = native_phase()
    phase["attempts"][0]["providerAssignment"] = {"adapterType": "claude_code"}
    assert "demo-backend:coding_adapter_mismatch" in workflow.phase_gates(select_scenarios("backend-repair")[0], phase)


def test_real_native_parser_artifact_receipt_and_current_input_are_rechecked(fixture):
    db, run, _, source = fixture
    completed = asyncio.run(execute_task_run(db, run, adapter_type="claude_code",
        adapter=ClaudeCodeAdapter(process_runner=ReviewRunner(), read_only=True), supervisor=RunSupervisor()))
    attempt = workflow.collect_attempt(db, completed, source.parents[3])
    assert len(attempt["reviews"]) == 1
    review = attempt["reviews"][0]
    assert review["verifiedNativeReceipt"] and review["model"]["status"] == "warning"
    assert SOURCE in review["readEvidence"] and SOURCE in review["boundFiles"]
    terminal = db.exec(select(TaskRunEvent).where(TaskRunEvent.task_run_id == run.id, TaskRunEvent.event_type == "completed")).one()
    payload = json.loads(terminal.payload_json)
    original = deepcopy(payload)
    payload["nativeReview"]["readEvidence"][SOURCE] = "wrong"
    terminal.payload_json = json.dumps(payload); db.add(terminal); db.commit()
    assert not workflow.collect_attempt(db, completed, source.parents[3])["reviews"][0]["verifiedNativeReceipt"]
    terminal.payload_json = json.dumps(original); db.add(terminal); db.commit()
    source.write_text("changed after review", encoding="utf-8")
    assert not workflow.collect_attempt(db, completed, source.parents[3])["reviews"][0]["verifiedNativeReceipt"]


def test_explicit_native_profiles_are_isolated_and_prompts_bind_actual_aliases(fixture):
    db, run, _, _ = fixture
    from app.models import Task, Session
    workspace = db.get(Session, db.get(Task, run.task_id).session_id).workspace_id
    profiles = configure_profiles(db, workspace, adapter="codex", qa_adapter="claude_code")
    assert len(profiles) == 3
    qa = next(p for p in profiles if p["alias"] == "workflow-qa")
    assert qa["toolPolicy"] == "claude_read_only" and qa["adapterType"] == "claude_code"
    assert db.get(AgentProfileDraft, qa["id"]).workspace_id == workspace
    scenario = bound_scenario(select_scenarios("backend-repair")[0], "claude_code")
    assert "@workflow-backend @workflow-qa" in scenario.prompts[0]
    assert bound_scenario(scenario, "claude_code") == scenario


def test_elapsed_time_preserves_unknowns_and_distinguishes_roles_and_retries():
    start = datetime(2026, 10, 16)
    assert attempt_seconds(SimpleNamespace(started_at=start, ended_at=start.replace(tzinfo=timezone.utc) + timedelta(seconds=2))) == 2
    assert attempt_seconds(SimpleNamespace(started_at=start, ended_at=None)) is None
    assert attempt_seconds(SimpleNamespace(started_at=start, ended_at=start - timedelta(seconds=1))) is None
    cases = [{"phases": [{"attempts": [{"role": "frontend", "state": "failed", "elapsedSeconds": 2},
        {"role": "frontend", "state": "completed", "elapsedSeconds": 3, "retryOfRunId": "previous"},
        {"role": "qa", "state": "completed", "elapsedSeconds": None}]}]}]
    result = role_stats(cases)
    assert result["coding"]["retries"] == 1 and result["coding"]["elapsed"]["totalSeconds"] == 5
    assert result["qa"]["elapsed"]["unknown"] == 1 and result["qa"]["elapsed"]["totalSeconds"] is None


def test_cohort_identity_includes_qa_mode_inputs_and_uncommitted_policy():
    options = dict(development_head="same-head", adapter="codex", qa_adapter="claude_code", scenarios=["fixed"], repetitions=2, max_retries=1)
    one = cohort({"file": "a"}, **options)
    assert cohort({"file": "b"}, **options)["id"] != one["id"]
    assert cohort({"file": "a"}, **{**options, "qa_adapter": "scripted_mock"})["id"] != one["id"]
    report = {"cohort": one, "cases": [{"caseId": "one", "verdict": "passed", "firstAttemptPassed": True},
        {"caseId": "two", "verdict": "not_attempted"}]}
    invalidate(report, reason="evaluation_policy_changed", index=1)
    result = workflow.aggregate(report["cases"], mode="live", cohort_valid=False)
    assert result["selected"] == 2 and result["finalSuccessRate"] is None and result["firstAttemptSuccessRate"] is None
    assert report["cases"][0]["observedVerdict"] == "passed" and report["cases"][0]["verdict"] == "invalidated"


def test_initial_category_selection_and_unknown_timing_survive_early_harness_failure(tmp_path, monkeypatch):
    policy = {"source": "one"}
    monkeypatch.setattr(workflow, "source_policy", lambda: dict(policy))

    async def failed(directory, scenario, **kwargs):
        initial = json.loads((directory.parent / "report.json").read_text(encoding="utf-8"))
        assert initial["summary"]["naturalScenarios"]["selected"] == 8
        assert initial["summary"]["faultInjectionScenarios"]["selected"] == 2
        assert initial["summary"]["attempted"] == 0
        policy["source"] = "two"
        raise RuntimeError("No timing receipt was available")

    monkeypatch.setattr(workflow, "run_scenario", failed)
    report = asyncio.run(workflow.run_benchmark(tmp_path / "unknown-time", repetitions=2))
    summary = report["summary"]
    assert summary["attempted"] == summary["finalized"] == 1
    assert summary["timed"] == 0 and summary["medianElapsedSeconds"] is None
    assert summary["naturalScenarios"]["selected"] == 8
    assert summary["faultInjectionScenarios"]["selected"] == 2
    assert summary["finalSuccessRate"] is None


def test_running_cases_are_attempted_without_fabricated_duration():
    value = workflow.aggregate([{"caseId": "running", "verdict": "running"},
        {"caseId": "waiting", "verdict": "not_attempted"}], mode="live", cohort_valid=False)
    assert value["attempted"] == 1 and value["finalized"] == value["timed"] == 0
    assert value["finalSuccessRate"] is None


def test_source_change_stops_whole_cohort_without_starting_another_case(tmp_path, monkeypatch):
    policy = {"version": "one"}; calls = []
    monkeypatch.setattr(workflow, "source_policy", lambda: dict(policy))
    async def sample(directory, scenario, **kwargs):
        calls.append(scenario.id); policy["version"] = "two"
        return {"caseId": scenario.id, "verdict": "passed", "firstAttemptPassed": True}
    monkeypatch.setattr(workflow, "run_scenario", sample)
    report = asyncio.run(workflow.run_benchmark(tmp_path / "cohort", repetitions=2))
    assert len(calls) == 1 and len(report["cases"]) == 10
    assert report["cohort"]["status"] == "invalidated" and report["summary"]["finalSuccessRate"] is None
    assert report["cases"][0]["observedVerdict"] == "passed"
    assert all(case["verdict"] == "not_attempted" for case in report["cases"][1:])


def test_unreadable_policy_invalidates_and_partial_reports_have_no_final_rate(tmp_path, monkeypatch):
    from app.workflow_cohort import cohort
    calls = []
    def policy():
        if calls:
            raise FileNotFoundError("source removed during cohort")
        return {"file": "initial"}
    async def sample(directory, scenario, **kwargs):
        calls.append(True)
        return {"caseId": scenario.id, "verdict": "passed", "firstAttemptPassed": True}
    monkeypatch.setattr(workflow, "source_policy", policy)
    monkeypatch.setattr(workflow, "run_scenario", sample)
    report = asyncio.run(workflow.run_benchmark(tmp_path / "unreadable", repetitions=2))
    assert report["status"] == "invalidated" and report["summary"]["finalSuccessRate"] is None
    assert len(calls) == 1 and report["cases"][0]["observedVerdict"] == "passed"
    report.update(status="running")
    report["cohort"]["status"] = "frozen"
    report["cases"][0].update(verdict="passed", firstAttemptPassed=True)
    workflow.save_report(tmp_path / "unreadable", report)
    assert report["summary"]["firstAttemptSuccessRate"] is None
    report["status"] = "completed"
    workflow.save_report(tmp_path / "unreadable", report)
    assert report["summary"]["firstAttemptSuccessRate"] == .1


def test_live_cannot_select_scripted_qa_or_unbounded_retries(tmp_path):
    with pytest.raises(ValueError): asyncio.run(workflow.run_benchmark(tmp_path / "no", qa_adapter="scripted_mock"))
    with pytest.raises(ValueError): asyncio.run(workflow.run_benchmark(tmp_path / "no", max_retries=3))
    assert not (tmp_path / "no").exists()


def test_source_policy_covers_fixtures_harness_helpers_dependencies_and_patches():
    policy = workflow.source_policy()
    for name in ("apps/api/app/workflow_profiles.py", "scripts/workflow-api-bridge.py", "scripts/preview-vite.config.mjs",
                 "apps/demo/src/App.tsx", "apps/demo-api/app/main.py", "pnpm-lock.yaml", "apps/api/requirements.txt",
                 "patches/braces@3.0.3.patch"):
        assert name in policy and len(policy[name]) == 64
    assert not any("node_modules/" in name or "/.env" in name or "__pycache__/" in name for name in policy)
