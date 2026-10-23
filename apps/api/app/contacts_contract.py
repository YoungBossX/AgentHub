"""Fixed integration contracts; no model-provided selectors or executable checks."""
import hashlib
import json

from app.automatic_validation import digest
from app.worktrees import repo_root

LEGACY = "contacts-create-v1"
RESILIENCE = "contacts-resilience-v2"
BOUNDARIES = "contacts-boundaries-v3"
CONTRACTS = {LEGACY: ("agenthub.workflow_contacts.v1", ("initial", "create", "persist", "layout", "runtime")),
    RESILIENCE: ("agenthub.workflow_contacts.v2", ("initial", "create", "duplicate", "invalid", "server_failure", "retry", "persist", "layout", "runtime")),
    BOUNDARIES: ("agenthub.workflow_contacts.v3", ("initial", "create", "duplicate", "invalid", "server_failure", "retry", "persist",
        "same_local_distinct_domain", "case_insensitive_duplicate", "saved_refresh_failure", "whitespace_name", "layout", "runtime"))}


def check_ids(contract):
    return [f"{view}.{name}" for view in ("desktop", "narrow") for name in CONTRACTS[contract][1]] + (
        ["api.whitespace_ascii", "api.whitespace_unicode"] if contract == BOUNDARIES else [])


def policy(contract, frontend, backend):
    platform = repo_root()
    files = ("scripts/workflow-contacts-check.mjs", "scripts/workflow-api-bridge.py",
             "scripts/demo-backend-check.py", "scripts/demo-validation-build.mjs",
             "apps/api/app/workflow_acceptance.py", "apps/api/app/contacts_contract.py")
    return digest({"contract": contract, "checks": check_ids(contract), "frontend": frontend["policyFingerprint"],
        "backend": backend["policyFingerprint"],
        "files": {name: hashlib.sha256((platform / name).read_bytes()).hexdigest() for name in files}})


def parse_result(result, contract):
    """A green exit, partial check list or different contract cannot establish pass."""
    unavailable = {"status": "unavailable", "reason": "incomplete_integration_evidence", "checks": []}
    try:
        parsed = json.loads(result["log"])
        if not isinstance(parsed, dict):
            return unavailable
        if parsed.get("schemaVersion") != CONTRACTS[contract][0]:
            return unavailable
        # v1 predates explicit contract metadata. v2 must always echo its enum.
        if contract != LEGACY and parsed.get("contract") != contract:
            return unavailable
        if parsed.get("status") == "unavailable":
            return {**unavailable, "reason": "workflow_transport_or_browser_unavailable"}
        checks = parsed["checks"]
        if [c["id"] for c in checks] != check_ids(contract) or any(c["status"] not in {"passed", "failed"} for c in checks):
            return unavailable
        passed = all(c["status"] == "passed" for c in checks)
        expected = "passed" if passed else "failed"
        if parsed["status"] != expected or result["status"] != expected or result["exitCode"] != (0 if passed else 1):
            return unavailable
        return parsed
    except (ValueError, KeyError, TypeError):
        return unavailable
