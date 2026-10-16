"""Frozen evaluation cohort identity, explicit invalidation and elapsed summaries."""
import hashlib
import json
import statistics
import sys


def cohort(source_policy, *, development_head, adapter, qa_adapter, scenarios, repetitions, max_retries):
    identity = {"developmentHead": development_head, "sourcePolicy": source_policy,
        "codingAdapter": adapter, "qaAdapter": qa_adapter, "python": sys.version,
        "selectedScenarios": scenarios, "repetitions": repetitions, "maxRetriesPerTask": max_retries}
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"id": fingerprint, "status": "frozen", "identity": identity,
        "limits": "Same implementation/input policy, not a model-version guarantee; fixed scenario repetitions are not distinct business tasks."}


def invalidate(report, *, reason, index):
    report["cohort"].update(status="invalidated", reason=reason, detectedAtCase=index)
    for case in report["cases"]:
        case.setdefault("observedVerdict", case["verdict"])
        case["cohortStatus"] = "invalidated"
        case["failureGates"] = sorted(set([*case.get("failureGates", []), reason]))
        if case["verdict"] not in {"not_attempted", "running", "preparing"}:
            case["verdict"] = "invalidated"


def elapsed_stats(values):
    known = [value for value in values if isinstance(value, (int, float)) and value >= 0]
    return {"observed": len(known), "unknown": len(values) - len(known),
        "totalSeconds": round(sum(known), 3) if known else None,
        "medianSeconds": statistics.median(known) if known else None,
        "maxSeconds": max(known) if known else None}


def role_stats(cases):
    attempts = [attempt for case in cases for phase in case.get("phases", []) for attempt in phase.get("attempts", [])]
    result = {}
    for name, roles in (("coding", {"frontend", "backend"}), ("qa", {"qa", "review"})):
        selected = [attempt for attempt in attempts if attempt.get("role") in roles]
        result[name] = {"attempts": len(selected), "retries": sum(bool(a.get("retryOfRunId")) for a in selected),
            "completed": sum(a.get("state") == "completed" for a in selected),
            "elapsed": elapsed_stats([a.get("elapsedSeconds") for a in selected])}
    return result
