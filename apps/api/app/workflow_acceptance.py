"""Independent, fixed workflow acceptance outside Agent-writable source."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading

from app.automatic_validation import capture_validation_source, digest, run_command, validate_copy, validation_environment
from app.backend_validation import capture_backend_source, validate_backend_copy
from app.worktrees import repo_root
from app.contacts_contract import LEGACY, CONTRACTS, check_ids, parse_result, policy

CONTACT_IDS = check_ids(LEGACY)


def contacts_acceptance(root, cancelled, *, contract=LEGACY):
    if contract not in CONTRACTS:
        raise ValueError("Unsupported contacts business contract.")
    frontend, front_contents = capture_validation_source(root)
    backend, back_contents = capture_backend_source(root)
    before_policy = policy(contract, frontend, backend)
    platform = repo_root()
    node = shutil.which("node")
    if node is None:
        return {"status": "unavailable", "reason": "node_missing"}
    with tempfile.TemporaryDirectory(prefix="agenthub-workflow-check-") as directory:
        copy = Path(directory).resolve()
        for relative, raw in {**front_contents, **back_contents}.items():
            path = copy / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        data = copy / "data"
        data.mkdir()
        project = copy / "apps/demo"
        link = project / "node_modules"
        link.symlink_to((platform / "apps/demo/node_modules").resolve(), target_is_directory=True)
        env = validation_environment()
        env.update({key: str(data) for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR")})
        env.update(AGENTHUB_VALIDATION_OUTPUT=str(project / "dist"), AGENTHUB_WORKFLOW_PYTHON=sys.executable,
                   AGENTHUB_WORKFLOW_BACKEND=str(copy / "apps/demo-api"), AGENTHUB_WORKFLOW_DATA=str(data),
                   AGENTHUB_CONTACTS_CONTRACT=contract)
        try:
            build = run_command([node, str(platform / "scripts/demo-validation-build.mjs")], project, env, cancelled)
            if build["status"] != "passed":
                return {"status": build["status"], "reason": "integration_build_failed", "checks": []}
            result = run_command([node, str(platform / "scripts/workflow-contacts-check.mjs")], project, env, cancelled)
            if result["status"] in {"timeout", "cancelled"}:
                return {"status": result["status"], "contract": contract, "checks": []}
            try:
                parsed = parse_result(result, contract)
                if parsed.get("status") == "unavailable":
                    return parsed
                unchanged = (capture_validation_source(root)[0] == frontend and capture_backend_source(root)[0] == backend)
                # Verify both copied input sets; target code runs with write denial,
                # and the source hash is checked again independently after execution.
                from app.automatic_validation import capture_validation_source_copy
                unchanged = unchanged and capture_validation_source_copy(copy, front_contents) and capture_backend_source(copy)[0] == backend
                unchanged = unchanged and policy(contract, frontend, backend) == before_policy
                return {"status": "cancelled" if cancelled.is_set() else "stale" if not unchanged else parsed["status"],
                        "contract": contract, "policyFingerprint": before_policy,
                        "checks": parsed["checks"], "requests": parsed.get("requests", []), "browserVersion": parsed.get("browserVersion"),
                        "frontendFingerprint": frontend["sourceFingerprint"], "backendFingerprint": backend["sourceFingerprint"]}
            except (ValueError, KeyError, TypeError):
                return {"status": result["status"] if result["status"] in {"timeout", "cancelled"} else "unavailable",
                        "reason": "missing_integration_evidence", "checks": []}
        finally:
            if link.is_symlink():
                link.unlink()


def evaluate_scenario(root, scenario, phase=0, *, cancelled=None):
    cancelled = cancelled if cancelled is not None else threading.Event()
    results = {}
    try:
        if scenario.backend:
            results["backend"] = validate_backend_copy(root, cancelled)
        if scenario.frontend:
            contract = ({"schemaVersion": "agenthub.requirement_validation.v1", "target": "demo_heading_text",
                         "expectedText": scenario.headings[phase]} if scenario.headings else None)
            results["frontend"] = validate_copy(root, cancelled, requirement_contract=contract)
        if scenario.integration:
            results["integration"] = contacts_acceptance(root, cancelled, contract=scenario.contacts_contract)
    except (OSError, ValueError) as exc:
        results["environment"] = {"status": "unavailable", "reason": type(exc).__name__}
    statuses = [value["status"] for value in results.values()]
    status = ("unavailable" if any(s in {"unavailable", "incomplete", "stale", "cancelled", "timeout"} for s in statuses)
              else "passed" if statuses and all(s == "passed" for s in statuses) else "failed")
    return {"status": status, "results": results, "expectedFingerprint": digest({"id": scenario.id, "phase": phase, "headings": scenario.headings})}
