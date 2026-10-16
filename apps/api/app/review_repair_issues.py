"""Bounded issue identities from stored review evidence, never client claims."""
import hashlib
import json
import re

from app.requirement_validation import check_ids
from app.process_environment import redact_process_evidence

MAX_ISSUES = 32
MAX_FINDINGS = 128
MAX_TEXT = 1000
FAILED = {"failed", "timeout", "cancelled", "recorded_failed"}
PROFILES = {"vite-build-smoke-v1", "fastapi-contract-v1"}


def _text(value, limit=MAX_TEXT):
    return redact_process_evidence(value[:limit]).strip() if isinstance(value, str) else ""


def _list(value):
    return value if isinstance(value, list) else []


def _dict(value):
    return value if isinstance(value, dict) else {}


def _id(kind, value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return kind + ":" + hashlib.sha256(raw).hexdigest()[:32]


def _versioned(qa):
    validation = _dict(qa.get("validation"))
    return (qa.get("schemaVersion") == "agenthub.qa.v1" and isinstance(validation.get("profile"), str) and validation["profile"] in PROFILES
            and isinstance(validation.get("eventId"), str) and bool(validation["eventId"])
            and isinstance(validation.get("sourceFingerprint"), str) and re.fullmatch(r"[0-9a-f]{64}", validation["sourceFingerprint"]) is not None)


def review_issues(findings, qa=None):
    """Return a catalog, not a finding-resolution judgment.

    Automatic eligibility only means a matching *new*, version-bound independent
    check could later establish recovery. Model prose never enables that flag.
    Callers must supply immutable server-stored QA and validate ownership/source
    before preparing or sending any repair; this catalog grants no permissions.
    """
    qa = _dict(qa)
    issues, seen = [], set()
    for source, values in (("report", findings), ("rules", _dict(qa.get("rules")).get("findings"))):
        for index, finding in enumerate(_list(values)[:MAX_FINDINGS]):
            if not isinstance(finding, dict):
                continue
            message = _text(finding.get("message"))
            path = _text(finding.get("file"), 240) or None
            line = finding.get("line")
            line = line if type(line) is int and 1 <= line <= 1000000 else None
            identity = (path, line, message)
            if not message or identity in seen:
                continue
            seen.add(identity)
            item = {"kind": "finding", "source": source, "index": index, "message": message,
                    "file": path, "line": line, "severity": _text(finding.get("severity"), 16) or "unknown",
                    "autoVerifiable": False}
            issues.append({"id": _id("finding", item), **item})
            if len(issues) == MAX_ISSUES:
                break
        if len(issues) == MAX_ISSUES:
            break
    finding_issues = issues
    issues = []
    for command in _list(qa.get("commands"))[:3]:
        if (not isinstance(command, dict) or not isinstance(command.get("kind"), str)
                or command["kind"] not in {"check", "test", "build"} or not isinstance(command.get("status"), str) or command["status"] not in FAILED):
            continue
        kind = command["kind"]
        identity = {"checkKind": kind, "status": command["status"], "validation": _dict(qa.get("validation")).get("eventId")}
        issues.append({"id": _id("command", identity), "kind": "command", "checkKind": kind,
                       "message": {"check": "静态检查", "test": "测试", "build": "构建"}[kind] + "未通过",
                       "file": None, "line": None, "autoVerifiable": command.get("versionBound") is True and _versioned(qa)})
    functional = _dict(qa.get("functional"))
    contract = _dict(functional.get("contract"))
    try:
        declared = set(check_ids(contract))
    except (KeyError, TypeError):
        declared = set()
    for check in _list(functional.get("checks"))[:32]:
        if not isinstance(check, dict) or check.get("status") != "failed":
            continue
        name = _text(check.get("id"), 120)
        if not name:
            continue
        identity = {"checkId": name, "contract": contract, "validation": _dict(qa.get("validation")).get("eventId")}
        issues.append({"id": _id("functional", identity), "kind": "functional", "checkId": name,
                       "message": "需求检查未通过：" + name, "detail": _text(check.get("detail")), "file": None, "line": None,
                       "autoVerifiable": _versioned(qa) and _dict(qa.get("validation")).get("profile") == "vite-build-smoke-v1"
                       and name in declared and functional.get("status") == "failed"})
    if len(finding_issues) + len(issues) <= MAX_ISSUES:
        return finding_issues + issues
    # Failed independent checks cannot disappear behind a large advisory list.
    return (issues + finding_issues)[:MAX_ISSUES]
