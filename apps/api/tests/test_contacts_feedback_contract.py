import json
import threading

import pytest

from app.contacts_contract import LEGACY, RESILIENCE, parse_result
from app.workflow_acceptance import contacts_acceptance
from app.workflow_suite import prepare_source, select_scenarios
from test_workflow_evaluation import fix_source


CONTRACT = "contacts-boundaries-v3"
CHECKS = [f"{view}.{name}" for view in ("desktop", "narrow") for name in (
    "initial", "create", "duplicate", "invalid", "server_failure", "retry", "persist",
    "same_local_distinct_domain", "case_insensitive_duplicate", "saved_refresh_failure", "whitespace_name", "layout", "runtime")]
CHECKS += ["api.whitespace_ascii", "api.whitespace_unicode"]

CHINESE_APP = '''import { useEffect, useState, type FormEvent } from 'react'
type Contact = {id: string, name: string, email: string}
export default function App() {
  const [contacts, setContacts] = useState<Contact[]>([])
  const [name, setName] = useState(''), [email, setEmail] = useState('')
  const [error, setError] = useState(''), [notice, setNotice] = useState(''), [saving, setSaving] = useState(false)
  async function load() {
    const response = await fetch('/api/contacts')
    if (!response.ok) throw new Error('刷新失败')
    setContacts(await response.json())
  }
  useEffect(() => { void load().catch(() => setError('无法读取联系人')) }, [])
  async function create(event: FormEvent) {
    event.preventDefault()
    setError(''); setNotice('')
    if (!name.trim()) { setError('姓名不能为空白，请填写有效姓名'); return }
    setSaving(true)
    try {
      const response = await fetch('/api/contacts', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:name.trim(),email})})
      if (!response.ok) throw new Error('保存失败，请重试')
      const created: Contact = await response.json()
      setContacts(previous => [...previous.filter(c => c.id !== created.id), created])
      setName(''); setEmail('')
      try { await load() } catch { setNotice('已保存，但列表刷新失败') }
    } catch { setError('保存失败，请重试') }
    finally { setSaving(false) }
  }
  return <main style={{maxWidth:'100%',padding:8}}><h1 id="demo-heading">中文联系人</h1>
    <form onSubmit={create}><label>姓名<input required value={name} onChange={e => setName(e.target.value)} /></label>
    <label>邮箱<input required type="email" value={email} onChange={e => setEmail(e.target.value)} /></label>
    <button type="submit" disabled={saving}>新增联系人</button></form>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    <ul aria-label="联系人列表">{contacts.map(c => <li key={c.id}>{c.name}</li>)}</ul></main>
}
'''


@pytest.fixture
def chinese_tree(tmp_path):
    scenario = select_scenarios('coordinated-contacts')[0]
    root = prepare_source(tmp_path, scenario)
    fix_source(root, scenario)
    (root/'apps/demo/src/App.tsx').write_text(CHINESE_APP, encoding='utf-8')
    path = root/'apps/demo-api/app/main.py'
    text = path.read_text(encoding='utf-8').replace('contact.email == payload.email', 'contact.email.casefold() == payload.email.casefold()')
    text = text.replace('    if any(', '    if not payload.name.strip():\n        raise HTTPException(status_code=422, detail="姓名不能为空白")\n    if any(')
    path.write_text(text, encoding='utf-8')
    return root


def test_real_chinese_contract_observes_all_edges_and_labels_synthetic_get_failure(chinese_tree):
    actual = contacts_acceptance(chinese_tree, threading.Event(), contract=CONTRACT)
    assert actual['status'] == 'passed', actual
    assert [c['id'] for c in actual['checks']] == CHECKS
    assert sum(r.get('injected') == 'fixed_get_503' for r in actual['requests']) == 2
    assert actual['frontendFingerprint'] and actual['backendFingerprint'] and actual['policyFingerprint']


def test_missing_chinese_ui_does_not_mark_independent_backend_edges_failed(chinese_tree):
    path = chinese_tree/'apps/demo/src/App.tsx'
    path.write_text(CHINESE_APP.replace('aria-label="联系人列表"', 'aria-label="Contacts"'), encoding='utf-8')
    actual = contacts_acceptance(chinese_tree, threading.Event(), contract=CONTRACT)
    assert actual['status'] == 'failed' and [c['id'] for c in actual['checks']] == CHECKS
    independent = {'same_local_distinct_domain', 'case_insensitive_duplicate', 'whitespace_ascii', 'whitespace_unicode'}
    assert all(c['status'] == 'passed' for c in actual['checks'] if c['id'].rsplit('.', 1)[-1] in independent)


@pytest.mark.parametrize('fault,check_id', [
    ('lost_save', 'desktop.saved_refresh_failure'), ('whitespace_client', 'desktop.whitespace_name'),
    ('whitespace_api', 'api.whitespace_ascii'),
])
def test_real_chinese_checks_detect_specific_generated_defects(chinese_tree, fault, check_id):
    path = chinese_tree/'apps/demo/src/App.tsx'
    if fault == 'lost_save':
        path.write_text(CHINESE_APP.replace('setContacts(previous => [...previous.filter(c => c.id !== created.id), created])', 'void created'), encoding='utf-8')
    elif fault == 'whitespace_client':
        path.write_text(CHINESE_APP.replace("if (!name.trim()) { setError('姓名不能为空白，请填写有效姓名'); return }", ''), encoding='utf-8')
    else:
        path = chinese_tree/'apps/demo-api/app/main.py'
        path.write_text(path.read_text(encoding='utf-8').replace('    if not payload.name.strip():\n        raise HTTPException(status_code=422, detail="姓名不能为空白")\n', ''), encoding='utf-8')
    actual = contacts_acceptance(chinese_tree, threading.Event(), contract=CONTRACT)
    assert actual['status'] == 'failed', actual
    assert any(c['id'] == check_id and c['status'] == 'failed' for c in actual['checks']), actual
    if fault == 'whitespace_api':
        assert all(c['status'] == 'passed' for c in actual['checks'] if c['id'].startswith('narrow.')), actual


def receipt():
    return {"status": "passed", "exitCode": 0, "log": json.dumps({
        "schemaVersion": "agenthub.workflow_contacts.v3", "contract": CONTRACT, "status": "passed",
        "checks": [{"id": name, "status": "passed"} for name in CHECKS]})}


def test_complete_chinese_boundary_receipt_is_recognized_without_relabeling_old_contracts():
    assert parse_result(receipt(), CONTRACT)["status"] == "passed"
    assert parse_result(receipt(), LEGACY)["status"] == "unavailable"
    assert parse_result(receipt(), RESILIENCE)["status"] == "unavailable"


@pytest.mark.parametrize("fault", ["missing", "duplicate", "schema", "contract", "exit", "contradictory"])
def test_incomplete_or_incoherent_boundary_evidence_cannot_pass(fault):
    command = receipt()
    data = json.loads(command["log"])
    if fault == "missing": data["checks"].pop()
    if fault == "duplicate": data["checks"][-1] = data["checks"][0]
    if fault == "schema": data["schemaVersion"] = "agenthub.workflow_contacts.v2"
    if fault == "contract": data["contract"] = RESILIENCE
    if fault == "exit": command["exitCode"] = 1
    if fault == "contradictory": data["checks"][0]["status"] = "failed"
    command["log"] = json.dumps(data)
    assert parse_result(command, CONTRACT)["status"] == "unavailable"
