"""Durable, fenced coordinator interpretations of bounded group evidence."""

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import update
from sqlmodel import Session as DbSession, select

from app.agent_instructions import capture_agent_instruction
from app.config import get_settings
from app.custom_agents import require_custom_agent
from app.events import publish_task_run_event, stage_task_run_event
from app.group_summary_contracts import SUMMARY_SCHEMA, parse_group_summary
from app.models import Agent, Artifact, ArtifactVersion, Diff, Message, Review, Session, Task, TaskRun, utc_now
from app.canonical_context import filter_protected_values
from app.planner_providers import resolve_planner_provider
from app.process_environment import redact_process_evidence
from app.task_runs import adapter_type_for_run

STATE_KEY = "_groupSummary"
ACTIVE = {"created", "queued", "streaming", "applying_changes", "collecting_diff", "starting_preview"}


def _json(value: str) -> dict:
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def frozen_summary_policy(provider, config, planner_input: dict, *, provider_id: str) -> dict:
    args = {key: getattr(config, key, None) for key in ("provider_preset_id", "model", "base_url", "api_key_env", "timeout_seconds")}
    args["provider_id"] = provider_id
    for field, attribute in [("provider_preset_id", "_provider_preset_id"), ("model", "_model"), ("base_url", "_base_url"), ("api_key_env", "_api_key_env"), ("timeout_seconds", "_timeout_sec")]:
        args[field] = args[field] or getattr(provider, attribute, None)
    prompt = planner_input.get("agentSystemPrompt") or ""
    return {"providerArgs": args, "source": provider.planner_source,
            "prompt": prompt, "promptSha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "selection": planner_input.get("agentProfileSelection"), "toolPolicy": "planner_no_tools"}


def deterministic_summary_policy(db: DbSession, session: Session, coordinator: Agent) -> dict:
    binding = capture_agent_instruction(db, workspace_id=session.workspace_id, agent=coordinator, role="planner")
    return {"providerArgs": {"provider_id": "disabled"}, "source": "disabled", "prompt": binding["text"],
            "promptSha256": binding["sha256"], "selection": None, "toolPolicy": "planner_no_tools"}


def _group_plan(db: DbSession, group_id: str) -> tuple[Message, dict] | None:
    tasks = db.exec(select(Task).where(Task.created_by_message_id == group_id).order_by(Task.priority, Task.created_at, Task.id)).all()
    if not tasks or len(tasks) > 6:
        return None
    group = _json(tasks[0].plan_json).get("groupAssignment", {})
    plan_message = db.get(Message, group.get("coordinatorMessageId"))
    if plan_message is None or plan_message.parent_message_id != group_id or plan_message.session_id != tasks[0].session_id:
        return None
    state = _json(plan_message.context_json).get(STATE_KEY)
    if not isinstance(state, dict) or state.get("schemaVersion") != SUMMARY_SCHEMA:
        return None
    if state.get("taskIds") != [task.id for task in tasks] or any(
        t.session_id != plan_message.session_id or _json(t.plan_json).get("planner") != "explicit_group_v1"
        or _json(t.plan_json).get("groupAssignment", {}).get("coordinatorMessageId") != plan_message.id for t in tasks
    ):
        return None
    return plan_message, state


def capture_group_evidence(db: DbSession, group_id: str) -> dict | None:
    bound = _group_plan(db, group_id)
    if bound is None:
        return None
    plan_message, state = bound
    rows = []
    has_attempt = False
    missing = False
    for task_id in state["taskIds"]:
        task = db.get(Task, task_id)
        plan = _json(task.plan_json)
        runs = db.exec(select(TaskRun).where(TaskRun.task_id == task.id).order_by(TaskRun.created_at, TaskRun.id)).all()
        run = runs[-1] if runs else None
        if run and run.state in ACTIVE:
            return None
        if run:
            has_attempt = True
        agent = db.get(Agent, task.assigned_agent_id)
        row = {"taskId": task.id, "title": task.title[:300], "role": plan.get("assignedRole"),
               "displayName": plan.get("agentProfileDisplayName") or (agent.name if agent else "Unavailable Agent"),
               "targetId": plan.get("targetId"), "runId": run.id if run else None,
               "state": run.state if run else "not_started", "attemptCount": len(runs),
               "adapterType": adapter_type_for_run(db, run) if run else None,
               "errorCode": run.error_code if run else plan.get("groupExecutionError", {}).get("code"),
               "artifacts": [], "reviews": [], "missingEvidence": []}
        if run:
            for artifact in db.exec(select(Artifact).where(Artifact.task_run_id == run.id).order_by(Artifact.created_at, Artifact.id)).all():
                if artifact.artifact_type not in {"diff", "review"}:
                    continue
                version = db.exec(select(ArtifactVersion).where(ArtifactVersion.artifact_id == artifact.id).order_by(ArtifactVersion.version.desc())).first()
                fact = {"artifactId": artifact.id, "type": artifact.artifact_type, "status": artifact.status,
                        "version": version.version if version else artifact.version,
                        "contentHash": version.content_hash if version else _digest(_json(artifact.meta_json)),
                        "editorSource": version.editor_source if version else "system"}
                if artifact.artifact_type == "diff":
                    diff = db.exec(select(Diff).where(Diff.artifact_id == artifact.id)).first()
                    if not diff or artifact.status != "ready":
                        continue
                    fact.update({"changedFiles": json.loads(diff.changed_files_json)[:128],
                                 "patchSha256": hashlib.sha256(diff.patch_text.encode("utf-8")).hexdigest(),
                                 "readOnlySnapshot": row["role"] in {"qa", "review"}})
                else:
                    review = db.exec(select(Review).where(Review.artifact_id == artifact.id)).first()
                    reviewed = db.get(Artifact, review.reviewed_diff_artifact_id) if review else None
                    if not review or artifact.status not in {"passed", "warning", "failed"} or not reviewed or reviewed.task_run_id != run.id or reviewed.artifact_type != "diff" or reviewed.status != "ready":
                        continue
                    meta = _json(artifact.meta_json)
                    row["reviews"].append({"artifactId": artifact.id, "reviewedDiffArtifactId": reviewed.id,
                                           "status": review.status, "riskLevel": review.risk_level,
                                           "adapterType": review.adapter_type,
                                           "source": "user_edited" if version and version.editor_source == "user" else "native_model" if meta.get("nativeReceipt") else "scripted_advisory",
                                           "summary": review.summary[:1200], "validation": "not_run"})
                row["artifacts"].append(fact)
            if run.state == "completed":
                types = {a["type"] for a in row["artifacts"]}
                expected = (set(plan.get("expectedArtifactTypes", [])) & {"diff", "review"}) | {"review" if row["role"] in {"qa", "review"} else "diff"}
                row["missingEvidence"] = sorted(expected - types)
                missing = missing or bool(row["missingEvidence"])
        rows.append(row)
    errors = any(row["errorCode"] for row in rows)
    if not has_attempt and not errors:
        return None
    complete = all(row["state"] == "completed" for row in rows) and not missing
    failures = any(row["state"] in {"failed", "interrupted"} or row["errorCode"] for row in rows)
    # Automatic ready/lock/dependency waits are still execution, not a settled result.
    if not complete and not failures and not missing and state.get("execution") == "automatic" and not any(row["state"] == "waiting_approval" for row in rows):
        return None
    outcome = "completed" if complete else "partial_failure" if failures and any(row["state"] == "completed" for row in rows) else "failed" if failures else "awaiting_action"
    evidence = filter_protected_values(redact_process_evidence({"schemaVersion": SUMMARY_SCHEMA, "groupId": group_id,
        "sessionId": plan_message.session_id, "originalRequest": db.get(Message, group_id).content_md[:3000],
        "outcome": outcome, "tasks": rows, "validation": "not_run",
        "promptSha256": state["policy"]["promptSha256"], "policyFingerprint": _digest(state["policy"])}))
    if len(json.dumps(evidence, ensure_ascii=False)) > 48 * 1024:
        raise ValueError("Group summary evidence exceeds its bounded budget.")
    evidence["inputFingerprint"] = _digest(evidence)
    return evidence


def _require_coordinator(db: DbSession, policy: dict, evidence: dict) -> None:
    coordinator = db.get(Agent, policy["agentId"])
    if coordinator is None or not coordinator.enabled or coordinator.role != "orchestrator":
        raise ValueError("Coordinator unavailable.")
    if policy["toolPolicy"] != "planner_no_tools" or hashlib.sha256(policy["prompt"].encode("utf-8")).hexdigest() != policy["promptSha256"]:
        raise ValueError("Coordinator binding invalid.")
    selection = policy.get("selection")
    if selection:
        profile = require_custom_agent(db, policy["workspaceId"], selection["id"])
        if profile.role != "orchestrator" or profile.provider_id != selection["providerId"] or profile.adapter_type != selection["adapterType"] or profile.tool_policy != "planner_no_tools":
            raise ValueError("Coordinator selection revoked.")
        if not {t["targetId"] for t in evidence["tasks"]}.issubset(json.loads(profile.supported_targets_json)):
            raise ValueError("Coordinator scope narrowed.")


@dataclass(frozen=True)
class SummaryJob:
    group_id: str
    message_id: str
    owner: str
    evidence: dict
    policy: dict


def _publish(db: DbSession, message: Message, evidence: dict, event_type: str) -> None:
    db.add(message)
    run_id = next((r["runId"] for r in reversed(evidence["tasks"]) if r["runId"]), None)
    event = stage_task_run_event(db, run_id, event_type, json.dumps({"groupId": evidence["groupId"], "messageId": message.id, "inputFingerprint": evidence["inputFingerprint"]}, separators=(",", ":"))) if run_id else None
    db.commit()
    if event:
        publish_task_run_event(db, event)


def prepare_group_summary(db: DbSession, group_id: str, *, retry: bool = False, regeneration: dict | None = None) -> SummaryJob | None:
    bound = _group_plan(db, group_id)
    if not bound:
        return None
    plan_message, _ = bound
    db.execute(update(Session).where(Session.id == plan_message.session_id).values(updated_at=Session.updated_at))
    db.expire_all()
    bound = _group_plan(db, group_id)
    if not bound:
        db.rollback(); return None
    plan_message, state = bound
    evidence = capture_group_evidence(db, group_id)
    if not evidence:
        db.rollback(); return None
    now = utc_now()
    same = state.get("fingerprint") == evidence["inputFingerprint"]
    if regeneration and (not same or state.get("status") != "completed" or state.get("messageId") != regeneration.get("sourceMessageId")):
        db.rollback(); return None
    if same and ((state.get("status") == "completed" and not regeneration) or (state.get("status") == "failed" and not retry)):
        db.rollback(); return None
    if same and state.get("status") == "calling" and state.get("leaseUntil", "") > now.isoformat():
        db.rollback(); return None
    owner = str(uuid4())
    policy = state["policy"]
    public = {"groupId": group_id, "state": "calling", "current": True, "source": "deterministic" if policy["source"] == "disabled" else "native_model",
              "coordinatorName": policy["displayName"], "evidence": evidence, "validation": "not_run"}
    message = Message(session_id=plan_message.session_id, sender_type="orchestrator", sender_id=policy["agentId"],
                      message_kind="group_summary", parent_message_id=group_id, stream_state="streaming",
                      content_md="正在根据任务运行和制品证据汇总结果…", context_json=json.dumps({"groupSummary": public}, ensure_ascii=False))
    if regeneration:
        message.id = regeneration["operationId"]
        message.regeneration_json = json.dumps(regeneration, separators=(",", ":"))
    timeout = policy["providerArgs"].get("timeout_seconds") or 60
    state.update({"fingerprint": evidence["inputFingerprint"], "status": "calling", "owner": owner, "messageId": message.id,
                  "leaseUntil": (now + timedelta(seconds=timeout + 30)).isoformat()})
    context = _json(plan_message.context_json); context[STATE_KEY] = state
    plan_message.context_json = json.dumps(context, ensure_ascii=False); db.add(plan_message)
    session = db.get(Session, plan_message.session_id)
    session.last_message_at = now; db.add(session)
    _publish(db, message, evidence, "group.summary.started")
    return SummaryJob(group_id, message.id, owner, evidence, policy)


def _interpret(bind, job: SummaryJob) -> tuple[dict | None, dict, str | None]:
    with DbSession(bind) as db:
        try:
            _require_coordinator(db, job.policy, job.evidence)
        except Exception:
            return None, {}, "GROUP_SUMMARY_SELECTION_REVOKED"
    if job.policy["source"] == "disabled":
        return None, {"plannerSource": "deterministic", "status": "not_configured"}, None
    try:
        provider = resolve_planner_provider(get_settings(), **job.policy["providerArgs"])
        result = provider.create_plan({"agentSystemPrompt": job.policy["prompt"], "agentToolPolicy": "planner_no_tools", "groupCompletionEvidence": job.evidence})
        metadata = {k: v for k, v in result.to_metadata().items() if k in {"providerId", "providerType", "plannerSource", "status", "durationMs", "model", "protocol", "providerPresetId", "errorCode"}}
        metadata = redact_process_evidence(metadata)
        if result.status != "succeeded" or result.planner_source == "disabled":
            return None, metadata, "GROUP_SUMMARY_PROVIDER_FAILED"
        metadata["outputSha256"] = hashlib.sha256(result.raw_output.encode("utf-8")).hexdigest()
        try:
            parsed = parse_group_summary(result.raw_output, job.evidence)
        except Exception:
            return None, metadata, "GROUP_SUMMARY_OUTPUT_INVALID"
        return filter_protected_values(redact_process_evidence(parsed)), metadata, None
    except Exception:
        return None, {}, "GROUP_SUMMARY_PROVIDER_FAILED"


def _finish(bind, job: SummaryJob, result: dict | None, metadata: dict, error: str | None) -> None:
    with DbSession(bind) as db:
        bound = _group_plan(db, job.group_id)
        if not bound:
            return
        plan_message, _ = bound
        db.execute(update(Session).where(Session.id == plan_message.session_id).values(updated_at=Session.updated_at))
        db.expire_all()
        bound = _group_plan(db, job.group_id)
        if not bound:
            db.rollback()
            return
        plan_message, state = bound
        current = capture_group_evidence(db, job.group_id)
        message = db.get(Message, job.message_id)
        if not message or _json(message.context_json).get("groupSummary", {}).get("state") != "calling":
            db.rollback()
            return
        public = _json(message.context_json)["groupSummary"]
        public["providerEvidence"] = metadata
        public["agentInstruction"] = {"sha256": job.policy["promptSha256"], "profileId": (job.policy.get("selection") or {}).get("id"), "characters": len(job.policy["prompt"])}
        owned = state.get("owner") == job.owner and state.get("messageId") == job.message_id and state.get("status") == "calling"
        fresh = current and current["inputFingerprint"] == job.evidence["inputFingerprint"] and state.get("leaseUntil", "") > utc_now().isoformat() and state["policy"] == job.policy
        if not owned or not fresh:
            public.update({"state": "superseded", "current": False})
            message.content_md = "本次汇总输入已过期；请查看最新运行或后续汇总。"
            message.stream_state = "complete"
            message.context_json = json.dumps({"groupSummary": public}, ensure_ascii=False)
            if owned:
                state.update({"status": "superseded", "leaseUntil": ""})
                context = _json(plan_message.context_json); context[STATE_KEY] = state
                plan_message.context_json = json.dumps(context, ensure_ascii=False); db.add(plan_message)
            _publish(db, message, job.evidence, "group.summary.superseded")
            return
        try:
            _require_coordinator(db, job.policy, job.evidence)
        except Exception:
            error = "GROUP_SUMMARY_SELECTION_REVOKED"
        public.update({"state": "failed" if error else "completed", "errorCode": error, "interpretation": result if not error else None})
        label = {"completed": "任务组执行已完成", "partial_failure": "任务组部分失败", "failed": "任务组未完成", "awaiting_action": "任务组等待继续"}[job.evidence["outcome"]]
        message.content_md = label + ("。模型汇总失败，可重试；任务运行结果未改变。" if error else "。" + (result["summary"] if result else "未配置原生协调模型，以下为确定性执行记录。"))
        message.stream_state = "failed" if error else "complete"
        message.context_json = json.dumps({"groupSummary": public}, ensure_ascii=False)
        state.update({"status": public["state"], "leaseUntil": ""})
        context = _json(plan_message.context_json); context[STATE_KEY] = state
        plan_message.context_json = json.dumps(context, ensure_ascii=False); db.add(plan_message)
        _publish(db, message, job.evidence, "group.summary.failed" if error else "group.summary.completed")


async def execute_group_summary(bind, job: SummaryJob) -> None:
    from app.run_engine import _run_sync_execution_step

    try:
        result, metadata, error = await _run_sync_execution_step(lambda: _interpret(bind, job))
    except asyncio.CancelledError:
        _finish(bind, job, None, {}, "GROUP_SUMMARY_INTERRUPTED")
        raise
    await _run_sync_execution_step(lambda: _finish(bind, job, result, metadata, error))


async def reconcile_group_summaries(bind) -> None:
    from app.run_engine import _run_sync_execution_step

    with DbSession(bind) as db:
        group_ids = [m.parent_message_id for m in db.exec(select(Message).where(Message.message_kind == "plan")).all() if STATE_KEY in _json(m.context_json)]
    for group_id in group_ids:
        def prepare():
            with DbSession(bind) as db:
                return prepare_group_summary(db, group_id)
        job = await _run_sync_execution_step(prepare)
        if job:
            await execute_group_summary(bind, job)


def public_group_summary(db: DbSession, message: Message) -> dict | None:
    context = _json(message.context_json)
    if STATE_KEY in context:
        state = context[STATE_KEY]
        evidence = capture_group_evidence(db, message.parent_message_id)
        settled = evidence and state.get("fingerprint") == evidence["inputFingerprint"] and state.get("status") in {"completed", "failed"}
        waiting_manual = not evidence and state.get("execution") == "manual" and state.get("status") == "waiting"
        return {"groupId": message.parent_message_id, "isPlan": True, "state": "ready" if settled else "waiting_manual_start" if waiting_manual else "pending"}
    summary = context.get("groupSummary")
    if not isinstance(summary, dict):
        return None
    bound = _group_plan(db, summary.get("groupId"))
    evidence = capture_group_evidence(db, summary["groupId"]) if bound else None
    summary["current"] = bool(summary.get("state") != "superseded" and bound and bound[1].get("messageId") == message.id and evidence and evidence["inputFingerprint"] == summary["evidence"]["inputFingerprint"])
    return summary
