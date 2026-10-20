"""Real persisted history must not turn streamed telemetry into Planner input."""
import json

from sqlmodel import select

from app.llm_planner import build_llm_planner_input
from app.mission_trace import build_session_mission_trace
from app.models import Agent, Artifact, Task, TaskRun, TaskRunEvent
from app.planner_providers import ClaudeCliPlannerProvider
from test_llm_planner import db, _message


def _run(db, message, *, state="completed", title="Previous change", plan=None):
    agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
    task = Task(session_id=message.session_id, title=title, intent_type="frontend_change",
                status=state, assigned_agent_id=agent.id, plan_json=json.dumps(plan or {}))
    db.add(task)
    db.flush([task])
    run = TaskRun(task_id=task.id, agent_id=agent.id, state=state,
                  worktree_path=".worktrees/llm-planning-session",
                  error_code="CHECK_FAILED" if state == "failed" else None,
                  error_message="Type checking failed" if state == "failed" else None)
    db.add(run)
    db.flush([run])
    return task, run


def test_streamed_history_does_not_overflow_followup_or_destroy_full_trace(db):
    message = _message(db, "Keep the existing page and add a restart button")
    task, run = _run(db, message)
    raw = "stream-payload-must-stay-in-ui-" * 100
    for index in range(200):
        db.add(TaskRunEvent(task_run_id=run.id, event_type="message.delta", sequence=index + 1,
                            payload_json=json.dumps({"text": raw})))
    db.commit()

    payload = build_llm_planner_input(db, message)
    ClaudeCliPlannerProvider()._build_command(payload)
    trace = payload["canonicalSharedContext"]["fields"]["missionTrace"]["value"]
    assert payload.context_budget["status"] == "within_limit"
    assert trace["selection"]["events"] == {"total": 200, "included": 0, "omitted": 200}
    assert trace["tasks"][0]["id"] == task.id
    assert raw not in json.dumps(payload)
    full_trace = build_session_mission_trace(db, message.session_id)
    assert len(full_trace.events) == 200
    assert all(event["payload"]["text"] == raw for event in full_trace.events)
    receipt = next(source for source in payload.context_budget["sources"] if source["source"] == "missionTrace")
    assert receipt["omissionReasons"]["historical_event_payloads"] == 200
    assert raw not in json.dumps(receipt)


def test_planner_summary_bounds_nested_telemetry_and_preserves_failure_identity(db):
    message = _message(db, "Fix the failed type check")
    huge = "historical-internal-telemetry-" * 15000
    task, run = _run(db, message, state="failed", plan={
        "plannerEvidence": {"providerId": "native-planner", "status": "succeeded", "raw": huge},
        "contextHandoff": {"raw": huge}})
    artifact = Artifact(task_run_id=run.id, artifact_type="review", title="Review", status="failed",
                        meta_json=json.dumps({"providerEvidence": {"raw": huge}, "status": "failed"}))
    db.add(artifact)
    db.commit()
    payload = build_llm_planner_input(db, message)
    ClaudeCliPlannerProvider()._build_command(payload)
    trace = payload["canonicalSharedContext"]["fields"]["missionTrace"]["value"]
    assert trace["tasks"][0]["plannerEvidence"]["providerId"] == "native-planner"
    assert trace["taskRuns"][0]["errorCode"] == "CHECK_FAILED"
    assert trace["artifacts"][0]["id"] == artifact.id
    assert huge not in json.dumps(payload)
    assert json.loads(db.get(Task, task.id).plan_json)["contextHandoff"]["raw"] == huge
    assert json.loads(db.get(Artifact, artifact.id).meta_json)["providerEvidence"]["raw"] == huge


def test_bounded_history_keeps_old_failed_work_ahead_of_completed_noise(db):
    message = _message(db, "Continue fixing unfinished work")
    failed_task, failed_run = _run(db, message, state="failed", title="Unresolved type error")
    for index in range(50):
        _run(db, message, title="Completed " + str(index))
    db.commit()
    payload = build_llm_planner_input(db, message)
    trace = payload["canonicalSharedContext"]["fields"]["missionTrace"]["value"]
    assert any(task["id"] == failed_task.id for task in trace["tasks"])
    assert any(run["id"] == failed_run.id for run in trace["taskRuns"])
    assert len(trace["tasks"]) <= 32 and len(trace["taskRuns"]) <= 32
    assert trace["selection"]["tasks"] == {"total": 51, "included": 32, "omitted": 19}
    assert trace["selection"]["taskRuns"] == {"total": 51, "included": 32, "omitted": 19}
    assert payload["originalUserRequest"] == message.content_md


def test_long_summary_strings_are_counted_without_trimming_current_request(db):
    message = _message(db, "当前需求必须完整保留 " * 120)
    _run(db, message, title="large historical title " * 1000)
    db.commit()
    payload = build_llm_planner_input(db, message)
    trace = payload["canonicalSharedContext"]["fields"]["missionTrace"]["value"]
    assert len(trace["tasks"][0]["title"]) <= 600
    assert trace["selection"]["truncated"] == 1
    assert payload["originalUserRequest"] == message.content_md
    assert payload["canonicalSharedContext"]["fields"]["userGoal"]["value"] == message.content_md
