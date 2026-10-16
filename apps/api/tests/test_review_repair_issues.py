from copy import deepcopy

import pytest

from app.review_repair_issues import MAX_ISSUES, review_issues


def evidence():
    return {"schemaVersion": "agenthub.qa.v1", "validation": {"profile": "vite-build-smoke-v1", "eventId": "server-event", "sourceFingerprint": "a" * 64},
            "rules": {"findings": []}, "commands": [{"kind": "check", "status": "failed", "versionBound": True}],
            "functional": {"status": "failed", "contract": {"schemaVersion": "agenthub.requirement_validation.v1", "target": "demo_heading_text", "expectedText": "Expected"},
                           "checks": [{"id": "desktop.text", "status": "failed"}, {"id": "narrow.text", "status": "passed"}]}}


def test_catalog_deduplicates_rule_findings_and_does_not_resolve_model_opinions():
    finding = {"file": "apps/demo/src/App.tsx", "line": 2, "message": "Check form labels", "severity": "low", "verified": True}
    qa = evidence()
    qa["rules"]["findings"] = [deepcopy(finding)]
    before = deepcopy(qa)
    issues = review_issues([finding], qa)
    assert [item["kind"] for item in issues] == ["finding", "command", "functional"]
    assert issues[0]["autoVerifiable"] is False
    assert issues[1]["autoVerifiable"] is True and issues[1]["checkKind"] == "check"
    assert issues[2]["autoVerifiable"] is True and issues[2]["checkId"] == "desktop.text"
    assert review_issues([finding], qa) == issues and qa == before


@pytest.mark.parametrize("mutation", ["legacy", "unbound", "unknown_profile", "missing_event", "unknown_check"])
def test_unverified_or_unknown_evidence_cannot_enable_automatic_resolution(mutation):
    qa = evidence()
    if mutation == "legacy": qa.pop("schemaVersion")
    if mutation == "unbound": qa["commands"][0]["versionBound"] = False
    if mutation == "unknown_profile": qa["validation"]["profile"] = "untrusted-profile"
    if mutation == "missing_event": qa["validation"].pop("eventId")
    if mutation == "unknown_check": qa["functional"]["checks"][0]["id"] = "arbitrary.script"
    issues = review_issues([], qa)
    if mutation == "unbound": assert not issues[0]["autoVerifiable"]
    elif mutation == "unknown_check": assert not issues[1]["autoVerifiable"]
    else: assert all(not item["autoVerifiable"] for item in issues)


def test_catalog_is_bounded_redacted_and_skips_malformed_data():
    assert review_issues(None, []) == []
    items = review_issues([None, {"message": 123}, {"message": "api_key=private-value", "file": ["bad"], "line": True}] +
                         [{"message": "Issue " + str(index)} for index in range(1000)])
    assert len(items) == MAX_ISSUES
    assert "private-value" not in str(items)
    assert items[0]["file"] is None and items[0]["line"] is None


def test_issue_identity_changes_with_selected_check_version():
    first = evidence()
    second = deepcopy(first)
    second["validation"]["eventId"] = "another-server-event"
    assert [item["id"] for item in review_issues([], first)] != [item["id"] for item in review_issues([], second)]


def test_failed_checks_are_retained_when_advisory_findings_fill_the_budget():
    items = review_issues([{"message": "Advisory " + str(index)} for index in range(100)], evidence())
    assert len(items) == MAX_ISSUES
    assert {item["kind"] for item in items[:2]} == {"command", "functional"}


def test_malformed_nested_metadata_fails_closed_without_crashing():
    qa = evidence()
    qa["validation"]["profile"] = []
    qa["commands"].extend([{"kind": []}, {"kind": "test", "status": {}}])
    issues = review_issues([], qa)
    assert all(not item["autoVerifiable"] for item in issues)


def test_backend_profile_cannot_claim_browser_check_eligibility():
    qa = evidence()
    qa["validation"]["profile"] = "fastapi-contract-v1"
    assert not next(item for item in review_issues([], qa) if item["kind"] == "functional")["autoVerifiable"]
