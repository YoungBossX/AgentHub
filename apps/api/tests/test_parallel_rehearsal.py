"""Bounded real-Git rehearsal; no real provider, preview server or deployment.

Set AGENTHUB_DAG_EVIDENCE_DIR to persist generated JSON evidence explicitly.
Without it this remains an ordinary isolated regression test.
"""
import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlmodel import select

import app.run_engine as run_engine
from app.dag_integration import integrate_join, integration_for_run
from app.models import Artifact, Diff, Task, TaskRun
from app.task_runs import create_task_run, retry_task_run
from test_dag_integration import commit_source, join_for
from test_execution_worktrees import BlockingWritingAdapter, branch_db, git, task_for


class RehearsalAdapter(BlockingWritingAdapter):
    fail_id = None

    async def streamEvents(self, run_id):
        async for event in super().streamEvents(run_id):
            if run_id == self.fail_id:
                raise RuntimeError("Bounded rehearsal injected branch failure")
            yield event


def persist(scenario, evidence):
    destination = os.environ.get("AGENTHUB_DAG_EVIDENCE_DIR")
    if destination:
        root = Path(destination).resolve()
        root.mkdir(parents=True, exist_ok=True)
        (root / f"{scenario}.json").write_text(json.dumps({
            "schemaVersion": "agenthub.parallel_rehearsal.v1",
            "recordedAt": datetime.now(timezone.utc).isoformat(),
            "scenario": scenario,
            "adapter": "bounded_test_adapter_actual_file_writes",
            "realProviderInvoked": False, "livePreviewStarted": False,
            "productionDeployed": False, **evidence,
        }, indent=2), encoding="utf-8")


@pytest.mark.parametrize("scenario", ["parallel_join", "failed_branch_retry", "conflict_retry"])
def test_bounded_parallel_rehearsal(branch_db, monkeypatch, scenario):
    db, session, source = branch_db
    tasks = [task_for(db, session, role) for role in ("backend", "frontend")]
    runs = [create_task_run(db, task.id) for task in tasks]
    base = git(source, "rev-parse", "HEAD")
    # Conflict scenario changes the canonical baseline before introducing a join.
    join = None if scenario == "conflict_retry" else join_for(db, session, tasks)
    adapter = RehearsalAdapter()
    if scenario == "failed_branch_retry":
        adapter.fail_id = runs[1].id
    monkeypatch.setattr(run_engine, "ScriptedMockAdapter", lambda: adapter)

    async def dispatch():
        job = asyncio.create_task(run_engine.BoundedRunDispatcher(max_concurrency=2).run_once(db))
        try:
            await asyncio.wait_for(adapter.all_started.wait(), timeout=30)
            assert git(source, "rev-parse", "HEAD") == base
            assert git(source, "status", "--porcelain") == ""
            if join:
                assert db.get(Task, join.id).status != "completed"
            await asyncio.sleep(0.05)
        finally:
            adapter.release.set()
        await asyncio.wait_for(job, timeout=60)

    asyncio.run(dispatch())
    db.expire_all()
    overlap = min(end for _, end in adapter.intervals.values()) - max(start for start, _ in adapter.intervals.values())
    assert overlap > 0
    evidence = {"baseCommit": base, "adapterIntervalsMonotonicSeconds": adapter.intervals,
                "overlapSeconds": overlap, "canonicalUnchangedWhileBranchesRunning": True}
    if scenario == "failed_branch_retry":
        assert db.get(TaskRun, runs[1].id).state == "failed"
        assert db.get(Task, join.id).status != "completed"
        successful_diff = db.exec(select(Diff).join(Artifact, Artifact.id == Diff.artifact_id).where(Artifact.task_run_id == runs[0].id)).one()
        before_hash = hashlib.sha256(successful_diff.patch_text.encode()).hexdigest()
        retried = retry_task_run(db, runs[1].id)
        recovery = RehearsalAdapter()
        recovery.release.set()
        monkeypatch.setattr(run_engine, "ScriptedMockAdapter", lambda: recovery)
        asyncio.run(run_engine.BoundedRunDispatcher().run_once(db))
        db.expire_all()
        assert list(recovery.requests) == [retried.id]
        assert len(db.exec(select(TaskRun).where(TaskRun.task_id == tasks[0].id)).all()) == 1
        assert hashlib.sha256(db.get(Diff, successful_diff.id).patch_text.encode()).hexdigest() == before_hash
        evidence["recovery"] = {"failedRunId": runs[1].id, "retryRunId": retried.id,
                                "preservedSuccessfulRunId": runs[0].id,
                                "preservedDiffId": successful_diff.id, "preservedPatchSha256": before_hash,
                                "onlyFailedBranchRerun": True}
        runs[1] = retried
    elif scenario == "conflict_retry":
        relative = "apps/demo/src/App.tsx"
        commit_source(source, relative, "canonical conflict\n")
        join = join_for(db, session, tasks)
        before = git(source, "rev-parse", "HEAD")
        conflict = integrate_join(db.get_bind(), join.id)
        assert conflict.artifact_type == "conflict"
        assert git(source, "rev-parse", "HEAD") == before
        assert (source / relative).read_text() == "canonical conflict\n"
        assert git(source, "status", "--porcelain") == ""
        assert integrate_join(db.get_bind(), join.id) is None
        evidence["conflict"] = {"artifactId": conflict.id, "canonicalUnchanged": True,
                                "metadata": json.loads(conflict.meta_json)}
        commit_source(source, relative, "baseline\n")
        assert integrate_join(db.get_bind(), join.id, retry=True).status == "ready"
        asyncio.run(run_engine.BoundedRunDispatcher().run_once(db))
        assert len(db.exec(select(TaskRun)).all()) == 2

    db.expire_all()
    record = integration_for_run(db, db.get(TaskRun, runs[0].id))
    assert record is not None
    metadata = json.loads(record.meta_json)
    assert set(metadata["sourceRunIds"]) == {run.id for run in runs}
    assert git(source, "rev-parse", "HEAD") == metadata["mergeCommit"]
    assert git(source, "status", "--porcelain") == ""
    assert db.get(Task, join.id).status == "completed"
    branches = []
    for run, relative in zip(runs, ["apps/demo-api/app/main.py", "apps/demo/src/App.tsx"]):
        diff = db.exec(select(Diff).join(Artifact, Artifact.id == Diff.artifact_id).where(Artifact.task_run_id == run.id)).one()
        assert json.loads(diff.changed_files_json) == [relative]
        assert run.id in (source / relative).read_text()
        branches.append({"runId": run.id, "diffId": diff.id, "file": relative,
                         "patchSha256": hashlib.sha256(diff.patch_text.encode()).hexdigest(),
                         "worktree": run.worktree_path})
    persist(scenario, {**evidence, "branches": branches, "joinTaskId": join.id,
                       "joinStatus": "completed", "integrationArtifactId": record.id,
                       "integration": metadata})


def test_bounded_serial_rehearsal(branch_db, monkeypatch):
    db, session, source = branch_db
    backend = task_for(db, session, "backend", isolated=False)
    frontend = task_for(db, session, "frontend", isolated=False, dependencies=[backend.id])
    runs = [create_task_run(db, backend.id)]
    adapter = RehearsalAdapter()
    adapter.release.set()
    monkeypatch.setattr(run_engine, "ScriptedMockAdapter", lambda: adapter)
    dispatcher = run_engine.BoundedRunDispatcher(max_concurrency=2)
    asyncio.run(dispatcher.run_once(db))
    assert list(adapter.requests) == [runs[0].id]
    # Ordinary serial plans allocate the downstream checkpoint after upstream
    # completion; unrelated shared writers must still hit dirty/conflict gates.
    runs.append(create_task_run(db, frontend.id))
    asyncio.run(dispatcher.run_once(db))
    db.expire_all()
    assert all(db.get(TaskRun, run.id).state == "completed" for run in runs)
    assert adapter.intervals[runs[0].id][1] <= adapter.intervals[runs[1].id][0]
    assert all(Path(run.worktree_path) == source for run in runs)
    persist("serial_control", {"runIds": [run.id for run in runs],
                               "adapterIntervalsMonotonicSeconds": adapter.intervals,
                               "overlap": False, "sharedWorktree": True})
