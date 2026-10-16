import asyncio
from dataclasses import replace
import json
from pathlib import Path
import re
import threading

import pytest
from sqlmodel import Session as DbSession, create_engine, select

from app import workflow_evaluation as workflow
from app import run_engine
from app.adapters import AgentEvent
from app.models import TaskRun
from app.planner_providers import PlannerProviderResult
from app.provider_gateway import ProviderHealthResult
from app.scripted_mock import ScriptedMockAdapter
from app.workflow_acceptance import contacts_acceptance, evaluate_scenario
from app.workflow_suite import prepare_source, select_scenarios

CONTACT_APP = '''import { useEffect, useState, type FormEvent } from 'react'
type Contact = {id: string, name: string, email: string}
export default function App() {
  const [contacts, setContacts] = useState<Contact[]>([])
  const [name, setName] = useState(''), [email, setEmail] = useState('')
  const [error, setError] = useState(''), [saving, setSaving] = useState(false)
  async function load() { setContacts(await (await fetch('/api/contacts')).json()) }
  useEffect(() => { void load() }, [])
  async function create(event: FormEvent) {
    event.preventDefault()
    setError(''); setSaving(true)
    try {
      const response = await fetch('/api/contacts', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name,email})})
      if (!response.ok) throw new Error(`Request failed: ${response.status}`)
      await load()
    } catch (problem) { setError(problem instanceof Error ? problem.message : 'Request failed') }
    finally { setSaving(false) }
  }
  return <main style={{maxWidth:'100%',padding:8}}><h1 id="demo-heading">Contacts workspace</h1>
    <form onSubmit={create}><label>Name<input required value={name} onChange={e => setName(e.target.value)} /></label>
    <label>Email<input required type="email" value={email} onChange={e => setEmail(e.target.value)} /></label>
    <button type="submit" disabled={saving}>Create contact</button></form>
    {error && <p role="alert">{error}</p>}
    <ul aria-label="Contacts">{contacts.map(c => <li key={c.id}>{c.name}</li>)}</ul></main>
}
'''


def fix_source(root, scenario, index=0):
    if scenario.backend:
        path = root / "apps/demo-api/app/main.py"
        text = path.read_text(encoding="utf-8").replace('status="broken"', 'status="ok"').replace("pass  # missing persistence", "_contacts.append(contact)")
        path.write_text(text, encoding="utf-8")
    if scenario.integration:
        (root / "apps/demo/src/App.tsx").write_text(CONTACT_APP, encoding="utf-8")
    elif scenario.frontend:
        path = root / "apps/demo/src/App.tsx"
        if scenario.multi_file:
            text = path.read_text(encoding="utf-8").replace("{workflowTitle} broken", "{workflowTitle}")
            path.write_text(text, encoding="utf-8")
            (path.parent / "workflow-copy.ts").write_text('export const workflowTitle = "Workflow ready"\n', encoding="utf-8")
        else:
            path.write_text(re.sub(r'(<h1 id="demo-heading">).*?(</h1>)', lambda match: match[1] + scenario.headings[index] + match[2], path.read_text(encoding="utf-8")), encoding="utf-8")


def fake_planner(monkeypatch):
    class Planner:
        planner_source = "fake_test"
        def create_plan(self, payload):
            tasks = []
            for item in payload["explicitGroupAssignments"]:
                files = [] if item["readOnly"] else ["apps/demo-api/app/main.py"] if item["role"] == "backend" else ["apps/demo/src/App.tsx"]
                if item["role"] == "frontend" and "workflow-copy.ts" in str(payload): files.append("apps/demo/src/workflow-copy.ts")
                tasks.append({"title": "Evaluate " + item["role"], "role": item["role"], "targetId": item["targetId"],
                    "intentType": item["intentType"], "plannedFiles": files, "dependsOn": [],
                    "expectedArtifactTypes": ["review" if item["readOnly"] else "diff"], "acceptanceCriteria": ["Fixed contract passes"],
                    "riskLevel": "low", "requiresApproval": False, "validationExpectations": [], "rationale": "Explicit test planner"})
            result = {"outcomeType": "task_plan", "planDraft": {"planId": "workflow-test", "planner": "llm_v1", "plannerMode": "llm_v1",
                "rationale": "Explicit test planning", "tasks": tasks, "acceptanceCriteria": ["Independent tests pass"], "validationExpectations": []}}
            return PlannerProviderResult("workflow-test-planner", "fake_test", "fake_test", "succeeded", raw_output=json.dumps(result))
    monkeypatch.setattr("app.group_planner.resolve_planner_provider", lambda *args, **kwargs: Planner())


def fake_writer(monkeypatch, scenario):
    class Writer(ScriptedMockAdapter):
        async def streamEvents(self, run_id):
            request = self._request_for(run_id)
            root = Path(request.worktree_path)
            if request.plan_context.get("forceFailure"):
                yield AgentEvent(type="error", taskRunId=request.task_run_id, payload={"code": "CODEX_FORCED_FAILURE", "message": "Explicit test failure injection"})
                return
            yield AgentEvent(type="task.state", taskRunId=request.task_run_id, payload={"state": "streaming", "codexEventType": "thread.started"})
            # Keep mutations within the role's actual scope, just like real work.
            frontend = request.plan_context.get("assignedRole") == "frontend"
            partial = replace(scenario, frontend=frontend, backend=not frontend, integration=scenario.integration and frontend)
            index = 1 if "Second revision" in request.instruction else 0
            fix_source(root, partial, index)
            yield AgentEvent(type="completed", taskRunId=request.task_run_id, payload={"codexEventType": "turn.completed"})
    monkeypatch.setattr(run_engine, "CodexAdapter", Writer)
    monkeypatch.setattr(run_engine._provider_health_probe, "check_provider", lambda provider, **kwargs:
                        ProviderHealthResult(provider.provider_id, "codex", "healthy", True, "Explicit workflow test double"))


@pytest.mark.parametrize("case_id", [case.id for case in select_scenarios()])
def test_real_prepare_proves_failing_baseline_without_provider(tmp_path, monkeypatch, case_id):
    async def forbidden(*args, **kwargs): pytest.fail("Prepare-only invoked provider")
    monkeypatch.setattr(run_engine.RunWorker, "run_once", forbidden)
    report = asyncio.run(workflow.run_benchmark(tmp_path / "fresh", case_id=case_id, prepare_only=True))
    case = report["cases"][0]
    assert case["baselineFailing"] and case["verdict"] == "prepared", case
    assert report["summary"]["finalSuccessRate"] is None
    assert not (tmp_path / "fresh" / f"{case_id}-1" / "workflow.sqlite3").exists()


def test_real_browser_contacts_bridge_requires_both_targets_and_persistence(tmp_path):
    scenario = select_scenarios("coordinated-contacts")[0]
    root = prepare_source(tmp_path, scenario)
    fix_source(root, scenario)
    result = contacts_acceptance(root, threading.Event())
    assert result["status"] == "passed", result
    assert len(result["checks"]) == 10 and all(c["status"] == "passed" for c in result["checks"])
    assert sum(r["method"] == "POST" and r["status"] == 201 for r in result["requests"]) == 2
    # A backend that returns 201 without storing fails refresh acceptance.
    path = root / "apps/demo-api/app/main.py"
    path.write_text(path.read_text(encoding="utf-8").replace("_contacts.append(contact)", "pass"), encoding="utf-8")
    broken = contacts_acceptance(root, threading.Event())
    assert broken["status"] == "failed"
    assert any(c["id"].endswith("persist") and c["status"] == "failed" for c in broken["checks"])


@pytest.mark.parametrize("case_id", ["backend-repair", "multi-file", "follow-up", "retry-recovery", "coordinated-contacts"])
def test_real_dispatch_queue_diff_acceptance_with_explicit_test_provider(tmp_path, monkeypatch, case_id):
    scenario = select_scenarios(case_id)[0]
    fake_planner(monkeypatch); fake_writer(monkeypatch, scenario)
    output = tmp_path / "test-double"
    report = asyncio.run(workflow.run_benchmark(output, case_id=case_id, test_execution=True, qa_adapter="scripted_mock"))
    case = report["cases"][0]
    assert case["verdict"] == "passed", case
    assert report["mode"] == "test_double" and report["summary"]["finalSuccessRate"] is None
    assert len(case["phases"]) == len(scenario.prompts)
    assert all(p["planningSource"] == "fake_test" and not p["nativePlanning"] for p in case["phases"])
    assert all(p["plannerCalls"] and p["plannerCalls"][0]["plannerSource"] == "fake_test" for p in case["phases"])
    assert all(p["immutableInputs"] and p["allTasksCompleted"] and p["acceptance"]["status"] == "passed" for p in case["phases"])
    if scenario.fault_injection:
        first, retry = case["phases"][0]["attempts"][:2]
        assert first["state"] == "failed" and retry["retryOfRunId"] == first["taskRunId"]
        assert case["retryCount"] == 1 and not case["firstAttemptPassed"]
    if case_id == "follow-up":
        assert case["phases"][0]["messageId"] != case["phases"][1]["messageId"]
        assert case["phases"][0]["sourceHashes"] != case["phases"][1]["sourceHashes"]
    engine = create_engine(f"sqlite:///{(output / f'{case_id}-1/workflow.sqlite3').as_posix()}")
    try:
        with DbSession(engine) as db:
            assert all(run.state in workflow.TERMINAL for run in db.exec(select(TaskRun)))
    finally: engine.dispose()


def test_unknown_options_reject_before_creating_output(tmp_path):
    output = tmp_path / "unknown"
    with pytest.raises(ValueError): asyncio.run(workflow.run_benchmark(output, case_id="unknown"))
    assert not output.exists()
    with pytest.raises(ValueError): asyncio.run(workflow.run_benchmark(output, repetitions=0))
    assert not output.exists()


def test_summary_keeps_failed_unattempted_denominators_and_injected_cases_separate():
    cases = [{"caseId": "api", "verdict": "passed", "firstAttemptPassed": True, "elapsedSeconds": 4},
             {"caseId": "retry", "verdict": "passed", "firstAttemptPassed": False, "retryCount": 1, "faultInjection": True, "elapsedSeconds": 6},
             {"caseId": "api", "verdict": "not_attempted"}]
    value = workflow.aggregate(cases, mode="live")
    assert value["selected"] == 3 and value["finalSuccessRate"] == pytest.approx(2/3)
    assert value["firstAttemptSuccessRate"] == pytest.approx(1/3)
    assert value["naturalScenarios"]["selected"] == 2 and value["naturalScenarios"]["finalSuccessRate"] == .5
    assert value["faultInjectionScenarios"]["firstAttemptSuccessRate"] == 0
    assert workflow.aggregate(cases, mode="test_double")["finalSuccessRate"] is None


def test_missing_native_planner_does_not_start_coding_or_appear_successful(tmp_path, monkeypatch):
    from app.planner_providers import DisabledPlannerProvider
    monkeypatch.setattr("app.group_planner.resolve_planner_provider", lambda *args, **kwargs: DisabledPlannerProvider())
    async def forbidden(*args, **kwargs): pytest.fail("Coding started without native planning")
    monkeypatch.setattr(run_engine.RunWorker, "run_once", forbidden)
    report = asyncio.run(workflow.run_benchmark(tmp_path / "unavailable", case_id="backend-repair"))
    case = report["cases"][0]
    assert case["verdict"] == "failed" and "native_planning_unobserved" in case["failureGates"]
    assert not case["phases"][0]["nativePlanning"]


def test_cancel_stops_owned_acceptance_thread(monkeypatch, tmp_path):
    entered, stopped = threading.Event(), threading.Event()
    def wait_for_cancel(root, scenario, index, *, cancelled):
        entered.set()
        assert cancelled.wait(5)
        stopped.set()
        return {"status": "unavailable", "results": {}}
    monkeypatch.setattr(workflow, "evaluate_scenario", wait_for_cancel)
    async def exercise():
        operation = asyncio.create_task(workflow.accept_source(tmp_path, select_scenarios()[0]))
        while not entered.is_set(): await asyncio.sleep(.01)
        operation.cancel()
        with pytest.raises(asyncio.CancelledError): await operation
    asyncio.run(exercise())
    assert stopped.is_set()


def test_cancel_preserves_partial_report_and_terminal_queue(tmp_path, monkeypatch):
    fake_planner(monkeypatch)
    entered = asyncio.Event()
    async def wait_for_cancel(self, db):
        entered.set()
        await asyncio.Event().wait()
    monkeypatch.setattr(run_engine.RunWorker, "run_once", wait_for_cancel)
    output = tmp_path / "cancelled"
    async def exercise():
        operation = asyncio.create_task(workflow.run_benchmark(output, case_id="backend-repair", test_execution=True, qa_adapter="scripted_mock"))
        await asyncio.wait_for(entered.wait(), 15)
        operation.cancel()
        with pytest.raises(asyncio.CancelledError): await operation
    asyncio.run(exercise())
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    case = report["cases"][0]
    assert case["verdict"] == "interrupted" and case["failureGates"] == ["evaluation_interrupted"]
    assert case["phases"][0]["messageId"] and case["phases"][0]["attempts"]
    assert case["phases"][0]["plannerCalls"][0]["status"] == "succeeded"
    assert all(attempt["state"] in workflow.TERMINAL for attempt in case["phases"][0]["attempts"])
    assert any(attempt["stateAtCutoff"] == "queued" and attempt["state"] == "interrupted" for attempt in case["phases"][0]["attempts"])
    engine = create_engine(f"sqlite:///{(output / 'backend-repair-1/workflow.sqlite3').as_posix()}")
    try:
        with DbSession(engine) as db: assert all(run.state in workflow.TERMINAL for run in db.exec(select(TaskRun)))
    finally: engine.dispose()
