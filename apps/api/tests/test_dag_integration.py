import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlmodel import Session as DbSession, select

import app.dag_integration as integration
import app.run_engine as run_engine
from app.dag_integration import delivery_worktree_path, integrate_join, integration_for_run
from app.deployments import _ensure_deploy_prerequisites
from app.models import Artifact, Diff, Task, TaskRun, TaskRunEvent
from app.previews import _ensure_preview_prerequisites
from app.routes.task_runs import retry_join_integration
from app.scheduler import evaluate_dependency_readiness
from app.task_runs import create_task_run, retry_task_run, transition_task_run
from test_execution_worktrees import BlockingWritingAdapter, branch_db, git, task_for


def complete(db, runs, monkeypatch):
    adapter = BlockingWritingAdapter()
    adapter.release.set()
    monkeypatch.setattr(run_engine, "ScriptedMockAdapter", lambda: adapter)
    asyncio.run(run_engine.BoundedRunDispatcher().run_once(db))
    db.expire_all()
    assert all(db.get(TaskRun, run.id).state == "completed" for run in runs)


@pytest.fixture
def completed_branches(branch_db, monkeypatch):
    db, session, source = branch_db
    tasks = [task_for(db, session, role) for role in ("backend", "frontend")]
    runs = [create_task_run(db, task.id) for task in tasks]
    complete(db, runs, monkeypatch)
    join = join_for(db, session, tasks)
    return db, session, source, tasks, runs, join


def join_for(db, session, tasks):
    join = Task(session_id=session.id, title="Review integrated branches", intent_type="review",
                depends_on_task_ids=json.dumps([task.id for task in tasks]),
                plan_json=json.dumps({"planner": "contract_first_v1"}),
                assigned_agent_id=tasks[0].assigned_agent_id)
    db.add(join)
    db.commit()
    return join


def commit_source(source, relative, content):
    (source / relative).write_text(content, encoding="utf-8")
    git(source, "add", "--", relative)
    git(source, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
        "-c", "core.hooksPath=", "commit", "-m", "canonical change")


def test_join_waits_for_every_branch_then_promotes_and_unlocks_delivery(branch_db, monkeypatch):
    db, session, source = branch_db
    tasks = [task_for(db, session, role) for role in ("backend", "frontend")]
    runs = [create_task_run(db, task.id) for task in tasks]
    join = join_for(db, session, tasks)
    original_head = git(source, "rev-parse", "HEAD")
    assert integrate_join(db.get_bind(), join.id) is None
    assert not evaluate_dependency_readiness(db, join).runnable

    complete(db, runs, monkeypatch)
    db.refresh(join)
    assert join.status == "completed"  # Coordinator integration precedes synthetic Review/QA.
    record = integration_for_run(db, runs[0])
    metadata = json.loads(record.meta_json)
    assert set(metadata["sourceRunIds"]) == {run.id for run in runs}
    assert metadata["sourceHead"] == original_head
    assert git(source, "rev-parse", "HEAD") == metadata["mergeCommit"]
    assert git(source, "status", "--porcelain") == ""
    for run, relative in zip(runs, ["apps/demo-api/app/main.py", "apps/demo/src/App.tsx"]):
        assert run.id in (source / relative).read_text()
        assert delivery_worktree_path(db, run) == session.worktree_path
        assert Path(run.worktree_path) != source
    _ensure_preview_prerequisites(db, runs[1])
    _ensure_deploy_prerequisites(db, runs[1])
    from app.previews import PreviewService
    from app.deployments import DeployService
    from test_previews import RecordingRunner, StaticHealthChecker

    runner = RecordingRunner()
    preview = PreviewService(process_runner=runner, health_checker=StaticHealthChecker(),
                             port_allocator=lambda: 5999).start_task_run_preview(db, runs[1].id)
    assert runner.started[0].cwd == source / "apps/demo"
    preview_metadata = json.loads(db.get(Artifact, preview.artifact_id).meta_json)
    assert preview_metadata["integration"]["mergeCommit"] == metadata["mergeCommit"]
    deployment = DeployService().create_mock_deployment(db, preview.id)
    assert json.loads(db.get(Artifact, deployment.artifact_id).meta_json)["source"]["integrationCommit"] == metadata["mergeCommit"]
    from app.deployments import DeployError

    preview_artifact = db.get(Artifact, preview.artifact_id)
    preview_metadata["integration"]["mergeCommit"] = "0" * 40
    preview_artifact.meta_json = json.dumps(preview_metadata)
    db.add(preview_artifact)
    db.commit()
    with pytest.raises(DeployError, match="Preview does not reference"):
        DeployService().create_mock_deployment(db, preview.id)
    assert len(db.exec(select(Artifact).where(Artifact.artifact_type == "integration")).all()) == 1
    assert len(db.exec(select(TaskRunEvent).where(TaskRunEvent.event_type == "artifact.integration.ready")).all()) == 1


def test_conflict_is_auditable_canonical_untouched_and_retry_reuses_branches(completed_branches):
    db, session, source, tasks, runs, join = completed_branches
    relative = "apps/demo/src/App.tsx"
    commit_source(source, relative, "canonical conflict\n")
    before = git(source, "rev-parse", "HEAD")
    conflict = integrate_join(db.get_bind(), join.id)
    assert conflict.artifact_type == "conflict"
    metadata = json.loads(conflict.meta_json)
    assert relative in metadata["conflictingFiles"]
    assert Path(metadata["worktreePath"]).exists()
    assert git(source, "rev-parse", "HEAD") == before
    assert (source / relative).read_text() == "canonical conflict\n"
    assert git(source, "status", "--porcelain") == ""
    assert integrate_join(db.get_bind(), join.id) is None  # No busy-loop duplicate artifact.
    assert integration_for_run(db, runs[1]) is None

    commit_source(source, relative, "baseline\n")
    result = retry_join_integration(join.id, BackgroundTasks(), db)
    assert result["status"] == "ready"
    assert result["artifactType"] == "integration"
    db.expire_all()
    assert len(db.exec(select(TaskRun)).all()) == 2
    assert db.get(Artifact, conflict.id).status == "blocked"  # Audit history is retained.
    assert runs[1].id in (source / relative).read_text()


def test_failed_branch_retry_does_not_rerun_successful_sibling(branch_db, monkeypatch):
    db, session, source = branch_db
    backend = task_for(db, session, "backend")
    frontend = task_for(db, session, "frontend")
    successful = create_task_run(db, backend.id)
    complete(db, [successful], monkeypatch)
    successful_diff = db.exec(select(Artifact).where(Artifact.task_run_id == successful.id, Artifact.artifact_type == "diff")).one()
    failed = create_task_run(db, frontend.id)
    transition_task_run(db, failed.id, "failed", error_message="test branch failure")
    join = join_for(db, session, [backend, frontend])
    assert integrate_join(db.get_bind(), join.id) is None
    retried = retry_task_run(db, failed.id)
    complete(db, [retried], monkeypatch)
    db.refresh(join)
    assert join.status == "completed"
    assert len(db.exec(select(TaskRun).where(TaskRun.task_id == backend.id)).all()) == 1
    assert db.get(Artifact, successful_diff.id).status == "ready"
    record = integration_for_run(db, successful)
    assert set(json.loads(record.meta_json)["sourceRunIds"]) == {successful.id, retried.id}
    assert db.get(TaskRun, failed.id).state == "failed"


def test_prepared_journal_recovers_crash_after_git_promotion(completed_branches, monkeypatch):
    db, session, source, tasks, runs, join = completed_branches
    promote = integration._promote_candidate

    def crash_after_promote(session, artifact):
        promote(session, artifact)
        raise RuntimeError("simulated worker exit after Git promotion")

    monkeypatch.setattr(integration, "_promote_candidate", crash_after_promote)
    with pytest.raises(RuntimeError, match="worker exit"):
        integrate_join(db.get_bind(), join.id)
    db.expire_all()
    prepared = db.exec(select(Artifact).where(Artifact.artifact_type == "integration")).one()
    assert prepared.status == "prepared"
    promoted_head = git(source, "rev-parse", "HEAD")
    monkeypatch.setattr(integration, "_promote_candidate", promote)
    asyncio.run(run_engine.BoundedRunDispatcher().run_once(db))
    db.refresh(prepared)
    db.refresh(join)
    assert prepared.status == "ready"
    assert join.status == "completed"
    assert git(source, "rev-parse", "HEAD") == promoted_head
    assert len(db.exec(select(Artifact).where(Artifact.artifact_type == "integration")).all()) == 1


def test_competing_coordinators_promote_once(completed_branches):
    db, session, source, tasks, runs, join = completed_branches
    bind, join_id = db.get_bind(), join.id
    db.commit()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: integrate_join(bind, join_id), range(2)))
    assert results[0].id == results[1].id
    db.expire_all()
    assert len(db.exec(select(Artifact).where(Artifact.artifact_type == "integration")).all()) == 1


def test_task_api_projects_verified_integration_without_host_paths(completed_branches):
    from app.routes.task_runs import task_response

    db, session, source, tasks, runs, join = completed_branches
    record = integrate_join(db.get_bind(), join.id)
    db.expire_all()
    response = task_response(db, db.get(Task, join.id)).model_dump(by_alias=True)
    diagnostic = response["integrationArtifacts"][0]
    assert diagnostic["artifactId"] == record.id
    assert diagnostic["verified"] is True
    assert set(diagnostic["sourceRunIds"]) == {run.id for run in runs}
    assert "worktreePath" not in diagnostic
    assert "canonicalWorktreePath" not in diagnostic
    diff = db.get(Diff, diagnostic["inputs"][0]["diffId"])
    diff.patch_text += "tampered"
    db.add(diff)
    db.commit()
    assert task_response(db, join).integration_artifacts[0]["verified"] is False


@pytest.mark.parametrize("tamper", ["dirty_canonical", "unsafe_patch", "scope_guard", "branch_path"])
def test_unverifiable_inputs_never_change_canonical(completed_branches, tamper):
    db, session, source, tasks, runs, join = completed_branches
    if tamper == "dirty_canonical":
        (source / "user-notes.txt").write_text("keep user data\n")
    elif tamper == "unsafe_patch":
        artifact = db.exec(select(Artifact).where(Artifact.task_run_id == runs[0].id, Artifact.artifact_type == "diff")).one()
        diff = db.exec(select(Diff).where(Diff.artifact_id == artifact.id)).one()
        diff.patch_text = diff.patch_text.replace("apps/demo-api/app/main.py", ".env")
        db.add(diff)
    elif tamper == "scope_guard":
        metrics = json.loads(runs[0].metrics_json)
        metrics.pop("taskRunScopeGuard")
        runs[0].metrics_json = json.dumps(metrics)
        db.add(runs[0])
    else:
        runs[0].worktree_path = str(source)
        db.add(runs[0])
    db.commit()
    before_head = git(source, "rev-parse", "HEAD")
    before_status = git(source, "status", "--porcelain")
    result = integrate_join(db.get_bind(), join.id)
    assert result.artifact_type == "conflict"
    assert git(source, "rev-parse", "HEAD") == before_head
    assert git(source, "status", "--porcelain") == before_status
    assert not (source / ".env").exists()


def test_merged_metadata_alone_does_not_unlock_join_or_delivery(completed_branches):
    db, session, source, tasks, runs, join = completed_branches
    metrics = json.loads(runs[0].metrics_json)
    metrics["executionWorktree"]["integrationStatus"] = "merged"
    runs[0].metrics_json = json.dumps(metrics)
    db.add(runs[0])
    db.commit()
    assert not evaluate_dependency_readiness(db, join).runnable
    assert integration_for_run(db, runs[0]) is None
    with pytest.raises(integration.IntegrationError):
        delivery_worktree_path(db, runs[0])


def test_join_waits_for_queued_shared_writer_without_creating_conflict(completed_branches):
    db, session, source, tasks, runs, join = completed_branches
    extra = task_for(db, session, "frontend", isolated=False)
    queued = create_task_run(db, extra.id)
    before = git(source, "rev-parse", "HEAD")
    db.commit()
    assert integrate_join(db.get_bind(), join.id) is None
    assert git(source, "rev-parse", "HEAD") == before
    assert db.exec(select(Artifact).where(Artifact.artifact_type == "conflict")).first() is None
    transition_task_run(db, queued.id, "interrupted")
    assert integrate_join(db.get_bind(), join.id).status == "ready"


@pytest.mark.parametrize("tamper", ["candidate", "canonical", "patch_evidence", "session_path"])
def test_delivery_revalidates_integrated_result(completed_branches, tamper):
    db, session, source, tasks, runs, join = completed_branches
    artifact = integrate_join(db.get_bind(), join.id)
    metadata = json.loads(artifact.meta_json)
    assert integration_for_run(db, runs[0], delivery=True) is not None
    if tamper == "candidate":
        (Path(metadata["worktreePath"]) / "apps/demo/src/App.tsx").write_text("tampered\n")
    elif tamper == "canonical":
        (source / "apps/demo/src/App.tsx").write_text("later user change\n")
    elif tamper == "session_path":
        other = source.parent / "other-canonical"
        git(source, "worktree", "add", "--detach", str(other), metadata["mergeCommit"])
        session.worktree_path = str(other)
        db.add(session)
        db.commit()
    else:
        diff = db.get(Diff, metadata["inputs"][0]["diffId"])
        diff.patch_text += "tampered"
        db.add(diff)
        db.commit()
    with pytest.raises(integration.IntegrationError):
        delivery_worktree_path(db, runs[0])


def test_run_creation_captures_baseline_after_concurrent_promotion(completed_branches, monkeypatch):
    db, session, source, tasks, runs, join = completed_branches
    next_task = task_for(db, session, "frontend", isolated=False)
    next_task_id, join_id, bind = next_task.id, join.id, db.get_bind()
    entered, release, creation_started = Event(), Event(), Event()
    promote = integration._promote_candidate

    def pause_at_promotion(session, artifact):
        entered.set()
        assert release.wait(10)
        promote(session, artifact)

    def create_next():
        creation_started.set()
        with DbSession(bind) as creation_db:
            run = create_task_run(creation_db, next_task_id)
            return run.base_ref

    monkeypatch.setattr(integration, "_promote_candidate", pause_at_promotion)
    db.commit()
    with ThreadPoolExecutor(max_workers=2) as pool:
        merge = pool.submit(integrate_join, bind, join_id)
        assert entered.wait(15)
        creation = pool.submit(create_next)
        try:
            assert creation_started.wait(5)
            assert not creation.done()
        finally:
            release.set()
        artifact = merge.result(timeout=15)
        new_base = creation.result(timeout=15)
    assert new_base == json.loads(artifact.meta_json)["mergeCommit"]
