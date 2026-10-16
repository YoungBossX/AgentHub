import json
import threading

import pytest

from app import workflow_acceptance as acceptance
from app.backend_validation import validate_backend_copy
from app.contacts_contract import LEGACY, RESILIENCE, CONTRACTS, check_ids, parse_result, policy
from app.workflow_suite import prepare_source, select_scenarios
from test_workflow_evaluation import CONTACT_APP, fix_source


@pytest.fixture
def contacts_tree(tmp_path):
    scenario = select_scenarios("coordinated-contacts")[0]
    root = prepare_source(tmp_path, scenario)
    fix_source(root, scenario)
    return root


def result(contract=RESILIENCE):
    return {"status": "passed", "exitCode": 0, "log": json.dumps({
        "schemaVersion": CONTRACTS[contract][0], "contract": contract, "status": "passed",
        "checks": [{"id": name, "status": "passed"} for name in check_ids(contract)]})}


@pytest.mark.parametrize("fault", ["schema", "contract", "coverage", "duplicate_id", "exit", "status", "check_status"])
def test_partial_wrong_contract_or_incoherent_browser_receipts_never_pass(fault):
    command = result()
    data = json.loads(command["log"])
    if fault == "schema": data["schemaVersion"] = CONTRACTS[LEGACY][0]
    if fault == "contract": data["contract"] = LEGACY
    if fault == "coverage": data["checks"].pop()
    if fault == "duplicate_id": data["checks"][1]["id"] = data["checks"][0]["id"]
    if fault == "exit": command["exitCode"] = 1
    if fault == "status": command["status"] = "cancelled"
    if fault == "check_status": data["checks"][0]["status"] = "skipped"
    command["log"] = json.dumps(data)
    assert parse_result(command, RESILIENCE)["status"] == "unavailable"
    assert parse_result(result(LEGACY), LEGACY)["status"] == "passed"


@pytest.mark.parametrize("payload", [None, [], True, 1, "passed"])
def test_non_object_receipts_fail_closed(payload):
    command = {**result(), "log": json.dumps(payload)}
    assert parse_result(command, RESILIENCE)["status"] == "unavailable"


@pytest.mark.parametrize("fault,failed_check", [
    ("company_limit", "api.field_boundaries"), ("defaults", "api.unique_identity"),
    ("identity", "api.unique_identity"), ("seed_duplicate", "api.seed_duplicate"),
    ("optional_type", "api.invalid_types"), ("method", "api.method_contract"),
])
def test_real_extended_api_contract_detects_business_defects(contacts_tree, fault, failed_check):
    path = contacts_tree / "apps/demo-api/app/main.py"
    text = path.read_text(encoding="utf-8")
    changes = {
        "company_limit": ('company: Optional[str] = Field(default=None, max_length=120)', 'company: Optional[str] = Field(default=None, max_length=200)'),
        "defaults": ('status: str = Field(default="lead"', 'status: str = Field(default="active"'),
        "identity": ('f"contact-{uuid4()}"', '"contact-fixed"'),
        "seed_duplicate": ('if any(contact.email == payload.email', 'if payload.email != "ada@example.com" and any(contact.email == payload.email'),
        "optional_type": ('company: Optional[str]', 'company: Optional[object]'),
        "method": ('@app.post("/contacts"', '@app.put("/contacts")\n@app.post("/contacts"'),
    }
    old, new = changes[fault]
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")
    actual = validate_backend_copy(contacts_tree, threading.Event())
    assert actual["status"] == "failed", actual
    log = actual["commands"][-1]["log"]
    receipt = json.loads(next(line.split("=", 1)[1] for line in log.splitlines() if line.startswith("AGENTHUB_BACKEND_RESULT=")))
    from app.backend_validation import CHECKS
    passed = [c["id"] for c in receipt["checks"]]
    assert passed == list(CHECKS["test"][:CHECKS["test"].index(failed_check)])


def test_real_contacts_resilience_and_both_source_policy_receipts(contacts_tree):
    actual = acceptance.contacts_acceptance(contacts_tree, threading.Event(), contract=RESILIENCE)
    assert actual["status"] == "passed", actual
    assert [c["id"] for c in actual["checks"]] == check_ids(RESILIENCE)
    assert actual["contract"] == RESILIENCE and len(actual["policyFingerprint"]) == 64
    assert actual["frontendFingerprint"] and actual["backendFingerprint"]
    assert sum(r.get("injected") == "fixed_503" for r in actual["requests"]) == 2
    assert sum(r["method"] == "POST" and r["status"] == 201 for r in actual["requests"]) == 4
    assert sum(r["method"] == "POST" and r["status"] == 409 for r in actual["requests"]) == 2


@pytest.mark.parametrize("fault,expected", [
    ("ignore_rejection", "duplicate"), ("clear_input", "server_failure"),
    ("optimistic_failure", "duplicate"), ("changed_existing_names", "duplicate"),
    ("no_recovery", "retry"), ("invalid_form", "invalid"),
])
def test_real_browser_detects_failure_handling_defects(contacts_tree, fault, expected):
    text = CONTACT_APP
    if fault == "ignore_rejection": text = text.replace('if (!response.ok) throw new Error(`Request failed: ${response.status}`)', '')
    if fault == "clear_input": text = text.replace('catch (problem) {', "catch (problem) { setName(''); setEmail('');")
    if fault == "optimistic_failure": text = text.replace('catch (problem) {', "catch (problem) { setContacts(previous => [...previous, {id: 'optimistic', name, email}]);")
    if fault == "changed_existing_names": text = text.replace('catch (problem) {', "catch (problem) { setContacts(previous => previous.map(contact => ({...contact, name: 'Changed ' + contact.name}))); ")
    if fault == "no_recovery": text = text.replace("event.preventDefault()", "event.preventDefault(); if (error) return")
    if fault == "invalid_form": text = text.replace('<form onSubmit={create}>', '<form noValidate onSubmit={create}>').replace(' required ', ' ')
    assert text != CONTACT_APP
    (contacts_tree / "apps/demo/src/App.tsx").write_text(text, encoding="utf-8")
    actual = acceptance.contacts_acceptance(contacts_tree, threading.Event(), contract=RESILIENCE)
    assert actual["status"] == "failed", actual
    assert any(c["id"].endswith('.' + expected) and c["status"] == "failed" for c in actual["checks"]), actual


@pytest.mark.parametrize("fault", ["source", "policy", "cancelled"])
def test_integration_copy_rejects_source_policy_drift_and_cancellation(contacts_tree, monkeypatch, fault):
    calls = []
    def command(*args):
        calls.append(args)
        if len(calls) == 1: return {"status": "passed"}
        if fault == "cancelled": return {"status": "cancelled"}
        if fault == "source":
            path = contacts_tree / "apps/demo-api/app/main.py"
            path.write_bytes(path.read_bytes() + b'\n# source drift\n')
        return result()
    monkeypatch.setattr(acceptance, "run_command", command)
    if fault == "policy":
        values = iter(("before", "after"))
        monkeypatch.setattr(acceptance, "policy", lambda *args: next(values))
    actual = acceptance.contacts_acceptance(contacts_tree, threading.Event(), contract=RESILIENCE)
    assert actual["status"] == ("cancelled" if fault == "cancelled" else "stale")


def test_contract_and_both_validation_policies_are_part_of_identity():
    front, back = {"policyFingerprint": "front"}, {"policyFingerprint": "back"}
    first = policy(RESILIENCE, front, back)
    assert first != policy(LEGACY, front, back)
    assert first != policy(RESILIENCE, {"policyFingerprint": "changed"}, back)
    assert first != policy(RESILIENCE, front, {"policyFingerprint": "changed"})
