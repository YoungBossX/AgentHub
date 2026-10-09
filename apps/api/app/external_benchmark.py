"""Bounded external coding benchmark. No production database or mock fallback.

Run with the existing virtualenv from apps/api:
python -m app.external_benchmark --output <fresh-external-directory> --prepare-only
python -m app.external_benchmark --output <fresh-external-directory> --case title-normalization
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session as DbSession, SQLModel, create_engine, select

from app.external_workspaces import (
    ExternalWorkspaceRegistration, is_system_path, register_external_project_target,
)
from app.memory_snapshots import create_memory_snapshot, memory_snapshot_metadata
from app.memory_store import MemoryItemInput, create_memory_item
from app.models import Agent, Artifact, Diff, Session, Task, TaskRun, TaskRunEvent, Workspace
from app.process_environment import project_process_env, redact_process_evidence
from app.run_engine import RunWorker
from app.task_runs import create_task_run, metrics_for_run

REPO_ROOT = Path(__file__).resolve().parents[3]
SUITE_ROOT = Path(__file__).resolve().parents[1] / "benchmarks" / "external-tasks"
ALLOWED_FILE = "src/domain.mjs"
RULE = "Keep named ESM exports compatible. Do not introduce dependencies or alter the React scaffold."


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str | None:
    return sha256(path.read_bytes()) if path.is_file() and not path.is_symlink() else None


def command(args: list[str], cwd: Path, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=project_process_env(), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout)


def git(root: Path, *args: str) -> str:
    result = command(["git", "-c", "core.hooksPath=", *args], root)
    if result.returncode:
        raise RuntimeError(f"Fixture Git command failed: {args[0]}")
    return result.stdout.strip()


def load_suite(case_id: str | None = None) -> list[dict[str, Any]]:
    suite = json.loads((SUITE_ROOT / "suite.json").read_text(encoding="utf-8"))
    cases = suite["cases"]
    if case_id is not None:
        cases = [case for case in cases if case["id"] == case_id]
    if not cases:
        raise ValueError("Unknown benchmark case")
    for case in cases:
        if type(case.get("expectedTests")) is not int or case["expectedTests"] < 1:
            raise ValueError("Invalid expected benchmark test count")
        if not re.fullmatch(r"[a-z][a-z0-9-]+", case["id"]):
            raise ValueError("Invalid benchmark case ID")
        for key in ("baseline", "evaluator"):
            path = (SUITE_ROOT / case[key]).resolve()
            if path.parent != SUITE_ROOT.resolve() or not path.is_file():
                raise ValueError("Invalid benchmark fixture path")
    return cases


def reserve_output(output: Path) -> Path:
    if output.expanduser().is_symlink():
        raise ValueError("Benchmark output must not be a symbolic link")
    root = output.expanduser().resolve()
    if root == REPO_ROOT or REPO_ROOT in root.parents or is_system_path(root):
        raise ValueError("Benchmark output must be outside the checkout and system roots")
    root.mkdir(parents=True, exist_ok=False)
    return root


def prepare_fixture(output: Path, case: dict[str, Any]) -> dict[str, Any]:
    root = output / case["id"]
    target = root / "target"
    (target / "src").mkdir(parents=True)
    (root / "evaluator").mkdir()
    files = {
        ALLOWED_FILE: (SUITE_ROOT / case["baseline"]).read_text(encoding="utf-8"),
        "src/App.jsx": (
            "import React from 'react';\n"
            f"import {{ {case['exportName']} }} from './domain.mjs';\n"
            f"export default function App() {{ return <main>{{{case['appExpression']}}}</main>; }}\n"
        ),
        "src/main.jsx": "import React from 'react';\nimport { createRoot } from 'react-dom/client';\nimport App from './App.jsx';\ncreateRoot(document.getElementById('root')).render(<App />);\n",
        "index.html": '<div id="root"></div><script type="module" src="/src/main.jsx"></script>\n',
        "package.json": json.dumps({
            "name": f"agenthub-benchmark-{case['id']}", "private": True, "type": "module",
            "packageManager": "pnpm@10.33.4", "scripts": {"dev": "vite", "build": "vite build"},
            "dependencies": {"react": "19.2.1", "react-dom": "19.2.1"},
            "devDependencies": {"vite": "7.3.6"},
        }, indent=2) + "\n",
    }
    for name, content in files.items():
        (target / name).write_text(content, encoding="utf-8")
    evaluator = root / "evaluator" / "acceptance.test.mjs"
    evaluator.write_bytes((SUITE_ROOT / case["evaluator"]).read_bytes())
    git(target, "init", "-b", "main")
    git(target, "add", ".")
    git(target, "-c", "user.name=AgentHub Benchmark", "-c", "user.email=benchmark@example.invalid",
        "commit", "-m", "Frozen synthetic benchmark baseline")
    return {
        "target": target, "evaluator": evaluator,
        "baseCommit": git(target, "rev-parse", "HEAD"),
        "inputHashes": {name: file_hash(target / name) for name in files},
        "evaluatorHash": file_hash(evaluator), "promptHash": sha256(case["prompt"].encode()),
    }


def evaluate(evaluator: Path) -> dict[str, Any]:
    started = time.monotonic()
    try:
        result = command([
            "node", "--permission", f"--allow-fs-read={evaluator.parent}",
            f"--allow-fs-read={evaluator.parent.parent / 'target'}",
            str(evaluator),
        ], evaluator.parent)
        counts = {}
        for key in ("tests", "pass", "fail"):
            match = re.search(rf"^# {key} (\d+)\s*$", result.stdout, re.MULTILINE)
            counts[key] = int(match[1]) if match else None
        return {"exitCode": result.returncode, "counts": counts,
                "stdoutHash": sha256(result.stdout.encode()), "stderrHash": sha256(result.stderr.encode()),
                "stderrExcerpt": redact_process_evidence(result.stderr)[:1200],
                "elapsedSeconds": round(time.monotonic() - started, 3)}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"exitCode": None, "errorType": type(exc).__name__,
                "elapsedSeconds": round(time.monotonic() - started, 3)}


def score_case(evidence: dict[str, Any]) -> list[str]:
    """Return failure gates. Do not equate a green evaluator with TaskRun success."""
    gates = {
        "baseline_not_failing": evidence.get("baselineFailing") is True,
        "run_not_completed": evidence.get("state") == "completed",
        "provider_turn_unobserved": evidence.get("providerTurnObserved") is True,
        "post_check_failed": (
            type(evidence.get("expectedTests")) is int and evidence["expectedTests"] > 0 and
            evidence.get("postCheck", {}).get("exitCode") == 0 and
            evidence.get("postCheck", {}).get("counts", {}).get("tests") == evidence.get("expectedTests") and
            evidence.get("postCheck", {}).get("counts", {}).get("pass") == evidence.get("expectedTests") and
            evidence.get("postCheck", {}).get("counts", {}).get("fail") == 0
        ),
        "inputs_modified": evidence.get("immutableInputs") is True,
        "memory_receipt_invalid": evidence.get("memoryReceiptValid") is True,
        "scope_not_passed": evidence.get("scope", {}).get("status") == "passed",
        "diff_invalid": evidence.get("diffValid") is True,
    }
    return [name for name, passed in gates.items() if not passed]


def summary(cases: list[dict[str, Any]], *, prepare_only: bool) -> dict[str, Any]:
    passed = sum(case.get("verdict") == "passed" for case in cases)
    return {"selectedCases": len(cases), "passedCases": passed,
            "failedCases": sum(case.get("verdict") in {"failed", "harness_error"} for case in cases),
            "notAttemptedCases": sum(case.get("verdict") == "not_attempted" for case in cases),
            "providerTurnsObserved": sum(case.get("providerTurnObserved") is True for case in cases),
            "successRate": None if prepare_only else passed / len(cases)}


def save_report(output: Path, report: dict[str, Any], *, prepare_only: bool) -> None:
    report["summary"] = summary(report["cases"], prepare_only=prepare_only)
    temporary = output / "report.json.tmp"
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output / "report.json")


async def run_case(db: DbSession, workspace: Workspace, rule_id: str, rule_hash: str,
                   output: Path, case: dict[str, Any], *, prepare_only: bool) -> dict[str, Any]:
    fixture = prepare_fixture(output, case)
    target_root = fixture["target"]
    baseline = evaluate(fixture["evaluator"])
    evidence = {"caseId": case["id"], "verdict": "prepared" if prepare_only else "failed",
                "baseCommit": fixture["baseCommit"], "inputHashes": fixture["inputHashes"],
                "evaluatorHash": fixture["evaluatorHash"], "promptHash": fixture["promptHash"],
                "expectedTests": case["expectedTests"],
                "baselineCheck": baseline,
                "baselineFailing": (baseline.get("exitCode") == 1 and
                    baseline.get("counts", {}).get("tests") == case["expectedTests"] and
                    (baseline.get("counts", {}).get("fail") or 0) > 0),
                "providerTurnObserved": False}
    if prepare_only or not evidence["baselineFailing"]:
        if not evidence["baselineFailing"]:
            evidence["verdict"] = "failed"
            evidence["failureGates"] = ["baseline_not_failing"]
        return evidence
    target = register_external_project_target(db, workspace, ExternalWorkspaceRegistration(
        target_id=f"external-bench-{case['id']}", name=case["id"], root_path=str(target_root),
        project_type="vite-react", allowed_paths=[ALLOWED_FILE],
        package_manager="pnpm", detected_framework="vite-react",
    ))
    snapshot = create_memory_snapshot(db, workspace_id=workspace.id, reason="external_benchmark")
    session = Session(workspace_id=workspace.id, title=case["id"], bound_branch="main",
                      worktree_path=str(target_root), memory_snapshot_id=snapshot.id,
                      active_frontend_target_id=target.target_id)
    agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
    task = Task(session_id=session.id, title=case["id"], intent_type="frontend_change",
                assigned_agent_id=agent.id, plan_json=json.dumps({
                    "planner": "external_benchmark_fixed_v1", "targetId": target.target_id,
                    "safeTarget": ALLOWED_FILE, "files": [ALLOWED_FILE],
                    "originalRequest": case["prompt"], "executionMode": "write",
                }))
    db.add(session)
    db.add(task)
    db.commit()
    run = create_task_run(db, task.id, adapter_type="codex")
    print(f"{case['id']}: executing {run.id}", flush=True)
    started = time.monotonic()
    execution_error = None
    try:
        await RunWorker().run_once(db)
    except Exception as exc:
        execution_error = type(exc).__name__
        db.rollback()
    db.expire_all()
    run = db.get(TaskRun, run.id)
    metrics = metrics_for_run(run)
    events = db.exec(select(TaskRunEvent).where(TaskRunEvent.task_run_id == run.id)
                     .order_by(TaskRunEvent.sequence)).all()
    observed = []
    provider_messages = []
    provider_diagnostics = []
    provider_health = None
    for event in events:
        payload = json.loads(event.payload_json)
        codex_type = payload.get("codexEventType")
        observed.append({"id": event.id, "sequence": event.sequence, "type": event.event_type,
                         "codexEventType": codex_type})
        if event.event_type == "provider.health_checked":
            provider_health = payload
        if event.event_type == "message.delta" and isinstance(payload.get("text"), str):
            provider_messages.append(redact_process_evidence(payload["text"])[:2000])
        if event.event_type in {"completed", "error"} and payload.get("adapter") == "codex":
            provider_diagnostics.append({
                "eventId": event.id, "exitCode": payload.get("exitCode"),
                "stderrExcerpt": redact_process_evidence(payload.get("stderr", ""))[:1200],
            })
    event_types = {event["codexEventType"] for event in observed}
    receipt = metrics.get("memoryUsage") or {}
    memory_valid = (receipt.get("memorySnapshotId") == snapshot.id and
                    receipt.get("snapshotContentStatus") == "frozen" and
                    any(item.get("id") == rule_id and item.get("contentHash") == rule_hash and
                        item.get("layer") == "rule" and item.get("contentVisible") is True
                        and item.get("visibleContentHash") == rule_hash
                        for item in receipt.get("items", [])))
    diffs = db.exec(select(Diff).join(Artifact, Artifact.id == Diff.artifact_id)
                    .where(Artifact.task_run_id == run.id)).all()
    post_check = evaluate(fixture["evaluator"])
    current_patch = git(target_root, "diff", "--", ALLOWED_FILE)
    diff_records = [{"id": diff.id, "artifactId": diff.artifact_id,
                     "changedFiles": json.loads(diff.changed_files_json),
                     "patchHash": sha256(diff.patch_text.encode()),
                     "matchesWorkingTree": diff.patch_text.strip() == current_patch} for diff in diffs]
    diff_valid = len(diff_records) == 1 and bool(current_patch) and (
        diff_records[0]["changedFiles"] == [ALLOWED_FILE] and diff_records[0]["matchesWorkingTree"])
    immutable = file_hash(fixture["evaluator"]) == fixture["evaluatorHash"] and all(
        file_hash(target_root / name) == value for name, value in fixture["inputHashes"].items()
        if name != ALLOWED_FILE)
    evidence.update({
        "taskId": task.id, "taskRunId": run.id, "sessionId": session.id, "targetId": target.target_id,
        "state": run.state, "errorCode": run.error_code,
        "errorMessage": redact_process_evidence(run.error_message), "executionErrorType": execution_error,
        "elapsedSeconds": round(time.monotonic() - started, 3), "adapterRunId": run.adapter_run_id,
        "providerAssignment": metrics.get("providerAssignment"), "model": None,
        "providerHealth": redact_process_evidence(provider_health),
        "providerMessages": provider_messages[-8:],
        "providerDiagnostics": provider_diagnostics[-8:],
        "providerTurnObserved": "thread.started" in event_types and bool(event_types & {"turn.completed", "turn.finished"}),
        "events": observed, "memorySnapshot": memory_snapshot_metadata(snapshot), "memoryUsage": receipt,
        "canonicalContextHash": sha256(json.dumps(metrics.get("canonicalContextSnapshot"),
            sort_keys=True, separators=(",", ":")).encode()) if metrics.get("canonicalContextSnapshot") else None,
        "memoryReceiptValid": memory_valid, "scope": metrics.get("taskRunScopeDecision") or {},
        "completionValidation": metrics.get("completionValidation"),
        "diffs": diff_records, "diffValid": diff_valid, "immutableInputs": immutable,
        "resultFileHash": file_hash(target_root / ALLOWED_FILE), "postCheck": post_check,
        "artifacts": [{"id": item.id, "type": item.artifact_type, "status": item.status}
                      for item in db.exec(select(Artifact).where(Artifact.task_run_id == run.id)).all()],
    })
    evidence["failureGates"] = score_case(evidence)
    evidence["verdict"] = "failed" if evidence["failureGates"] else "passed"
    return evidence


async def run_benchmark(output: Path, *, prepare_only: bool = False, case_id: str | None = None) -> dict[str, Any]:
    cases = load_suite(case_id)
    root = reserve_output(output)
    source_hashes = {str(path.relative_to(REPO_ROOT)).replace("\\", "/"): file_hash(path)
                     for path in sorted((SUITE_ROOT.parent.parent / "app").rglob("*.py"))}
    suite_hashes = {path.name: file_hash(path) for path in sorted(SUITE_ROOT.iterdir()) if path.is_file()}
    report = {
        "schemaVersion": "agenthub.external_task_benchmark.v1", "recordedAt": datetime.now(timezone.utc).isoformat(),
        "mode": "prepare_only" if prepare_only else "live_codex", "developmentHead": git(REPO_ROOT, "rev-parse", "HEAD"),
        "sourceHashes": source_hashes, "suiteHashes": suite_hashes,
        "livePreviewStarted": False, "buildExecuted": False, "productionDeployed": False,
        "planner": "fixed_task_plan", "cases": [{"caseId": case["id"], "verdict": "not_attempted"} for case in cases],
    }
    save_report(root, report, prepare_only=prepare_only)
    engine = create_engine(f"sqlite:///{(root / 'benchmark.sqlite3').as_posix()}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    try:
        with DbSession(engine) as db:
            workspace = Workspace(name="External Task Benchmark", repo_url="local://benchmark", root_path=str(root), default_branch="main")
            db.add(workspace)
            db.add(Agent(name="Frontend Agent", role="frontend", adapter_type="codex", provider="local"))
            db.commit()
            rule = create_memory_item(db, MemoryItemInput(workspace_id=workspace.id, scope="project",
                memory_type="project_rule", source="user_explicit", title="Benchmark module contract",
                content_md=RULE, status="active", trust_level="user_confirmed"))
            for index, case in enumerate(cases):
                try:
                    evidence = await run_case(db, workspace, rule.id, rule.content_hash, root, case, prepare_only=prepare_only)
                except Exception as exc:
                    db.rollback()
                    evidence = {"caseId": case["id"], "verdict": "harness_error", "errorType": type(exc).__name__,
                                "errorMessage": redact_process_evidence(str(exc)), "providerTurnObserved": False}
                report["cases"][index] = evidence
                save_report(root, report, prepare_only=prepare_only)
                print(f"{case['id']}: {evidence['verdict']}", flush=True)
    finally:
        engine.dispose()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--case", choices=[case["id"] for case in load_suite()])
    args = parser.parse_args()
    report = asyncio.run(run_benchmark(args.output, prepare_only=args.prepare_only, case_id=args.case))
    return 0 if all(case["verdict"] in {"passed", "prepared"} for case in report["cases"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
