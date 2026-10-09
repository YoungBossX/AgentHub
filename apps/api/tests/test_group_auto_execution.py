import asyncio
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session as DbSession, SQLModel, create_engine, select

from app.group_execution import automatic_group_task, enqueue_ready_group_tasks, has_pending_automatic_groups
from app.main import app, get_db
from app.models import Agent, Artifact, Message, Session, Task, TaskRun, TaskRunEvent, Workspace
from app.planning import MentionParseError, plan_for_message
from app.run_engine import BoundedRunDispatcher, execute_task_run_background
from app.session_queue import entry_for_task_run
from app.task_runs import TaskRunLifecycleError, claim_task_run_for_worker, create_task_run, interrupt_task_run, retry_task_run, transition_task_run


@pytest.fixture
def runtime(tmp_path):
    from pathlib import Path

    root = tmp_path / "group-repo"
    source = root / "apps/demo/src"
    source.mkdir(parents=True)
    baseline = Path(__file__).resolve().parents[3] / "apps/demo/src"
    for name in ["App.tsx", "styles.css"]:
        shutil.copyfile(baseline / name, source / name)
    for cmd in [["git", "init"], ["git", "config", "user.email", "group@test.local"], ["git", "config", "user.name", "Group Fixture"], ["git", "add", "."], ["git", "commit", "-m", "Fixture"]]:
        subprocess.run(cmd, cwd=root, check=True, capture_output=True)
    engine = create_engine(f"sqlite:///{tmp_path / 'runtime.sqlite3'}", connect_args={"check_same_thread": False, "timeout": 30})
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        ws = Workspace(name="Auto", root_path="apps/demo", repo_url="local://apps/demo", default_branch="main")
        session = Session(workspace_id=ws.id, title="Automatic", bound_branch="main", worktree_path=str(root))
        db.add_all([ws, session, *[Agent(name=role, role=role, adapter_type="scripted_mock", provider="local") for role in ["orchestrator", "frontend", "backend", "qa"]]])
        db.commit()
        yield db, source
    engine.dispose()


def group(db, *, execution=None, content="@frontend @qa for demo app change button to Automatic Group"):
    message = Message(session_id=db.exec(select(Session)).one().id, sender_type="user", content_md=content, context_json=json.dumps({} if execution is None else {"groupExecution": execution}))
    db.add(message); db.commit()
    return plan_for_message(db, message, content)


def test_new_group_defaults_automatic_and_executes_own_reviewer(runtime):
    db, source = runtime
    tasks = group(db)
    assert all(automatic_group_task(t) for t in tasks)
    reply = db.exec(select(Message).where(Message.sender_type == "orchestrator")).one()
    assert "自动启动" in reply.content_md
    ids = enqueue_ready_group_tasks(db)
    assert len(ids) == 1
    assert enqueue_ready_group_tasks(db) == []
    dispatched = asyncio.run(BoundedRunDispatcher(max_concurrency=1).run_until_idle(db))
    runs = db.exec(select(TaskRun).order_by(TaskRun.created_at)).all()
    assert dispatched == [r.id for r in runs]
    assert len(runs) == 2 and all(r.state == "completed" for r in runs), [(r.state, r.error_code) for r in runs]
    assert b"Automatic Group" in (source / "App.tsx").read_bytes()
    assert entry_for_task_run(db, runs[1].id).access_mode == "readonly"
    assert entry_for_task_run(db, runs[1].id).target_lock_key is None
    reviews = db.exec(select(Artifact).where(Artifact.task_run_id == runs[1].id, Artifact.artifact_type == "review")).all()
    assert len(reviews) == 1
    assert asyncio.run(BoundedRunDispatcher().run_until_idle(db)) == []
    assert not has_pending_automatic_groups(db)
    with pytest.raises(TaskRunLifecycleError, match="already has an attempt"):
        create_task_run(db, tasks[0].id)


def test_automatic_login_group_writes_form_and_finishes_independent_review(runtime):
    db, source = runtime
    tasks = group(db, content="@frontend @qa build a login page for the demo app")
    assert json.loads(tasks[0].plan_json)["target"] == "login_page"
    enqueue_ready_group_tasks(db)
    asyncio.run(BoundedRunDispatcher(max_concurrency=1).run_until_idle(db))
    runs = db.exec(select(TaskRun).order_by(TaskRun.created_at)).all()
    assert len(runs) == 2 and all(run.state == "completed" for run in runs)
    assert '<form className="login-form"' in (source / "App.tsx").read_text(encoding="utf-8")
    assert entry_for_task_run(db, runs[1].id).access_mode == "readonly"
    assert not has_pending_automatic_groups(db)


@pytest.mark.parametrize("execution", ["manual", "historical"])
def test_manual_and_historical_groups_are_not_authorized(runtime, execution):
    db, _ = runtime
    tasks = group(db, execution="manual")
    if execution == "historical":
        for t in tasks:
            value = json.loads(t.plan_json)
            value["groupAssignment"].pop("execution")
            value["autoStart"] = True
            t.plan_json = json.dumps(value); db.add(t)
        db.commit()
    assert not any(automatic_group_task(t) for t in tasks)
    assert asyncio.run(BoundedRunDispatcher().run_until_idle(db)) == []
    assert db.exec(select(TaskRun)).all() == []


@pytest.mark.parametrize("state", ["failed", "interrupted"])
def test_terminal_attempt_stops_group_and_explicit_retry_resumes(runtime, state):
    db, _ = runtime
    tasks = group(db)
    run_id = enqueue_ready_group_tasks(db)[0]
    if state == "interrupted":
        interrupt_task_run(db, run_id)
    else:
        transition_task_run(db, run_id, "failed", error_code="CONTROLLED_FAILURE", error_message="Controlled fixture failure")
    assert asyncio.run(BoundedRunDispatcher().run_until_idle(db)) == []
    db.refresh(tasks[1]); assert tasks[1].status == "blocked"
    assert len(db.exec(select(TaskRun)).all()) == 1
    retry = retry_task_run(db, run_id)
    asyncio.run(BoundedRunDispatcher(max_concurrency=1).run_until_idle(db))
    db.refresh(retry); assert retry.state == "completed"
    runs = db.exec(select(TaskRun)).all()
    assert len(runs) == 3
    assert len([r for r in runs if r.task_id == tasks[1].id and r.state == "completed"]) == 1


def test_restart_reconciles_uncreated_downstream_from_persisted_plan(runtime):
    db, source = runtime
    tasks = group(db)
    first = enqueue_ready_group_tasks(db)[0]
    assert asyncio.run(execute_task_run_background(db, first, "scripted_mock"))
    assert len(db.exec(select(TaskRun)).all()) == 1
    before = (source / "App.tsx").read_bytes()
    with DbSession(db.get_bind()) as restarted:
        dispatched = asyncio.run(BoundedRunDispatcher().run_until_idle(restarted))
        assert len(dispatched) == 1
        assert restarted.get(TaskRun, first).state == "completed"
        assert len(restarted.exec(select(TaskRun)).all()) == 2
    assert (source / "App.tsx").read_bytes() == before


def test_concurrent_manual_and_automatic_initial_creation_is_unique(runtime):
    db, _ = runtime
    task = group(db)[0]
    task_id = task.id
    bind = db.get_bind()
    db.commit()

    def create(automatic):
        with DbSession(bind) as worker:
            try:
                return create_task_run(worker, task_id, automatic_group=automatic).id
            except TaskRunLifecycleError:
                return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        values = list(pool.map(create, [True, False]))
    assert len([v for v in values if v]) == 1
    db.expire_all()
    assert len(db.exec(select(TaskRun)).all()) == 1


def test_preparation_rejection_is_visible_and_not_repeated(runtime):
    db, _ = runtime
    tasks = group(db)
    agent = db.get(Agent, tasks[0].assigned_agent_id)
    agent.enabled = False; db.add(agent); db.commit()
    assert enqueue_ready_group_tasks(db) == []
    db.refresh(tasks[0]); assert json.loads(tasks[0].plan_json)["autoStart"] is False
    diagnostic = db.exec(select(Message).where(Message.message_kind == "chat", Message.sender_type == "orchestrator")).one()
    assert "自动启动被拒绝" in diagnostic.content_md
    assert db.exec(select(TaskRun)).all() == []
    assert enqueue_ready_group_tasks(db) == []
    assert len(db.exec(select(Message).where(Message.sender_type == "orchestrator")).all()) == 2
    agent.enabled = True; db.add(agent); db.commit()
    run = create_task_run(db, tasks[0].id)
    assert asyncio.run(execute_task_run_background(db, run.id, "scripted_mock"))
    asyncio.run(BoundedRunDispatcher().run_until_idle(db))
    assert len(db.exec(select(TaskRun)).all()) == 2


def test_http_submission_schedules_group_without_second_start(runtime, monkeypatch):
    db, _ = runtime
    session = db.exec(select(Session)).one()
    scheduled = []
    monkeypatch.setattr("app.routes.messages.schedule_task_run_execution", lambda _: scheduled.append(True))
    app.dependency_overrides[get_db] = lambda: db
    try:
        response = TestClient(app).post(f"/sessions/{session.id}/messages", json={"contentMd": "@frontend @qa for demo app change button to Automatic HTTP"})
        assert response.status_code == 201
        assert scheduled == [True]
        assert len(db.exec(select(TaskRun)).all()) == 1
        asyncio.run(BoundedRunDispatcher().run_until_idle(db))
        assert all(r.state == "completed" for r in db.exec(select(TaskRun)).all())
    finally:
        app.dependency_overrides.clear()


def test_competing_dispatcher_does_not_mutate_live_preparation_snapshot(runtime):
    db, _ = runtime
    task = group(db)[0]
    rid = enqueue_ready_group_tasks(db)[0]
    claimed = claim_task_run_for_worker(db, rid, worker_id="first-worker")
    db.refresh(task)
    before = (task.plan_json, task.updated_at, entry_for_task_run(db, rid).updated_at)
    assert claimed.state == "queued"
    assert asyncio.run(BoundedRunDispatcher().run_once(db)) == []
    db.refresh(task)
    assert (task.plan_json, task.updated_at, entry_for_task_run(db, rid).updated_at) == before
    assert db.get(TaskRun, rid).runner_id == "first-worker"
    assert asyncio.run(execute_task_run_background(db, rid, "scripted_mock", worker_id="first-worker"))
    assert db.get(TaskRun, rid).state == "completed"


def test_downstream_preparation_rejection_persists_sse_wakeup(runtime):
    db, _ = runtime
    tasks = group(db)
    rid = enqueue_ready_group_tasks(db)[0]
    assert asyncio.run(execute_task_run_background(db, rid, "scripted_mock"))
    agent = db.get(Agent, tasks[1].assigned_agent_id)
    agent.enabled = False; db.add(agent); db.commit()
    assert enqueue_ready_group_tasks(db) == []
    event = db.exec(select(TaskRunEvent).where(TaskRunEvent.event_type == "group.task.preparation_rejected")).one()
    assert event.task_run_id == rid
    payload = json.loads(event.payload_json)
    assert payload["taskId"] == tasks[1].id
    assert "自动启动被拒绝" in db.get(Message, payload["messageId"]).content_md
    assert enqueue_ready_group_tasks(db) == []
    assert len(db.exec(select(TaskRunEvent).where(TaskRunEvent.event_type == "group.task.preparation_rejected")).all()) == 1


@pytest.mark.parametrize("value", ["parallel", None, {}, False])
def test_invalid_execution_mode_rejects_without_partial_tasks(runtime, value):
    db, _ = runtime
    with pytest.raises(MentionParseError, match="groupExecution"):
        # None normally means missing in helper; here explicitly pass it.
        m = Message(session_id=db.exec(select(Session)).one().id, sender_type="user", content_md="@frontend @qa update demo app", context_json=json.dumps({"groupExecution": value}))
        db.add(m); db.commit()
        plan_for_message(db, m, m.content_md)
    assert db.exec(select(Task)).all() == []
