"""Reproducible natural-language local workflow evaluation, never production DB.

python -m app.workflow_evaluation --output <fresh-external-path> --prepare-only
Live execution uses existing configured Planner/CLI providers; no mock fallback.
"""
import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import statistics
import threading
import time

from fastapi import BackgroundTasks
from sqlmodel import Session as DbSession, create_engine, select

from app.db_migrations import prepare_database
from app.automatic_validation import validation_for_run
from app.external_benchmark import reserve_output, git, file_hash
from app.group_execution import enqueue_ready_group_tasks
from app.models import Agent, Artifact, Diff, Session, Task, TaskRun, TaskRunEvent, Workspace
from app.native_reviews import _read_file, _no_link
from app.process_environment import redact_process_evidence
from app.routes.messages import create_message
from app.run_engine import RunWorker, interrupt_supervised_task_run
from app.schemas import MessageCreateRequest
from app.seed import seed_demo_data
from app.task_runs import metrics_for_run, retry_task_run, interrupt_task_run, TaskRunLifecycleError
from app.workflow_acceptance import evaluate_scenario
from app.workflow_suite import RULE, Scenario, permitted, prepare_source, select_scenarios
from app.memory_store import MemoryItemInput, create_memory_item
from app.planner_observation import observe_planner_calls
from app.worktrees import repo_root
from app.workflow_review_evidence import attempt_seconds, collect_reviews, review_gates
from app.workflow_cohort import cohort, invalidate, role_stats, elapsed_stats
from app.workflow_profiles import bound_scenario, configure_profiles, QA_PROMPT

SCHEMA = "agenthub.workflow_evaluation.v2"
TERMINAL = {"completed", "failed", "interrupted", "cancelled"}


def hashes(root):
    result = {}
    for directory, directories, files in os.walk(root, followlinks=False):
        directories[:] = [name for name in directories if name != ".git"]
        for name in directories:
            _no_link(Path(directory) / name)
        for name in files:
            path = Path(directory) / name
            result[path.relative_to(root).as_posix()] = _read_file(root, path)["sha256"]
        if len(result) > 1024:
            raise ValueError("Workflow source exceeds the fixed file budget.")
    return result


def source_policy():
    platform = repo_root()
    paths = (list((platform / "apps/api/app").rglob("*.py"))
             + list((platform / "scripts").glob("*.py")) + list((platform / "scripts").glob("*.mjs")))
    paths += list((platform / "patches").glob("*.patch"))
    paths += [platform / name for name in ("package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", "apps/api/requirements.txt")]
    for name in ("demo", "demo-api"):
        for base, directories, files in os.walk(platform / "apps" / name, followlinks=False):
            directories[:] = [item for item in directories if item not in {"node_modules", "dist", "__pycache__", ".pytest_cache"}]
            paths.extend(Path(base) / file for file in files if not file.startswith(".env"))
    return {path.relative_to(platform).as_posix(): file_hash(path) for path in sorted(set(paths))}


def policy_matches(expected):
    try:
        return source_policy() == expected
    except (OSError, ValueError):
        return False  # an unreadable source is not evidence of a frozen cohort


def collect_attempt(db, run, root):
    task = db.get(Task, run.task_id)
    plan = json.loads(task.plan_json)
    metrics = metrics_for_run(run)
    events = db.exec(select(TaskRunEvent).where(TaskRunEvent.task_run_id == run.id).order_by(TaskRunEvent.sequence)).all()
    native = [json.loads(event.payload_json) for event in events]
    codex = {p.get("codexEventType") for p in native}
    claude = {p.get("claudeEventType") for p in native}
    observed = (("thread.started" in codex and bool(codex & {"turn.completed", "turn.finished"}))
                or (bool(claude & {"system", "session.started", "init"}) and bool(claude & {"result", "completed", "turn.completed"})))
    diffs = db.exec(select(Diff).join(Artifact, Artifact.id == Diff.artifact_id).where(Artifact.task_run_id == run.id)).all()
    return {"taskRunId": run.id, "taskId": task.id, "role": plan.get("assignedRole"), "targetId": plan.get("targetId"),
            "elapsedSeconds": attempt_seconds(run), "startedAt": run.started_at.isoformat() if run.started_at else None,
            "endedAt": run.ended_at.isoformat() if run.ended_at else None,
            "state": run.state, "errorCode": run.error_code, "adapterRunId": run.adapter_run_id,
            "retryOfRunId": metrics.get("retryOfRunId"), "providerAssignment": metrics.get("providerAssignment"),
            "providerTurnObserved": observed, "scope": metrics.get("taskRunScopeDecision"),
            "completion": metrics.get("completionValidation"), "memoryUsage": metrics.get("memoryUsage"),
            "validation": validation_for_run(db, run.id),
            "reviews": collect_reviews(db, run, [json.loads(event.payload_json) for event in events if event.event_type == "completed"]),
            "diffs": [{"id": diff.id, "artifactId": diff.artifact_id, "files": json.loads(diff.changed_files_json),
                       "patchHash": hashlib.sha256(diff.patch_text.encode()).hexdigest(), "nonempty": bool(diff.patch_text.strip()),
                       "currentFileHashes": {path: file_hash(root / path) for path in json.loads(diff.changed_files_json)}} for diff in diffs],
            "events": [{"id": event.id, "type": event.event_type, "sequence": event.sequence} for event in events]}


def phase_gates(scenario, phase):
    gates = []
    if not phase.get("nativePlanning") and not (phase.get("testExecution") and phase.get("planningSource") == "fake_test"):
        gates.append("native_planning_unobserved")
    attempts = phase.get("attempts", [])
    for target in (["demo-backend"] if scenario.backend else []) + (["demo-frontend"] if scenario.frontend else []):
        writers = [a for a in attempts if a["targetId"] == target and a["role"] in {"backend", "frontend"}]
        last = writers[-1] if writers else {}
        if last.get("state") != "completed": gates.append(f"{target}:execution_incomplete")
        if not last.get("providerTurnObserved"): gates.append(f"{target}:provider_turn_unobserved")
        if phase.get("requireNativeQa") and (last.get("providerAssignment") or {}).get("adapterType") != phase.get("codingAdapter"):
            gates.append(f"{target}:coding_adapter_mismatch")
        if (last.get("scope") or {}).get("status") != "passed": gates.append(f"{target}:scope_not_passed")
        if not last.get("diffs") or not all(d.get("nonempty") for d in last["diffs"]): gates.append(f"{target}:diff_missing")
        if (last.get("validation") or {}).get("status") != "passed": gates.append(f"{target}:automatic_checks_not_passed")
        expected = phase.get("acceptance", {}).get("results", {}).get("backend" if target == "demo-backend" else "frontend", {})
        if not expected.get("sourceFingerprint"):
            gates.append(f"{target}:validation_source_unverified")
        elif (last.get("validation") or {}).get("sourceFingerprint") != expected.get("sourceFingerprint"):
            gates.append(f"{target}:validation_source_mismatch")
        if not _rule_visible(last.get("memoryUsage"), phase):
            gates.append(f"{target}:memory_binding_invalid")
        if phase.get("requireNativeQa"):
            reviewers = [a for a in attempts if a.get("targetId") == target and a.get("role") in {"qa", "review"}]
            gates.extend(review_gates(target, last, reviewers, phase))
    if not phase.get("plannerReceipts") or not all(_rule_visible(receipt, phase) for receipt in phase["plannerReceipts"]):
        gates.append("planner_memory_binding_invalid")
    if not phase.get("allTasksCompleted"):
        gates.append("planned_tasks_incomplete")
    if phase.get("acceptance", {}).get("status") != "passed": gates.append("independent_acceptance_failed")
    if not phase.get("immutableInputs"): gates.append("immutable_inputs_changed")
    changed = phase.get("changedPaths", [])
    if scenario.multi_file and len([path for path in changed if path.startswith("apps/demo/src/")]) < 2:
        gates.append("multi_file_output_missing")
    if scenario.fault_injection:
        initial = attempts[0] if attempts else {}
        if initial.get("state") != "failed" or not any(a.get("retryOfRunId") == initial.get("taskRunId") for a in attempts[1:]):
            gates.append("recovery_lineage_missing")
    return gates


def _rule_visible(receipt, phase):
    return (isinstance(receipt, dict) and phase.get("requiredSnapshotId") is not None
            and receipt.get("memorySnapshotId") == phase["requiredSnapshotId"] and receipt.get("snapshotContentStatus") == "frozen"
            and any(item.get("id") == phase.get("requiredRuleId") and item.get("contentHash") == phase.get("requiredRuleHash")
                    and item.get("layer") == "rule" and item.get("contentVisible") is True
                    and item.get("visibleContentHash") == phase.get("requiredRuleHash") for item in receipt.get("items", [])))


def aggregate(cases, *, mode, cohort_valid=True):
    def stats(items):
        attempted = [case for case in items if case.get("observedVerdict", case["verdict"]) != "not_attempted"]
        finalized = [case for case in attempted if case.get("observedVerdict", case["verdict"]) not in {"running", "preparing"}]
        durations = [case["elapsedSeconds"] for case in items if case.get("elapsedSeconds") is not None]
        failures = {}
        for case in items:
            for gate in case.get("failureGates", []): failures[gate] = failures.get(gate, 0) + 1
        denominator = len(items)
        live = mode == "live" and cohort_valid
        return {"selected": denominator, "attempted": len(attempted), "finalized": len(finalized), "timed": len(durations),
                "passed": sum(c.get("verdict") == "passed" for c in items),
                "firstAttemptPassed": sum(c.get("firstAttemptPassed") is True for c in items),
                "firstAttemptSuccessRate": sum(c.get("firstAttemptPassed") is True for c in items) / denominator if live and denominator else None,
                "finalSuccessRate": sum(c.get("verdict") == "passed" for c in items) / denominator if live and denominator else None,
                "retryCount": sum(c.get("retryCount", 0) for c in items),
                "roles": role_stats(items),
                "totalElapsed": elapsed_stats([case.get("totalElapsedSeconds") for case in items]),
                "nativeQaVerifiedAttempts": sum(bool(a.get("reviews")) and all(r.get("verifiedNativeReceipt") for r in a["reviews"])
                    for case in items for phase in case.get("phases", []) for a in phase.get("attempts", []) if a.get("role") in {"qa", "review"}),
                "medianElapsedSeconds": statistics.median(durations) if durations else None,
                "maxElapsedSeconds": max(durations) if durations else None, "failureCounts": failures}
    return {**stats(cases), "naturalScenarios": stats([case for case in cases if not case.get("faultInjection")]),
            "faultInjectionScenarios": stats([case for case in cases if case.get("faultInjection")]),
            "categories": {name: stats([c for c in cases if c["caseId"] == name]) for name in sorted({c["caseId"] for c in cases})}}


def save_report(root, report):
    report["summary"] = aggregate(report["cases"], mode=report["mode"],
        cohort_valid=report.get("cohort", {}).get("status") == "frozen" and report.get("status") == "completed")
    path = root / "report.json.tmp"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.replace(root / "report.json")


async def _dispatch(db, session, content, *, evidence=None):
    # Invoke the real route/dispatcher with an explicitly isolated DB. Collect
    # scheduling callbacks, then drive only this DB; never start a global worker.
    with observe_planner_calls() as calls:
        operation = asyncio.create_task(asyncio.to_thread(create_message, session.id, MessageCreateRequest(contentMd=content), BackgroundTasks(), db))
        try:
            return await asyncio.shield(operation)
        except asyncio.CancelledError:
            await asyncio.gather(operation, return_exceptions=True)
            raise
        finally:
            if evidence is not None:
                evidence["plannerCalls"] = calls


async def accept_source(root, scenario, index=0):
    cancelled = threading.Event()
    operation = asyncio.create_task(asyncio.to_thread(evaluate_scenario, root, scenario, index, cancelled=cancelled))
    try:
        return await asyncio.shield(operation)
    except asyncio.CancelledError:
        cancelled.set()
        await asyncio.gather(operation, return_exceptions=True)
        raise


async def run_phase(db, session, root, scenario, index, baseline_hashes, *, phase=None, test_execution=False, required_rule=None, progress=None,
                    require_native_qa=False, max_retries=1, coding_adapter="codex"):
    started = time.monotonic()
    if phase is None:
        phase = {}
    phase.update(index=index, promptHash=hashlib.sha256(scenario.prompts[index].encode()).hexdigest(), attempts=[], testExecution=test_execution)
    phase.update(requireNativeQa=require_native_qa, maxRetriesPerTask=max_retries, codingAdapter=coding_adapter)
    phase.update(requiredRuleId=required_rule.id if required_rule else None, requiredRuleHash=required_rule.content_hash if required_rule else None)
    before = hashes(root)
    try:
        message = await _dispatch(db, session, scenario.prompts[index], evidence=phase)
        phase["messageId"] = message.id
        tasks = db.exec(select(Task).where(Task.created_by_message_id == message.id).order_by(Task.priority, Task.created_at)).all()
        phase["tasks"] = [{"id": task.id, "dependsOn": json.loads(task.depends_on_task_ids), "plan": redact_process_evidence(json.loads(task.plan_json))} for task in tasks]
        plans = [json.loads(task.plan_json) for task in tasks]
        db.refresh(session)
        phase["requiredSnapshotId"] = session.memory_snapshot_id
        phase["plannerReceipts"] = [(p.get("groupAssignment", {}).get("plannerEvidence") or {}).get("memoryUsage") for p in plans]
        phase["nativePlanning"] = bool(plans) and all((p.get("groupAssignment", {}).get("plannerEvidence") or {}).get("plannerSource") == "real_llm" for p in plans)
        sources = {(p.get("groupAssignment", {}).get("plannerEvidence") or {}).get("plannerSource", "deterministic") for p in plans}
        phase["planningSource"] = next(iter(sources)) if len(sources) == 1 else "mixed_or_missing"
        if progress: progress()
        if not phase["nativePlanning"] and not (test_execution and phase["planningSource"] == "fake_test"):
            phase["error"] = "Configured native planning did not execute; no coding provider was started."
            return phase
        if scenario.fault_injection:
            queued = db.exec(select(TaskRun).join(Task, Task.id == TaskRun.task_id).where(Task.created_by_message_id == message.id, TaskRun.state == "queued")).first()
            if queued:
                metrics = json.loads(queued.metrics_json); metrics["forceFailure"] = True
                queued.metrics_json = json.dumps(metrics); db.add(queued); db.commit()
                phase["faultInjection"] = {"kind": "existing_codex_force_failure", "taskRunId": queued.id, "naturalProviderOutage": False}
        retries = {}
        for _ in range(max(12, len(tasks) * (max_retries + 1) + 1)):
            enqueue_ready_group_tasks(db, session_id=session.id)
            run = await RunWorker().run_once(db)
            if run is None:
                break
            db.expire_all(); run = db.get(TaskRun, run.id)
            phase["attempts"].append(collect_attempt(db, run, root))
            if progress: progress()
            if run.state != "completed":
                if run.state in {"failed", "interrupted"} and retries.get(run.task_id, 0) < max_retries:
                    retry_task_run(db, run.id)
                    retries[run.task_id] = retries.get(run.task_id, 0) + 1
                    phase.setdefault("retryDecisions", []).append({"failedRunId": run.id, "taskId": run.task_id,
                        "reason": "explicit_fault_injection" if scenario.fault_injection and len(phase["attempts"]) == 1 else "natural_execution_failure"})
                    continue
                break
        db.expire_all()
        phase["allTasksCompleted"] = bool(tasks) and all(db.get(Task, task.id).status == "completed" for task in tasks)
        phase["acceptance"] = await accept_source(root, scenario, index)
    except asyncio.CancelledError:
        phase["error"] = "scenario_timeout_or_cancel"
        raise
    except Exception as exc:
        db.rollback()
        phase["error"] = {"type": type(exc).__name__, "message": redact_process_evidence(str(exc))[:500]}
    finally:
        if phase.get("messageId"):
            db.expire_all()
            recorded = {attempt["taskRunId"] for attempt in phase["attempts"]}
            runs = db.exec(select(TaskRun).join(Task, Task.id == TaskRun.task_id).where(Task.created_by_message_id == phase["messageId"])).all()
            phase["attempts"].extend(collect_attempt(db, run, root) for run in runs if run.id not in recorded)
        after = hashes(root)
        phase["changedPaths"] = sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))
        phase["immutableInputs"] = all(baseline_hashes.get(path) == after.get(path) for path in set(baseline_hashes) | set(after) if not permitted(scenario, path))
        phase["sourceHashes"] = after
        phase["elapsedSeconds"] = round(time.monotonic() - started, 3)
        phase["failureGates"] = phase_gates(scenario, phase)
        phase["verdict"] = "failed" if phase["failureGates"] else "passed"
        if progress: progress()
    return phase


async def run_scenario(directory, scenario, *, prepare_only=False, adapter="codex", qa_adapter="claude_code", timeout=900,
                       test_execution=False, progress=None, max_retries=1):
    preparation_started = time.monotonic()
    scenario = bound_scenario(scenario, qa_adapter)
    root = prepare_source(directory, scenario)
    baseline_hashes = hashes(root)
    baseline = await accept_source(root, scenario)
    result = {"caseId": scenario.id, "scenario": asdict(scenario), "baseCommit": git(root, "rev-parse", "HEAD"),
              "inputHashes": baseline_hashes, "baseline": baseline, "baselineFailing": baseline["status"] == "failed",
              "phases": [], "faultInjection": scenario.fault_injection, "model": None, "tokenUsage": None, "cost": None}
    result.update(preparationElapsedSeconds=round(time.monotonic() - preparation_started, 3), qaAdapter=qa_adapter,
                  requireNativeQa=qa_adapter == "claude_code")
    result["verdict"] = "preparing" if prepare_only else "running"
    if progress: progress(result)
    if prepare_only:
        return {**result, "verdict": "prepared" if result["baselineFailing"] else "failed", "failureGates": [] if result["baselineFailing"] else ["baseline_not_failing"]}
    if not result["baselineFailing"]:
        return {**result, "verdict": "failed", "failureGates": ["baseline_not_failing"]}
    engine = create_engine(f"sqlite:///{(directory / 'workflow.sqlite3').as_posix()}", connect_args={"check_same_thread": False})
    prepare_database(engine)
    started = time.monotonic()
    try:
        with DbSession(engine) as db:
            seed_demo_data(db)
            workspace = Workspace(name=f"Workflow {scenario.id}", root_path="apps/demo", repo_url="local://workflow", default_branch="main")
            db.add(workspace); db.commit()
            for agent in db.exec(select(Agent).where(Agent.role.in_(["frontend", "backend"]))):
                agent.adapter_type = adapter; db.add(agent)
            qa = db.exec(select(Agent).where(Agent.role == "qa")).one()
            qa.adapter_type = qa_adapter
            qa.system_prompt = QA_PROMPT
            db.add(qa)
            db.commit()
            result["profiles"] = configure_profiles(db, workspace.id, adapter=adapter, qa_adapter=qa_adapter)
            rule = create_memory_item(db, MemoryItemInput(workspace_id=workspace.id, scope="project", memory_type="project_rule",
                source="user_explicit", title="Workflow fixture boundary", content_md=RULE, status="active", trust_level="user_confirmed"))
            session = Session(workspace_id=workspace.id, title=scenario.id, bound_branch="main", worktree_path=str(root))
            db.add(session); db.commit()
            result["sessionId"] = session.id
            result["ruleId"] = rule.id
            try:
                for index in range(len(scenario.prompts)):
                    print(f"{scenario.id}: natural-language phase {index + 1}", flush=True)
                    phase = {}
                    result["phases"].append(phase)
                    if progress: progress(result)
                    await asyncio.wait_for(run_phase(db, session, root, scenario, index, baseline_hashes,
                                                     phase=phase, test_execution=test_execution, required_rule=rule,
                                                     require_native_qa=qa_adapter == "claude_code", max_retries=max_retries, coding_adapter=adapter,
                                                     progress=(lambda: progress(result)) if progress else None), timeout=timeout)
                    if phase["verdict"] != "passed": break
            except asyncio.TimeoutError:
                result["error"] = "scenario_timeout"
            finally:
                for run in db.exec(select(TaskRun).join(Task, Task.id == TaskRun.task_id).where(Task.session_id == session.id)).all():
                    if run.state not in TERMINAL:
                        await interrupt_supervised_task_run(run.id)
                        db.refresh(run)
                        if run.state not in TERMINAL:
                            try:
                                interrupt_task_run(db, run.id)
                            except TaskRunLifecycleError:
                                db.refresh(run)
                                if run.state not in TERMINAL:
                                    raise
                # Preserve successful earlier phases at their original version.
                # Only refresh the interrupted phase after its owned queue is
                # actually terminal; a cutoff streaming state is not a live run.
                if result["phases"] and result["phases"][-1].get("error") == "scenario_timeout_or_cancel":
                    interrupted = result["phases"][-1]
                    for attempt in interrupted["attempts"]:
                        cutoff = attempt["state"]
                        db.expire_all()
                        attempt.update(collect_attempt(db, db.get(TaskRun, attempt["taskRunId"]), root))
                        attempt.update(stateAtCutoff=cutoff, stoppedBy="workflow_evaluation")
                    interrupted["failureGates"] = phase_gates(scenario, interrupted)
                    if progress: progress(result)
    except asyncio.CancelledError:
        result.update(verdict="interrupted", failureGates=["evaluation_interrupted"], elapsedSeconds=round(time.monotonic() - started, 3))
        if progress: progress(result)
        raise
    finally:
        engine.dispose()
    phases = result["phases"]
    gates = sorted({gate for phase in phases for gate in phase["failureGates"]})
    if len(phases) != len(scenario.prompts): gates.append("workflow_phases_incomplete")
    attempts = [attempt for phase in phases for attempt in phase["attempts"]]
    result.update(verdict="failed" if gates else "passed", failureGates=gates,
                  elapsedSeconds=round(time.monotonic() - started, 3), retryCount=sum(bool(a.get("retryOfRunId")) for a in attempts),
                  firstAttemptPassed=bool(phases) and not gates and not any(a["state"] != "completed" or a.get("retryOfRunId") for a in attempts))
    result["totalElapsedSeconds"] = round(time.monotonic() - preparation_started, 3)
    return result


async def run_benchmark(output, *, case_id=None, repetitions=1, prepare_only=False, adapter="codex", qa_adapter="claude_code", timeout=900,
                        test_execution=False, max_retries=1):
    scenarios = [bound_scenario(scenario, qa_adapter) for scenario in select_scenarios(case_id)]
    if (type(repetitions) is not int or not 1 <= repetitions <= 5 or adapter not in {"codex", "claude_code"} or not 60 <= timeout <= 1800
            or type(max_retries) is not int or not 0 <= max_retries <= 2
            or qa_adapter not in ({"claude_code", "scripted_mock"} if test_execution else {"claude_code"})):
        raise ValueError("Invalid bounded workflow evaluation options.")
    root = reserve_output(output)
    policy = source_policy()
    report = {"schemaVersion": SCHEMA, "recordedAt": datetime.now(timezone.utc).isoformat(),
              "mode": "prepare_only" if prepare_only else "test_double" if test_execution else "live", "status": "running",
              "developmentHead": git(repo_root(), "rev-parse", "HEAD"), "sourcePolicy": policy,
              "entrypoint": "production_message_route_and_dispatch_with_isolated_db", "httpUiTested": False,
              "livePreviewStarted": False, "deploymentExecuted": False, "summaryModelEvaluated": False,
              "cases": [{"caseId": case.id, "repetition": rep, "faultInjection": case.fault_injection, "verdict": "not_attempted"} for rep in range(1, repetitions + 1) for case in scenarios]}
    report["cohort"] = cohort(policy, development_head=report["developmentHead"], adapter=adapter, qa_adapter=qa_adapter,
                              scenarios=[asdict(case) for case in scenarios], repetitions=repetitions, max_retries=max_retries)
    save_report(root, report)
    for index, pending in enumerate(report["cases"]):
        if not policy_matches(policy):
            invalidate(report, reason="evaluation_policy_changed", index=index)
            report["status"] = "invalidated"
            save_report(root, report)
            break
        scenario = next(case for case in scenarios if case.id == pending["caseId"])
        directory = root / f"{scenario.id}-{pending['repetition']}"
        directory.mkdir()
        def progress(result):
            report["cases"][index] = {**pending, **result}
            save_report(root, report)
        try:
            result = await run_scenario(directory, scenario, prepare_only=prepare_only, adapter=adapter, qa_adapter=qa_adapter, timeout=timeout,
                                        test_execution=test_execution, progress=progress, max_retries=max_retries)
        except asyncio.CancelledError:
            report["status"] = "interrupted"
            save_report(root, report)
            raise
        except Exception as exc:
            result = {"caseId": scenario.id, "verdict": "harness_error", "failureGates": ["harness_error"], "errorType": type(exc).__name__}
        report["cases"][index] = {**pending, **result}
        if not policy_matches(policy):
            invalidate(report, reason="evaluation_policy_changed", index=index)
            report["status"] = "invalidated"
            save_report(root, report)
            break
        save_report(root, report)
        print(f"{scenario.id}: {result['verdict']}", flush=True)
    if report["status"] == "running":
        report["status"] = "completed"
    save_report(root, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", choices=[case.id for case in select_scenarios()])
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--adapter", choices=["codex", "claude_code"], default="codex")
    parser.add_argument("--max-retries", type=int, default=1, help="Explicit failed/interrupted retries per task, 0–2; never retry a completed model assessment")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    report = asyncio.run(run_benchmark(args.output, case_id=args.case, repetitions=args.repetitions,
                                      prepare_only=args.prepare_only, adapter=args.adapter, timeout=args.timeout, max_retries=args.max_retries))
    return 0 if all(c["verdict"] in {"passed", "prepared"} for c in report["cases"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
