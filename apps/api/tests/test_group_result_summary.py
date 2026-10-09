import asyncio
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session as DbSession, select

from test_group_auto_execution import runtime, group  # noqa: F401
from app.group_summaries import STATE_KEY, _finish, capture_group_evidence, execute_group_summary, prepare_group_summary, public_group_summary, reconcile_group_summaries
from app.group_summary_contracts import SUMMARY_SCHEMA, parse_group_summary
from app.main import app, get_db
from app.models import Agent, Artifact, Diff, Message, Review, Session, TaskRun, TaskRunEvent, utc_now
from app.planner_providers import PlannerProviderResult
from app.run_engine import execute_task_run_background
from app.task_runs import create_task_run, transition_task_run


def settled(db):
    tasks = group(db, execution="manual")
    for task in tasks:
        run = create_task_run(db, task.id)
        assert asyncio.run(execute_task_run_background(db, run.id, "scripted_mock"))
    return tasks[0].created_by_message_id


def plan_state(db, gid, mutate):
    plan = db.exec(select(Message).where(Message.parent_message_id == gid, Message.message_kind == "plan")).one()
    value = json.loads(plan.context_json)
    mutate(value[STATE_KEY])
    plan.context_json = json.dumps(value); db.add(plan); db.commit()
    return plan


def native(db, gid, monkeypatch, *, mutate=None, callback=None, failed=False):
    calls = []
    plan_state(db, gid, lambda state: state["policy"].update({"source": "real_llm", "providerArgs": {"provider_id": "claude-cli-planner"}, "prompt": "SUMMARY_FROZEN_MARKER", "promptSha256": hashlib.sha256(b"SUMMARY_FROZEN_MARKER").hexdigest()}))
    class Provider:
        def create_plan(self, payload):
            calls.append(payload)
            evidence = payload["groupCompletionEvidence"]
            value = {"schemaVersion": SUMMARY_SCHEMA, **{key: evidence[key] for key in ["groupId", "inputFingerprint", "outcome"]}, "summary": "SUMMARY_FROZEN_MARKER: actual evidence only", "nextSteps": [], "validation": "not_run"}
            if mutate: mutate(value)
            if callback: callback()
            return PlannerProviderResult("claude-cli-planner", "controlled_test", "real_llm", "failed" if failed else "succeeded", raw_output=json.dumps(value))
    monkeypatch.setattr("app.group_summaries.resolve_planner_provider", lambda *args, **kwargs: Provider())
    return calls


def summaries(db):
    db.expire_all()
    return db.exec(select(Message).where(Message.message_kind == "group_summary").order_by(Message.created_at, Message.id)).all()


def test_deterministic_receipt_is_bound_to_own_run_and_readonly_artifacts(runtime):
    db, _ = runtime; gid = settled(db)
    before = db.exec(select(Session)).one().updated_at
    job = prepare_group_summary(db, gid)
    asyncio.run(execute_group_summary(db.get_bind(), job))
    message = summaries(db)[0]; receipt = public_group_summary(db, message)
    assert receipt["state"] == "completed" and receipt["current"]
    assert receipt["source"] == "deterministic" and receipt["interpretation"] is None
    assert receipt["evidence"]["outcome"] == "completed" and receipt["validation"] == "not_run"
    rows = receipt["evidence"]["tasks"]
    assert rows[0]["adapterType"] == "scripted_mock"
    assert rows[1]["reviews"][0]["source"] == "scripted_advisory"
    assert rows[1]["reviews"][0]["validation"] == "not_run"
    assert any(a.get("readOnlySnapshot") for a in rows[1]["artifacts"])
    assert prepare_group_summary(db, gid) is None
    assert db.exec(select(Session)).one().updated_at == before
    events = db.exec(select(TaskRunEvent).where(TaskRunEvent.event_type == "group.summary.completed")).all()
    assert len(events) == 1 and json.loads(events[0].payload_json)["messageId"] == message.id


def test_native_call_uses_frozen_prompt_no_tools_and_actual_receipt(runtime, monkeypatch):
    db, _ = runtime; gid = settled(db); calls = native(db, gid, monkeypatch)
    job = prepare_group_summary(db, gid)
    agent = db.get(Agent, job.policy["agentId"]); agent.system_prompt = "EDITED_LATER"; db.add(agent); db.commit()
    asyncio.run(execute_group_summary(db.get_bind(), job))
    receipt = public_group_summary(db, summaries(db)[0])
    assert len(calls) == 1 and calls[0]["agentSystemPrompt"] == "SUMMARY_FROZEN_MARKER"
    assert calls[0]["agentToolPolicy"] == "planner_no_tools"
    assert receipt["state"] == "completed" and receipt["interpretation"]["summary"].startswith("SUMMARY_FROZEN_MARKER")
    assert receipt["providerEvidence"]["outputSha256"] and receipt["agentInstruction"]["sha256"] == job.policy["promptSha256"]


@pytest.mark.parametrize("field,value", [("groupId", "other"), ("inputFingerprint", "other"), ("outcome", "failed"), ("validation", "passed"), ("summary", " "), ("nextSteps", [" "]), ("extra", True)])
def test_invalid_native_binding_visible_and_requires_explicit_retry(runtime, monkeypatch, field, value):
    db, _ = runtime; gid = settled(db)
    calls = native(db, gid, monkeypatch, mutate=lambda result: result.update({field: value}))
    job = prepare_group_summary(db, gid); asyncio.run(execute_group_summary(db.get_bind(), job))
    receipt = public_group_summary(db, summaries(db)[0])
    assert receipt["state"] == "failed" and receipt["errorCode"] == "GROUP_SUMMARY_OUTPUT_INVALID"
    assert prepare_group_summary(db, gid) is None and len(calls) == 1
    assert all(run.state == "completed" for run in db.exec(select(TaskRun)).all())


@pytest.mark.parametrize("output", ['{"groupId":"a","groupId":"b"}', 'prefix ```json\n{}\n```', '[]', '{}', 'x' * 33000], ids=["duplicate", "outside_prose", "array", "empty", "oversized"])
def test_untrusted_summary_shape_rejected(output):
    with pytest.raises((ValueError, TypeError)):
        parse_group_summary(output, {"groupId": "a", "inputFingerprint": "hash", "outcome": "completed"})


def test_provider_failure_retry_preserves_history_and_unique_current(runtime, monkeypatch):
    db, _ = runtime; gid = settled(db); native(db, gid, monkeypatch, failed=True)
    first = prepare_group_summary(db, gid); asyncio.run(execute_group_summary(db.get_bind(), first))
    assert public_group_summary(db, summaries(db)[0])["errorCode"] == "GROUP_SUMMARY_PROVIDER_FAILED"
    native(db, gid, monkeypatch)
    second = prepare_group_summary(db, gid, retry=True); asyncio.run(execute_group_summary(db.get_bind(), second))
    values = [public_group_summary(db, m) for m in summaries(db)]
    assert [v["current"] for v in values] == [False, True]
    assert [v["state"] for v in values] == ["failed", "completed"]


def test_active_group_waits_and_failure_is_actual_not_complete(runtime):
    db, _ = runtime; tasks = group(db)
    assert capture_group_evidence(db, tasks[0].created_by_message_id) is None
    run = create_task_run(db, tasks[0].id)
    assert prepare_group_summary(db, tasks[0].created_by_message_id) is None
    transition_task_run(db, run.id, "failed", error_code="CONTROLLED", error_message="Failure")
    evidence = capture_group_evidence(db, tasks[0].created_by_message_id)
    assert evidence["outcome"] == "failed" and evidence["tasks"][1]["runId"] is None


def test_missing_artifact_does_not_count_as_completed_and_failed_verdict_is_separate(runtime):
    db, _ = runtime; gid = settled(db)
    reviews = db.exec(select(Review)).all()
    for review in reviews:
        review.status = "failed"; db.add(review)
    db.commit()
    assert capture_group_evidence(db, gid)["outcome"] == "completed"
    artifact = db.get(Artifact, review.artifact_id); artifact.status = "invalid"; db.add(artifact); db.commit()
    evidence = capture_group_evidence(db, gid)
    assert evidence["outcome"] == "awaiting_action" and evidence["tasks"][1]["missingEvidence"] == ["review"]


def test_concurrent_claim_and_duplicate_completion_are_idempotent(runtime):
    db, _ = runtime; gid = settled(db); bind = db.get_bind(); db.commit()
    def prepare(_):
        with DbSession(bind) as worker: return prepare_group_summary(worker, gid)
    with ThreadPoolExecutor(max_workers=2) as pool: jobs = list(pool.map(prepare, range(2)))
    job = next(job for job in jobs if job)
    assert sum(bool(job) for job in jobs) == 1
    _finish(bind, job, None, {}, None); _finish(bind, job, None, {}, None)
    assert len(summaries(db)) == 1
    assert len(db.exec(select(TaskRunEvent).where(TaskRunEvent.event_type == "group.summary.completed")).all()) == 1


@pytest.mark.parametrize("change", ["patch", "latest_attempt", "policy", "expired"])
def test_mutated_evidence_or_expired_lease_cannot_publish_success(runtime, change):
    db, _ = runtime; gid = settled(db); job = prepare_group_summary(db, gid)
    if change == "patch":
        diff = db.exec(select(Diff)).first(); diff.patch_text += "\nChanged"; db.add(diff); db.commit()
    elif change == "latest_attempt":
        previous = db.get(TaskRun, job.evidence["tasks"][0]["runId"])
        db.add(TaskRun(task_id=previous.task_id, agent_id=previous.agent_id, worktree_path=previous.worktree_path, base_ref=previous.base_ref, head_ref=previous.head_ref, state="failed")); db.commit()
    elif change == "policy":
        plan_state(db, gid, lambda state: state["policy"].update({"displayName": "Changed"}))
    else:
        plan_state(db, gid, lambda state: state.update({"leaseUntil": (utc_now() - timedelta(seconds=1)).isoformat()}))
    _finish(db.get_bind(), job, None, {}, None)
    receipt = public_group_summary(db, summaries(db)[0])
    assert receipt["state"] == "superseded" and not receipt["current"]


def test_expired_claim_recovery_old_owner_cannot_overwrite_successor(runtime):
    db, _ = runtime; gid = settled(db); first = prepare_group_summary(db, gid)
    plan_state(db, gid, lambda state: state.update({"leaseUntil": (utc_now() - timedelta(seconds=1)).isoformat()}))
    with DbSession(db.get_bind()) as restarted: second = prepare_group_summary(restarted, gid)
    _finish(db.get_bind(), second, None, {}, None); _finish(db.get_bind(), first, None, {}, None)
    values = [public_group_summary(db, m) for m in summaries(db)]
    assert [v["state"] for v in values] == ["superseded", "completed"]
    assert [v["current"] for v in values] == [False, True]


def test_coordinator_revocation_during_native_call_rejects_result(runtime, monkeypatch):
    db, _ = runtime; gid = settled(db)
    def revoke():
        with DbSession(db.get_bind()) as worker:
            agent = worker.exec(select(Agent).where(Agent.role == "orchestrator")).one()
            agent.enabled = False; worker.add(agent); worker.commit()
    native(db, gid, monkeypatch, callback=revoke)
    job = prepare_group_summary(db, gid); asyncio.run(execute_group_summary(db.get_bind(), job))
    assert public_group_summary(db, summaries(db)[0])["errorCode"] == "GROUP_SUMMARY_SELECTION_REVOKED"


def test_read_endpoint_is_pure_and_retry_is_session_bound(runtime, monkeypatch):
    db, _ = runtime; gid = settled(db); calls = native(db, gid, monkeypatch, failed=True)
    job = prepare_group_summary(db, gid); asyncio.run(execute_group_summary(db.get_bind(), job))
    sid = db.exec(select(Session)).one().id; before = [m.context_json for m in summaries(db)]
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        response = client.get(f"/sessions/{sid}/messages")
        assert response.status_code == 200
        assert next(m for m in response.json() if m["messageKind"] == "group_summary")["groupSummary"]["state"] == "failed"
        assert "_groupSummary" not in response.text and "providerArgs" not in response.text
        assert [m.context_json for m in summaries(db)] == before and len(calls) == 1
        assert client.post(f"/sessions/other/groups/{gid}/summary/retry").status_code == 404
        native(db, gid, monkeypatch)
        assert client.post(f"/sessions/{sid}/groups/{gid}/summary/retry").status_code == 201
        assert public_group_summary(db, summaries(db)[-1])["state"] == "completed"
        assert client.post(f"/sessions/{sid}/groups/{gid}/summary/retry").status_code == 409
    finally: app.dependency_overrides.clear()


def test_historical_group_is_not_implicitly_summarized(runtime):
    db, _ = runtime; gid = settled(db)
    message = plan_state(db, gid, lambda _: None); message.context_json = "{}"; db.add(message); db.commit()
    asyncio.run(reconcile_group_summaries(db.get_bind()))
    assert summaries(db) == []


@pytest.mark.parametrize("change", ["status", "provider_id", "adapter_type", "supported_targets_json"])
def test_custom_coordinator_permission_or_identity_revoked(runtime, monkeypatch, change):
    from test_group_planning import custom_planner
    db, _ = runtime; gid = settled(db); profile = custom_planner(db)
    native(db, gid, monkeypatch)
    plan_state(db, gid, lambda state: state["policy"].update({"selection": {"id": profile.id, "providerId": profile.provider_id, "adapterType": profile.adapter_type}}))
    job = prepare_group_summary(db, gid)
    setattr(profile, change, {"status": "disabled", "provider_id": "openai-api-planner", "adapter_type": "other", "supported_targets_json": "[]"}[change])
    db.add(profile); db.commit()
    asyncio.run(execute_group_summary(db.get_bind(), job))
    assert public_group_summary(db, summaries(db)[0])["errorCode"] == "GROUP_SUMMARY_SELECTION_REVOKED"


def test_freezes_resolved_api_settings_and_uses_summary_contract_all_transports():
    from app.config import Settings
    from app.group_summaries import frozen_summary_policy
    from app.planner_providers import OpenAICompatibleChatPlannerProvider, ClaudeCliPlannerProvider, resolve_planner_provider, _openai_responses_payload, _openai_compatible_chat_payload, _anthropic_messages_payload
    provider = OpenAICompatibleChatPlannerProvider(provider_id="deepseek-api-planner", api_key_env="DEEPSEEK_API_KEY", model="model", base_url="https://api.deepseek.com", provider_preset_id="deepseek_api", timeout_sec=41)
    policy = frozen_summary_policy(provider, None, {"agentSystemPrompt": "marker"}, provider_id=provider.provider_id)
    restored = resolve_planner_provider(Settings(), **policy["providerArgs"])
    assert restored._model == "model" and restored._timeout_sec == 41 and restored._provider_preset_id == "deepseek_api"
    evidence = {"groupId": "gid", "inputFingerprint": "fp", "outcome": "completed"}
    payload = {"agentSystemPrompt": "marker", "agentToolPolicy": "planner_no_tools", "groupCompletionEvidence": evidence}
    command = ClaudeCliPlannerProvider(claude_binary="claude.exe")._build_command(payload)
    assert command[command.index("--tools") + 1] == "" and "--safe-mode" in command
    assert "selected group coordinator" in command[-1] and "marker" in command[-1]
    for builder in [_openai_responses_payload, _openai_compatible_chat_payload, _anthropic_messages_payload]:
        value = builder(model="model", planner_input=payload)
        text = json.dumps(value)
        assert SUMMARY_SCHEMA in text and "selected group coordinator" in text and "marker" in text
