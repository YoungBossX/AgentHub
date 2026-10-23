import asyncio
from pathlib import Path

import pytest

from app import workflow_evaluation as workflow, run_engine
from app.adapters import AgentEvent
from app.provider_gateway import ProviderHealthResult
from app.scripted_mock import ScriptedMockAdapter
from app.workflow_suite import select_scenarios
from test_contacts_feedback_contract import CHINESE_APP
from test_workflow_evaluation import fake_planner


def test_chinese_boundary_scenario_is_explicit_and_does_not_expand_default_cohort():
    try:
        scenario = select_scenarios('contacts-boundaries')[0]
    except ValueError:
        pytest.fail('缺少可显式选择的中文联系人固定边界场景')
    assert len(select_scenarios()) == 5
    assert scenario.contacts_contract == 'contacts-boundaries-v3' and scenario.integration
    assert '姓名' in scenario.prompts[0] and '刷新' in scenario.prompts[0]


@pytest.mark.parametrize('options', [{'case_id': 'backend-repair'}, {'case_id': None},
                                   {'case_id': 'contacts-boundaries', 'repair_contract_failures': 1}])
def test_unsupported_or_non_boolean_repair_option_never_creates_output(tmp_path, options):
    settings = {'repair_contract_failures': True, **options}
    with pytest.raises(ValueError):
        asyncio.run(workflow.run_benchmark(tmp_path/'untouched', **settings))
    assert not (tmp_path/'untouched').exists()


def test_finalization_error_preserves_already_recorded_original_and_repair_evidence(tmp_path, monkeypatch):
    async def broken(directory, scenario, *, progress, **options):
        progress({'caseId': scenario.id, 'verdict': 'running',
            'phases': [{'messageId': 'original', 'verdict': 'failed', 'attempts': [{'taskRunId': 'original-run'}]}],
            'repairPhases': [{'attempts': [{'taskRunId': 'repair-run', 'providerUsage': {'inputTokens': 7}}]}],
            'repairOutcome': {'status': 'running', 'binding': {'originalMessageId': 'original'}}})
        raise FileNotFoundError('output disappeared during finalization')
    monkeypatch.setattr(workflow, 'run_scenario', broken)
    report = asyncio.run(workflow.run_benchmark(tmp_path/'preserved', case_id='contacts-boundaries',
        test_execution=True, qa_adapter='scripted_mock', repair_contract_failures=True))
    case = report['cases'][0]
    assert case['verdict'] == 'harness_error'
    assert case['phases'][0]['messageId'] == 'original'
    assert case['repairPhases'][0]['attempts'][0]['taskRunId'] == 'repair-run'
    assert case['repairOutcome']['status'] == 'harness_error'
    assert report['summary']['measurements']['providerUsage']['fields']['inputTokens']['knownSum'] == 7


def test_rejected_repair_plan_reports_its_stopped_queue_state(tmp_path, monkeypatch):
    from sqlmodel import Session as DbSession, select
    from app.db_engine import create_runtime_engine
    from app.models import TaskRun
    from app.workflow_feedback import ContactsRepairGuard
    from test_workflow_feedback import failed_phase

    fake_planner(monkeypatch)
    actual_phase = workflow.run_phase

    async def phase(db, session, root, scenario, index, baseline_hashes, **options):
        if options.get('feedback_guard'):
            return await actual_phase(db, session, root, scenario, index, baseline_hashes, **options)
        options['phase'].update(failed_phase(root), attempts=[])

    async def failed_acceptance(*args, **kwargs):
        return {'status': 'failed'}

    monkeypatch.setattr(workflow, 'run_phase', phase)
    monkeypatch.setattr(workflow, 'accept_source', failed_acceptance)
    monkeypatch.setattr(ContactsRepairGuard, 'validate_tasks', lambda guard, tasks: guard.reject())
    output = tmp_path/'rejected'
    report = asyncio.run(workflow.run_benchmark(output, case_id='contacts-boundaries',
        test_execution=True, qa_adapter='scripted_mock', repair_contract_failures=True))
    case = report['cases'][0]
    repair = case['repairPhases'][0]
    assert repair['error']['type'] == 'TaskRunScopeError'
    assert repair['planningSource'] == 'fake_test'
    assert len(repair['tasks']) == 2
    assert repair['attempts']
    engine = create_runtime_engine('sqlite:///'+(output/'contacts-boundaries-1/workflow.sqlite3').as_posix())
    try:
        with DbSession(engine) as db:
            states = {run.id: run.state for run in db.exec(select(TaskRun)).all()}
        for attempt in repair['attempts']:
            assert attempt['state'] == states[attempt['taskRunId']] == 'interrupted'
            assert attempt['stateAtCutoff'] == 'queued'
            assert attempt['stoppedBy'] == 'workflow_evaluation'
    finally:
        engine.dispose()


def install_writer(monkeypatch, *, repair_succeeds=True):
    class Writer(ScriptedMockAdapter):
        async def streamEvents(self, run_id):
            request = self._request_for(run_id)
            root = Path(request.worktree_path)
            yield AgentEvent(type='task.state', taskRunId=request.task_run_id,
                payload={'state': 'streaming', 'codexEventType': 'thread.started'})
            if request.plan_context.get('assignedRole') == 'backend':
                path = root/'apps/demo-api/app/main.py'
                text = path.read_text(encoding='utf-8').replace('pass  # missing persistence', '_contacts.append(contact)')
                text = text.replace('contact.email == payload.email', 'contact.email.casefold() == payload.email.casefold()')
                text = text.replace('    if any(', '    if not payload.name.strip():\n        raise HTTPException(status_code=422, detail="姓名不能为空白")\n    if any(')
                path.write_text(text, encoding='utf-8')
            else:
                repaired = '已被固定业务验收复现' in request.instruction
                text = CHINESE_APP
                if not repaired or not repair_succeeds:
                    text = text.replace('setContacts(previous => [...previous.filter(c => c.id !== created.id), created])', 'void created')
                if repaired:
                    text += '\n// 明确的受限修复尝试\n'
                (root/'apps/demo/src/App.tsx').write_text(text, encoding='utf-8')
            yield AgentEvent(type='completed', taskRunId=request.task_run_id, payload={'codexEventType': 'turn.completed'})
    monkeypatch.setattr(run_engine, 'CodexAdapter', Writer)
    monkeypatch.setattr(run_engine._provider_health_probe, 'check_provider', lambda provider, **kwargs:
        ProviderHealthResult(provider.provider_id, 'codex', 'healthy', True, 'Explicit test double'))


@pytest.mark.parametrize('repair_succeeds', [True, False])
def test_real_queue_diff_business_repair_runs_once_and_keeps_original_failure(tmp_path, monkeypatch, repair_succeeds):
    fake_planner(monkeypatch)
    install_writer(monkeypatch, repair_succeeds=repair_succeeds)
    try:
        report = asyncio.run(workflow.run_benchmark(tmp_path/'run', case_id='contacts-boundaries',
            test_execution=True, qa_adapter='scripted_mock', repair_contract_failures=True))
    except TypeError as exc:
        pytest.fail('现有工作流缺少显式一次业务修复入口：'+str(exc))
    case = report['cases'][0]
    assert report['status'] == 'completed' and report['mode'] == 'test_double'
    assert case['verdict'] == 'failed' and case['firstAttemptPassed'] is False
    assert len(case['repairPhases']) == 1
    assert case['repairOutcome']['status'] == ('recovered' if repair_succeeds else 'failed')
    assert case['phases'][0]['acceptance']['status'] == 'failed'
    assert case['repairPhases'][0]['acceptance']['status'] == ('passed' if repair_succeeds else 'failed')
    assert all('saved_refresh_failure' in name for name in case['repairOutcome']['binding']['failedCheckIds'])
    assert case['repairPhases'][0]['repairLaunches']
    for attempt in case['repairPhases'][0]['attempts']:
        binding = attempt['businessRepair']
        assert binding['originalMessageId'] == case['phases'][0]['messageId']
        assert binding['originalRunIds'] == [a['taskRunId'] for a in case['phases'][0]['attempts']]
        assert binding['allowedFiles'] == ['apps/demo/src/App.tsx']
    assert report['summary']['passed'] == 0
    assert report['summary']['repairs']['attempted'] == 1
    assert report['summary']['repairs']['recovered'] == int(repair_succeeds)
    # Include planning, failed original output and all repair attempts in usage.
    assert report['summary']['measurements']['providerUsage']['callRecords'] == 8
    assert report['cohort']['identity']['repairContractFailures'] is True


@pytest.mark.parametrize('stop', ['timeout', 'cancel'])
def test_repair_uses_remaining_budget_and_preserves_interrupted_evidence(tmp_path, monkeypatch, stop):
    from test_workflow_feedback import failed_phase
    from app import workflow_feedback

    async def baseline(*args, **kwargs):
        return {'status': 'failed'}
    monkeypatch.setattr(workflow, 'accept_source', baseline)
    phases, limits, saved = [], [], []
    async def phase(db, session, root, scenario, index, baseline_hashes, **options):
        output = options['phase']
        phases.append(output)
        if len(phases) == 1:
            output.update(failed_phase(root), attempts=[])
            return output
        output.update(attempts=[], error='scenario_timeout_or_cancel', failureGates=['phase_execution_error'], verdict='failed')
        assert options['max_retries'] == 0 and options['feedback_guard']
        with workflow_feedback.activate_repair(options['feedback_guard']):
            assert workflow_feedback._active.get() is options['feedback_guard']
            raise asyncio.CancelledError()
    async def wait(operation, *, timeout):
        limits.append(timeout)
        try:
            return await operation
        except asyncio.CancelledError:
            if stop == 'timeout': raise asyncio.TimeoutError()
            raise
    monkeypatch.setattr(workflow, 'run_phase', phase)
    monkeypatch.setattr(workflow.asyncio, 'wait_for', wait)
    scenario = select_scenarios('contacts-boundaries')[0]
    options = dict(qa_adapter='scripted_mock', test_execution=True, repair_contract_failures=True,
                   progress=lambda value: saved.append(value))
    if stop == 'cancel':
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(workflow.run_scenario(tmp_path, scenario, **options))
        case = saved[-1]
    else:
        case = asyncio.run(workflow.run_scenario(tmp_path, scenario, **options))
    assert len(phases) == 2 and 0 < limits[1] < limits[0] == 900
    assert len(case['repairPhases']) == 1 and case['phases'][0]['verdict'] == 'failed'
    assert case['repairOutcome']['status'] == ('budget_exhausted' if stop == 'timeout' else 'interrupted')
    assert workflow_feedback._active.get() is None
