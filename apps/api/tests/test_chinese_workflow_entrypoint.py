"""Chinese evaluation operator boundaries; no real API invocation in these tests."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.fixture
def entrypoint():
    path = Path(__file__).resolve().parents[3] / 'scripts/evaluate-chinese-workflows.py'
    spec = importlib.util.spec_from_file_location('chinese_workflow_entrypoint', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ten_tasks_are_five_natural_chinese_scenarios_twice(entrypoint):
    cases = entrypoint.chinese_scenarios()
    assert [c.id for c in cases] == ['backend-repair','multi-file','contacts-boundaries','follow-up','heading-single']
    assert len(cases) * 2 == 10 and not any(c.fault_injection for c in cases)
    assert all('简体中文' in p for c in cases for p in c.prompts)
    assert cases[2].contacts_contract == 'contacts-boundaries-v3'
    assert len(cases[3].prompts) == 2
    assert entrypoint.chinese_scenarios('heading-single') == [cases[-1]]
    with pytest.raises(ValueError):entrypoint.chinese_scenarios('retry-recovery')


def test_only_model_transport_settings_are_forwarded(entrypoint,tmp_path):
    settings=tmp_path/'settings.json'
    settings.write_text(json.dumps({'env':{'ANTHROPIC_AUTH_TOKEN':'test-key','ANTHROPIC_BASE_URL':'https://example.invalid',
        'ANTHROPIC_DEFAULT_SONNET_MODEL':'test-model','ANTHROPIC_MODEL':7,'PATH':'unsafe','NODE_OPTIONS':'--require unsafe'}}),encoding='utf-8')
    assert entrypoint.provider_environment(settings)=={'ANTHROPIC_AUTH_TOKEN':'test-key','ANTHROPIC_BASE_URL':'https://example.invalid','ANTHROPIC_DEFAULT_SONNET_MODEL':'test-model'}
    assert entrypoint.provider_environment(tmp_path/'missing.json')=={}


@pytest.mark.parametrize('value',[[],{'env':'not an object'}])
def test_malformed_local_config_is_rejected(entrypoint,tmp_path,value):
    settings=tmp_path/'settings.json';settings.write_text(json.dumps(value),encoding='utf-8')
    with pytest.raises(ValueError):entrypoint.provider_environment(settings)


@pytest.mark.parametrize('option,value',[('--repetitions','0'),('--repetitions','11'),('--timeout','59'),('--timeout','1801'),('--max-retries','-1'),('--max-retries','3')])
def test_invalid_budget_does_not_create_output(entrypoint,tmp_path,option,value):
    output=tmp_path/'never-created'
    with pytest.raises(SystemExit) as error:entrypoint.main(['--output',str(output),option,value])
    assert error.value.code==2 and not output.exists()


def test_missing_auth_fails_before_any_output_or_model_call(entrypoint,tmp_path,monkeypatch):
    monkeypatch.delenv('ANTHROPIC_AUTH_TOKEN',raising=False);monkeypatch.delenv('ANTHROPIC_API_KEY',raising=False)
    output=tmp_path/'no-paid-call'
    with pytest.raises(SystemExit) as error:entrypoint.main(['--output',str(output),'--claude-settings',str(tmp_path/'absent.json')])
    assert error.value.code==2 and not output.exists()


def test_existing_output_is_never_overwritten(entrypoint,tmp_path):
    output=tmp_path/'old-evidence';output.mkdir();sentinel=output/'keep.txt';sentinel.write_text('old result',encoding='utf-8')
    with pytest.raises(FileExistsError):entrypoint.main(['--prepare-only','--output',str(output),'--claude-settings',str(tmp_path/'absent.json')])
    assert sentinel.read_text(encoding='utf-8')=='old result'


def test_preservation_hashes_include_sqlite_wal_and_not_plaintext(entrypoint,tmp_path,monkeypatch):
    monkeypatch.setattr(entrypoint,'REPO',tmp_path)
    database=tmp_path/'apps/api/data/agenthub.sqlite3';database.parent.mkdir(parents=True);database.write_bytes(b'database')
    wal=database.with_name(database.name+'-wal');wal.write_bytes(b'pending records')
    settings=tmp_path/'private.json';settings.write_text('private value',encoding='utf-8')
    before=entrypoint.product_hashes(settings)
    assert str(wal) in before and all(len(v)==64 for v in before.values())
    assert 'private value' not in json.dumps(before)
    wal.write_bytes(b'changed records');assert entrypoint.product_hashes(settings)!=before


@pytest.mark.parametrize('change',['product','policy','unverifiable'])
def test_preservation_failure_invalidates_a_would_be_green_report(entrypoint,tmp_path,monkeypatch,change):
    from app import workflow_evaluation as workflow
    monkeypatch.setattr(entrypoint,'REPO',tmp_path/'product')
    private=tmp_path/'private.json';private.write_text('initial',encoding='utf-8')
    root=tmp_path/'results';(root/'cohort').mkdir(parents=True)
    before=entrypoint.product_hashes(private)
    frozen={'version':'one'}
    policy=lambda:{'version':'two' if change=='policy' else 'one'}
    report={'status':'completed','mode':'live','cohort':{'status':'frozen'},
            'cases':[{'caseId':'heading-single','verdict':'passed','faultInjection':False}]}
    workflow.save_report(root/'cohort',report)
    assert report['summary']['finalSuccessRate']==1
    if change=='product':private.write_text('modified',encoding='utf-8')
    if change=='unverifiable':monkeypatch.setattr(entrypoint,'product_hashes',lambda *_:(_ for _ in ()).throw(OSError('unavailable')))
    with pytest.raises(RuntimeError):
        entrypoint.finalize_evidence(root,before=before,settings_path=private,policy=policy,frozen=frozen,
                                    report=report,workflow=workflow,phase='evaluated')
    saved=json.loads((root/'cohort/report.json').read_text(encoding='utf-8'))
    assert saved['status']=='invalidated' and saved['cohort']['status']=='invalidated'
    assert saved['summary']['finalSuccessRate'] is None
    assert saved['cases'][0]['observedVerdict']=='passed' and saved['cases'][0]['verdict']=='invalidated'
    state=json.loads((root/'execution-state.json').read_text(encoding='utf-8'))
    assert not state['cohortValid']
    if change=='unverifiable':assert saved['cohort']['reason']=='preservation_or_policy_unverifiable'


def test_fresh_interpreter_isolates_before_runtime_import_and_records_preparation_failure(entrypoint,tmp_path):
    output=tmp_path/'preparation-failure'
    program=r'''
import builtins, importlib.util, json, os, pathlib, sys
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('entrypoint',sys.argv[1]);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
sys.dont_write_bytecode=False
original=builtins.__import__
def guarded(name,globals=None,locals=None,fromlist=(),level=0):
    if name.startswith('app'):assert sys.dont_write_bytecode,'Bytecode was not suppressed before application import'
    if name=='app' and 'workflow_evaluation' in fromlist:
        root=pathlib.Path(sys.argv[2])
        assert os.environ['AGENTHUB_DATABASE_URL']=='sqlite:///'+(root/'operator-runtime.sqlite3').as_posix()
        assert os.environ['CLAUDE_CONFIG_DIR']==str(root/'claude-config')
        assert (root/'tmp').is_dir()
        print('INITIALIZATION_ORDER_OK',flush=True)
        raise RuntimeError('controlled preparation failure')
    return original(name,globals,locals,fromlist,level)
builtins.__import__=guarded
module.main(['--prepare-only','--output',sys.argv[2],'--claude-settings',sys.argv[2]+'/absent.json'])
'''
    env={key:value for key,value in os.environ.items() if key!='PYTHONDONTWRITEBYTECODE'}
    result=subprocess.run([sys.executable,'-X','utf8','-c',program,str(Path(entrypoint.__file__)),str(output)],
        env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
    assert result.returncode!=0 and 'INITIALIZATION_ORDER_OK' in result.stdout,(result.stdout,result.stderr)
    assert 'controlled preparation failure' in result.stderr
    state=json.loads((output/'execution-state.json').read_text(encoding='utf-8'))
    assert state['state']=='preparation_failed' and not state['cohortValid']
    assert state['pythonBytecodeDisabled'] and state['databaseConfiguredInsideOutput']
    assert json.loads((output/'preserved-after.json').read_text(encoding='utf-8'))['unchanged']
