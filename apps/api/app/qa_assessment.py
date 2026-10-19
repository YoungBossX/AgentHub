"""Server-owned review-time evidence; model prose never establishes acceptance."""

import hashlib
from copy import deepcopy
from typing import Any

from sqlmodel import Session as DbSession

from app.external_evidence import list_task_run_command_evidence
from app.models import Artifact, Session, Task, TaskRun
from app.target_registry import TargetRegistryError, get_target_for_workspace
from app.automatic_validation import validation_for_run, validation_currentness, required_command_kinds


def build_qa_assessment(
    db: DbSession, artifact: Artifact, *, plan: dict[str, Any],
    files: list[str], patch: str, findings: list[dict[str, Any]],
    model_status: str | None = None, input_fingerprint: str | None = None,
) -> dict[str, Any]:
    run = db.get(TaskRun, artifact.task_run_id)
    task = db.get(Task, run.task_id) if run else None
    session = db.get(Session, task.session_id) if task else None
    target = None
    target_id = plan.get("targetId")
    if session and isinstance(target_id, str):
        try:
            target = get_target_for_workspace(db, session.workspace_id, target_id)
        except TargetRegistryError:
            pass

    violations = [path for path in files if target and not target.permits_path(path)]
    rule_status = (
        "failed" if violations or any(f.get("severity") == "high" for f in findings)
        else "unknown" if target is None
        else "warning" if findings else "passed"
    )
    receipts = list_task_run_command_evidence(db, artifact.task_run_id)
    commands = []
    for kind in ("check", "test", "build"):
        configured = getattr(target, f"{kind}_command", None) if target else None
        matching = [item for item in receipts if configured and item.target_id == target_id
                    and item.command_type == kind and item.command == configured]
        # These legacy receipts record exit codes, not the source version tested.
        status = ("recorded_failed" if any(item.exit_code != 0 for item in matching)
                  else "recorded_passed" if matching else "not_run")
        commands.append({
            "kind": kind, "status": status, "configured": bool(configured),
            "versionBound": False,
            "evidence": [{"artifactId": item.artifact_id, "taskRunId": item.task_run_id,
                          "command": item.command, "exitCode": item.exit_code}
                         for item in matching],
        })
    validation = validation_for_run(db, artifact.task_run_id)
    currentness = validation_currentness(db, artifact.task_run_id, validation) if validation else None
    if validation:
        required = required_command_kinds(validation.get("profile"))
        for item in commands:
            if item["kind"] not in required:
                item.update(configured=False, versionBound=False, status="not_applicable", evidence=[])
                continue
            entry = next((entry for entry in validation.get("commands", []) if entry.get("kind") == item["kind"]), None)
            item.update(configured=True, versionBound=currentness == "current")
            item["status"] = entry["status"] if entry and currentness == "current" else "not_run"
            item["evidence"] = ([{"eventId": validation["eventId"], "taskRunId": artifact.task_run_id,
                                 "command": entry["command"], "exitCode": entry["exitCode"],
                                 "log": entry.get("log", ""), "durationMs": entry.get("durationMs", 0)}] if entry else [])
    functional = validation.get("functional") if validation else None
    blocked = (rule_status == "failed" or model_status == "failed"
               or (currentness == "current" and validation and validation.get("status") == "failed")
               or (currentness == "current" and functional and functional.get("status") == "failed")
               or any(item["status"] in {"recorded_failed", "failed", "timeout", "cancelled"} for item in commands))
    passed = (not blocked and rule_status == "passed" and model_status == "passed"
              and bool(input_fingerprint) and currentness == "current"
              and validation.get("status") == "passed"
              and bool(required_command_kinds(validation.get("profile")))
              and all(item["status"] == "passed" and item["versionBound"]
                      for item in commands if item["configured"]))
    result = {
        "schemaVersion": "agenthub.qa.v1",
        "taskRunId": artifact.task_run_id, "diffArtifactId": artifact.id,
        "patchSha256": hashlib.sha256(patch.encode("utf-8")).hexdigest(),
        "inputFingerprint": input_fingerprint,
        "status": "blocked" if blocked else "passed" if passed else "incomplete",
        "rules": {"status": rule_status, "violations": violations, "findings": findings},
        "model": {"status": model_status or "not_run", "source": "native" if model_status else "none"},
        "commands": commands,
        "acceptance": ("requirement_checks_passed" if functional and functional.get("status") == "passed" else "configured_checks_passed") if passed else "not_established",
    }
    if validation:
        result.update(validation={key: value for key, value in validation.items() if key not in {"files", "commands", "functional"}},
                      currentness=currentness)
    if functional:
        result["functional"] = deepcopy(functional)
        if currentness != "current" and functional.get("status") in {"passed", "failed"}:
            result["functional"]["status"] = "expired" if currentness == "expired" else "unknown"
    return result


def current_qa_assessment(db: DbSession, qa):
    """Read-time overlay; never rewrite the historical assessment in SQLite."""
    if not isinstance(qa, dict) or not isinstance(qa.get("validation"), dict):
        return qa
    result = deepcopy(qa)
    currentness = validation_currentness(db, qa.get("taskRunId"), qa["validation"])
    result["currentness"] = currentness
    if currentness != "current":
        result["status"] = "expired" if currentness == "expired" else "incomplete"
        result["acceptance"] = "not_established"
        if result.get("functional", {}).get("status") in {"passed", "failed"}:
            result["functional"]["status"] = "expired" if currentness == "expired" else "unknown"
        for command in result.get("commands", []):
            if command.get("versionBound"):
                command.update(status="expired" if currentness == "expired" else "unknown", versionBound=False)
    return result
