import asyncio
import json
import subprocess
from pathlib import Path

import pytest
from fastapi import BackgroundTasks
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

import app.run_engine as run_engine
from app.adapters import AdapterRun
from app.deployments import DeployError, _ensure_deploy_prerequisites
from app.diffs import DiffCollectionError, collect_task_run_diff
from app.execution_worktrees import (
    ExecutionWorktreeError, allocate_execution_worktree, can_overlap_writes,
    execution_binding, validate_execution_worktree,
)
from app.models import Agent, Artifact, Message, Session, Task, TaskRun, Workspace
from app.previews import PreviewError, _ensure_preview_prerequisites
from app.routes.messages import auto_start_safe_tasks
from app.scheduler import evaluate_dependency_readiness
from app.scripted_mock import ScriptedMockAdapter
from app.session_queue import queue_gate_for_task_run
from app.task_runs import TaskRunLifecycleError, create_task_run, retry_task_run, transition_task_run


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


@pytest.fixture
def branch_db(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENTHUB_ISOLATED_WRITES", raising=False)
    source = tmp_path / "canonical"
    source.mkdir()
    for path in ("apps/demo/src/App.tsx", "apps/demo-api/app/main.py"):
        file = source / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("baseline\n", encoding="utf-8")
    git(source, "init")
    git(source, "add", ".")
    git(source, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
        "-c", "core.hooksPath=", "commit", "-m", "test baseline")
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'branches.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        workspace = Workspace(name="Isolated writes", repo_url="local://test", root_path=str(source), default_branch="main")
        session = Session(workspace_id=workspace.id, title="Branch session", worktree_path=str(source), bound_branch="main")
        db.add(workspace)
        db.add(session)
        for role in ("frontend", "backend"):
            db.add(Agent(name=role, role=role, adapter_type="scripted_mock", provider="local"))
        db.commit()
        yield db, session, source
    engine.dispose()


def task_for(db, session, role, *, isolated=True, dependencies=()):
    agent = db.exec(select(Agent).where(Agent.role == role)).one()
    relative = "apps/demo/src/App.tsx" if role == "frontend" else "apps/demo-api/app/main.py"
    task = Task(
        session_id=session.id, title=f"Write {role}", intent_type=f"{role}_change",
        assigned_agent_id=agent.id, depends_on_task_ids=json.dumps(list(dependencies)),
        plan_json=json.dumps({
            "targetId": f"demo-{role}", "files": [relative],
            "parallelGroup": "hint-only", "autoStart": True,
            **({"executionMode": "isolated_write"} if isolated else {}),
        }),
    )
    db.add(task)
    db.commit()
    return task


def test_branches_have_independent_baselines_patches_and_retry_history(branch_db):
    db, session, source = branch_db
    first = create_task_run(db, task_for(db, session, "backend").id, adapter_type="codex")
    second = create_task_run(db, task_for(db, session, "frontend").id)
    assert first.worktree_path != second.worktree_path != session.worktree_path
    assert first.base_ref == second.base_ref == git(source, "rev-parse", "HEAD")
    for run, relative in ((first, "apps/demo-api/app/main.py"), (second, "apps/demo/src/App.tsx")):
        binding = validate_execution_worktree(db, run)
        assert binding["branch"].endswith(run.id)
        (Path(run.worktree_path) / relative).write_text(f"output {run.id}\n", encoding="utf-8")
        patch = collect_task_run_diff(db, run.id)
        assert patch.changed_files == [relative]
        assert f"+output {run.id}" in patch.patch_text
        artifact = db.get(Artifact, patch.artifact_id)
        assert json.loads(artifact.meta_json)["executionWorktree"]["baseCommit"] == run.base_ref
    assert git(source, "status", "--porcelain") == ""
    old_path = Path(first.worktree_path)
    transition_task_run(db, first.id, "failed", error_message="retry test")
    retry = retry_task_run(db, first.id)
    assert retry.worktree_path != first.worktree_path
    assert execution_binding(retry)["previousRunId"] == first.id
    assert retry.base_ref == first.base_ref
    assert (Path(retry.worktree_path) / "apps/demo-api/app/main.py").read_text() == "baseline\n"
    assert first.id in (old_path / "apps/demo-api/app/main.py").read_text()
    assert db.get(TaskRun, first.id).state == "failed"


@pytest.mark.parametrize("isolated,same_target,expected", [(True, False, True), (True, True, False), (False, False, False)])
def test_queue_only_overlaps_verified_distinct_target_branches(branch_db, isolated, same_target, expected):
    db, session, _ = branch_db
    first = create_task_run(db, task_for(db, session, "backend", isolated=isolated).id)
    second = create_task_run(db, task_for(db, session, "backend" if same_target else "frontend", isolated=isolated).id)
    assert can_overlap_writes(db, first, second) is expected
    assert queue_gate_for_task_run(db, second.id).runnable is expected


@pytest.mark.parametrize("first_isolated", [True, False])
def test_mixed_shared_and_isolated_writes_remain_serial(branch_db, first_isolated):
    db, session, _ = branch_db
    first = create_task_run(db, task_for(db, session, "backend", isolated=first_isolated).id)
    second = create_task_run(db, task_for(db, session, "frontend", isolated=not first_isolated).id)
    assert queue_gate_for_task_run(db, second.id).blocking_task_run_ids == [first.id]


def test_isolated_retry_rejects_changed_canonical_baseline(branch_db):
    db, session, source = branch_db
    task = task_for(db, session, "frontend")
    run = create_task_run(db, task.id)
    transition_task_run(db, run.id, "failed")
    (source / "apps/demo/src/App.tsx").write_text("new canonical baseline\n")
    git(source, "add", ".")
    git(source, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
        "-c", "core.hooksPath=", "commit", "-m", "baseline moved")
    with pytest.raises(TaskRunLifecycleError, match="baseline"):
        retry_task_run(db, run.id)
    assert len(db.exec(select(TaskRun)).all()) == 1
    assert Path(run.worktree_path).exists()


def test_dirty_source_falls_back_to_serial_and_records_reason(branch_db):
    db, session, source = branch_db
    task = task_for(db, session, "backend")
    (source / "apps/demo-api/app/main.py").write_text("existing user change\n")
    run = create_task_run(db, task.id)
    assert run.worktree_path == session.worktree_path
    assert execution_binding(run) is None
    assert "dirty" in json.loads(run.metrics_json)["executionIsolationFallback"]["reason"]
    assert "existing user change" in (source / "apps/demo-api/app/main.py").read_text()


def test_unsupported_target_does_not_allocate(branch_db):
    db, session, _ = branch_db
    task = task_for(db, session, "backend")
    binding, reason = allocate_execution_worktree(
        db, task=task, session=session, run_id=task.id,
        target_id="external-test", access_mode="write",
    )
    assert binding is None
    assert "built-in" in reason


@pytest.mark.parametrize("tamper", ["path", "branch", "base", "session"])
def test_tampered_binding_cannot_bypass_fifo_or_launch_or_collect_diff(branch_db, tamper):
    db, session, source = branch_db
    first = create_task_run(db, task_for(db, session, "backend").id)
    second_task = task_for(db, session, "frontend")
    second = create_task_run(db, second_task.id)
    if tamper == "path":
        second.worktree_path = first.worktree_path
    elif tamper == "branch":
        git(Path(second.worktree_path), "checkout", "--detach")
    elif tamper == "base":
        second.base_ref = "0" * 40
    else:
        session.worktree_path = str(source.parent)
        db.add(session)
    db.add(second)
    db.commit()
    with pytest.raises(ExecutionWorktreeError):
        validate_execution_worktree(db, second)
    assert queue_gate_for_task_run(db, second.id).runnable is False
    assert run_engine._expected_task_run_worktree_path(db, second_task, session, "demo-frontend", second) is None
    with pytest.raises(DiffCollectionError):
        collect_task_run_diff(db, second.id)


def test_unmerged_outputs_do_not_unlock_join_preview_or_deployment(branch_db):
    db, session, _ = branch_db
    task = task_for(db, session, "frontend")
    run = create_task_run(db, task.id)
    transition_task_run(db, run.id, "completed")
    join = task_for(db, session, "backend", dependencies=[task.id])
    decision = evaluate_dependency_readiness(db, join)
    assert decision.runnable is False
    assert decision.blocking_dependency_ids == [task.id]
    with pytest.raises(PreviewError, match="integration"):
        _ensure_preview_prerequisites(db, run)
    with pytest.raises(DeployError, match="integration"):
        _ensure_deploy_prerequisites(db, run)


def test_auto_start_queues_both_isolated_roots(branch_db):
    db, session, _ = branch_db
    tasks = [task_for(db, session, "backend"), task_for(db, session, "frontend")]
    auto_start_safe_tasks(db, tasks, BackgroundTasks())
    runs = db.exec(select(TaskRun)).all()
    assert len(runs) == 2
    assert all(execution_binding(run) for run in runs)


@pytest.mark.parametrize("enabled", [False, True])
def test_contract_first_isolation_is_explicit_opt_in(branch_db, monkeypatch, enabled):
    from app.planning_intents import parse_app_contract_intent
    from app.planning_tasks import _create_contract_first_plan

    db, session, _ = branch_db
    if enabled:
        monkeypatch.setenv("AGENTHUB_ISOLATED_WRITES", "1")
    for role in ("orchestrator", "qa"):
        db.add(Agent(name=role, role=role, adapter_type="scripted_mock", provider="local"))
    message = Message(session_id=session.id, sender_type="user", content_md="Build a todo app")
    db.add(message)
    db.commit()
    tasks = _create_contract_first_plan(db, message, parse_app_contract_intent(message.content_md))
    modes = [json.loads(task.plan_json).get("executionMode") for task in tasks]
    assert modes == [None, "isolated_write" if enabled else None, "isolated_write" if enabled else None, None]


def test_real_write_execution_intervals_overlap_without_cross_branch_diffs(branch_db, monkeypatch):
    db, session, source = branch_db
    runs = [create_task_run(db, task_for(db, session, role).id) for role in ("backend", "frontend")]
    adapter = BlockingWritingAdapter()
    monkeypatch.setattr(run_engine, "ScriptedMockAdapter", lambda: adapter)
    dispatcher = run_engine.BoundedRunDispatcher(max_concurrency=2)

    async def exercise():
        dispatch = asyncio.create_task(dispatcher.run_once(db))
        try:
            await asyncio.wait_for(adapter.all_started.wait(), timeout=20)
            assert not dispatch.done()
            await asyncio.sleep(0.02)
        finally:
            adapter.release.set()
        return await asyncio.wait_for(dispatch, timeout=30)

    dispatched = asyncio.run(exercise())
    assert set(dispatched) == {run.id for run in runs}
    assert max(interval[0] for interval in adapter.intervals.values()) < min(interval[1] for interval in adapter.intervals.values())
    db.expire_all()
    for run in runs:
        stored = db.get(TaskRun, run.id)
        assert stored.state == "completed", (stored.error_code, stored.error_message, stored.metrics_json)
        artifacts = db.exec(select(Artifact).where(Artifact.task_run_id == run.id, Artifact.artifact_type == "diff")).all()
        assert len(artifacts) == 1
        metadata = json.loads(artifacts[0].meta_json)
        assert len(metadata["changedFiles"]) == 1
        assert metadata["executionWorktree"]["taskRunId"] == run.id
    assert git(source, "status", "--porcelain") == ""


class BlockingWritingAdapter(ScriptedMockAdapter):
    def __init__(self):
        self.requests = {}
        self.intervals = {}
        self.all_started = asyncio.Event()
        self.release = asyncio.Event()

    async def createRun(self, request):
        self.requests[request.task_run_id] = request
        return AdapterRun(adapterRunId=request.task_run_id)

    async def streamEvents(self, run_id):
        request = self.requests[run_id]
        loop = asyncio.get_running_loop()
        self.intervals[run_id] = [loop.time(), 0.0]
        if len(self.intervals) == 2:
            self.all_started.set()
        await self.release.wait()
        relative = request.plan_context["files"][0]
        (Path(request.worktree_path) / relative).write_text(f"isolated output {run_id}\n", encoding="utf-8")
        self.intervals[run_id][1] = loop.time()
        yield {"type": "completed", "payload": {"summary": "Bounded test adapter wrote one file."}}

    async def collectArtifacts(self, run_id):
        return []

    async def cleanup(self, run_id):
        pass

    async def interrupt(self, run_id):
        self.release.set()
