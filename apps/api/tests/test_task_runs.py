import asyncio
import json
import sqlite3
import subprocess
from collections.abc import Iterator
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from threading import Barrier, Event, Thread, get_ident
from time import monotonic
from typing import Optional

import pytest
import app.main as main_module
import app.run_engine as run_engine_module
import app.session_queue as session_queue_module
import app.target_locks as target_locks_module
import app.task_run_scope as task_run_scope
import app.task_runs as task_runs_module
from fastapi.testclient import TestClient
from sqlalchemy import event, func, update
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.adapters import (
    AdapterCapabilities,
    AdapterRun,
    AgentEvent,
    AgentRunRequest,
    run_adapter_event_stream,
)
from app.context_pack import build_session_context_pack
from app.external_workspaces import (
    ExternalWorkspaceRegistration,
    register_external_project_target,
)
from app.instruction_adapters import adapter_for_provider
from app.agent_runtime_config import RuntimeRoleConfig, upsert_runtime_config
from app.main import (
    _complete_ready_pipeline_review_tasks,
    agent_run_request_for,
    app,
    get_db,
    task_run_response,
)
from app.memory_snapshots import refresh_session_memory_snapshot
from app.guardrails import ApprovalRequestPayload, request_task_run_approval
from app.reviews import create_scripted_review_for_task_run
from app.diffs import DiffCollectionError
from app.models import (
    Agent,
    Artifact,
    Deployment,
    Diff,
    ExternalProjectTarget,
    Message,
    Preview,
    Review,
    Session,
    SessionExecutionLedger,
    SessionQueueEntry,
    TargetLock,
    Task,
    TaskRun,
    TaskRunEvent,
    Workspace,
)
from app.models import utc_now
from app.provider_gateway import ProviderHealthResult
from app.run_diagnostics import build_task_run_diagnostics
from app.run_supervisor import RunRegistrationRejected
from app.task_runs import (
    TaskRunLifecycleError,
    claim_task_run_for_worker,
    create_task_run,
    mark_stale_task_runs,
    refresh_task_run_heartbeat,
    transition_task_run,
)
from app.session_queue import entry_for_task_run
from app.target_locks import (
    acquire_target_lock,
    held_lock_for_target,
    recover_stale_target_locks,
    release_target_lock_for_task_run,
)
from app.target_registry import (
    AGENTHUB_PLATFORM_TARGET_ID,
    DEMO_BACKEND_TARGET_ID,
    DEMO_FRONTEND_TARGET_ID,
)


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with DbSession(engine) as db:
        workspace = Workspace(
            name="AgentHub Demo",
            repo_url="local://apps/demo",
            root_path="apps/demo",
            default_branch="main",
        )
        session = Session(
            workspace_id=workspace.id,
            title="TaskRun session",
            bound_branch="main",
            worktree_path=".worktrees/taskrun-session",
        )
        frontend = Agent(
            name="Frontend Agent",
            role="frontend",
            adapter_type="codex",
            provider="local",
        )
        backend = Agent(
            name="Backend Agent",
            role="backend",
            adapter_type="codex",
            provider="local",
        )
        qa = Agent(
            name="QA Agent",
            role="qa",
            adapter_type="scripted_mock",
            provider="local",
        )
        task = Task(
            session_id=session.id,
            title="Build login page",
            intent_type="frontend_change",
            status="pending",
            assigned_agent_id=frontend.id,
        )
        db.add(workspace)
        db.add(session)
        db.add(frontend)
        db.add(backend)
        db.add(qa)
        db.add(task)
        db.commit()

    def override_db() -> Iterator[DbSession]:
        with DbSession(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def db_from_override() -> DbSession:
    override = app.dependency_overrides[get_db]
    return next(override())


async def _allow_execution_access_binding_launch(operation):
    return True, await operation()


def task_id() -> str:
    with db_from_override() as db:
        return db.exec(select(Task).where(Task.title == "Build login page")).one().id


def _scope_snapshot(
    *,
    entries: tuple[task_run_scope.ScopeEntry, ...] = (),
    trusted_git_dir: str = "trusted-gitdir-a",
) -> task_run_scope.ScopeSnapshot:
    snapshot = task_run_scope.ScopeSnapshot(
        schema_version=task_run_scope.SCOPE_SNAPSHOT_SCHEMA_VERSION,
        available=True,
        reason=None,
        entries=entries,
        protected_control_digest="a" * 64,
    )
    object.__setattr__(snapshot, "_trusted_git_dir", trusted_git_dir)
    return snapshot


def _stub_scope_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    snapshot: task_run_scope.ScopeSnapshot,
) -> None:
    monkeypatch.setattr(
        task_runs_module,
        "capture_worktree_scope_snapshot",
        lambda worktree_path, **kwargs: snapshot,
    )


def _acquire_scope_lock(
    db: DbSession,
    task_run: TaskRun,
    *,
    target_id: str = DEMO_FRONTEND_TARGET_ID,
) -> None:
    task = db.get(Task, task_run.task_id)
    result = acquire_target_lock(
        db,
        target_id=target_id,
        session_id=task.session_id,
        task_run_id=task_run.id,
        worker_id=task_run.runner_id or "worker:scope-test",
        lease_expires_at=task_run.lease_expires_at,
    )
    assert result.acquired is True
    assert result.lock is not None
    task_run_scope.store_task_run_target_lock_acquisition_context(
        task_run.id,
        target_id=target_id,
        session_id=task.session_id,
        worker_id=task_run.runner_id or "worker:scope-test",
        lock_id=result.lock.id,
    )


def _allow_test_provider_health(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        run_engine_module._provider_health_probe,
        "check_provider",
        lambda provider, *, context: ProviderHealthResult(
            provider_id=provider.provider_id,
            adapter_type=provider.adapter_type,
            status="healthy",
            available=True,
            reason="Test provider health is available.",
        ),
    )


def _mark_task_run_queue_started(
    db: DbSession,
    task_run: TaskRun,
) -> None:
    queue_entry = entry_for_task_run(db, task_run.id)
    assert queue_entry is not None
    queue_entry.state = "running"
    queue_entry.started_at = queue_entry.started_at or utc_now()
    db.add(queue_entry)
    db.commit()


def _bind_started_write_execution(
    db: DbSession,
    task_run: TaskRun,
) -> TaskRun:
    _mark_task_run_queue_started(db, task_run)
    task_run = db.get(TaskRun, task_run.id)
    assert task_run is not None
    checkpoint = json.loads(task_run.metrics_json)["preRunCheckpoint"]
    execution_attempt_id = checkpoint["scopeExecutionAttemptId"]
    task_run = task_runs_module.persist_task_run_execution_access_binding(
        db,
        task_run.id,
        access_mode="write",
        execution_attempt_id=execution_attempt_id,
    )
    task_run.adapter_run_id = f"adapter-run:{task_run.id}"
    task_run.started_at = task_run.started_at or utc_now()
    db.add(task_run)
    db.commit()
    db.refresh(task_run)
    return task_run


def test_capture_scope_baseline_preserves_checkpoint_and_redacts_internal_evidence(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        run_id = run.id
        git_status = json.loads(run.metrics_json)["preRunCheckpoint"]["gitStatus"]

    snapshot = _scope_snapshot()
    _stub_scope_snapshot(monkeypatch, snapshot)

    with db_from_override() as db:
        stored = task_runs_module.capture_task_run_scope_baseline(db, run_id)
        raw_metrics = json.loads(stored.metrics_json)
        public_metrics = task_run_response(db, stored).metrics_json

    assert raw_metrics["preRunCheckpoint"]["gitStatus"] == git_status
    assert raw_metrics["preRunCheckpoint"]["scopeBaseline"]["schema_version"] == (
        task_run_scope.SCOPE_SNAPSHOT_SCHEMA_VERSION
    )
    assert raw_metrics["preRunCheckpoint"]["scopeBaseline"]["available"] is True
    checkpoint = raw_metrics["preRunCheckpoint"]
    assert checkpoint["scopeBaselineTaskRunId"] == run_id
    assert checkpoint["scopeBaselineIdentity"]
    assert checkpoint["scopeExecutionAttemptId"]
    assert checkpoint["scopeBaselineCapturedAt"].endswith("+00:00")
    assert checkpoint["scopeWorkspaceId"]
    assert checkpoint["scopePolicySchemaVersion"]
    assert checkpoint["scopePolicyIdentity"]
    assert "scopeControlKey" not in raw_metrics
    assert "scopeControlKey" not in public_metrics
    for internal_key in (
        "scopeWorkspaceId",
        "scopePolicySchemaVersion",
        "scopePolicyIdentity",
    ):
        assert internal_key not in public_metrics["preRunCheckpoint"]
    assert public_metrics["preRunCheckpoint"]["scopeBaseline"] == {
        "schema_version": task_run_scope.SCOPE_SNAPSHOT_SCHEMA_VERSION,
        "available": True,
        "reason": None,
        "protected_categories": [],
        "protected_entry_count": 0,
    }


def test_context_snapshot_keeps_internal_scope_evidence_out_of_public_metrics(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        run_id = run.id

    snapshot = _scope_snapshot(
        entries=(
            task_run_scope.ScopeEntry(
                path="apps/demo/src/App.tsx",
                status="tracked-present",
                fingerprint="b" * 64,
            ),
        ),
    )
    _stub_scope_snapshot(monkeypatch, snapshot)

    with db_from_override() as db:
        stored = task_runs_module.capture_task_run_scope_baseline(db, run_id)
        run_engine_module._persist_context_snapshot(
            db,
            stored,
            {"canonicalContext": {"requestId": "context-1"}},
        )
        db.refresh(stored)
        raw_metrics = json.loads(stored.metrics_json)
        public_metrics = task_runs_module.metrics_for_run(stored)

    assert "scopeControlKey" not in raw_metrics
    assert raw_metrics["preRunCheckpoint"]["scopeBaseline"]["entries"] == [
        {
            "path": "apps/demo/src/App.tsx",
            "status": "tracked-present",
            "fingerprint": "b" * 64,
        }
    ]
    assert raw_metrics["preRunCheckpoint"]["scopeBaseline"][
        "protected_control_digest"
    ] == "a" * 64
    assert "scopeControlKey" not in public_metrics
    assert "entries" not in public_metrics["preRunCheckpoint"]["scopeBaseline"]
    assert (
        "protected_control_digest"
        not in public_metrics["preRunCheckpoint"]["scopeBaseline"]
    )


def test_public_scope_metrics_allowlist_redacts_external_root_and_bindings(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    external_root = tmp_path / "private-host-root"
    (external_root / "src").mkdir(parents=True)
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    decision = task_run_scope.ScopeDecision(
        status="passed",
        error_code=None,
        target_id="external-public-metrics",
        changed_paths=(),
        rejected_paths=(),
        reason=None,
    )

    with db_from_override() as db:
        workspace = db.exec(
            select(Workspace).where(Workspace.name == "AgentHub Demo")
        ).one()
        register_external_project_target(
            db,
            workspace,
            ExternalWorkspaceRegistration(
                target_id="external-public-metrics",
                name="External Public Metrics",
                root_path=str(external_root),
                project_type="vite-react",
                allowed_paths=["src"],
            ),
        )
        task = db.get(Task, task_id())
        task.plan_json = json.dumps(
            {
                "targetId": "external-public-metrics",
                "safeTarget": "src",
                "files": ["src/App.tsx"],
            },
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run, target_id="external-public-metrics")
        baseline = task_runs_module.capture_task_run_scope_baseline(db, run.id)
        stored = task_runs_module.persist_scope_decision(db, baseline, decision)
        internal = task_runs_module.internal_metrics_for_run(stored)
        public = task_runs_module.metrics_for_run(stored)
        response_metrics = task_run_response(db, stored).metrics_json

    internal_checkpoint = internal["preRunCheckpoint"]
    assert internal_checkpoint["targetRoot"] == str(external_root.resolve())
    for key in (
        "scopeBaselineTaskRunId",
        "scopeBaselineIdentity",
        "scopeBaselineCapturedAt",
        "scopeExecutionAttemptId",
        "scopeWorkspaceId",
        "scopePolicySchemaVersion",
        "scopePolicyIdentity",
    ):
        assert internal_checkpoint[key]
    for evidence_key in ("taskRunScopeDecision", "taskRunScopeGuard"):
        for key in (
            "baselineIdentity",
            "baselineCapturedAt",
            "executionAttemptId",
            "workspaceId",
            "scopePolicySchemaVersion",
            "scopePolicyIdentity",
        ):
            assert internal[evidence_key][key]

    public_checkpoint = public["preRunCheckpoint"]
    for key in (
        "targetRoot",
        "scopeBaselineTaskRunId",
        "scopeBaselineIdentity",
        "scopeBaselineCapturedAt",
        "scopeExecutionAttemptId",
        "scopeWorkspaceId",
        "scopePolicySchemaVersion",
        "scopePolicyIdentity",
    ):
        assert key not in public_checkpoint
    assert public_checkpoint["allowedPaths"] == ["src"]
    assert public_checkpoint["plannedFiles"] == ["src/App.tsx"]
    assert set(public_checkpoint["scopeBaseline"]) == {
        "schema_version",
        "available",
        "reason",
        "protected_categories",
        "protected_entry_count",
    }
    assert set(public["taskRunScopeDecision"]) == {
        "schemaVersion",
        "taskRunId",
        "targetId",
        "baselineSchemaVersion",
        "status",
        "changedPathCount",
        "timestamp",
        "errorCode",
        "reason",
    }
    assert set(public["taskRunScopeGuard"]) == {
        "schemaVersion",
        "taskRunId",
        "targetId",
        "baselineSchemaVersion",
        "status",
        "changedPathCount",
        "timestamp",
    }
    assert "private-host-root" not in json.dumps(public, sort_keys=True)
    assert response_metrics == public


def test_public_scope_metrics_drop_forged_values_but_keep_internal_evidence(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    decision = task_run_scope.ScopeDecision(
        status="passed",
        error_code=None,
        target_id=DEMO_FRONTEND_TARGET_ID,
        changed_paths=(),
        rejected_paths=(),
        reason=None,
    )
    windows_host = r"C:\private-host\scope-secret.txt"
    posix_host = "/private-host/scope-secret.txt"
    secret = "sk-review-sentinel"
    nul_path = "src/\0nul-sentinel"

    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        baseline = task_runs_module.capture_task_run_scope_baseline(db, run.id)
        stored = task_runs_module.persist_scope_decision(db, baseline, decision)
        metrics = json.loads(stored.metrics_json)
        checkpoint = metrics["preRunCheckpoint"]
        checkpoint.update(
            {
                "targetId": windows_host,
                "targetRoot": windows_host,
                "allowedPaths": ["src", posix_host],
                "deniedPaths": [".env*", "../denied-sentinel"],
                "plannedFiles": ["src/App.tsx", windows_host],
                "dirtyFiles": ["src/App.tsx", nul_path],
                "gitStatus": {
                    "available": False,
                    "reason": f"{secret} at {windows_host}",
                    "dirtyFiles": ["../git-sentinel"],
                },
                "scopeBaseline": {
                    "schema_version": task_run_scope.SCOPE_SNAPSHOT_SCHEMA_VERSION,
                    "available": False,
                    "reason": f"{secret} at {posix_host}",
                    "entries": [],
                    "protected_control_digest": None,
                    "protected_categories": [],
                    "protected_entry_count": 0,
                },
            }
        )
        metrics["taskRunScopeDecision"].update(
            {
                "targetId": windows_host,
                "status": "rejected",
                "errorCode": "TASK_RUN_SCOPE_VIOLATION",
                "reason": f"{secret} at {posix_host}",
            }
        )
        metrics["taskRunScopeGuard"]["targetId"] = posix_host
        stored.metrics_json = json.dumps(metrics, separators=(",", ":"))
        db.add(stored)
        db.commit()
        db.refresh(stored)

        internal = task_runs_module.internal_metrics_for_run(stored)
        public = task_runs_module.metrics_for_run(stored)

    internal_json = json.dumps(internal, sort_keys=True)
    assert windows_host.replace("\\", "\\\\") in internal_json
    assert posix_host in internal_json
    assert secret in internal_json
    assert "nul-sentinel" in internal_json

    public_json = json.dumps(public, sort_keys=True)
    for sentinel in (
        "private-host",
        "scope-secret",
        secret,
        "denied-sentinel",
        "git-sentinel",
        "nul-sentinel",
    ):
        assert sentinel not in public_json
    assert "taskRunScopeDecision" not in public
    assert "taskRunScopeGuard" not in public
    public_checkpoint = public["preRunCheckpoint"]
    for unsafe_field in (
        "targetId",
        "targetRoot",
        "allowedPaths",
        "deniedPaths",
        "plannedFiles",
        "dirtyFiles",
        "gitStatus",
    ):
        assert unsafe_field not in public_checkpoint
    assert public_checkpoint["scopeBaseline"]["available"] is False
    assert public_checkpoint["scopeBaseline"]["reason"] == (
        "scope_snapshot_unavailable"
    )


def test_public_scope_decision_uses_fixed_safe_failure_reason(
    client: TestClient,
) -> None:
    persisted_reason = r"C:\private-host\sk-reason-sentinel"
    with db_from_override() as db:
        run = create_task_run(db, task_id())
        metrics = json.loads(run.metrics_json)
        metrics["taskRunScopeDecision"] = {
            "schemaVersion": task_run_scope.SCOPE_VALIDATION_SCHEMA_VERSION,
            "taskRunId": run.id,
            "targetId": DEMO_FRONTEND_TARGET_ID,
            "workspaceId": "workspace-safe",
            "scopePolicySchemaVersion": (
                task_runs_module.EFFECTIVE_WRITE_SCOPE_SCHEMA_VERSION
            ),
            "scopePolicyIdentity": "a" * 64,
            "baselineSchemaVersion": task_run_scope.SCOPE_SNAPSHOT_SCHEMA_VERSION,
            "baselineIdentity": "baseline-safe",
            "baselineCapturedAt": "2026-07-18T08:00:00+00:00",
            "executionAttemptId": "attempt-safe",
            "status": "rejected",
            "changedPathCount": 1,
            "timestamp": "2026-07-18T08:00:01+00:00",
            "errorCode": "TASK_RUN_SCOPE_VIOLATION",
            "reason": persisted_reason,
        }
        run.metrics_json = json.dumps(metrics, separators=(",", ":"))
        db.add(run)
        db.commit()
        db.refresh(run)

        internal = task_runs_module.internal_metrics_for_run(run)
        public = task_runs_module.metrics_for_run(run)

    assert internal["taskRunScopeDecision"]["reason"] == persisted_reason
    public_decision = public["taskRunScopeDecision"]
    assert public_decision == {
        "schemaVersion": task_run_scope.SCOPE_VALIDATION_SCHEMA_VERSION,
        "taskRunId": run.id,
        "targetId": DEMO_FRONTEND_TARGET_ID,
        "baselineSchemaVersion": task_run_scope.SCOPE_SNAPSHOT_SCHEMA_VERSION,
        "status": "rejected",
        "changedPathCount": 1,
        "timestamp": "2026-07-18T08:00:01+00:00",
        "errorCode": "TASK_RUN_SCOPE_VIOLATION",
        "reason": "The task run changed paths outside the assigned target.",
    }
    assert "reason-sentinel" not in json.dumps(public, sort_keys=True)


def test_capture_scope_baseline_stores_trusted_gitdir_only_in_runtime_context(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        run_id = run.id

    snapshot = _scope_snapshot()
    _stub_scope_snapshot(monkeypatch, snapshot)

    with db_from_override() as db:
        stored = task_runs_module.capture_task_run_scope_baseline(db, run_id)
        raw_metrics = json.loads(stored.metrics_json)
        checkpoint = raw_metrics["preRunCheckpoint"]
        context = task_run_scope.get_task_run_scope_runtime_context(
            run_id,
            baseline_identity=checkpoint["scopeBaselineIdentity"],
            execution_attempt_id=checkpoint["scopeExecutionAttemptId"],
        )

    assert context is not None
    assert context.task_run_id == run_id
    assert context.workspace_id == checkpoint["scopeWorkspaceId"]
    assert context.target_id == checkpoint["targetId"]
    assert context.policy_identity == checkpoint["scopePolicyIdentity"]
    assert context.baseline_identity == checkpoint["scopeBaselineIdentity"]
    assert context.execution_attempt_id == checkpoint["scopeExecutionAttemptId"]
    assert context.baseline_captured_at == checkpoint["scopeBaselineCapturedAt"]
    assert context.control_key
    assert context.trusted_git_dir == "trusted-gitdir-a"
    assert "trusted-gitdir-a" not in repr(context)
    assert context.control_key not in repr(context)
    assert (
        task_run_scope.get_task_run_scope_runtime_context(
            run_id,
            baseline_identity="other-baseline",
            execution_attempt_id=checkpoint["scopeExecutionAttemptId"],
        )
        is None
    )
    assert "trusted-gitdir-a" not in str(raw_metrics)
    assert context.control_key not in str(raw_metrics)


def test_capture_scope_baseline_marks_unknown_target_as_unavailable_without_host_path(
    client: TestClient,
    tmp_path: Path,
) -> None:
    external_root = tmp_path / "private-external-root"
    external_root.mkdir()
    with db_from_override() as db:
        task = db.get(Task, task_id())
        session = db.get(Session, task.session_id)
        workspace = db.get(Workspace, session.workspace_id)
        target = register_external_project_target(
            db,
            workspace,
            ExternalWorkspaceRegistration(
                target_id="external-unknown-baseline",
                name="External Unknown Baseline",
                root_path=str(external_root),
                project_type="vite-react",
                allowed_paths=["src"],
            ),
        )
        task.plan_json = json.dumps({"targetId": target.target_id})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        db.delete(target)
        db.commit()
        stored = task_runs_module.capture_task_run_scope_baseline(db, run.id)
        baseline = json.loads(stored.metrics_json)["preRunCheckpoint"]["scopeBaseline"]

    assert baseline["available"] is False
    assert baseline["reason"] == "scope_baseline_target_unavailable"
    assert "worktree" not in str(baseline)
    assert "X:" not in str(baseline)
    assert str(external_root) not in str(baseline)


def test_capture_scope_baseline_rejects_invalid_registry_policy(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        target = task_runs_module.get_target_for_workspace(
            db,
            db.get(Session, task.session_id).workspace_id,
            DEMO_FRONTEND_TARGET_ID,
        )
        invalid_target = replace(
            target,
            allowed_paths=("*", "../outside"),
        )
        monkeypatch.setattr(
            task_runs_module,
            "get_target_for_workspace",
            lambda db, workspace_id, target_id: invalid_target,
        )

        stored = task_runs_module.capture_task_run_scope_baseline(db, run.id)
        baseline = json.loads(stored.metrics_json)["preRunCheckpoint"][
            "scopeBaseline"
        ]
        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            task_runs_module.require_task_run_scope_baseline(db, run.id)

    assert baseline["available"] is False
    assert baseline["reason"] == "scope_baseline_target_unavailable"
    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


def test_capture_scope_baseline_requires_the_run_target_lock(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        run_id = run.id

    capture_calls = 0

    def capture(worktree_path, **kwargs):
        nonlocal capture_calls
        capture_calls += 1
        return _scope_snapshot()

    monkeypatch.setattr(task_runs_module, "capture_worktree_scope_snapshot", capture)
    with db_from_override() as db:
        stored = task_runs_module.capture_task_run_scope_baseline(db, run_id)
        baseline = json.loads(stored.metrics_json)["preRunCheckpoint"]["scopeBaseline"]

    assert capture_calls == 0
    assert baseline["available"] is False
    assert baseline["reason"] == "scope_baseline_lock_unavailable"
    assert task_run_scope.get_task_run_scope_runtime_context(run_id) is None


def test_scope_baseline_requirement_fails_if_target_lock_was_released(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.target_locks import release_target_lock_for_task_run

    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        task_runs_module.capture_task_run_scope_baseline(db, run.id)
        runtime_context = task_run_scope.get_task_run_scope_runtime_context(run.id)
        assert runtime_context is not None
        assert runtime_context.lock_id is not None
        release_target_lock_for_task_run(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            expected_lock_id=runtime_context.lock_id,
            worker_id=run.runner_id,
            task_run_id=run.id,
            session_id=task.session_id,
            release_reason="test_lock_loss_before_create_run",
        )

        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            task_runs_module.require_task_run_scope_baseline(db, run.id)

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


def test_terminal_transition_retains_scope_runtime_without_durable_decision(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        run_id = run.id
        _acquire_scope_lock(db, run)
        task_runs_module.capture_task_run_scope_baseline(db, run_id)
        assert task_run_scope.get_task_run_scope_runtime_context(run_id) is not None

        transition_task_run(
            db,
            run_id,
            "failed",
            error_code="TEST_FAILURE",
            error_message="Adapter failed before scope validation.",
        )

    assert task_run_scope.get_task_run_scope_runtime_context(run_id) is not None
    assert (
        task_run_scope.get_task_run_target_lock_acquisition_context(run_id)
        is None
    )
    task_run_scope.clear_task_run_scope_runtime_context(run_id)


def test_terminal_finalizer_retains_contexts_when_generation_release_is_unconfirmed(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        run_id = run.id
        _acquire_scope_lock(db, run)
        task_runs_module.capture_task_run_scope_baseline(db, run_id)
        runtime_context = task_run_scope.get_task_run_scope_runtime_context(run_id)
        acquisition_context = (
            task_run_scope.get_task_run_target_lock_acquisition_context(run_id)
        )
        assert runtime_context is not None
        assert acquisition_context is not None
        assert runtime_context.lock_id is not None
        expected_lock_id = runtime_context.lock_id
        worker_id = run.runner_id
        assert worker_id is not None

        release_calls: list[dict[str, object]] = []

        def release_generation(db_arg: DbSession, **kwargs):
            assert db_arg is db
            assert task_run_scope.get_task_run_scope_runtime_context(run_id) is runtime_context
            release_calls.append(kwargs)
            return None

        monkeypatch.setattr(
            target_locks_module,
            "release_target_lock_for_task_run",
            release_generation,
        )

        transition_task_run(
            db,
            run_id,
            "failed",
            error_code="TEST_FAILURE",
            error_message="Adapter failed after acquiring the target lock.",
        )

    assert release_calls == [
        {
            "target_id": DEMO_FRONTEND_TARGET_ID,
            "expected_lock_id": expected_lock_id,
            "worker_id": worker_id,
            "task_run_id": run_id,
            "session_id": task.session_id,
            "release_reason": "task_run_failed",
        }
    ]
    assert task_run_scope.get_task_run_scope_runtime_context(run_id) is runtime_context
    assert (
        task_run_scope.get_task_run_target_lock_acquisition_context(run_id)
        is acquisition_context
    )
    task_run_scope.clear_task_run_scope_runtime_context(run_id)
    task_run_scope.clear_task_run_target_lock_acquisition_context(run_id)


def test_terminal_finalizer_replay_retires_exactly_released_generation_contexts(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        run_id = run.id
        _acquire_scope_lock(db, run)
        baseline = task_runs_module.capture_task_run_scope_baseline(db, run_id)
        decision = task_runs_module.validate_task_run_scope(db, run_id)
        assert decision.status == "passed"
        run = task_runs_module.persist_scope_decision(db, baseline, decision)
        runtime_context = task_run_scope.get_task_run_scope_runtime_context(run_id)
        acquisition_context = (
            task_run_scope.get_task_run_target_lock_acquisition_context(run_id)
        )
        assert runtime_context is not None
        assert acquisition_context is not None
        assert runtime_context.lock_id == acquisition_context.lock_id
        original_lock_id = acquisition_context.lock_id
        worker_id = acquisition_context.worker_id

        original_mark_terminal = session_queue_module.mark_task_run_terminal
        queue_calls = 0

        def fail_queue_terminalization_once(*args, **kwargs):
            nonlocal queue_calls
            queue_calls += 1
            if queue_calls == 1:
                raise RuntimeError("injected queue terminalization failure")
            return original_mark_terminal(*args, **kwargs)

        monkeypatch.setattr(
            session_queue_module,
            "mark_task_run_terminal",
            fail_queue_terminalization_once,
        )
        with pytest.raises(
            RuntimeError,
            match="injected queue terminalization failure",
        ):
            transition_task_run(
                db,
                run_id,
                "failed",
                error_code="TEST_FAILURE",
                error_message="Queue terminalization failed after lock release.",
            )
        db.rollback()

        released = db.exec(
            select(TargetLock).where(
                TargetLock.lock_key
                == f"target:{DEMO_FRONTEND_TARGET_ID}:write"
            )
        ).one()
        queue_entry = entry_for_task_run(db, run_id)
        assert released.id == original_lock_id
        assert released.state == "released"
        assert queue_entry is not None
        assert queue_entry.state not in {"completed", "failed", "interrupted", "cancelled"}

        replacement = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=task.session_id,
            task_run_id=run_id,
            worker_id=worker_id,
            lease_expires_at=utc_now() + timedelta(minutes=5),
        )
        assert replacement.acquired is True
        assert replacement.lock is not None
        replacement_lock_id = replacement.lock.id
        assert replacement_lock_id != original_lock_id

        fresh_task = db.get(Task, task.id)
        fresh_run = db.get(TaskRun, run_id)
        task_runs_module.finalize_terminal_task_run(
            db,
            fresh_task,
            fresh_run,
            "failed",
        )

        durable_lock = db.exec(
            select(TargetLock).where(
                TargetLock.lock_key
                == f"target:{DEMO_FRONTEND_TARGET_ID}:write"
            )
        ).one()
        queue_entry = entry_for_task_run(db, run_id)
        events = db.exec(
            select(TaskRunEvent).where(TaskRunEvent.task_run_id == run_id)
        ).all()
        durable_metrics = json.loads(db.get(TaskRun, run_id).metrics_json)
        event_payloads = [json.loads(item.payload_json) for item in events]

    assert queue_calls == 2
    assert queue_entry is not None
    assert queue_entry.state == "failed"
    assert durable_lock.id == replacement_lock_id
    assert durable_lock.state == "held"
    assert task_run_scope.get_task_run_scope_runtime_context(run_id) is None
    assert (
        task_run_scope.get_task_run_target_lock_acquisition_context(run_id)
        is None
    )
    public_evidence = json.dumps(
        {
            "metrics": durable_metrics,
            "events": event_payloads,
        },
        sort_keys=True,
    )
    assert original_lock_id not in public_evidence
    assert replacement_lock_id not in public_evidence


def test_capture_scope_baseline_marks_capture_exception_as_unavailable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        run_id = run.id

    def raise_capture_error(worktree_path, *, control_key):
        raise RuntimeError("X:/sensitive-worktree")

    monkeypatch.setattr(
        task_runs_module,
        "capture_worktree_scope_snapshot",
        raise_capture_error,
    )
    with db_from_override() as db:
        stored = task_runs_module.capture_task_run_scope_baseline(db, run_id)
        baseline = json.loads(stored.metrics_json)["preRunCheckpoint"]["scopeBaseline"]
        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            task_runs_module.require_task_run_scope_baseline(db, run_id)

    assert baseline["available"] is False
    assert baseline["reason"] == "scope_capture_unavailable"
    assert "sensitive-worktree" not in str(baseline)
    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert "sensitive-worktree" not in exc_info.value.message


def test_validate_scope_is_unverifiable_after_runtime_context_is_lost(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        run_id = run.id

    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    with db_from_override() as db:
        stored = task_runs_module.capture_task_run_scope_baseline(db, run_id)
        metrics = json.loads(stored.metrics_json)
        task_run_scope.clear_task_run_scope_runtime_context(run_id)
        decision = task_runs_module.validate_task_run_scope(db, run_id)

    assert decision.status == "unverifiable"
    assert decision.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert "trusted-gitdir-a" not in str(metrics)


def test_validate_scope_is_unverifiable_for_missing_run_target_or_baseline(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        missing_run = task_runs_module.validate_task_run_scope(db, "missing-run")

        missing_target_run = create_task_run(db, task_id())
        missing_target = task_runs_module.validate_task_run_scope(
            db, missing_target_run.id
        )

        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        missing_baseline_run = create_task_run(db, task.id)
        missing_baseline = task_runs_module.validate_task_run_scope(
            db, missing_baseline_run.id
        )

    for decision in (missing_run, missing_target, missing_baseline):
        assert decision.status == "unverifiable"
        assert decision.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


def test_validate_scope_uses_execution_bound_runtime_context(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        run_id = run.id

    baseline = _scope_snapshot()
    current = _scope_snapshot(
        entries=(
            task_run_scope.ScopeEntry(
                path="apps/demo/src/App.tsx",
                status="tracked-present",
                fingerprint="b" * 64,
            ),
        )
    )
    captures: list[dict[str, object]] = []

    def capture(worktree_path, **kwargs):
        captures.append(kwargs)
        return baseline if len(captures) == 1 else current

    monkeypatch.setattr(task_runs_module, "capture_worktree_scope_snapshot", capture)
    with db_from_override() as db:
        task_runs_module.capture_task_run_scope_baseline(db, run_id)
        decision = task_runs_module.validate_task_run_scope(db, run_id)

    assert decision.status == "passed"
    assert decision.changed_paths == ("apps/demo/src/App.tsx",)
    assert captures[1]["control_key"] == captures[0]["control_key"]
    assert captures[1]["trusted_git_dir"] == "trusted-gitdir-a"


def test_validate_scope_is_unverifiable_when_same_target_policy_changes(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline_snapshot = _scope_snapshot()
    post_snapshot = _scope_snapshot(
        entries=(
            task_run_scope.ScopeEntry(
                path="package.json",
                status="tracked-present",
                fingerprint="b" * 64,
            ),
        )
    )
    capture_calls = 0

    def capture(worktree_path, **kwargs):
        nonlocal capture_calls
        capture_calls += 1
        return baseline_snapshot if capture_calls == 1 else post_snapshot

    monkeypatch.setattr(task_runs_module, "capture_worktree_scope_snapshot", capture)
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        task_runs_module.capture_task_run_scope_baseline(db, run.id)

        original_target = task_runs_module.get_target_for_workspace(
            db,
            db.get(Session, task.session_id).workspace_id,
            DEMO_FRONTEND_TARGET_ID,
        )
        widened_target = replace(
            original_target,
            allowed_paths=(*original_target.allowed_paths, "package.json"),
        )
        monkeypatch.setattr(
            task_runs_module,
            "get_target_for_workspace",
            lambda db, workspace_id, target_id: widened_target,
        )

        decision = task_runs_module.validate_task_run_scope(db, run.id)

    assert decision.status == "unverifiable"
    assert decision.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


def test_require_scope_passed_rejects_legacy_run_without_marker(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        run = create_task_run(db, task_id())

        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            task_runs_module.require_task_run_scope_passed(db, run.id)

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


def test_persisted_passed_scope_decision_authorizes_the_task_run(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = task_run_scope.ScopeDecision(
        status="passed",
        error_code=None,
        target_id=DEMO_FRONTEND_TARGET_ID,
        changed_paths=("apps/demo/src/App.tsx",),
        rejected_paths=(),
        reason=None,
    )
    baseline_snapshot = _scope_snapshot()
    post_snapshot = _scope_snapshot(
        entries=(
            task_run_scope.ScopeEntry(
                path="apps/demo/src/App.tsx",
                status="tracked-present",
                fingerprint="b" * 64,
            ),
        )
    )
    captures: list[dict[str, object]] = []

    def capture(worktree_path, **kwargs):
        captures.append(kwargs)
        return baseline_snapshot if len(captures) == 1 else post_snapshot

    monkeypatch.setattr(task_runs_module, "capture_worktree_scope_snapshot", capture)
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        baseline = task_runs_module.capture_task_run_scope_baseline(db, run.id)
        checkpoint = json.loads(baseline.metrics_json)["preRunCheckpoint"]
        stored = task_runs_module.persist_scope_decision(db, baseline, decision)
        marker = json.loads(stored.metrics_json)["taskRunScopeGuard"]
        public_metrics = task_runs_module.metrics_for_run(stored)
        required = task_runs_module.require_task_run_scope_passed(db, run.id)

    assert marker == {
        "schemaVersion": task_run_scope.SCOPE_VALIDATION_SCHEMA_VERSION,
        "taskRunId": run.id,
        "targetId": DEMO_FRONTEND_TARGET_ID,
        "workspaceId": checkpoint["scopeWorkspaceId"],
        "scopePolicySchemaVersion": checkpoint["scopePolicySchemaVersion"],
        "scopePolicyIdentity": checkpoint["scopePolicyIdentity"],
        "baselineSchemaVersion": task_run_scope.SCOPE_SNAPSHOT_SCHEMA_VERSION,
        "baselineIdentity": checkpoint["scopeBaselineIdentity"],
        "baselineCapturedAt": checkpoint["scopeBaselineCapturedAt"],
        "executionAttemptId": checkpoint["scopeExecutionAttemptId"],
        "status": "passed",
        "changedPathCount": 1,
        "timestamp": marker["timestamp"],
    }
    assert marker["timestamp"].endswith("+00:00")
    for evidence_key in ("taskRunScopeDecision", "taskRunScopeGuard"):
        for internal_key in (
            "workspaceId",
            "scopePolicySchemaVersion",
            "scopePolicyIdentity",
        ):
            assert internal_key not in public_metrics[evidence_key]
    assert required.status == "passed"
    assert len(captures) == 2


@pytest.mark.parametrize("decision_status", ("passed", "rejected"))
def test_scope_decision_persistence_fails_closed_if_lock_generation_changes_after_validation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    decision_status: str,
) -> None:
    baseline_snapshot = _scope_snapshot()
    current_snapshot = (
        baseline_snapshot
        if decision_status == "passed"
        else _scope_snapshot(
            entries=(
                task_run_scope.ScopeEntry(
                    path="package.json",
                    status="tracked-present",
                    fingerprint="b" * 64,
                ),
            )
        )
    )
    capture_calls = 0

    def capture(worktree_path, **kwargs):
        nonlocal capture_calls
        capture_calls += 1
        return baseline_snapshot if capture_calls == 1 else current_snapshot

    monkeypatch.setattr(task_runs_module, "capture_worktree_scope_snapshot", capture)
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        baseline = task_runs_module.capture_task_run_scope_baseline(db, run.id)
        runtime_context = task_run_scope.get_task_run_scope_runtime_context(run.id)
        assert runtime_context is not None
        assert runtime_context.lock_id is not None
        original_lock_id = runtime_context.lock_id
        decision = task_runs_module.validate_task_run_scope(db, run.id)
        assert decision.status == decision_status
        worker_id = run.runner_id or "worker:scope-test"
        session_id = task.session_id
        lease_expires_at = run.lease_expires_at
        rotated = False

        def rotate_lock_before_persistence() -> str:
            nonlocal rotated
            assert rotated is False
            released = release_target_lock_for_task_run(
                db,
                target_id=DEMO_FRONTEND_TARGET_ID,
                expected_lock_id=original_lock_id,
                worker_id=worker_id,
                task_run_id=run.id,
                session_id=session_id,
                release_reason="rotate_after_scope_validation",
            )
            assert released is not None
            reacquired = acquire_target_lock(
                db,
                target_id=DEMO_FRONTEND_TARGET_ID,
                session_id=session_id,
                task_run_id=run.id,
                worker_id=worker_id,
                lease_expires_at=lease_expires_at,
            )
            assert reacquired.acquired is True
            assert reacquired.lock is not None
            rotated = True
            return "2026-07-26T12:00:00+00:00"

        monkeypatch.setattr(
            task_runs_module,
            "_utc_scope_timestamp",
            rotate_lock_before_persistence,
        )
        stored = task_runs_module.persist_scope_decision(db, baseline, decision)
        metrics = json.loads(stored.metrics_json)
        events = db.exec(
            select(TaskRunEvent).where(TaskRunEvent.task_run_id == run.id)
        ).all()

        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            task_runs_module.require_task_run_scope_passed(db, run.id)

    assert rotated is True
    assert "taskRunScopeGuard" not in metrics
    assert metrics["taskRunScopeDecision"]["status"] == "unverifiable"
    assert metrics["taskRunScopeDecision"]["errorCode"] == (
        "TASK_RUN_SCOPE_UNVERIFIABLE"
    )
    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert original_lock_id not in stored.metrics_json
    assert all(original_lock_id not in event.payload_json for event in events)


def test_target_lock_generation_stays_private_across_public_run_surfaces(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        worker_id = run.runner_id or "worker:scope-test"
        first = held_lock_for_target(db, DEMO_FRONTEND_TARGET_ID)
        assert first is not None
        first_generation_id = first.id

        released = release_target_lock_for_task_run(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            expected_lock_id=first_generation_id,
            worker_id=worker_id,
            task_run_id=run.id,
            session_id=task.session_id,
            release_reason="rotate_private_generation",
        )
        assert released is not None
        task_run_scope.clear_task_run_target_lock_acquisition_context(run.id)
        second = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=task.session_id,
            task_run_id=run.id,
            worker_id=worker_id,
            lease_expires_at=run.lease_expires_at,
        )
        assert second.acquired is True
        assert second.lock is not None
        second_generation_id = second.lock.id
        second_acquired_at = second.lock.acquired_at
        second_lease = second.lock.lease_expires_at
        assert second_generation_id != first_generation_id
        assert second_acquired_at is not None
        acquisition_context = (
            task_run_scope.store_task_run_target_lock_acquisition_context(
                run.id,
                target_id=DEMO_FRONTEND_TARGET_ID,
                session_id=task.session_id,
                worker_id=worker_id,
                lock_id=second_generation_id,
            )
        )

        stored = task_runs_module.capture_task_run_scope_baseline(db, run.id)
        runtime_context = task_run_scope.get_task_run_scope_runtime_context(run.id)
        assert runtime_context is not None
        runtime_context_repr = repr(runtime_context)
        private_runtime_context = {
            "execution_attempt_id": runtime_context.execution_attempt_id,
            "control_key": runtime_context.control_key,
            "trusted_git_dir": runtime_context.trusted_git_dir,
            "lock_id": runtime_context.lock_id,
        }
        for field_name, field_value in private_runtime_context.items():
            assert isinstance(field_value, str) and field_value
            assert field_name not in runtime_context_repr
            assert field_value not in runtime_context_repr
        repeated = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=task.session_id,
            task_run_id=run.id,
            worker_id=worker_id,
            lease_expires_at=(
                second_lease + timedelta(minutes=1)
                if second_lease is not None
                else None
            ),
        )
        assert repeated.acquired is True
        assert repeated.lock is not None
        assert repeated.lock.id == second_generation_id
        assert repeated.lock.acquired_at == second_acquired_at
        assert repeated.lock.lease_expires_at == second_lease

        request = agent_run_request_for(db, run, adapter_type="codex")

        lock_diagnostics = target_locks_module.lock_diagnostics_for_task_run(
            db,
            run.id,
        )
        assert lock_diagnostics is not None
        response_payload = task_run_response(db, stored).model_dump(
            mode="json",
            by_alias=True,
        )
        diagnostics_payload = build_task_run_diagnostics(
            db,
            db.get(TaskRun, run.id),
        ).model_dump(mode="json", by_alias=True)
        events = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == run.id)
            .order_by(TaskRunEvent.sequence)
        ).all()
        event_payloads = [event.payload_json for event in events]
        acquired_payloads = [
            json.loads(event.payload_json)
            for event in events
            if event.event_type == "target_lock.acquired"
        ]
        metrics_json = db.get(TaskRun, run.id).metrics_json
        session_id = task.session_id

    mission_trace_response = client.get(f"/sessions/{session_id}/mission-trace")
    assert mission_trace_response.status_code == 200
    mission_trace_payload = mission_trace_response.json()
    run_trace = next(
        item for item in mission_trace_payload["taskRuns"] if item["id"] == run.id
    )

    assert request.task_run_id == run.id
    assert request.session_id == session_id
    assert request.adapter_type == "codex"
    assert request.plan_context["targetId"] == DEMO_FRONTEND_TARGET_ID
    assert request.plan_context["sessionContext"]["version"] == (
        "session_context_pack_v1"
    )
    assert DEMO_FRONTEND_TARGET_ID in request.instruction
    assert "Canonical Shared Context" in request.instruction

    expected_acquired_at = second_acquired_at.isoformat()
    assert lock_diagnostics["acquiredAt"] == expected_acquired_at
    assert response_payload["targetLock"]["acquiredAt"] == expected_acquired_at
    assert run_trace["targetLock"]["acquiredAt"] == expected_acquired_at
    assert [payload["acquiredAt"] for payload in acquired_payloads[-2:]] == [
        expected_acquired_at,
        expected_acquired_at,
    ]

    serialized_surfaces = [
        metrics_json,
        *event_payloads,
        json.dumps(lock_diagnostics, sort_keys=True),
        json.dumps(response_payload, sort_keys=True),
        json.dumps(diagnostics_payload, sort_keys=True),
        json.dumps(mission_trace_payload, sort_keys=True),
        runtime_context_repr,
        repr(acquisition_context),
        request.instruction,
        json.dumps(request.plan_context, sort_keys=True),
        request.model_dump_json(by_alias=True),
    ]
    for generation_id in (first_generation_id, second_generation_id):
        assert all(generation_id not in surface for surface in serialized_surfaces)

    forbidden_generation_keys = {
        "id",
        "lockId",
        "lock_id",
        "targetLockId",
        "generationId",
    }
    public_lock_payloads = [
        lock_diagnostics,
        response_payload["targetLock"],
        run_trace["targetLock"],
        *acquired_payloads,
    ]
    assert all(
        forbidden_generation_keys.isdisjoint(payload)
        for payload in public_lock_payloads
    )
    task_run_scope.clear_task_run_scope_runtime_context(run.id)
    task_run_scope.clear_task_run_target_lock_acquisition_context(run.id)


@pytest.mark.parametrize("decision_status", ("passed", "rejected"))
def test_scope_decision_guard_rechecks_sqlite_time_after_write_lock_wait(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    decision_status: str,
) -> None:
    database_path = tmp_path / f"scope-lease-wait-{decision_status}.db"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    SQLModel.metadata.create_all(engine)
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")

    baseline_snapshot = _scope_snapshot()
    current_snapshot = (
        baseline_snapshot
        if decision_status == "passed"
        else _scope_snapshot(
            entries=(
                task_run_scope.ScopeEntry(
                    path="package.json",
                    status="tracked-present",
                    fingerprint="b" * 64,
                ),
            )
        )
    )
    capture_calls = 0

    def capture(worktree_path, **kwargs):
        nonlocal capture_calls
        capture_calls += 1
        return baseline_snapshot if capture_calls == 1 else current_snapshot

    monkeypatch.setattr(task_runs_module, "capture_worktree_scope_snapshot", capture)
    with DbSession(engine) as setup_db:
        workspace = Workspace(
            name=f"Scope lease wait {decision_status}",
            repo_url="local://apps/demo",
            root_path="apps/demo",
            default_branch="main",
        )
        session = Session(
            workspace_id=workspace.id,
            title=f"Scope lease wait {decision_status}",
            bound_branch="main",
            worktree_path=f".worktrees/scope-lease-wait-{decision_status}",
        )
        agent = Agent(
            name=f"Scope Lease Wait {decision_status.title()}",
            role="frontend",
            adapter_type="codex",
            provider="local",
        )
        task = Task(
            session_id=session.id,
            title=f"Reject expired lock evidence after wait ({decision_status})",
            intent_type="frontend_change",
            status="pending",
            assigned_agent_id=agent.id,
            plan_json=json.dumps(
                {
                    "targetId": DEMO_FRONTEND_TARGET_ID,
                    "safeTarget": "apps/demo/src",
                    "files": ["apps/demo/src/App.tsx"],
                },
                separators=(",", ":"),
            ),
        )
        setup_db.add(workspace)
        setup_db.add(session)
        setup_db.add(agent)
        setup_db.add(task)
        setup_db.commit()
        run = claim_task_run_for_worker(
            setup_db,
            create_task_run(setup_db, task.id).id,
            worker_id=f"worker:lease-wait:{decision_status}",
        )
        _acquire_scope_lock(setup_db, run)
        task_runs_module.capture_task_run_scope_baseline(setup_db, run.id)
        runtime_context = task_run_scope.get_task_run_scope_runtime_context(run.id)
        assert runtime_context is not None
        assert runtime_context.lock_id is not None
        run_id = run.id
        lock_id = runtime_context.lock_id

    with DbSession(engine) as validation_db:
        decision = task_runs_module.validate_task_run_scope(validation_db, run_id)
    assert decision.status == decision_status

    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            UPDATE targetlock
            SET lease_expires_at = strftime('%Y-%m-%d %H:%M:%f', 'now', '+2 seconds')
            WHERE id = ?
            """,
            (lock_id,),
        )

    guarded_update_started = Event()
    guarded_update_finished = Event()
    writer_finished = Event()
    writer_results: list[dict[str, object]] = []
    writer_errors: list[BaseException] = []

    def is_guarded_scope_update(statement: str) -> bool:
        normalized = " ".join(statement.lower().split())
        return normalized.startswith("update taskrun set") and "targetlock" in normalized

    def before_cursor_execute(
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        if is_guarded_scope_update(statement):
            guarded_update_started.set()

    def after_cursor_execute(
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        if is_guarded_scope_update(statement):
            guarded_update_finished.set()

    def persist_from_second_session() -> None:
        try:
            with DbSession(engine) as writer_db:
                stored = task_runs_module.persist_scope_decision(
                    writer_db,
                    writer_db.get(TaskRun, run_id),
                    decision,
                )
                writer_results.append(json.loads(stored.metrics_json))
        except BaseException as exc:
            writer_errors.append(exc)
        finally:
            writer_finished.set()

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    event.listen(engine, "after_cursor_execute", after_cursor_execute)
    blocker = engine.connect()
    writer = Thread(target=persist_from_second_session, daemon=True)
    try:
        blocker.exec_driver_sql("BEGIN IMMEDIATE")
        writer.start()
        assert guarded_update_started.wait(timeout=5)
        assert blocker.exec_driver_sql(
            """
            SELECT julianday(lease_expires_at) > julianday('now')
            FROM targetlock
            WHERE id = ?
            """,
            (lock_id,),
        ).scalar_one() == 1
        assert guarded_update_finished.is_set() is False
        assert writer_finished.is_set() is False

        deadline = monotonic() + 5
        while blocker.exec_driver_sql(
            """
            SELECT julianday(lease_expires_at) <= julianday('now')
            FROM targetlock
            WHERE id = ?
            """,
            (lock_id,),
        ).scalar_one() != 1:
            assert monotonic() < deadline
            writer_finished.wait(timeout=0.01)

        assert guarded_update_finished.is_set() is False
        assert writer_finished.is_set() is False
        blocker.commit()
        assert writer_finished.wait(timeout=5)
        writer.join(timeout=5)
    finally:
        if blocker.in_transaction():
            blocker.rollback()
        blocker.close()
        writer.join(timeout=5)
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
        event.remove(engine, "after_cursor_execute", after_cursor_execute)

    assert writer.is_alive() is False
    assert guarded_update_finished.is_set() is True
    assert writer_errors == []
    assert len(writer_results) == 1
    assert writer_results[0]["taskRunScopeDecision"]["status"] == "unverifiable"
    assert "taskRunScopeGuard" not in writer_results[0]

    with DbSession(engine) as fresh_db:
        durable_metrics = json.loads(fresh_db.get(TaskRun, run_id).metrics_json)
    engine.dispose()

    assert durable_metrics["taskRunScopeDecision"]["status"] == "unverifiable"
    assert "taskRunScopeGuard" not in durable_metrics


def test_scope_decision_fallback_cas_preserves_write_after_refresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "scope-fallback-cas.db"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 5},
    )
    SQLModel.metadata.create_all(engine)
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")

    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    with DbSession(engine) as setup_db:
        workspace = Workspace(
            name="Scope fallback CAS",
            repo_url="local://apps/demo",
            root_path="apps/demo",
            default_branch="main",
        )
        session = Session(
            workspace_id=workspace.id,
            title="Scope fallback CAS",
            bound_branch="main",
            worktree_path=".worktrees/scope-fallback-cas",
        )
        agent = Agent(
            name="Scope Fallback Frontend",
            role="frontend",
            adapter_type="codex",
            provider="local",
        )
        task = Task(
            session_id=session.id,
            title="Preserve concurrent fallback metrics",
            intent_type="frontend_change",
            status="pending",
            assigned_agent_id=agent.id,
            plan_json=json.dumps(
                {
                    "targetId": DEMO_FRONTEND_TARGET_ID,
                    "safeTarget": "apps/demo/src",
                    "files": ["apps/demo/src/App.tsx"],
                },
                separators=(",", ":"),
            ),
        )
        setup_db.add(workspace)
        setup_db.add(session)
        setup_db.add(agent)
        setup_db.add(task)
        setup_db.commit()
        run = create_task_run(setup_db, task.id)
        _acquire_scope_lock(setup_db, run)
        task_runs_module.capture_task_run_scope_baseline(setup_db, run.id)
        run_id = run.id

    decision = task_run_scope.ScopeDecision(
        status="passed",
        error_code=None,
        target_id=DEMO_FRONTEND_TARGET_ID,
        changed_paths=(),
        rejected_paths=(),
        reason=None,
    )
    monkeypatch.setattr(
        task_runs_module,
        "_persist_scope_metrics_under_current_lock",
        lambda *args, **kwargs: False,
    )
    original_merge = task_runs_module._scope_metrics_with_decision
    concurrent_write_done = False

    with DbSession(engine) as concurrent_db, DbSession(engine) as writer_db:
        def write_between_fallback_refresh_and_cas(
            metrics,
            persisted_decision,
            decision_evidence,
            *,
            binding,
        ):
            nonlocal concurrent_write_done
            merged = original_merge(
                metrics,
                persisted_decision,
                decision_evidence,
                binding=binding,
            )
            if persisted_decision.status == "unverifiable" and not concurrent_write_done:
                concurrent_run = concurrent_db.get(TaskRun, run_id)
                concurrent_metrics = json.loads(concurrent_run.metrics_json)
                concurrent_metrics["concurrentAfterFallbackRefresh"] = {
                    "preserved": True
                }
                concurrent_run.metrics_json = json.dumps(
                    concurrent_metrics,
                    separators=(",", ":"),
                )
                concurrent_db.add(concurrent_run)
                concurrent_db.commit()
                concurrent_write_done = True
            return merged

        monkeypatch.setattr(
            task_runs_module,
            "_scope_metrics_with_decision",
            write_between_fallback_refresh_and_cas,
        )
        stored = task_runs_module.persist_scope_decision(
            writer_db,
            writer_db.get(TaskRun, run_id),
            decision,
        )
        metrics = json.loads(stored.metrics_json)

    assert concurrent_write_done is True
    assert metrics["concurrentAfterFallbackRefresh"] == {"preserved": True}
    assert metrics["taskRunScopeDecision"]["status"] == "unverifiable"
    assert "taskRunScopeGuard" not in metrics


def test_require_scope_passed_rejects_same_target_policy_mutation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = task_run_scope.ScopeDecision(
        status="passed",
        error_code=None,
        target_id=DEMO_FRONTEND_TARGET_ID,
        changed_paths=(),
        rejected_paths=(),
        reason=None,
    )
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        baseline = task_runs_module.capture_task_run_scope_baseline(db, run.id)
        task_runs_module.persist_scope_decision(db, baseline, decision)

        session = db.get(Session, task.session_id)
        original_target = task_runs_module.get_target_for_workspace(
            db,
            session.workspace_id,
            DEMO_FRONTEND_TARGET_ID,
        )
        widened_target = replace(
            original_target,
            allowed_paths=(*original_target.allowed_paths, "package.json"),
        )
        monkeypatch.setattr(
            task_runs_module,
            "get_target_for_workspace",
            lambda db, workspace_id, target_id: widened_target,
        )

        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            task_runs_module.require_task_run_scope_passed(db, run.id)

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


def test_scope_decision_timestamp_is_recorded_after_post_validation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = task_run_scope.ScopeDecision(
        status="passed",
        error_code=None,
        target_id=DEMO_FRONTEND_TARGET_ID,
        changed_paths=(),
        rejected_paths=(),
        reason=None,
    )
    events: list[str] = []
    capture_count = 0
    timestamp_count = 0

    def capture(worktree_path, **kwargs):
        nonlocal capture_count
        capture_count += 1
        events.append(f"capture:{capture_count}")
        return _scope_snapshot()

    def timestamp() -> str:
        nonlocal timestamp_count
        timestamp_count += 1
        events.append(f"timestamp:{timestamp_count}")
        return f"2026-07-16T00:00:0{timestamp_count}+00:00"

    monkeypatch.setattr(task_runs_module, "capture_worktree_scope_snapshot", capture)
    monkeypatch.setattr(task_runs_module, "_utc_scope_timestamp", timestamp)

    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        baseline = task_runs_module.capture_task_run_scope_baseline(db, run.id)
        stored = task_runs_module.persist_scope_decision(db, baseline, decision)
        marker = json.loads(stored.metrics_json)["taskRunScopeGuard"]

    assert events == ["capture:1", "timestamp:1", "capture:2", "timestamp:2"]
    assert marker["timestamp"] == "2026-07-16T00:00:02+00:00"


@pytest.mark.parametrize("post_mode", ("unavailable", "decision_mismatch"))
def test_persist_passed_scope_decision_requires_matching_post_validation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    post_mode: str,
) -> None:
    decision = task_run_scope.ScopeDecision(
        status="passed",
        error_code=None,
        target_id=DEMO_FRONTEND_TARGET_ID,
        changed_paths=("apps/demo/src/App.tsx",),
        rejected_paths=(),
        reason=None,
    )
    baseline_snapshot = _scope_snapshot()
    if post_mode == "unavailable":
        post_snapshot = task_run_scope.ScopeSnapshot(
            schema_version=task_run_scope.SCOPE_SNAPSHOT_SCHEMA_VERSION,
            available=False,
            reason="scope_capture_unavailable",
            entries=(),
            protected_control_digest=None,
        )
    else:
        post_snapshot = _scope_snapshot()
    capture_calls = 0

    def capture(worktree_path, **kwargs):
        nonlocal capture_calls
        capture_calls += 1
        return baseline_snapshot if capture_calls == 1 else post_snapshot

    monkeypatch.setattr(task_runs_module, "capture_worktree_scope_snapshot", capture)
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        baseline = task_runs_module.capture_task_run_scope_baseline(db, run.id)
        stored = task_runs_module.persist_scope_decision(db, baseline, decision)
        metrics = json.loads(stored.metrics_json)

    assert capture_calls == 2
    assert "taskRunScopeGuard" not in metrics
    assert metrics["taskRunScopeDecision"]["status"] == "unverifiable"
    assert metrics["taskRunScopeDecision"]["errorCode"] == (
        "TASK_RUN_SCOPE_UNVERIFIABLE"
    )


def test_persist_forged_rejected_scope_decision_is_unverifiable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = task_run_scope.ScopeDecision(
        status="rejected",
        error_code="TASK_RUN_SCOPE_VIOLATION",
        target_id=DEMO_FRONTEND_TARGET_ID,
        changed_paths=("package.json",),
        rejected_paths=("package.json",),
        reason="unsafe path",
    )
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        baseline = task_runs_module.capture_task_run_scope_baseline(db, run.id)
        stored = task_runs_module.persist_scope_decision(db, baseline, decision)
        metrics = json.loads(stored.metrics_json)

        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            task_runs_module.require_task_run_scope_passed(db, run.id)

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert "taskRunScopeGuard" not in metrics
    assert metrics["taskRunScopeDecision"]["status"] == "unverifiable"
    assert metrics["taskRunScopeDecision"]["errorCode"] == (
        "TASK_RUN_SCOPE_UNVERIFIABLE"
    )


def test_persist_real_out_of_scope_delta_preserves_violation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline_snapshot = _scope_snapshot()
    current_snapshot = _scope_snapshot(
        entries=(
            task_run_scope.ScopeEntry(
                path="package.json",
                status="tracked-present",
                fingerprint="b" * 64,
            ),
        )
    )
    capture_calls = 0

    def capture(worktree_path, **kwargs):
        nonlocal capture_calls
        capture_calls += 1
        return baseline_snapshot if capture_calls == 1 else current_snapshot

    monkeypatch.setattr(task_runs_module, "capture_worktree_scope_snapshot", capture)
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        baseline = task_runs_module.capture_task_run_scope_baseline(db, run.id)
        decision = task_runs_module.validate_task_run_scope(db, run.id)
        stored = task_runs_module.persist_scope_decision(db, baseline, decision)
        evidence = json.loads(stored.metrics_json)["taskRunScopeDecision"]

        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            task_runs_module.require_task_run_scope_passed(db, run.id)

    assert decision.status == "rejected"
    assert decision.error_code == "TASK_RUN_SCOPE_VIOLATION"
    assert decision.rejected_paths == ("package.json",)
    assert evidence["status"] == "rejected"
    assert evidence["errorCode"] == "TASK_RUN_SCOPE_VIOLATION"
    assert exc_info.value.error_code == "TASK_RUN_SCOPE_VIOLATION"


def test_persist_rejected_scope_decision_without_binding_is_unverifiable(
    client: TestClient,
) -> None:
    decision = task_run_scope.ScopeDecision(
        status="rejected",
        error_code="TASK_RUN_SCOPE_VIOLATION",
        target_id=DEMO_FRONTEND_TARGET_ID,
        changed_paths=("package.json",),
        rejected_paths=("package.json",),
        reason="The task run changed paths outside the assigned target.",
    )
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)

        stored = task_runs_module.persist_scope_decision(db, run, decision)
        evidence = json.loads(stored.metrics_json)["taskRunScopeDecision"]

    assert evidence["status"] == "unverifiable"
    assert evidence["errorCode"] == "TASK_RUN_SCOPE_UNVERIFIABLE"


def test_require_scope_passed_rejects_unverifiable_decision_with_safe_code(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = task_run_scope.ScopeDecision(
        status="unverifiable",
        error_code="TASK_RUN_SCOPE_UNVERIFIABLE",
        target_id=DEMO_FRONTEND_TARGET_ID,
        changed_paths=(),
        rejected_paths=(),
        reason="snapshot unavailable",
    )
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        baseline = task_runs_module.capture_task_run_scope_baseline(db, run.id)
        stored = task_runs_module.persist_scope_decision(db, baseline, decision)
        metrics = json.loads(stored.metrics_json)

        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            task_runs_module.require_task_run_scope_passed(db, run.id)

    assert "taskRunScopeGuard" not in metrics
    assert metrics["taskRunScopeDecision"]["status"] == "unverifiable"
    assert metrics["taskRunScopeDecision"]["reason"] == (
        "The task run scope evidence is unavailable or invalid."
    )
    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


def test_require_scope_passed_fails_closed_when_marker_target_differs_from_task(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = task_run_scope.ScopeDecision(
        status="passed",
        error_code=None,
        target_id=DEMO_FRONTEND_TARGET_ID,
        changed_paths=(),
        rejected_paths=(),
        reason=None,
    )
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        baseline = task_runs_module.capture_task_run_scope_baseline(db, run.id)
        task_runs_module.persist_scope_decision(db, baseline, decision)
        task.plan_json = json.dumps({"targetId": DEMO_BACKEND_TARGET_ID})
        db.add(task)
        db.commit()

        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            task_runs_module.require_task_run_scope_passed(db, run.id)

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


def test_require_scope_passed_rejects_same_target_rebound_to_other_workspace(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = task_run_scope.ScopeDecision(
        status="passed",
        error_code=None,
        target_id=DEMO_FRONTEND_TARGET_ID,
        changed_paths=(),
        rejected_paths=(),
        reason=None,
    )
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        baseline = task_runs_module.capture_task_run_scope_baseline(db, run.id)
        task_runs_module.persist_scope_decision(db, baseline, decision)

        other_workspace = Workspace(
            name="Other workspace",
            repo_url="local://apps/demo",
            root_path="apps/demo",
            default_branch="main",
        )
        other_session = Session(
            workspace_id=other_workspace.id,
            title="Other workspace session",
            bound_branch="main",
            worktree_path=".worktrees/other-workspace-session",
        )
        db.add(other_workspace)
        db.add(other_session)
        db.commit()
        task.session_id = other_session.id
        db.add(task)
        db.commit()

        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            task_runs_module.require_task_run_scope_passed(db, run.id)

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


def test_require_scope_passed_fails_closed_for_malformed_marker(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = task_run_scope.ScopeDecision(
        status="passed",
        error_code=None,
        target_id=DEMO_FRONTEND_TARGET_ID,
        changed_paths=(),
        rejected_paths=(),
        reason=None,
    )
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        baseline = task_runs_module.capture_task_run_scope_baseline(db, run.id)
        stored = task_runs_module.persist_scope_decision(db, baseline, decision)
        metrics = json.loads(stored.metrics_json)
        metrics["taskRunScopeGuard"]["changedPaths"] = ["apps/demo/src/App.tsx"]
        stored.metrics_json = json.dumps(metrics, separators=(",", ":"))
        db.add(stored)
        db.commit()

        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            task_runs_module.require_task_run_scope_passed(db, stored.id)

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


def test_require_scope_passed_fails_closed_when_marker_run_id_is_forged(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = task_run_scope.ScopeDecision(
        status="passed",
        error_code=None,
        target_id=DEMO_FRONTEND_TARGET_ID,
        changed_paths=(),
        rejected_paths=(),
        reason=None,
    )
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        baseline = task_runs_module.capture_task_run_scope_baseline(db, run.id)
        stored = task_runs_module.persist_scope_decision(db, baseline, decision)
        metrics = json.loads(stored.metrics_json)
        metrics["taskRunScopeGuard"]["taskRunId"] = "other-task-run"
        stored.metrics_json = json.dumps(metrics, separators=(",", ":"))
        db.add(stored)
        db.commit()

        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            task_runs_module.require_task_run_scope_passed(db, run.id)

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("baselineCapturedAt", "2000-01-01T00:00:00+00:00"),
        ("timestamp", "2000-01-01T01:00:00+01:00"),
        ("baselineSchemaVersion", "agenthub.task_run_scope.v999"),
        ("baselineIdentity", "forged-baseline"),
        ("executionAttemptId", "forged-attempt"),
        ("workspaceId", "forged-workspace"),
        ("scopePolicySchemaVersion", "agenthub.effective_write_scope.v999"),
        ("scopePolicyIdentity", "f" * 64),
    ),
)
def test_require_scope_passed_fails_closed_for_forged_marker_time_or_baseline(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
) -> None:
    decision = task_run_scope.ScopeDecision(
        status="passed",
        error_code=None,
        target_id=DEMO_FRONTEND_TARGET_ID,
        changed_paths=(),
        rejected_paths=(),
        reason=None,
    )
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        baseline = task_runs_module.capture_task_run_scope_baseline(db, run.id)
        stored = task_runs_module.persist_scope_decision(db, baseline, decision)
        metrics = json.loads(stored.metrics_json)
        metrics["taskRunScopeGuard"][field] = value
        stored.metrics_json = json.dumps(metrics, separators=(",", ":"))
        db.add(stored)
        db.commit()

        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            task_runs_module.require_task_run_scope_passed(db, run.id)

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


def test_require_scope_passed_rejects_marker_replayed_after_new_baseline(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = task_run_scope.ScopeDecision(
        status="passed",
        error_code=None,
        target_id=DEMO_FRONTEND_TARGET_ID,
        changed_paths=(),
        rejected_paths=(),
        reason=None,
    )
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        first_baseline = task_runs_module.capture_task_run_scope_baseline(db, run.id)
        first_stored = task_runs_module.persist_scope_decision(
            db, first_baseline, decision
        )
        first_marker = json.loads(first_stored.metrics_json)["taskRunScopeGuard"]

        second_baseline = task_runs_module.capture_task_run_scope_baseline(db, run.id)
        metrics = json.loads(second_baseline.metrics_json)
        assert metrics["preRunCheckpoint"]["scopeBaselineIdentity"] != first_marker[
            "baselineIdentity"
        ]
        assert metrics["preRunCheckpoint"]["scopeExecutionAttemptId"] != first_marker[
            "executionAttemptId"
        ]
        metrics["taskRunScopeGuard"] = first_marker
        second_baseline.metrics_json = json.dumps(metrics, separators=(",", ":"))
        db.add(second_baseline)
        db.commit()

        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            task_runs_module.require_task_run_scope_passed(db, run.id)

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


def test_create_task_run_persists_queued_state_before_event(client: TestClient) -> None:
    response = client.post(f"/tasks/{task_id()}/runs")

    assert response.status_code == 201
    run = response.json()
    assert run["state"] == "queued"
    assert run["adapterType"] == "codex"
    assert run["worktreePath"] == ".worktrees/taskrun-session"

    with db_from_override() as db:
        stored = db.get(TaskRun, run["id"])
        event = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == run["id"])
            .where(TaskRunEvent.event_type == "task.state")
        ).one()
        task = db.get(Task, stored.task_id)

        assert stored.state == "queued"
        assert task.status == "running"
        assert event.sequence == 1
        assert event.event_type == "task.state"
        assert json.loads(event.payload_json)["state"] == "queued"


def test_create_task_run_records_runner_heartbeat_and_lease(client: TestClient) -> None:
    with db_from_override() as db:
        stored = create_task_run(db, task_id())
        run = task_run_response(db, stored).model_dump(by_alias=True)

        assert run["runnerId"].startswith("local:")
        assert run["lastHeartbeatAt"] is not None
        assert run["leaseExpiresAt"] is not None
        assert run["staleDetectedAt"] is None
        assert run["staleReason"] is None
        assert stored.runner_id == run["runnerId"]
        assert stored.last_heartbeat_at is not None
        assert stored.lease_expires_at is not None
        assert stored.lease_expires_at > stored.last_heartbeat_at


def test_create_task_run_records_memory_snapshot_consistently(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        session = db.exec(select(Session).where(Session.title == "TaskRun session")).one()
        assert session.memory_snapshot_id is None

        task_run = create_task_run(db, task_id())
        db.refresh(session)
        run = task_run_response(db, task_run).model_dump(by_alias=True)
        context_pack = build_session_context_pack(
            db,
            db.get(Task, task_run.task_id),
        )

        assert session.memory_snapshot_id
        assert run["memorySnapshot"]["memorySnapshotId"] == session.memory_snapshot_id
        assert (
            context_pack["memorySnapshot"]["memorySnapshotId"]
            == session.memory_snapshot_id
        )
        assert (
            context_pack["canonicalContext"]["fields"]["memorySnapshot"]["value"][
                "memorySnapshotId"
            ]
            == session.memory_snapshot_id
        )


def test_memory_snapshot_refresh_is_explicit_and_blocks_active_runs(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        session = db.exec(select(Session).where(Session.title == "TaskRun session")).one()
        first = refresh_session_memory_snapshot(db, session.id)
        assert first.id == session.memory_snapshot_id

        task_run = create_task_run(db, task_id())
        blocked = client.post(f"/sessions/{session.id}/memory-snapshot/refresh")
        assert blocked.status_code == 409
        assert task_run.id in blocked.json()["detail"]

        transition_task_run(db, task_run.id, "completed")
        refreshed = client.post(f"/sessions/{session.id}/memory-snapshot/refresh")
        assert refreshed.status_code == 200
        second_snapshot_id = refreshed.json()["memorySnapshotId"]

        assert second_snapshot_id
        assert second_snapshot_id != first.id

        stored_run = db.get(TaskRun, task_run.id)
        metrics = json.loads(stored_run.metrics_json)
        assert metrics["memorySnapshot"]["memorySnapshotId"] == first.id


def test_refresh_task_run_heartbeat_extends_active_lease(client: TestClient) -> None:
    with db_from_override() as db:
        task_run = create_task_run(db, task_id())
        original_heartbeat = task_run.last_heartbeat_at
        original_lease = task_run.lease_expires_at

        refreshed = refresh_task_run_heartbeat(
            db,
            task_run.id,
            runner_id=task_run.runner_id,
            lease_seconds=900,
        )

        assert refreshed.last_heartbeat_at >= original_heartbeat
        assert refreshed.lease_expires_at > original_lease

        event = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == task_run.id)
            .where(TaskRunEvent.event_type == "task.heartbeat")
        ).one()
        payload = json.loads(event.payload_json)

        assert payload["runnerId"] == task_run.runner_id
        assert payload["leaseExpiresAt"] is not None


def test_claim_task_run_for_worker_records_claim_and_lease(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        task_run = create_task_run(db, task_id())
        original_runner_id = task_run.runner_id

        claimed = claim_task_run_for_worker(
            db,
            task_run.id,
            worker_id="worker:test",
            lease_seconds=120,
        )

        assert claimed.state == "queued"
        assert claimed.runner_id == "worker:test"
        assert claimed.runner_id != original_runner_id
        assert claimed.last_heartbeat_at is not None
        assert claimed.lease_expires_at > claimed.last_heartbeat_at

        event = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == task_run.id)
            .where(TaskRunEvent.event_type == "run.claimed")
        ).one()
        payload = json.loads(event.payload_json)

        assert payload["workerId"] == "worker:test"
        assert payload["runnerId"] == "worker:test"
        assert payload["leaseExpiresAt"] is not None


def test_claim_task_run_for_worker_rejects_terminal_run(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        task_run = create_task_run(db, task_id())
        transition_task_run(db, task_run.id, "completed")

        with pytest.raises(TaskRunLifecycleError, match="Only queued"):
            claim_task_run_for_worker(
                db,
                task_run.id,
                worker_id="worker:test",
            )


def test_mark_stale_task_runs_marks_expired_active_run_honestly(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        task_run = create_task_run(db, task_id())
        task_run.lease_expires_at = utc_now() - timedelta(minutes=1)
        db.add(task_run)
        db.commit()

        stale_runs = mark_stale_task_runs(db, reason="lease_expired_for_test")

        assert [run.id for run in stale_runs] == [task_run.id]

        stored = db.get(TaskRun, task_run.id)
        task = db.get(Task, stored.task_id)
        stale_event = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == task_run.id)
            .where(TaskRunEvent.event_type == "task.stale")
        ).one()
        payload = json.loads(stale_event.payload_json)

        assert stored.state == "failed"
        assert stored.error_code == "TASK_RUN_STALE"
        assert stored.stale_detected_at is not None
        assert stored.stale_reason == "lease_expired_for_test"
        assert stored.ended_at is not None
        assert task.status == "failed"
        assert payload["runnerId"] == task_run.runner_id
        assert payload["reason"] == "lease_expired_for_test"
        assert "success" not in payload


def test_collecting_diff_stale_recovery_fails_closed_for_missing_control_digest(
    client: TestClient,
) -> None:
    raw_fingerprint = "f" * 64
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        task_run = create_task_run(db, task.id)
        _acquire_scope_lock(db, task_run)
        transition_task_run(db, task_run.id, "collecting_diff")
        metrics = json.loads(task_run.metrics_json)
        metrics["preRunCheckpoint"].update(
            {
                "targetId": DEMO_FRONTEND_TARGET_ID,
                "scopeBaseline": {
                    "schema_version": task_run_scope.SCOPE_SNAPSHOT_SCHEMA_VERSION,
                    "available": True,
                    "reason": None,
                    "entries": [
                        {
                            "path": "apps/demo/src/App.tsx",
                            "status": "tracked-present",
                            "fingerprint": raw_fingerprint,
                        }
                    ],
                    "protected_categories": [".git"],
                    "protected_entry_count": 1,
                },
                "collectorHostPath": "Z:\\private-host\\scope-fixture\\.git\\private",
                "secretValue": "sk-crash-secret",
            }
        )
        task_run.metrics_json = json.dumps(metrics, separators=(",", ":"))
        task_run.lease_expires_at = utc_now() - timedelta(minutes=1)
        db.add(task_run)
        db.commit()
        task_run_id = task_run.id

        stale_runs = mark_stale_task_runs(
            db,
            reason="worker_crash_recovery_test",
        )

        stored = db.get(TaskRun, task_run_id)
        artifacts = db.exec(
            select(Artifact).where(Artifact.task_run_id == task_run_id)
        ).all()
        events = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == task_run_id)
            .order_by(TaskRunEvent.sequence)
        ).all()
        diagnostics = build_task_run_diagnostics(db, stored)

    assert [run.id for run in stale_runs] == [task_run_id]
    assert stored.state == "failed"
    assert stored.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert artifacts == []
    scope_events = [
        event
        for event in events
        if event.event_type == "task.scope_validation.failed"
    ]
    assert len(scope_events) == 1
    payload = json.loads(scope_events[0].payload_json)
    assert payload == {
        "result": "unverifiable",
        "errorCode": "TASK_RUN_SCOPE_UNVERIFIABLE",
        "taskRunId": task_run_id,
        "snapshotVersion": task_run_scope.SCOPE_SNAPSHOT_SCHEMA_VERSION,
        "protectedEntryCount": 1,
        "protectedCategories": [".git"],
        "reasonCategory": "crash_recovery",
    }
    exposed = " ".join(event.payload_json for event in events)
    assert "Z:\\" not in exposed
    assert "sk-crash-secret" not in exposed
    assert raw_fingerprint not in exposed
    assert "protected_control_digest" not in exposed
    assert diagnostics.primary_failure is not None
    assert diagnostics.primary_failure.category == "validation_failed"
    assert any(
        item.phase == "validation" and item.status == "failed"
        for item in diagnostics.timeline
    )


def test_collecting_diff_stale_recovery_keeps_stale_code_for_valid_scope_pass(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = task_run_scope.ScopeDecision(
        status="passed",
        error_code=None,
        target_id=DEMO_FRONTEND_TARGET_ID,
        changed_paths=(),
        rejected_paths=(),
        reason=None,
    )
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        task_run = create_task_run(db, task.id)
        _acquire_scope_lock(db, task_run)
        task_run = task_runs_module.capture_task_run_scope_baseline(
            db,
            task_run.id,
        )
        task_run = _bind_started_write_execution(db, task_run)
        transition_task_run(db, task_run.id, "collecting_diff")
        task_run = task_runs_module.persist_scope_decision(
            db,
            task_run,
            decision,
        )
        assert "taskRunScopeGuard" in json.loads(task_run.metrics_json)
        task_run.lease_expires_at = utc_now() - timedelta(minutes=1)
        db.add(task_run)
        db.commit()

        mark_stale_task_runs(db, reason="passed_scope_stale_test")

        stored = db.get(TaskRun, task_run.id)
        scope_failures = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == task_run.id)
            .where(TaskRunEvent.event_type == "task.scope_validation.failed")
        ).all()

    assert stored.state == "failed"
    assert stored.error_code == "TASK_RUN_STALE"
    assert scope_failures == []


def test_collecting_diff_stale_recovery_preserves_persisted_scope_violation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rejected_path = "apps/demo/package.json"
    raw_fingerprint = "c" * 64
    raw_control_digest = "a" * 64
    baseline_snapshot = _scope_snapshot()
    current_snapshot = _scope_snapshot(
        entries=(
            task_run_scope.ScopeEntry(
                path=rejected_path,
                status="tracked-present",
                fingerprint=raw_fingerprint,
            ),
        )
    )
    capture_calls = 0

    def capture(worktree_path, **kwargs):
        nonlocal capture_calls
        capture_calls += 1
        return baseline_snapshot if capture_calls == 1 else current_snapshot

    monkeypatch.setattr(task_runs_module, "capture_worktree_scope_snapshot", capture)
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        task_run = create_task_run(db, task.id)
        _acquire_scope_lock(db, task_run)
        task_run = task_runs_module.capture_task_run_scope_baseline(
            db,
            task_run.id,
        )
        task_run = _bind_started_write_execution(db, task_run)
        transition_task_run(db, task_run.id, "collecting_diff")
        decision = task_runs_module.validate_task_run_scope(db, task_run.id)
        assert decision.status == "rejected"
        task_run = task_runs_module.persist_scope_decision(
            db,
            task_run,
            decision,
        )
        assert json.loads(task_run.metrics_json)["taskRunScopeDecision"][
            "status"
        ] == "rejected"
        task_run.lease_expires_at = utc_now() - timedelta(minutes=1)
        db.add(task_run)
        db.commit()

        mark_stale_task_runs(db, reason="violation_recovery_test")

        stored = db.get(TaskRun, task_run.id)
        artifacts = db.exec(
            select(Artifact).where(Artifact.task_run_id == task_run.id)
        ).all()
        events = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == task_run.id)
            .order_by(TaskRunEvent.sequence)
        ).all()
        diagnostics = build_task_run_diagnostics(db, stored)

    assert stored.state == "failed"
    assert stored.error_code == "TASK_RUN_SCOPE_VIOLATION"
    assert artifacts == []
    scope_event = next(
        event
        for event in events
        if event.event_type == "task.scope_validation.failed"
    )
    payload = json.loads(scope_event.payload_json)
    assert payload["result"] == "violation"
    assert payload["errorCode"] == "TASK_RUN_SCOPE_VIOLATION"
    assert payload["reasonCategory"] == "crash_recovery"
    exposed = " ".join(event.payload_json for event in events)
    assert rejected_path not in exposed
    assert raw_fingerprint not in exposed
    assert raw_control_digest not in exposed
    assert diagnostics.primary_failure is not None
    assert diagnostics.primary_failure.category == "validation_failed"


@pytest.mark.parametrize(
    ("mismatched_field", "mismatched_value"),
    (
        ("taskRunId", "other-task-run"),
        ("baselineIdentity", "other-baseline"),
        ("targetId", DEMO_BACKEND_TARGET_ID),
        ("workspaceId", "other-workspace"),
        ("scopePolicySchemaVersion", "agenthub.effective_write_scope.v999"),
        ("scopePolicyIdentity", "f" * 64),
    ),
)
def test_collecting_diff_stale_recovery_rejects_unbound_violation_evidence(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    mismatched_field: str,
    mismatched_value: str,
) -> None:
    rejected_path = "apps/demo/package.json"
    baseline_snapshot = _scope_snapshot()
    current_snapshot = _scope_snapshot(
        entries=(
            task_run_scope.ScopeEntry(
                path=rejected_path,
                status="tracked-present",
                fingerprint="d" * 64,
            ),
        )
    )
    capture_calls = 0

    def capture(worktree_path, **kwargs):
        nonlocal capture_calls
        capture_calls += 1
        return baseline_snapshot if capture_calls == 1 else current_snapshot

    monkeypatch.setattr(task_runs_module, "capture_worktree_scope_snapshot", capture)
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        task_run = create_task_run(db, task.id)
        _acquire_scope_lock(db, task_run)
        task_run = task_runs_module.capture_task_run_scope_baseline(
            db,
            task_run.id,
        )
        transition_task_run(db, task_run.id, "collecting_diff")
        decision = task_runs_module.validate_task_run_scope(db, task_run.id)
        assert decision.status == "rejected"
        task_run = task_runs_module.persist_scope_decision(
            db,
            task_run,
            decision,
        )
        metrics = json.loads(task_run.metrics_json)
        metrics["taskRunScopeDecision"][mismatched_field] = mismatched_value
        task_run.metrics_json = json.dumps(metrics, separators=(",", ":"))
        task_run.lease_expires_at = utc_now() - timedelta(minutes=1)
        db.add(task_run)
        db.commit()

        mark_stale_task_runs(db, reason="unbound_violation_recovery_test")

        stored = db.get(TaskRun, task_run.id)
        events = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == task_run.id)
            .where(TaskRunEvent.event_type == "task.scope_validation.failed")
        ).all()

    assert stored.state == "failed"
    assert stored.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert len(events) == 1
    assert json.loads(events[0].payload_json)["errorCode"] == (
        "TASK_RUN_SCOPE_UNVERIFIABLE"
    )


@pytest.mark.parametrize(
    ("scope_case", "run_state", "expected_error_code"),
    (
        ("missing", "collecting_diff", "TASK_RUN_SCOPE_UNVERIFIABLE"),
        ("rejected", "collecting_diff", "TASK_RUN_SCOPE_VIOLATION"),
        ("passed", "collecting_diff", "TASK_RUN_STALE"),
        ("ordinary", "streaming", "TASK_RUN_STALE"),
        ("missing-task", "collecting_diff", "TASK_RUN_SCOPE_UNVERIFIABLE"),
        (
            "reclassified-readonly",
            "collecting_diff",
            "TASK_RUN_SCOPE_UNVERIFIABLE",
        ),
    ),
    ids=(
        "missing-evidence",
        "rejected-evidence",
        "passed-evidence",
        "ordinary-streaming",
        "missing-task",
        "reclassified-readonly",
    ),
)
def test_target_lock_recovery_preserves_collecting_diff_scope_classification(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    scope_case: str,
    run_state: str,
    expected_error_code: str,
) -> None:
    boundary = utc_now()
    rejected_path = "apps/demo/package.json"
    baseline_snapshot = _scope_snapshot()
    current_snapshot = (
        _scope_snapshot(
            entries=(
                task_run_scope.ScopeEntry(
                    path=rejected_path,
                    status="tracked-present",
                    fingerprint="d" * 64,
                ),
            )
        )
        if scope_case == "rejected"
        else baseline_snapshot
    )
    capture_calls = 0

    def capture(worktree_path, **kwargs):
        nonlocal capture_calls
        capture_calls += 1
        return baseline_snapshot if capture_calls == 1 else current_snapshot

    monkeypatch.setattr(task_runs_module, "capture_worktree_scope_snapshot", capture)
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        task_run = create_task_run(db, task.id)
        _acquire_scope_lock(db, task_run)
        if scope_case in {"passed", "rejected"}:
            task_run = task_runs_module.capture_task_run_scope_baseline(
                db,
                task_run.id,
            )
            task_run = _bind_started_write_execution(db, task_run)
        task_run = transition_task_run(db, task_run.id, run_state)
        if scope_case in {"passed", "rejected"}:
            decision = task_runs_module.validate_task_run_scope(db, task_run.id)
            assert decision.status == scope_case
            task_run = task_runs_module.persist_scope_decision(
                db,
                task_run,
                decision,
            )

        held_lock = held_lock_for_target(db, DEMO_FRONTEND_TARGET_ID)
        assert held_lock is not None
        assert held_lock.mode == "write"
        lock_id = held_lock.id
        task_run_id = task_run.id
        expired_at = boundary - timedelta(seconds=1)
        task_run.last_heartbeat_at = expired_at
        task_run.lease_expires_at = expired_at
        held_lock.lease_expires_at = expired_at
        queue_entry = entry_for_task_run(db, task_run_id)
        assert queue_entry is not None
        queue_entry.state = "running"
        if scope_case == "missing-task":
            db.delete(task)
        else:
            task.status = "running"
            if scope_case == "reclassified-readonly":
                task.plan_json = json.dumps(
                    {
                        "targetId": DEMO_FRONTEND_TARGET_ID,
                        "readOnly": True,
                    }
                )
            db.add(task)
        db.add(task_run)
        db.add(held_lock)
        db.add(queue_entry)
        db.commit()

        recovered = target_locks_module.recover_stale_target_locks(
            db,
            now=boundary,
        )

        stored_run = db.get(TaskRun, task_run_id)
        stored_lock = db.get(TargetLock, lock_id)
        stored_queue = entry_for_task_run(db, task_run_id)
        artifacts = db.exec(
            select(Artifact).where(Artifact.task_run_id == task_run_id)
        ).all()
        recovery_events = [
            event
            for event in db.exec(
                select(TaskRunEvent)
                .where(TaskRunEvent.task_run_id == task_run_id)
                .order_by(TaskRunEvent.sequence)
            ).all()
            if event.event_type
            in {
                "target_lock.stale_released",
                "task.scope_validation.failed",
                "task.stale",
                "session_queue.advanced",
            }
        ]

    assert len(recovered) == 1
    assert stored_run.state == "failed"
    assert stored_run.error_code == expected_error_code
    assert stored_lock.state == "stale_released"
    assert stored_queue.state == "failed"
    assert artifacts == []
    scope_events = [
        event
        for event in recovery_events
        if event.event_type == "task.scope_validation.failed"
    ]
    if expected_error_code.startswith("TASK_RUN_SCOPE_"):
        assert len(scope_events) == 1
        scope_payload = json.loads(scope_events[0].payload_json)
        assert scope_payload["errorCode"] == expected_error_code
        assert scope_payload["reasonCategory"] == "crash_recovery"
        assert rejected_path not in scope_events[0].payload_json
    else:
        assert scope_events == []
    expected_event_types = ["target_lock.stale_released"]
    if expected_error_code.startswith("TASK_RUN_SCOPE_"):
        expected_event_types.append("task.scope_validation.failed")
    expected_event_types.extend(["task.stale", "session_queue.advanced"])
    assert [event.event_type for event in recovery_events] == expected_event_types
    event_sequences = [event.sequence for event in recovery_events]
    assert event_sequences == list(
        range(event_sequences[0], event_sequences[0] + len(event_sequences))
    )
    assert all(lock_id not in event.payload_json for event in recovery_events)


def test_mark_stale_task_runs_ignores_unexpired_active_run(client: TestClient) -> None:
    with db_from_override() as db:
        task_run = create_task_run(db, task_id())

        stale_runs = mark_stale_task_runs(db)

        assert stale_runs == []

        stored = db.get(TaskRun, task_run.id)
        assert stored.state == "queued"
        assert stored.stale_detected_at is None
        assert stored.stale_reason is None


def test_checkpoint_created_event_uses_safe_public_projection(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    windows_host = r"C:\private-host\checkpoint-secret.txt"
    posix_host = "/private-host/checkpoint-secret.txt"
    secret = "sk-checkpoint-sentinel"
    forged_checkpoint = {
        "targetId": posix_host,
        "targetRoot": windows_host,
        "allowedPaths": ["src", posix_host],
        "deniedPaths": [".env*", "../denied-event-sentinel"],
        "baseCommit": windows_host,
        "gitStatus": {
            "available": False,
            "reason": f"{secret} at {posix_host}",
            "dirtyFiles": ["../git-event-sentinel"],
        },
        "dirtyFiles": ["src/App.tsx", windows_host],
        "plannedFiles": ["src/App.tsx", "src/\0nul-event-sentinel"],
        "contractId": secret,
        "contractHash": windows_host,
        "createdAt": posix_host,
        "scopeBaseline": {
            "schema_version": task_run_scope.SCOPE_SNAPSHOT_SCHEMA_VERSION,
            "available": False,
            "reason": f"{secret} at {windows_host}",
            "entries": [],
            "protected_control_digest": None,
            "protected_categories": [],
            "protected_entry_count": 0,
        },
    }
    monkeypatch.setattr(
        task_runs_module,
        "_pre_run_checkpoint_for_task",
        lambda *args, **kwargs: forged_checkpoint,
    )

    with db_from_override() as db:
        run = create_task_run(db, task_id())
        internal_checkpoint = json.loads(run.metrics_json)["preRunCheckpoint"]
        event = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == run.id)
            .where(TaskRunEvent.event_type == "task.checkpoint.created")
        ).one()
        event_checkpoint = json.loads(event.payload_json)["checkpoint"]

    assert internal_checkpoint == forged_checkpoint
    internal_json = json.dumps(internal_checkpoint, sort_keys=True)
    assert secret in internal_json
    assert "private-host" in internal_json
    assert "nul-event-sentinel" in internal_json

    event_json = json.dumps(event_checkpoint, sort_keys=True)
    for sentinel in (
        "private-host",
        secret,
        "denied-event-sentinel",
        "git-event-sentinel",
        "nul-event-sentinel",
    ):
        assert sentinel not in event_json
    assert event_checkpoint == {
        "scopeBaseline": {
            "schema_version": task_run_scope.SCOPE_SNAPSHOT_SCHEMA_VERSION,
            "available": False,
            "reason": "scope_snapshot_unavailable",
            "protected_categories": [],
            "protected_entry_count": 0,
        }
    }


def test_write_task_run_records_pre_run_checkpoint_for_demo_target(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        contract = {"contractId": "contract-demo-dashboard", "version": 1}
        task.plan_json = json.dumps(
            {
                "targetId": DEMO_FRONTEND_TARGET_ID,
                "safeTarget": "apps/demo/src",
                "files": ["apps/demo/src/App.tsx"],
                "contractId": contract["contractId"],
                "appContract": contract,
            },
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()

        task_run = create_task_run(db, task.id)

        checkpoint = json.loads(task_run.metrics_json)["preRunCheckpoint"]
        event = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == task_run.id)
            .where(TaskRunEvent.event_type == "task.checkpoint.created")
        ).one()
        payload = json.loads(event.payload_json)

        assert checkpoint["targetId"] == DEMO_FRONTEND_TARGET_ID
        assert checkpoint["targetRoot"] == "apps/demo"
        assert checkpoint["allowedPaths"] == ["apps/demo/src"]
        assert "node_modules" in checkpoint["deniedPaths"]
        assert checkpoint["plannedFiles"] == ["apps/demo/src/App.tsx"]
        assert checkpoint["contractId"] == "contract-demo-dashboard"
        assert checkpoint["contractHash"] is not None
        assert "gitStatus" in checkpoint
        event_checkpoint = payload["checkpoint"]
        assert event_checkpoint["targetId"] == DEMO_FRONTEND_TARGET_ID
        assert "targetRoot" not in event_checkpoint
        assert event_checkpoint["allowedPaths"] == ["apps/demo/src"]
        assert "node_modules" in event_checkpoint["deniedPaths"]
        assert event_checkpoint["plannedFiles"] == ["apps/demo/src/App.tsx"]
        assert event_checkpoint["dirtyFiles"] == checkpoint["dirtyFiles"]
        assert event_checkpoint["contractId"] == "contract-demo-dashboard"
        assert event_checkpoint["contractHash"] == checkpoint["contractHash"]
        assert type(event_checkpoint["gitStatus"]["available"]) is bool


def test_external_write_task_run_checkpoint_uses_target_registry_policy(
    client: TestClient,
    tmp_path: Path,
) -> None:
    external_root = tmp_path / "external-app"
    (external_root / "src").mkdir(parents=True)
    (external_root / "src" / "App.tsx").write_text("export default function App() {}\n")
    subprocess.run(["git", "init"], cwd=external_root, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=external_root,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=external_root,
        check=True,
    )
    subprocess.run(["git", "add", "src/App.tsx"], cwd=external_root, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=external_root, check=True)
    (external_root / "src" / "App.tsx").write_text("export default function App() { return null }\n")

    with db_from_override() as db:
        workspace = db.exec(select(Workspace).where(Workspace.name == "AgentHub Demo")).one()
        register_external_project_target(
            db,
            workspace,
            ExternalWorkspaceRegistration(
                target_id="external-checkpoint-app",
                name="External Checkpoint App",
                root_path=str(external_root),
                project_type="vite-react",
                allowed_paths=["src"],
                denied_paths=[".env", "node_modules", ".git"],
            ),
        )
        task = db.get(Task, task_id())
        task.plan_json = json.dumps(
            {
                "targetId": "external-checkpoint-app",
                "safeTarget": "src",
                "files": ["src/App.tsx"],
            },
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()

        task_run = create_task_run(db, task.id)

        checkpoint = json.loads(task_run.metrics_json)["preRunCheckpoint"]

        assert checkpoint["targetId"] == "external-checkpoint-app"
        assert checkpoint["targetRoot"] == str(external_root.resolve())
        assert checkpoint["allowedPaths"] == ["src"]
        assert ".env" in checkpoint["deniedPaths"]
        assert checkpoint["plannedFiles"] == ["src/App.tsx"]
        assert checkpoint["dirtyFiles"] == ["src/App.tsx"]
        assert "do-not-expose" not in json.dumps(checkpoint)


def test_default_code_adapter_env_selects_claude_code_for_frontend_task(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENTHUB_DEFAULT_CODE_ADAPTER", "claude_code")

    with db_from_override() as db:
        task_run = create_task_run(db, task_id())
        event = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == task_run.id)
            .where(TaskRunEvent.event_type == "task.state")
        ).one()

        assert json.loads(task_run.metrics_json)["adapterType"] == "claude_code"
        assert json.loads(event.payload_json)["adapterType"] == "claude_code"


def test_runtime_config_frontend_adapter_overrides_default_adapter(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENTHUB_DEFAULT_CODE_ADAPTER", "codex")

    with db_from_override() as db:
        workspace_id = db.exec(select(Session)).first().workspace_id
        upsert_runtime_config(
            db,
            workspace_id,
            {
                "frontend": RuntimeRoleConfig(
                    role="frontend",
                    agent_profile_id="agent-frontend",
                    provider_id="local-claude-code-cli",
                    adapter_type="claude_code",
                    mode="frontend",
                    enabled=True,
                    fallback_policy="explicit_only",
                )
            },
        )

        task_run = create_task_run(db, task_id())
        metrics = json.loads(task_run.metrics_json)
        response = task_run_response(db, task_run).model_dump(by_alias=True)

        assert metrics["adapterType"] == "claude_code"
        assert metrics["providerAssignment"]["source"] == "runtime_config"
        assert metrics["providerAssignment"]["providerId"] == "local-claude-code-cli"
        assert metrics["runtimeConfigResolution"]["configSource"] == "workspace"
        assert response["providerAssignment"]["source"] == "runtime_config"
        assert response["runtimeConfigResolution"]["providerId"] == "local-claude-code-cli"


def test_run_engine_gateway_honors_runtime_provider_id(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENTHUB_DEFAULT_CODE_ADAPTER", "codex")
    _allow_test_provider_health(monkeypatch)

    with db_from_override() as db:
        workspace_id = db.exec(select(Session)).first().workspace_id
        upsert_runtime_config(
            db,
            workspace_id,
            {
                "frontend": RuntimeRoleConfig(
                    role="frontend",
                    agent_profile_id="agent-frontend",
                    provider_id="local-claude-code-cli",
                    adapter_type="claude_code",
                    mode="frontend",
                    enabled=True,
                    fallback_policy="explicit_only",
                )
            },
        )

        task_run = create_task_run(db, task_id())
        try:
            gateway = run_engine_module._resolve_provider_gateway_for_run(
                db,
                task_run,
                "claude_code",
            )
            metrics = json.loads(db.get(TaskRun, task_run.id).metrics_json)
        finally:
            run_engine_module._release_provider_capacity(db, task_run.id)

    assert gateway["adapter_type"] == "claude_code"
    assert metrics["providerGateway"]["resolution"]["selectedProviderId"] == (
        "local-claude-code-cli"
    )
    assert metrics["providerGateway"]["resolution"]["selectedAdapterType"] == (
        "claude_code"
    )


def test_run_engine_gateway_honors_stored_provider_assignment_for_retry(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENTHUB_DEFAULT_CODE_ADAPTER", "codex")
    _allow_test_provider_health(monkeypatch)

    with db_from_override() as db:
        task_run = create_task_run(db, task_id(), adapter_type="claude_code")
        try:
            gateway = run_engine_module._resolve_provider_gateway_for_run(
                db,
                task_run,
                "claude_code",
            )
            metrics = json.loads(db.get(TaskRun, task_run.id).metrics_json)
        finally:
            run_engine_module._release_provider_capacity(db, task_run.id)

    assert gateway["adapter_type"] == "claude_code"
    assert metrics["providerAssignment"]["providerId"] == "local-claude-code-cli"
    assert metrics["providerGateway"]["resolution"]["selectedProviderId"] == (
        "local-claude-code-cli"
    )


def test_runtime_config_backend_adapter_overrides_environment_default(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENTHUB_DEFAULT_CODE_ADAPTER", "claude_code")

    with db_from_override() as db:
        workspace_id = db.exec(select(Session)).first().workspace_id
        backend_agent_id = db.exec(select(Agent).where(Agent.role == "backend")).one().id
        session_id = db.exec(select(Session)).first().id
        backend_task = Task(
            session_id=session_id,
            title="Build contacts API",
            intent_type="backend_change",
            status="pending",
            assigned_agent_id=backend_agent_id,
            plan_json=json.dumps({"assignedRole": "backend"}),
        )
        db.add(backend_task)
        db.commit()
        db.refresh(backend_task)
        upsert_runtime_config(
            db,
            workspace_id,
            {
                "backend": RuntimeRoleConfig(
                    role="backend",
                    agent_profile_id="agent-backend",
                    provider_id="local-codex-cli",
                    adapter_type="codex",
                    mode="backend",
                    enabled=True,
                    fallback_policy="explicit_only",
                )
            },
        )

        task_run = create_task_run(db, backend_task.id)
        metrics = json.loads(task_run.metrics_json)

        assert metrics["adapterType"] == "codex"
        assert metrics["providerAssignment"]["source"] == "runtime_config"
        assert metrics["providerAssignment"]["providerId"] == "local-codex-cli"


def test_default_code_adapter_env_preserves_explicit_and_non_code_adapters(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENTHUB_DEFAULT_CODE_ADAPTER", "claude_code")

    with db_from_override() as db:
        explicit = create_task_run(db, task_id(), adapter_type="codex")
        qa_agent_id = db.exec(select(Agent).where(Agent.role == "qa")).one().id
        session_id = db.exec(select(Task).where(Task.title == "Build login page")).one().session_id
        qa_task = Task(
            session_id=session_id,
            title="Review login page",
            intent_type="review",
            status="pending",
            assigned_agent_id=qa_agent_id,
        )
        db.add(qa_task)
        db.commit()
        scripted = create_task_run(db, qa_task.id)

        assert json.loads(explicit.metrics_json)["adapterType"] == "codex"
        assert json.loads(scripted.metrics_json)["adapterType"] == "scripted_mock"


def test_default_code_adapter_env_rejects_unknown_adapter(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENTHUB_DEFAULT_CODE_ADAPTER", "unknown")

    with db_from_override() as db:
        with pytest.raises(TaskRunLifecycleError, match="Unsupported"):
            create_task_run(db, task_id())


def test_provider_assignment_matrix_resolves_role_defaults(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "AGENTHUB_PROVIDER_ASSIGNMENT_MATRIX",
        json.dumps(
            {
                "roles": {
                    "frontend": {
                        "adapterType": "claude_code",
                        "providerId": "local-claude-code-cli",
                    },
                    "backend": {
                        "adapterType": "codex",
                        "providerId": "local-codex-cli",
                    },
                    "review": {
                        "adapterType": "scripted_mock",
                        "providerId": "local-scripted-review",
                    },
                }
            }
        ),
    )

    with db_from_override() as db:
        frontend_run = create_task_run(db, task_id())
        backend_agent = db.exec(select(Agent).where(Agent.role == "backend")).one()
        qa_agent = db.exec(select(Agent).where(Agent.role == "qa")).one()
        session_id = db.get(Task, task_id()).session_id
        backend_task = Task(
            session_id=session_id,
            title="Add contacts API",
            intent_type="backend_change",
            status="pending",
            assigned_agent_id=backend_agent.id,
            plan_json=json.dumps({"targetId": DEMO_BACKEND_TARGET_ID}),
        )
        review_task = Task(
            session_id=session_id,
            title="Review contacts work",
            intent_type="review",
            status="pending",
            assigned_agent_id=qa_agent.id,
            plan_json=json.dumps(
                {"assignedRole": "review", "targetId": DEMO_FRONTEND_TARGET_ID}
            ),
        )
        db.add(backend_task)
        db.add(review_task)
        db.commit()

        backend_run = create_task_run(db, backend_task.id)
        review_run = create_task_run(db, review_task.id)
        frontend_metrics = json.loads(frontend_run.metrics_json)
        backend_metrics = json.loads(backend_run.metrics_json)
        review_metrics = json.loads(review_run.metrics_json)

    assert frontend_metrics["adapterType"] == "claude_code"
    assert frontend_metrics["providerAssignment"]["source"] == "role_default"
    assert frontend_metrics["providerAssignment"]["role"] == "frontend"
    assert frontend_metrics["providerAssignment"]["providerId"] == "local-claude-code-cli"
    assert backend_metrics["adapterType"] == "codex"
    assert backend_metrics["providerAssignment"]["providerId"] == "local-codex-cli"
    assert review_metrics["adapterType"] == "scripted_mock"
    assert review_metrics["providerAssignment"]["role"] == "review"


def test_provider_assignment_matrix_target_override_precedes_role_default(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "AGENTHUB_PROVIDER_ASSIGNMENT_MATRIX",
        json.dumps(
            {
                "roles": {
                    "frontend": {
                        "adapterType": "codex",
                        "providerId": "local-codex-cli",
                    }
                },
                "targets": {
                    DEMO_FRONTEND_TARGET_ID: {
                        "frontend": {
                            "adapterType": "claude_code",
                            "providerId": "local-claude-code-cli",
                        }
                    }
                },
            }
        ),
    )

    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps(
            {"targetId": DEMO_FRONTEND_TARGET_ID},
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        task_run = create_task_run(db, task.id)
        response = task_run_response(db, task_run).model_dump(by_alias=True)

    assignment = response["metricsJson"]["providerAssignment"]
    assert response["adapterType"] == "claude_code"
    assert assignment["source"] == "target_override"
    assert assignment["targetId"] == DEMO_FRONTEND_TARGET_ID
    assert assignment["providerId"] == "local-claude-code-cli"


def test_provider_assignment_matrix_preserves_default_adapter_fallback(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AGENTHUB_PROVIDER_ASSIGNMENT_MATRIX", raising=False)
    monkeypatch.setenv("AGENTHUB_DEFAULT_CODE_ADAPTER", "claude_code")

    with db_from_override() as db:
        task_run = create_task_run(db, task_id())
        metrics = json.loads(task_run.metrics_json)

    assert metrics["adapterType"] == "claude_code"
    assert metrics["providerAssignment"]["source"] == "legacy_default"
    assert metrics["providerAssignment"]["fallbackPolicy"] == "legacy_default_adapter"


def test_provider_assignment_matrix_rejects_invalid_assignment(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "AGENTHUB_PROVIDER_ASSIGNMENT_MATRIX",
        json.dumps(
            {
                "roles": {
                    "frontend": {
                        "adapterType": "open_code",
                        "providerId": "local-opencode",
                    }
                }
            }
        ),
    )

    with db_from_override() as db:
        with pytest.raises(TaskRunLifecycleError, match="Unsupported provider assignment"):
            create_task_run(db, task_id())


def test_provider_assignment_is_visible_in_mission_trace(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "AGENTHUB_PROVIDER_ASSIGNMENT_MATRIX",
        json.dumps(
            {
                "roles": {
                    "frontend": {
                        "adapterType": "claude_code",
                        "providerId": "local-claude-code-cli",
                    }
                }
            }
        ),
    )

    with db_from_override() as db:
        task = db.get(Task, task_id())
        task_run = create_task_run(db, task.id)
        session_id = task.session_id
        run_id = task_run.id

    response = client.get(f"/sessions/{session_id}/mission-trace")

    assert response.status_code == 200
    trace = response.json()
    run_trace = next(run for run in trace["taskRuns"] if run["id"] == run_id)
    assert run_trace["adapterType"] == "claude_code"
    assert run_trace["providerAssignment"]["providerId"] == "local-claude-code-cli"
    assert run_trace["durableRun"]["runnerId"]
    assert run_trace["durableRun"]["lastHeartbeatAt"]
    assert run_trace["durableRun"]["leaseExpiresAt"]
    assert "worktree" not in run_trace["durableRun"]


def test_runtime_config_resolution_is_visible_in_mission_trace(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        session = db.exec(select(Session)).first()
        upsert_runtime_config(
            db,
            session.workspace_id,
            {
                "frontend": RuntimeRoleConfig(
                    role="frontend",
                    agent_profile_id="agent-frontend",
                    provider_id="local-claude-code-cli",
                    adapter_type="claude_code",
                    mode="frontend",
                    enabled=True,
                    fallback_policy="explicit_only",
                )
            },
        )
        task = db.get(Task, task_id())
        task_run = create_task_run(db, task.id)
        session_id = task.session_id
        run_id = task_run.id

    response = client.get(f"/sessions/{session_id}/mission-trace")

    assert response.status_code == 200
    trace = response.json()
    run_trace = next(run for run in trace["taskRuns"] if run["id"] == run_id)
    assert run_trace["runtimeConfigResolution"]["configSource"] == "workspace"
    assert run_trace["runtimeConfigResolution"]["providerId"] == "local-claude-code-cli"


def test_agent_run_request_bounds_frontend_login_demo_instruction(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps(
            {
                "target": "login_page",
                "files": ["apps/demo/src/App.tsx", "apps/demo/src/styles.css"],
            },
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        task_run = create_task_run(db, task.id)

        request = agent_run_request_for(db, task_run, adapter_type="codex")

    assert 'data-agenthub-target="login-page-slot"' in request.instruction
    assert "apps/demo/src/App.tsx" in request.instruction
    assert "do not read the OpenSpec change" in request.instruction
    assert "dependency install" in request.instruction
    assert request.instruction != "Build login page"


def test_provider_instruction_adapters_dispatch_without_losing_context(
    client: TestClient,
) -> None:
    assert adapter_for_provider("codex").provider_id == "codex"
    assert adapter_for_provider("claude_code").provider_id == "claude_code"
    assert adapter_for_provider("scripted_mock").provider_id == "scripted_mock"

    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps(
            {
                "target": "demo_frontend_request",
                "safeTarget": "apps/demo/src",
                "files": ["apps/demo/src/App.tsx"],
                "originalRequest": "Update the demo dashboard",
            },
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        task_run = create_task_run(db, task.id, adapter_type="claude_code")

        request = agent_run_request_for(db, task_run, adapter_type="claude_code")

    assert "Update the demo dashboard" in request.instruction
    assert "Canonical Shared Context" in request.instruction
    assert "canonical_shared_context_v1" in request.instruction
    assert "legacyContext" not in request.instruction
    assert request.adapter_type == "claude_code"


def test_provider_backed_instruction_filters_protected_context_values(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps(
            {
                "target": "demo_frontend_request",
                "safeTarget": "apps/demo/src",
                "files": [
                    "apps/demo/src/App.tsx",
                    "apps/demo/node_modules/pkg/index.js",
                    "/Users/example/secrets/token.txt",
                ],
                "originalRequest": "Build a dashboard",
                "secretToken": "should-not-leak",
            },
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        task_run = create_task_run(db, task.id, adapter_type="codex")

        request = agent_run_request_for(db, task_run, adapter_type="codex")
        stored_run = db.get(TaskRun, task_run.id)
        metrics = json.loads(stored_run.metrics_json)

    assert "Canonical Shared Context" in request.instruction
    assert "apps/demo/src/App.tsx" in request.instruction
    assert "apps/demo/node_modules/pkg/index.js" not in request.instruction
    assert "/Users/example/secrets/token.txt" not in request.instruction
    assert "should-not-leak" not in request.instruction
    assert "legacyContext" not in request.instruction
    snapshot = metrics["canonicalContextSnapshot"]
    assert snapshot["fields"]["safePaths"]["value"] == [
        "apps/demo/src",
        "apps/demo/src/App.tsx",
    ]


def test_codex_and_claude_instructions_preserve_same_canonical_facts(
    client: TestClient,
) -> None:
    contract = {
        "contractId": "contract-mini_crm_contacts",
        "appName": "Mini CRM",
        "backendTargetId": DEMO_BACKEND_TARGET_ID,
        "frontendTargetId": DEMO_FRONTEND_TARGET_ID,
        "apiRoutes": [{"method": "GET", "path": "/contacts"}],
    }
    handoff = {
        "artifactId": "handoff-1",
        "fromProviderId": "local-codex-cli",
        "fromAdapterType": "codex",
        "fromTaskRunId": "backend-run-1",
        "changedFiles": ["apps/demo-api/app/main.py"],
        "implementedRoutes": ["GET /contacts"],
        "warnings": [],
    }
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.title = "Frontend: render mini CRM contacts"
        task.plan_json = json.dumps(
            {
                "target": "demo_frontend_request",
                "targetId": DEMO_FRONTEND_TARGET_ID,
                "backendTargetId": DEMO_BACKEND_TARGET_ID,
                "appContract": contract,
                "contractId": contract["contractId"],
                "handoffNotes": [handoff],
                "expectedArtifactTypes": ["diff"],
                "safeTarget": "apps/demo/src",
                "files": ["apps/demo/src/App.tsx"],
                "originalRequest": "Build the mini CRM contacts UI",
            },
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        task_run = create_task_run(db, task.id)

        codex_request = agent_run_request_for(db, task_run, adapter_type="codex")
        claude_request = agent_run_request_for(db, task_run, adapter_type="claude_code")

    shared_facts = [
        "canonical_shared_context_v1",
        "contract-mini_crm_contacts",
        "demo-frontend",
        "demo-backend",
        "handoff-1",
        "local-codex-cli",
        "GET /contacts",
        "Produce a focused git diff in the assigned safe target.",
        "Do not edit .env files",
    ]
    for fact in shared_facts:
        assert fact in codex_request.instruction
        assert fact in claude_request.instruction

    assert "Codex Provider Instruction" in codex_request.instruction
    assert "Claude Code Provider Instruction" in claude_request.instruction
    assert codex_request.instruction != claude_request.instruction


def test_agent_run_request_bounds_followup_button_instruction(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.title = "Change primary button text to Sign in"
        task.plan_json = json.dumps(
            {
                "target": "primary_action_button_text",
                "targetText": "Sign in",
                "files": ["apps/demo/src/App.tsx"],
            },
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        task_run = create_task_run(db, task.id)

        request = agent_run_request_for(db, task_run, adapter_type="codex")

    assert 'data-agenthub-target="primary-action-button"' in request.instruction
    assert '"Sign in"' in request.instruction
    assert "do not read the OpenSpec change" in request.instruction
    assert "dependency install" in request.instruction


def test_agent_run_request_bounds_followup_heading_instruction(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.title = "Change demo heading text to Welcome back"
        task.plan_json = json.dumps(
            {
                "target": "demo_heading_text",
                "targetText": "Welcome back",
                "files": ["apps/demo/src/App.tsx"],
            },
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        task_run = create_task_run(db, task.id)

        request = agent_run_request_for(db, task_run, adapter_type="codex")

    assert 'id="demo-heading"' in request.instruction
    assert '"Welcome back"' in request.instruction
    assert "do not read the OpenSpec change" in request.instruction
    assert "dependency install" in request.instruction


def test_agent_run_request_preserves_generic_demo_frontend_request(
    client: TestClient,
) -> None:
    original_request = "帮我把当前 demo app 改成一个 dashboard，有三张统计卡片和一个最近活动列表"
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.title = "Frontend: dashboard request"
        task.plan_json = json.dumps(
            {
                "target": "demo_frontend_request",
                "safeTarget": "apps/demo/src",
                "files": ["apps/demo/src/App.tsx", "apps/demo/src/styles.css"],
                "originalRequest": original_request,
            },
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        task_run = create_task_run(db, task.id)

        request = agent_run_request_for(db, task_run, adapter_type="codex")

    assert original_request in request.instruction
    assert "Work only inside apps/demo/src" in request.instruction
    assert "apps/demo/src/App.tsx" in request.instruction
    assert "node_modules" in request.instruction
    assert "production deploy" in request.instruction
    assert "login-page-slot" not in request.instruction
    assert request.plan_context["originalRequest"] == original_request
    assert "Canonical Shared Context" in request.instruction
    assert request.plan_context["sessionContext"]["originalUserRequest"] == original_request
    assert request.plan_context["sessionContext"]["safeTargetPaths"] == [
        "apps/demo/src",
        "apps/demo/src/App.tsx",
        "apps/demo/src/styles.css",
    ]
    with db_from_override() as db:
        stored_run = db.get(TaskRun, task_run.id)
        metrics = json.loads(stored_run.metrics_json)

    snapshot = metrics["canonicalContextSnapshot"]
    assert snapshot["version"] == "canonical_shared_context_v1"
    assert snapshot["fields"]["userGoal"]["value"] == original_request
    assert snapshot["fields"]["currentTask"]["trustLevel"] == "system"
    assert snapshot["fields"]["safePaths"]["value"] == [
        "apps/demo/src",
        "apps/demo/src/App.tsx",
        "apps/demo/src/styles.css",
    ]


def test_context_pack_includes_recent_messages_ledger_and_excludes_other_sessions(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        workspace = db.exec(select(Workspace).where(Workspace.name == "AgentHub Demo")).one()
        task = db.get(Task, task_id())
        shared_message_time = utc_now()
        user_message = Message(
            id="fffffff0-0000-0000-0000-000000000000",
            session_id=task.session_id,
            sender_type="user",
            content_md="Build a dashboard",
            created_at=shared_message_time,
        )
        assistant_message = Message(
            id="0000000f-0000-0000-0000-000000000000",
            session_id=task.session_id,
            sender_type="orchestrator",
            content_md="Routing to the Frontend Agent.",
            created_at=shared_message_time,
        )
        other_session = Session(
            workspace_id=workspace.id,
            title="Other session",
            bound_branch="main",
            worktree_path=".worktrees/other-session",
        )
        other_message = Message(
            session_id=other_session.id,
            sender_type="user",
            content_md="Do not leak this message",
        )
        task.created_by_message_id = user_message.id
        task.plan_json = json.dumps(
            {
                "target": "demo_frontend_request",
                "safeTarget": "apps/demo/src",
                "files": ["apps/demo/src/App.tsx"],
                "originalRequest": "Build a dashboard",
            },
            separators=(",", ":"),
        )
        db.add(user_message)
        db.add(assistant_message)
        db.add(other_session)
        db.add(other_message)
        db.add(task)
        db.commit()

        context = build_session_context_pack(db, task)

    assert context["version"] == "session_context_pack_v1"
    assert context["originalUserRequest"] == "Build a dashboard"
    assert context["currentGoal"] == "Build a dashboard"
    assert context["ledger"]["summaryMd"].startswith("Current goal: Build a dashboard")
    assert [message["contentMd"] for message in context["recentMessages"]] == [
        "Build a dashboard",
        "Routing to the Frontend Agent.",
    ]
    assert all(
        message["contentMd"] != "Do not leak this message"
        for message in context["recentMessages"]
    )
    canonical = context["canonicalContext"]
    assert canonical["version"] == "canonical_shared_context_v1"
    assert canonical["fields"]["session"]["value"]["sessionId"] == task.session_id
    assert canonical["fields"]["userGoal"]["source"] == "session_ledger"
    assert canonical["fields"]["recentMessages"]["visibility"] == "provider"
    assert canonical["fields"]["guardrails"]["trustLevel"] == "system"


def test_canonical_context_filters_protected_provider_visible_paths(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps(
            {
                "target": "demo_frontend_request",
                "safeTarget": "apps/demo/src",
                "files": [
                    "apps/demo/src/App.tsx",
                    ".env",
                    "node_modules/pkg/index.js",
                    "/Users/example/secrets/token.txt",
                ],
                "originalRequest": "Build a dashboard",
                "secretToken": "should-not-leak",
            },
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()

        context = build_session_context_pack(db, task)

    safe_paths = context["canonicalContext"]["fields"]["safePaths"]["value"]
    visible = json.dumps(
        context["providerVisibleContext"],
        ensure_ascii=True,
        sort_keys=True,
    )
    assert safe_paths == ["apps/demo/src", "apps/demo/src/App.tsx"]
    assert ".env" not in visible
    assert "node_modules" not in visible
    assert "/Users/example" not in visible
    assert "should-not-leak" not in visible


def test_context_pack_includes_latest_artifact_preview_and_deploy_metadata(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps(
            {
                "target": "demo_frontend_request",
                "safeTarget": "apps/demo/src",
                "files": ["apps/demo/src/App.tsx"],
                "originalRequest": "Build a dashboard",
            },
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        task_run = create_task_run(db, task.id)
        transition_task_run(db, task_run.id, "completed")
        now = utc_now()
        diff_artifact = Artifact(
            task_run_id=task_run.id,
            artifact_type="diff",
            title="Git diff",
            status="ready",
            meta_json=json.dumps(
                {"changedFiles": ["apps/demo/src/App.tsx"]},
                separators=(",", ":"),
            ),
            created_at=now,
            updated_at=now,
        )
        db.add(diff_artifact)
        db.commit()
        db.refresh(diff_artifact)
        diff = Diff(
            artifact_id=diff_artifact.id,
            base_ref="base",
            head_ref="head+worktree",
            patch_text="diff --git a/apps/demo/src/App.tsx b/apps/demo/src/App.tsx",
            changed_files_json=json.dumps(["apps/demo/src/App.tsx"], separators=(",", ":")),
            stats_json=json.dumps({"filesChanged": 1, "additions": 3, "deletions": 1}, separators=(",", ":")),
        )
        review_artifact = Artifact(
            task_run_id=task_run.id,
            artifact_type="review",
            title="Review Agent report",
            status="passed",
            created_at=now,
            updated_at=now,
        )
        preview_artifact = Artifact(
            task_run_id=task_run.id,
            artifact_type="preview",
            title="Vite preview",
            status="running",
            created_at=now,
            updated_at=now,
        )
        deploy_artifact = Artifact(
            task_run_id=task_run.id,
            artifact_type="deployment",
            title="Mock deploy",
            status="ready",
            created_at=now,
            updated_at=now,
        )
        db.add(diff)
        db.add(review_artifact)
        db.add(preview_artifact)
        db.add(deploy_artifact)
        db.commit()
        db.refresh(review_artifact)
        db.refresh(preview_artifact)
        db.refresh(deploy_artifact)
        review = Review(
            artifact_id=review_artifact.id,
            reviewed_diff_artifact_id=diff_artifact.id,
            adapter_type="scripted_mock",
            status="passed",
            risk_level="low",
            summary="Looks good.",
            files_reviewed_json=json.dumps(["apps/demo/src/App.tsx"], separators=(",", ":")),
        )
        preview = Preview(
            artifact_id=preview_artifact.id,
            port=5173,
            url="http://127.0.0.1:5173",
            command="pnpm dev --host 127.0.0.1 --port 5173",
            health_status="healthy",
        )
        deployment = Deployment(
            artifact_id=deploy_artifact.id,
            provider="mock",
            environment="preview",
            url="https://mock.agenthub.local/deployments/demo",
            status="ready",
        )
        db.add(review)
        db.add(preview)
        db.add(deployment)
        db.commit()

        context = build_session_context_pack(
            db,
            task,
            plan_context={"selectedArtifactId": diff_artifact.id},
        )

    assert context["latestDiff"]["artifactId"] == diff_artifact.id
    assert context["latestDiff"]["changedFiles"] == ["apps/demo/src/App.tsx"]
    assert context["latestReview"]["summary"] == "Looks good."
    assert context["latestPreview"]["healthStatus"] == "healthy"
    assert context["latestDeployment"]["provider"] == "mock"
    assert context["selectedArtifact"]["valid"] is True
    assert context["selectedArtifact"]["artifactId"] == diff_artifact.id
    assert context["artifactReferences"][0]["artifact_id"] == diff_artifact.id
    assert context["artifactReferences"][0]["artifact_type"] == "diff"
    assert context["artifactReferences"][0]["valid"] is True
    assert context["ledger"]["latestChangedFiles"] == ["apps/demo/src/App.tsx"]


def test_artifact_reference_context_supports_preview_review_and_deploy(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task_run = create_task_run(db, task.id)
        transition_task_run(db, task_run.id, "completed")
        artifacts = [
            Artifact(
                task_run_id=task_run.id,
                artifact_type=artifact_type,
                title=f"{artifact_type} artifact",
                status="ready",
            )
            for artifact_type in ["review", "preview", "deployment"]
        ]
        for artifact in artifacts:
            db.add(artifact)
        db.commit()
        for artifact in artifacts:
            db.refresh(artifact)

        references = [
            build_session_context_pack(
                db,
                task,
                plan_context={"selectedArtifactId": artifact.id},
            )["artifactReferences"][0]
            for artifact in artifacts
        ]

    assert [reference["artifact_type"] for reference in references] == [
        "review",
        "preview",
        "deployment",
    ]
    assert all(reference["valid"] is True for reference in references)


def test_deployment_artifact_reference_context_includes_safe_metadata(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task_run = create_task_run(db, task.id)
        transition_task_run(db, task_run.id, "completed")
        deploy_artifact = Artifact(
            task_run_id=task_run.id,
            artifact_type="deployment",
            title="Blocked Vercel deployment",
            status="blocked",
            meta_json=json.dumps(
                {
                    "provider": "vercel",
                    "providerType": "external_static",
                    "targetId": "demo-frontend",
                    "environment": "external",
                    "source": {
                        "previewId": "preview-1",
                        "previewArtifactId": "artifact-preview-1",
                        "diffArtifactId": "artifact-diff-1",
                        "reviewArtifactId": "artifact-review-1",
                    },
                    "logs": [
                        "Vercel provider missing config.",
                        "api_key=sk-test-secret should not leak",
                    ],
                    "statusHistory": [
                        {"status": "queued", "message": "Deploy queued."},
                        {"status": "blocked", "message": "api_key missing"},
                    ],
                },
                separators=(",", ":"),
            ),
        )
        db.add(deploy_artifact)
        db.commit()
        db.refresh(deploy_artifact)
        deployment = Deployment(
            artifact_id=deploy_artifact.id,
            provider="vercel",
            environment="external",
            url=None,
            status="blocked",
        )
        db.add(deployment)
        db.commit()

        context = build_session_context_pack(
            db,
            task,
            plan_context={"selectedArtifactId": deploy_artifact.id},
        )

    reference = context["artifactReferences"][0]
    serialized = json.dumps(context)
    assert reference["artifact_type"] == "deployment"
    assert reference["valid"] is True
    assert reference["metadata"]["provider"] == "vercel"
    assert reference["metadata"]["providerType"] == "external_static"
    assert reference["metadata"]["source"]["previewId"] == "preview-1"
    assert reference["metadata"]["source"]["diffArtifactId"] == "artifact-diff-1"
    assert reference["metadata"]["logsSummary"][0] == "Vercel provider missing config."
    assert "[redacted]" in reference["metadata"]["logsSummary"]
    assert "sk-test-secret" not in serialized
    assert "api_key" not in serialized
    assert context["latestDeployment"]["provider"] == "vercel"
    assert context["latestDeployment"]["providerType"] == "external_static"
    assert context["latestDeployment"]["source"]["reviewArtifactId"] == "artifact-review-1"
    assert "[redacted]" in context["latestDeployment"]["logsSummary"]


def test_artifact_reference_context_rejects_unsupported_artifact_type(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task_run = create_task_run(db, task.id)
        artifact = Artifact(
            task_run_id=task_run.id,
            artifact_type="command_evidence",
            title="Command evidence",
            status="ready",
        )
        db.add(artifact)
        db.commit()
        db.refresh(artifact)

        context = build_session_context_pack(
            db,
            task,
            plan_context={"selectedArtifactId": artifact.id},
        )

    reference = context["artifactReferences"][0]
    assert reference["artifact_type"] == "command_evidence"
    assert reference["valid"] is False
    assert "not supported in P23" in reference["reason"]


def test_artifact_reference_context_supports_workbench_version_context(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task_run = create_task_run(db, task.id)
        artifact = Artifact(
            task_run_id=task_run.id,
            artifact_type="markdown_document",
            title="Release notes",
            status="ready",
            meta_json='{"safeSummary":"Edited notes","apiToken":"sk-secret"}',
        )
        db.add(artifact)
        db.commit()
        db.refresh(artifact)
        message = Message(
            session_id=task.session_id,
            sender_type="user",
            content_md="请参考这个产物继续修改",
            context_json=json.dumps(
                {
                    "selectedArtifactId": artifact.id,
                    "selectedArtifactVersionId": "version-2",
                    "selectedArtifact": {
                        "artifactId": artifact.id,
                        "selectedText": "## Selected section",
                        "versionId": "version-2",
                    },
                },
                separators=(",", ":"),
            ),
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        task.created_by_message_id = message.id
        db.add(task)
        db.commit()
        context = build_session_context_pack(db, task)

    reference = context["artifactReferences"][0]
    assert reference["artifact_id"] == artifact.id
    assert reference["artifact_type"] == "markdown_document"
    assert reference["version_id"] == "version-2"
    assert reference["selected_text"] == "## Selected section"
    assert reference["safe_summary"] == "Edited notes"
    assert "apiToken" not in json.dumps(reference)
    assert context["selectedArtifact"]["versionId"] == "version-2"
    assert context["contextItems"][0]["kind"] == "artifact"
    assert context["contextItems"][0]["artifactId"] == artifact.id
    assert context["contextItems"][0]["artifactVersionId"] == "version-2"
    assert context["contextItems"][0]["selectedText"] == "## Selected section"
    relevant_artifacts = context["canonicalContext"]["fields"]["relevantArtifacts"]["value"]
    assert relevant_artifacts["contextItems"][0]["artifactId"] == artifact.id
    assert (
        context["providerVisibleContext"]["canonicalContext"]["fields"]["relevantArtifacts"][
            "value"
        ]["contextItems"][0]["artifactVersionId"]
        == "version-2"
    )


def test_session_mission_trace_exposes_tasks_artifacts_and_blockers(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task_run = create_task_run(db, task.id)
        transition_task_run(db, task_run.id, "completed")
        artifact = Artifact(
            task_run_id=task_run.id,
            artifact_type="diff",
            title="Git diff",
            status="ready",
        )
        db.add(artifact)
        db.commit()
        task.plan_json = json.dumps(
            {
                "scheduler": {
                    "state": "waiting_dependency",
                    "reason": "Waiting for upstream dependencies to complete.",
                    "dependencyIds": ["upstream-task"],
                    "blockingDependencyIds": ["upstream-task"],
                    "targetId": DEMO_FRONTEND_TARGET_ID,
                }
            },
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        session_id = task.session_id
        task_run_id_value = task_run.id

    response = client.get(f"/sessions/{session_id}/mission-trace")

    assert response.status_code == 200
    trace = response.json()
    assert trace["tasks"][0]["id"] == task_id()
    assert trace["taskRuns"][0]["id"] == task_run_id_value
    assert trace["events"]
    assert trace["artifacts"][0]["artifactType"] == "diff"
    assert trace["blockers"][0]["state"] == "waiting_dependency"
    assert trace["blockers"][0]["blockingDependencyIds"] == ["upstream-task"]
    assert trace["nextActions"][0]["type"] == "inspect_blocker"


def test_completed_dependency_creates_handoff_context_for_downstream_task(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        upstream = db.get(Task, task_id())
        upstream.plan_json = json.dumps(
            {
                "target": "demo_frontend_request",
                "files": ["apps/demo/src/App.tsx"],
                "originalRequest": "Build a dashboard",
            },
            separators=(",", ":"),
        )
        qa_agent = db.exec(select(Agent).where(Agent.role == "qa")).one()
        downstream = Task(
            session_id=upstream.session_id,
            title="Review dashboard diff",
            intent_type="review",
            status="pending",
            assigned_agent_id=qa_agent.id,
            depends_on_task_ids=json.dumps([upstream.id], separators=(",", ":")),
            plan_json=json.dumps(
                {
                    "assignedRole": "review",
                    "target": "session_review_request",
                    "originalRequest": "Review the dashboard",
                },
                separators=(",", ":"),
            ),
        )
        db.add(upstream)
        db.add(downstream)
        db.commit()
        db.refresh(upstream)
        db.refresh(downstream)

        upstream_run = create_task_run(db, upstream.id, adapter_type="claude_code")
        diff_artifact = Artifact(
            task_run_id=upstream_run.id,
            artifact_type="diff",
            title="Git diff",
            status="ready",
            meta_json=json.dumps(
                {"changedFiles": ["apps/demo/src/App.tsx"]},
                separators=(",", ":"),
            ),
        )
        db.add(diff_artifact)
        db.commit()
        transition_task_run(db, upstream_run.id, "completed")
        handoff = db.exec(
            select(Artifact).where(Artifact.artifact_type == "handoff")
        ).one()
        context = build_session_context_pack(db, downstream)
        handoff_id = handoff.id
        handoff_status = handoff.status
        handoff_meta = json.loads(handoff.meta_json)
        upstream_id = upstream.id
        upstream_run_id = upstream_run.id
        downstream_id = downstream.id
        session_id = upstream.session_id

    assert handoff_status == "ready"
    assert handoff_meta["fromTaskId"] == upstream_id
    assert handoff_meta["fromTaskRunId"] == upstream_run_id
    assert handoff_meta["fromAgentRole"] == "frontend"
    assert handoff_meta["fromProviderId"] == "local-claude-code-cli"
    assert handoff_meta["fromAdapterType"] == "claude_code"
    assert handoff_meta["toTaskId"] == downstream_id
    assert handoff_meta["toAgentRole"] == "qa"
    assert handoff_meta["toProviderId"] == "local-scripted-review"
    assert handoff_meta["toAdapterType"] == "scripted_mock"
    assert handoff_meta["changedFiles"] == ["apps/demo/src/App.tsx"]
    assert handoff_meta["implementedComponents"] == ["apps/demo/src/App.tsx"]
    assert handoff_meta["implementedRoutes"] == []
    assert handoff_meta["warnings"] == []
    assert handoff_meta["verificationStatus"] == "completed"
    assert context["handoffNotes"][0]["artifactId"] == handoff_id
    assert context["canonicalContext"]["fields"]["handoffNotes"]["value"][0][
        "toTaskId"
    ] == downstream_id
    assert context["canonicalContext"]["fields"]["handoffNotes"]["value"][0][
        "fromProviderId"
    ] == "local-claude-code-cli"

    response = client.get(f"/sessions/{session_id}/mission-trace")
    assert response.status_code == 200
    trace = response.json()
    handoff_trace = next(
        artifact
        for artifact in trace["artifacts"]
        if artifact["artifactType"] == "handoff"
    )
    assert handoff_trace["meta"]["fromProviderId"] == "local-claude-code-cli"
    assert handoff_trace["meta"]["toProviderId"] == "local-scripted-review"


def test_review_handoff_carries_provider_warnings_to_fix_task(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        qa_agent = db.exec(select(Agent).where(Agent.role == "qa")).one()
        frontend_agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        session_id = db.exec(select(Task).where(Task.title == "Build login page")).one().session_id
        review_task = Task(
            session_id=session_id,
            title="Review dashboard diff",
            intent_type="review",
            status="pending",
            assigned_agent_id=qa_agent.id,
            plan_json=json.dumps(
                {
                    "assignedRole": "review",
                    "target": "session_review_request",
                    "files": ["apps/demo/src/App.tsx"],
                },
                separators=(",", ":"),
            ),
        )
        fix_task = Task(
            session_id=session_id,
            title="Fix review warnings",
            intent_type="frontend_change",
            status="pending",
            assigned_agent_id=frontend_agent.id,
            depends_on_task_ids="[]",
            plan_json=json.dumps(
                {
                    "assignedRole": "frontend",
                    "target": "demo_frontend_request",
                    "safeTarget": "apps/demo/src",
                },
                separators=(",", ":"),
            ),
        )
        db.add(review_task)
        db.add(fix_task)
        db.commit()
        db.refresh(review_task)
        db.refresh(fix_task)
        fix_task.depends_on_task_ids = json.dumps([review_task.id], separators=(",", ":"))
        db.add(fix_task)
        db.commit()

        review_run = create_task_run(db, review_task.id, adapter_type="scripted_mock")
        review_artifact = Artifact(
            task_run_id=review_run.id,
            artifact_type="review",
            title="Review Agent report",
            status="warning",
            meta_json=json.dumps(
                {
                    "summary": "Needs a loading state.",
                    "findings": [
                        {
                            "severity": "warning",
                            "message": "Add a loading state before rendering contacts.",
                        }
                    ],
                    "suggestedChanges": ["Add loading state."],
                },
                separators=(",", ":"),
            ),
        )
        db.add(review_artifact)
        db.commit()
        transition_task_run(db, review_run.id, "completed")

        handoff = db.exec(
            select(Artifact).where(Artifact.artifact_type == "handoff")
        ).one()
        context = build_session_context_pack(db, fix_task)
        handoff_meta = json.loads(handoff.meta_json)

    assert handoff_meta["fromAgentRole"] == "qa"
    assert handoff_meta["fromAdapterType"] == "scripted_mock"
    assert handoff_meta["toAgentRole"] == "frontend"
    assert handoff_meta["warnings"] == ["Add a loading state before rendering contacts."]
    assert handoff_meta["suggestedFollowUpScope"] == ["Add loading state."]
    assert context["canonicalContext"]["fields"]["handoffNotes"]["value"][0][
        "warnings"
    ] == ["Add a loading state before rendering contacts."]


def test_backend_instruction_targets_demo_backend_without_platform_api_access(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        backend_agent = db.exec(select(Agent).where(Agent.role == "backend")).one()
        session_id = db.exec(select(Task).where(Task.title == "Build login page")).one().session_id
        backend_task = Task(
            session_id=session_id,
            title="Backend: add contacts endpoint",
            intent_type="backend_change",
            status="pending",
            assigned_agent_id=backend_agent.id,
            plan_json=json.dumps(
                {
                    "target": "demo_backend_request",
                    "targetId": DEMO_BACKEND_TARGET_ID,
                    "safeTarget": "apps/demo-api",
                    "originalRequest": "@backend add a contacts endpoint",
                },
                separators=(",", ":"),
            ),
        )
        db.add(backend_task)
        db.commit()
        db.refresh(backend_task)
        task_run = create_task_run(db, backend_task.id)

        request = agent_run_request_for(db, task_run, adapter_type="codex")

    assert "apps/demo-api exists" in request.instruction
    assert "Work only inside apps/demo-api" in request.instruction
    assert "GET /health" in request.instruction
    assert "POST /contacts" in request.instruction
    assert "targetId: demo-backend" in request.instruction
    assert "testCommand: pnpm demo:api:test" in request.instruction
    assert "Do not edit apps/api" in request.instruction
    assert "not available yet" not in request.instruction
    assert request.plan_context["sessionContext"]["targetProject"]["targetId"] == DEMO_BACKEND_TARGET_ID
    assert request.plan_context["sessionContext"]["safeTargetPaths"] == ["apps/demo-api"]


def test_passthrough_instruction_preserves_original_request_without_demo_rewrite(
    client: TestClient,
) -> None:
    breakout_request = (
        "帮我在当前前端项目里实现一个 Breakout / 打砖块游戏，要求可以用键盘控制挡板，"
        "球能反弹，能击碎砖块，有得分、胜利/失败状态和重新开始按钮。"
    )
    with db_from_override() as db:
        frontend_agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        session_id = db.exec(select(Task).where(Task.title == "Build login page")).one().session_id
        task = Task(
            session_id=session_id,
            title="Implement Breakout game",
            intent_type="frontend_change",
            status="pending",
            assigned_agent_id=frontend_agent.id,
            plan_json=json.dumps(
                {
                    "planner": "llm_v1",
                    "plannerMode": "llm_v1",
                    "target": "login_page",
                    "targetId": DEMO_FRONTEND_TARGET_ID,
                    "safeTarget": "apps/demo/src",
                    "files": ["apps/demo/src/App.tsx", "apps/demo/src/styles.css"],
                    "originalRequest": breakout_request,
                    "description": "Implement a playable Breakout game.",
                    "acceptanceCriteria": [
                        "Keyboard controls move the paddle",
                        "Ball can break bricks",
                    ],
                    "validationExpectations": ["pnpm build"],
                },
                separators=(",", ":"),
            ),
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_run = create_task_run(db, task.id)

        request = agent_run_request_for(db, task_run, adapter_type="codex")

    assert breakout_request in request.instruction
    assert "Instruction mode: llm_v1" in request.instruction
    assert "Do not rewrite this request into the old login-page" in request.instruction
    assert "Keyboard controls move the paddle" in request.instruction
    assert "pnpm build" in request.instruction
    assert 'data-agenthub-target="login-page-slot"' not in request.instruction


def test_llm_review_task_is_satisfied_by_generated_review_artifact(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        session_id = db.exec(select(Task).where(Task.title == "Build login page")).one().session_id
        frontend_agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        qa_agent = db.exec(select(Agent).where(Agent.role == "qa")).one()
        frontend_task = db.exec(select(Task).where(Task.title == "Build login page")).one()
        frontend_task.status = "completed"
        frontend_task.plan_json = json.dumps(
            {
                "planner": "llm_v1",
                "targetId": DEMO_FRONTEND_TARGET_ID,
            },
            separators=(",", ":"),
        )
        frontend_run = TaskRun(
            task_id=frontend_task.id,
            agent_id=frontend_agent.id,
            state="completed",
            worktree_path=".worktrees/taskrun-session",
            metrics_json=json.dumps({"adapterType": "claude_code"}, separators=(",", ":")),
        )
        db.add(frontend_task)
        db.add(frontend_run)
        db.commit()
        db.refresh(frontend_run)

        diff_artifact = Artifact(
            task_run_id=frontend_run.id,
            artifact_type="diff",
            title="Git diff",
            status="ready",
        )
        review_artifact = Artifact(
            task_run_id=frontend_run.id,
            artifact_type="review",
            title="Review Agent report",
            status="passed",
        )
        db.add(diff_artifact)
        db.add(review_artifact)
        db.commit()
        db.refresh(diff_artifact)
        db.refresh(review_artifact)
        review = Review(
            artifact_id=review_artifact.id,
            reviewed_diff_artifact_id=diff_artifact.id,
            adapter_type="scripted_mock",
            status="passed",
            risk_level="low",
            summary="Generated review passed.",
        )
        db.add(review)

        review_task = Task(
            session_id=session_id,
            title="QA review Breakout game implementation",
            intent_type="review",
            status="pending",
            assigned_agent_id=qa_agent.id,
            depends_on_task_ids=json.dumps([frontend_task.id], separators=(",", ":")),
            plan_json=json.dumps(
                {
                    "planner": "llm_v1",
                    "targetId": DEMO_FRONTEND_TARGET_ID,
                },
                separators=(",", ":"),
            ),
        )
        db.add(review_task)
        db.commit()
        db.refresh(review_task)

        completed = _complete_ready_pipeline_review_tasks(db, frontend_task.id)

        assert [task.id for task in completed] == [review_task.id]
        db.refresh(review_task)
        assert review_task.status == "completed"
        assert json.loads(review_task.plan_json)["scheduler"]["state"] == "completed"
        assert "generated review artifact" in json.loads(review_task.plan_json)["scheduler"]["reason"]


def test_external_target_context_reaches_instruction_builder(
    client: TestClient,
    tmp_path,
) -> None:
    with db_from_override() as db:
        workspace = db.exec(select(Workspace).where(Workspace.name == "AgentHub Demo")).one()
        external_root = tmp_path / "external-vite"
        (external_root / "src").mkdir(parents=True)
        register_external_project_target(
            db,
            workspace,
            ExternalWorkspaceRegistration(
                target_id="external-vite-app",
                name="External Vite App",
                root_path=str(external_root),
                project_type="vite-react",
                allowed_paths=["src"],
                dev_command="pnpm dev",
                test_command="pnpm test",
                check_command="pnpm check",
                package_manager="pnpm",
                detected_framework="vite-react",
            ),
        )
        frontend_agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        session_id = db.exec(select(Task).where(Task.title == "Build login page")).one().session_id
        task = Task(
            session_id=session_id,
            title="External frontend change",
            intent_type="frontend_change",
            status="pending",
            assigned_agent_id=frontend_agent.id,
            plan_json=json.dumps(
                {
                    "targetId": "external-vite-app",
                    "safeTarget": "src",
                    "files": ["src/App.tsx"],
                    "originalRequest": "@frontend update the external app",
                },
                separators=(",", ":"),
            ),
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_run = create_task_run(db, task.id)

        request = agent_run_request_for(db, task_run, adapter_type="codex")

    target_context = request.plan_context["sessionContext"]["targetProject"]
    assert request.worktree_path == str(external_root.resolve())
    assert target_context["targetId"] == "external-vite-app"
    assert target_context["root"] == str(external_root.resolve())
    assert target_context["allowedPaths"] == ["src"]
    assert request.plan_context["sessionContext"]["safeTargetPaths"] == [
        "src",
        "src/App.tsx",
    ]
    assert "targetId: external-vite-app" in request.instruction
    assert f"root: {external_root.resolve()}" in request.instruction
    assert "packageManager: pnpm" in request.instruction
    assert "detectedFramework: vite-react" in request.instruction
    assert "projectProfileId: vite-react" in request.instruction
    assert "previewStrategy: vite-dev-server" in request.instruction
    assert "projectProfileCommands: check=pnpm check, dev=pnpm dev, test=pnpm test" in request.instruction
    assert "registered external AgentHub target" in request.instruction
    assert "Do not assume apps/demo" in request.instruction


def test_external_backend_instruction_uses_external_target_metadata(
    client: TestClient,
    tmp_path,
) -> None:
    with db_from_override() as db:
        workspace = db.exec(select(Workspace).where(Workspace.name == "AgentHub Demo")).one()
        external_root = tmp_path / "external-api"
        (external_root / "app").mkdir(parents=True)
        register_external_project_target(
            db,
            workspace,
            ExternalWorkspaceRegistration(
                target_id="external-fastapi",
                name="External FastAPI",
                root_path=str(external_root),
                project_type="fastapi",
                allowed_paths=["app", "tests"],
                test_command="pytest",
                check_command="python -m compileall .",
                package_manager="pip",
                detected_framework="fastapi",
            ),
        )
        backend_agent = db.exec(select(Agent).where(Agent.role == "backend")).one()
        session_id = db.exec(select(Task).where(Task.title == "Build login page")).one().session_id
        task = Task(
            session_id=session_id,
            title="External backend change",
            intent_type="backend_change",
            status="pending",
            assigned_agent_id=backend_agent.id,
            plan_json=json.dumps(
                {
                    "targetId": "external-fastapi",
                    "safeTarget": "app",
                    "files": ["app/main.py"],
                    "originalRequest": "@backend add a status endpoint",
                },
                separators=(",", ":"),
            ),
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_run = create_task_run(db, task.id)

        request = agent_run_request_for(db, task_run, adapter_type="codex")

    assert "Backend Agent for a registered external AgentHub target" in request.instruction
    assert "targetId: external-fastapi" in request.instruction
    assert f"root: {external_root.resolve()}" in request.instruction
    assert "allowedPaths: app, tests" in request.instruction
    assert "checkCommand: python -m compileall ." in request.instruction
    assert "testCommand: pytest" in request.instruction
    assert "projectProfileId: fastapi-python" in request.instruction
    assert "previewStrategy: python-api" in request.instruction
    assert "Do not edit AgentHub platform backend `apps/api`" in request.instruction
    assert "safe demo backend target" not in request.instruction


def test_rehearsal_root_instruction_points_new_project_to_dedicated_subdirectory(
    client: TestClient,
    tmp_path,
) -> None:
    with db_from_override() as db:
        workspace = db.exec(select(Workspace).where(Workspace.name == "AgentHub Demo")).one()
        external_root = tmp_path / "agenthub-rehearsals"
        external_root.mkdir()
        register_external_project_target(
            db,
            workspace,
            ExternalWorkspaceRegistration(
                target_id="external-agenthub-rehearsals",
                name="AgentHub rehearsals",
                root_path=str(external_root),
                project_type="unknown",
                allowed_paths=["*"],
            ),
        )
        frontend_agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        session_id = db.exec(select(Task).where(Task.title == "Build login page")).one().session_id
        task = Task(
            session_id=session_id,
            title="External bookkeeping app",
            intent_type="frontend_change",
            status="pending",
            assigned_agent_id=frontend_agent.id,
            plan_json=json.dumps(
                {
                    "targetId": "external-agenthub-rehearsals",
                    "safeTarget": "*",
                    "files": ["*"],
                    "originalRequest": "帮我做一个记账软件，登记每天的支出与收入，界面可爱",
                },
                separators=(",", ":"),
            ),
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_run = create_task_run(db, task.id)

        request = agent_run_request_for(db, task_run, adapter_type="codex")

    assert "dedicated subdirectory `bookkeeping-app`" in request.instruction
    assert "Do not reuse or rewrite unrelated sibling rehearsal apps" in request.instruction


def test_external_review_instruction_is_read_oriented_with_command_evidence(
    client: TestClient,
    tmp_path,
) -> None:
    with db_from_override() as db:
        workspace = db.exec(select(Workspace).where(Workspace.name == "AgentHub Demo")).one()
        external_root = tmp_path / "external-review-app"
        (external_root / "src").mkdir(parents=True)
        register_external_project_target(
            db,
            workspace,
            ExternalWorkspaceRegistration(
                target_id="external-review-app",
                name="External Review App",
                root_path=str(external_root),
                project_type="vite-react",
                allowed_paths=["src"],
                test_command="pnpm test",
                check_command="pnpm check",
                package_manager="pnpm",
                detected_framework="vite-react",
            ),
        )
        qa_agent = db.exec(select(Agent).where(Agent.role == "qa")).one()
        session_id = db.exec(select(Task).where(Task.title == "Build login page")).one().session_id
        task = Task(
            session_id=session_id,
            title="Review external app diff",
            intent_type="review",
            status="pending",
            assigned_agent_id=qa_agent.id,
            plan_json=json.dumps(
                {
                    "targetId": "external-review-app",
                    "readOnly": True,
                    "originalRequest": "@review check the external app diff",
                    "expectedArtifactTypes": ["review"],
                },
                separators=(",", ":"),
            ),
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_run = create_task_run(db, task.id)

        request = agent_run_request_for(db, task_run, adapter_type="scripted_mock")

    assert "QA / Review Agent for a registered external AgentHub target" in request.instruction
    assert "Review target `external-review-app`" in request.instruction
    assert "configured check/test/build evidence" in request.instruction
    assert "do not claim validation success" in request.instruction
    assert "Stay read-oriented" in request.instruction


def test_review_instruction_includes_reviewable_diff_context(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task_run = create_task_run(db, task.id)
        transition_task_run(db, task_run.id, "completed")
        diff_artifact = Artifact(
            task_run_id=task_run.id,
            artifact_type="diff",
            title="Git diff",
            status="ready",
            meta_json="{}",
        )
        db.add(diff_artifact)
        db.commit()
        db.refresh(diff_artifact)
        diff = Diff(
            artifact_id=diff_artifact.id,
            base_ref="base",
            head_ref="head+worktree",
            patch_text="diff --git a/apps/demo/src/App.tsx b/apps/demo/src/App.tsx",
            changed_files_json=json.dumps(["apps/demo/src/App.tsx"], separators=(",", ":")),
            stats_json=json.dumps({"filesChanged": 1}, separators=(",", ":")),
        )
        qa_agent = db.exec(select(Agent).where(Agent.role == "qa")).one()
        review_task = Task(
            session_id=task.session_id,
            title="Review latest diff",
            intent_type="review",
            status="pending",
            assigned_agent_id=qa_agent.id,
            plan_json=json.dumps(
                {
                    "assignedRole": "review",
                    "target": "session_review_request",
                    "selectedArtifactId": diff_artifact.id,
                    "originalRequest": "@review check the latest diff",
                },
                separators=(",", ":"),
            ),
        )
        db.add(diff)
        db.add(review_task)
        db.commit()
        db.refresh(review_task)
        review_run = create_task_run(db, review_task.id)

        request = agent_run_request_for(db, review_run, adapter_type="scripted_mock")

    assert "QA / Review Agent" in request.instruction
    assert "read-oriented by default" in request.instruction
    assert diff_artifact.id in request.instruction
    assert "apps/demo/src/App.tsx" in request.instruction
    assert request.plan_context["sessionContext"]["latestDiff"]["artifactId"] == diff_artifact.id


def test_contract_aware_role_instructions_reference_same_contract(
    client: TestClient,
) -> None:
    contract = {
        "contractId": "contract-mini_crm_contacts",
        "appName": "Mini CRM Contacts",
        "appType": "mini_crm_contacts",
        "userGoal": "帮我做一个 mini CRM，包含联系人和备注",
        "frontendTargetId": DEMO_FRONTEND_TARGET_ID,
        "backendTargetId": DEMO_BACKEND_TARGET_ID,
        "backendTarget": "apps/demo-api",
        "frontendTarget": "apps/demo",
        "demoApiBaseUrl": "http://127.0.0.1:5174",
        "apiRoutes": [
            {"method": "GET", "path": "/contacts"},
            {"method": "POST", "path": "/contacts"},
        ],
    }
    with db_from_override() as db:
        session_id = db.exec(select(Task).where(Task.title == "Build login page")).one().session_id
        backend_agent = db.exec(select(Agent).where(Agent.role == "backend")).one()
        frontend_agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        qa_agent = db.exec(select(Agent).where(Agent.role == "qa")).one()
        backend_task = Task(
            session_id=session_id,
            title="Implement CRM backend",
            intent_type="backend_change",
            status="pending",
            assigned_agent_id=backend_agent.id,
            plan_json=json.dumps(
                {
                    "assignedRole": "backend",
                    "targetId": DEMO_BACKEND_TARGET_ID,
                    "backendTargetId": DEMO_BACKEND_TARGET_ID,
                    "safeTarget": "apps/demo-api",
                    "appContract": contract,
                    "contractId": contract["contractId"],
                    "originalRequest": contract["userGoal"],
                },
                separators=(",", ":"),
            ),
        )
        frontend_task = Task(
            session_id=session_id,
            title="Implement CRM frontend",
            intent_type="frontend_change",
            status="pending",
            assigned_agent_id=frontend_agent.id,
            plan_json=json.dumps(
                {
                    "assignedRole": "frontend",
                    "targetId": DEMO_FRONTEND_TARGET_ID,
                    "frontendTargetId": DEMO_FRONTEND_TARGET_ID,
                    "backendTargetId": DEMO_BACKEND_TARGET_ID,
                    "safeTarget": "apps/demo/src",
                    "frontendTarget": "apps/demo",
                    "files": ["apps/demo/src/App.tsx"],
                    "appContract": contract,
                    "contractId": contract["contractId"],
                    "originalRequest": contract["userGoal"],
                },
                separators=(",", ":"),
            ),
        )
        review_task = Task(
            session_id=session_id,
            title="Review CRM contract work",
            intent_type="review",
            status="pending",
            assigned_agent_id=qa_agent.id,
            plan_json=json.dumps(
                {
                    "assignedRole": "review",
                    "targetId": DEMO_FRONTEND_TARGET_ID,
                    "target": "contract_review",
                    "appContract": contract,
                    "contractId": contract["contractId"],
                    "originalRequest": contract["userGoal"],
                },
                separators=(",", ":"),
            ),
        )
        db.add(backend_task)
        db.add(frontend_task)
        db.add(review_task)
        db.commit()
        db.refresh(backend_task)
        db.refresh(frontend_task)
        db.refresh(review_task)
        backend_run = create_task_run(db, backend_task.id)
        frontend_run = create_task_run(db, frontend_task.id)
        review_run = create_task_run(db, review_task.id)

        backend_request = agent_run_request_for(db, backend_run, adapter_type="codex")
        frontend_request = agent_run_request_for(db, frontend_run, adapter_type="codex")
        review_request = agent_run_request_for(db, review_run, adapter_type="scripted_mock")

    for request in [backend_request, frontend_request, review_request]:
        assert "contract-mini_crm_contacts" in request.instruction
        assert request.plan_context["sessionContext"]["appContract"] == contract

    assert "targeting `demo-backend` (apps/demo-api)" in backend_request.instruction
    assert "targeting `demo-frontend` (apps/demo/src)" in frontend_request.instruction
    assert "targetId: demo-frontend" in frontend_request.instruction
    assert "relatedBackendTargetId: demo-backend" in frontend_request.instruction
    assert "http://127.0.0.1:5174" in frontend_request.instruction
    assert "Do not call the AgentHub platform API at http://localhost:8000" in frontend_request.instruction
    assert "Review backend and frontend work" in review_request.instruction
    assert frontend_request.plan_context["sessionContext"]["targetProject"]["targetId"] == DEMO_FRONTEND_TARGET_ID
    assert frontend_request.plan_context["sessionContext"]["relatedTargetProjects"][0]["targetId"] == DEMO_BACKEND_TARGET_ID


def test_platform_instruction_requires_explicit_platform_mode_and_approval(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        backend_agent = db.exec(select(Agent).where(Agent.role == "backend")).one()
        session_id = db.exec(select(Task).where(Task.title == "Build login page")).one().session_id
        platform_task = Task(
            session_id=session_id,
            title="Platform maintenance: adjust AgentHub API",
            intent_type="platform_maintenance",
            status="pending",
            assigned_agent_id=backend_agent.id,
            plan_json=json.dumps(
                {
                    "assignedRole": "backend",
                    "targetId": AGENTHUB_PLATFORM_TARGET_ID,
                    "platformMode": True,
                    "requiresApproval": True,
                    "originalRequest": "platform mode: adjust AgentHub API",
                },
                separators=(",", ":"),
            ),
        )
        db.add(platform_task)
        db.commit()
        db.refresh(platform_task)
        task_run = create_task_run(db, platform_task.id)
        event = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == task_run.id)
            .where(TaskRunEvent.event_type == "approval.requested")
        ).one()
        task_run_state = task_run.state
        approval_payload = json.loads(event.payload_json)

        request = agent_run_request_for(db, task_run, adapter_type="codex")

    assert task_run_state == "waiting_approval"
    assert approval_payload["approvalType"] == "security_approval"
    assert approval_payload["riskLevel"] == "high"
    assert approval_payload["path"] == "apps/api"
    assert "AgentHub Platform Maintenance Mode" in request.instruction
    assert "targetId: agenthub-platform" in request.instruction
    assert "requiresPlatformMode: true" in request.instruction
    assert "requiresApproval: true" in request.instruction
    assert "pnpm check && pnpm test" in request.instruction
    assert request.plan_context["sessionContext"]["targetProject"]["targetId"] == AGENTHUB_PLATFORM_TARGET_ID


def test_runtime_config_backend_does_not_bypass_platform_approval(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        backend_agent = db.exec(select(Agent).where(Agent.role == "backend")).one()
        session = db.exec(select(Session)).first()
        upsert_runtime_config(
            db,
            session.workspace_id,
            {
                "backend": RuntimeRoleConfig(
                    role="backend",
                    agent_profile_id="agent-backend",
                    provider_id="local-codex-cli",
                    adapter_type="codex",
                    mode="backend",
                    enabled=True,
                    fallback_policy="explicit_only",
                )
            },
        )
        platform_task = Task(
            session_id=session.id,
            title="Platform maintenance with runtime backend config",
            intent_type="platform_maintenance",
            status="pending",
            assigned_agent_id=backend_agent.id,
            plan_json=json.dumps(
                {
                    "assignedRole": "backend",
                    "targetId": AGENTHUB_PLATFORM_TARGET_ID,
                    "platformMode": True,
                    "requiresApproval": True,
                    "originalRequest": "platform mode: adjust AgentHub API",
                },
                separators=(",", ":"),
            ),
        )
        db.add(platform_task)
        db.commit()
        db.refresh(platform_task)

        task_run = create_task_run(db, platform_task.id)
        metrics = json.loads(task_run.metrics_json)

        assert task_run.state == "waiting_approval"
        assert metrics["runtimeConfigResolution"]["providerId"] == "local-codex-cli"
        assert metrics["providerAssignment"]["source"] == "runtime_config"


def test_contract_aware_review_validates_backend_and_frontend_targets(
    client: TestClient,
) -> None:
    contract = {
        "contractId": "contract-mini_crm_contacts",
        "appName": "Mini CRM Contacts",
        "backendTarget": "apps/demo-api",
        "frontendTarget": "apps/demo",
        "demoApiBaseUrl": "http://127.0.0.1:5174",
    }
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps(
            {
                "assignedRole": "frontend",
                "appContract": contract,
                "contractId": contract["contractId"],
                "safeTarget": "apps/demo/src",
                "files": ["apps/demo/src/App.tsx"],
            },
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        task_run = create_task_run(db, task.id)
        transition_task_run(db, task_run.id, "completed")
        diff_artifact = Artifact(
            task_run_id=task_run.id,
            artifact_type="diff",
            title="Git diff",
            status="ready",
            meta_json="{}",
        )
        db.add(diff_artifact)
        db.commit()
        db.refresh(diff_artifact)
        diff = Diff(
            artifact_id=diff_artifact.id,
            base_ref="base",
            head_ref="head+worktree",
            patch_text=(
                "diff --git a/apps/demo-api/app/main.py b/apps/demo-api/app/main.py\n"
                "diff --git a/apps/demo/src/App.tsx b/apps/demo/src/App.tsx\n"
            ),
            changed_files_json=json.dumps(
                ["apps/demo-api/app/main.py", "apps/demo/src/App.tsx"],
                separators=(",", ":"),
            ),
            stats_json=json.dumps({"filesChanged": 2}, separators=(",", ":")),
        )
        db.add(diff)
        db.commit()

        review = create_scripted_review_for_task_run(db, task_run.id)

    assert review.status == "passed"
    assert review.risk_level == "low"
    assert review.findings == []
    assert "contract-mini_crm_contacts" in review.summary


def test_contract_aware_review_warns_on_platform_api_base_mismatch(
    client: TestClient,
) -> None:
    contract = {
        "contractId": "contract-mini_crm_contacts",
        "appName": "Mini CRM Contacts",
        "backendTarget": "apps/demo-api",
        "frontendTarget": "apps/demo",
        "demoApiBaseUrl": "http://127.0.0.1:5174",
    }
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps(
            {
                "assignedRole": "frontend",
                "appContract": contract,
                "contractId": contract["contractId"],
                "safeTarget": "apps/demo/src",
                "files": ["apps/demo/src/App.tsx"],
            },
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        task_run = create_task_run(db, task.id)
        transition_task_run(db, task_run.id, "completed")
        diff_artifact = Artifact(
            task_run_id=task_run.id,
            artifact_type="diff",
            title="Git diff",
            status="ready",
            meta_json="{}",
        )
        db.add(diff_artifact)
        db.commit()
        db.refresh(diff_artifact)
        diff = Diff(
            artifact_id=diff_artifact.id,
            base_ref="base",
            head_ref="head+worktree",
            patch_text=(
                "diff --git a/apps/demo-api/app/main.py b/apps/demo-api/app/main.py\n"
                "diff --git a/apps/demo/src/App.tsx b/apps/demo/src/App.tsx\n"
                '+const API_BASE = "http://localhost:8000";\n'
            ),
            changed_files_json=json.dumps(
                ["apps/demo-api/app/main.py", "apps/demo/src/App.tsx"],
                separators=(",", ":"),
            ),
            stats_json=json.dumps({"filesChanged": 2}, separators=(",", ":")),
        )
        db.add(diff)
        db.commit()

        review = create_scripted_review_for_task_run(db, task_run.id)

    assert review.status == "warning"
    assert review.risk_level == "medium"
    assert any("http://localhost:8000" in finding["message"] for finding in review.findings)
    assert any("http://127.0.0.1:5174" in suggestion for suggestion in review.suggested_changes)


def test_target_aware_review_fails_on_platform_code_mutation(
    client: TestClient,
) -> None:
    contract = {
        "contractId": "contract-mini_crm_contacts",
        "appName": "Mini CRM Contacts",
        "frontendTargetId": DEMO_FRONTEND_TARGET_ID,
        "backendTargetId": DEMO_BACKEND_TARGET_ID,
        "backendTarget": "apps/demo-api",
        "frontendTarget": "apps/demo",
        "demoApiBaseUrl": "http://127.0.0.1:5174",
    }
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps(
            {
                "assignedRole": "backend",
                "targetId": DEMO_BACKEND_TARGET_ID,
                "backendTargetId": DEMO_BACKEND_TARGET_ID,
                "frontendTargetId": DEMO_FRONTEND_TARGET_ID,
                "appContract": contract,
                "contractId": contract["contractId"],
                "safeTarget": "apps/demo-api",
            },
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        task_run = create_task_run(db, task.id)
        transition_task_run(db, task_run.id, "completed")
        diff_artifact = Artifact(
            task_run_id=task_run.id,
            artifact_type="diff",
            title="Git diff",
            status="ready",
            meta_json="{}",
        )
        db.add(diff_artifact)
        db.commit()
        db.refresh(diff_artifact)
        diff = Diff(
            artifact_id=diff_artifact.id,
            base_ref="base",
            head_ref="head+worktree",
            patch_text="diff --git a/apps/api/app/main.py b/apps/api/app/main.py\n",
            changed_files_json=json.dumps(["apps/api/app/main.py"], separators=(",", ":")),
            stats_json=json.dumps({"filesChanged": 1}, separators=(",", ":")),
        )
        db.add(diff)
        db.commit()

        review = create_scripted_review_for_task_run(db, task_run.id)

    assert review.status == "failed"
    assert review.risk_level == "high"
    assert any("denied target path apps/api/app/main.py" in finding["message"] for finding in review.findings)


def test_target_aware_review_detects_task_target_mismatch(
    client: TestClient,
) -> None:
    contract = {
        "contractId": "contract-mini_crm_contacts",
        "appName": "Mini CRM Contacts",
        "frontendTargetId": DEMO_FRONTEND_TARGET_ID,
        "backendTargetId": DEMO_BACKEND_TARGET_ID,
        "backendTarget": "apps/demo-api",
        "frontendTarget": "apps/demo",
        "demoApiBaseUrl": "http://127.0.0.1:5174",
    }
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps(
            {
                "assignedRole": "backend",
                "targetId": DEMO_FRONTEND_TARGET_ID,
                "backendTargetId": DEMO_BACKEND_TARGET_ID,
                "frontendTargetId": DEMO_FRONTEND_TARGET_ID,
                "appContract": contract,
                "contractId": contract["contractId"],
            },
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        with pytest.raises(TaskRunLifecycleError, match="does not support target"):
            create_task_run(db, task.id)


def test_transition_helper_rejects_unknown_states(client: TestClient) -> None:
    run = client.post(f"/tasks/{task_id()}/runs").json()

    with db_from_override() as db:
        with pytest.raises(ValueError, match="Unsupported TaskRun state"):
            transition_task_run(db, run["id"], "sleeping")


def test_interrupt_running_task_run_updates_task_and_preserves_history(
    client: TestClient,
) -> None:
    run = client.post(f"/tasks/{task_id()}/runs").json()

    response = client.post(f"/task-runs/{run['id']}/interrupt")

    assert response.status_code == 200
    interrupted = response.json()
    assert interrupted["id"] == run["id"]
    assert interrupted["state"] == "interrupted"
    assert interrupted["errorCode"] == "TASK_RUN_INTERRUPTED"

    task_response = client.get(f"/sessions/{interrupted['sessionId']}/tasks")
    task = task_response.json()[0]
    assert task["status"] == "interrupted"
    assert [task_run["id"] for task_run in task["taskRuns"]] == [run["id"]]
    assert task["taskRuns"][0]["state"] == "interrupted"


def test_retry_failed_or_interrupted_run_creates_new_history_row(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps(
            {
                "targetId": DEMO_FRONTEND_TARGET_ID,
                "safeTarget": "apps/demo/src",
                "files": ["apps/demo/src/App.tsx"],
            },
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()

    original = client.post(f"/tasks/{task_id()}/runs").json()
    client.post(f"/task-runs/{original['id']}/interrupt")

    retry_response = client.post(f"/task-runs/{original['id']}/retry")

    assert retry_response.status_code == 201
    retried = retry_response.json()
    assert retried["id"] != original["id"]
    assert retried["state"] == "queued"
    assert retried["adapterType"] == "codex"
    assert retried["metricsJson"]["retryOfRunId"] == original["id"]
    assert retried["metricsJson"]["previousRunId"] == original["id"]
    assert retried["metricsJson"]["retryMode"] == "current_state"
    assert retried["metricsJson"]["failureSummary"]["state"] == "interrupted"
    assert retried["metricsJson"]["dirtyWorktreeDecision"]["status"] == "safe"
    assert retried["metricsJson"]["checkpointId"] == original["id"]

    with db_from_override() as db:
        previous = db.get(TaskRun, original["id"])
        runs = db.exec(select(TaskRun).where(TaskRun.task_id == previous.task_id)).all()
        assert previous.state == "interrupted"
        assert len(runs) == 2


def test_retry_failed_run_schedules_background_execution(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps(
            {
                "targetId": DEMO_FRONTEND_TARGET_ID,
                "safeTarget": "apps/demo/src",
                "files": ["apps/demo/src/App.tsx"],
            },
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        original = create_task_run(db, task.id)
        transition_task_run(
            db,
            original.id,
            "failed",
            error_code="CODEX_TEST_FAILURE",
            error_message="Codex failed before retry.",
        )
        original_id = original.id

    scheduled: list[str] = []

    def fake_schedule_task_run_execution(
        background_tasks,
    ) -> None:
        scheduled.append("worker")

    monkeypatch.setattr(
        main_module,
        "schedule_task_run_execution",
        fake_schedule_task_run_execution,
    )

    response = client.post(f"/task-runs/{original_id}/retry")

    assert response.status_code == 201
    retried = response.json()
    assert retried["state"] == "queued"
    assert scheduled == ["worker"]


def test_run_endpoints_use_shared_execution_scheduler(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scheduled: list[str] = []

    def fake_schedule_task_run_execution(
        background_tasks,
    ) -> None:
        scheduled.append("worker")

    monkeypatch.setattr(
        main_module,
        "schedule_task_run_execution",
        fake_schedule_task_run_execution,
    )

    response = client.post(f"/tasks/{task_id()}/runs")

    assert response.status_code == 201
    manual = response.json()
    assert scheduled == ["worker"]

    with db_from_override() as db:
        transition_task_run(
            db,
            manual["id"],
            "failed",
            error_code="CODEX_TEST_FAILURE",
            error_message="Codex failed before retry.",
        )

    retry_response = client.post(f"/task-runs/{manual['id']}/retry")

    assert retry_response.status_code == 201
    assert retry_response.json()["state"] == "queued"
    assert scheduled == ["worker", "worker"]


def test_execute_task_run_registers_with_supervisor(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_runs_module,
        "CAPABILITIES_BY_ADAPTER",
        {
            **task_runs_module.CAPABILITIES_BY_ADAPTER,
            "codex": (),
        },
    )
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"writeMode": False})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)

        class CompletingAdapter:
            def getCapabilities(self) -> AdapterCapabilities:
                return AdapterCapabilities(
                    supportsStreaming=True,
                    supportsInterrupt=True,
                    supportsApproval=False,
                    supportsFileEdit=False,
                    supportsShellCommand=False,
                    supportsDiffArtifact=False,
                    supportsPreviewArtifact=False,
                    supportsNetwork=False,
                )

            async def createRun(self, request):
                return AdapterRun(adapterRunId="adapter-run-test")

            async def streamEvents(self, adapter_run_id):
                yield {
                    "type": "error",
                    "payload": {
                        "code": "TEST_ADAPTER_STOP",
                        "message": "stop before artifact collection",
                    },
                }

            async def interrupt(self, adapter_run_id):
                return None

            async def approve(self, adapter_run_id, approval):
                return None

            async def collectArtifacts(self, adapter_run_id):
                return []

            async def cleanup(self, adapter_run_id):
                return None

        class RecordingSupervisor(run_engine_module.RunSupervisor):
            def __init__(self) -> None:
                super().__init__()
                self.registered: list[tuple[str, str]] = []
                self.unregistered: list[str] = []

            def register(
                self,
                *,
                task_run_id: str,
                adapter_type: str,
                adapter_run_id: Optional[str] = None,
                adapter=None,
            ):
                self.registered.append((task_run_id, adapter_type))
                return super().register(
                    task_run_id=task_run_id,
                    adapter_type=adapter_type,
                    adapter_run_id=adapter_run_id,
                    adapter=adapter,
                )

            def unregister(self, task_run_id: str, *, expected=None):
                self.unregistered.append(task_run_id)
                return super().unregister(task_run_id, expected=expected)

        supervisor = RecordingSupervisor()

        import asyncio

        asyncio.run(
            run_engine_module.execute_task_run(
                db,
                run,
                adapter_type="scripted_mock",
                adapter=CompletingAdapter(),
                supervisor=supervisor,
            )
        )

        assert supervisor.registered == [(run.id, "scripted_mock")]
        assert supervisor.unregistered == [run.id]


def test_create_run_gate_rejects_readonly_task_mutated_to_write_by_capabilities(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_runs_module,
        "CAPABILITIES_BY_ADAPTER",
        {
            **task_runs_module.CAPABILITIES_BY_ADAPTER,
            "scripted_mock": ("review",),
        },
    )
    with db_from_override() as db:
        task = db.get(Task, task_id())
        qa = db.exec(select(Agent).where(Agent.role == "qa")).one()
        task.intent_type = "review"
        task.assigned_agent_id = qa.id
        task.plan_json = json.dumps(
            {"targetId": DEMO_FRONTEND_TARGET_ID, "readOnly": True},
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        create_run_calls = 0

        class MutatingCapabilitiesAdapter:
            def getCapabilities(self) -> AdapterCapabilities:
                current = db.get(Task, task.id)
                current.intent_type = "frontend_change"
                current.plan_json = json.dumps(
                    {"targetId": DEMO_FRONTEND_TARGET_ID},
                    separators=(",", ":"),
                )
                db.add(current)
                db.commit()
                return AdapterCapabilities(
                    supportsStreaming=True,
                    supportsInterrupt=True,
                    supportsApproval=False,
                    supportsFileEdit=True,
                    supportsShellCommand=False,
                    supportsDiffArtifact=False,
                    supportsPreviewArtifact=False,
                    supportsNetwork=False,
                )

            async def createRun(self, request):
                nonlocal create_run_calls
                create_run_calls += 1
                return AdapterRun(adapterRunId="adapter-run-must-not-start")

            async def streamEvents(self, adapter_run_id):
                yield {"type": "completed", "payload": {}}

            async def interrupt(self, adapter_run_id):
                return None

            async def approve(self, adapter_run_id, approval):
                return None

            async def collectArtifacts(self, adapter_run_id):
                return []

            async def cleanup(self, adapter_run_id):
                return None

        import asyncio

        asyncio.run(
            run_engine_module.execute_task_run(
                db,
                run,
                adapter_type="scripted_mock",
                adapter=MutatingCapabilitiesAdapter(),
            )
        )
        stored = db.get(TaskRun, run.id)
        metrics = json.loads(stored.metrics_json)
        artifacts = db.exec(
            select(Artifact).where(Artifact.task_run_id == run.id)
        ).all()

    assert create_run_calls == 0
    assert stored.state == "failed"
    assert stored.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert stored.adapter_run_id is None
    assert "taskRunExecutionAccessBinding" not in metrics
    assert "scopeBaseline" not in metrics.get("preRunCheckpoint", {})
    assert artifacts == []


def test_readonly_review_with_scripted_mock_enqueues_write(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        qa = db.exec(select(Agent).where(Agent.role == "qa")).one()
        task = db.get(Task, task_id())
        task.intent_type = "review"
        task.assigned_agent_id = qa.id
        task.plan_json = json.dumps(
            {"targetId": DEMO_FRONTEND_TARGET_ID, "readOnly": True},
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        queue_entry = entry_for_task_run(db, run.id)
        metrics = json.loads(run.metrics_json)

    assert metrics["adapterType"] == "scripted_mock"
    assert queue_entry.access_mode == "write"


def test_background_prepare_rejects_readonly_queue_drifted_to_write(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_runs_module,
        "CAPABILITIES_BY_ADAPTER",
        {
            **task_runs_module.CAPABILITIES_BY_ADAPTER,
            "scripted_mock": ("review",),
        },
    )
    with db_from_override() as db:
        qa = db.exec(select(Agent).where(Agent.role == "qa")).one()
        task = db.get(Task, task_id())
        task.intent_type = "review"
        task.assigned_agent_id = qa.id
        task.plan_json = json.dumps(
            {"targetId": DEMO_FRONTEND_TARGET_ID, "readOnly": True},
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        queue_entry = entry_for_task_run(db, run.id)
        assert queue_entry is not None
        assert queue_entry.access_mode == "readonly"
        assert "preRunCheckpoint" not in json.loads(run.metrics_json)

        queue_entry.access_mode = "write"
        queue_entry.target_lock_key = (
            run_engine_module.target_lock_key_for_target(
                DEMO_FRONTEND_TARGET_ID
            )
        )
        db.add(queue_entry)
        db.commit()

        import asyncio

        executed = asyncio.run(
            run_engine_module.execute_task_run_background(
                db,
                run.id,
                "scripted_mock",
                worker_id="worker:readonly-queue-write-drift",
            )
        )
        stored = db.get(TaskRun, run.id)
        internal_metrics = task_runs_module.internal_metrics_for_run(stored)
        held_locks = db.exec(
            select(TargetLock).where(
                TargetLock.task_run_id == run.id,
                TargetLock.state == "held",
            )
        ).all()
        artifacts = db.exec(
            select(Artifact).where(Artifact.task_run_id == run.id)
        ).all()

    assert executed is True
    assert stored.state == "failed"
    assert stored.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert stored.adapter_run_id is None
    assert held_locks == []
    assert "preRunCheckpoint" not in internal_metrics
    assert "taskRunExecutionAccessBinding" not in internal_metrics
    assert artifacts == []


@pytest.mark.parametrize(
    "adapter_type_case",
    ("missing", "non-string", "blank", "unknown", "malformed-json"),
)
def test_background_prepare_rejects_invalid_persisted_adapter_type_provenance(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    adapter_type_case: str,
) -> None:
    monkeypatch.setattr(
        task_runs_module,
        "CAPABILITIES_BY_ADAPTER",
        {
            **task_runs_module.CAPABILITIES_BY_ADAPTER,
            "scripted_mock": ("review",),
        },
    )
    with db_from_override() as db:
        qa = db.exec(select(Agent).where(Agent.role == "qa")).one()
        task = db.get(Task, task_id())
        task.intent_type = "review"
        task.assigned_agent_id = qa.id
        task.plan_json = json.dumps(
            {"targetId": DEMO_FRONTEND_TARGET_ID, "readOnly": True},
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        queue_entry = entry_for_task_run(db, run.id)
        assert queue_entry is not None
        assert queue_entry.access_mode == "readonly"
        assert "preRunCheckpoint" not in json.loads(run.metrics_json)

        metrics = json.loads(run.metrics_json)
        if adapter_type_case == "missing":
            metrics.pop("adapterType")
        elif adapter_type_case == "non-string":
            metrics["adapterType"] = 7
        elif adapter_type_case == "blank":
            metrics["adapterType"] = " "
        elif adapter_type_case == "unknown":
            metrics["adapterType"] = "unknown_adapter"
        else:
            assert adapter_type_case == "malformed-json"
        run.metrics_json = (
            "{"
            if adapter_type_case == "malformed-json"
            else json.dumps(metrics, separators=(",", ":"))
        )
        qa.adapter_type = "codex"
        queue_entry.access_mode = "write"
        queue_entry.target_lock_key = (
            run_engine_module.target_lock_key_for_target(
                DEMO_FRONTEND_TARGET_ID
            )
        )
        db.add(qa)
        db.add(run)
        db.add(queue_entry)
        db.commit()

        import asyncio

        executed = asyncio.run(
            run_engine_module.execute_task_run_background(
                db,
                run.id,
                "scripted_mock",
                worker_id=f"worker:invalid-adapter-type:{adapter_type_case}",
            )
        )
        stored = db.get(TaskRun, run.id)
        internal_metrics = task_runs_module.internal_metrics_for_run(stored)
        held_locks = db.exec(
            select(TargetLock).where(
                TargetLock.task_run_id == run.id,
                TargetLock.state == "held",
            )
        ).all()
        artifacts = db.exec(
            select(Artifact).where(Artifact.task_run_id == run.id)
        ).all()

    assert executed is True
    assert stored.state == "failed"
    assert stored.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert stored.adapter_run_id is None
    assert held_locks == []
    assert "preRunCheckpoint" not in internal_metrics
    assert "taskRunExecutionAccessBinding" not in internal_metrics
    assert artifacts == []


def _create_controlled_readonly_review_run(
    db: DbSession,
    monkeypatch: pytest.MonkeyPatch,
) -> TaskRun:
    monkeypatch.setattr(
        task_runs_module,
        "CAPABILITIES_BY_ADAPTER",
        {
            **task_runs_module.CAPABILITIES_BY_ADAPTER,
            "scripted_mock": ("review",),
        },
    )
    qa = db.exec(select(Agent).where(Agent.role == "qa")).one()
    task = db.get(Task, task_id())
    task.intent_type = "review"
    task.assigned_agent_id = qa.id
    task.plan_json = json.dumps(
        {"targetId": DEMO_FRONTEND_TARGET_ID, "readOnly": True},
        separators=(",", ":"),
    )
    db.add(task)
    db.commit()
    run = create_task_run(db, task.id)
    queue_entry = entry_for_task_run(db, run.id)
    assert queue_entry is not None
    assert queue_entry.access_mode == "readonly"
    assert queue_entry.target_lock_key is None
    assert "preRunCheckpoint" not in json.loads(run.metrics_json)
    return run


@pytest.mark.parametrize(
    "file_edit_capability_reads",
    [(True, True), (True, False), (False, True)],
    ids=["stable-mutating", "drift-to-readonly", "drift-to-mutating"],
)
def test_create_run_gate_rejects_mutating_or_drifting_readonly_capability(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    file_edit_capability_reads: tuple[bool, bool],
) -> None:
    with db_from_override() as db:
        run = _create_controlled_readonly_review_run(db, monkeypatch)
        create_run_calls = 0
        capability_read_count = 0
        capabilities_model = AdapterCapabilities(
            supportsStreaming=True,
            supportsInterrupt=True,
            supportsApproval=False,
            supportsFileEdit=file_edit_capability_reads[0],
            supportsShellCommand=False,
            supportsDiffArtifact=False,
            supportsPreviewArtifact=False,
            supportsNetwork=False,
        )

        class FileEditingAdapter:
            def getCapabilities(self) -> AdapterCapabilities:
                nonlocal capability_read_count
                supports_file_edit = file_edit_capability_reads[
                    min(capability_read_count, 1)
                ]
                capability_read_count += 1
                capabilities_model.supports_file_edit = supports_file_edit
                return capabilities_model

            async def createRun(self, request):
                nonlocal create_run_calls
                create_run_calls += 1
                return AdapterRun(adapterRunId="adapter-run-must-not-start")

            async def streamEvents(self, adapter_run_id):
                yield {
                    "type": "error",
                    "payload": {
                        "code": "MUTATING_READONLY_ADAPTER_STARTED",
                        "message": "The mutating readonly adapter started.",
                    },
                }

            async def interrupt(self, adapter_run_id):
                return None

            async def approve(self, adapter_run_id, approval):
                return None

            async def collectArtifacts(self, adapter_run_id):
                return []

            async def cleanup(self, adapter_run_id):
                return None

        import asyncio

        asyncio.run(
            run_engine_module.execute_task_run(
                db,
                run,
                adapter_type="scripted_mock",
                adapter=FileEditingAdapter(),
            )
        )
        stored = db.get(TaskRun, run.id)
        internal_metrics = task_runs_module.internal_metrics_for_run(stored)

    assert create_run_calls == 0
    assert capability_read_count == 2
    assert stored.state == "failed"
    assert stored.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert stored.adapter_run_id is None
    assert "taskRunExecutionAccessBinding" not in internal_metrics


@pytest.mark.parametrize(
    "malformed_capability_reads",
    [(True, True), (False, True)],
    ids=["malformed-both-reads", "malformed-launch-read"],
)
def test_create_run_gate_rejects_malformed_readonly_capabilities(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    malformed_capability_reads: tuple[bool, bool],
) -> None:
    with db_from_override() as db:
        run = _create_controlled_readonly_review_run(db, monkeypatch)
        create_run_calls = 0
        capability_read_count = 0
        valid_capabilities = AdapterCapabilities(
            supportsStreaming=True,
            supportsInterrupt=True,
            supportsApproval=False,
            supportsFileEdit=False,
            supportsShellCommand=False,
            supportsDiffArtifact=False,
            supportsPreviewArtifact=False,
            supportsNetwork=False,
        )
        malformed_capabilities = valid_capabilities.model_copy(deep=True)
        malformed_capabilities.supports_file_edit = None
        malformed_capabilities.supports_shell_command = None

        class MalformedCapabilitiesAdapter:
            def getCapabilities(self) -> AdapterCapabilities:
                nonlocal capability_read_count
                malformed = malformed_capability_reads[
                    min(capability_read_count, 1)
                ]
                capability_read_count += 1
                return malformed_capabilities if malformed else valid_capabilities

            async def createRun(self, request):
                nonlocal create_run_calls
                create_run_calls += 1
                return AdapterRun(adapterRunId="malformed-adapter-must-not-start")

            async def streamEvents(self, adapter_run_id):
                yield {
                    "type": "error",
                    "payload": {
                        "code": "MALFORMED_CAPABILITIES_ADAPTER_STARTED",
                        "message": "The malformed capabilities adapter started.",
                    },
                }

            async def interrupt(self, adapter_run_id):
                return None

            async def approve(self, adapter_run_id, approval):
                return None

            async def collectArtifacts(self, adapter_run_id):
                return []

            async def cleanup(self, adapter_run_id):
                return None

        import asyncio

        asyncio.run(
            run_engine_module.execute_task_run(
                db,
                run,
                adapter_type="scripted_mock",
                adapter=MalformedCapabilitiesAdapter(),
            )
        )
        stored = db.get(TaskRun, run.id)
        internal_metrics = task_runs_module.internal_metrics_for_run(stored)

    expected_reads = 1 if malformed_capability_reads[0] else 2
    assert create_run_calls == 0
    assert capability_read_count == expected_reads
    assert stored.state == "failed"
    assert stored.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert stored.adapter_run_id is None
    assert "taskRunExecutionAccessBinding" not in internal_metrics


def test_real_scripted_mock_readonly_review_uses_write_scope(
    client: TestClient,
    tmp_path: Path,
) -> None:
    source_app = Path(__file__).resolve().parents[2] / "demo" / "src" / "App.tsx"
    worktree_path = tmp_path / "scripted-readonly-review"
    app_path = worktree_path / "apps" / "demo" / "src" / "App.tsx"
    app_path.parent.mkdir(parents=True)
    original_source = source_app.read_text()
    app_path.write_text(original_source)
    subprocess.run(["git", "init"], cwd=worktree_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=worktree_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=worktree_path,
        check=True,
    )
    subprocess.run(["git", "add", "apps/demo/src/App.tsx"], cwd=worktree_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=worktree_path,
        check=True,
        capture_output=True,
    )

    with db_from_override() as db:
        qa = db.exec(select(Agent).where(Agent.role == "qa")).one()
        task = db.get(Task, task_id())
        session = db.get(Session, task.session_id)
        session.worktree_path = str(worktree_path)
        task.title = "Inspect demo output"
        task.intent_type = "review"
        task.assigned_agent_id = qa.id
        task.plan_json = json.dumps(
            {"targetId": DEMO_FRONTEND_TARGET_ID, "readOnly": True},
            separators=(",", ":"),
        )
        db.add(session)
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        assert run.worktree_path == str(worktree_path)
        run_id = run.id

        import asyncio

        executed = asyncio.run(
            run_engine_module.execute_task_run_background(
                db,
                run_id,
                "scripted_mock",
                worker_id="worker:scripted-readonly-review",
            )
        )
        stored = db.get(TaskRun, run_id)
        queue_entry = entry_for_task_run(db, run_id)
        internal_metrics = task_runs_module.internal_metrics_for_run(stored)
        public_metrics = task_runs_module.metrics_for_run(stored)
        event_types = [
            event.event_type
            for event in db.exec(
                select(TaskRunEvent)
                .where(TaskRunEvent.task_run_id == run_id)
                .order_by(TaskRunEvent.sequence)
            ).all()
        ]
    assert executed is True
    assert app_path.read_text() != original_source, (
        stored.state,
        stored.error_code,
        stored.error_message,
        queue_entry.state,
        sorted(internal_metrics),
        event_types,
    )
    assert stored.state == "completed"
    assert queue_entry.state == "completed"
    assert queue_entry.access_mode == "write"
    assert internal_metrics["taskRunExecutionAccessBinding"]["accessMode"] == "write"
    assert internal_metrics["taskRunScopeDecision"]["status"] == "passed"
    assert "target_lock.acquired" in event_types
    assert "task.scope_validation.passed" in event_types
    assert "taskRunExecutionAccessBinding" not in public_metrics


def test_real_readonly_create_run_binding_allows_completion_and_stays_internal(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_runs_module,
        "CAPABILITIES_BY_ADAPTER",
        {
            **task_runs_module.CAPABILITIES_BY_ADAPTER,
            "scripted_mock": ("review",),
        },
    )
    with db_from_override() as db:
        task = db.get(Task, task_id())
        qa = db.exec(select(Agent).where(Agent.role == "qa")).one()
        task.intent_type = "review"
        task.assigned_agent_id = qa.id
        task.plan_json = json.dumps(
            {"targetId": DEMO_FRONTEND_TARGET_ID, "readOnly": True},
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)

        class CompletingReadonlyAdapter:
            def getCapabilities(self) -> AdapterCapabilities:
                return AdapterCapabilities(
                    supportsStreaming=True,
                    supportsInterrupt=True,
                    supportsApproval=False,
                    supportsFileEdit=False,
                    supportsShellCommand=False,
                    supportsDiffArtifact=False,
                    supportsPreviewArtifact=False,
                    supportsNetwork=False,
                )

            async def createRun(self, request):
                return AdapterRun(adapterRunId="adapter-run-readonly-bound")

            async def streamEvents(self, adapter_run_id):
                yield {"type": "completed", "payload": {}}

            async def interrupt(self, adapter_run_id):
                return None

            async def approve(self, adapter_run_id, approval):
                return None

            async def collectArtifacts(self, adapter_run_id):
                return []

            async def cleanup(self, adapter_run_id):
                return None

        monkeypatch.setattr(
            run_engine_module, "collect_task_run_diff", lambda db, run_id: None
        )
        monkeypatch.setattr(
            run_engine_module,
            "create_scripted_review_for_task_run",
            lambda db, run_id: None,
        )
        monkeypatch.setattr(
            run_engine_module,
            "refresh_session_ledger_for_task_run",
            lambda db, run_id: None,
        )
        monkeypatch.setattr(
            run_engine_module,
            "_complete_ready_pipeline_review_tasks",
            lambda db, task_id: [],
        )
        monkeypatch.setattr(
            run_engine_module,
            "_maybe_auto_preview_and_mock_deploy",
            lambda db, task_run: None,
        )

        async def no_downstream(db, task_id):
            return None

        monkeypatch.setattr(
            run_engine_module, "_auto_start_next_pipeline_task", no_downstream
        )

        import asyncio

        event.listen(
            db.get_bind(),
            "before_cursor_execute",
            _fail_if_readonly_touches_target_lock,
        )
        try:
            asyncio.run(
                run_engine_module.execute_task_run(
                    db,
                    run,
                    adapter_type="scripted_mock",
                    adapter=CompletingReadonlyAdapter(),
                )
            )
        finally:
            event.remove(
                db.get_bind(),
                "before_cursor_execute",
                _fail_if_readonly_touches_target_lock,
            )
        stored = db.get(TaskRun, run.id)
        internal_metrics = task_runs_module.internal_metrics_for_run(stored)
        public_metrics = task_runs_module.metrics_for_run(stored)

    binding = internal_metrics["taskRunExecutionAccessBinding"]
    assert stored.state == "completed"
    assert stored.adapter_run_id == "adapter-run-readonly-bound"
    assert stored.started_at is not None
    assert binding["taskRunId"] == stored.id
    assert binding["taskId"] == stored.task_id
    assert binding["accessMode"] == "readonly"
    assert binding["executionAttemptId"]
    assert "taskRunExecutionAccessBinding" not in public_metrics


def test_interrupt_supervised_task_run_calls_adapter_interrupt() -> None:
    class InterruptRecordingAdapter:
        def __init__(self) -> None:
            self.interrupted: list[str] = []

        async def interrupt(self, adapter_run_id: str) -> None:
            self.interrupted.append(adapter_run_id)

    adapter = InterruptRecordingAdapter()
    supervisor = run_engine_module.RunSupervisor()
    supervisor.register(
        task_run_id="run-1",
        adapter_type="codex",
        adapter_run_id="adapter-1",
        adapter=adapter,
    )

    import asyncio

    interrupted = asyncio.run(
        run_engine_module.interrupt_supervised_task_run(
            "run-1",
            supervisor=supervisor,
        )
    )

    assert interrupted is True
    assert adapter.interrupted == ["adapter-1"]


def test_supervisor_generation_loss_notification_is_thread_safe_during_loop_bind() -> None:
    marker_released_generation_lock = Event()
    allow_marker_to_continue = Event()
    waiter_released_generation_lock = Event()
    waiter_entered_event_wait = Event()
    waiter_completed = Event()
    loop_ready = Event()
    marker_errors: list[BaseException] = []
    waiter_errors: list[BaseException] = []
    loop_state: dict[str, object] = {}
    fallback_cleanup_used = False

    class ThreadCheckingEvent(asyncio.Event):
        def __init__(self) -> None:
            super().__init__()
            self.loop_thread_id: int | None = None

        async def wait(self) -> bool:
            self.loop_thread_id = get_ident()
            waiter_entered_event_wait.set()
            return await super().wait()

        def set(self) -> None:
            if (
                self.loop_thread_id is not None
                and self.loop_thread_id != get_ident()
            ):
                raise RuntimeError("cross-thread asyncio.Event.set")
            super().set()

    class PausingGenerationLock:
        def __init__(self, inner_lock) -> None:
            self.inner_lock = inner_lock
            self.marker_thread_id: int | None = None

        def __enter__(self):
            self.inner_lock.acquire()
            return self

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            self.inner_lock.release()
            if get_ident() == self.marker_thread_id:
                marker_released_generation_lock.set()
                assert allow_marker_to_continue.wait(timeout=1)
            else:
                waiter_released_generation_lock.set()

    supervisor = run_engine_module.RunSupervisor()
    generation_a = supervisor.register(
        task_run_id="thread-race-run",
        adapter_type="scripted_mock",
    )
    generation_a._generation.ownership_lost = ThreadCheckingEvent()
    controlled_lock = PausingGenerationLock(generation_a._generation.lock)
    generation_a._generation.lock = controlled_lock

    def replace_generation() -> None:
        controlled_lock.marker_thread_id = get_ident()
        try:
            supervisor.register(
                task_run_id="thread-race-run",
                adapter_type="scripted_mock",
            )
        except BaseException as exc:
            marker_errors.append(exc)

    def wait_for_generation_loss() -> None:
        async def wait() -> None:
            loop = asyncio.get_running_loop()
            loop.set_debug(True)
            loop_state["loop"] = loop
            loop_state["task"] = asyncio.current_task()
            loop_ready.set()
            await generation_a.wait_until_ownership_lost()

        try:
            asyncio.run(wait())
        except BaseException as exc:
            waiter_errors.append(exc)
        finally:
            waiter_completed.set()

    marker_thread = Thread(target=replace_generation, daemon=True)
    waiter_thread = Thread(target=wait_for_generation_loss, daemon=True)
    marker_thread.start()
    assert marker_released_generation_lock.wait(timeout=1)
    waiter_thread.start()
    assert loop_ready.wait(timeout=1)
    assert waiter_released_generation_lock.wait(timeout=1)

    deadline = monotonic() + 1
    while (
        not waiter_completed.is_set()
        and not waiter_entered_event_wait.is_set()
        and monotonic() < deadline
    ):
        waiter_completed.wait(timeout=0.01)
    assert waiter_completed.is_set() or waiter_entered_event_wait.is_set()

    allow_marker_to_continue.set()
    marker_thread.join(timeout=1)
    assert marker_thread.is_alive() is False
    completed_from_generation_b_mark_lost = waiter_completed.wait(timeout=1)
    if not completed_from_generation_b_mark_lost:
        fallback_cleanup_used = True
        loop = loop_state["loop"]
        assert isinstance(loop, asyncio.AbstractEventLoop)
        loop.call_soon_threadsafe(generation_a._generation.ownership_lost.set)
    waiter_thread.join(timeout=1)
    assert waiter_thread.is_alive() is False

    generation_b = supervisor.active("thread-race-run")
    assert marker_errors == []
    assert waiter_errors == []
    assert completed_from_generation_b_mark_lost is True
    assert fallback_cleanup_used is False
    assert waiter_completed.is_set()
    assert generation_b is not None
    assert generation_b is not generation_a
    assert generation_b._generation.ownership_lost.is_set() is False
    assert (
        supervisor.unregister("thread-race-run", expected=generation_a) is None
    )
    assert supervisor.active("thread-race-run") is generation_b


def test_interrupt_endpoint_attempts_supervisor_interrupt(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        run = create_task_run(db, task_id())
        run_id = run.id

    interrupted: list[str] = []

    async def fake_interrupt_supervised_task_run(task_run_id: str) -> bool:
        interrupted.append(task_run_id)
        return True

    monkeypatch.setattr(
        main_module,
        "interrupt_supervised_task_run",
        fake_interrupt_supervised_task_run,
    )

    response = client.post(f"/task-runs/{run_id}/interrupt")

    assert response.status_code == 200
    assert response.json()["state"] == "interrupted"
    assert interrupted == [run_id]


def test_execute_task_run_timeout_interrupts_and_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_runs_module,
        "CAPABILITIES_BY_ADAPTER",
        {
            **task_runs_module.CAPABILITIES_BY_ADAPTER,
            "scripted_mock": ("review",),
        },
    )
    with db_from_override() as db:
        task = db.get(Task, task_id())
        qa = db.exec(select(Agent).where(Agent.role == "qa")).one()
        task.intent_type = "review"
        task.assigned_agent_id = qa.id
        task.plan_json = json.dumps(
            {"targetId": DEMO_FRONTEND_TARGET_ID, "readOnly": True},
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        queue_entry = entry_for_task_run(db, run.id)
        assert queue_entry is not None
        assert json.loads(run.metrics_json)["adapterType"] == "scripted_mock"
        assert queue_entry.access_mode == "readonly"
        assert queue_entry.target_lock_key is None

        class HangingAdapter:
            def __init__(self) -> None:
                self.interrupted: list[str] = []

            def getCapabilities(self) -> AdapterCapabilities:
                return AdapterCapabilities(
                    supportsStreaming=True,
                    supportsInterrupt=True,
                    supportsApproval=False,
                    supportsFileEdit=False,
                    supportsShellCommand=False,
                    supportsDiffArtifact=False,
                    supportsPreviewArtifact=False,
                    supportsNetwork=False,
                    maxRuntimeSec=60,
                )

            async def createRun(self, request):
                return AdapterRun(adapterRunId="adapter-run-timeout")

            async def streamEvents(self, adapter_run_id):
                import asyncio

                await asyncio.sleep(60)
                if False:
                    yield {}

            async def interrupt(self, adapter_run_id):
                self.interrupted.append(adapter_run_id)

            async def approve(self, adapter_run_id, approval):
                return None

            async def collectArtifacts(self, adapter_run_id):
                return []

            async def cleanup(self, adapter_run_id):
                return None

        adapter = HangingAdapter()

        import asyncio

        asyncio.run(
            run_engine_module.execute_task_run(
                db,
                run,
                adapter_type="scripted_mock",
                adapter=adapter,
                max_runtime_seconds=0.01,
            )
        )

        stored = db.get(TaskRun, run.id)
        assert stored.state == "failed"
        assert stored.error_code == "TASK_RUN_TIMEOUT"
        assert adapter.interrupted == ["adapter-run-timeout"]


def test_execute_task_run_only_finalizes_completed_runs(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_runs_module,
        "CAPABILITIES_BY_ADAPTER",
        {
            **task_runs_module.CAPABILITIES_BY_ADAPTER,
            "scripted_mock": ("review",),
        },
    )
    with db_from_override() as db:
        task = db.get(Task, task_id())
        qa = db.exec(select(Agent).where(Agent.role == "qa")).one()
        task.intent_type = "review"
        task.assigned_agent_id = qa.id
        task.plan_json = json.dumps(
            {"targetId": DEMO_FRONTEND_TARGET_ID, "readOnly": True},
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        queue_entry = entry_for_task_run(db, run.id)
        assert queue_entry is not None
        assert json.loads(run.metrics_json)["adapterType"] == "scripted_mock"
        assert queue_entry.access_mode == "readonly"
        assert queue_entry.target_lock_key is None

        class FailingAdapter:
            def getCapabilities(self) -> AdapterCapabilities:
                return AdapterCapabilities(
                    supportsStreaming=True,
                    supportsInterrupt=True,
                    supportsApproval=False,
                    supportsFileEdit=False,
                    supportsShellCommand=False,
                    supportsDiffArtifact=False,
                    supportsPreviewArtifact=False,
                    supportsNetwork=False,
                )

            async def createRun(self, request):
                return AdapterRun(adapterRunId="adapter-run-failed")

            async def streamEvents(self, adapter_run_id):
                yield {
                    "type": "error",
                    "payload": {
                        "code": "TEST_FAILURE",
                        "message": "failed before finalizer",
                    },
                }

            async def interrupt(self, adapter_run_id):
                return None

            async def approve(self, adapter_run_id, approval):
                return None

            async def collectArtifacts(self, adapter_run_id):
                return []

            async def cleanup(self, adapter_run_id):
                return None

        finalized: list[str] = []

        async def fake_finalize_completed_task_run(db, task_run):
            finalized.append(task_run.id)
            return task_run

        monkeypatch.setattr(
            run_engine_module,
            "finalize_completed_task_run",
            fake_finalize_completed_task_run,
        )

        import asyncio

        asyncio.run(
            run_engine_module.execute_task_run(
                db,
                run,
                adapter_type="scripted_mock",
                adapter=FailingAdapter(),
            )
        )

        stored = db.get(TaskRun, run.id)
        assert finalized == []
        assert stored.state == "failed"
        assert stored.error_code == "TEST_FAILURE"


@pytest.mark.parametrize(
    ("decision_status", "error_code"),
    (
        ("rejected", "TASK_RUN_SCOPE_VIOLATION"),
        ("unverifiable", "TASK_RUN_SCOPE_UNVERIFIABLE"),
    ),
)
def test_finalize_adapter_completed_task_run_fails_scope_before_artifacts(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    decision_status: str,
    error_code: str,
) -> None:
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        run = task_runs_module.capture_task_run_scope_baseline(db, run.id)
        _bind_started_write_execution(db, run)
        transition_task_run(db, run.id, "collecting_diff")
        run_id = run.id

    decision = task_run_scope.ScopeDecision(
        status=decision_status,
        error_code=error_code,
        target_id=DEMO_FRONTEND_TARGET_ID,
        changed_paths=("apps/demo/package.json",),
        rejected_paths=("apps/demo/package.json",)
        if decision_status == "rejected"
        else (),
        reason="The task run scope evidence did not pass validation.",
    )
    calls: list[str] = []
    persisted: list[str] = []

    def validate_scope(db, task_run_id):
        calls.append(f"scope:{task_run_id}")
        return decision

    def persist_decision(db, task_run, value):
        persisted.append(value.status)
        return task_run

    def require_scope(db, task_run_id):
        calls.append(f"require:{task_run_id}")
        raise task_run_scope.TaskRunScopeError(
            error_code,
            (
                "The task run changed paths outside the assigned target."
                if error_code == "TASK_RUN_SCOPE_VIOLATION"
                else "The task run has no verifiable scope evidence."
            ),
        )

    def ledger(db, task_run_id):
        calls.append(f"ledger:{task_run_id}")

    def unexpected(*args, **kwargs):
        pytest.fail("scope failure reached an artifact or success side effect")

    async def unexpected_async(*args, **kwargs):
        pytest.fail("scope failure reached downstream scheduling")

    monkeypatch.setattr(
        run_engine_module, "validate_task_run_scope", validate_scope, raising=False
    )
    monkeypatch.setattr(
        run_engine_module, "persist_scope_decision", persist_decision, raising=False
    )
    monkeypatch.setattr(
        run_engine_module,
        "require_task_run_scope_passed",
        require_scope,
        raising=False,
    )
    monkeypatch.setattr(run_engine_module, "collect_task_run_diff", unexpected)
    monkeypatch.setattr(
        run_engine_module, "create_scripted_review_for_task_run", unexpected
    )
    monkeypatch.setattr(
        run_engine_module, "refresh_session_ledger_for_task_run", ledger
    )
    monkeypatch.setattr(
        run_engine_module, "_complete_ready_pipeline_review_tasks", unexpected
    )
    monkeypatch.setattr(
        run_engine_module, "_maybe_auto_preview_and_mock_deploy", unexpected
    )
    monkeypatch.setattr(
        run_engine_module, "_auto_start_next_pipeline_task", unexpected_async
    )

    import asyncio

    with db_from_override() as db:
        asyncio.run(
            run_engine_module.finalize_adapter_completed_task_run(
                db, db.get(TaskRun, run_id)
            )
        )
        asyncio.run(
            run_engine_module.finalize_adapter_completed_task_run(
                db, db.get(TaskRun, run_id)
            )
        )
        stored = db.get(TaskRun, run_id)
        queue_entry = entry_for_task_run(db, run_id)
        events = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == run_id)
            .order_by(TaskRunEvent.sequence)
        ).all()

    assert stored.state == "failed"
    assert stored.error_code == error_code
    assert calls == [
        f"scope:{run_id}",
        f"require:{run_id}",
        f"ledger:{run_id}",
    ]
    assert persisted == [decision_status]
    assert queue_entry.state == "failed"
    assert held_lock_for_target(db, DEMO_FRONTEND_TARGET_ID) is None
    event_types = [event.event_type for event in events]
    assert "artifact.diff.ready" not in event_types
    scope_index = event_types.index("task.scope_validation.failed")
    scope_event = json.loads(events[scope_index].payload_json)
    assert scope_event["result"] == decision_status
    assert scope_event["errorCode"] == error_code
    failed_state_index = next(
        index
        for index, event in enumerate(events)
        if event.event_type == "task.state"
        and json.loads(event.payload_json).get("state") == "failed"
    )
    assert scope_index < failed_state_index


def test_finalize_adapter_completed_task_run_uses_durable_unverifiable_after_stale_rejection(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        task_run = create_task_run(db, task.id)
        _acquire_scope_lock(db, task_run)
        task_run = task_runs_module.capture_task_run_scope_baseline(db, task_run.id)
        _bind_started_write_execution(db, task_run)
        transition_task_run(db, task_run.id, "collecting_diff")
        run_id = task_run.id

    stale_rejection = task_run_scope.ScopeDecision(
        status="rejected",
        error_code="TASK_RUN_SCOPE_VIOLATION",
        target_id=DEMO_FRONTEND_TARGET_ID,
        changed_paths=("apps/demo/package.json",),
        rejected_paths=("apps/demo/package.json",),
        reason="The task run changed paths outside the assigned target.",
    )
    fresh_decision = task_run_scope.ScopeDecision(
        status="passed",
        error_code=None,
        target_id=DEMO_FRONTEND_TARGET_ID,
        changed_paths=("apps/demo/src/App.tsx",),
        rejected_paths=(),
        reason=None,
    )
    validation_calls: list[str] = []

    def stale_validate_scope(db, task_run_id):
        validation_calls.append(f"transient:{task_run_id}")
        return stale_rejection

    def fresh_validate_scope(db, task_run_id):
        validation_calls.append(f"durable:{task_run_id}")
        return fresh_decision

    def unexpected(*args, **kwargs):
        pytest.fail("stale scope evidence reached an artifact or success side effect")

    async def unexpected_async(*args, **kwargs):
        pytest.fail("stale scope evidence reached downstream scheduling")

    monkeypatch.setattr(
        run_engine_module,
        "validate_task_run_scope",
        stale_validate_scope,
        raising=False,
    )
    monkeypatch.setattr(
        task_runs_module,
        "validate_task_run_scope",
        fresh_validate_scope,
    )
    monkeypatch.setattr(run_engine_module, "collect_task_run_diff", unexpected)
    monkeypatch.setattr(
        run_engine_module, "create_scripted_review_for_task_run", unexpected
    )
    monkeypatch.setattr(
        run_engine_module, "_complete_ready_pipeline_review_tasks", unexpected
    )
    monkeypatch.setattr(
        run_engine_module, "_maybe_auto_preview_and_mock_deploy", unexpected
    )
    monkeypatch.setattr(
        run_engine_module, "_auto_start_next_pipeline_task", unexpected_async
    )

    import asyncio

    with db_from_override() as db:
        asyncio.run(
            run_engine_module.finalize_adapter_completed_task_run(
                db, db.get(TaskRun, run_id)
            )
        )
        stored = db.get(TaskRun, run_id)
        metrics = json.loads(stored.metrics_json)
        queue_entry = entry_for_task_run(db, run_id)
        held_lock = held_lock_for_target(db, DEMO_FRONTEND_TARGET_ID)
        events = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == run_id)
            .order_by(TaskRunEvent.sequence)
        ).all()
        artifacts = db.exec(
            select(Artifact).where(Artifact.task_run_id == run_id)
        ).all()
        diffs = db.exec(
            select(Diff)
            .join(Artifact, Diff.artifact_id == Artifact.id)
            .where(Artifact.task_run_id == run_id)
        ).all()
        reviews = db.exec(
            select(Review)
            .join(Artifact, Review.artifact_id == Artifact.id)
            .where(Artifact.task_run_id == run_id)
        ).all()
        previews = db.exec(
            select(Preview)
            .join(Artifact, Preview.artifact_id == Artifact.id)
            .where(Artifact.task_run_id == run_id)
        ).all()
        deployments = db.exec(
            select(Deployment)
            .join(Artifact, Deployment.artifact_id == Artifact.id)
            .where(Artifact.task_run_id == run_id)
        ).all()
        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            task_runs_module.require_task_run_scope_passed(db, run_id)

    assert validation_calls == [f"transient:{run_id}", f"durable:{run_id}"]
    assert metrics["taskRunScopeDecision"]["status"] == "unverifiable"
    assert metrics["taskRunScopeDecision"]["errorCode"] == (
        "TASK_RUN_SCOPE_UNVERIFIABLE"
    )
    assert "taskRunScopeGuard" not in metrics
    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert stored.state == "failed"
    assert stored.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert queue_entry.state == "failed"
    assert held_lock is None
    assert artifacts == []
    assert diffs == []
    assert reviews == []
    assert previews == []
    assert deployments == []
    scope_events = [
        json.loads(event.payload_json)
        for event in events
        if event.event_type == "task.scope_validation.failed"
    ]
    assert scope_events == [
        {
            "result": "unverifiable",
            "taskRunId": run_id,
            "errorCode": "TASK_RUN_SCOPE_UNVERIFIABLE",
        }
    ]


def test_finalize_protected_tree_capture_exception_is_safe_and_unverifiable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sensitive_path = r"\\private-server\secret-share\repo\.git\objects"
    sensitive_secret = "sk-protected-tree-secret"
    capture_calls = 0

    def capture(worktree_path, **kwargs):
        nonlocal capture_calls
        capture_calls += 1
        if capture_calls == 1:
            return _scope_snapshot()
        raise OSError(
            f"protected tree read failed at {sensitive_path} with {sensitive_secret}"
        )

    monkeypatch.setattr(task_runs_module, "capture_worktree_scope_snapshot", capture)
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        task_run = create_task_run(db, task.id)
        _acquire_scope_lock(db, task_run)
        task_run = task_runs_module.capture_task_run_scope_baseline(
            db,
            task_run.id,
        )
        task_run = _bind_started_write_execution(db, task_run)
        transition_task_run(db, task_run.id, "collecting_diff")

        import asyncio

        asyncio.run(
            run_engine_module.finalize_adapter_completed_task_run(db, task_run)
        )

        stored = db.get(TaskRun, task_run.id)
        artifacts = db.exec(
            select(Artifact).where(Artifact.task_run_id == task_run.id)
        ).all()
        events = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == task_run.id)
            .order_by(TaskRunEvent.sequence)
        ).all()

    assert capture_calls == 2
    assert stored.state == "failed"
    assert stored.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert artifacts == []
    scope_event = next(
        event
        for event in events
        if event.event_type == "task.scope_validation.failed"
    )
    assert json.loads(scope_event.payload_json)["errorCode"] == (
        "TASK_RUN_SCOPE_UNVERIFIABLE"
    )
    exposed = " ".join(
        [
            stored.metrics_json,
            stored.error_message or "",
            *(event.payload_json for event in events),
        ]
    )
    assert sensitive_path not in exposed
    assert sensitive_secret not in exposed


def test_finalize_adapter_completed_task_run_passes_scope_before_completion(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        _acquire_scope_lock(db, run)
        run = task_runs_module.capture_task_run_scope_baseline(db, run.id)
        _bind_started_write_execution(db, run)
        transition_task_run(db, run.id, "collecting_diff")
        run_id = run.id
        task_id_value = task.id

    decision = task_run_scope.ScopeDecision(
        status="passed",
        error_code=None,
        target_id=DEMO_FRONTEND_TARGET_ID,
        changed_paths=("apps/demo/src/App.tsx",),
        rejected_paths=(),
        reason=None,
    )
    calls: list[str] = []

    def validate_scope(db, task_run_id):
        calls.append(f"scope:{task_run_id}")
        return decision

    def persist_decision(db, task_run, value):
        calls.append(f"persist:{task_run.id}")
        assert value is decision
        return task_run

    def require_scope(db, task_run_id):
        calls.append(f"require:{task_run_id}")
        return decision

    def collect_diff(db, task_run_id):
        calls.append(f"diff:{task_run_id}")

    def create_review(db, task_run_id):
        calls.append(f"review:{task_run_id}")

    def ledger(db, task_run_id):
        calls.append(f"ledger:{task_run_id}")

    def review_tasks(db, task_id):
        calls.append(f"review-tasks:{task_id}")
        return []

    def preview(db, task_run):
        calls.append(f"preview:{task_run.id}")

    async def downstream(db, task_id):
        calls.append(f"downstream:{task_id}")
        return None

    monkeypatch.setattr(
        run_engine_module, "validate_task_run_scope", validate_scope, raising=False
    )
    monkeypatch.setattr(
        run_engine_module, "persist_scope_decision", persist_decision, raising=False
    )
    monkeypatch.setattr(
        run_engine_module, "require_task_run_scope_passed", require_scope, raising=False
    )
    monkeypatch.setattr(run_engine_module, "collect_task_run_diff", collect_diff)
    monkeypatch.setattr(
        run_engine_module, "create_scripted_review_for_task_run", create_review
    )
    monkeypatch.setattr(
        run_engine_module, "refresh_session_ledger_for_task_run", ledger
    )
    monkeypatch.setattr(
        run_engine_module, "_complete_ready_pipeline_review_tasks", review_tasks
    )
    monkeypatch.setattr(
        run_engine_module, "_maybe_auto_preview_and_mock_deploy", preview
    )
    monkeypatch.setattr(
        run_engine_module, "_auto_start_next_pipeline_task", downstream
    )

    import asyncio

    with db_from_override() as db:
        asyncio.run(
            run_engine_module.finalize_adapter_completed_task_run(
                db, db.get(TaskRun, run_id)
            )
        )
        asyncio.run(
            run_engine_module.finalize_adapter_completed_task_run(
                db, db.get(TaskRun, run_id)
            )
        )
        stored = db.get(TaskRun, run_id)
        queue_entry = entry_for_task_run(db, run_id)
        events = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == run_id)
            .order_by(TaskRunEvent.sequence)
        ).all()

    assert stored.state == "completed"
    assert stored.ended_at is not None
    assert queue_entry.state == "completed"
    assert calls == [
        f"scope:{run_id}",
        f"persist:{run_id}",
        f"require:{run_id}",
        f"diff:{run_id}",
        f"review:{run_id}",
        f"ledger:{run_id}",
        f"review-tasks:{task_id_value}",
        f"preview:{run_id}",
        f"downstream:{task_id_value}",
    ]
    event_types = [event.event_type for event in events]
    scope_index = event_types.index("task.scope_validation.passed")
    completed_state_indexes = [
        index
        for index, event in enumerate(events)
        if event.event_type == "task.state"
        and json.loads(event.payload_json).get("state") == "completed"
    ]
    assert completed_state_indexes == [completed_state_indexes[0]]
    assert len(completed_state_indexes) == 1
    assert scope_index < completed_state_indexes[0]


def test_scope_finalization_claim_has_one_persistent_winner(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        run = create_task_run(db, task_id())
        transition_task_run(db, run.id, "collecting_diff")
        run_id = run.id

    with db_from_override() as first_db, db_from_override() as second_db:
        first_run = first_db.get(TaskRun, run_id)
        second_run = second_db.get(TaskRun, run_id)

        assert run_engine_module._claim_scope_finalization(first_db, first_run) is True
        assert run_engine_module._claim_scope_finalization(second_db, second_run) is False

        second_db.refresh(second_run)
        assert second_run.state == "collecting_diff"
        assert "scopeFinalizationClaim" not in task_runs_module.metrics_for_run(
            second_run
        )


def test_finalize_completed_task_run_runs_artifact_steps(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        run = create_task_run(db, task_id())
        transition_task_run(db, run.id, "completed")
        calls: list[str] = []

        monkeypatch.setattr(
            run_engine_module,
            "require_task_run_artifact_scope_passed",
            lambda db, task_run_id: None,
        )

        def fake_collect_task_run_diff(db, task_run_id):
            calls.append(f"diff:{task_run_id}")

        def fake_create_scripted_review_for_task_run(db, task_run_id):
            calls.append(f"review:{task_run_id}")

        def fake_refresh_session_ledger_for_task_run(db, task_run_id):
            calls.append(f"ledger:{task_run_id}")

        def fake_complete_ready_pipeline_review_tasks(db, task_id):
            calls.append(f"review-tasks:{task_id}")
            return []

        def fake_maybe_auto_preview_and_mock_deploy(db, task_run):
            calls.append(f"preview:{task_run.id}")

        async def fake_auto_start_next_pipeline_task(db, task_id):
            calls.append(f"downstream:{task_id}")
            return None

        monkeypatch.setattr(run_engine_module, "collect_task_run_diff", fake_collect_task_run_diff)
        monkeypatch.setattr(
            run_engine_module,
            "create_scripted_review_for_task_run",
            fake_create_scripted_review_for_task_run,
        )
        monkeypatch.setattr(
            run_engine_module,
            "refresh_session_ledger_for_task_run",
            fake_refresh_session_ledger_for_task_run,
        )
        monkeypatch.setattr(
            run_engine_module,
            "_complete_ready_pipeline_review_tasks",
            fake_complete_ready_pipeline_review_tasks,
        )
        monkeypatch.setattr(
            run_engine_module,
            "_maybe_auto_preview_and_mock_deploy",
            fake_maybe_auto_preview_and_mock_deploy,
        )
        monkeypatch.setattr(
            run_engine_module,
            "_auto_start_next_pipeline_task",
            fake_auto_start_next_pipeline_task,
        )

        import asyncio

        asyncio.run(run_engine_module.finalize_completed_task_run(db, run))

        assert calls == [
            f"diff:{run.id}",
            f"review:{run.id}",
            f"ledger:{run.id}",
            f"review-tasks:{run.task_id}",
            f"preview:{run.id}",
            f"downstream:{run.task_id}",
        ]


def test_finalize_completed_task_run_records_artifact_failures_without_blocking_pipeline(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        run = create_task_run(db, task_id())
        transition_task_run(db, run.id, "completed")
        calls: list[str] = []

        monkeypatch.setattr(
            run_engine_module,
            "require_task_run_artifact_scope_passed",
            lambda db, task_run_id: None,
        )

        def fake_collect_task_run_diff(db, task_run_id):
            calls.append(f"diff:{task_run_id}")
            raise DiffCollectionError("TaskRun does not have a usable baseRef or file snapshot.")

        def fake_create_scripted_review_for_task_run(db, task_run_id):
            calls.append(f"review:{task_run_id}")

        def fake_refresh_session_ledger_for_task_run(db, task_run_id):
            calls.append(f"ledger:{task_run_id}")

        def fake_complete_ready_pipeline_review_tasks(db, task_id):
            calls.append(f"review-tasks:{task_id}")
            return []

        def fake_maybe_auto_preview_and_mock_deploy(db, task_run):
            calls.append(f"preview:{task_run.id}")

        async def fake_auto_start_next_pipeline_task(db, task_id):
            calls.append(f"downstream:{task_id}")
            return None

        monkeypatch.setattr(run_engine_module, "collect_task_run_diff", fake_collect_task_run_diff)
        monkeypatch.setattr(
            run_engine_module,
            "create_scripted_review_for_task_run",
            fake_create_scripted_review_for_task_run,
        )
        monkeypatch.setattr(
            run_engine_module,
            "refresh_session_ledger_for_task_run",
            fake_refresh_session_ledger_for_task_run,
        )
        monkeypatch.setattr(
            run_engine_module,
            "_complete_ready_pipeline_review_tasks",
            fake_complete_ready_pipeline_review_tasks,
        )
        monkeypatch.setattr(
            run_engine_module,
            "_maybe_auto_preview_and_mock_deploy",
            fake_maybe_auto_preview_and_mock_deploy,
        )
        monkeypatch.setattr(
            run_engine_module,
            "_auto_start_next_pipeline_task",
            fake_auto_start_next_pipeline_task,
        )

        import asyncio

        asyncio.run(run_engine_module.finalize_completed_task_run(db, run))

        assert calls == [
            f"diff:{run.id}",
            f"ledger:{run.id}",
            f"review-tasks:{run.task_id}",
            f"preview:{run.id}",
            f"downstream:{run.task_id}",
        ]
        failed_events = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == run.id)
            .where(TaskRunEvent.event_type.in_(["artifact.diff.failed", "artifact.review.failed"]))
            .order_by(TaskRunEvent.sequence)
        ).all()
        assert [event.event_type for event in failed_events] == [
            "artifact.diff.failed",
            "artifact.review.failed",
        ]
        diff_payload = json.loads(failed_events[0].payload_json)
        review_payload = json.loads(failed_events[1].payload_json)
        assert diff_payload["errorCode"] == "ARTIFACT_COLLECTION_FAILED"
        assert "baseRef" in diff_payload["message"]
        assert review_payload["status"] == "skipped"

        diagnostics = build_task_run_diagnostics(db, db.get(TaskRun, run.id))
        assert diagnostics.primary_failure is None
        assert any(
            item.category == "artifact_collection_failed"
            for item in diagnostics.contributing_factors
        )
        assert any(
            item.phase == "diff" and item.status == "failed"
            for item in diagnostics.timeline
        )


def test_auto_start_next_pipeline_task_runs_external_downstream_task(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    frontend_root = tmp_path / "external-fullstack" / "frontend"
    backend_root = tmp_path / "external-fullstack" / "backend"
    (frontend_root / "src").mkdir(parents=True)
    (frontend_root / "src" / "App.tsx").write_text(
        "export default function App() { return null }\n"
    )
    (backend_root / "app").mkdir(parents=True)
    (backend_root / "app" / "main.py").write_text("from fastapi import FastAPI\n")

    executed: list[tuple[str, str]] = []

    async def fake_execute_task_run_background(
        db,
        task_run_id,
        adapter_type,
        *,
        worker_id=None,
    ):
        executed.append((task_run_id, adapter_type))
        return True

    async def reject_direct_execute(*args, **kwargs):
        pytest.fail("auto-start bypassed the standard background worker path")

    monkeypatch.setattr(
        run_engine_module,
        "execute_task_run_background",
        fake_execute_task_run_background,
    )
    monkeypatch.setattr(run_engine_module, "execute_task_run", reject_direct_execute)

    with db_from_override() as db:
        workspace = db.exec(select(Workspace).where(Workspace.name == "AgentHub Demo")).one()
        session = db.exec(select(Session).where(Session.title == "TaskRun session")).one()
        frontend_agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        backend_agent = db.exec(select(Agent).where(Agent.role == "backend")).one()
        register_external_project_target(
            db,
            workspace,
            ExternalWorkspaceRegistration(
                target_id="external-fullstack-frontend",
                name="External Fullstack Frontend",
                root_path=str(frontend_root),
                project_type="vite-react",
                allowed_paths=["src", "package.json", "vite.config.ts"],
                denied_paths=[".env", "node_modules"],
            ),
        )
        register_external_project_target(
            db,
            workspace,
            ExternalWorkspaceRegistration(
                target_id="external-fullstack-backend",
                name="External Fullstack Backend",
                root_path=str(backend_root),
                project_type="fastapi",
                allowed_paths=["app", "tests", "requirements.txt"],
                denied_paths=[".env", ".venv"],
            ),
        )
        upstream = Task(
            session_id=session.id,
            title="Frontend external task",
            intent_type="frontend_change",
            status="completed",
            assigned_agent_id=frontend_agent.id,
            plan_json=json.dumps(
                {
                    "planner": "orchestrator_external_target_v1",
                    "targetId": "external-fullstack-frontend",
                    "safeTarget": "src",
                    "files": ["src/App.tsx"],
                    "autoStart": True,
                },
                separators=(",", ":"),
            ),
        )
        db.add(upstream)
        db.commit()
        db.refresh(upstream)
        downstream = Task(
            session_id=session.id,
            title="Backend external task",
            intent_type="backend_change",
            status="waiting_dependency",
            assigned_agent_id=backend_agent.id,
            depends_on_task_ids=json.dumps([upstream.id], separators=(",", ":")),
            plan_json=json.dumps(
                {
                    "planner": "orchestrator_external_target_v1",
                    "targetId": "external-fullstack-backend",
                    "safeTarget": "app",
                    "files": ["app/main.py"],
                    "autoStart": True,
                },
                separators=(",", ":"),
            ),
        )
        db.add(downstream)
        db.commit()
        db.refresh(downstream)

        import asyncio

        started = asyncio.run(
            run_engine_module._auto_start_next_pipeline_task(db, upstream.id)
        )

        runs = db.exec(select(TaskRun).where(TaskRun.task_id == downstream.id)).all()
        stored_downstream = db.get(Task, downstream.id)

        assert started is not None
        db.refresh(stored_downstream)
        assert [run.id for run in runs] == [started.id]
        assert executed == [(started.id, "codex")]
        assert stored_downstream.status == "running"


@pytest.mark.parametrize(
    ("role", "intent_type", "target_id", "safe_target", "planned_file"),
    (
        (
            "frontend",
            "frontend_change",
            DEMO_FRONTEND_TARGET_ID,
            "apps/demo/src",
            "apps/demo/src/App.tsx",
        ),
        (
            "backend",
            "backend_change",
            DEMO_BACKEND_TARGET_ID,
            "apps/demo-api",
            "apps/demo-api/app.py",
        ),
    ),
)
def test_auto_started_writing_pipeline_claims_lock_and_captures_baseline(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    role: str,
    intent_type: str,
    target_id: str,
    safe_target: str,
    planned_file: str,
) -> None:
    with db_from_override() as db:
        session = db.exec(select(Session).where(Session.title == "TaskRun session")).one()
        agent = db.exec(select(Agent).where(Agent.role == role)).one()
        upstream = Task(
            session_id=session.id,
            title=f"Completed upstream for {role}",
            intent_type="review",
            status="completed",
            assigned_agent_id=agent.id,
        )
        db.add(upstream)
        db.commit()
        db.refresh(upstream)
        downstream = Task(
            session_id=session.id,
            title=f"Auto-started {role} write",
            intent_type=intent_type,
            status="waiting_dependency",
            assigned_agent_id=agent.id,
            depends_on_task_ids=json.dumps([upstream.id], separators=(",", ":")),
            plan_json=json.dumps(
                {
                    "planner": "contract_first_v1",
                    "targetId": target_id,
                    "safeTarget": safe_target,
                    "files": [planned_file],
                    "autoStart": True,
                },
                separators=(",", ":"),
            ),
        )
        db.add(downstream)
        db.commit()
        db.refresh(downstream)
        upstream_id = upstream.id
        downstream_id = downstream.id

    calls: list[str] = []

    def capture(worktree_path, **kwargs):
        with db_from_override() as lock_db:
            held = held_lock_for_target(lock_db, target_id)
            assert held is not None
            stored = lock_db.get(TaskRun, held.task_run_id)
            assert stored is not None
            assert stored.task_id == downstream_id
            assert stored.runner_id is not None
        calls.append("baseline")
        return _scope_snapshot()

    class FailingAfterCreateAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=True,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            with db_from_override() as evidence_db:
                held = held_lock_for_target(evidence_db, target_id)
                assert held is not None
                assert held.task_run_id == request.task_run_id
                stored = evidence_db.get(TaskRun, request.task_run_id)
                checkpoint = json.loads(stored.metrics_json)["preRunCheckpoint"]
                assert checkpoint["scopeBaseline"]["available"] is True
                events = evidence_db.exec(
                    select(TaskRunEvent).where(
                        TaskRunEvent.task_run_id == request.task_run_id
                    )
                ).all()
                assert "run.claimed" in {event.event_type for event in events}
            calls.append("createRun")
            raise RuntimeError("stop after auto-start security assertions")

        async def streamEvents(self, adapter_run_id):
            if False:
                yield {}

        async def interrupt(self, adapter_run_id):
            return None

        async def approve(self, adapter_run_id, approval):
            return None

        async def collectArtifacts(self, adapter_run_id):
            return []

        async def cleanup(self, adapter_run_id):
            return None

    _allow_test_provider_health(monkeypatch)
    monkeypatch.setattr(task_runs_module, "capture_worktree_scope_snapshot", capture)
    monkeypatch.setattr(
        run_engine_module,
        "CodexAdapter",
        lambda: FailingAfterCreateAdapter(),
    )

    import asyncio

    with db_from_override() as db:
        started = asyncio.run(
            run_engine_module._auto_start_next_pipeline_task(db, upstream_id)
        )
        runs = db.exec(select(TaskRun).where(TaskRun.task_id == downstream_id)).all()

    assert started is not None
    assert [run.id for run in runs] == [started.id]
    assert calls == ["baseline", "createRun"]


def test_background_execution_claims_and_refreshes_lease(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        run_id = run.id

    class FailingBeforeStreamAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=False,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            raise RuntimeError("stop after claim")

        async def streamEvents(self, adapter_run_id):
            if False:
                yield {}

        async def interrupt(self, adapter_run_id):
            return None

        async def approve(self, adapter_run_id, approval):
            return None

        async def collectArtifacts(self, adapter_run_id):
            return []

        async def cleanup(self, adapter_run_id):
            return None

    _allow_test_provider_health(monkeypatch)
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    monkeypatch.setattr(
        run_engine_module,
        "CodexAdapter",
        lambda: FailingBeforeStreamAdapter(),
    )

    import asyncio

    with db_from_override() as db:
        asyncio.run(
            run_engine_module.execute_task_run_background(
                db,
                run_id,
                "codex",
                worker_id="worker:test",
            )
        )
        stored = db.get(TaskRun, run_id)
        events = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == run_id)
            .order_by(TaskRunEvent.sequence)
        ).all()
        event_types = [event.event_type for event in events]
        metrics = json.loads(stored.metrics_json)

        assert stored.state == "failed"
        assert stored.runner_id == "worker:test"
        assert stored.last_heartbeat_at is not None
        assert stored.lease_expires_at > stored.last_heartbeat_at
        assert "run.claimed" in event_types
        assert "task.heartbeat" in event_types
        assert "provider.resolved" in event_types
        assert "provider.health_checked" in event_types
        assert "provider.capacity_acquired" in event_types
        assert "provider.capacity_released" in event_types
        assert metrics["providerGateway"]["resolution"]["selectedProviderId"] == (
            "local-codex-cli"
        )
        assert metrics["providerGateway"]["capacity"]["reason"] == (
            "Provider capacity released."
        )


def test_background_scope_baseline_is_captured_under_lock_before_create_run(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        run_id = run.id

    calls: list[str] = []

    def capture(worktree_path, **kwargs):
        with db_from_override() as lock_db:
            held = held_lock_for_target(lock_db, DEMO_FRONTEND_TARGET_ID)
            assert held is not None
            assert held.task_run_id == run_id
        calls.append("baseline")
        return _scope_snapshot()

    class FailingAfterCreateAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=True,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            with db_from_override() as evidence_db:
                stored = evidence_db.get(TaskRun, run_id)
                checkpoint = json.loads(stored.metrics_json)["preRunCheckpoint"]
                assert checkpoint["scopeBaseline"]["available"] is True
                assert checkpoint["scopeBaselineTaskRunId"] == run_id
            calls.append("createRun")
            raise RuntimeError("stop after createRun ordering assertion")

        async def streamEvents(self, adapter_run_id):
            if False:
                yield {}

        async def interrupt(self, adapter_run_id):
            return None

        async def approve(self, adapter_run_id, approval):
            return None

        async def collectArtifacts(self, adapter_run_id):
            return []

        async def cleanup(self, adapter_run_id):
            return None

    _allow_test_provider_health(monkeypatch)
    monkeypatch.setattr(task_runs_module, "capture_worktree_scope_snapshot", capture)
    monkeypatch.setattr(
        run_engine_module,
        "CodexAdapter",
        lambda: FailingAfterCreateAdapter(),
    )

    import asyncio

    with db_from_override() as db:
        asyncio.run(
            run_engine_module.execute_task_run_background(
                db,
                run_id,
                "codex",
                worker_id="worker:scope-order",
            )
        )
        stored = db.get(TaskRun, run_id)

    assert calls == ["baseline", "createRun"], (
        stored.state,
        stored.error_code,
        stored.error_message,
    )


def test_background_expired_same_holder_lock_never_starts_scope_capture_or_adapter(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        run_id = run.id

    capture_calls = 0
    create_run_calls = 0
    real_acquire = run_engine_module.acquire_target_lock

    def acquire_then_expire(*args, **kwargs):
        result = real_acquire(*args, **kwargs)
        assert result.acquired is True
        assert result.lock is not None
        result.lock.lease_expires_at = utc_now() - timedelta(seconds=1)
        args[0].add(result.lock)
        args[0].commit()
        return result

    def capture(worktree_path, **kwargs):
        nonlocal capture_calls
        capture_calls += 1
        return _scope_snapshot()

    class UnexpectedAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=True,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            nonlocal create_run_calls
            create_run_calls += 1
            return AdapterRun(adapterRunId="unexpected-expired-lock-run")

    _allow_test_provider_health(monkeypatch)
    monkeypatch.setattr(run_engine_module, "acquire_target_lock", acquire_then_expire)
    monkeypatch.setattr(task_runs_module, "capture_worktree_scope_snapshot", capture)
    monkeypatch.setattr(run_engine_module, "CodexAdapter", lambda: UnexpectedAdapter())

    import asyncio

    with db_from_override() as db:
        executed = asyncio.run(
            run_engine_module.execute_task_run_background(
                db,
                run_id,
                "codex",
                worker_id="worker:expired-same-holder",
            )
        )
        stored = db.get(TaskRun, run_id)

    assert executed is True
    assert capture_calls == 0
    assert create_run_calls == 0
    assert stored.state != "completed"
    assert stored.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


def test_scope_capture_rejects_same_owner_lock_generation_change_before_create_run(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_lock_now = utc_now()
    monkeypatch.setattr(target_locks_module, "utc_now", lambda: fixed_lock_now)
    worker_id = "worker:same-owner-new-generation"
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = claim_task_run_for_worker(
            db,
            create_task_run(db, task.id).id,
            worker_id=worker_id,
        )
        _acquire_scope_lock(db, run)
        held_lock = held_lock_for_target(db, DEMO_FRONTEND_TARGET_ID)
        assert held_lock is not None
        original_lock_id = held_lock.id
        run_id = run.id
        session_id = task.session_id
        request = agent_run_request_for(db, run, adapter_type="codex")
        _mark_task_run_queue_started(db, run)

    capture_calls = 0
    create_run_calls = 0

    def capture(worktree_path, **kwargs):
        nonlocal capture_calls
        capture_calls += 1
        with db_from_override() as lock_db:
            released = release_target_lock_for_task_run(
                lock_db,
                target_id=DEMO_FRONTEND_TARGET_ID,
                expected_lock_id=original_lock_id,
                worker_id=worker_id,
                task_run_id=run_id,
                session_id=session_id,
                release_reason="test_same_owner_generation_change",
            )
            assert released is not None
            reacquired = acquire_target_lock(
                lock_db,
                target_id=DEMO_FRONTEND_TARGET_ID,
                session_id=session_id,
                task_run_id=run_id,
                worker_id=worker_id,
                lease_expires_at=utc_now() + timedelta(minutes=5),
            )
            assert reacquired.acquired is True
        return _scope_snapshot()

    class UnexpectedAdapter:
        async def createRun(self, request):
            nonlocal create_run_calls
            create_run_calls += 1
            return AdapterRun(adapterRunId="unexpected-new-generation-run")

    monkeypatch.setattr(task_runs_module, "capture_worktree_scope_snapshot", capture)

    import asyncio

    with db_from_override() as db:
        guard = run_engine_module._ExecutionAccessBindingAdapter(
            db,
            run_id,
            UnexpectedAdapter(),
            launch_reservation=_allow_execution_access_binding_launch,
        )
        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            asyncio.run(guard.createRun(request))

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert capture_calls == 1
    assert create_run_calls == 0


def test_scope_capture_rejects_acquisition_generation_replaced_before_baseline(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker_id = "worker:acquired-generation-a"
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = claim_task_run_for_worker(
            db,
            create_task_run(db, task.id).id,
            worker_id=worker_id,
        )
        _acquire_scope_lock(db, run)
        acquired_lock = held_lock_for_target(db, DEMO_FRONTEND_TARGET_ID)
        assert acquired_lock is not None
        acquired_lock_id = acquired_lock.id
        task_run_scope.store_task_run_target_lock_acquisition_context(
            run.id,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=task.session_id,
            worker_id=worker_id,
            lock_id=acquired_lock_id,
        )
        released = release_target_lock_for_task_run(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            expected_lock_id=acquired_lock_id,
            worker_id=worker_id,
            task_run_id=run.id,
            session_id=task.session_id,
            release_reason="test_rotate_before_scope_baseline",
        )
        assert released is not None
        reacquired = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=task.session_id,
            task_run_id=run.id,
            worker_id=worker_id,
            lease_expires_at=utc_now() + timedelta(minutes=5),
        )
        assert reacquired.acquired is True
        assert reacquired.lock is not None
        assert reacquired.lock.id != acquired_lock_id
        replacement_lock_id = reacquired.lock.id
        run_id = run.id
        session_id = task.session_id
        request = agent_run_request_for(db, run, adapter_type="codex")
        _mark_task_run_queue_started(db, run)

    capture_calls = 0
    create_run_calls = 0

    def capture(worktree_path, **kwargs):
        nonlocal capture_calls
        capture_calls += 1
        return _scope_snapshot()

    class UnexpectedAdapter:
        async def createRun(self, request):
            nonlocal create_run_calls
            create_run_calls += 1
            return AdapterRun(adapterRunId="unexpected-replacement-generation-run")

    monkeypatch.setattr(task_runs_module, "capture_worktree_scope_snapshot", capture)

    import asyncio

    try:
        with db_from_override() as db:
            guard = run_engine_module._ExecutionAccessBindingAdapter(
                db,
                run_id,
                UnexpectedAdapter(),
                launch_reservation=_allow_execution_access_binding_launch,
            )
            with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
                asyncio.run(guard.createRun(request))

        assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
        assert capture_calls == 0
        assert create_run_calls == 0
    finally:
        with db_from_override() as db:
            release_target_lock_for_task_run(
                db,
                target_id=DEMO_FRONTEND_TARGET_ID,
                expected_lock_id=replacement_lock_id,
                worker_id=worker_id,
                task_run_id=run_id,
                session_id=session_id,
                release_reason="test_cleanup_replacement_generation",
            )
        task_run_scope.clear_task_run_scope_runtime_context(run_id)
        task_run_scope.clear_task_run_target_lock_acquisition_context(run_id)


def test_scope_adapter_reentry_does_not_replace_launch_baseline_or_restart_adapter(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = claim_task_run_for_worker(
            db,
            create_task_run(db, task.id).id,
            worker_id="worker:single-launch",
        )
        _acquire_scope_lock(db, run)
        run_id = run.id
        _mark_task_run_queue_started(db, run)
        launch_snapshots: list[run_engine_module._RequestLaunchSnapshot] = []
        request = agent_run_request_for(
            db,
            run,
            adapter_type="codex",
            fence_current_execution=True,
            _launch_snapshot_out=launch_snapshots,
        )
        assert len(launch_snapshots) == 1
        launch_snapshot = launch_snapshots[0]

    capture_calls = 0
    create_run_calls = 0

    def capture(worktree_path, **kwargs):
        nonlocal capture_calls
        capture_calls += 1
        return _scope_snapshot()

    class RecordingAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=True,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            nonlocal create_run_calls
            create_run_calls += 1
            return AdapterRun(adapterRunId=f"adapter-{create_run_calls}")

    monkeypatch.setattr(task_runs_module, "capture_worktree_scope_snapshot", capture)
    adapter = RecordingAdapter()
    supervisor = run_engine_module.RunSupervisor()
    supervised_run = supervisor.register(
        task_run_id=run_id,
        adapter_type="codex",
        adapter_run_id=None,
        adapter=adapter,
    )

    async def reserve_binding_launch(operation):
        return await supervisor.run_async_if_current(supervised_run, operation)

    import asyncio

    with db_from_override() as db:
        first_guard = run_engine_module._ExecutionAccessBindingAdapter(
            db,
            run_id,
            adapter,
            launch_reservation=reserve_binding_launch,
            expected_capabilities=adapter.getCapabilities(),
            expected_launch_snapshot=launch_snapshot,
            supervisor_ownership_guard=lambda: supervisor.is_current(
                supervised_run
            ),
        )
        asyncio.run(first_guard.createRun(request))
        first_checkpoint = json.loads(db.get(TaskRun, run_id).metrics_json)[
            "preRunCheckpoint"
        ]
        first_baseline_identity = first_checkpoint["scopeBaselineIdentity"]
        first_execution_attempt_id = first_checkpoint["scopeExecutionAttemptId"]

        second_guard = run_engine_module._ExecutionAccessBindingAdapter(
            db,
            run_id,
            adapter,
            launch_reservation=reserve_binding_launch,
            expected_capabilities=adapter.getCapabilities(),
            expected_launch_snapshot=launch_snapshot,
            supervisor_ownership_guard=lambda: supervisor.is_current(
                supervised_run
            ),
        )
        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            asyncio.run(second_guard.createRun(request))

        second_checkpoint = json.loads(db.get(TaskRun, run_id).metrics_json)[
            "preRunCheckpoint"
        ]

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert capture_calls == 1
    assert create_run_calls == 1
    assert second_checkpoint["scopeBaselineIdentity"] == first_baseline_identity
    assert second_checkpoint["scopeExecutionAttemptId"] == first_execution_attempt_id


def test_background_recovery_does_not_replace_started_run_launch_baseline(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture_calls = 0

    def capture(worktree_path, **kwargs):
        nonlocal capture_calls
        capture_calls += 1
        return _scope_snapshot()

    monkeypatch.setattr(task_runs_module, "capture_worktree_scope_snapshot", capture)
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = claim_task_run_for_worker(
            db,
            create_task_run(db, task.id).id,
            worker_id="worker:started-run",
        )
        _acquire_scope_lock(db, run)
        baseline = task_runs_module.capture_task_run_scope_baseline(db, run.id)
        first_checkpoint = json.loads(baseline.metrics_json)["preRunCheckpoint"]
        first_baseline_identity = first_checkpoint["scopeBaselineIdentity"]
        first_execution_attempt_id = first_checkpoint["scopeExecutionAttemptId"]
        transition_task_run(db, run.id, "streaming")
        run_id = run.id

    create_run_calls = 0

    class UnexpectedAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=True,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            nonlocal create_run_calls
            create_run_calls += 1
            return AdapterRun(adapterRunId="unexpected-reclaimed-run")

        async def streamEvents(self, adapter_run_id):
            if False:
                yield {}

        async def interrupt(self, adapter_run_id):
            return None

        async def approve(self, adapter_run_id, approval):
            return None

        async def collectArtifacts(self, adapter_run_id):
            return []

        async def cleanup(self, adapter_run_id):
            return None

    _allow_test_provider_health(monkeypatch)
    monkeypatch.setattr(run_engine_module, "CodexAdapter", lambda: UnexpectedAdapter())

    import asyncio

    with db_from_override() as db:
        executed = asyncio.run(
            run_engine_module.execute_task_run_background(
                db,
                run_id,
                "codex",
                worker_id="worker:recovery",
            )
        )
        stored = db.get(TaskRun, run_id)
        second_checkpoint = json.loads(stored.metrics_json)["preRunCheckpoint"]

    assert executed is True
    assert capture_calls == 1
    assert create_run_calls == 0
    assert stored.state == "failed"
    assert stored.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert second_checkpoint["scopeBaselineIdentity"] == first_baseline_identity
    assert second_checkpoint["scopeExecutionAttemptId"] == first_execution_attempt_id


def test_background_active_run_without_launch_baseline_fails_closed_before_adapter_restart(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture_calls = 0

    def capture(worktree_path, **kwargs):
        nonlocal capture_calls
        capture_calls += 1
        return _scope_snapshot()

    monkeypatch.setattr(task_runs_module, "capture_worktree_scope_snapshot", capture)
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = claim_task_run_for_worker(
            db,
            create_task_run(db, task.id).id,
            worker_id="worker:started-without-baseline",
        )
        _acquire_scope_lock(db, run)
        transition_task_run(db, run.id, "streaming")
        run_id = run.id

    create_run_calls = 0

    class UnexpectedAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=True,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            nonlocal create_run_calls
            create_run_calls += 1
            return AdapterRun(adapterRunId="unexpected-active-restart")

        async def streamEvents(self, adapter_run_id):
            if False:
                yield {}

        async def interrupt(self, adapter_run_id):
            return None

        async def approve(self, adapter_run_id, approval):
            return None

        async def collectArtifacts(self, adapter_run_id):
            return []

        async def cleanup(self, adapter_run_id):
            return None

    _allow_test_provider_health(monkeypatch)
    monkeypatch.setattr(run_engine_module, "CodexAdapter", lambda: UnexpectedAdapter())

    import asyncio

    with db_from_override() as db:
        executed = asyncio.run(
            run_engine_module.execute_task_run_background(
                db,
                run_id,
                "codex",
                worker_id="worker:recovery",
            )
        )
        stored = db.get(TaskRun, run_id)
        checkpoint = json.loads(stored.metrics_json)["preRunCheckpoint"]

    assert executed is True
    assert capture_calls == 0
    assert create_run_calls == 0
    assert stored.state == "failed"
    assert stored.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert "scopeExecutionAttemptId" not in checkpoint
    assert "scopeBaseline" not in checkpoint


def test_background_scope_capture_failure_does_not_start_adapter(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        run_id = run.id
        waiter_session = Session(
            workspace_id=db.get(Session, task.session_id).workspace_id,
            title="Scope capture failure waiter",
            bound_branch="main",
            worktree_path=".worktrees/scope-capture-failure-waiter",
        )
        waiter_task = Task(
            session_id=waiter_session.id,
            title="Wait after scope capture failure",
            intent_type="frontend_change",
            status="pending",
            assigned_agent_id=task.assigned_agent_id,
            plan_json=json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID}),
        )
        db.add(waiter_session)
        db.add(waiter_task)
        db.commit()
        waiter_run = claim_task_run_for_worker(
            db,
            create_task_run(db, waiter_task.id).id,
            worker_id="worker:scope-failure-waiter",
        )
        waiter_run_id = waiter_run.id
        waiter_session_id = waiter_session.id
        waiter_lease = waiter_run.lease_expires_at

    create_run_calls = 0
    blocked_results: list[dict[str, object]] = []
    blocked_generation_ids: list[str] = []

    def capture_failure(worktree_path, **kwargs):
        with db_from_override() as waiter_db:
            held = held_lock_for_target(waiter_db, DEMO_FRONTEND_TARGET_ID)
            assert held is not None
            blocked_generation_ids.append(held.id)
            blocked = acquire_target_lock(
                waiter_db,
                target_id=DEMO_FRONTEND_TARGET_ID,
                session_id=waiter_session_id,
                task_run_id=waiter_run_id,
                worker_id="worker:scope-failure-waiter",
                lease_expires_at=waiter_lease,
            )
            blocked_results.append(
                {
                    "acquired": blocked.acquired,
                    "holder_task_run_id": blocked.holder_task_run_id,
                    "lock_id": blocked.lock.id if blocked.lock is not None else None,
                }
            )
        raise RuntimeError("X:/sensitive-worktree/secret-command-output")

    class UnexpectedAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=True,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            nonlocal create_run_calls
            create_run_calls += 1
            return AdapterRun(adapterRunId="unexpected")

        async def streamEvents(self, adapter_run_id):
            if False:
                yield {}

        async def interrupt(self, adapter_run_id):
            return None

        async def approve(self, adapter_run_id, approval):
            return None

        async def collectArtifacts(self, adapter_run_id):
            return []

        async def cleanup(self, adapter_run_id):
            return None

    _allow_test_provider_health(monkeypatch)
    monkeypatch.setattr(
        task_runs_module,
        "capture_worktree_scope_snapshot",
        capture_failure,
    )
    monkeypatch.setattr(run_engine_module, "CodexAdapter", lambda: UnexpectedAdapter())

    import asyncio

    with db_from_override() as db:
        asyncio.run(
            run_engine_module.execute_task_run_background(
                db,
                run_id,
                "codex",
                worker_id="worker:scope-failure",
            )
        )
        stored = db.get(TaskRun, run_id)
        checkpoint = json.loads(stored.metrics_json)["preRunCheckpoint"]
        assert "scopeBaseline" in checkpoint, (
            stored.state,
            stored.error_code,
            stored.error_message,
            sorted(checkpoint),
        )
        baseline = checkpoint["scopeBaseline"]
        held_after_failure = held_lock_for_target(db, DEMO_FRONTEND_TARGET_ID)
        acquisition_context_after_failure = (
            task_run_scope.get_task_run_target_lock_acquisition_context(run_id)
        )
        released_generation = db.get(TargetLock, blocked_generation_ids[0])
        stored_error_code = stored.error_code
        stored_error_message = stored.error_message
        released_state = (
            released_generation.state if released_generation is not None else None
        )
        released_reason = (
            released_generation.release_reason
            if released_generation is not None
            else None
        )
        waiter_result = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=waiter_session_id,
            task_run_id=waiter_run_id,
            worker_id="worker:scope-failure-waiter",
            lease_expires_at=waiter_lease,
        )
        waiter_projection = {
            "acquired": waiter_result.acquired,
            "lock_id": waiter_result.lock.id if waiter_result.lock is not None else None,
            "task_run_id": (
                waiter_result.lock.task_run_id
                if waiter_result.lock is not None
                else None
            ),
        }

    assert create_run_calls == 0
    assert len(blocked_results) == 1
    assert blocked_results[0]["acquired"] is False
    assert blocked_results[0]["holder_task_run_id"] == run_id
    assert blocked_results[0]["lock_id"] == blocked_generation_ids[0]
    assert stored_error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert baseline["available"] is False
    assert baseline["reason"] == "scope_capture_unavailable"
    assert "sensitive-worktree" not in stored_error_message
    assert "secret-command-output" not in str(baseline)
    assert held_after_failure is None
    assert acquisition_context_after_failure is None
    assert released_generation is not None
    assert released_state == "released"
    assert released_reason == "task_run_failed"
    assert waiter_projection["acquired"] is True
    assert waiter_projection["lock_id"] is not None
    assert waiter_projection["lock_id"] != blocked_generation_ids[0]
    assert waiter_projection["task_run_id"] == waiter_run_id


def test_background_write_run_without_target_fails_closed_before_create_run(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"writeMode": True})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        run_id = run.id

    create_run_calls = 0

    class UnexpectedAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=True,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            nonlocal create_run_calls
            create_run_calls += 1
            return AdapterRun(adapterRunId="unexpected")

        async def streamEvents(self, adapter_run_id):
            if False:
                yield {}

        async def interrupt(self, adapter_run_id):
            return None

        async def approve(self, adapter_run_id, approval):
            return None

        async def collectArtifacts(self, adapter_run_id):
            return []

        async def cleanup(self, adapter_run_id):
            return None

    monkeypatch.setattr(run_engine_module, "CodexAdapter", lambda: UnexpectedAdapter())

    import asyncio

    with db_from_override() as db:
        asyncio.run(
            run_engine_module.execute_task_run_background(
                db,
                run_id,
                "codex",
                worker_id="worker:missing-scope-target",
            )
        )
        stored = db.get(TaskRun, run_id)

    assert create_run_calls == 0
    assert stored.state == "failed"
    assert stored.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert stored.error_message == "The task run scope target cannot be verified."


def test_queued_shared_worktree_run_captures_baseline_after_previous_completed_run(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        first_task = db.get(Task, task_id())
        first_task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        second_task = Task(
            session_id=first_task.session_id,
            title="Queued shared worktree change",
            intent_type="frontend_change",
            status="pending",
            assigned_agent_id=first_task.assigned_agent_id,
            plan_json=json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID}),
        )
        db.add(first_task)
        db.add(second_task)
        db.commit()
        db.refresh(second_task)

        first_run = claim_task_run_for_worker(
            db,
            create_task_run(db, first_task.id).id,
            worker_id="worker:first-shared",
        )
        _acquire_scope_lock(db, first_run)
        second_run = create_task_run(db, second_task.id)
        second_run_id = second_run.id
        creation_metrics = json.loads(second_run.metrics_json)

        assert "scopeBaseline" not in creation_metrics["preRunCheckpoint"]
        transition_task_run(db, first_run.id, "completed")
        assert db.get(TaskRun, first_run.id).state == "completed"

    earlier_run_entry = task_run_scope.ScopeEntry(
        path="apps/demo-api/app.py",
        status="tracked-present",
        fingerprint="b" * 64,
    )
    calls: list[str] = []

    def capture(worktree_path, **kwargs):
        with db_from_override() as lock_db:
            held = held_lock_for_target(lock_db, DEMO_FRONTEND_TARGET_ID)
            assert held is not None
            assert held.task_run_id == second_run_id
        calls.append("baseline-after-first")
        return _scope_snapshot(entries=(earlier_run_entry,))

    class FailingAfterCreateAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=True,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            with db_from_override() as evidence_db:
                stored = evidence_db.get(TaskRun, second_run_id)
                entries = json.loads(stored.metrics_json)["preRunCheckpoint"][
                    "scopeBaseline"
                ]["entries"]
                assert entries == [
                    {
                        "path": earlier_run_entry.path,
                        "status": earlier_run_entry.status,
                        "fingerprint": earlier_run_entry.fingerprint,
                    }
                ]
            calls.append("createRun")
            raise RuntimeError("stop after shared baseline assertion")

        async def streamEvents(self, adapter_run_id):
            if False:
                yield {}

        async def interrupt(self, adapter_run_id):
            return None

        async def approve(self, adapter_run_id, approval):
            return None

        async def collectArtifacts(self, adapter_run_id):
            return []

        async def cleanup(self, adapter_run_id):
            return None

    _allow_test_provider_health(monkeypatch)
    monkeypatch.setattr(task_runs_module, "capture_worktree_scope_snapshot", capture)
    monkeypatch.setattr(
        run_engine_module,
        "CodexAdapter",
        lambda: FailingAfterCreateAdapter(),
    )

    import asyncio

    with db_from_override() as db:
        executed = asyncio.run(
            run_engine_module.execute_task_run_background(
                db,
                second_run_id,
                "codex",
                worker_id="worker:second-shared",
            )
        )

    assert executed is True
    assert calls == ["baseline-after-first", "createRun"]


def test_background_execution_waits_for_target_lock_without_starting_adapter(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        current_session = db.get(Session, task.session_id)
        other_session = Session(
            workspace_id=current_session.workspace_id,
            title="Other target lock session",
            bound_branch="main",
            worktree_path=".worktrees/other-target-lock-session",
        )
        second = Task(
            session_id=other_session.id,
            title="Second login page change",
            intent_type="frontend_change",
            status="pending",
            assigned_agent_id=task.assigned_agent_id,
            plan_json=json.dumps(
                {
                    "targetId": DEMO_FRONTEND_TARGET_ID,
                    "safeTarget": "apps/demo/src",
                    "files": ["apps/demo/src/App.tsx"],
                },
                separators=(",", ":"),
            ),
        )
        db.add(other_session)
        db.add(second)
        db.commit()
        db.refresh(second)
        first_run = claim_task_run_for_worker(
            db,
            create_task_run(db, task.id).id,
            worker_id="worker:first",
        )
        first_run_id = first_run.id
        acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=task.session_id,
            task_run_id=first_run.id,
            worker_id="worker:first",
            lease_expires_at=first_run.lease_expires_at,
        )
        second_run = create_task_run(db, second.id)
        second_run_id = second_run.id

    calls: list[str] = []

    class UnexpectedAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=False,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            calls.append("createRun")
            return AdapterRun(id="unexpected")

        async def streamEvents(self, adapter_run_id):
            if False:
                yield {}

        async def interrupt(self, adapter_run_id):
            return None

        async def approve(self, adapter_run_id, approval):
            return None

        async def collectArtifacts(self, adapter_run_id):
            return []

        async def cleanup(self, adapter_run_id):
            return None

    monkeypatch.setattr(run_engine_module, "CodexAdapter", lambda: UnexpectedAdapter())

    import asyncio

    with db_from_override() as db:
        executed = asyncio.run(
            run_engine_module.execute_task_run_background(
                db,
                second_run_id,
                "codex",
                worker_id="worker:second",
            )
        )
        stored = db.get(TaskRun, second_run_id)
        stored_task = db.get(Task, stored.task_id)
        queue_entry = entry_for_task_run(db, second_run_id)
        scheduler = json.loads(stored_task.plan_json)["scheduler"]

        assert executed is False
        assert calls == []
        assert stored.state == "queued"
        assert queue_entry.state == "waiting_lock"
        assert scheduler["state"] == "waiting_target_lock"
        assert scheduler["lockHolderTaskRunIds"] == [first_run_id]


def test_adapter_completed_event_retains_target_lock_until_scope_finalizer(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        run_id = run.id

    class CompletingAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=False,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            return AdapterRun(adapterRunId="adapter-completed")

        async def streamEvents(self, adapter_run_id):
            yield {
                "type": "completed",
                "taskRunId": run_id,
                "payload": {"adapter": "codex"},
            }

        async def interrupt(self, adapter_run_id):
            return None

        async def approve(self, adapter_run_id, approval):
            return None

        async def collectArtifacts(self, adapter_run_id):
            return []

        async def cleanup(self, adapter_run_id):
            return None

    _allow_test_provider_health(monkeypatch)
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    monkeypatch.setattr(run_engine_module, "CodexAdapter", lambda: CompletingAdapter())
    finalized: list[str] = []

    async def fake_finalize_adapter_completed_task_run(db, task_run, **kwargs):
        db.refresh(task_run)
        assert task_run.state == "collecting_diff"
        assert task_run.ended_at is None
        held = held_lock_for_target(db, DEMO_FRONTEND_TARGET_ID)
        assert held is not None
        assert held.task_run_id == task_run.id
        finalized.append(task_run.id)
        return task_run

    monkeypatch.setattr(
        run_engine_module,
        "finalize_adapter_completed_task_run",
        fake_finalize_adapter_completed_task_run,
        raising=False,
    )

    import asyncio

    with db_from_override() as db:
        asyncio.run(
            run_engine_module.execute_task_run_background(
                db,
                run_id,
                "codex",
                worker_id="worker:complete",
            )
        )
        stored = db.get(TaskRun, run_id)
        queue_entry = entry_for_task_run(db, run_id)

        assert stored.state == "collecting_diff"
        assert stored.ended_at is None
        held = held_lock_for_target(db, DEMO_FRONTEND_TARGET_ID)
        assert held is not None
        assert held.task_run_id == run_id
        assert queue_entry.state == "running"
        assert finalized == [run_id]


def test_background_retains_scope_runtime_when_all_decision_cas_attempts_fail(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        run_id = run.id

    class CompletingAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=False,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            return AdapterRun(adapterRunId="adapter-decision-cas-failure")

        async def streamEvents(self, adapter_run_id):
            yield {
                "type": "completed",
                "taskRunId": run_id,
                "payload": {"adapter": "codex"},
            }

        async def interrupt(self, adapter_run_id):
            return None

        async def approve(self, adapter_run_id, approval):
            return None

        async def collectArtifacts(self, adapter_run_id):
            return []

        async def cleanup(self, adapter_run_id):
            return None

    fallback_cas_calls = 0

    def fail_fallback_cas(*args, **kwargs):
        nonlocal fallback_cas_calls
        fallback_cas_calls += 1
        return False

    _allow_test_provider_health(monkeypatch)
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    monkeypatch.setattr(run_engine_module, "CodexAdapter", lambda: CompletingAdapter())
    monkeypatch.setattr(
        task_runs_module,
        "_persist_scope_metrics_under_current_lock",
        lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(
        task_runs_module,
        "_persist_scope_metrics_cas",
        fail_fallback_cas,
    )

    import asyncio

    try:
        with db_from_override() as db:
            executed = asyncio.run(
                run_engine_module.execute_task_run_background(
                    db,
                    run_id,
                    "codex",
                    worker_id="worker:decision-cas-failure",
                )
            )
            stored = db.get(TaskRun, run_id)
            metrics = json.loads(stored.metrics_json)
            queue_entry = entry_for_task_run(db, run_id)

        assert executed is True
        assert fallback_cas_calls == 3
        assert stored.state == "failed"
        assert stored.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
        assert "taskRunScopeDecision" not in metrics
        assert task_run_scope.get_task_run_scope_runtime_context(run_id) is not None
        assert (
            task_run_scope.get_task_run_target_lock_acquisition_context(run_id)
            is None
        )
        assert queue_entry.state == "failed"
        with db_from_override() as db:
            assert held_lock_for_target(db, DEMO_FRONTEND_TARGET_ID) is None
    finally:
        task_run_scope.clear_task_run_scope_runtime_context(run_id)
        task_run_scope.clear_task_run_target_lock_acquisition_context(run_id)


def test_create_task_run_recovers_terminal_holder_target_lock(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        main_module,
        "schedule_task_run_execution",
        lambda background_tasks: None,
    )
    with db_from_override() as db:
        task = db.get(Task, task_id())
        current_session = db.get(Session, task.session_id)
        other_session = Session(
            workspace_id=current_session.workspace_id,
            title="Recovered terminal lock session",
            bound_branch="main",
            worktree_path=".worktrees/recovered-terminal-lock-session",
        )
        second = Task(
            session_id=other_session.id,
            title="Second task after terminal holder",
            intent_type="frontend_change",
            status="pending",
            assigned_agent_id=task.assigned_agent_id,
            plan_json=json.dumps(
                {
                    "targetId": DEMO_FRONTEND_TARGET_ID,
                    "safeTarget": "apps/demo/src",
                    "files": ["apps/demo/src/App.tsx"],
                },
                separators=(",", ":"),
            ),
        )
        db.add(other_session)
        db.add(second)
        db.commit()
        db.refresh(second)
        second_id = second.id

        first_run = claim_task_run_for_worker(
            db,
            create_task_run(db, task.id).id,
            worker_id="worker:first",
        )
        acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=task.session_id,
            task_run_id=first_run.id,
            worker_id="worker:first",
            lease_expires_at=first_run.lease_expires_at,
        )
        first_run.state = "completed"
        first_run.ended_at = utc_now()
        db.add(first_run)
        db.commit()

    response = client.post(f"/tasks/{second_id}/runs")

    assert response.status_code == 201
    with db_from_override() as db:
        assert held_lock_for_target(db, DEMO_FRONTEND_TARGET_ID) is None
        stored_second = db.get(Task, second_id)
        assert stored_second.status == "running"


def test_run_worker_executes_next_queued_task_run(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        first = create_task_run(db, task_id())
        first_id = first.id

    class FailingBeforeStreamAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=False,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            raise RuntimeError("stop after claim")

        async def streamEvents(self, adapter_run_id):
            if False:
                yield {}

        async def interrupt(self, adapter_run_id):
            return None

        async def approve(self, adapter_run_id, approval):
            return None

        async def collectArtifacts(self, adapter_run_id):
            return []

        async def cleanup(self, adapter_run_id):
            return None

    monkeypatch.setattr(
        run_engine_module,
        "CodexAdapter",
        lambda: FailingBeforeStreamAdapter(),
    )

    import asyncio

    with db_from_override() as db:
        executed = asyncio.run(
            run_engine_module.RunWorker(worker_id="worker:test").run_once(db)
        )

        stored = db.get(TaskRun, first_id)
        assert executed.id == first_id
        assert stored.state == "failed"
        assert stored.runner_id == "worker:test"


def test_run_worker_ignores_when_no_queued_task_run(client: TestClient) -> None:
    with db_from_override() as db:
        run = create_task_run(db, task_id())
        transition_task_run(db, run.id, "completed")

        import asyncio

        executed = asyncio.run(
            run_engine_module.RunWorker(worker_id="worker:test").run_once(db)
        )

        assert executed is None


def test_background_worker_recovers_stale_runs_before_queue_scan(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    worker = run_engine_module.RunWorker(worker_id="worker:production-recovery")

    def recover(db, *, reason="worker_startup"):
        calls.append(f"recover:{reason}")
        return {}

    def scan(db):
        calls.append("queue_scan")
        return []

    monkeypatch.setattr(worker, "recover_stale_runs", recover)
    monkeypatch.setattr(run_engine_module, "queued_task_runs", scan)
    with db_from_override() as db:
        assert asyncio.run(worker.run_once(db)) is None
    assert calls == ["recover:worker_startup", "queue_scan"]

    calls.clear()

    def fail_recovery(db, *, reason="worker_startup"):
        calls.append(f"recover:{reason}")
        raise RuntimeError("injected recovery failure")

    monkeypatch.setattr(worker, "recover_stale_runs", fail_recovery)
    with db_from_override() as db:
        with pytest.raises(RuntimeError, match="injected recovery failure"):
            asyncio.run(worker.run_once(db))
    assert calls == ["recover:worker_startup"]


def test_exact_generation_lease_renewal_rejects_rotated_lock(
    client: TestClient,
) -> None:
    now = utc_now()
    worker_id = "worker:exact-generation-renewal"
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = claim_task_run_for_worker(
            db,
            create_task_run(db, task.id).id,
            worker_id=worker_id,
        )
        run.state = "streaming"
        run.lease_expires_at = now + timedelta(minutes=5)
        run.metrics_json = json.dumps(
            {
                "taskRunExecutionAccessBinding": {
                    "taskRunId": run.id,
                    "taskId": task.id,
                    "sessionId": task.session_id,
                    "queueEntryId": entry_for_task_run(db, run.id).id,
                    "accessMode": "write",
                    "runnerId": worker_id,
                    "executionAttemptId": "attempt:generation-a",
                }
            },
            separators=(",", ":"),
        )
        db.add(run)
        db.commit()
        generation_a = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=task.session_id,
            task_run_id=run.id,
            worker_id=worker_id,
            lease_expires_at=run.lease_expires_at,
        )
        assert generation_a.lock is not None
        token = run_engine_module._ExecutionLeaseToken(
            task_run_id=run.id,
            task_id=task.id,
            session_id=task.session_id,
            workspace_id=db.get(Session, task.session_id).workspace_id,
            queue_entry_id=entry_for_task_run(db, run.id).id,
            runner_id=worker_id,
            access_mode="write",
            task_write_lock_required=True,
            target_id=DEMO_FRONTEND_TARGET_ID,
            expected_lock_id=generation_a.lock.id,
            execution_attempt_id="attempt:generation-a",
        )
        released = release_target_lock_for_task_run(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            expected_lock_id=generation_a.lock.id,
            worker_id=worker_id,
            task_run_id=run.id,
            session_id=task.session_id,
            release_reason="rotate_before_renewal",
        )
        assert released is not None
        generation_b = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=task.session_id,
            task_run_id=run.id,
            worker_id=worker_id,
            lease_expires_at=run.lease_expires_at,
        )
        assert generation_b.lock is not None
        assert generation_b.lock.id != generation_a.lock.id
        generation_b_id = generation_b.lock.id
        original_expiry = generation_b.lock.lease_expires_at

        renewed = run_engine_module._renew_execution_lease(
            db,
            token,
            now=now + timedelta(minutes=1),
            lease_seconds=300,
        )

        db.expire_all()
        stored_run = db.get(TaskRun, run.id)
        stored_lock = db.get(TargetLock, generation_b_id)
        assert renewed is False
        assert stored_run.lease_expires_at == original_expiry
        assert stored_lock.lease_expires_at == original_expiry


def test_execution_lease_renewal_rolls_back_task_run_when_exact_lock_is_lost(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = utc_now()
    worker_id = "worker:renewal-rollback"
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = claim_task_run_for_worker(
            db,
            create_task_run(db, task.id).id,
            worker_id=worker_id,
        )
        run.state = "streaming"
        run.lease_expires_at = now + timedelta(minutes=5)
        run.metrics_json = json.dumps(
            {
                "taskRunExecutionAccessBinding": {
                    "taskRunId": run.id,
                    "taskId": task.id,
                    "sessionId": task.session_id,
                    "queueEntryId": entry_for_task_run(db, run.id).id,
                    "accessMode": "write",
                    "runnerId": worker_id,
                    "executionAttemptId": "attempt:rollback",
                }
            },
            separators=(",", ":"),
        )
        db.add(run)
        db.commit()
        acquired = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=task.session_id,
            task_run_id=run.id,
            worker_id=worker_id,
            lease_expires_at=run.lease_expires_at,
        )
        assert acquired.lock is not None
        original_expiry = run.lease_expires_at
        token = run_engine_module._ExecutionLeaseToken(
            task_run_id=run.id,
            task_id=task.id,
            session_id=task.session_id,
            workspace_id=db.get(Session, task.session_id).workspace_id,
            queue_entry_id=entry_for_task_run(db, run.id).id,
            runner_id=worker_id,
            access_mode="write",
            task_write_lock_required=True,
            target_id=DEMO_FRONTEND_TARGET_ID,
            expected_lock_id=acquired.lock.id,
            execution_attempt_id="attempt:rollback",
        )
        real_execute = db.execute

        class LostLockResult:
            rowcount = 0

        def lose_exact_lock(statement, *args, **kwargs):
            if getattr(getattr(statement, "table", None), "name", None) == "targetlock":
                return LostLockResult()
            return real_execute(statement, *args, **kwargs)

        monkeypatch.setattr(db, "execute", lose_exact_lock)
        renewed = run_engine_module._renew_execution_lease(
            db,
            token,
            now=now + timedelta(minutes=1),
            lease_seconds=300,
        )
        monkeypatch.setattr(db, "execute", real_execute)

        db.expire_all()
        stored_run = db.get(TaskRun, run.id)
        stored_lock = db.get(TargetLock, acquired.lock.id)
        assert renewed is False
        assert stored_run.lease_expires_at == original_expiry
        assert stored_lock.lease_expires_at == original_expiry


def test_write_execution_lease_token_rejects_rotated_durable_lock_generation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        task_run = create_task_run(db, task.id)
        _acquire_scope_lock(db, task_run)
        task_run = task_runs_module.capture_task_run_scope_baseline(
            db,
            task_run.id,
        )
        task_run = _bind_started_write_execution(db, task_run)
        execution_attempt_id = json.loads(task_run.metrics_json)[
            "taskRunExecutionAccessBinding"
        ]["executionAttemptId"]
        held_lock = held_lock_for_target(db, DEMO_FRONTEND_TARGET_ID)
        assert held_lock is not None
        assert held_lock.state == "held"
        generation_a_context = (
            task_run_scope.get_task_run_target_lock_acquisition_context(
                task_run.id
            )
        )
        assert generation_a_context is not None
        assert generation_a_context.lock_id == held_lock.id
        generation_b_id = None
        try:
            released = release_target_lock_for_task_run(
                db,
                target_id=DEMO_FRONTEND_TARGET_ID,
                expected_lock_id=generation_a_context.lock_id,
                worker_id=generation_a_context.worker_id,
                task_run_id=task_run.id,
                session_id=task.session_id,
                release_reason="rotate_before_execution_lease_token",
            )
            assert released is not None
            generation_b = acquire_target_lock(
                db,
                target_id=DEMO_FRONTEND_TARGET_ID,
                session_id=task.session_id,
                task_run_id=task_run.id,
                worker_id=generation_a_context.worker_id,
                lease_expires_at=task_run.lease_expires_at,
            )
            assert generation_b.acquired is True
            assert generation_b.lock is not None
            generation_b_id = generation_b.lock.id
            assert generation_b_id != generation_a_context.lock_id
            stale_context = (
                task_run_scope.get_task_run_target_lock_acquisition_context(
                    task_run.id
                )
            )
            assert stale_context == generation_a_context

            with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
                run_engine_module._execution_lease_token_for_task_run(
                    db,
                    task_run.id,
                    access_mode="write",
                    execution_attempt_id=execution_attempt_id,
                    expected_session_id=task.session_id,
                )
        finally:
            if generation_b_id is not None:
                released = release_target_lock_for_task_run(
                    db,
                    target_id=DEMO_FRONTEND_TARGET_ID,
                    expected_lock_id=generation_b_id,
                    worker_id=generation_a_context.worker_id,
                    task_run_id=task_run.id,
                    session_id=task.session_id,
                    release_reason="cleanup_rotated_execution_lease_token_test",
                )
                assert released is not None
            task_run_scope.clear_task_run_scope_runtime_context(task_run.id)
            task_run_scope.clear_task_run_target_lock_acquisition_context(
                task_run.id
            )

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


def _prepare_readonly_execution_boundary(
    db: DbSession,
    monkeypatch: pytest.MonkeyPatch,
    *,
    worker_id: str,
):
    monkeypatch.setattr(
        task_runs_module,
        "CAPABILITIES_BY_ADAPTER",
        {
            **task_runs_module.CAPABILITIES_BY_ADAPTER,
            "scripted_mock": ("review",),
        },
    )
    task = db.get(Task, task_id())
    qa = db.exec(select(Agent).where(Agent.role == "qa")).one()
    task.intent_type = "review"
    task.assigned_agent_id = qa.id
    task.plan_json = json.dumps(
        {"targetId": DEMO_FRONTEND_TARGET_ID, "readOnly": True},
        separators=(",", ":"),
    )
    db.add(task)
    db.commit()
    run = claim_task_run_for_worker(
        db,
        create_task_run(db, task.id).id,
        worker_id=worker_id,
    )
    session_queue_module.mark_task_run_running(
        db,
        run.id,
        "Readonly execution started.",
    )
    entry = entry_for_task_run(db, run.id)
    assert entry is not None
    assert entry.access_mode == "readonly"
    assert entry.target_id == DEMO_FRONTEND_TARGET_ID
    session = db.get(Session, task.session_id)
    request = AgentRunRequest(
        taskRunId=run.id,
        sessionId=session.id,
        workspaceId=session.workspace_id,
        worktreePath=run.worktree_path,
        agentId=run.agent_id,
        adapterType="scripted_mock",
        instruction="Review the assigned target without modifying files.",
    )
    return task, run, entry, request


def _prepare_readonly_execution_lease(
    db: DbSession,
    monkeypatch: pytest.MonkeyPatch,
    *,
    worker_id: str,
    execution_attempt_id: str,
):
    _, run, entry, request = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id=worker_id,
    )
    task_runs_module.persist_task_run_execution_access_binding(
        db,
        run.id,
        access_mode="readonly",
        execution_attempt_id=execution_attempt_id,
    )
    token = run_engine_module._execution_lease_token_for_task_run(
        db,
        run.id,
        access_mode="readonly",
        execution_attempt_id=execution_attempt_id,
        expected_session_id=request.session_id,
    )
    return run, entry, token


def _fail_if_readonly_touches_target_lock(
    connection,
    cursor,
    statement,
    parameters,
    context,
    executemany,
) -> None:
    if "targetlock" in statement.casefold():
        pytest.fail("readonly execution touched the TargetLock table")


class _ReadonlyCreateRunDelegate:
    def __init__(self) -> None:
        self.create_run_calls: list[str] = []

    def getCapabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supportsStreaming=True,
            supportsInterrupt=True,
            supportsApproval=False,
            supportsFileEdit=False,
            supportsShellCommand=False,
            supportsDiffArtifact=False,
            supportsPreviewArtifact=False,
            supportsNetwork=False,
        )

    async def createRun(self, request: AgentRunRequest) -> AdapterRun:
        self.create_run_calls.append(request.task_run_id)
        return AdapterRun(adapterRunId=f"readonly-{request.task_run_id}")


@pytest.mark.parametrize(
    "invalid_durable_state",
    [
        "queue_not_running",
        "queue_missing_started_at",
        "task_target_drift",
        "expired_task_run_lease",
        "readonly_target_lock_key",
    ],
)
@pytest.mark.anyio
async def test_readonly_token_revalidates_durable_state_before_delegate_create_run(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    invalid_durable_state: str,
) -> None:
    with db_from_override() as db:
        task, run, _, request = _prepare_readonly_execution_boundary(
            db,
            monkeypatch,
            worker_id=f"worker:readonly-token:{invalid_durable_state}",
        )
        real_persist = run_engine_module.persist_task_run_execution_access_binding

        def persist_then_invalidate(*args, **kwargs):
            stored = real_persist(*args, **kwargs)
            entry = entry_for_task_run(db, stored.id)
            if invalid_durable_state == "queue_not_running":
                entry.state = "queued"
            elif invalid_durable_state == "queue_missing_started_at":
                entry.started_at = None
            elif invalid_durable_state == "task_target_drift":
                task.plan_json = json.dumps(
                    {"targetId": DEMO_BACKEND_TARGET_ID, "readOnly": True},
                    separators=(",", ":"),
                )
                db.add(task)
            elif invalid_durable_state == "expired_task_run_lease":
                stored.lease_expires_at = utc_now() - timedelta(seconds=1)
                db.add(stored)
            else:
                entry.target_lock_key = "unexpected-readonly-lock-key"
            db.add(entry)
            db.commit()
            return stored

        monkeypatch.setattr(
            run_engine_module,
            "persist_task_run_execution_access_binding",
            persist_then_invalidate,
        )
        delegate = _ReadonlyCreateRunDelegate()
        controller = run_engine_module._ExecutionLeaseController(
            db.get_bind(),
            interval_seconds=3600,
        )
        adapter = run_engine_module._ExecutionAccessBindingAdapter(
            db,
            run.id,
            delegate,
            launch_reservation=_allow_execution_access_binding_launch,
            expected_capabilities=delegate.getCapabilities(),
            on_execution_bound=controller.start,
        )
        event.listen(
            db.get_bind(),
            "before_cursor_execute",
            _fail_if_readonly_touches_target_lock,
        )
        try:
            with pytest.raises(task_run_scope.TaskRunScopeError):
                await adapter.createRun(request)
        finally:
            await controller.stop()
            event.remove(
                db.get_bind(),
                "before_cursor_execute",
                _fail_if_readonly_touches_target_lock,
            )

    assert delegate.create_run_calls == []


@pytest.mark.anyio
async def test_readonly_controller_guards_ownership_immediately_before_create_run(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        _, run, _, request = _prepare_readonly_execution_boundary(
            db,
            monkeypatch,
            worker_id="worker:readonly-immediate-guard",
        )
        real_token_for_run = run_engine_module._execution_lease_token_for_task_run

        def token_then_expire(*args, **kwargs):
            token = real_token_for_run(*args, **kwargs)
            stored = db.get(TaskRun, run.id)
            stored.lease_expires_at = utc_now() - timedelta(seconds=1)
            db.add(stored)
            db.commit()
            return token

        monkeypatch.setattr(
            run_engine_module,
            "_execution_lease_token_for_task_run",
            token_then_expire,
        )
        delegate = _ReadonlyCreateRunDelegate()
        controller = run_engine_module._ExecutionLeaseController(
            db.get_bind(),
            interval_seconds=3600,
        )
        adapter = run_engine_module._ExecutionAccessBindingAdapter(
            db,
            run.id,
            delegate,
            launch_reservation=_allow_execution_access_binding_launch,
            expected_capabilities=delegate.getCapabilities(),
            on_execution_bound=controller.start,
        )
        event.listen(
            db.get_bind(),
            "before_cursor_execute",
            _fail_if_readonly_touches_target_lock,
        )
        try:
            with pytest.raises(task_run_scope.TaskRunScopeError):
                await adapter.createRun(request)
        finally:
            await controller.stop()
            event.remove(
                db.get_bind(),
                "before_cursor_execute",
                _fail_if_readonly_touches_target_lock,
            )

    assert delegate.create_run_calls == []


@pytest.mark.anyio
async def test_readonly_controller_rejects_task_target_drift_after_token_before_create_run(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        task, run, _, request = _prepare_readonly_execution_boundary(
            db,
            monkeypatch,
            worker_id="worker:readonly-task-target-immediate-guard",
        )
        real_token_for_run = run_engine_module._execution_lease_token_for_task_run

        def token_then_drift_task_target(*args, **kwargs):
            token = real_token_for_run(*args, **kwargs)
            task.plan_json = json.dumps(
                {"targetId": DEMO_BACKEND_TARGET_ID, "readOnly": True},
                separators=(",", ":"),
            )
            db.add(task)
            db.commit()
            return token

        monkeypatch.setattr(
            run_engine_module,
            "_execution_lease_token_for_task_run",
            token_then_drift_task_target,
        )
        delegate = _ReadonlyCreateRunDelegate()
        controller = run_engine_module._ExecutionLeaseController(
            db.get_bind(),
            interval_seconds=3600,
        )
        adapter = run_engine_module._ExecutionAccessBindingAdapter(
            db,
            run.id,
            delegate,
            launch_reservation=_allow_execution_access_binding_launch,
            expected_capabilities=delegate.getCapabilities(),
            on_execution_bound=controller.start,
        )
        ownership_error = None
        event.listen(
            db.get_bind(),
            "before_cursor_execute",
            _fail_if_readonly_touches_target_lock,
        )
        try:
            try:
                await adapter.createRun(request)
            except task_run_scope.TaskRunScopeError as exc:
                ownership_error = exc
        finally:
            await controller.stop()
            event.remove(
                db.get_bind(),
                "before_cursor_execute",
                _fail_if_readonly_touches_target_lock,
            )

    assert delegate.create_run_calls == []
    assert ownership_error is not None
    assert ownership_error.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


def _invalidate_execution_session(
    db: DbSession,
    task_run_id: str,
    invalid_session_state: str,
    *,
    align_durable_binding: bool = False,
) -> None:
    task_run = db.get(TaskRun, task_run_id)
    task = db.get(Task, task_run.task_id)
    session = db.get(Session, task.session_id)
    assert session is not None
    if invalid_session_state == "missing_session":
        db.delete(session)
    else:
        other_session = Session(
            workspace_id=session.workspace_id,
            title="Execution relationship mismatch",
            bound_branch=session.bound_branch,
            worktree_path=(
                f"{session.worktree_path}-relationship-{task_run.id[:8]}"
            ),
        )
        task.session_id = other_session.id
        db.add(other_session)
        db.add(task)
        if align_durable_binding:
            entry = entry_for_task_run(db, task_run.id)
            entry.session_id = other_session.id
            metrics = json.loads(task_run.metrics_json)
            metrics["taskRunExecutionAccessBinding"]["sessionId"] = other_session.id
            task_run.metrics_json = json.dumps(metrics, separators=(",", ":"))
            db.add(entry)
            db.add(task_run)
    db.commit()


@pytest.mark.parametrize(
    "invalid_session_state",
    ["missing_session", "task_session_relationship_mismatch"],
)
@pytest.mark.anyio
async def test_readonly_token_revalidates_real_session_before_delegate_create_run(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    invalid_session_state: str,
) -> None:
    with db_from_override() as db:
        task, run, _, request = _prepare_readonly_execution_boundary(
            db,
            monkeypatch,
            worker_id=f"worker:readonly-session-token:{invalid_session_state}",
        )
        real_persist = run_engine_module.persist_task_run_execution_access_binding

        def persist_then_invalidate_session(*args, **kwargs):
            stored = real_persist(*args, **kwargs)
            _invalidate_execution_session(
                db,
                stored.id,
                invalid_session_state,
                align_durable_binding=True,
            )
            return stored

        monkeypatch.setattr(
            run_engine_module,
            "persist_task_run_execution_access_binding",
            persist_then_invalidate_session,
        )
        delegate = _ReadonlyCreateRunDelegate()
        controller = run_engine_module._ExecutionLeaseController(
            db.get_bind(),
            interval_seconds=3600,
        )
        adapter = run_engine_module._ExecutionAccessBindingAdapter(
            db,
            run.id,
            delegate,
            launch_reservation=_allow_execution_access_binding_launch,
            expected_capabilities=delegate.getCapabilities(),
            on_execution_bound=controller.start,
        )
        event.listen(
            db.get_bind(),
            "before_cursor_execute",
            _fail_if_readonly_touches_target_lock,
        )
        try:
            with pytest.raises(task_run_scope.TaskRunScopeError):
                await adapter.createRun(request)
        finally:
            await controller.stop()
            event.remove(
                db.get_bind(),
                "before_cursor_execute",
                _fail_if_readonly_touches_target_lock,
            )

    assert delegate.create_run_calls == []


@pytest.mark.parametrize(
    ("ownership_boundary", "invalid_session_state"),
    [
        ("renewal", "missing_session"),
        ("renewal", "task_session_relationship_mismatch"),
        ("immediate_guard", "missing_session"),
        ("immediate_guard", "task_session_relationship_mismatch"),
    ],
)
@pytest.mark.anyio
async def test_readonly_ownership_revalidates_real_session(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    ownership_boundary: str,
    invalid_session_state: str,
) -> None:
    with db_from_override() as db:
        run, _, token = _prepare_readonly_execution_lease(
            db,
            monkeypatch,
            worker_id=(
                f"worker:readonly-session:{ownership_boundary}:"
                f"{invalid_session_state}"
            ),
            execution_attempt_id=(
                f"attempt:readonly-session:{ownership_boundary}:"
                f"{invalid_session_state}"
            ),
        )
        _invalidate_execution_session(db, run.id, invalid_session_state)
        controller = run_engine_module._ExecutionLeaseController(
            db.get_bind(),
            interval_seconds=3600,
        )
        event.listen(
            db.get_bind(),
            "before_cursor_execute",
            _fail_if_readonly_touches_target_lock,
        )
        try:
            if ownership_boundary == "renewal":
                assert (
                    run_engine_module._renew_execution_lease(
                        db,
                        token,
                        lease_seconds=300,
                    )
                    is False
                )
            else:
                with pytest.raises(task_run_scope.TaskRunScopeError):
                    controller.start(token)
        finally:
            await controller.stop()
            event.remove(
                db.get_bind(),
                "before_cursor_execute",
                _fail_if_readonly_touches_target_lock,
            )


def test_readonly_execution_lease_token_binds_durable_queue_target(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution_attempt_id = "attempt:readonly-target-private"
    with db_from_override() as db:
        _, _, token = _prepare_readonly_execution_lease(
            db,
            monkeypatch,
            worker_id="worker:readonly-target-binding",
            execution_attempt_id=execution_attempt_id,
        )
        assert token.target_id == DEMO_FRONTEND_TARGET_ID
        assert token.expected_lock_id is None
        expected_lock_id = "private-lock-generation"
        adapter_run_id = "private-adapter-run"
        token_with_private_ids = replace(
            token,
            expected_lock_id=expected_lock_id,
            adapter_run_id=adapter_run_id,
        )
        token_repr = repr(token_with_private_ids)
        for private_value in (
            expected_lock_id,
            execution_attempt_id,
            adapter_run_id,
        ):
            assert private_value not in token_repr


def test_readonly_execution_lease_rejects_durable_queue_target_drift(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        run, entry, token = _prepare_readonly_execution_lease(
            db,
            monkeypatch,
            worker_id="worker:readonly-target-drift",
            execution_attempt_id="attempt:readonly-target-drift",
        )
        original_expiry = run.lease_expires_at
        entry.target_id = DEMO_BACKEND_TARGET_ID
        db.add(entry)
        db.commit()

        renewed = run_engine_module._renew_execution_lease(
            db,
            token,
            lease_seconds=300,
        )

        db.expire_all()
        assert renewed is False
        assert db.get(TaskRun, run.id).lease_expires_at == original_expiry
        assert db.exec(select(TargetLock)).all() == []


def test_readonly_execution_lease_rejects_task_target_drift_without_renewal(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        run, _, token = _prepare_readonly_execution_lease(
            db,
            monkeypatch,
            worker_id="worker:readonly-task-target-renewal",
            execution_attempt_id="attempt:readonly-task-target-renewal",
        )
        task = db.get(Task, run.task_id)
        original_expiry = run.lease_expires_at
        task.plan_json = json.dumps(
            {"targetId": DEMO_BACKEND_TARGET_ID, "readOnly": True},
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()

        event.listen(
            db.get_bind(),
            "before_cursor_execute",
            _fail_if_readonly_touches_target_lock,
        )
        try:
            renewed = run_engine_module._renew_execution_lease(
                db,
                token,
                lease_seconds=300,
            )
        finally:
            event.remove(
                db.get_bind(),
                "before_cursor_execute",
                _fail_if_readonly_touches_target_lock,
            )

        db.expire_all()
        assert renewed is False
        assert db.get(TaskRun, run.id).lease_expires_at == original_expiry
        assert db.exec(select(TargetLock)).all() == []


@pytest.mark.anyio
async def test_valid_readonly_execution_ownership_never_touches_target_lock(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        run, _, token = _prepare_readonly_execution_lease(
            db,
            monkeypatch,
            worker_id="worker:readonly-valid-ownership",
            execution_attempt_id="attempt:readonly-valid-ownership",
        )
        original_expiry = run.lease_expires_at
        controller = run_engine_module._ExecutionLeaseController(
            db.get_bind(),
            interval_seconds=3600,
        )
        renewed = False
        event.listen(
            db.get_bind(),
            "before_cursor_execute",
            _fail_if_readonly_touches_target_lock,
        )
        try:
            controller.start(token)
            renewed = run_engine_module._renew_execution_lease(
                db,
                token,
                lease_seconds=300,
            )
        finally:
            await controller.stop()
            event.remove(
                db.get_bind(),
                "before_cursor_execute",
                _fail_if_readonly_touches_target_lock,
            )

        db.expire_all()
        assert renewed is True
        assert db.get(TaskRun, run.id).lease_expires_at > original_expiry
        assert db.exec(select(TargetLock)).all() == []


@pytest.mark.anyio
async def test_execution_ownership_loss_wins_when_operation_completes_same_turn(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        run, _, token = _prepare_readonly_execution_lease(
            db,
            monkeypatch,
            worker_id="worker:ownership-priority",
            execution_attempt_id="attempt:ownership-priority",
        )
        controller = run_engine_module._ExecutionLeaseController(
            db.get_bind(),
            interval_seconds=3600,
        )
        controller.start(token)
        task_run_id = run.id
        adapter_run_id = f"adapter-run:{task_run_id}"
        run.adapter_run_id = adapter_run_id
        db.add(run)
        db.commit()
        controller.bind_adapter_run(adapter_run_id)

    interrupted: list[str] = []

    class InterruptibleAdapter:
        async def interrupt(self, adapter_run_id):
            interrupted.append(adapter_run_id)

    supervisor = run_engine_module.RunSupervisor()
    supervisor.register(
        task_run_id=task_run_id,
        adapter_type="scripted_mock",
        adapter_run_id=adapter_run_id,
        adapter=InterruptibleAdapter(),
    )

    async def complete_with_ownership_loss():
        controller._ownership_lost.set()
        return "operation-completed"

    try:
        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            await run_engine_module._run_with_execution_lease(
                complete_with_ownership_loss(),
                controller,
                supervisor=supervisor,
                task_run_id=task_run_id,
            )
    finally:
        await controller.stop()

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert interrupted == [adapter_run_id]


@pytest.mark.parametrize("interrupt_raises", [False, True])
@pytest.mark.anyio
async def test_stream_ownership_loss_cancels_before_slow_interrupt_finishes(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    interrupt_raises: bool,
) -> None:
    db = db_from_override()
    task, run, _, _ = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id=f"worker:stream-cancellation:{interrupt_raises}",
    )
    launch_snapshots: list[run_engine_module._RequestLaunchSnapshot] = []
    request = agent_run_request_for(
        db,
        run,
        adapter_type="scripted_mock",
        fence_current_execution=True,
        _launch_snapshot_out=launch_snapshots,
    )
    assert task.session_id == request.session_id
    assert len(launch_snapshots) == 1
    launch_snapshot = launch_snapshots[0]
    bind = db.get_bind()
    task_run_id = run.id

    adapter_run_id = f"adapter-run:stream-cancellation:{task_run_id}"
    replacement_adapter_run_id = f"adapter-run:replacement:{task_run_id}"
    stream_started = asyncio.Event()
    stream_cancelled = asyncio.Event()
    interrupt_started = asyncio.Event()
    release_interrupt = asyncio.Event()
    cleanup_called = asyncio.Event()
    lifecycle: list[str] = []
    replacement_interrupts: list[str] = []

    class SlowInterruptAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=False,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, current_request):
            lifecycle.append("create-run")
            return AdapterRun(adapterRunId=adapter_run_id)

        async def streamEvents(self, current_adapter_run_id):
            assert current_adapter_run_id == adapter_run_id
            lifecycle.append("stream-started")
            stream_started.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                lifecycle.append("stream-cancelled")
                stream_cancelled.set()
                raise
            if False:
                yield AgentEvent(
                    type="completed",
                    taskRunId=task_run_id,
                    sequence=1,
                    payload={"ok": True},
                )

        async def interrupt(self, current_adapter_run_id):
            assert current_adapter_run_id == adapter_run_id
            lifecycle.append("interrupt-started")
            interrupt_started.set()
            await release_interrupt.wait()
            if interrupt_raises:
                lifecycle.append("interrupt-failed")
                raise RuntimeError("injected slow interrupt failure")
            lifecycle.append("interrupt-finished")

        async def approve(self, current_adapter_run_id, approval):
            return None

        async def collectArtifacts(self, current_adapter_run_id):
            return []

        async def cleanup(self, current_adapter_run_id):
            assert current_adapter_run_id == adapter_run_id
            lifecycle.append("cleanup")
            cleanup_called.set()

    class ReplacementAdapter:
        async def interrupt(self, current_adapter_run_id):
            replacement_interrupts.append(current_adapter_run_id)

    adapter = SlowInterruptAdapter()
    supervisor = run_engine_module.RunSupervisor()
    supervised_run = supervisor.register(
        task_run_id=task_run_id,
        adapter_type="scripted_mock",
        adapter_run_id=None,
        adapter=adapter,
    )

    async def reserve_binding_launch(operation):
        return await supervisor.run_async_if_current(supervised_run, operation)

    controller = run_engine_module._ExecutionLeaseController(
        bind,
        interval_seconds=3600,
    )
    stream_adapter = run_engine_module._ExecutionAccessBindingAdapter(
        db,
        task_run_id,
        adapter,
        launch_reservation=reserve_binding_launch,
        expected_capabilities=adapter.getCapabilities(),
        expected_launch_snapshot=launch_snapshot,
        on_execution_bound=controller.start,
        supervisor_ownership_guard=lambda: supervisor.is_current(supervised_run),
    )

    def bind_adapter_run(current_run: AdapterRun) -> None:
        controller.bind_adapter_run(current_run.adapter_run_id)
        supervised = supervisor.update_adapter_run_id(
            task_run_id,
            current_run.adapter_run_id,
            expected=supervised_run,
        )
        assert supervised is not None

    stream = run_adapter_event_stream(
        db,
        stream_adapter,
        request,
        on_adapter_run_created=bind_adapter_run,
        ownership_guard=controller.owns_current_execution,
    )
    execution = asyncio.create_task(
        run_engine_module._run_adapter_stream_with_execution_lease(
            stream,
            controller,
            supervisor=supervisor,
            task_run_id=task_run_id,
            expected_supervised_run=supervised_run,
        )
    )
    try:
        await asyncio.wait_for(stream_started.wait(), timeout=1)
        with DbSession(bind) as ownership_db:
            stored = ownership_db.get(TaskRun, task_run_id)
            assert stored is not None
            assert stored.adapter_run_id == adapter_run_id
        assert controller._token is not None
        assert controller._token.adapter_run_id == adapter_run_id
        assert supervisor.active(task_run_id).adapter_run_id == adapter_run_id
        supervisor.register(
            task_run_id=task_run_id,
            adapter_type="scripted_mock",
            adapter_run_id=replacement_adapter_run_id,
            adapter=ReplacementAdapter(),
        )

        controller._ownership_lost.set()
        await asyncio.wait_for(interrupt_started.wait(), timeout=1)
        await asyncio.wait_for(stream_cancelled.wait(), timeout=1)
        await asyncio.wait_for(cleanup_called.wait(), timeout=1)
        assert execution.done() is False

        release_interrupt.set()
        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            await execution
    finally:
        release_interrupt.set()
        if not execution.done():
            execution.cancel()
        await asyncio.gather(execution, return_exceptions=True)
        await controller.stop()
        db.close()

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert replacement_interrupts == []
    assert lifecycle[:5] == [
        "create-run",
        "stream-started",
        "interrupt-started",
        "stream-cancelled",
        "cleanup",
    ]
    assert lifecycle[-1] == (
        "interrupt-failed" if interrupt_raises else "interrupt-finished"
    )


@pytest.mark.anyio
async def test_bound_stream_ownership_loss_interrupts_once_before_cancellation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    task, run, _, _ = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id="worker:bound-stream-cancellation",
    )
    launch_snapshots: list[run_engine_module._RequestLaunchSnapshot] = []
    request = agent_run_request_for(
        db,
        run,
        adapter_type="scripted_mock",
        fence_current_execution=True,
        _launch_snapshot_out=launch_snapshots,
    )
    assert task.session_id == request.session_id
    assert len(launch_snapshots) == 1
    launch_snapshot = launch_snapshots[0]
    bind = db.get_bind()
    task_run_id = run.id
    adapter_run_id = f"adapter-run:bound-stream:{task_run_id}"
    replacement_adapter_run_id = f"adapter-run:bound-replacement:{task_run_id}"
    stream_started = asyncio.Event()
    stream_cancelled = asyncio.Event()
    interrupt_started = asyncio.Event()
    release_interrupt = asyncio.Event()
    cleanup_called = asyncio.Event()
    lifecycle: list[str] = []
    original_interrupts: list[str] = []
    replacement_interrupts: list[str] = []

    class BoundSlowInterruptAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=False,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, current_request):
            lifecycle.append("create-run")
            return AdapterRun(adapterRunId=adapter_run_id)

        async def streamEvents(self, current_adapter_run_id):
            assert current_adapter_run_id == adapter_run_id
            lifecycle.append("stream-started")
            stream_started.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                lifecycle.append("stream-cancelled")
                stream_cancelled.set()
                raise
            if False:
                yield AgentEvent(
                    type="completed",
                    taskRunId=task_run_id,
                    sequence=1,
                    payload={"ok": True},
                )

        async def interrupt(self, current_adapter_run_id):
            assert current_adapter_run_id == adapter_run_id
            original_interrupts.append(current_adapter_run_id)
            lifecycle.append("interrupt-started")
            interrupt_started.set()
            await release_interrupt.wait()
            lifecycle.append("interrupt-finished")

        async def approve(self, current_adapter_run_id, approval):
            return None

        async def collectArtifacts(self, current_adapter_run_id):
            return []

        async def cleanup(self, current_adapter_run_id):
            assert current_adapter_run_id == adapter_run_id
            lifecycle.append("cleanup")
            cleanup_called.set()

    class ReplacementAdapter:
        async def interrupt(self, current_adapter_run_id):
            replacement_interrupts.append(current_adapter_run_id)

    adapter = BoundSlowInterruptAdapter()
    supervisor = run_engine_module.RunSupervisor()
    generation_a = supervisor.register(
        task_run_id=task_run_id,
        adapter_type="scripted_mock",
        adapter_run_id=adapter_run_id,
        adapter=adapter,
    )

    async def reserve_binding_launch(operation):
        return await supervisor.run_async_if_current(generation_a, operation)

    controller = run_engine_module._ExecutionLeaseController(
        bind,
        interval_seconds=3600,
    )
    stream_adapter = run_engine_module._ExecutionAccessBindingAdapter(
        db,
        task_run_id,
        adapter,
        launch_reservation=reserve_binding_launch,
        expected_capabilities=adapter.getCapabilities(),
        expected_launch_snapshot=launch_snapshot,
        on_execution_bound=controller.start,
        supervisor_ownership_guard=lambda: supervisor.is_current(generation_a),
    )

    def bind_adapter_run(current_run: AdapterRun) -> None:
        controller.bind_adapter_run(current_run.adapter_run_id)

    stream = run_adapter_event_stream(
        db,
        stream_adapter,
        request,
        on_adapter_run_created=bind_adapter_run,
        ownership_guard=controller.owns_current_execution,
    )
    execution = asyncio.create_task(
        run_engine_module._run_adapter_stream_with_execution_lease(
            stream,
            controller,
            supervisor=supervisor,
            task_run_id=task_run_id,
            expected_supervised_run=generation_a,
        )
    )
    replacement = None
    try:
        await asyncio.wait_for(stream_started.wait(), timeout=1)
        replacement = supervisor.register(
            task_run_id=task_run_id,
            adapter_type="scripted_mock",
            adapter_run_id=replacement_adapter_run_id,
            adapter=ReplacementAdapter(),
        )

        await asyncio.wait_for(interrupt_started.wait(), timeout=1)
        await asyncio.wait_for(stream_cancelled.wait(), timeout=1)
        await asyncio.wait_for(cleanup_called.wait(), timeout=1)
        assert execution.done() is False
        assert original_interrupts == [adapter_run_id]

        release_interrupt.set()
        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            await execution
    finally:
        release_interrupt.set()
        if not execution.done():
            execution.cancel()
        await asyncio.gather(execution, return_exceptions=True)
        await controller.stop()
        db.close()

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert lifecycle == [
        "create-run",
        "stream-started",
        "interrupt-started",
        "stream-cancelled",
        "cleanup",
        "interrupt-finished",
    ]
    assert original_interrupts == [adapter_run_id]
    assert supervisor.active(task_run_id) is replacement
    assert replacement_interrupts == []


@pytest.mark.parametrize("interrupt_raises", [False, True])
@pytest.mark.anyio
async def test_execute_task_run_preserves_replacement_supervisor_generation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    interrupt_raises: bool,
) -> None:
    db = db_from_override()
    _, run, _, _ = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id=f"worker:supervisor-generation-a:{interrupt_raises}",
    )
    task_run_id = run.id
    adapter_run_id = f"adapter-run:supervisor-a:{task_run_id}"
    replacement_adapter_run_id = f"adapter-run:supervisor-b:{task_run_id}"
    create_started = asyncio.Event()
    release_create = asyncio.Event()
    stream_started = asyncio.Event()
    release_stream = asyncio.Event()
    lifecycle: list[str] = []
    replacement_interrupts: list[str] = []

    class GenerationAAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=False,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, current_request):
            lifecycle.append("create-started")
            create_started.set()
            await release_create.wait()
            return AdapterRun(adapterRunId=adapter_run_id)

        async def streamEvents(self, current_adapter_run_id):
            lifecycle.append(f"stream:{current_adapter_run_id}")
            stream_started.set()
            try:
                await release_stream.wait()
                yield AgentEvent(
                    type="completed",
                    taskRunId=task_run_id,
                    sequence=1,
                    payload={"ok": True},
                )
            except asyncio.CancelledError:
                lifecycle.append("stream-cancelled")
                raise

        async def interrupt(self, current_adapter_run_id):
            lifecycle.append(f"interrupt:{current_adapter_run_id}")
            if interrupt_raises:
                raise RuntimeError("injected supervisor generation interrupt failure")

        async def approve(self, current_adapter_run_id, approval):
            return None

        async def collectArtifacts(self, current_adapter_run_id):
            return []

        async def cleanup(self, current_adapter_run_id):
            lifecycle.append(f"cleanup:{current_adapter_run_id}")

    class GenerationBAdapter:
        async def interrupt(self, current_adapter_run_id):
            replacement_interrupts.append(current_adapter_run_id)

    supervisor = run_engine_module.RunSupervisor()
    execution = asyncio.create_task(
        run_engine_module.execute_task_run(
            db,
            run,
            adapter_type="scripted_mock",
            adapter=GenerationAAdapter(),
            supervisor=supervisor,
            lease_renewal_interval_seconds=3600,
        )
    )
    replacement = None
    try:
        await asyncio.wait_for(create_started.wait(), timeout=1)
        generation_a = supervisor.active(task_run_id)
        assert generation_a is not None
        assert generation_a.adapter_run_id is None
        assert generation_a._generation.is_reserved() is True
        with db_from_override() as late_db:
            late_task_run = late_db.get(TaskRun, task_run_id)
            late_queue_entry = entry_for_task_run(late_db, task_run_id)
            assert late_task_run is not None
            assert late_queue_entry is not None
            original_metrics_json = late_task_run.metrics_json
            original_blocked_reason = late_queue_entry.blocked_reason
            late_task_run.metrics_json = json.dumps(
                {"staleReservedGenerationMetric": True},
                separators=(",", ":"),
            )
            late_queue_entry.blocked_reason = "stale reserved generation"
            late_db.add(late_task_run)
            late_db.add(late_queue_entry)
            writes: list[str] = []

            def record_sql_writes(
                connection,
                cursor,
                statement,
                parameters,
                context,
                executemany,
            ) -> None:
                normalized = statement.lstrip().casefold()
                if normalized.startswith(("insert ", "update ", "delete ", "replace ")):
                    writes.append(statement)

            engine = late_db.get_bind()
            event.listen(engine, "before_cursor_execute", record_sql_writes)
            try:
                with pytest.raises(RunRegistrationRejected, match="finalizing"):
                    await run_engine_module.execute_task_run(
                        late_db,
                        late_task_run,
                        adapter_type="scripted_mock",
                        adapter=GenerationBAdapter(),
                        supervisor=supervisor,
                        lease_renewal_interval_seconds=3600,
                    )
                late_db.commit()
            finally:
                event.remove(engine, "before_cursor_execute", record_sql_writes)
            assert writes == []
            late_db.refresh(late_task_run)
            late_db.refresh(late_queue_entry)
            assert late_task_run.metrics_json == original_metrics_json
            assert late_queue_entry.blocked_reason == original_blocked_reason
        with pytest.raises(RunRegistrationRejected, match="finalizing"):
            supervisor.register(
                task_run_id=task_run_id,
                adapter_type="scripted_mock",
                adapter_run_id=replacement_adapter_run_id,
                adapter=GenerationBAdapter(),
            )
        assert supervisor.active(task_run_id) is generation_a
        unrelated = supervisor.register(
            task_run_id=f"unrelated:{task_run_id}",
            adapter_type="scripted_mock",
        )
        assert supervisor.active(unrelated.task_run_id) is unrelated
        assert (
            supervisor.unregister(unrelated.task_run_id, expected=unrelated)
            is unrelated
        )
        release_create.set()
        await asyncio.wait_for(stream_started.wait(), timeout=1)
        generation_a = supervisor.active(task_run_id)
        assert generation_a is not None
        assert generation_a.adapter_run_id == adapter_run_id
        replacement = supervisor.register(
            task_run_id=task_run_id,
            adapter_type="scripted_mock",
            adapter_run_id=replacement_adapter_run_id,
            adapter=GenerationBAdapter(),
        )
        await execution
    finally:
        release_create.set()
        release_stream.set()
        if not execution.done():
            execution.cancel()
        await asyncio.gather(execution, return_exceptions=True)
        db.close()

    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
    assert stored is not None
    assert stored.state == "failed"
    assert stored.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert supervisor.active(task_run_id) is replacement
    assert replacement.adapter_run_id == replacement_adapter_run_id
    assert replacement_interrupts == []
    assert lifecycle == [
        "create-started",
        f"stream:{adapter_run_id}",
        f"interrupt:{adapter_run_id}",
        "stream-cancelled",
        f"cleanup:{adapter_run_id}",
    ]


@pytest.mark.anyio
async def test_execute_task_run_fences_supervisor_replacement_after_adapter_bind(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    _, run, _, _ = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id="worker:post-bind-supervisor-generation-a",
    )
    task_run_id = run.id
    adapter_run_id = f"adapter-run:post-bind-supervisor-a:{task_run_id}"
    replacement_adapter_run_id = (
        f"adapter-run:post-bind-supervisor-b:{task_run_id}"
    )
    stream_started = asyncio.Event()
    release_stream = asyncio.Event()
    lifecycle: list[str] = []
    replacement_interrupts: list[str] = []

    class GenerationAAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=False,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, current_request):
            return AdapterRun(adapterRunId=adapter_run_id)

        async def streamEvents(self, current_adapter_run_id):
            lifecycle.append(f"stream:{current_adapter_run_id}")
            stream_started.set()
            await release_stream.wait()
            yield AgentEvent(
                type="completed",
                taskRunId=task_run_id,
                sequence=1,
                payload={"ok": True},
            )

        async def interrupt(self, current_adapter_run_id):
            lifecycle.append(f"interrupt:{current_adapter_run_id}")

        async def approve(self, current_adapter_run_id, approval):
            return None

        async def collectArtifacts(self, current_adapter_run_id):
            return []

        async def cleanup(self, current_adapter_run_id):
            lifecycle.append(f"cleanup:{current_adapter_run_id}")

    class GenerationBAdapter:
        async def interrupt(self, current_adapter_run_id):
            replacement_interrupts.append(current_adapter_run_id)

    supervisor = run_engine_module.RunSupervisor()
    execution = asyncio.create_task(
        run_engine_module.execute_task_run(
            db,
            run,
            adapter_type="scripted_mock",
            adapter=GenerationAAdapter(),
            supervisor=supervisor,
            lease_renewal_interval_seconds=3600,
        )
    )
    replacement = None
    try:
        await asyncio.wait_for(stream_started.wait(), timeout=1)
        generation_a = supervisor.active(task_run_id)
        assert generation_a is not None
        assert generation_a.adapter_run_id == adapter_run_id
        replacement = supervisor.register(
            task_run_id=task_run_id,
            adapter_type="scripted_mock",
            adapter_run_id=replacement_adapter_run_id,
            adapter=GenerationBAdapter(),
        )
        release_stream.set()
        await asyncio.wait_for(execution, timeout=1)
    finally:
        release_stream.set()
        if not execution.done():
            execution.cancel()
        await asyncio.gather(execution, return_exceptions=True)
        db.close()

    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        completed_events = verification_db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == task_run_id)
            .where(TaskRunEvent.event_type == "completed")
        ).all()
    assert stored is not None
    assert stored.state == "failed"
    assert stored.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert completed_events == []
    assert supervisor.active(task_run_id) is replacement
    assert replacement is not None
    assert replacement.adapter_run_id == replacement_adapter_run_id
    assert replacement_interrupts == []
    assert lifecycle == [
        f"stream:{adapter_run_id}",
        f"interrupt:{adapter_run_id}",
        f"cleanup:{adapter_run_id}",
    ]


@pytest.mark.anyio
async def test_finalizer_scope_error_survives_persistent_rollback_failure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    _, run, _, _ = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id="worker:finalizer-rollback-failure",
    )
    task_run_id = run.id
    adapter_run_id = f"adapter-run:finalizer-rollback:{task_run_id}"
    scope_error = task_run_scope.TaskRunScopeError(
        "TASK_RUN_SCOPE_UNVERIFIABLE",
        "The task run execution lease ownership cannot be verified.",
    )
    rollback_error = RuntimeError("injected persistent finalizer rollback failure")
    original_rollback = db.rollback
    lifecycle: list[str] = []

    class CompletingReadonlyAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=False,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, current_request):
            return AdapterRun(adapterRunId=adapter_run_id)

        async def streamEvents(self, current_adapter_run_id):
            yield AgentEvent(
                type="completed",
                taskRunId=task_run_id,
                sequence=1,
                payload={"ok": True},
            )

        async def interrupt(self, current_adapter_run_id):
            lifecycle.append(f"interrupt:{current_adapter_run_id}")

        async def approve(self, current_adapter_run_id, approval):
            return None

        async def collectArtifacts(self, current_adapter_run_id):
            return []

        async def cleanup(self, current_adapter_run_id):
            lifecycle.append(f"cleanup:{current_adapter_run_id}")

    def fail_rollback() -> None:
        raise rollback_error

    async def fail_scope_finalizer(current_db, current_task_run, **kwargs):
        assert current_db is db
        assert current_task_run.state == "collecting_diff"
        monkeypatch.setattr(db, "rollback", fail_rollback)
        raise scope_error

    monkeypatch.setattr(
        run_engine_module,
        "finalize_adapter_completed_task_run",
        fail_scope_finalizer,
    )
    event.listen(
        db.get_bind(),
        "before_cursor_execute",
        _fail_if_readonly_touches_target_lock,
    )
    try:
        await run_engine_module.execute_task_run(
            db,
            run,
            adapter_type="scripted_mock",
            adapter=CompletingReadonlyAdapter(),
            supervisor=run_engine_module.RunSupervisor(),
            lease_renewal_interval_seconds=3600,
        )
    finally:
        monkeypatch.setattr(db, "rollback", original_rollback)
        original_rollback()
        event.remove(
            db.get_bind(),
            "before_cursor_execute",
            _fail_if_readonly_touches_target_lock,
        )
        db.close()

    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        artifacts = verification_db.exec(
            select(Artifact).where(Artifact.task_run_id == task_run_id)
        ).all()

    assert stored is not None
    assert stored.state == "failed"
    assert stored.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert stored.error_message == scope_error.message
    assert artifacts == []
    assert lifecycle == [f"cleanup:{adapter_run_id}"]


@pytest.mark.anyio
async def test_finalizer_scope_error_does_not_fail_replacement_write_lock_generation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    generation_b_id = None
    controller = None
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        task_run = create_task_run(db, task.id)
        _acquire_scope_lock(db, task_run)
        task_run = task_runs_module.capture_task_run_scope_baseline(db, task_run.id)
        task_run = _bind_started_write_execution(db, task_run)
        transition_task_run(db, task_run.id, "collecting_diff")
        execution_attempt_id = json.loads(task_run.metrics_json)[
            "taskRunExecutionAccessBinding"
        ]["executionAttemptId"]
        token = run_engine_module._execution_lease_token_for_task_run(
            db,
            task_run.id,
            access_mode="write",
            execution_attempt_id=execution_attempt_id,
            expected_session_id=task.session_id,
        )
        controller = run_engine_module._ExecutionLeaseController(
            db.get_bind(),
            interval_seconds=3600,
        )
        controller.start(token)
        generation_a_context = (
            task_run_scope.get_task_run_target_lock_acquisition_context(
                task_run.id
            )
        )
        assert generation_a_context is not None
        released = release_target_lock_for_task_run(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            expected_lock_id=generation_a_context.lock_id,
            worker_id=generation_a_context.worker_id,
            task_run_id=task_run.id,
            session_id=task.session_id,
            release_reason="rotate_before_scope_error_recovery",
        )
        assert released is not None
        generation_b = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=task.session_id,
            task_run_id=task_run.id,
            worker_id=generation_a_context.worker_id,
            lease_expires_at=task_run.lease_expires_at,
        )
        assert generation_b.acquired is True
        assert generation_b.lock is not None
        generation_b_id = generation_b.lock.id
        assert generation_b_id != token.expected_lock_id

        handled, recovered = run_engine_module._recover_finalizer_scope_error(
            db,
            task_run.id,
            task_run_scope.TaskRunScopeError(
                "TASK_RUN_SCOPE_UNVERIFIABLE",
                "The task run execution lease ownership cannot be verified.",
            ),
            controller,
        )

        db.expire_all()
        stored = db.get(TaskRun, task_run.id)
        assert handled is True
        assert recovered is None
        assert stored.state == "collecting_diff"
        assert stored.error_code is None

        released = release_target_lock_for_task_run(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            expected_lock_id=generation_b_id,
            worker_id=generation_a_context.worker_id,
            task_run_id=task_run.id,
            session_id=task.session_id,
            release_reason="cleanup_scope_error_replacement_generation_test",
        )
        assert released is not None

    assert controller is not None
    await controller.stop()
    task_run_scope.clear_task_run_scope_runtime_context(token.task_run_id)
    task_run_scope.clear_task_run_target_lock_acquisition_context(token.task_run_id)


@pytest.mark.anyio
async def test_execute_task_run_timeout_interrupts_exact_run_before_cleanup(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    _, run, _, _ = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id="worker:exact-timeout-order",
    )
    task_run_id = run.id
    adapter_run_id = f"adapter-run:exact-timeout:{task_run_id}"
    lifecycle: list[str] = []

    class HangingAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=False,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, current_request):
            return AdapterRun(adapterRunId=adapter_run_id)

        async def streamEvents(self, current_adapter_run_id):
            lifecycle.append(f"stream:{current_adapter_run_id}")
            await asyncio.Event().wait()
            if False:
                yield AgentEvent(
                    type="completed",
                    taskRunId=task_run_id,
                    sequence=1,
                    payload={"ok": True},
                )

        async def interrupt(self, current_adapter_run_id):
            lifecycle.append(f"interrupt:{current_adapter_run_id}")

        async def approve(self, current_adapter_run_id, approval):
            return None

        async def collectArtifacts(self, current_adapter_run_id):
            return []

        async def cleanup(self, current_adapter_run_id):
            lifecycle.append(f"cleanup:{current_adapter_run_id}")

    supervisor = run_engine_module.RunSupervisor()
    try:
        await run_engine_module.execute_task_run(
            db,
            run,
            adapter_type="scripted_mock",
            adapter=HangingAdapter(),
            supervisor=supervisor,
            max_runtime_seconds=0.01,
            lease_renewal_interval_seconds=3600,
        )
    finally:
        db.close()

    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
    assert stored is not None
    assert stored.state == "failed"
    assert stored.error_code == "TASK_RUN_TIMEOUT"
    assert lifecycle == [
        f"stream:{adapter_run_id}",
        f"interrupt:{adapter_run_id}",
        f"cleanup:{adapter_run_id}",
    ]
    assert supervisor.active(task_run_id) is None


def _prepare_finalizer_execution_lease(
    db: DbSession,
    monkeypatch: pytest.MonkeyPatch,
    *,
    worker_id: str,
    execution_attempt_id: str,
    adapter_run_id: str,
):
    run, _, token = _prepare_readonly_execution_lease(
        db,
        monkeypatch,
        worker_id=worker_id,
        execution_attempt_id=execution_attempt_id,
    )
    task_run_id = run.id
    controller = run_engine_module._ExecutionLeaseController(
        db.get_bind(),
        interval_seconds=3600,
    )
    controller.start(token)
    run.adapter_run_id = adapter_run_id
    db.add(run)
    db.commit()
    controller.bind_adapter_run(adapter_run_id)
    return task_run_id, controller


@pytest.mark.anyio
async def test_finalizer_ownership_loss_interrupts_frozen_exact_adapter_run(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter_run_id = "adapter-run:finalizer-original"
    with db_from_override() as db:
        task_run_id, controller = _prepare_finalizer_execution_lease(
            db,
            monkeypatch,
            worker_id="worker:finalizer-exact-run",
            execution_attempt_id="attempt:finalizer-exact-run",
            adapter_run_id=adapter_run_id,
        )

    original_interrupts: list[str] = []
    replacement_interrupts: list[str] = []

    class RecordingAdapter:
        def __init__(self, calls: list[str]) -> None:
            self.calls = calls

        async def interrupt(self, run_id: str) -> None:
            self.calls.append(run_id)

    supervisor = run_engine_module.RunSupervisor()
    supervisor.register(
        task_run_id=task_run_id,
        adapter_type="scripted_mock",
        adapter_run_id=adapter_run_id,
        adapter=RecordingAdapter(original_interrupts),
    )
    finalizer_started = asyncio.Event()

    async def blocked_finalizer() -> None:
        finalizer_started.set()
        await asyncio.Event().wait()

    execution = asyncio.create_task(
        run_engine_module._run_with_execution_lease(
            blocked_finalizer(),
            controller,
            supervisor=supervisor,
            task_run_id=task_run_id,
        )
    )
    try:
        await asyncio.wait_for(finalizer_started.wait(), timeout=1)
        supervisor.register(
            task_run_id=task_run_id,
            adapter_type="scripted_mock",
            adapter_run_id="adapter-run:finalizer-replacement",
            adapter=RecordingAdapter(replacement_interrupts),
        )
        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            await asyncio.wait_for(execution, timeout=1)
    finally:
        if not execution.done():
            execution.cancel()
            await asyncio.gather(execution, return_exceptions=True)
        await controller.stop()

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert original_interrupts == [adapter_run_id]
    assert replacement_interrupts == []


@pytest.mark.anyio
async def test_finalizer_ownership_loss_awaits_cancellation_before_interrupt(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter_run_id = "adapter-run:finalizer-cancellation-order"
    with db_from_override() as db:
        task_run_id, controller = _prepare_finalizer_execution_lease(
            db,
            monkeypatch,
            worker_id="worker:finalizer-cancellation-order",
            execution_attempt_id="attempt:finalizer-cancellation-order",
            adapter_run_id=adapter_run_id,
        )

    lifecycle: list[str] = []
    continued_side_effects: list[str] = []
    finalizer_started = asyncio.Event()
    cancellation_started = asyncio.Event()
    allow_cancellation_to_finish = asyncio.Event()

    class OrderedInterruptAdapter:
        async def interrupt(self, run_id: str) -> None:
            lifecycle.append(f"interrupt:{run_id}")

    async def blocked_finalizer() -> None:
        finalizer_started.set()
        try:
            await asyncio.Event().wait()
            continued_side_effects.append("continued-after-ownership-loss")
        except asyncio.CancelledError:
            lifecycle.append("finalizer-cancellation-started")
            cancellation_started.set()
            await allow_cancellation_to_finish.wait()
            lifecycle.append("finalizer-cancellation-finished")
            raise

    supervisor = run_engine_module.RunSupervisor()
    supervisor.register(
        task_run_id=task_run_id,
        adapter_type="scripted_mock",
        adapter_run_id=adapter_run_id,
        adapter=OrderedInterruptAdapter(),
    )
    execution = asyncio.create_task(
        run_engine_module._run_with_execution_lease(
            blocked_finalizer(),
            controller,
            supervisor=supervisor,
            task_run_id=task_run_id,
        )
    )
    observed_before_cancellation_finished: list[str] = []
    ownership_error = None
    try:
        await asyncio.wait_for(finalizer_started.wait(), timeout=1)
        controller._ownership_lost.set()
        await asyncio.wait_for(cancellation_started.wait(), timeout=1)
        observed_before_cancellation_finished = list(lifecycle)
    finally:
        allow_cancellation_to_finish.set()
        try:
            await execution
        except task_run_scope.TaskRunScopeError as exc:
            ownership_error = exc
        await controller.stop()

    assert observed_before_cancellation_finished == [
        "finalizer-cancellation-started"
    ]
    assert lifecycle == [
        "finalizer-cancellation-started",
        "finalizer-cancellation-finished",
        f"interrupt:{adapter_run_id}",
    ]
    assert continued_side_effects == []
    assert ownership_error is not None
    assert ownership_error.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


@pytest.mark.anyio
async def test_finalizer_interrupt_failure_preserves_scope_unverifiable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter_run_id = "adapter-run:finalizer-interrupt-failure"
    with db_from_override() as db:
        task_run_id, controller = _prepare_finalizer_execution_lease(
            db,
            monkeypatch,
            worker_id="worker:finalizer-interrupt-failure",
            execution_attempt_id="attempt:finalizer-interrupt-failure",
            adapter_run_id=adapter_run_id,
        )

    finalizer_started = asyncio.Event()
    interrupted: list[str] = []

    class FailingInterruptAdapter:
        async def interrupt(self, run_id: str) -> None:
            interrupted.append(run_id)
            raise RuntimeError("injected adapter interrupt failure")

    async def blocked_finalizer() -> None:
        finalizer_started.set()
        await asyncio.Event().wait()

    supervisor = run_engine_module.RunSupervisor()
    supervisor.register(
        task_run_id=task_run_id,
        adapter_type="scripted_mock",
        adapter_run_id=adapter_run_id,
        adapter=FailingInterruptAdapter(),
    )
    execution = asyncio.create_task(
        run_engine_module._run_with_execution_lease(
            blocked_finalizer(),
            controller,
            supervisor=supervisor,
            task_run_id=task_run_id,
        )
    )
    try:
        await asyncio.wait_for(finalizer_started.wait(), timeout=1)
        controller._ownership_lost.set()
        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            await execution
    finally:
        if not execution.done():
            execution.cancel()
            await asyncio.gather(execution, return_exceptions=True)
        await controller.stop()

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert interrupted == [adapter_run_id]


@pytest.mark.anyio
async def test_finalizer_interrupt_cancellation_preserves_scope_unverifiable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter_run_id = "adapter-run:finalizer-interrupt-cancelled"
    with db_from_override() as db:
        task_run_id, controller = _prepare_finalizer_execution_lease(
            db,
            monkeypatch,
            worker_id="worker:finalizer-interrupt-cancelled",
            execution_attempt_id="attempt:finalizer-interrupt-cancelled",
            adapter_run_id=adapter_run_id,
        )

    finalizer_started = asyncio.Event()
    interrupted: list[str] = []

    class CancelledInterruptAdapter:
        async def interrupt(self, run_id: str) -> None:
            interrupted.append(run_id)
            raise asyncio.CancelledError("injected adapter interrupt cancellation")

    async def blocked_finalizer() -> None:
        finalizer_started.set()
        await asyncio.Event().wait()

    supervisor = run_engine_module.RunSupervisor()
    supervisor.register(
        task_run_id=task_run_id,
        adapter_type="scripted_mock",
        adapter_run_id=adapter_run_id,
        adapter=CancelledInterruptAdapter(),
    )
    execution = asyncio.create_task(
        run_engine_module._run_with_execution_lease(
            blocked_finalizer(),
            controller,
            supervisor=supervisor,
            task_run_id=task_run_id,
        )
    )
    try:
        await asyncio.wait_for(finalizer_started.wait(), timeout=1)
        controller._ownership_lost.set()
        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            await execution
    finally:
        if not execution.done():
            execution.cancel()
            await asyncio.gather(execution, return_exceptions=True)
        await controller.stop()

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert interrupted == [adapter_run_id]


@pytest.mark.anyio
async def test_interrupt_exact_supervised_run_propagates_cancellation_without_primary_error() -> None:
    adapter_run_id = "adapter-run:direct-interrupt-cancelled"

    class CancelledInterruptAdapter:
        async def interrupt(self, run_id: str) -> None:
            raise asyncio.CancelledError("injected adapter interrupt cancellation")

    supervisor = run_engine_module.RunSupervisor()
    supervised_run = supervisor.register(
        task_run_id="direct-interrupt-cancelled-run",
        adapter_type="scripted_mock",
        adapter_run_id=adapter_run_id,
        adapter=CancelledInterruptAdapter(),
    )

    with pytest.raises(asyncio.CancelledError):
        await run_engine_module._interrupt_exact_supervised_run(
            supervisor,
            supervised_run,
        )


@pytest.mark.anyio
async def test_write_execution_lease_renews_exact_lock_generation_while_adapter_streams(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        run_id = run.id

    stream_started = asyncio.Event()
    finish_stream = asyncio.Event()
    renewed_twice = asyncio.Event()
    renewal_count = 0

    class PausedStreamingAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=True,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            return AdapterRun(adapterRunId=f"paused-{request.task_run_id}")

        async def streamEvents(self, adapter_run_id):
            stream_started.set()
            await finish_stream.wait()
            yield AgentEvent(
                type="error",
                taskRunId=run_id,
                sequence=1,
                payload={"code": "TEST_FAILURE", "message": "Test stream finished."},
            )

        async def interrupt(self, adapter_run_id):
            finish_stream.set()

        async def approve(self, adapter_run_id, approval):
            return None

        async def collectArtifacts(self, adapter_run_id):
            return []

        async def cleanup(self, adapter_run_id):
            return None

    real_renew = run_engine_module._renew_execution_lease

    def record_renewal(db, token, **kwargs):
        nonlocal renewal_count
        renewed = real_renew(db, token, **kwargs)
        if renewed:
            renewal_count += 1
            if renewal_count >= 2:
                renewed_twice.set()
        return renewed

    _allow_test_provider_health(monkeypatch)
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    monkeypatch.setattr(run_engine_module, "CodexAdapter", PausedStreamingAdapter)
    monkeypatch.setattr(run_engine_module, "_renew_execution_lease", record_renewal)
    monkeypatch.setattr(
        run_engine_module,
        "EXECUTION_LEASE_RENEWAL_INTERVAL_SECONDS",
        0.02,
        raising=False,
    )

    execution = asyncio.create_task(
        run_engine_module.execute_task_run_background(
            db_from_override(),
            run_id,
            "codex",
            worker_id="worker:periodic-renewal",
        )
    )
    try:
        await asyncio.wait_for(stream_started.wait(), timeout=1)
        with db_from_override() as db:
            initial_run = db.get(TaskRun, run_id)
            initial_lock = held_lock_for_target(db, DEMO_FRONTEND_TARGET_ID)
            assert initial_lock is not None
            original_lock_id = initial_lock.id
            original_run_expiry = initial_run.lease_expires_at
            original_lock_expiry = initial_lock.lease_expires_at

        await asyncio.wait_for(renewed_twice.wait(), timeout=1)
        with db_from_override() as recovery_db:
            renewed_run = recovery_db.get(TaskRun, run_id)
            renewed_lock = recovery_db.get(TargetLock, original_lock_id)
            old_recovery_boundary = max(original_run_expiry, original_lock_expiry)
            assert renewed_run.lease_expires_at > old_recovery_boundary
            assert renewed_lock.lease_expires_at == renewed_run.lease_expires_at
            monkeypatch.setattr(
                target_locks_module,
                "utc_now",
                lambda: old_recovery_boundary + timedelta(microseconds=1),
            )
            recovered = recover_stale_target_locks(recovery_db)
            recovery_db.refresh(renewed_run)
            recovery_db.refresh(renewed_lock)
            assert recovered == []
            assert renewed_run.state != "failed"
            assert renewed_lock.state == "held"
    finally:
        finish_stream.set()
        await execution


@pytest.mark.anyio
async def test_old_adapter_completed_event_is_fenced_after_stale_recovery(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        run_id = run.id

    stream_started = asyncio.Event()
    release_completed = asyncio.Event()
    finalizer_calls: list[str] = []

    class DelayedCompletedAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=True,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            return AdapterRun(adapterRunId=f"stale-stream-{request.task_run_id}")

        async def streamEvents(self, adapter_run_id):
            stream_started.set()
            await release_completed.wait()
            yield AgentEvent(
                type="completed",
                taskRunId=run_id,
                sequence=1,
                payload={"ok": True},
            )

        async def interrupt(self, adapter_run_id):
            release_completed.set()

        async def approve(self, adapter_run_id, approval):
            return None

        async def collectArtifacts(self, adapter_run_id):
            return []

        async def cleanup(self, adapter_run_id):
            return None

    async def record_finalizer(db, task_run, **kwargs):
        finalizer_calls.append(task_run.id)

    _allow_test_provider_health(monkeypatch)
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    monkeypatch.setattr(run_engine_module, "CodexAdapter", DelayedCompletedAdapter)
    monkeypatch.setattr(
        run_engine_module,
        "EXECUTION_LEASE_RENEWAL_INTERVAL_SECONDS",
        3600,
    )
    monkeypatch.setattr(
        run_engine_module,
        "finalize_adapter_completed_task_run",
        record_finalizer,
    )
    execution = asyncio.create_task(
        run_engine_module.execute_task_run_background(
            db_from_override(),
            run_id,
            "codex",
            worker_id="worker:old-adapter-stream",
        )
    )
    try:
        await asyncio.wait_for(stream_started.wait(), timeout=1)
        recovery_time = utc_now()
        with db_from_override() as recovery_db:
            stale_run = recovery_db.get(TaskRun, run_id)
            stale_lock = held_lock_for_target(recovery_db, DEMO_FRONTEND_TARGET_ID)
            assert stale_lock is not None
            stale_run.lease_expires_at = recovery_time - timedelta(seconds=1)
            stale_lock.lease_expires_at = recovery_time - timedelta(seconds=1)
            recovery_db.add(stale_run)
            recovery_db.add(stale_lock)
            recovery_db.commit()
            recovered = recover_stale_target_locks(
                recovery_db,
                now=recovery_time,
            )
            recovered_run = recovery_db.get(TaskRun, run_id)
            expected_error_message = recovered_run.error_message
            assert len(recovered) == 1
            assert recovered_run.state == "failed"
            assert recovered_run.error_code == "TASK_RUN_STALE"

        release_completed.set()
        await execution
        with db_from_override() as db:
            stored = db.get(TaskRun, run_id)
            completed_events = db.exec(
                select(TaskRunEvent)
                .where(TaskRunEvent.task_run_id == run_id)
                .where(TaskRunEvent.event_type == "completed")
            ).all()
            assert stored.state == "failed"
            assert stored.error_code == "TASK_RUN_STALE"
            assert stored.error_message == expected_error_message
            assert completed_events == []
            assert finalizer_calls == []
    finally:
        release_completed.set()
        if not execution.done():
            await execution


@pytest.mark.anyio
async def test_durable_adapter_run_replacement_during_real_finalizer_fails_closed(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        task_run = create_task_run(db, task.id)
        task_run_id = task_run.id

    adapter_run_id = f"adapter-run:a:{task_run_id}"
    replacement_adapter_run_id = f"adapter-run:b:{task_run_id}"
    interrupted: list[str] = []

    class CompletedAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=True,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            return AdapterRun(adapterRunId=adapter_run_id)

        async def streamEvents(self, current_adapter_run_id):
            yield AgentEvent(
                type="completed",
                taskRunId=task_run_id,
                sequence=1,
                payload={"ok": True},
            )

        async def interrupt(self, current_adapter_run_id):
            interrupted.append(current_adapter_run_id)

        async def approve(self, current_adapter_run_id, approval):
            return None

        async def collectArtifacts(self, current_adapter_run_id):
            return []

        async def cleanup(self, current_adapter_run_id):
            return None

    decision = task_run_scope.ScopeDecision(
        status="passed",
        error_code=None,
        target_id=DEMO_FRONTEND_TARGET_ID,
        changed_paths=("apps/demo/src/App.tsx",),
        rejected_paths=(),
        reason=None,
    )
    critical_side_effects: list[str] = []

    def record_sync(name: str):
        def recorder(*args, **kwargs):
            critical_side_effects.append(name)
            return decision if name in {"scope", "require"} else None

        return recorder

    async def record_downstream(*args, **kwargs):
        critical_side_effects.append("downstream")
        return None

    real_finalizer = run_engine_module.finalize_adapter_completed_task_run
    finalizer_preflight_passed = asyncio.Event()
    allow_real_finalizer = asyncio.Event()

    async def gated_real_finalizer(db, current_task_run, **kwargs):
        finalizer_preflight_passed.set()
        await allow_real_finalizer.wait()
        return await real_finalizer(db, current_task_run, **kwargs)

    _allow_test_provider_health(monkeypatch)
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    monkeypatch.setattr(run_engine_module, "CodexAdapter", CompletedAdapter)
    monkeypatch.setattr(
        run_engine_module,
        "EXECUTION_LEASE_RENEWAL_INTERVAL_SECONDS",
        0.01,
    )
    monkeypatch.setattr(
        run_engine_module,
        "finalize_adapter_completed_task_run",
        gated_real_finalizer,
    )
    monkeypatch.setattr(
        run_engine_module,
        "validate_task_run_scope",
        record_sync("scope"),
    )
    monkeypatch.setattr(
        run_engine_module,
        "persist_scope_decision",
        record_sync("persist"),
    )
    monkeypatch.setattr(
        run_engine_module,
        "require_task_run_scope_passed",
        record_sync("require"),
    )
    monkeypatch.setattr(
        run_engine_module,
        "collect_task_run_diff",
        record_sync("diff"),
    )
    monkeypatch.setattr(
        run_engine_module,
        "create_scripted_review_for_task_run",
        record_sync("review"),
    )
    monkeypatch.setattr(
        run_engine_module,
        "refresh_session_ledger_for_task_run",
        record_sync("ledger"),
    )
    monkeypatch.setattr(
        run_engine_module,
        "_complete_ready_pipeline_review_tasks",
        record_sync("review-tasks"),
    )
    monkeypatch.setattr(
        run_engine_module,
        "_maybe_auto_preview_and_mock_deploy",
        record_sync("preview"),
    )
    monkeypatch.setattr(
        run_engine_module,
        "_auto_start_next_pipeline_task",
        record_downstream,
    )

    execution = asyncio.create_task(
        run_engine_module.execute_task_run_background(
            db_from_override(),
            task_run_id,
            "codex",
            worker_id="worker:durable-adapter-replacement",
        )
    )
    finished_before_releasing_finalizer = True
    try:
        await asyncio.wait_for(finalizer_preflight_passed.wait(), timeout=1)
        with db_from_override() as mutation_db:
            stored = mutation_db.get(TaskRun, task_run_id)
            assert stored is not None
            assert stored.adapter_run_id == adapter_run_id
            stored.adapter_run_id = replacement_adapter_run_id
            mutation_db.add(stored)
            mutation_db.commit()
        try:
            await asyncio.wait_for(asyncio.shield(execution), timeout=0.5)
        except asyncio.TimeoutError:
            finished_before_releasing_finalizer = False
    finally:
        allow_real_finalizer.set()
        if not execution.done():
            await execution

    with db_from_override() as db:
        stored = db.get(TaskRun, task_run_id)
        metrics = json.loads(stored.metrics_json)
        artifacts = db.exec(
            select(Artifact).where(Artifact.task_run_id == task_run_id)
        ).all()
        scope_events = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == task_run_id)
            .where(TaskRunEvent.event_type.like("task.scope_validation.%"))
        ).all()

    assert finished_before_releasing_finalizer is True
    assert stored.state == "collecting_diff"
    assert stored.adapter_run_id == replacement_adapter_run_id
    assert stored.error_code is None
    assert stored.error_message is None
    assert interrupted == [adapter_run_id]
    assert critical_side_effects == []
    assert "scopeFinalizationClaim" not in metrics
    assert artifacts == []
    assert scope_events == []


@pytest.mark.anyio
async def test_real_scope_finalizer_never_starts_after_execution_ownership_is_lost(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        task_run = create_task_run(db, task.id)
        _acquire_scope_lock(db, task_run)
        task_run = task_runs_module.capture_task_run_scope_baseline(db, task_run.id)
        task_run = _bind_started_write_execution(db, task_run)
        transition_task_run(db, task_run.id, "collecting_diff")
        task_run = db.get(TaskRun, task_run.id)
        execution_attempt_id = json.loads(task_run.metrics_json)[
            "taskRunExecutionAccessBinding"
        ]["executionAttemptId"]
        token = run_engine_module._execution_lease_token_for_task_run(
            db,
            task_run.id,
            access_mode="write",
            execution_attempt_id=execution_attempt_id,
            expected_session_id=task.session_id,
        )
        bind = db.get_bind()
        run_id = task_run.id

    decision = task_run_scope.ScopeDecision(
        status="passed",
        error_code=None,
        target_id=DEMO_FRONTEND_TARGET_ID,
        changed_paths=("apps/demo/src/App.tsx",),
        rejected_paths=(),
        reason=None,
    )
    critical_side_effects: list[str] = []

    def record_sync(name: str):
        def recorder(*args, **kwargs):
            critical_side_effects.append(name)
            return decision if name in {"scope", "require"} else None

        return recorder

    async def record_downstream(*args, **kwargs):
        critical_side_effects.append("downstream")
        return None

    monkeypatch.setattr(run_engine_module, "validate_task_run_scope", record_sync("scope"))
    monkeypatch.setattr(run_engine_module, "persist_scope_decision", record_sync("persist"))
    monkeypatch.setattr(
        run_engine_module,
        "require_task_run_scope_passed",
        record_sync("require"),
    )
    monkeypatch.setattr(run_engine_module, "collect_task_run_diff", record_sync("diff"))
    monkeypatch.setattr(
        run_engine_module,
        "create_scripted_review_for_task_run",
        record_sync("review"),
    )
    monkeypatch.setattr(
        run_engine_module,
        "refresh_session_ledger_for_task_run",
        record_sync("ledger"),
    )
    monkeypatch.setattr(
        run_engine_module,
        "_complete_ready_pipeline_review_tasks",
        record_sync("review-tasks"),
    )
    monkeypatch.setattr(
        run_engine_module,
        "_maybe_auto_preview_and_mock_deploy",
        record_sync("preview"),
    )
    monkeypatch.setattr(
        run_engine_module,
        "_auto_start_next_pipeline_task",
        record_downstream,
    )

    interrupted: list[str] = []

    class InterruptibleAdapter:
        async def interrupt(self, adapter_run_id):
            interrupted.append(adapter_run_id)

    supervisor = run_engine_module.RunSupervisor()
    supervisor.register(
        task_run_id=run_id,
        adapter_type="codex",
        adapter_run_id=f"adapter-run:{run_id}",
        adapter=InterruptibleAdapter(),
    )

    controller = run_engine_module._ExecutionLeaseController(
        bind,
        interval_seconds=3600,
    )
    controller.start(token)
    assert controller._ownership_lost.is_set() is False
    with db_from_override() as ownership_db:
        released = release_target_lock_for_task_run(
            ownership_db,
            target_id=token.target_id,
            expected_lock_id=token.expected_lock_id,
            worker_id=token.runner_id,
            task_run_id=token.task_run_id,
            session_id=token.session_id,
            release_reason="rotate_before_scope_finalizer_preflight",
        )
        assert released is not None
        replacement = acquire_target_lock(
            ownership_db,
            target_id=token.target_id,
            session_id=token.session_id,
            task_run_id=token.task_run_id,
            worker_id=token.runner_id,
            lease_expires_at=ownership_db.get(
                TaskRun,
                token.task_run_id,
            ).lease_expires_at,
        )
        assert replacement.acquired is True
        assert replacement.lock is not None
        assert replacement.lock.id != token.expected_lock_id
    assert controller._ownership_lost.is_set() is False

    ownership_error = None
    with db_from_override() as db:
        before_event_ids = {
            event.id
            for event in db.exec(
                select(TaskRunEvent).where(TaskRunEvent.task_run_id == run_id)
            ).all()
        }
        before_artifact_ids = {
            artifact.id
            for artifact in db.exec(
                select(Artifact).where(Artifact.task_run_id == run_id)
            ).all()
        }
        try:
            try:
                await run_engine_module._run_with_execution_lease(
                    run_engine_module.finalize_adapter_completed_task_run(
                        db,
                        db.get(TaskRun, run_id),
                    ),
                    controller,
                    supervisor=supervisor,
                    task_run_id=run_id,
                )
            except task_run_scope.TaskRunScopeError as exc:
                ownership_error = exc
        finally:
            await controller.stop()

        db.expire_all()
        stored = db.get(TaskRun, run_id)
        metrics = json.loads(stored.metrics_json)
        after_event_ids = {
            event.id
            for event in db.exec(
                select(TaskRunEvent).where(TaskRunEvent.task_run_id == run_id)
            ).all()
        }
        after_artifact_ids = {
            artifact.id
            for artifact in db.exec(
                select(Artifact).where(Artifact.task_run_id == run_id)
            ).all()
        }

    assert critical_side_effects == []
    assert ownership_error is not None
    assert ownership_error.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert interrupted == [f"adapter-run:{run_id}"]
    assert controller._ownership_lost.is_set() is False
    assert stored.state == "collecting_diff"
    assert "scopeFinalizationClaim" not in metrics
    assert after_artifact_ids == before_artifact_ids
    assert after_event_ids == before_event_ids


class _FinalizerFencePausingSupervisor(run_engine_module.RunSupervisor):
    def __init__(self) -> None:
        super().__init__()
        self.finalizer_waiting = Event()
        self.competitor_finished = Event()

    def commit_if_current(self, expected, operation):
        self.finalizer_waiting.set()
        if not self.competitor_finished.wait(timeout=2):
            raise AssertionError("The competing generation operation did not finish.")
        return super().commit_if_current(expected, operation)


class _FenceRaceCompletedAdapter:
    def __init__(self, task_run_id: str, interrupted: list[str]) -> None:
        self.task_run_id = task_run_id
        self.adapter_run_id = f"adapter-run:a:{task_run_id}"
        self.interrupted = interrupted

    def getCapabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supportsStreaming=True,
            supportsInterrupt=True,
            supportsApproval=False,
            supportsFileEdit=True,
            supportsShellCommand=False,
            supportsDiffArtifact=False,
            supportsPreviewArtifact=False,
            supportsNetwork=False,
        )

    async def createRun(self, request):
        return AdapterRun(adapterRunId=self.adapter_run_id)

    async def streamEvents(self, adapter_run_id):
        yield AgentEvent(
            type="completed",
            taskRunId=self.task_run_id,
            sequence=1,
            payload={"ok": True},
        )

    async def interrupt(self, adapter_run_id):
        self.interrupted.append(adapter_run_id)

    async def approve(self, adapter_run_id, approval):
        return None

    async def collectArtifacts(self, adapter_run_id):
        return []

    async def cleanup(self, adapter_run_id):
        return None


def _prepare_write_finalizer_fence_race(
    db: DbSession,
    monkeypatch: pytest.MonkeyPatch,
    *,
    worker_id: str,
) -> TaskRun:
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    task = db.get(Task, task_id())
    task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
    db.add(task)
    db.commit()
    task_run = claim_task_run_for_worker(
        db,
        create_task_run(db, task.id).id,
        worker_id=worker_id,
    )
    assert run_engine_module._prepare_claimed_task_run_for_adapter(
        db,
        task_run,
        worker_id,
    ) is True
    stored = db.get(TaskRun, task_run.id)
    assert stored is not None
    return stored


def _record_finalizer_critical_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> list[str]:
    calls: list[str] = []

    def record_sync(name: str):
        def recorder(*args, **kwargs):
            calls.append(name)
            return None

        return recorder

    async def record_downstream(*args, **kwargs):
        calls.append("downstream")
        return None

    monkeypatch.setattr(
        run_engine_module,
        "collect_task_run_diff",
        record_sync("diff"),
    )
    monkeypatch.setattr(
        run_engine_module,
        "create_scripted_review_for_task_run",
        record_sync("review"),
    )
    monkeypatch.setattr(
        run_engine_module,
        "refresh_session_ledger_for_task_run",
        record_sync("ledger"),
    )
    monkeypatch.setattr(
        run_engine_module,
        "_complete_ready_pipeline_review_tasks",
        record_sync("review-tasks"),
    )
    monkeypatch.setattr(
        run_engine_module,
        "_maybe_auto_preview_and_mock_deploy",
        record_sync("preview-deploy"),
    )
    monkeypatch.setattr(
        run_engine_module,
        "_auto_start_next_pipeline_task",
        record_downstream,
    )
    return calls


@pytest.mark.anyio
async def test_generation_replacement_wins_before_real_finalizer_commit_fence(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    task_run = _prepare_write_finalizer_fence_race(
        db,
        monkeypatch,
        worker_id="worker:finalizer-fence-replacement-a",
    )
    task_run_id = task_run.id
    critical_calls = _record_finalizer_critical_calls(monkeypatch)
    generation_a_interrupts: list[str] = []
    generation_b_interrupts: list[str] = []
    thread_errors: list[BaseException] = []
    supervisor = _FinalizerFencePausingSupervisor()
    replacement: list[run_engine_module.SupervisedRun] = []

    class GenerationBAdapter:
        async def interrupt(self, adapter_run_id):
            generation_b_interrupts.append(adapter_run_id)

    def replace_generation() -> None:
        try:
            if not supervisor.finalizer_waiting.wait(timeout=2):
                return
            replacement.append(
                supervisor.register(
                    task_run_id=task_run_id,
                    adapter_type="scripted_mock",
                    adapter_run_id=f"adapter-run:b:{task_run_id}",
                    adapter=GenerationBAdapter(),
                )
            )
        except BaseException as exc:
            thread_errors.append(exc)
        finally:
            supervisor.competitor_finished.set()

    replacement_thread = Thread(target=replace_generation)
    replacement_thread.start()
    try:
        await run_engine_module.execute_task_run(
            db,
            task_run,
            adapter_type="scripted_mock",
            adapter=_FenceRaceCompletedAdapter(
                task_run_id,
                generation_a_interrupts,
            ),
            supervisor=supervisor,
            lease_renewal_interval_seconds=3600,
        )
    finally:
        supervisor.finalizer_waiting.set()
        supervisor.competitor_finished.set()
        replacement_thread.join(timeout=2)
        db.close()

    assert replacement_thread.is_alive() is False
    assert thread_errors == []
    assert len(replacement) == 1
    assert supervisor.active(task_run_id) is replacement[0]
    assert replacement[0].adapter_run_id == f"adapter-run:b:{task_run_id}"
    assert generation_b_interrupts == []
    assert generation_a_interrupts == [f"adapter-run:a:{task_run_id}"]
    assert critical_calls == []
    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        scope_passed = verification_db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == task_run_id)
            .where(TaskRunEvent.event_type == "task.scope_validation.passed")
        ).all()
        state_events = verification_db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == task_run_id)
            .where(TaskRunEvent.event_type == "task.state")
        ).all()
        assert verification_db.exec(
            select(Diff)
            .join(Artifact, Diff.artifact_id == Artifact.id)
            .where(Artifact.task_run_id == task_run_id)
        ).all() == []
        assert verification_db.exec(
            select(Review)
            .join(Artifact, Review.artifact_id == Artifact.id)
            .where(Artifact.task_run_id == task_run_id)
        ).all() == []
        assert verification_db.exec(
            select(Preview)
            .join(Artifact, Preview.artifact_id == Artifact.id)
            .where(Artifact.task_run_id == task_run_id)
        ).all() == []
        assert verification_db.exec(
            select(Deployment)
            .join(Artifact, Deployment.artifact_id == Artifact.id)
            .where(Artifact.task_run_id == task_run_id)
        ).all() == []
    assert stored is not None
    assert stored.state == "collecting_diff"
    assert scope_passed == []
    assert all(json.loads(item.payload_json).get("state") != "completed" for item in state_events)


@pytest.mark.anyio
async def test_user_interrupt_wins_before_real_finalizer_commit_fence(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    task_run = _prepare_write_finalizer_fence_race(
        db,
        monkeypatch,
        worker_id="worker:finalizer-fence-user-interrupt",
    )
    task_run_id = task_run.id
    critical_calls = _record_finalizer_critical_calls(monkeypatch)
    adapter_interrupts: list[str] = []
    interrupt_results: list[bool] = []
    thread_errors: list[BaseException] = []
    supervisor = _FinalizerFencePausingSupervisor()

    def interrupt_generation() -> None:
        try:
            if not supervisor.finalizer_waiting.wait(timeout=2):
                return
            interrupt_results.append(
                asyncio.run(
                    run_engine_module.interrupt_supervised_task_run(
                        task_run_id,
                        supervisor=supervisor,
                    )
                )
            )
            with db_from_override() as interrupt_db:
                task_runs_module.interrupt_task_run(interrupt_db, task_run_id)
        except BaseException as exc:
            thread_errors.append(exc)
        finally:
            supervisor.competitor_finished.set()

    interrupt_thread = Thread(target=interrupt_generation)
    interrupt_thread.start()
    try:
        await run_engine_module.execute_task_run(
            db,
            task_run,
            adapter_type="scripted_mock",
            adapter=_FenceRaceCompletedAdapter(task_run_id, adapter_interrupts),
            supervisor=supervisor,
            lease_renewal_interval_seconds=3600,
        )
    finally:
        supervisor.finalizer_waiting.set()
        supervisor.competitor_finished.set()
        interrupt_thread.join(timeout=2)
        db.close()

    assert interrupt_thread.is_alive() is False
    assert thread_errors == []
    assert interrupt_results == [True]
    assert adapter_interrupts == [f"adapter-run:a:{task_run_id}"]
    assert critical_calls == []
    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        scope_passed = verification_db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == task_run_id)
            .where(TaskRunEvent.event_type == "task.scope_validation.passed")
        ).all()
        state_events = verification_db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == task_run_id)
            .where(TaskRunEvent.event_type == "task.state")
        ).all()
    assert stored is not None
    assert stored.state == "interrupted"
    assert scope_passed == []
    assert all(json.loads(item.payload_json).get("state") != "completed" for item in state_events)


@pytest.mark.anyio
async def test_real_finalizer_winner_seals_generation_through_async_downstream(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    task_run = _prepare_write_finalizer_fence_race(
        db,
        monkeypatch,
        worker_id="worker:finalizer-fence-winner",
    )
    task_run_id = task_run.id
    adapter_interrupts: list[str] = []
    replacement_interrupts: list[str] = []
    downstream_started = asyncio.Event()
    allow_downstream = asyncio.Event()
    downstream_calls: list[str] = []
    supervisor = run_engine_module.RunSupervisor()

    monkeypatch.setattr(
        run_engine_module,
        "collect_task_run_diff",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        run_engine_module,
        "create_scripted_review_for_task_run",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        run_engine_module,
        "refresh_session_ledger_for_task_run",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        run_engine_module,
        "_complete_ready_pipeline_review_tasks",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        run_engine_module,
        "_maybe_auto_preview_and_mock_deploy",
        lambda *args, **kwargs: None,
    )

    async def blocked_downstream(*args, **kwargs):
        downstream_calls.append(task_run_id)
        downstream_started.set()
        await allow_downstream.wait()
        return None

    monkeypatch.setattr(
        run_engine_module,
        "_auto_start_next_pipeline_task",
        blocked_downstream,
    )

    class ReplacementAdapter:
        async def interrupt(self, adapter_run_id):
            replacement_interrupts.append(adapter_run_id)

    execution = asyncio.create_task(
        run_engine_module.execute_task_run(
            db,
            task_run,
            adapter_type="scripted_mock",
            adapter=_FenceRaceCompletedAdapter(task_run_id, adapter_interrupts),
            supervisor=supervisor,
            lease_renewal_interval_seconds=3600,
        )
    )
    execution_error: Optional[BaseException] = None
    try:
        await asyncio.wait_for(downstream_started.wait(), timeout=2)
        generation_a = supervisor.active(task_run_id)
        assert generation_a is not None
        assert generation_a.adapter_run_id == f"adapter-run:a:{task_run_id}"

        public_interrupted = await run_engine_module.interrupt_supervised_task_run(
            task_run_id,
            supervisor=supervisor,
        )
        exact_interrupted = await run_engine_module._interrupt_exact_supervised_run(
            supervisor,
            generation_a,
        )
        with pytest.raises(RuntimeError, match="sealed"):
            supervisor.register(
                task_run_id=task_run_id,
                adapter_type="scripted_mock",
                adapter_run_id=f"adapter-run:b:{task_run_id}",
                adapter=ReplacementAdapter(),
            )

        assert public_interrupted is False
        assert exact_interrupted is False
        assert supervisor.active(task_run_id) is generation_a
        assert generation_a._generation._lost is False
        assert generation_a._generation._sealed is True
    finally:
        allow_downstream.set()
        try:
            await execution
        except BaseException as exc:
            execution_error = exc
        db.close()

    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
    assert execution_error is None
    assert stored is not None
    assert stored.state == "completed"
    assert downstream_calls == [task_run_id]
    assert adapter_interrupts == []
    assert replacement_interrupts == []


@pytest.mark.anyio
async def test_terminal_commit_before_sync_side_effect_error_keeps_generation_sealed(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    _, task_run, _, _ = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id="worker:terminal-before-sync-side-effect-error",
    )
    task_run_id = task_run.id
    terminal_observations: list[tuple[str, str]] = []

    class CompletingReadonlyAdapter(_ReadonlyCreateRunDelegate):
        async def streamEvents(self, current_adapter_run_id):
            yield {"type": "completed", "payload": {}}

        async def interrupt(self, current_adapter_run_id):
            return None

        async def approve(self, current_adapter_run_id, approval):
            return None

        async def collectArtifacts(self, current_adapter_run_id):
            return []

        async def cleanup(self, current_adapter_run_id):
            return None

    monkeypatch.setattr(
        run_engine_module,
        "collect_task_run_diff",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        run_engine_module,
        "create_scripted_review_for_task_run",
        lambda *args, **kwargs: None,
    )

    def fail_sync_side_effects(current_db, current_task_run) -> None:
        with db_from_override() as verification_db:
            stored = verification_db.get(TaskRun, task_run_id)
            durable_queue = entry_for_task_run(verification_db, task_run_id)
            assert stored is not None
            assert durable_queue is not None
            terminal_observations.append((stored.state, durable_queue.state))
        raise RuntimeError("injected sync side effect failure after terminal commit")

    monkeypatch.setattr(
        run_engine_module,
        "_run_completed_task_run_sync_side_effects",
        fail_sync_side_effects,
    )

    def forbid_posthoc_terminal_winner_inference(*args, **kwargs):
        raise AssertionError("terminal sealing must come from the after_commit milestone")

    monkeypatch.setattr(
        run_engine_module,
        "_durable_terminal_finalizer_winner",
        forbid_posthoc_terminal_winner_inference,
        raising=False,
    )
    supervisor = run_engine_module.RunSupervisor()

    with pytest.raises(
        RuntimeError,
        match="injected sync side effect failure after terminal commit",
    ):
        await run_engine_module.execute_task_run(
            db,
            task_run,
            adapter_type="scripted_mock",
            adapter=CompletingReadonlyAdapter(),
            supervisor=supervisor,
            lease_renewal_interval_seconds=3600,
        )
    db.close()

    assert terminal_observations == [("completed", "completed")]
    assert supervisor.active(task_run_id) is None
    with pytest.raises(RunRegistrationRejected, match="sealed"):
        supervisor.register(
            task_run_id=task_run_id,
            adapter_type="scripted_mock",
        )
    assert await supervisor.interrupt(task_run_id) is False
    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        durable_queue = entry_for_task_run(verification_db, task_run_id)
    assert stored is not None
    assert durable_queue is not None
    assert stored.state == "completed"
    assert durable_queue.state == "completed"


@pytest.mark.anyio
async def test_finalizer_callback_without_terminal_after_commit_milestone_does_not_seal(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    task_run_id, controller = _prepare_finalizer_execution_lease(
        db,
        monkeypatch,
        worker_id="worker:finalizer-without-terminal-milestone",
        execution_attempt_id="attempt:finalizer-without-terminal-milestone",
        adapter_run_id="adapter-run:finalizer-without-terminal-milestone",
    )
    task_run = transition_task_run(db, task_run_id, "collecting_diff")
    supervisor = run_engine_module.RunSupervisor()
    generation_a = supervisor.register(
        task_run_id=task_run_id,
        adapter_type="scripted_mock",
        adapter_run_id=task_run.adapter_run_id,
    )
    monkeypatch.setattr(
        run_engine_module,
        "_commit_adapter_completed_task_run",
        lambda *args, **kwargs: True,
    )

    try:
        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            run_engine_module._commit_exact_generation_finalizer(
                db,
                task_run,
                lease_controller=controller,
                supervisor=supervisor,
                expected_supervised_run=generation_a,
            )
    finally:
        await controller.stop()
        db.close()

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert generation_a._generation.is_sealed() is False
    generation_b = supervisor.register(
        task_run_id=task_run_id,
        adapter_type="scripted_mock",
    )
    assert generation_b is not generation_a
    assert generation_a._generation.is_lost() is True


@pytest.mark.anyio
async def test_concurrent_execute_rejects_sealed_generation_without_disturbing_winner(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    _, task_run, _, _ = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id="worker:sealed-register-winner",
    )
    task_run_id = task_run.id
    adapter_run_id = f"adapter-run:sealed-winner:{task_run_id}"
    downstream_started = asyncio.Event()
    allow_downstream = asyncio.Event()
    downstream_calls: list[str] = []
    winner_adapter_starts: list[str] = []
    late_adapter_starts: list[str] = []
    supervisor = run_engine_module.RunSupervisor()

    class CompletingReadonlyAdapter:
        def __init__(self, starts: list[str], run_id: str) -> None:
            self.starts = starts
            self.run_id = run_id

        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=False,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            self.starts.append(request.task_run_id)
            return AdapterRun(adapterRunId=self.run_id)

        async def streamEvents(self, current_adapter_run_id):
            yield {"type": "completed", "payload": {}}

        async def interrupt(self, current_adapter_run_id):
            return None

        async def approve(self, current_adapter_run_id, approval):
            return None

        async def collectArtifacts(self, current_adapter_run_id):
            return []

        async def cleanup(self, current_adapter_run_id):
            return None

    monkeypatch.setattr(
        run_engine_module,
        "collect_task_run_diff",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        run_engine_module,
        "create_scripted_review_for_task_run",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        run_engine_module,
        "refresh_session_ledger_for_task_run",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        run_engine_module,
        "_complete_ready_pipeline_review_tasks",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        run_engine_module,
        "_maybe_auto_preview_and_mock_deploy",
        lambda *args, **kwargs: None,
    )

    async def blocked_downstream(*args, **kwargs):
        downstream_calls.append("started")
        downstream_started.set()
        await allow_downstream.wait()
        downstream_calls.append("finished")
        return None

    monkeypatch.setattr(
        run_engine_module,
        "_auto_start_next_pipeline_task",
        blocked_downstream,
    )

    execution = asyncio.create_task(
        run_engine_module.execute_task_run(
            db,
            task_run,
            adapter_type="scripted_mock",
            adapter=CompletingReadonlyAdapter(
                winner_adapter_starts,
                adapter_run_id,
            ),
            supervisor=supervisor,
            lease_renewal_interval_seconds=3600,
        )
    )
    try:
        await asyncio.wait_for(downstream_started.wait(), timeout=2)
        generation_a = supervisor.active(task_run_id)
        assert generation_a is not None
        assert generation_a._generation.is_sealed() is True
        assert generation_a._generation.is_lost() is False

        with db_from_override() as late_db:
            late_task_run = late_db.get(TaskRun, task_run_id)
            assert late_task_run is not None
            with pytest.raises(RuntimeError, match="sealed"):
                await run_engine_module.execute_task_run(
                    late_db,
                    late_task_run,
                    adapter_type="scripted_mock",
                    adapter=CompletingReadonlyAdapter(
                        late_adapter_starts,
                        f"adapter-run:sealed-late:{task_run_id}",
                    ),
                    supervisor=supervisor,
                    lease_renewal_interval_seconds=3600,
                )

        assert late_adapter_starts == []
        assert supervisor.active(task_run_id) is generation_a
        assert generation_a._generation.is_lost() is False
        assert generation_a._generation.is_sealed() is True
    finally:
        allow_downstream.set()
        await asyncio.gather(execution, return_exceptions=True)
        db.close()

    assert winner_adapter_starts == [task_run_id]
    assert downstream_calls == ["started", "finished"]


@pytest.mark.anyio
async def test_replaced_generation_after_prepare_cannot_bind_or_launch(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    task_run = _prepare_write_finalizer_fence_race(
        db,
        monkeypatch,
        worker_id="worker:replaced-after-prepare-a",
    )
    task_run_id = task_run.id
    adapter_run_id = f"adapter-run:replaced-after-prepare-a:{task_run_id}"
    adapter_starts: list[str] = []
    replacement: list[run_engine_module.SupervisedRun] = []
    prepared_task_run_snapshots: list[dict[str, object]] = []
    prepared_queue_snapshots: list[dict[str, object]] = []

    class ReplaceAfterPrepareSupervisor(run_engine_module.RunSupervisor):
        def run_if_current(self, expected, operation):
            current, prepared = super().run_if_current(expected, operation)
            if current and prepared is not None and not replacement:
                replacement.append(
                    self.register(
                        task_run_id=expected.task_run_id,
                        adapter_type="scripted_mock",
                        adapter_run_id=f"adapter-run:replaced-after-prepare-b:{task_run_id}",
                    )
                )
                with db_from_override() as snapshot_db:
                    stored = snapshot_db.get(TaskRun, task_run_id)
                    queue_entry = entry_for_task_run(snapshot_db, task_run_id)
                    assert stored is not None
                    assert queue_entry is not None
                    prepared_task_run_snapshots.append(
                        stored.model_dump(mode="python")
                    )
                    prepared_queue_snapshots.append(
                        queue_entry.model_dump(mode="python")
                    )
            return current, prepared

    class GenerationAAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=True,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            adapter_starts.append(request.task_run_id)
            return AdapterRun(adapterRunId=adapter_run_id)

        async def streamEvents(self, current_adapter_run_id):
            yield {"type": "completed", "payload": {}}

        async def interrupt(self, current_adapter_run_id):
            return None

        async def approve(self, current_adapter_run_id, approval):
            return None

        async def collectArtifacts(self, current_adapter_run_id):
            return []

        async def cleanup(self, current_adapter_run_id):
            return None

    supervisor = ReplaceAfterPrepareSupervisor()
    try:
        await run_engine_module.execute_task_run(
            db,
            task_run,
            adapter_type="scripted_mock",
            adapter=GenerationAAdapter(),
            supervisor=supervisor,
            lease_renewal_interval_seconds=3600,
        )
    finally:
        db.close()

    assert adapter_starts == []
    assert len(replacement) == 1
    assert len(prepared_task_run_snapshots) == 1
    assert len(prepared_queue_snapshots) == 1
    prepared_metrics = json.loads(
        str(prepared_task_run_snapshots[0]["metrics_json"])
    )
    prepared_checkpoint = prepared_metrics.get("preRunCheckpoint")
    assert isinstance(prepared_checkpoint, dict)
    assert "scopeExecutionAttemptId" not in prepared_checkpoint
    assert "scopeBaseline" not in prepared_checkpoint
    assert "taskRunExecutionAccessBinding" not in prepared_metrics

    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        queue_entry = entry_for_task_run(verification_db, task_run_id)
        assert stored is not None
        assert queue_entry is not None
        assert stored.model_dump(mode="python") == prepared_task_run_snapshots[0]
        assert queue_entry.model_dump(mode="python") == prepared_queue_snapshots[0]

    assert supervisor.active(task_run_id) is replacement[0]


@pytest.mark.anyio
async def test_prepare_scope_failure_cannot_fail_replacement_generation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    _, task_run, queue_entry, _ = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id="worker:prepare-scope-failure-a",
    )
    task_run_id = task_run.id
    initial_task_run = task_run.model_dump(mode="python")
    initial_queue_entry = queue_entry.model_dump(mode="python")
    adapter_starts: list[str] = []
    replacement: list[run_engine_module.SupervisedRun] = []

    class ReplaceAtFailureGateSupervisor(run_engine_module.RunSupervisor):
        def __init__(self) -> None:
            super().__init__()
            self.prepare_failed = False

        def run_if_current(self, expected, operation):
            if self.prepare_failed and not replacement:
                replacement.append(
                    self.register(
                        task_run_id=expected.task_run_id,
                        adapter_type="scripted_mock",
                        adapter_run_id=f"adapter-run:prepare-failure-b:{task_run_id}",
                    )
                )
            try:
                return super().run_if_current(expected, operation)
            except task_run_scope.TaskRunScopeError:
                self.prepare_failed = True
                raise

    valid_capabilities = AdapterCapabilities(
        supportsStreaming=True,
        supportsInterrupt=True,
        supportsApproval=False,
        supportsFileEdit=False,
        supportsShellCommand=False,
        supportsDiffArtifact=False,
        supportsPreviewArtifact=False,
        supportsNetwork=False,
    )
    malformed_capabilities = valid_capabilities.model_copy(deep=True)
    malformed_capabilities.supports_file_edit = None

    class MalformedCapabilitiesAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return malformed_capabilities

        async def createRun(self, request):
            adapter_starts.append(request.task_run_id)
            return AdapterRun(adapterRunId="prepare-failure-must-not-start")

        async def streamEvents(self, current_adapter_run_id):
            yield {"type": "completed", "payload": {}}

        async def interrupt(self, current_adapter_run_id):
            return None

        async def approve(self, current_adapter_run_id, approval):
            return None

        async def collectArtifacts(self, current_adapter_run_id):
            return []

        async def cleanup(self, current_adapter_run_id):
            return None

    supervisor = ReplaceAtFailureGateSupervisor()
    try:
        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            await run_engine_module.execute_task_run(
                db,
                task_run,
                adapter_type="scripted_mock",
                adapter=MalformedCapabilitiesAdapter(),
                supervisor=supervisor,
                lease_renewal_interval_seconds=3600,
            )
    finally:
        db.close()

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert exc_info.value.message == (
        "The task run execution access binding cannot be verified."
    )
    assert adapter_starts == []
    assert len(replacement) == 1
    assert supervisor.active(task_run_id) is replacement[0]
    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        stored_queue_entry = entry_for_task_run(verification_db, task_run_id)
        assert stored is not None
        assert stored_queue_entry is not None
        assert stored.model_dump(mode="python") == initial_task_run
        assert stored_queue_entry.model_dump(mode="python") == initial_queue_entry


@pytest.mark.anyio
async def test_replacement_after_binding_error_does_not_hide_scope_failure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    task_run = _prepare_write_finalizer_fence_race(
        db,
        monkeypatch,
        worker_id="worker:binding-error-replacement-a",
    )
    task_run_id = task_run.id
    capability_reads = 0
    adapter_starts: list[str] = []
    replacement: list[run_engine_module.SupervisedRun] = []

    class ReplaceAfterBindingErrorSupervisor(run_engine_module.RunSupervisor):
        async def run_async_if_current(self, expected, operation):
            try:
                return await super().run_async_if_current(expected, operation)
            except task_run_scope.TaskRunScopeError:
                replacement.append(
                    self.register(
                        task_run_id=expected.task_run_id,
                        adapter_type="scripted_mock",
                        adapter_run_id=(
                            f"adapter-run:binding-error-replacement-b:{task_run_id}"
                        ),
                    )
                )
                raise

    class DriftingCapabilitiesAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            nonlocal capability_reads
            capability_reads += 1
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=True,
                supportsShellCommand=capability_reads > 1,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            adapter_starts.append(request.task_run_id)
            return AdapterRun(
                adapterRunId=f"adapter-run:binding-error-a:{task_run_id}"
            )

        async def streamEvents(self, current_adapter_run_id):
            yield {"type": "completed", "payload": {}}

        async def interrupt(self, current_adapter_run_id):
            return None

        async def approve(self, current_adapter_run_id, approval):
            return None

        async def collectArtifacts(self, current_adapter_run_id):
            return []

        async def cleanup(self, current_adapter_run_id):
            return None

    supervisor = ReplaceAfterBindingErrorSupervisor()
    try:
        await run_engine_module.execute_task_run(
            db,
            task_run,
            adapter_type="scripted_mock",
            adapter=DriftingCapabilitiesAdapter(),
            supervisor=supervisor,
            lease_renewal_interval_seconds=3600,
        )
    finally:
        db.close()

    assert capability_reads == 2
    assert adapter_starts == []
    assert len(replacement) == 1
    assert supervisor.active(task_run_id) is replacement[0]
    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        queue_entry = entry_for_task_run(verification_db, task_run_id)
        assert stored is not None
        assert queue_entry is not None
        assert stored.state == "failed"
        assert stored.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
        assert stored.adapter_run_id is None
        assert queue_entry.state == "failed"
        metrics = json.loads(stored.metrics_json)
        checkpoint = metrics.get("preRunCheckpoint")
        assert isinstance(checkpoint, dict)
        assert "scopeExecutionAttemptId" in checkpoint
        assert "scopeBaseline" in checkpoint
        assert "taskRunExecutionAccessBinding" not in metrics


@pytest.mark.anyio
async def test_unregistered_sealed_generation_rejects_dirty_execute_without_sql_writes(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    _, task_run, queue_entry, _ = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id="worker:unregistered-sealed-dirty-execute",
    )
    task_run_id = task_run.id
    original_metrics_json = task_run.metrics_json
    original_blocked_reason = queue_entry.blocked_reason
    supervisor = run_engine_module.RunSupervisor()
    winner = supervisor.register(
        task_run_id=task_run_id,
        adapter_type="scripted_mock",
    )

    def seal_winner() -> None:
        assert supervisor.seal_reserved_if_current(winner) is True

    assert supervisor.commit_if_current(winner, seal_winner) == (True, None)
    assert supervisor.unregister(task_run_id, expected=winner) is winner
    assert supervisor.active(task_run_id) is None

    task_run.metrics_json = json.dumps(
        {"staleGenerationMetric": True},
        separators=(",", ":"),
    )
    queue_entry.blocked_reason = "stale generation must be rolled back"
    db.add(task_run)
    db.add(queue_entry)
    writes: list[str] = []

    def record_sql_writes(
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        normalized = statement.lstrip().casefold()
        if normalized.startswith(("insert ", "update ", "delete ", "replace ")):
            writes.append(statement)

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", record_sql_writes)
    try:
        with pytest.raises(RunRegistrationRejected, match="sealed"):
            await run_engine_module.execute_task_run(
                db,
                task_run,
                adapter_type="scripted_mock",
                adapter=_ReadonlyCreateRunDelegate(),
                supervisor=supervisor,
                lease_renewal_interval_seconds=3600,
            )
        db.commit()
    finally:
        event.remove(engine, "before_cursor_execute", record_sql_writes)
        db.close()

    assert writes == []
    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        durable_queue = entry_for_task_run(verification_db, task_run_id)
    assert stored is not None
    assert durable_queue is not None
    assert stored.metrics_json == original_metrics_json
    assert durable_queue.blocked_reason == original_blocked_reason


@pytest.mark.anyio
async def test_registered_generation_replaced_before_request_cannot_persist_metrics(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    _, task_run, _, _ = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id="worker:registered-stale-request",
    )
    task_run_id = task_run.id
    stale_registered = Event()
    allow_stale_request = Event()
    stale_errors: list[BaseException] = []
    stale_adapter_starts: list[str] = []

    class PauseFirstRegistrationSupervisor(run_engine_module.RunSupervisor):
        def register(self, **kwargs):
            registered = super().register(**kwargs)
            if not stale_registered.is_set():
                stale_registered.set()
                if not allow_stale_request.wait(timeout=2):
                    raise AssertionError("The stale registered generation was not released.")
            return registered

    class CompletingReadonlyAdapter:
        def __init__(self, starts: list[str], adapter_run_id: str) -> None:
            self.starts = starts
            self.adapter_run_id = adapter_run_id

        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=False,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            self.starts.append(request.task_run_id)
            return AdapterRun(adapterRunId=self.adapter_run_id)

        async def streamEvents(self, current_adapter_run_id):
            yield {"type": "completed", "payload": {}}

        async def interrupt(self, current_adapter_run_id):
            return None

        async def approve(self, current_adapter_run_id, approval):
            return None

        async def collectArtifacts(self, current_adapter_run_id):
            return []

        async def cleanup(self, current_adapter_run_id):
            return None

    monkeypatch.setattr(
        run_engine_module,
        "collect_task_run_diff",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        run_engine_module,
        "create_scripted_review_for_task_run",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        run_engine_module,
        "refresh_session_ledger_for_task_run",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        run_engine_module,
        "_complete_ready_pipeline_review_tasks",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        run_engine_module,
        "_maybe_auto_preview_and_mock_deploy",
        lambda *args, **kwargs: None,
    )

    async def no_downstream(*args, **kwargs):
        return None

    monkeypatch.setattr(
        run_engine_module,
        "_auto_start_next_pipeline_task",
        no_downstream,
    )
    supervisor = PauseFirstRegistrationSupervisor()

    def run_stale_execute() -> None:
        try:
            with db_from_override() as stale_db:
                stale_task_run = stale_db.get(TaskRun, task_run_id)
                assert stale_task_run is not None
                asyncio.run(
                    run_engine_module.execute_task_run(
                        stale_db,
                        stale_task_run,
                        adapter_type="scripted_mock",
                        adapter=CompletingReadonlyAdapter(
                            stale_adapter_starts,
                            f"adapter-run:stale:{task_run_id}",
                        ),
                        supervisor=supervisor,
                        lease_renewal_interval_seconds=3600,
                    )
                )
        except BaseException as exc:
            stale_errors.append(exc)

    stale_thread = Thread(target=run_stale_execute, daemon=True)
    winner_starts: list[str] = []
    stale_thread.start()
    try:
        assert await asyncio.to_thread(stale_registered.wait, 2)
        await run_engine_module.execute_task_run(
            db,
            task_run,
            adapter_type="scripted_mock",
            adapter=CompletingReadonlyAdapter(
                winner_starts,
                f"adapter-run:winner:{task_run_id}",
            ),
            supervisor=supervisor,
            lease_renewal_interval_seconds=3600,
        )
        assert supervisor.active(task_run_id) is None
        with db_from_override() as verification_db:
            winner = verification_db.get(TaskRun, task_run_id)
            assert winner is not None
            winner_snapshot = winner.model_dump()

        allow_stale_request.set()
        await asyncio.to_thread(stale_thread.join, 2)
        assert stale_thread.is_alive() is False
        with db_from_override() as verification_db:
            after_stale = verification_db.get(TaskRun, task_run_id)
            assert after_stale is not None
            after_stale_snapshot = after_stale.model_dump()
    finally:
        allow_stale_request.set()
        await asyncio.to_thread(stale_thread.join, 2)
        db.close()

    assert len(stale_errors) == 1
    assert isinstance(stale_errors[0], task_run_scope.TaskRunScopeError)
    assert stale_errors[0].error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert winner_starts == [task_run_id]
    assert stale_adapter_starts == []
    assert after_stale_snapshot == winner_snapshot


@pytest.mark.anyio
async def test_request_snapshot_cas_rejects_terminal_durable_run_and_queue(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    _, task_run, queue_entry, _ = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id="worker:request-snapshot-terminal-cas",
    )
    task_run_id = task_run.id
    original_persist_context_snapshot = run_engine_module._persist_context_snapshot
    adapter_starts: list[str] = []

    def terminalize_before_context_snapshot(
        current_db,
        current_task_run,
        context_pack,
        **kwargs,
    ) -> None:
        terminalized_at = utc_now()
        run_result = current_db.execute(
            update(TaskRun)
            .where(TaskRun.id == task_run_id)
            .where(TaskRun.state.in_(task_runs_module.ACTIVE_STATES))
            .values(
                state="interrupted",
                error_code="COMPETING_REQUEST_FINALIZER",
                error_message="A competing owner finalized before request persistence.",
                ended_at=terminalized_at,
                updated_at=terminalized_at,
            )
            .execution_options(synchronize_session=False)
        )
        queue_result = current_db.execute(
            update(SessionQueueEntry)
            .where(SessionQueueEntry.id == queue_entry.id)
            .where(SessionQueueEntry.state == "running")
            .values(state="interrupted", finished_at=terminalized_at)
            .execution_options(synchronize_session=False)
        )
        current_db.commit()
        assert run_result.rowcount == 1
        assert queue_result.rowcount == 1
        original_persist_context_snapshot(
            current_db,
            current_task_run,
            context_pack,
            **kwargs,
        )

    monkeypatch.setattr(
        run_engine_module,
        "_persist_context_snapshot",
        terminalize_before_context_snapshot,
    )

    class RecordingReadonlyAdapter(_ReadonlyCreateRunDelegate):
        async def createRun(self, request: AgentRunRequest) -> AdapterRun:
            adapter_starts.append(request.task_run_id)
            return await super().createRun(request)

    with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
        await run_engine_module.execute_task_run(
            db,
            task_run,
            adapter_type="scripted_mock",
            adapter=RecordingReadonlyAdapter(),
            supervisor=run_engine_module.RunSupervisor(),
            lease_renewal_interval_seconds=3600,
        )
    db.close()

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert adapter_starts == []
    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        durable_queue = entry_for_task_run(verification_db, task_run_id)
    assert stored is not None
    assert durable_queue is not None
    assert stored.state == "interrupted"
    assert stored.error_code == "COMPETING_REQUEST_FINALIZER"
    assert durable_queue.state == "interrupted"
    assert "canonicalContextSnapshot" not in json.loads(stored.metrics_json)


@pytest.mark.parametrize("initial_state", ("streaming", "collecting_diff"))
@pytest.mark.anyio
async def test_execute_task_run_rejects_nonqueued_initial_active_state_before_adapter(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    initial_state: str,
) -> None:
    db = db_from_override()
    _, task_run, queue_entry, _ = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id=f"worker:nonqueued-initial-state:{initial_state}",
    )
    task_run_id = task_run.id
    queue_entry_id = queue_entry.id
    original_metrics_json = task_run.metrics_json
    result = db.execute(
        update(TaskRun)
        .where(TaskRun.id == task_run_id)
        .where(TaskRun.state == "queued")
        .values(state=initial_state, updated_at=utc_now())
        .execution_options(synchronize_session=False)
    )
    db.commit()
    assert result.rowcount == 1
    db.expire_all()
    task_run = db.get(TaskRun, task_run_id)
    assert task_run is not None
    adapter_calls: list[str] = []

    class AdapterMustNotBeTouched:
        def getCapabilities(self):
            adapter_calls.append("getCapabilities")
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=False,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            adapter_calls.append("createRun")
            raise task_run_scope.TaskRunScopeError(
                "TASK_RUN_SCOPE_UNVERIFIABLE",
                "A nonqueued TaskRun reached the adapter.",
            )

    execution_error: Optional[task_run_scope.TaskRunScopeError] = None
    try:
        await run_engine_module.execute_task_run(
            db,
            task_run,
            adapter_type="scripted_mock",
            adapter=AdapterMustNotBeTouched(),
            supervisor=run_engine_module.RunSupervisor(),
            lease_renewal_interval_seconds=3600,
        )
    except task_run_scope.TaskRunScopeError as exc:
        execution_error = exc
    finally:
        db.close()

    assert adapter_calls == []
    assert execution_error is not None
    assert execution_error.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        durable_queue = entry_for_task_run(verification_db, task_run_id)
    assert stored is not None
    assert durable_queue is not None
    assert stored.state == initial_state
    assert stored.metrics_json == original_metrics_json
    assert durable_queue.id == queue_entry_id
    assert durable_queue.state == "running"
    assert "canonicalContextSnapshot" not in json.loads(stored.metrics_json)


@pytest.mark.parametrize(
    "execution_drift",
    ("agent_id", "worktree_path", "expired_lease"),
)
@pytest.mark.anyio
async def test_prepare_scope_failure_preserves_execution_identity_drift(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    execution_drift: str,
) -> None:
    db = db_from_override()
    _, task_run, queue_entry, _ = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id=f"worker:prepare-failure-drift:{execution_drift}",
    )
    task_run_id = task_run.id
    queue_entry_id = queue_entry.id
    original_metrics_json = task_run.metrics_json
    replacement_agent_id = db.exec(
        select(Agent.id).where(Agent.id != task_run.agent_id)
    ).first()
    replacement_worktree_path = f"{task_run.worktree_path}-replacement"
    capability_reads = 0

    class DriftThenFailCapabilities:
        def getCapabilities(self) -> AdapterCapabilities:
            nonlocal capability_reads
            capability_reads += 1
            if execution_drift == "agent_id":
                values = {"agent_id": replacement_agent_id}
            elif execution_drift == "worktree_path":
                values = {"worktree_path": replacement_worktree_path}
            else:
                assert execution_drift == "expired_lease"
                values = {
                    "lease_expires_at": func.datetime("now", "-1 minute")
                }
            result = db.execute(
                update(TaskRun)
                .where(TaskRun.id == task_run_id)
                .where(TaskRun.state == "queued")
                .values(**values)
                .execution_options(synchronize_session=False)
            )
            db.commit()
            assert result.rowcount == 1
            capabilities = AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=False,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )
            capabilities.supports_file_edit = None
            return capabilities

        async def createRun(self, request):
            raise AssertionError("Drifted prepare ownership reached the adapter.")

    try:
        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            await run_engine_module.execute_task_run(
                db,
                task_run,
                adapter_type="scripted_mock",
                adapter=DriftThenFailCapabilities(),
                supervisor=run_engine_module.RunSupervisor(),
                lease_renewal_interval_seconds=3600,
            )
    finally:
        db.close()

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert capability_reads == 1
    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        durable_queue = entry_for_task_run(verification_db, task_run_id)
    assert stored is not None
    assert durable_queue is not None
    assert stored.state == "queued"
    assert stored.error_code is None
    assert stored.metrics_json == original_metrics_json
    assert durable_queue.id == queue_entry_id
    assert durable_queue.state == "running"
    if execution_drift == "agent_id":
        assert stored.agent_id == replacement_agent_id
    elif execution_drift == "worktree_path":
        assert stored.worktree_path == replacement_worktree_path
    else:
        assert stored.lease_expires_at is not None
        with db_from_override() as verification_db:
            lease_is_current = verification_db.execute(
                select(
                    func.julianday(TaskRun.lease_expires_at)
                    > func.julianday("now")
                ).where(TaskRun.id == task_run_id)
            ).scalar_one()
        assert lease_is_current is False


@pytest.mark.anyio
async def test_malformed_canonical_context_is_owned_prepare_failure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    _, task_run, _, _ = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id="worker:malformed-canonical-context-prepare-failure",
    )
    task_run_id = task_run.id
    monkeypatch.setattr(
        run_engine_module,
        "build_session_context_pack",
        lambda *args, **kwargs: {"canonicalContext": "malformed"},
    )
    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", _fail_if_readonly_touches_target_lock)
    try:
        result = await run_engine_module.execute_task_run(
            db,
            task_run,
            adapter_type="scripted_mock",
            adapter=_ReadonlyCreateRunDelegate(),
            supervisor=run_engine_module.RunSupervisor(),
            lease_renewal_interval_seconds=3600,
        )
        result_state = result.state
        result_error_code = result.error_code
    finally:
        event.remove(
            engine,
            "before_cursor_execute",
            _fail_if_readonly_touches_target_lock,
        )
        db.close()

    assert result_state == "failed"
    assert result_error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        durable_queue = entry_for_task_run(verification_db, task_run_id)
    assert stored is not None
    assert durable_queue is not None
    assert stored.state == "failed"
    assert durable_queue.state == "failed"
    assert "canonicalContextSnapshot" not in json.loads(stored.metrics_json)


@pytest.mark.anyio
async def test_prepare_scope_failure_preserves_reacquired_write_lock_generation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    task_run = _prepare_write_finalizer_fence_race(
        db,
        monkeypatch,
        worker_id="worker:prepare-failure-lock-generation",
    )
    task_run_id = task_run.id
    task = db.get(Task, task_run.task_id)
    queue_entry = entry_for_task_run(db, task_run_id)
    lock_a = held_lock_for_target(db, DEMO_FRONTEND_TARGET_ID)
    acquisition = (
        task_run_scope.get_task_run_target_lock_acquisition_context(task_run_id)
    )
    assert task is not None
    assert queue_entry is not None
    assert lock_a is not None
    assert acquisition is not None
    assert acquisition.lock_id == lock_a.id
    lock_a_id = lock_a.id
    runner_id = task_run.runner_id
    queue_entry_id = queue_entry.id
    capability_reads = 0
    lock_b_id: Optional[str] = None

    class RotateLockThenFailCapabilities:
        def getCapabilities(self) -> AdapterCapabilities:
            nonlocal capability_reads, lock_b_id
            capability_reads += 1
            released = release_target_lock_for_task_run(
                db,
                target_id=DEMO_FRONTEND_TARGET_ID,
                expected_lock_id=lock_a_id,
                worker_id=runner_id,
                task_run_id=task_run_id,
                session_id=task.session_id,
                release_reason="rotate_prepare_failure_generation",
            )
            assert released is not None
            reacquired = acquire_target_lock(
                db,
                target_id=DEMO_FRONTEND_TARGET_ID,
                session_id=task.session_id,
                task_run_id=task_run_id,
                worker_id=runner_id,
                lease_expires_at=task_run.lease_expires_at,
            )
            assert reacquired.acquired is True
            assert reacquired.lock is not None
            assert reacquired.lock.id != lock_a_id
            lock_b_id = reacquired.lock.id
            capabilities = AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=True,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )
            capabilities.supports_file_edit = None
            return capabilities

        async def createRun(self, request):
            raise AssertionError("Rotated write-lock generation reached the adapter.")

    try:
        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            await run_engine_module.execute_task_run(
                db,
                task_run,
                adapter_type="scripted_mock",
                adapter=RotateLockThenFailCapabilities(),
                supervisor=run_engine_module.RunSupervisor(),
                lease_renewal_interval_seconds=3600,
            )
    finally:
        db.close()

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert capability_reads == 1
    assert lock_b_id is not None
    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        durable_queue = entry_for_task_run(verification_db, task_run_id)
        durable_lock = held_lock_for_target(
            verification_db,
            DEMO_FRONTEND_TARGET_ID,
        )
    task_run_scope.clear_task_run_target_lock_acquisition_context(task_run_id)

    assert stored is not None
    assert durable_queue is not None
    assert durable_lock is not None
    assert stored.state == "queued"
    assert stored.error_code is None
    assert durable_queue.id == queue_entry_id
    assert durable_queue.state == "running"
    assert durable_lock.id == lock_b_id
    assert durable_lock.id != lock_a_id
    assert durable_lock.task_run_id == task_run_id
    assert durable_lock.worker_id == runner_id
    assert durable_lock.state == "held"


@pytest.mark.anyio
async def test_invalid_pre_cas_launch_snapshot_is_owned_prepare_failure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    _, task_run, _, _ = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id="worker:invalid-pre-cas-launch-snapshot",
    )
    task_run_id = task_run.id
    original_capture = run_engine_module._capture_request_launch_snapshot

    def capture_invalid_launch_snapshot(*args, **kwargs):
        snapshot = original_capture(*args, **kwargs)
        return replace(snapshot, task_run_state="streaming")

    monkeypatch.setattr(
        run_engine_module,
        "_capture_request_launch_snapshot",
        capture_invalid_launch_snapshot,
    )
    try:
        result = await run_engine_module.execute_task_run(
            db,
            task_run,
            adapter_type="scripted_mock",
            adapter=_ReadonlyCreateRunDelegate(),
            supervisor=run_engine_module.RunSupervisor(),
            lease_renewal_interval_seconds=3600,
        )
        result_state = result.state
        result_error_code = result.error_code
    finally:
        db.close()

    assert result_state == "failed"
    assert result_error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        durable_queue = entry_for_task_run(verification_db, task_run_id)
    assert stored is not None
    assert durable_queue is not None
    assert stored.state == "failed"
    assert durable_queue.state == "failed"
    assert "canonicalContextSnapshot" not in json.loads(stored.metrics_json)


@pytest.mark.anyio
async def test_prepare_scope_failure_fences_competing_queued_owner_cas(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "prepare-failure-owner-fence.db"
    with db_from_override() as source_db:
        source_connection = source_db.connection().connection.driver_connection
        with sqlite3.connect(database_path) as target_connection:
            source_connection.backup(target_connection)
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 5},
    )
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")

    failure_transition_entered = Event()
    writer_statement_started = Event()
    writer_committed = Event()
    writer_finished = Event()
    writer_rowcounts: list[int] = []
    writer_errors: list[BaseException] = []
    committed_before_failure_transition: list[bool] = []
    original_transition = run_engine_module.transition_task_run
    writer_connections: list[object] = []

    def record_competing_update_cursor_entry(
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        if (
            writer_connections
            and connection is writer_connections[0]
            and statement.lstrip().casefold().startswith("update taskrun")
        ):
            writer_statement_started.set()

    event.listen(
        engine,
        "before_cursor_execute",
        record_competing_update_cursor_entry,
    )

    with DbSession(engine) as db:
        _, task_run, _, _ = _prepare_readonly_execution_boundary(
            db,
            monkeypatch,
            worker_id="worker:prepare-failure-owner-fence",
        )
        task_run_id = task_run.id

        def compete_for_queued_run() -> None:
            try:
                assert failure_transition_entered.wait(timeout=2)
                with DbSession(engine) as writer_db:
                    writer_connections.append(writer_db.connection())
                    result = writer_db.execute(
                        update(TaskRun)
                        .where(TaskRun.id == task_run_id)
                        .where(TaskRun.state == "queued")
                        .values(state="streaming", updated_at=utc_now())
                        .execution_options(synchronize_session=False)
                    )
                    writer_rowcounts.append(result.rowcount)
                    writer_db.commit()
                    writer_committed.set()
            except BaseException as exc:
                writer_errors.append(exc)
            finally:
                writer_finished.set()

        def transition_with_competing_writer(*args, **kwargs):
            failure_transition_entered.set()
            assert writer_statement_started.wait(timeout=2)
            committed_before_failure_transition.append(
                writer_committed.wait(timeout=0.2)
            )
            return original_transition(*args, **kwargs)

        monkeypatch.setattr(
            run_engine_module,
            "transition_task_run",
            transition_with_competing_writer,
        )

        class MalformedCapabilitiesAdapter:
            def getCapabilities(self) -> AdapterCapabilities:
                capabilities = AdapterCapabilities(
                    supportsStreaming=True,
                    supportsInterrupt=True,
                    supportsApproval=False,
                    supportsFileEdit=False,
                    supportsShellCommand=False,
                    supportsDiffArtifact=False,
                    supportsPreviewArtifact=False,
                    supportsNetwork=False,
                )
                capabilities.supports_file_edit = None
                return capabilities

            async def createRun(self, request):
                raise AssertionError("A malformed adapter must not start.")

        writer = Thread(target=compete_for_queued_run, daemon=True)
        writer.start()
        try:
            result = await run_engine_module.execute_task_run(
                db,
                task_run,
                adapter_type="scripted_mock",
                adapter=MalformedCapabilitiesAdapter(),
                supervisor=run_engine_module.RunSupervisor(),
                lease_renewal_interval_seconds=3600,
            )
            result_state = result.state
            result_error_code = result.error_code
            assert writer_finished.wait(timeout=5)
            writer.join(timeout=5)
        finally:
            failure_transition_entered.set()
            writer.join(timeout=5)
            event.remove(
                engine,
                "before_cursor_execute",
                record_competing_update_cursor_entry,
            )

    assert writer.is_alive() is False
    assert writer_errors == []
    assert committed_before_failure_transition == [False]
    assert writer_rowcounts == [0]
    assert writer_committed.is_set() is True
    assert result_state == "failed"
    assert result_error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    with DbSession(engine) as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        durable_queue = entry_for_task_run(verification_db, task_run_id)
    engine.dispose()

    assert stored is not None
    assert durable_queue is not None
    assert stored.state == "failed"
    assert durable_queue.state == "failed"


def test_request_snapshot_cas_runs_after_complete_request_construction(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    _, task_run, _, _ = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id="worker:request-snapshot-last-step",
    )
    construction_order: list[str] = []
    original_agent_run_request = run_engine_module.AgentRunRequest
    original_persist_context_snapshot = run_engine_module._persist_context_snapshot

    def record_complete_request(**kwargs):
        request = original_agent_run_request(**kwargs)
        construction_order.append("request")
        return request

    def record_context_snapshot_cas(*args, **kwargs):
        construction_order.append("cas")
        return original_persist_context_snapshot(*args, **kwargs)

    monkeypatch.setattr(
        run_engine_module,
        "AgentRunRequest",
        record_complete_request,
    )
    monkeypatch.setattr(
        run_engine_module,
        "_persist_context_snapshot",
        record_context_snapshot_cas,
    )
    try:
        request = run_engine_module.agent_run_request_for(
            db,
            task_run,
            adapter_type="scripted_mock",
            fence_current_execution=True,
        )
    finally:
        db.close()

    assert request.task_run_id == task_run.id
    assert construction_order == ["request", "cas"]


def test_request_snapshot_cas_binds_fresh_external_target_policy_identity(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db = db_from_override()
    workspace = db.exec(
        select(Workspace).where(Workspace.name == "AgentHub Demo")
    ).one()
    external_root = tmp_path / "request-cas-external-target"
    (external_root / "src").mkdir(parents=True)
    external_target = register_external_project_target(
        db,
        workspace,
        ExternalWorkspaceRegistration(
            target_id="external-request-cas-target",
            name="Request CAS Target",
            root_path=str(external_root),
            project_type="vite-react",
            allowed_paths=["src"],
        ),
    )
    task, task_run, queue_entry, _ = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id="worker:request-cas-external-registration",
    )
    task.plan_json = json.dumps(
        {
            "targetId": external_target.target_id,
            "safeTarget": "src",
            "readOnly": True,
        },
        separators=(",", ":"),
    )
    task.updated_at = utc_now()
    task_run.worktree_path = external_target.root_path
    task_run.updated_at = utc_now()
    queue_entry.target_id = external_target.target_id
    queue_entry.updated_at = utc_now()
    db.add(task)
    db.add(task_run)
    db.add(queue_entry)
    db.commit()
    db.refresh(task)
    db.refresh(task_run)
    db.refresh(queue_entry)
    cached_allowed_paths_json = external_target.allowed_paths_json
    original_persist_context_snapshot = run_engine_module._persist_context_snapshot
    registration_drifted = False

    def drift_external_registration_before_cas(*args, **kwargs):
        nonlocal registration_drifted
        result = db.execute(
            update(ExternalProjectTarget)
            .where(ExternalProjectTarget.id == external_target.id)
            .values(
                allowed_paths_json=json.dumps(["src", "other"]),
                updated_at=utc_now(),
            )
            .execution_options(synchronize_session=False)
        )
        assert result.rowcount == 1
        assert external_target.allowed_paths_json == cached_allowed_paths_json
        registration_drifted = True
        return original_persist_context_snapshot(*args, **kwargs)

    monkeypatch.setattr(
        run_engine_module,
        "_persist_context_snapshot",
        drift_external_registration_before_cas,
    )
    try:
        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            run_engine_module.agent_run_request_for(
                db,
                task_run,
                adapter_type="scripted_mock",
                fence_current_execution=True,
            )
    finally:
        db.close()

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert registration_drifted is True


def _prepare_external_write_launch_boundary(
    db: DbSession,
    monkeypatch: pytest.MonkeyPatch,
    external_root: Path,
    *,
    target_id: str,
    worker_id: str,
) -> tuple[ExternalProjectTarget, TaskRun]:
    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    (external_root / "src").mkdir(parents=True)
    (external_root / "src" / "App.tsx").write_text(
        "export default function App() {}\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=external_root, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "agenthub@example.com"],
        cwd=external_root,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "AgentHub"],
        cwd=external_root,
        check=True,
    )
    subprocess.run(["git", "add", "src/App.tsx"], cwd=external_root, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=external_root,
        check=True,
        capture_output=True,
    )
    workspace = db.exec(
        select(Workspace).where(Workspace.name == "AgentHub Demo")
    ).one()
    external_target = register_external_project_target(
        db,
        workspace,
        ExternalWorkspaceRegistration(
            target_id=target_id,
            name="External launch boundary target",
            root_path=str(external_root),
            project_type="vite-react",
            allowed_paths=["src"],
        ),
    )
    task = db.exec(select(Task).where(Task.title == "Build login page")).one()
    session = db.get(Session, task.session_id)
    assert session is not None
    task.plan_json = json.dumps({"targetId": target_id}, separators=(",", ":"))
    task.updated_at = utc_now()
    db.add(task)
    db.commit()
    task_run = claim_task_run_for_worker(
        db,
        create_task_run(db, task.id).id,
        worker_id=worker_id,
    )
    assert run_engine_module._prepare_claimed_task_run_for_adapter(
        db,
        task_run,
        worker_id,
    ) is True
    stored = db.get(TaskRun, task_run.id)
    assert stored is not None
    return external_target, stored


@pytest.mark.anyio
async def test_final_launch_rejects_post_binding_same_target_policy_drift(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db = db_from_override()
    external_target, task_run = _prepare_external_write_launch_boundary(
        db,
        monkeypatch,
        tmp_path / "post-binding-policy-drift",
        target_id="external-post-binding-policy-drift",
        worker_id="worker:post-binding-policy-drift",
    )
    task_run_id = task_run.id
    delegate_calls: list[str] = []
    binding_committed = False
    original_persist_binding = (
        run_engine_module.persist_task_run_execution_access_binding
    )

    def persist_binding_then_drift_policy(*args, **kwargs):
        nonlocal binding_committed
        result = original_persist_binding(*args, **kwargs)
        with db_from_override() as mutation_db:
            drift = mutation_db.execute(
                update(ExternalProjectTarget)
                .where(ExternalProjectTarget.id == external_target.id)
                .values(
                    allowed_paths_json=json.dumps(["src", "other"]),
                    denied_paths_json=json.dumps(["src/private"]),
                    updated_at=utc_now(),
                )
                .execution_options(synchronize_session=False)
            )
            mutation_db.commit()
        assert drift.rowcount == 1
        binding_committed = True
        return result

    monkeypatch.setattr(
        run_engine_module,
        "persist_task_run_execution_access_binding",
        persist_binding_then_drift_policy,
    )

    class AdapterMustNotLaunchAfterPolicyDrift(_FenceRaceCompletedAdapter):
        async def createRun(self, request):
            delegate_calls.append(request.task_run_id)
            return await super().createRun(request)

    try:
        result = await run_engine_module.execute_task_run(
            db,
            task_run,
            adapter_type="scripted_mock",
            adapter=AdapterMustNotLaunchAfterPolicyDrift(task_run_id, []),
            supervisor=run_engine_module.RunSupervisor(),
            lease_renewal_interval_seconds=3600,
        )
    finally:
        db.close()

    assert binding_committed is True
    assert delegate_calls == []
    assert result.state == "failed"
    assert result.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
    assert stored is not None
    assert stored.state == "failed"
    assert stored.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


@pytest.mark.anyio
async def test_final_launch_rejects_post_binding_task_run_started_at_drift(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    task_run = _prepare_write_finalizer_fence_race(
        db,
        monkeypatch,
        worker_id="worker:post-binding-started-at-drift",
    )
    task_run_id = task_run.id
    delegate_calls: list[str] = []
    binding_committed = False
    original_persist_binding = (
        run_engine_module.persist_task_run_execution_access_binding
    )

    def persist_binding_then_set_started_at(*args, **kwargs):
        nonlocal binding_committed
        result = original_persist_binding(*args, **kwargs)
        with db_from_override() as mutation_db:
            drift = mutation_db.execute(
                update(TaskRun)
                .where(TaskRun.id == task_run_id)
                .values(started_at=utc_now())
                .execution_options(synchronize_session=False)
            )
            mutation_db.commit()
        assert drift.rowcount == 1
        binding_committed = True
        return result

    monkeypatch.setattr(
        run_engine_module,
        "persist_task_run_execution_access_binding",
        persist_binding_then_set_started_at,
    )

    class AdapterMustNotLaunchAfterStartedAtDrift(_FenceRaceCompletedAdapter):
        async def createRun(self, request):
            delegate_calls.append(request.task_run_id)
            return await super().createRun(request)

    try:
        result = await run_engine_module.execute_task_run(
            db,
            task_run,
            adapter_type="scripted_mock",
            adapter=AdapterMustNotLaunchAfterStartedAtDrift(task_run_id, []),
            supervisor=run_engine_module.RunSupervisor(),
            lease_renewal_interval_seconds=3600,
        )
    finally:
        db.close()

    assert binding_committed is True
    assert delegate_calls == []
    assert result.state == "failed"
    assert result.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
    assert stored is not None
    assert stored.state == "failed"
    assert stored.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


@pytest.mark.anyio
async def test_final_launch_rejects_post_binding_baseline_removal(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    task_run = _prepare_write_finalizer_fence_race(
        db,
        monkeypatch,
        worker_id="worker:post-binding-baseline-removal",
    )
    task_run_id = task_run.id
    delegate_calls: list[str] = []
    binding_committed = False
    original_persist_binding = (
        run_engine_module.persist_task_run_execution_access_binding
    )

    def persist_binding_then_remove_baseline(*args, **kwargs):
        nonlocal binding_committed
        result = original_persist_binding(*args, **kwargs)
        with db_from_override() as mutation_db:
            stored = mutation_db.get(TaskRun, task_run_id)
            assert stored is not None
            metrics = json.loads(stored.metrics_json)
            checkpoint = metrics.get("preRunCheckpoint")
            assert isinstance(checkpoint, dict)
            assert checkpoint.pop("scopeBaseline", None) is not None
            drift = mutation_db.execute(
                update(TaskRun)
                .where(TaskRun.id == task_run_id)
                .where(TaskRun.metrics_json == stored.metrics_json)
                .values(
                    metrics_json=json.dumps(metrics, separators=(",", ":")),
                    updated_at=utc_now(),
                )
                .execution_options(synchronize_session=False)
            )
            mutation_db.commit()
        assert drift.rowcount == 1
        binding_committed = True
        return result

    monkeypatch.setattr(
        run_engine_module,
        "persist_task_run_execution_access_binding",
        persist_binding_then_remove_baseline,
    )

    class AdapterMustNotLaunchWithoutBoundBaseline(_FenceRaceCompletedAdapter):
        async def createRun(self, request):
            delegate_calls.append(request.task_run_id)
            return await super().createRun(request)

    try:
        result = await run_engine_module.execute_task_run(
            db,
            task_run,
            adapter_type="scripted_mock",
            adapter=AdapterMustNotLaunchWithoutBoundBaseline(task_run_id, []),
            supervisor=run_engine_module.RunSupervisor(),
            lease_renewal_interval_seconds=3600,
        )
    finally:
        db.close()

    assert binding_committed is True
    assert delegate_calls == []
    assert result.state == "failed"
    assert result.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


@pytest.mark.anyio
async def test_final_launch_rejects_lock_rotation_after_controller_start(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    task_run = _prepare_write_finalizer_fence_race(
        db,
        monkeypatch,
        worker_id="worker:final-launch-lock-rotation",
    )
    task_run_id = task_run.id
    delegate_calls: list[str] = []
    rotated_lock_ids: list[str] = []
    original_start = run_engine_module._ExecutionLeaseController.start

    def start_then_rotate_lock(self, token):
        original_start(self, token)
        assert token.expected_lock_id is not None
        released = release_target_lock_for_task_run(
            db,
            target_id=token.target_id,
            expected_lock_id=token.expected_lock_id,
            worker_id=token.runner_id,
            task_run_id=token.task_run_id,
            session_id=token.session_id,
            release_reason="rotate_after_controller_start",
        )
        assert released is not None
        replacement = acquire_target_lock(
            db,
            target_id=token.target_id,
            session_id=token.session_id,
            task_run_id=token.task_run_id,
            worker_id=token.runner_id,
            lease_expires_at=task_run.lease_expires_at,
        )
        assert replacement.acquired is True
        assert replacement.lock is not None
        assert replacement.lock.id != token.expected_lock_id
        rotated_lock_ids.append(replacement.lock.id)

    monkeypatch.setattr(
        run_engine_module._ExecutionLeaseController,
        "start",
        start_then_rotate_lock,
    )

    class AdapterMustNotLaunchAfterLockRotation(_FenceRaceCompletedAdapter):
        async def createRun(self, request):
            delegate_calls.append(request.task_run_id)
            return await super().createRun(request)

    try:
        result = await run_engine_module.execute_task_run(
            db,
            task_run,
            adapter_type="scripted_mock",
            adapter=AdapterMustNotLaunchAfterLockRotation(task_run_id, []),
            supervisor=run_engine_module.RunSupervisor(),
            lease_renewal_interval_seconds=3600,
        )
    finally:
        db.close()

    assert len(rotated_lock_ids) == 1
    assert delegate_calls == []
    assert result.state == "failed"
    assert result.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


@pytest.mark.parametrize("delegate_exit", ("return", "error", "cancel"))
@pytest.mark.anyio
async def test_final_launch_holds_sqlite_writer_boundary_until_delegate_returns(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    delegate_exit: str,
) -> None:
    database_path = tmp_path / f"final-launch-writer-boundary-{delegate_exit}.db"
    with db_from_override() as source_db:
        source_connection = source_db.connection().connection.driver_connection
        with sqlite3.connect(database_path) as target_connection:
            source_connection.backup(target_connection)
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 5},
    )
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")

    delegate_entered = Event()
    writer_statement_started = Event()
    writer_committed = Event()
    writer_errors: list[BaseException] = []
    committed_during_delegate: list[bool] = []
    with DbSession(engine) as db:
        external_target, task_run = _prepare_external_write_launch_boundary(
            db,
            monkeypatch,
            tmp_path / "writer-boundary-target",
            target_id="external-final-launch-writer-boundary",
            worker_id="worker:final-launch-writer-boundary",
        )
        task_run_id = task_run.id

        def mutate_policy() -> None:
            try:
                assert delegate_entered.wait(timeout=2)
                with DbSession(engine) as writer_db:
                    writer_statement_started.set()
                    result = writer_db.execute(
                        update(ExternalProjectTarget)
                        .where(ExternalProjectTarget.id == external_target.id)
                        .values(
                            allowed_paths_json=json.dumps(["src", "other"]),
                            updated_at=utc_now(),
                        )
                        .execution_options(synchronize_session=False)
                    )
                    writer_db.commit()
                    assert result.rowcount == 1
                    writer_committed.set()
            except BaseException as exc:
                writer_errors.append(exc)

        writer = Thread(target=mutate_policy)
        writer.start()

        class WriterBoundaryAdapter(_FenceRaceCompletedAdapter):
            async def createRun(self, request):
                delegate_entered.set()
                assert writer_statement_started.wait(timeout=2)
                committed_during_delegate.append(writer_committed.wait(timeout=0.5))
                if delegate_exit == "error":
                    raise RuntimeError("injected final launch adapter error")
                if delegate_exit == "cancel":
                    raise asyncio.CancelledError()
                return AdapterRun(adapterRunId=self.adapter_run_id)

            async def streamEvents(self, adapter_run_id):
                yield AgentEvent(
                    type="error",
                    taskRunId=self.task_run_id,
                    sequence=1,
                    payload={"message": "Stop after launch-boundary verification."},
                )

        try:
            execution = run_engine_module.execute_task_run(
                db,
                task_run,
                adapter_type="scripted_mock",
                adapter=WriterBoundaryAdapter(task_run_id, []),
                supervisor=run_engine_module.RunSupervisor(),
                lease_renewal_interval_seconds=3600,
            )
            if delegate_exit == "error":
                with pytest.raises(
                    RuntimeError,
                    match="injected final launch adapter error",
                ):
                    await execution
            elif delegate_exit == "cancel":
                with pytest.raises(asyncio.CancelledError):
                    await execution
            else:
                await execution
        finally:
            delegate_entered.set()
            writer.join(timeout=6)
            task_run_scope.clear_task_run_scope_runtime_context(task_run_id)
            task_run_scope.clear_task_run_target_lock_acquisition_context(task_run_id)
    engine.dispose()

    assert writer.is_alive() is False
    assert writer_errors == []
    assert committed_during_delegate == [False]
    assert writer_committed.is_set() is True


@pytest.mark.parametrize(
    "context_pack",
    (
        {},
        {"canonicalContext": None},
        {"canonicalContext": []},
        {"canonicalContext": "malformed"},
    ),
)
def test_fenced_context_snapshot_rejects_malformed_canonical_context(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    context_pack: dict[str, object],
) -> None:
    db = db_from_override()
    _, task_run, _, _ = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id="worker:fenced-malformed-canonical-context",
    )
    original_metrics_json = task_run.metrics_json
    try:
        assert (
            run_engine_module._persist_context_snapshot(
                db,
                task_run,
                context_pack,
            )
            is None
        )
        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            run_engine_module._persist_context_snapshot(
                db,
                task_run,
                context_pack,
                fence_current_execution=True,
            )
    finally:
        db.close()

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run.id)
    assert stored is not None
    assert stored.metrics_json == original_metrics_json


@pytest.mark.anyio
async def test_request_binding_rejects_exact_state_drift_after_snapshot_cas(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    _, task_run, _, _ = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id="worker:request-binding-post-cas-drift",
    )
    task_run_id = task_run.id
    original_persist_context_snapshot = run_engine_module._persist_context_snapshot
    post_cas_adapter_calls: list[str] = []
    snapshot_committed = False

    def persist_then_drift_exact_state(*args, **kwargs):
        nonlocal snapshot_committed
        persisted_snapshot = original_persist_context_snapshot(*args, **kwargs)
        drifted_at = utc_now()
        result = db.execute(
            update(TaskRun)
            .where(TaskRun.id == task_run_id)
            .where(TaskRun.state == "queued")
            .values(state="streaming", updated_at=drifted_at)
            .execution_options(synchronize_session=False)
        )
        db.commit()
        assert result.rowcount == 1
        snapshot_committed = True
        return persisted_snapshot

    monkeypatch.setattr(
        run_engine_module,
        "_persist_context_snapshot",
        persist_then_drift_exact_state,
    )

    class AdapterMustNotBeReachedAfterSnapshot:
        def getCapabilities(self):
            if snapshot_committed:
                post_cas_adapter_calls.append("getCapabilities")
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=False,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            post_cas_adapter_calls.append("createRun")
            return AdapterRun(adapterRunId=f"unexpected:{request.task_run_id}")

        async def streamEvents(self, current_adapter_run_id):
            if False:
                yield None

        async def interrupt(self, current_adapter_run_id):
            return None

        async def approve(self, current_adapter_run_id, approval):
            return None

        async def collectArtifacts(self, current_adapter_run_id):
            return []

        async def cleanup(self, current_adapter_run_id):
            return None

    try:
        result = await run_engine_module.execute_task_run(
            db,
            task_run,
            adapter_type="scripted_mock",
            adapter=AdapterMustNotBeReachedAfterSnapshot(),
            supervisor=run_engine_module.RunSupervisor(),
            lease_renewal_interval_seconds=3600,
        )
    finally:
        db.close()

    assert result.state == "failed"
    assert result.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert snapshot_committed is True
    assert post_cas_adapter_calls == []


@pytest.mark.anyio
async def test_request_snapshot_cas_rejects_exact_active_launch_state_drift(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    _, task_run, queue_entry, _ = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id="worker:request-snapshot-active-state-drift",
    )
    task_run_id = task_run.id
    queue_entry_id = queue_entry.id
    launch_state = task_run.state
    assert launch_state == "queued"
    original_persist_context_snapshot = run_engine_module._persist_context_snapshot
    adapter_calls: list[str] = []

    def drift_active_state_before_context_snapshot(
        current_db,
        current_task_run,
        context_pack,
        **kwargs,
    ) -> None:
        drifted_at = utc_now()
        result = current_db.execute(
            update(TaskRun)
            .where(TaskRun.id == task_run_id)
            .where(TaskRun.state == launch_state)
            .values(state="streaming", updated_at=drifted_at)
            .execution_options(synchronize_session=False)
        )
        current_db.commit()
        assert result.rowcount == 1
        original_persist_context_snapshot(
            current_db,
            current_task_run,
            context_pack,
            **kwargs,
        )

    monkeypatch.setattr(
        run_engine_module,
        "_persist_context_snapshot",
        drift_active_state_before_context_snapshot,
    )

    class AdapterMustNotStart:
        def getCapabilities(self):
            adapter_calls.append("getCapabilities")
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=False,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            adapter_calls.append("createRun")
            raise AssertionError("request drift started the adapter")

    try:
        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            await run_engine_module.execute_task_run(
                db,
                task_run,
                adapter_type="scripted_mock",
                adapter=AdapterMustNotStart(),
                supervisor=run_engine_module.RunSupervisor(),
                lease_renewal_interval_seconds=3600,
            )
    finally:
        db.close()

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert adapter_calls == ["getCapabilities"]
    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        durable_queue = entry_for_task_run(verification_db, task_run_id)
    assert stored is not None
    assert durable_queue is not None
    assert stored.state == "streaming"
    assert durable_queue.id == queue_entry_id
    assert durable_queue.state == "running"
    assert "canonicalContextSnapshot" not in json.loads(stored.metrics_json)


@pytest.mark.parametrize(
    "identity_drift",
    (
        "queue_entry_id",
        "queue_session_id",
        "queue_access_mode",
        "queue_target_id",
        "queue_started_at",
        "task_target",
        "session_workspace_id",
    ),
)
@pytest.mark.anyio
async def test_request_snapshot_cas_rejects_frozen_identity_drift(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    identity_drift: str,
) -> None:
    db = db_from_override()
    task, task_run, queue_entry, request = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id=f"worker:request-snapshot-identity-drift:{identity_drift}",
    )
    task_run_id = task_run.id
    task_id = task.id
    original_queue_entry_id = queue_entry.id
    original_session_id = request.session_id
    replacement_queue_entry_id = f"replacement:{queue_entry.id}"
    replacement_started_at = queue_entry.started_at + timedelta(seconds=1)
    replacement_session_id = f"replacement:{original_session_id}"
    replacement_workspace_id = f"replacement:{request.workspace_id}"
    original_persist_context_snapshot = run_engine_module._persist_context_snapshot
    adapter_calls: list[str] = []

    def drift_identity_before_context_snapshot(
        current_db,
        current_task_run,
        context_pack,
        **kwargs,
    ) -> None:
        if identity_drift == "queue_entry_id":
            result = current_db.execute(
                update(SessionQueueEntry)
                .where(SessionQueueEntry.id == original_queue_entry_id)
                .values(id=replacement_queue_entry_id)
                .execution_options(synchronize_session=False)
            )
        elif identity_drift == "queue_session_id":
            result = current_db.execute(
                update(SessionQueueEntry)
                .where(SessionQueueEntry.id == original_queue_entry_id)
                .values(session_id=replacement_session_id)
                .execution_options(synchronize_session=False)
            )
        elif identity_drift == "queue_access_mode":
            result = current_db.execute(
                update(SessionQueueEntry)
                .where(SessionQueueEntry.id == original_queue_entry_id)
                .values(
                    access_mode="write",
                    target_lock_key=run_engine_module.target_lock_key_for_target(
                        DEMO_FRONTEND_TARGET_ID
                    ),
                )
                .execution_options(synchronize_session=False)
            )
        elif identity_drift == "queue_target_id":
            result = current_db.execute(
                update(SessionQueueEntry)
                .where(SessionQueueEntry.id == original_queue_entry_id)
                .values(target_id=DEMO_BACKEND_TARGET_ID)
                .execution_options(synchronize_session=False)
            )
        elif identity_drift == "queue_started_at":
            result = current_db.execute(
                update(SessionQueueEntry)
                .where(SessionQueueEntry.id == original_queue_entry_id)
                .values(started_at=replacement_started_at)
                .execution_options(synchronize_session=False)
            )
        elif identity_drift == "task_target":
            result = current_db.execute(
                update(Task)
                .where(Task.id == task.id)
                .values(
                    plan_json=json.dumps(
                        {"targetId": DEMO_BACKEND_TARGET_ID, "readOnly": True},
                        separators=(",", ":"),
                    ),
                    updated_at=utc_now(),
                )
                .execution_options(synchronize_session=False)
            )
        else:
            assert identity_drift == "session_workspace_id"
            result = current_db.execute(
                update(Session)
                .where(Session.id == original_session_id)
                .values(workspace_id=replacement_workspace_id, updated_at=utc_now())
                .execution_options(synchronize_session=False)
            )
        current_db.commit()
        assert result.rowcount == 1
        original_persist_context_snapshot(
            current_db,
            current_task_run,
            context_pack,
            **kwargs,
        )

    monkeypatch.setattr(
        run_engine_module,
        "_persist_context_snapshot",
        drift_identity_before_context_snapshot,
    )

    class AdapterMustNotStart:
        def getCapabilities(self):
            adapter_calls.append("getCapabilities")
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=False,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            adapter_calls.append("createRun")
            raise AssertionError("request identity drift started the adapter")

    try:
        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            await run_engine_module.execute_task_run(
                db,
                task_run,
                adapter_type="scripted_mock",
                adapter=AdapterMustNotStart(),
                supervisor=run_engine_module.RunSupervisor(),
                lease_renewal_interval_seconds=3600,
            )
    finally:
        db.close()

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert adapter_calls == ["getCapabilities"]
    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        durable_queue = entry_for_task_run(verification_db, task_run_id)
        durable_task = verification_db.get(Task, task_id)
        durable_session = verification_db.get(Session, original_session_id)
    assert stored is not None
    assert durable_queue is not None
    assert durable_task is not None
    assert durable_session is not None
    assert stored.state == "queued"
    assert durable_queue.state == "running"
    assert "canonicalContextSnapshot" not in json.loads(stored.metrics_json)
    if identity_drift == "queue_entry_id":
        assert durable_queue.id == replacement_queue_entry_id
    elif identity_drift == "queue_session_id":
        assert durable_queue.session_id == replacement_session_id
    elif identity_drift == "queue_access_mode":
        assert durable_queue.access_mode == "write"
        assert durable_queue.target_lock_key == (
            run_engine_module.target_lock_key_for_target(DEMO_FRONTEND_TARGET_ID)
        )
    elif identity_drift == "queue_target_id":
        assert durable_queue.target_id == DEMO_BACKEND_TARGET_ID
    elif identity_drift == "queue_started_at":
        assert durable_queue.started_at == replacement_started_at
    elif identity_drift == "task_target":
        assert json.loads(durable_task.plan_json)["targetId"] == DEMO_BACKEND_TARGET_ID
    else:
        assert durable_session.workspace_id == replacement_workspace_id


@pytest.mark.anyio
async def test_execute_task_run_unregisters_generation_when_request_construction_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    _, task_run, _, _ = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id="worker:request-construction-failure",
    )
    task_run_id = task_run.id
    registered: list[str] = []
    unregistered: list[str] = []

    class RecordingSupervisor(run_engine_module.RunSupervisor):
        def register(self, **kwargs):
            registered.append(kwargs["task_run_id"])
            return super().register(**kwargs)

        def unregister(self, task_run_id, *, expected=None):
            unregistered.append(task_run_id)
            return super().unregister(task_run_id, expected=expected)

    def fail_request_construction(*args, **kwargs):
        raise RuntimeError("injected request construction failure")

    monkeypatch.setattr(
        run_engine_module,
        "agent_run_request_for",
        fail_request_construction,
    )
    supervisor = RecordingSupervisor()
    try:
        with pytest.raises(RuntimeError, match="injected request construction failure"):
            await run_engine_module.execute_task_run(
                db,
                task_run,
                adapter_type="scripted_mock",
                adapter=_FenceRaceCompletedAdapter(task_run_id, []),
                supervisor=supervisor,
                lease_renewal_interval_seconds=3600,
            )
    finally:
        db.close()

    assert registered == [task_run_id]
    assert unregistered == [task_run_id]
    assert supervisor.active(task_run_id) is None


@pytest.mark.anyio
async def test_stale_concurrent_execute_cannot_persist_request_after_winner_seals(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    task_run = _prepare_write_finalizer_fence_race(
        db,
        monkeypatch,
        worker_id="worker:stale-request-winner",
    )
    task_run_id = task_run.id
    stale_request_waiting = Event()
    allow_stale_request = Event()
    downstream_started = asyncio.Event()
    allow_downstream = asyncio.Event()
    downstream_calls: list[str] = []
    stale_adapter_starts: list[str] = []
    stale_errors: list[BaseException] = []
    stale_initial_metrics: list[str] = []
    class PauseFirstRequestGateSupervisor(run_engine_module.RunSupervisor):
        def __init__(self) -> None:
            super().__init__()
            self.stale_generation = None

        def register(self, **kwargs):
            registered = super().register(**kwargs)
            if self.stale_generation is None:
                self.stale_generation = registered
            return registered

        def run_if_current(self, expected, operation):
            if expected is self.stale_generation:
                stale_request_waiting.set()
                if not allow_stale_request.wait(timeout=2):
                    raise AssertionError("The stale request was not released.")
            return super().run_if_current(expected, operation)

    supervisor = PauseFirstRequestGateSupervisor()
    monkeypatch.setattr(
        run_engine_module,
        "collect_task_run_diff",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        run_engine_module,
        "create_scripted_review_for_task_run",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        run_engine_module,
        "refresh_session_ledger_for_task_run",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        run_engine_module,
        "_complete_ready_pipeline_review_tasks",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        run_engine_module,
        "_maybe_auto_preview_and_mock_deploy",
        lambda *args, **kwargs: None,
    )

    async def blocked_downstream(*args, **kwargs):
        downstream_calls.append("started")
        downstream_started.set()
        await allow_downstream.wait()
        downstream_calls.append("finished")
        return None

    monkeypatch.setattr(
        run_engine_module,
        "_auto_start_next_pipeline_task",
        blocked_downstream,
    )

    class StaleAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=True,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            stale_adapter_starts.append(request.task_run_id)
            return AdapterRun(adapterRunId=f"adapter-run:stale:{task_run_id}")

        async def streamEvents(self, current_adapter_run_id):
            yield {"type": "completed", "payload": {}}

        async def interrupt(self, current_adapter_run_id):
            return None

        async def approve(self, current_adapter_run_id, approval):
            return None

        async def collectArtifacts(self, current_adapter_run_id):
            return []

        async def cleanup(self, current_adapter_run_id):
            return None

    def run_stale_execute() -> None:
        try:
            with db_from_override() as stale_db:
                stale_task_run = stale_db.get(TaskRun, task_run_id)
                assert stale_task_run is not None
                stale_initial_metrics.append(stale_task_run.metrics_json)
                asyncio.run(
                    run_engine_module.execute_task_run(
                        stale_db,
                        stale_task_run,
                        adapter_type="scripted_mock",
                        adapter=StaleAdapter(),
                        supervisor=supervisor,
                        lease_renewal_interval_seconds=3600,
                    )
                )
        except BaseException as exc:
            stale_errors.append(exc)

    stale_thread = Thread(target=run_stale_execute)
    stale_thread.start()
    execution = None
    winner_snapshot: Optional[dict[str, object]] = None
    generation_a = None
    try:
        stale_waiting = await asyncio.to_thread(stale_request_waiting.wait, 2)
        assert stale_waiting is True
        execution = asyncio.create_task(
            run_engine_module.execute_task_run(
                db,
                task_run,
                adapter_type="scripted_mock",
                adapter=_FenceRaceCompletedAdapter(task_run_id, []),
                supervisor=supervisor,
                lease_renewal_interval_seconds=3600,
            )
        )
        await asyncio.wait_for(downstream_started.wait(), timeout=2)
        generation_a = supervisor.active(task_run_id)
        assert generation_a is not None
        assert generation_a._generation.is_sealed() is True
        with db_from_override() as verification_db:
            winner = verification_db.get(TaskRun, task_run_id)
            assert winner is not None
            winner_snapshot = winner.model_dump()
            winner_metrics = json.loads(winner.metrics_json)
        assert winner.state == "completed"
        assert "taskRunScopeDecision" in winner_metrics
        assert "taskRunScopeGuard" in winner_metrics
        assert stale_initial_metrics != [winner.metrics_json]

        allow_stale_request.set()
        await asyncio.to_thread(stale_thread.join, 2)
        assert stale_thread.is_alive() is False
        assert len(stale_errors) == 1
        assert isinstance(stale_errors[0], task_run_scope.TaskRunScopeError)
        assert stale_errors[0].error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
        assert stale_adapter_starts == []
        assert supervisor.active(task_run_id) is generation_a

        with db_from_override() as verification_db:
            after_stale = verification_db.get(TaskRun, task_run_id)
            assert after_stale is not None
            assert after_stale.model_dump() == winner_snapshot
    finally:
        allow_stale_request.set()
        allow_downstream.set()
        await asyncio.to_thread(stale_thread.join, 2)
        if execution is not None:
            await asyncio.gather(execution, return_exceptions=True)
        db.close()

    assert downstream_calls == ["started", "finished"]


@pytest.mark.anyio
async def test_write_finalizer_stops_after_durable_commit_gap_loses_exact_generation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    task_run = _prepare_write_finalizer_fence_race(
        db,
        monkeypatch,
        worker_id="worker:finalizer-durable-gap-write",
    )
    task_run_id = task_run.id
    adapter_run_id = f"adapter-run:a:{task_run_id}"
    phase_committed = Event()
    competitor_finished = Event()
    competitor_errors: list[BaseException] = []
    replacement_lock_ids: list[str] = []
    baseline_ledgers: dict[str, dict[str, object]] = {}
    real_record_scope_validation_event = (
        run_engine_module._record_scope_validation_event
    )

    def pause_before_scope_pass_event(
        current_db,
        current_task_run,
        status,
        error_code,
    ):
        if status == "passed":
            phase_committed.set()
            if not competitor_finished.wait(timeout=2):
                raise AssertionError("The competing durable mutation did not finish.")
        return real_record_scope_validation_event(
            current_db,
            current_task_run,
            status,
            error_code,
        )

    monkeypatch.setattr(
        run_engine_module,
        "_record_scope_validation_event",
        pause_before_scope_pass_event,
    )

    def replace_durable_generation() -> None:
        try:
            if not phase_committed.wait(timeout=2):
                raise AssertionError("The write finalizer never reached the commit gap.")
            with db_from_override() as mutation_db:
                stored = mutation_db.get(TaskRun, task_run_id)
                task = mutation_db.get(Task, stored.task_id) if stored is not None else None
                original_lock = held_lock_for_target(
                    mutation_db,
                    DEMO_FRONTEND_TARGET_ID,
                )
                assert stored is not None
                assert task is not None
                baseline_ledgers.update(
                    {
                        ledger.id: ledger.model_dump()
                        for ledger in mutation_db.exec(
                            select(SessionExecutionLedger).where(
                                SessionExecutionLedger.session_id == task.session_id
                            )
                        ).all()
                    }
                )
                assert stored.state == "collecting_diff"
                assert stored.adapter_run_id == adapter_run_id
                assert original_lock is not None
                original_lock_id = original_lock.id
                released = release_target_lock_for_task_run(
                    mutation_db,
                    target_id=DEMO_FRONTEND_TARGET_ID,
                    expected_lock_id=original_lock_id,
                    worker_id=stored.runner_id,
                    task_run_id=stored.id,
                    session_id=task.session_id,
                    release_reason="test_rotate_during_finalizer_commit_gap",
                )
                assert released is not None
                replacement = acquire_target_lock(
                    mutation_db,
                    target_id=DEMO_FRONTEND_TARGET_ID,
                    session_id=task.session_id,
                    task_run_id=stored.id,
                    worker_id=stored.runner_id,
                    lease_expires_at=stored.lease_expires_at,
                )
                assert replacement.acquired is True
                assert replacement.lock is not None
                assert replacement.lock.id != original_lock_id
                replacement_lock_ids.append(replacement.lock.id)
                now = utc_now()
                result = mutation_db.execute(
                    update(TaskRun)
                    .where(TaskRun.id == stored.id)
                    .where(TaskRun.state == "collecting_diff")
                    .where(TaskRun.adapter_run_id == adapter_run_id)
                    .values(
                        state="interrupted",
                        error_code="COMPETING_FINALIZER",
                        error_message="A competing durable owner won finalization.",
                        ended_at=now,
                        updated_at=now,
                    )
                    .execution_options(synchronize_session=False)
                )
                mutation_db.commit()
                assert result.rowcount == 1
        except BaseException as exc:
            competitor_errors.append(exc)
        finally:
            competitor_finished.set()

    competitor = Thread(target=replace_durable_generation)
    competitor.start()
    execution_error: Optional[BaseException] = None
    try:
        await run_engine_module.execute_task_run(
            db,
            task_run,
            adapter_type="scripted_mock",
            adapter=_FenceRaceCompletedAdapter(task_run_id, []),
            supervisor=run_engine_module.RunSupervisor(),
            lease_renewal_interval_seconds=3600,
        )
    except BaseException as exc:
        execution_error = exc
    finally:
        competitor_finished.set()
        competitor.join(timeout=2)
        db.close()

    assert competitor.is_alive() is False
    assert competitor_errors == []
    assert execution_error is None
    assert len(replacement_lock_ids) == 1
    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        replacement_lock = verification_db.get(TargetLock, replacement_lock_ids[0])
        artifacts = verification_db.exec(
            select(Artifact).where(Artifact.task_run_id == task_run_id)
        ).all()
        events = verification_db.exec(
            select(TaskRunEvent).where(TaskRunEvent.task_run_id == task_run_id)
        ).all()
        task = verification_db.get(Task, stored.task_id) if stored is not None else None
        ledgers = (
            verification_db.exec(
                select(SessionExecutionLedger).where(
                    SessionExecutionLedger.session_id == task.session_id
                )
            ).all()
            if task is not None
            else []
        )

    assert stored is not None
    assert stored.state == "interrupted"
    assert stored.error_code == "COMPETING_FINALIZER"
    assert replacement_lock is not None
    assert replacement_lock.state == "held"
    assert replacement_lock.task_run_id == task_run_id
    assert artifacts == []
    assert {ledger.id: ledger.model_dump() for ledger in ledgers} == baseline_ledgers
    assert all(event.event_type != "task.scope_validation.passed" for event in events)
    assert all(
        not (
            event.event_type == "task.state"
            and json.loads(event.payload_json).get("state") == "completed"
        )
        for event in events
    )
    assert all(not event.event_type.startswith("artifact.") for event in events)


@pytest.mark.parametrize(
    "drift_kind",
    ("active_state", "task_target", "task_access", "session_workspace"),
)
@pytest.mark.anyio
async def test_write_finalizer_commit_fence_rejects_durable_scope_generation_drift(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    drift_kind: str,
) -> None:
    db = db_from_override()
    task_run = _prepare_write_finalizer_fence_race(
        db,
        monkeypatch,
        worker_id=f"worker:finalizer-scope-drift:{drift_kind}",
    )
    task_run_id = task_run.id
    task = db.get(Task, task_run.task_id)
    assert task is not None
    task_session_id = task.session_id
    session = db.get(Session, task.session_id)
    assert session is not None
    original_workspace_id = session.workspace_id
    replacement_workspace = Workspace(
        name=f"Finalizer drift workspace {drift_kind}",
        repo_url=f"local://finalizer-drift-{drift_kind}",
        root_path=f".worktrees/finalizer-drift-{drift_kind}",
        default_branch="main",
    )
    db.add(replacement_workspace)
    db.commit()
    replacement_workspace_id = replacement_workspace.id

    phase_committed = Event()
    competitor_finished = Event()
    competitor_errors: list[BaseException] = []
    baseline_ledgers: dict[str, dict[str, object]] = {}
    critical_calls = _record_finalizer_critical_calls(monkeypatch)
    real_record_scope_validation_event = (
        run_engine_module._record_scope_validation_event
    )

    def pause_before_scope_pass_event(
        current_db,
        current_task_run,
        status,
        error_code,
    ):
        if status == "passed":
            phase_committed.set()
            if not competitor_finished.wait(timeout=2):
                raise AssertionError("The competing scope mutation did not finish.")
        return real_record_scope_validation_event(
            current_db,
            current_task_run,
            status,
            error_code,
        )

    monkeypatch.setattr(
        run_engine_module,
        "_record_scope_validation_event",
        pause_before_scope_pass_event,
    )

    def drift_durable_scope_generation() -> None:
        try:
            if not phase_committed.wait(timeout=2):
                raise AssertionError("The finalizer never reached the commit gap.")
            with db_from_override() as mutation_db:
                stored = mutation_db.get(TaskRun, task_run_id)
                durable_task = (
                    mutation_db.get(Task, stored.task_id)
                    if stored is not None
                    else None
                )
                durable_session = (
                    mutation_db.get(Session, durable_task.session_id)
                    if durable_task is not None
                    else None
                )
                assert stored is not None
                assert durable_task is not None
                assert durable_session is not None
                assert stored.state == "collecting_diff"
                baseline_ledgers.update(
                    {
                        ledger.id: ledger.model_dump()
                        for ledger in mutation_db.exec(
                            select(SessionExecutionLedger).where(
                                SessionExecutionLedger.session_id
                                == task_session_id
                            )
                        ).all()
                    }
                )

                if drift_kind == "active_state":
                    result = mutation_db.execute(
                        update(TaskRun)
                        .where(TaskRun.id == task_run_id)
                        .where(TaskRun.state == "collecting_diff")
                        .values(state="starting_preview", updated_at=utc_now())
                        .execution_options(synchronize_session=False)
                    )
                    mutation_db.commit()
                    assert result.rowcount == 1
                elif drift_kind == "task_target":
                    plan = json.loads(durable_task.plan_json)
                    plan["targetId"] = DEMO_BACKEND_TARGET_ID
                    durable_task.plan_json = json.dumps(plan, separators=(",", ":"))
                    mutation_db.add(durable_task)
                    mutation_db.commit()
                elif drift_kind == "task_access":
                    plan = json.loads(durable_task.plan_json)
                    plan["writeMode"] = False
                    plan["readOnly"] = True
                    durable_task.plan_json = json.dumps(plan, separators=(",", ":"))
                    mutation_db.add(durable_task)
                    mutation_db.commit()
                else:
                    durable_session.workspace_id = replacement_workspace_id
                    mutation_db.add(durable_session)
                    mutation_db.commit()
        except BaseException as exc:
            competitor_errors.append(exc)
        finally:
            competitor_finished.set()

    competitor = Thread(target=drift_durable_scope_generation)
    competitor.start()
    execution_error: Optional[BaseException] = None
    try:
        await run_engine_module.execute_task_run(
            db,
            task_run,
            adapter_type="scripted_mock",
            adapter=_FenceRaceCompletedAdapter(task_run_id, []),
            supervisor=run_engine_module.RunSupervisor(),
            lease_renewal_interval_seconds=3600,
        )
    except BaseException as exc:
        execution_error = exc
    finally:
        competitor_finished.set()
        competitor.join(timeout=2)
        db.close()

    assert competitor.is_alive() is False
    assert competitor_errors == []
    assert execution_error is None
    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        durable_task = (
            verification_db.get(Task, stored.task_id)
            if stored is not None
            else None
        )
        durable_session = (
            verification_db.get(Session, durable_task.session_id)
            if durable_task is not None
            else None
        )
        events = verification_db.exec(
            select(TaskRunEvent).where(TaskRunEvent.task_run_id == task_run_id)
        ).all()
        artifacts = verification_db.exec(
            select(Artifact).where(Artifact.task_run_id == task_run_id)
        ).all()
        diffs = verification_db.exec(
            select(Diff)
            .join(Artifact, Diff.artifact_id == Artifact.id)
            .where(Artifact.task_run_id == task_run_id)
        ).all()
        reviews = verification_db.exec(
            select(Review)
            .join(Artifact, Review.artifact_id == Artifact.id)
            .where(Artifact.task_run_id == task_run_id)
        ).all()
        previews = verification_db.exec(
            select(Preview)
            .join(Artifact, Preview.artifact_id == Artifact.id)
            .where(Artifact.task_run_id == task_run_id)
        ).all()
        deployments = verification_db.exec(
            select(Deployment)
            .join(Artifact, Deployment.artifact_id == Artifact.id)
            .where(Artifact.task_run_id == task_run_id)
        ).all()
        ledgers = {
            ledger.id: ledger.model_dump()
            for ledger in verification_db.exec(
                select(SessionExecutionLedger).where(
                    SessionExecutionLedger.session_id == task_session_id
                )
            ).all()
        }

    assert stored is not None
    assert durable_task is not None
    assert durable_session is not None
    assert stored.state == (
        "starting_preview" if drift_kind == "active_state" else "collecting_diff"
    )
    if drift_kind == "task_target":
        assert json.loads(durable_task.plan_json)["targetId"] == (
            DEMO_BACKEND_TARGET_ID
        )
    elif drift_kind == "task_access":
        durable_plan = json.loads(durable_task.plan_json)
        assert durable_plan["writeMode"] is False
        assert durable_plan["readOnly"] is True
    elif drift_kind == "session_workspace":
        assert durable_session.workspace_id == replacement_workspace_id
    else:
        assert durable_session.workspace_id == original_workspace_id
    assert critical_calls == []
    assert artifacts == []
    assert diffs == []
    assert reviews == []
    assert previews == []
    assert deployments == []
    assert ledgers == baseline_ledgers
    assert all(
        event.event_type != "task.scope_validation.passed" for event in events
    )
    assert all(
        not (
            event.event_type == "task.state"
            and json.loads(event.payload_json).get("state") in {"completed", "failed"}
        )
        for event in events
    )


@pytest.mark.parametrize(
    ("terminal_state", "competing_queue_state"),
    (("completed", "failed"), ("failed", "completed")),
)
@pytest.mark.anyio
async def test_finalizer_terminal_commit_rejects_opposite_queue_terminal_state(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    terminal_state: str,
    competing_queue_state: str,
) -> None:
    db = db_from_override()
    task_run = _prepare_write_finalizer_fence_race(
        db,
        monkeypatch,
        worker_id=f"worker:opposite-terminal-queue:{terminal_state}",
    )
    task_run_id = task_run.id
    task = db.get(Task, task_run.task_id)
    assert task is not None
    task_session_id = task.session_id
    terminal_committed = Event()
    competitor_finished = Event()
    competitor_errors: list[BaseException] = []
    baseline_ledgers: dict[str, dict[str, object]] = {}
    ledger_commits: list[str] = []
    later_side_effects: list[str] = []
    real_refresh_ledger = run_engine_module.refresh_session_ledger_for_task_run

    if terminal_state == "failed":
        decision = task_run_scope.ScopeDecision(
            status="rejected",
            error_code="TASK_RUN_SCOPE_VIOLATION",
            target_id=DEMO_FRONTEND_TARGET_ID,
            changed_paths=("apps/demo/package.json",),
            rejected_paths=("apps/demo/package.json",),
            reason="The task run changed paths outside the assigned target.",
        )
        monkeypatch.setattr(
            run_engine_module,
            "validate_task_run_scope",
            lambda *args, **kwargs: decision,
        )
        monkeypatch.setattr(
            run_engine_module,
            "persist_scope_decision",
            lambda current_db, current_task_run, current_decision: current_task_run,
        )

        def reject_scope(*args, **kwargs):
            raise task_run_scope.TaskRunScopeError(
                "TASK_RUN_SCOPE_VIOLATION",
                "The task run changed paths outside the assigned target.",
            )

        monkeypatch.setattr(
            run_engine_module,
            "require_task_run_scope_passed",
            reject_scope,
        )

    def record_diff(*args, **kwargs):
        later_side_effects.append("diff")
        return None

    def record_review(*args, **kwargs):
        later_side_effects.append("review")
        return None

    def pause_then_refresh_ledger(current_db, current_task_run_id):
        terminal_committed.set()
        if not competitor_finished.wait(timeout=2):
            raise AssertionError("The competing queue mutation did not finish.")
        result = real_refresh_ledger(current_db, current_task_run_id)
        ledger_commits.append(current_task_run_id)
        return result

    def record_review_tasks(*args, **kwargs):
        later_side_effects.append("review-tasks")
        return []

    def record_preview_deploy(*args, **kwargs):
        later_side_effects.append("preview-deploy")
        return None

    async def record_downstream(*args, **kwargs):
        later_side_effects.append("downstream")
        return None

    monkeypatch.setattr(run_engine_module, "collect_task_run_diff", record_diff)
    monkeypatch.setattr(
        run_engine_module,
        "create_scripted_review_for_task_run",
        record_review,
    )
    monkeypatch.setattr(
        run_engine_module,
        "refresh_session_ledger_for_task_run",
        pause_then_refresh_ledger,
    )
    monkeypatch.setattr(
        run_engine_module,
        "_complete_ready_pipeline_review_tasks",
        record_review_tasks,
    )
    monkeypatch.setattr(
        run_engine_module,
        "_maybe_auto_preview_and_mock_deploy",
        record_preview_deploy,
    )
    monkeypatch.setattr(
        run_engine_module,
        "_auto_start_next_pipeline_task",
        record_downstream,
    )

    def replace_queue_terminal_state() -> None:
        try:
            if not terminal_committed.wait(timeout=2):
                raise AssertionError("The finalizer never committed its terminal state.")
            with db_from_override() as mutation_db:
                stored = mutation_db.get(TaskRun, task_run_id)
                queue_entry = entry_for_task_run(mutation_db, task_run_id)
                assert stored is not None
                assert stored.state == terminal_state
                assert queue_entry is not None
                assert queue_entry.state == terminal_state
                queue_entry.state = competing_queue_state
                mutation_db.add(queue_entry)
                mutation_db.commit()
                baseline_ledgers.update(
                    {
                        ledger.id: ledger.model_dump()
                        for ledger in mutation_db.exec(
                            select(SessionExecutionLedger).where(
                                SessionExecutionLedger.session_id
                                == task_session_id
                            )
                        ).all()
                    }
                )
        except BaseException as exc:
            competitor_errors.append(exc)
        finally:
            competitor_finished.set()

    competitor = Thread(target=replace_queue_terminal_state)
    competitor.start()
    execution_error: Optional[BaseException] = None
    try:
        await run_engine_module.execute_task_run(
            db,
            task_run,
            adapter_type="scripted_mock",
            adapter=_FenceRaceCompletedAdapter(task_run_id, []),
            supervisor=run_engine_module.RunSupervisor(),
            lease_renewal_interval_seconds=3600,
        )
    except BaseException as exc:
        execution_error = exc
    finally:
        competitor_finished.set()
        competitor.join(timeout=2)
        db.close()

    assert competitor.is_alive() is False
    assert competitor_errors == []
    assert execution_error is None
    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        queue_entry = entry_for_task_run(verification_db, task_run_id)
        ledgers = {
            ledger.id: ledger.model_dump()
            for ledger in verification_db.exec(
                select(SessionExecutionLedger).where(
                    SessionExecutionLedger.session_id == task_session_id
                )
            ).all()
        }
        previews = verification_db.exec(
            select(Preview)
            .join(Artifact, Preview.artifact_id == Artifact.id)
            .where(Artifact.task_run_id == task_run_id)
        ).all()
        deployments = verification_db.exec(
            select(Deployment)
            .join(Artifact, Deployment.artifact_id == Artifact.id)
            .where(Artifact.task_run_id == task_run_id)
        ).all()

    assert stored is not None
    assert stored.state == terminal_state
    assert queue_entry is not None
    assert queue_entry.state == competing_queue_state
    assert ledger_commits == []
    assert ledgers == baseline_ledgers
    assert previews == []
    assert deployments == []
    assert not {"review-tasks", "preview-deploy", "downstream"}.intersection(
        later_side_effects
    )


@pytest.mark.anyio
async def test_terminal_authorization_rejects_collecting_diff_identity_map_aba(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    _, task_run, queue_entry, _ = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id="worker:terminal-authorization-aba",
    )
    task_run_id = task_run.id
    baseline_ledgers: dict[str, dict[str, object]] = {}
    later_side_effects: list[str] = []
    real_refresh_ledger = run_engine_module.refresh_session_ledger_for_task_run
    reverted = False

    class CompletingReadonlyAdapter(_ReadonlyCreateRunDelegate):
        async def streamEvents(self, current_adapter_run_id):
            yield {"type": "completed", "payload": {}}

        async def interrupt(self, current_adapter_run_id):
            return None

        async def approve(self, current_adapter_run_id, approval):
            return None

        async def collectArtifacts(self, current_adapter_run_id):
            return []

        async def cleanup(self, current_adapter_run_id):
            return None

    monkeypatch.setattr(
        run_engine_module,
        "collect_task_run_diff",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        run_engine_module,
        "create_scripted_review_for_task_run",
        lambda *args, **kwargs: None,
    )

    def revert_terminal_then_refresh_ledger(current_db, current_task_run_id):
        nonlocal reverted
        assert reverted is False
        reverted = True
        with db_from_override() as mutation_db:
            stored = mutation_db.get(TaskRun, task_run_id)
            task = mutation_db.get(Task, stored.task_id) if stored is not None else None
            durable_queue = entry_for_task_run(mutation_db, task_run_id)
            assert stored is not None
            assert task is not None
            assert durable_queue is not None
            assert stored.state == "completed"
            assert durable_queue.state == "completed"
            baseline_ledgers.update(
                {
                    ledger.id: ledger.model_dump()
                    for ledger in mutation_db.exec(
                        select(SessionExecutionLedger).where(
                            SessionExecutionLedger.session_id == task.session_id
                        )
                    ).all()
                }
            )
            now = utc_now()
            run_result = mutation_db.execute(
                update(TaskRun)
                .where(TaskRun.id == task_run_id)
                .where(TaskRun.state == "completed")
                .values(
                    state="collecting_diff",
                    ended_at=None,
                    updated_at=now,
                )
                .execution_options(synchronize_session=False)
            )
            queue_result = mutation_db.execute(
                update(SessionQueueEntry)
                .where(SessionQueueEntry.id == queue_entry.id)
                .where(SessionQueueEntry.state == "completed")
                .values(
                    state="running",
                    finished_at=None,
                    updated_at=now,
                )
                .execution_options(synchronize_session=False)
            )
            mutation_db.commit()
            assert run_result.rowcount == 1
            assert queue_result.rowcount == 1
        return real_refresh_ledger(current_db, current_task_run_id)

    monkeypatch.setattr(
        run_engine_module,
        "refresh_session_ledger_for_task_run",
        revert_terminal_then_refresh_ledger,
    )
    monkeypatch.setattr(
        run_engine_module,
        "_complete_ready_pipeline_review_tasks",
        lambda *args, **kwargs: later_side_effects.append("review-tasks"),
    )
    monkeypatch.setattr(
        run_engine_module,
        "_maybe_auto_preview_and_mock_deploy",
        lambda *args, **kwargs: later_side_effects.append("preview-deploy"),
    )

    async def record_downstream(*args, **kwargs):
        later_side_effects.append("downstream")

    monkeypatch.setattr(
        run_engine_module,
        "_auto_start_next_pipeline_task",
        record_downstream,
    )
    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", _fail_if_readonly_touches_target_lock)
    try:
        await run_engine_module.execute_task_run(
            db,
            task_run,
            adapter_type="scripted_mock",
            adapter=CompletingReadonlyAdapter(),
            supervisor=run_engine_module.RunSupervisor(),
            lease_renewal_interval_seconds=3600,
        )
    finally:
        event.remove(
            engine,
            "before_cursor_execute",
            _fail_if_readonly_touches_target_lock,
        )
        db.close()

    assert reverted is True
    assert later_side_effects == []
    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        durable_queue = entry_for_task_run(verification_db, task_run_id)
        task = verification_db.get(Task, stored.task_id) if stored is not None else None
        ledgers = (
            {
                ledger.id: ledger.model_dump()
                for ledger in verification_db.exec(
                    select(SessionExecutionLedger).where(
                        SessionExecutionLedger.session_id == task.session_id
                    )
                ).all()
            }
            if task is not None
            else {}
        )
    assert stored is not None
    assert durable_queue is not None
    assert stored.state == "failed"
    assert stored.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert durable_queue.state == "failed"
    assert ledgers == baseline_ledgers


@pytest.mark.parametrize("access_mode", ("readonly", "write"))
def test_finalizer_fence_rechecks_database_lease_after_writer_wait(
    tmp_path: Path,
    access_mode: str,
) -> None:
    database_path = tmp_path / f"finalizer-lease-wait-{access_mode}.db"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    SQLModel.metadata.create_all(engine)
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")

    with DbSession(engine) as setup_db:
        workspace = Workspace(
            name=f"Finalizer lease wait {access_mode}",
            repo_url="local://apps/demo",
            root_path="apps/demo",
            default_branch="main",
        )
        session = Session(
            workspace_id=workspace.id,
            title=f"Finalizer lease wait {access_mode}",
            bound_branch="main",
            worktree_path=f".worktrees/finalizer-lease-wait-{access_mode}",
        )
        agent = Agent(
            name=f"Finalizer Lease {access_mode.title()}",
            role="qa" if access_mode == "readonly" else "frontend",
            adapter_type="scripted_mock",
            provider="local",
        )
        task = Task(
            session_id=session.id,
            title=f"Finalizer lease wait {access_mode}",
            intent_type="review" if access_mode == "readonly" else "frontend_change",
            status="in_progress",
            assigned_agent_id=agent.id,
            plan_json=json.dumps(
                {
                    "targetId": DEMO_FRONTEND_TARGET_ID,
                    "readOnly": access_mode == "readonly",
                },
                separators=(",", ":"),
            ),
        )
        now = utc_now()
        runner_id = f"worker:finalizer-lease-wait:{access_mode}"
        adapter_run_id = f"adapter-run:finalizer-lease-wait:{access_mode}"
        task_run = TaskRun(
            task_id=task.id,
            agent_id=agent.id,
            adapter_run_id=adapter_run_id,
            state="collecting_diff",
            started_at=now,
            runner_id=runner_id,
            last_heartbeat_at=now,
            lease_expires_at=now + timedelta(seconds=30),
            worktree_path=session.worktree_path,
        )
        queue_entry = SessionQueueEntry(
            session_id=session.id,
            task_id=task.id,
            task_run_id=task_run.id,
            access_mode=access_mode,
            target_id=DEMO_FRONTEND_TARGET_ID,
            target_lock_key=(
                run_engine_module.target_lock_key_for_target(
                    DEMO_FRONTEND_TARGET_ID
                )
                if access_mode == "write"
                else None
            ),
            position=1,
            state="running",
            started_at=now,
        )
        execution_attempt_id = f"attempt:finalizer-lease-wait:{access_mode}"
        task_run.metrics_json = json.dumps(
            {
                "taskRunExecutionAccessBinding": {
                    "taskRunId": task_run.id,
                    "taskId": task.id,
                    "sessionId": session.id,
                    "queueEntryId": queue_entry.id,
                    "runnerId": runner_id,
                    "accessMode": access_mode,
                    "executionAttemptId": execution_attempt_id,
                }
            },
            separators=(",", ":"),
        )
        target_lock = None
        if access_mode == "write":
            target_lock = TargetLock(
                lock_key=run_engine_module.target_lock_key_for_target(
                    DEMO_FRONTEND_TARGET_ID
                ),
                target_id=DEMO_FRONTEND_TARGET_ID,
                session_id=session.id,
                task_run_id=task_run.id,
                worker_id=runner_id,
                mode="write",
                state="held",
                lease_expires_at=now + timedelta(seconds=30),
                acquired_at=now,
            )
        setup_db.add(workspace)
        setup_db.add(session)
        setup_db.add(agent)
        setup_db.add(task)
        setup_db.add(task_run)
        setup_db.add(queue_entry)
        if target_lock is not None:
            setup_db.add(target_lock)
        setup_db.commit()
        token = run_engine_module._ExecutionLeaseToken(
            task_run_id=task_run.id,
            task_id=task.id,
            session_id=session.id,
            workspace_id=workspace.id,
            queue_entry_id=queue_entry.id,
            runner_id=runner_id,
            access_mode=access_mode,
            task_write_lock_required=access_mode == "write",
            target_id=DEMO_FRONTEND_TARGET_ID,
            expected_lock_id=target_lock.id if target_lock is not None else None,
            execution_attempt_id=execution_attempt_id,
            adapter_run_id=adapter_run_id,
        )
        task_run_id = task_run.id
        target_lock_id = target_lock.id if target_lock is not None else None

    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            UPDATE taskrun
            SET lease_expires_at = strftime('%Y-%m-%d %H:%M:%f', 'now', '+2 seconds')
            WHERE id = ?
            """,
            (task_run_id,),
        )
        if target_lock_id is not None:
            connection.exec_driver_sql(
                """
                UPDATE targetlock
                SET lease_expires_at = strftime('%Y-%m-%d %H:%M:%f', 'now', '+30 seconds')
                WHERE id = ?
                """,
                (target_lock_id,),
            )

    cas_started = Event()
    cas_finished = Event()
    writer_finished = Event()
    writer_errors: list[BaseException] = []
    target_lock_sql: list[str] = []

    def is_finalizer_cas(statement: str) -> bool:
        normalized = " ".join(statement.casefold().split())
        return normalized.startswith("update taskrun set updated_at=taskrun.updated_at")

    def before_cursor_execute(
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        if is_finalizer_cas(statement):
            cas_started.set()
        if "targetlock" in statement.casefold():
            target_lock_sql.append(statement)

    def after_cursor_execute(
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        if is_finalizer_cas(statement):
            cas_finished.set()

    def delayed_finalizer_commit() -> None:
        fence = run_engine_module._FinalizerCommitFence(token)
        try:
            with DbSession(engine) as writer_db:
                stored = writer_db.get(TaskRun, task_run_id)
                assert stored is not None
                stored.error_message = "expired finalizer must not commit"
                writer_db.add(stored)
                event.listen(writer_db, "before_commit", fence.before_commit)
                event.listen(writer_db, "after_commit", fence.after_commit)
                event.listen(writer_db, "after_rollback", fence.after_rollback)
                try:
                    writer_db.commit()
                finally:
                    event.remove(writer_db, "before_commit", fence.before_commit)
                    event.remove(writer_db, "after_commit", fence.after_commit)
                    event.remove(writer_db, "after_rollback", fence.after_rollback)
        except BaseException as exc:
            writer_errors.append(exc)
        finally:
            writer_finished.set()

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    event.listen(engine, "after_cursor_execute", after_cursor_execute)
    blocker = engine.connect()
    writer = Thread(target=delayed_finalizer_commit, daemon=True)
    try:
        blocker.exec_driver_sql("BEGIN IMMEDIATE")
        writer.start()
        assert cas_started.wait(timeout=5)
        assert blocker.exec_driver_sql(
            """
            SELECT julianday(lease_expires_at) > julianday('now')
            FROM taskrun
            WHERE id = ?
            """,
            (task_run_id,),
        ).scalar_one() == 1
        assert cas_finished.is_set() is False
        assert writer_finished.is_set() is False

        deadline = monotonic() + 5
        while blocker.exec_driver_sql(
            """
            SELECT julianday(lease_expires_at) <= julianday('now')
            FROM taskrun
            WHERE id = ?
            """,
            (task_run_id,),
        ).scalar_one() != 1:
            assert monotonic() < deadline
            writer_finished.wait(timeout=0.01)

        assert writer_finished.is_set() is False
        blocker.commit()
        assert writer_finished.wait(timeout=5)
        writer.join(timeout=5)
    finally:
        if blocker.in_transaction():
            blocker.rollback()
        blocker.close()
        writer.join(timeout=5)
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
        event.remove(engine, "after_cursor_execute", after_cursor_execute)

    assert writer.is_alive() is False
    assert cas_finished.is_set() is True
    assert len(writer_errors) == 1
    assert isinstance(writer_errors[0], task_run_scope.TaskRunScopeError)
    assert writer_errors[0].error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    if access_mode == "readonly":
        assert target_lock_sql == []
    with DbSession(engine) as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        durable_queue = entry_for_task_run(verification_db, task_run_id)
    engine.dispose()

    assert stored is not None
    assert durable_queue is not None
    assert stored.state == "collecting_diff"
    assert stored.error_message is None
    assert durable_queue.state == "running"


@pytest.mark.parametrize("access_mode", ("readonly", "write"))
def test_execute_task_run_recovery_rechecks_database_lease_after_writer_wait(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    access_mode: str,
) -> None:
    database_path = tmp_path / f"finalizer-recovery-lease-wait-{access_mode}.db"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    SQLModel.metadata.create_all(engine)
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")

    _stub_scope_snapshot(monkeypatch, _scope_snapshot())
    if access_mode == "readonly":
        monkeypatch.setattr(
            task_runs_module,
            "CAPABILITIES_BY_ADAPTER",
            {
                **task_runs_module.CAPABILITIES_BY_ADAPTER,
                "scripted_mock": ("review",),
            },
        )

    with DbSession(engine) as setup_db:
        workspace = Workspace(
            name=f"Finalizer recovery lease wait {access_mode}",
            repo_url="local://apps/demo",
            root_path="apps/demo",
            default_branch="main",
        )
        session = Session(
            workspace_id=workspace.id,
            title=f"Finalizer recovery lease wait {access_mode}",
            bound_branch="main",
            worktree_path=f".worktrees/finalizer-recovery-lease-wait-{access_mode}",
        )
        agent = Agent(
            name=f"Finalizer Recovery Lease {access_mode.title()}",
            role="qa" if access_mode == "readonly" else "frontend",
            adapter_type="scripted_mock",
            provider="local",
        )
        task = Task(
            session_id=session.id,
            title=f"Finalizer recovery lease wait {access_mode}",
            intent_type="review" if access_mode == "readonly" else "frontend_change",
            status="pending",
            assigned_agent_id=agent.id,
            plan_json=json.dumps(
                {
                    "targetId": DEMO_FRONTEND_TARGET_ID,
                    "readOnly": access_mode == "readonly",
                },
                separators=(",", ":"),
            ),
        )
        setup_db.add(workspace)
        setup_db.add(session)
        setup_db.add(agent)
        setup_db.add(task)
        setup_db.commit()

        runner_id = f"worker:finalizer-recovery-lease-wait:{access_mode}"
        task_run = claim_task_run_for_worker(
            setup_db,
            create_task_run(setup_db, task.id).id,
            worker_id=runner_id,
        )
        assert run_engine_module._prepare_claimed_task_run_for_adapter(
            setup_db,
            task_run,
            runner_id,
        ) is True
        queue_entry = entry_for_task_run(setup_db, task_run.id)
        assert queue_entry is not None
        assert queue_entry.state == "running"
        target_lock = (
            held_lock_for_target(setup_db, DEMO_FRONTEND_TARGET_ID)
            if access_mode == "write"
            else None
        )
        if access_mode == "write":
            assert target_lock is not None
        task_run_id = task_run.id
        queue_entry_id = queue_entry.id
        target_lock_id = target_lock.id if target_lock is not None else None

    finalizer_ready = Event()
    allow_finalizer = Event()
    finalizer_cas_started = Event()
    execution_finished = Event()
    execution_errors: list[BaseException] = []
    target_lock_sql: list[str] = []
    adapter_run_id = f"adapter-run:finalizer-recovery-lease-wait:{access_mode}"
    real_transition_task_run = run_engine_module.transition_task_run

    def pause_before_terminal_transition(
        current_db,
        current_task_run_id,
        state,
        *args,
        **kwargs,
    ):
        if current_task_run_id == task_run_id and state == "completed":
            current_db.rollback()
            finalizer_ready.set()
            if not allow_finalizer.wait(timeout=5):
                raise AssertionError("The finalizer writer fence was not released.")
        return real_transition_task_run(
            current_db,
            current_task_run_id,
            state,
            *args,
            **kwargs,
        )

    monkeypatch.setattr(
        run_engine_module,
        "transition_task_run",
        pause_before_terminal_transition,
    )
    monkeypatch.setattr(
        run_engine_module,
        "_collect_completed_task_run_artifacts",
        lambda *args, **kwargs: None,
    )

    class CompletedAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=access_mode == "write",
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            return AdapterRun(adapterRunId=adapter_run_id)

        async def streamEvents(self, current_adapter_run_id):
            yield AgentEvent(
                type="completed",
                taskRunId=task_run_id,
                sequence=1,
                payload={"ok": True},
            )

        async def interrupt(self, current_adapter_run_id):
            return None

        async def approve(self, current_adapter_run_id, approval):
            return None

        async def collectArtifacts(self, current_adapter_run_id):
            return []

        async def cleanup(self, current_adapter_run_id):
            return None

    def is_finalizer_cas(statement: str) -> bool:
        normalized = " ".join(statement.casefold().split())
        return normalized.startswith("update taskrun set updated_at=taskrun.updated_at")

    def before_cursor_execute(
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        if is_finalizer_cas(statement):
            finalizer_cas_started.set()
        if "targetlock" in statement.casefold():
            target_lock_sql.append(statement)

    def run_execution() -> None:
        try:
            with DbSession(engine) as execution_db:
                stored = execution_db.get(TaskRun, task_run_id)
                assert stored is not None
                asyncio.run(
                    run_engine_module.execute_task_run(
                        execution_db,
                        stored,
                        adapter_type="scripted_mock",
                        adapter=CompletedAdapter(),
                        supervisor=run_engine_module.RunSupervisor(),
                        lease_renewal_interval_seconds=3600,
                    )
                )
        except BaseException as exc:
            execution_errors.append(exc)
        finally:
            execution_finished.set()

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    blocker = None
    execution = Thread(target=run_execution, daemon=True)
    try:
        execution.start()
        assert finalizer_ready.wait(timeout=5)
        with engine.begin() as connection:
            connection.exec_driver_sql(
                """
                UPDATE taskrun
                SET lease_expires_at = strftime('%Y-%m-%d %H:%M:%f', 'now', '+2 seconds')
                WHERE id = ?
                """,
                (task_run_id,),
            )
            if target_lock_id is not None:
                connection.exec_driver_sql(
                    """
                    UPDATE targetlock
                    SET lease_expires_at = strftime('%Y-%m-%d %H:%M:%f', 'now', '+30 seconds')
                    WHERE id = ?
                    """,
                    (target_lock_id,),
                )

        blocker = engine.connect()
        blocker.exec_driver_sql("BEGIN IMMEDIATE")
        allow_finalizer.set()
        assert finalizer_cas_started.wait(timeout=5)
        assert blocker.exec_driver_sql(
            """
            SELECT julianday(lease_expires_at) > julianday('now')
            FROM taskrun
            WHERE id = ?
            """,
            (task_run_id,),
        ).scalar_one() == 1
        assert execution_finished.is_set() is False

        deadline = monotonic() + 5
        while blocker.exec_driver_sql(
            """
            SELECT julianday(lease_expires_at) <= julianday('now')
            FROM taskrun
            WHERE id = ?
            """,
            (task_run_id,),
        ).scalar_one() != 1:
            assert monotonic() < deadline
            execution_finished.wait(timeout=0.01)

        assert execution_finished.is_set() is False
        blocker.commit()
        assert execution_finished.wait(timeout=5)
        execution.join(timeout=5)
    finally:
        allow_finalizer.set()
        if blocker is not None:
            if blocker.in_transaction():
                blocker.rollback()
            blocker.close()
        execution.join(timeout=5)
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
        task_run_scope.clear_task_run_scope_runtime_context(task_run_id)
        task_run_scope.clear_task_run_target_lock_acquisition_context(task_run_id)

    assert execution.is_alive() is False
    assert execution_errors == []
    if access_mode == "readonly":
        assert target_lock_sql == []
    with DbSession(engine) as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        durable_queue = verification_db.get(SessionQueueEntry, queue_entry_id)
        durable_lock = (
            verification_db.get(TargetLock, target_lock_id)
            if target_lock_id is not None
            else None
        )
        terminal_events = [
            event
            for event in verification_db.exec(
                select(TaskRunEvent).where(TaskRunEvent.task_run_id == task_run_id)
            ).all()
            if event.event_type == "task.state"
            and json.loads(event.payload_json).get("state") in {"completed", "failed"}
        ]
        artifacts = verification_db.exec(
            select(Artifact).where(Artifact.task_run_id == task_run_id)
        ).all()
    engine.dispose()

    assert stored is not None
    assert durable_queue is not None
    assert stored.state == "collecting_diff"
    assert stored.error_code is None
    assert stored.error_message is None
    assert durable_queue.state == "running"
    assert durable_queue.finished_at is None
    assert terminal_events == []
    assert artifacts == []
    if access_mode == "write":
        assert durable_lock is not None
        assert durable_lock.state == "held"
        assert durable_lock.task_run_id == task_run_id
        assert durable_lock.worker_id == runner_id


def test_finalizer_fence_maps_initial_database_lock_to_scope_error(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        task_run, _, token = _prepare_readonly_execution_lease(
            db,
            monkeypatch,
            worker_id="worker:finalizer-initial-database-lock",
            execution_attempt_id="attempt:finalizer-initial-database-lock",
        )
        adapter_run_id = "adapter-run:finalizer-initial-database-lock"
        task_run.adapter_run_id = adapter_run_id
        db.add(task_run)
        db.commit()
        token = replace(token, adapter_run_id=adapter_run_id)
        transition_task_run(db, task_run.id, "collecting_diff")

        stored = db.get(TaskRun, task_run.id)
        assert stored is not None
        stored.error_message = "locked finalizer must not commit"
        db.add(stored)
        fence = run_engine_module._FinalizerCommitFence(token)
        fail_next_fence_select = True

        def raise_initial_database_lock(
            connection,
            cursor,
            statement,
            parameters,
            context,
            executemany,
        ) -> None:
            nonlocal fail_next_fence_select
            normalized = " ".join(statement.casefold().split())
            if (
                fail_next_fence_select
                and normalized.startswith("select taskrun.id, taskrun.task_id")
            ):
                fail_next_fence_select = False
                raise sqlite3.OperationalError("database is locked")

        event.listen(db, "before_commit", fence.before_commit)
        event.listen(db.get_bind(), "before_cursor_execute", raise_initial_database_lock)
        try:
            with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
                db.commit()
            db.rollback()
        finally:
            event.remove(db, "before_commit", fence.before_commit)
            event.remove(
                db.get_bind(),
                "before_cursor_execute",
                raise_initial_database_lock,
            )

        assert fail_next_fence_select is False
        assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
        task_run_id = task_run.id

    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        durable_queue = entry_for_task_run(verification_db, task_run_id)

    assert stored is not None
    assert durable_queue is not None
    assert stored.state == "collecting_diff"
    assert stored.error_message is None
    assert durable_queue.state == "running"


@pytest.mark.anyio
async def test_exact_finalizer_scope_failure_completes_failed_queue_and_lock_cleanup(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    task_run = _prepare_write_finalizer_fence_race(
        db,
        monkeypatch,
        worker_id="worker:exact-finalizer-scope-failure",
    )
    task_run_id = task_run.id
    original_lock = held_lock_for_target(db, DEMO_FRONTEND_TARGET_ID)
    assert original_lock is not None
    original_lock_id = original_lock.id
    decision = task_run_scope.ScopeDecision(
        status="rejected",
        error_code="TASK_RUN_SCOPE_VIOLATION",
        target_id=DEMO_FRONTEND_TARGET_ID,
        changed_paths=("apps/demo/package.json",),
        rejected_paths=("apps/demo/package.json",),
        reason="The task run changed paths outside the assigned target.",
    )
    ledger_calls: list[str] = []
    real_refresh_ledger = run_engine_module.refresh_session_ledger_for_task_run

    monkeypatch.setattr(
        run_engine_module,
        "validate_task_run_scope",
        lambda *args, **kwargs: decision,
    )
    monkeypatch.setattr(
        run_engine_module,
        "persist_scope_decision",
        lambda current_db, current_task_run, current_decision: current_task_run,
    )

    def reject_scope(*args, **kwargs):
        raise task_run_scope.TaskRunScopeError(
            "TASK_RUN_SCOPE_VIOLATION",
            "The task run changed paths outside the assigned target.",
        )

    monkeypatch.setattr(
        run_engine_module,
        "require_task_run_scope_passed",
        reject_scope,
    )

    def refresh_ledger(current_db, current_task_run_id):
        ledger_calls.append(current_task_run_id)
        return real_refresh_ledger(current_db, current_task_run_id)

    monkeypatch.setattr(
        run_engine_module,
        "refresh_session_ledger_for_task_run",
        refresh_ledger,
    )

    def unexpected(*args, **kwargs):
        pytest.fail("scope failure reached an artifact or success side effect")

    async def unexpected_async(*args, **kwargs):
        pytest.fail("scope failure reached downstream scheduling")

    monkeypatch.setattr(run_engine_module, "collect_task_run_diff", unexpected)
    monkeypatch.setattr(
        run_engine_module,
        "create_scripted_review_for_task_run",
        unexpected,
    )
    monkeypatch.setattr(
        run_engine_module,
        "_complete_ready_pipeline_review_tasks",
        unexpected,
    )
    monkeypatch.setattr(
        run_engine_module,
        "_maybe_auto_preview_and_mock_deploy",
        unexpected,
    )
    monkeypatch.setattr(
        run_engine_module,
        "_auto_start_next_pipeline_task",
        unexpected_async,
    )

    supervisor = run_engine_module.RunSupervisor()
    try:
        await run_engine_module.execute_task_run(
            db,
            task_run,
            adapter_type="scripted_mock",
            adapter=_FenceRaceCompletedAdapter(task_run_id, []),
            supervisor=supervisor,
            lease_renewal_interval_seconds=3600,
        )
    finally:
        db.close()

    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        queue_entry = entry_for_task_run(verification_db, task_run_id)
        durable_lock = verification_db.get(TargetLock, original_lock_id)
        events = verification_db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == task_run_id)
            .order_by(TaskRunEvent.sequence)
        ).all()
        artifacts = verification_db.exec(
            select(Artifact).where(Artifact.task_run_id == task_run_id)
        ).all()

    assert stored is not None
    assert stored.state == "failed"
    assert stored.error_code == "TASK_RUN_SCOPE_VIOLATION"
    assert queue_entry is not None
    assert queue_entry.state == "failed"
    assert durable_lock is not None
    assert durable_lock.state == "released"
    assert durable_lock.worker_id is None
    assert durable_lock.lease_expires_at is None
    assert ledger_calls == [task_run_id]
    assert artifacts == []
    assert supervisor.active(task_run_id) is None
    assert any(
        event.event_type == "task.scope_validation.failed" for event in events
    )
    assert any(
        event.event_type == "task.state"
        and json.loads(event.payload_json).get("state") == "failed"
        for event in events
    )


@pytest.mark.anyio
async def test_readonly_finalizer_stops_after_commit_gap_identity_drift_without_target_lock_sql(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = db_from_override()
    _, task_run, _, _ = _prepare_readonly_execution_boundary(
        db,
        monkeypatch,
        worker_id="worker:finalizer-durable-gap-readonly",
    )
    task_run_id = task_run.id
    adapter_run_id = f"adapter-run:readonly:a:{task_run_id}"
    replacement_adapter_run_id = f"adapter-run:readonly:b:{task_run_id}"
    phase_committed = Event()
    competitor_finished = Event()
    competitor_errors: list[BaseException] = []
    baseline_ledgers: dict[str, dict[str, object]] = {}
    real_transition_task_run = run_engine_module.transition_task_run

    def pause_before_completed_transition(
        current_db,
        current_task_run_id,
        state,
        *args,
        **kwargs,
    ):
        if current_task_run_id == task_run_id and state == "completed":
            phase_committed.set()
            if not competitor_finished.wait(timeout=2):
                raise AssertionError("The competing readonly mutation did not finish.")
        return real_transition_task_run(
            current_db,
            current_task_run_id,
            state,
            *args,
            **kwargs,
        )

    monkeypatch.setattr(
        run_engine_module,
        "transition_task_run",
        pause_before_completed_transition,
    )

    class CompletedReadonlyAdapter:
        def getCapabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                supportsStreaming=True,
                supportsInterrupt=True,
                supportsApproval=False,
                supportsFileEdit=False,
                supportsShellCommand=False,
                supportsDiffArtifact=False,
                supportsPreviewArtifact=False,
                supportsNetwork=False,
            )

        async def createRun(self, request):
            return AdapterRun(adapterRunId=adapter_run_id)

        async def streamEvents(self, current_adapter_run_id):
            yield {"type": "completed", "payload": {}}

        async def interrupt(self, current_adapter_run_id):
            return None

        async def approve(self, current_adapter_run_id, approval):
            return None

        async def collectArtifacts(self, current_adapter_run_id):
            return []

        async def cleanup(self, current_adapter_run_id):
            return None

    def replace_readonly_identity() -> None:
        try:
            if not phase_committed.wait(timeout=2):
                raise AssertionError("The readonly finalizer never reached the commit gap.")
            with db_from_override() as mutation_db:
                stored = mutation_db.get(TaskRun, task_run_id)
                task = mutation_db.get(Task, stored.task_id) if stored is not None else None
                assert task is not None
                baseline_ledgers.update(
                    {
                        ledger.id: ledger.model_dump()
                        for ledger in mutation_db.exec(
                            select(SessionExecutionLedger).where(
                                SessionExecutionLedger.session_id == task.session_id
                            )
                        ).all()
                    }
                )
                now = utc_now()
                result = mutation_db.execute(
                    update(TaskRun)
                    .where(TaskRun.id == task_run_id)
                    .where(TaskRun.state == "collecting_diff")
                    .where(TaskRun.adapter_run_id == adapter_run_id)
                    .values(
                        state="interrupted",
                        adapter_run_id=replacement_adapter_run_id,
                        error_code="COMPETING_READONLY_FINALIZER",
                        error_message="A competing readonly owner won finalization.",
                        ended_at=now,
                        updated_at=now,
                    )
                    .execution_options(synchronize_session=False)
                )
                mutation_db.commit()
                assert result.rowcount == 1
        except BaseException as exc:
            competitor_errors.append(exc)
        finally:
            competitor_finished.set()

    competitor = Thread(target=replace_readonly_identity)
    competitor.start()
    execution_error: Optional[BaseException] = None
    event.listen(
        db.get_bind(),
        "before_cursor_execute",
        _fail_if_readonly_touches_target_lock,
    )
    try:
        await run_engine_module.execute_task_run(
            db,
            task_run,
            adapter_type="scripted_mock",
            adapter=CompletedReadonlyAdapter(),
            supervisor=run_engine_module.RunSupervisor(),
            lease_renewal_interval_seconds=3600,
        )
    except BaseException as exc:
        execution_error = exc
    finally:
        competitor_finished.set()
        competitor.join(timeout=2)
        event.remove(
            db.get_bind(),
            "before_cursor_execute",
            _fail_if_readonly_touches_target_lock,
        )
        db.close()

    assert competitor.is_alive() is False
    assert competitor_errors == []
    assert execution_error is None
    with db_from_override() as verification_db:
        stored = verification_db.get(TaskRun, task_run_id)
        artifacts = verification_db.exec(
            select(Artifact).where(Artifact.task_run_id == task_run_id)
        ).all()
        events = verification_db.exec(
            select(TaskRunEvent).where(TaskRunEvent.task_run_id == task_run_id)
        ).all()
        task = verification_db.get(Task, stored.task_id) if stored is not None else None
        ledgers = (
            verification_db.exec(
                select(SessionExecutionLedger).where(
                    SessionExecutionLedger.session_id == task.session_id
                )
            ).all()
            if task is not None
            else []
        )

    assert stored is not None
    assert stored.state == "interrupted"
    assert stored.adapter_run_id == replacement_adapter_run_id
    assert stored.error_code == "COMPETING_READONLY_FINALIZER"
    assert artifacts == []
    assert {ledger.id: ledger.model_dump() for ledger in ledgers} == baseline_ledgers
    assert all(
        not (
            event.event_type == "task.state"
            and json.loads(event.payload_json).get("state") == "completed"
        )
        for event in events
    )
    assert all(not event.event_type.startswith("artifact.") for event in events)


def test_failed_finalizer_callback_does_not_seal_supervisor_generation() -> None:
    supervisor = run_engine_module.RunSupervisor()
    generation_a = supervisor.register(
        task_run_id="run:failed-finalizer-callback",
        adapter_type="scripted_mock",
    )

    def fail_finalizer_callback() -> None:
        raise RuntimeError("injected finalizer callback failure")

    with pytest.raises(RuntimeError, match="injected finalizer callback failure"):
        supervisor.commit_if_current(generation_a, fail_finalizer_callback)

    assert generation_a._generation._sealed is False
    generation_b = supervisor.register(
        task_run_id=generation_a.task_run_id,
        adapter_type="scripted_mock",
    )
    assert generation_b is not generation_a
    assert generation_a._generation._lost is True
    assert supervisor.active(generation_a.task_run_id) is generation_b


@pytest.mark.parametrize("exit_mode", ["error", "cancel"])
@pytest.mark.anyio
async def test_async_supervisor_reservation_releases_on_abnormal_exit(
    exit_mode: str,
) -> None:
    supervisor = run_engine_module.RunSupervisor()
    generation_a = supervisor.register(
        task_run_id=f"run:async-reservation-{exit_mode}",
        adapter_type="scripted_mock",
    )
    operation_started = asyncio.Event()
    release_operation = asyncio.Event()

    async def operation() -> None:
        operation_started.set()
        await release_operation.wait()
        raise RuntimeError("injected async reservation failure")

    reserved_operation = asyncio.create_task(
        supervisor.run_async_if_current(generation_a, operation)
    )
    await asyncio.wait_for(operation_started.wait(), timeout=1)
    assert generation_a._generation.is_reserved() is True
    with pytest.raises(RunRegistrationRejected, match="finalizing"):
        supervisor.register(
            task_run_id=generation_a.task_run_id,
            adapter_type="scripted_mock",
        )
    assert (
        supervisor.update_adapter_run_id(
            generation_a.task_run_id,
            f"adapter-run:reserved-{exit_mode}",
            expected=generation_a,
        )
        is None
    )
    assert await supervisor.interrupt(
        generation_a.task_run_id,
        expected=generation_a,
    ) is False
    assert (
        supervisor.unregister(
            generation_a.task_run_id,
            expected=generation_a,
        )
        is None
    )
    if exit_mode == "cancel":
        reserved_operation.cancel()
        with pytest.raises(asyncio.CancelledError):
            await reserved_operation
    else:
        release_operation.set()
        with pytest.raises(RuntimeError, match="injected async reservation failure"):
            await reserved_operation

    assert generation_a._generation.is_reserved() is False
    generation_b = supervisor.register(
        task_run_id=generation_a.task_run_id,
        adapter_type="scripted_mock",
    )
    assert supervisor.active(generation_a.task_run_id) is generation_b


def test_finalizer_reservation_does_not_block_unrelated_task_run_operations() -> None:
    supervisor = run_engine_module.RunSupervisor()
    finalizing_run = supervisor.register(
        task_run_id="run:reserved-finalizer",
        adapter_type="scripted_mock",
    )
    callback_started = Event()
    release_callback = Event()
    finalizer_finished = Event()
    finalizer_errors: list[BaseException] = []

    def block_finalizer() -> None:
        callback_started.set()
        if not release_callback.wait(timeout=2):
            raise AssertionError("The finalizer callback was not released.")
        assert supervisor.seal_reserved_if_current(finalizing_run) is True

    def commit_finalizer() -> None:
        try:
            assert supervisor.commit_if_current(finalizing_run, block_finalizer) == (
                True,
                None,
            )
        except BaseException as exc:
            finalizer_errors.append(exc)
        finally:
            finalizer_finished.set()

    finalizer = Thread(target=commit_finalizer, daemon=True)
    unrelated_finished = Event()
    unrelated_results: list[object] = []

    def use_unrelated_run() -> None:
        try:
            unrelated = supervisor.register(
                task_run_id="run:unrelated-during-finalizer",
                adapter_type="scripted_mock",
            )
            unrelated_results.extend(
                [
                    supervisor.is_current(unrelated),
                    supervisor.active(unrelated.task_run_id) is unrelated,
                    supervisor.unregister(
                        unrelated.task_run_id,
                        expected=unrelated,
                    )
                    is unrelated,
                ]
            )
        finally:
            unrelated_finished.set()

    unrelated = Thread(target=use_unrelated_run, daemon=True)
    try:
        finalizer.start()
        assert callback_started.wait(timeout=2)
        unrelated.start()
        assert unrelated_finished.wait(timeout=0.5)
        assert finalizer_finished.is_set() is False
    finally:
        release_callback.set()
        finalizer.join(timeout=2)
        unrelated.join(timeout=2)

    assert finalizer.is_alive() is False
    assert unrelated.is_alive() is False
    assert finalizer_errors == []
    assert unrelated_results == [True, True, True]


def test_finalizer_reservation_rejects_same_task_run_mutations() -> None:
    adapter_run_id = "adapter-run:reserved-finalizer"
    adapter_interrupts: list[str] = []

    class RecordingAdapter:
        async def interrupt(self, current_adapter_run_id):
            adapter_interrupts.append(current_adapter_run_id)

    supervisor = run_engine_module.RunSupervisor()
    finalizing_run = supervisor.register(
        task_run_id="run:reserved-finalizer-mutations",
        adapter_type="scripted_mock",
        adapter_run_id=adapter_run_id,
        adapter=RecordingAdapter(),
    )
    callback_started = Event()
    release_callback = Event()
    finalizer_errors: list[BaseException] = []

    def block_finalizer() -> None:
        callback_started.set()
        if not release_callback.wait(timeout=2):
            raise AssertionError("The finalizer callback was not released.")
        assert supervisor.seal_reserved_if_current(finalizing_run) is True

    def commit_finalizer() -> None:
        try:
            supervisor.commit_if_current(finalizing_run, block_finalizer)
        except BaseException as exc:
            finalizer_errors.append(exc)

    finalizer = Thread(target=commit_finalizer, daemon=True)
    mutation_finished = Event()
    mutation_results: list[object] = []

    def mutate_same_run() -> None:
        try:
            with pytest.raises(RunRegistrationRejected, match="finalizing"):
                supervisor.register(
                    task_run_id=finalizing_run.task_run_id,
                    adapter_type="scripted_mock",
                )
            mutation_results.append(
                asyncio.run(
                    supervisor.interrupt(
                        finalizing_run.task_run_id,
                        expected=finalizing_run,
                    )
                )
            )
            mutation_results.append(
                supervisor.unregister(
                    finalizing_run.task_run_id,
                    expected=finalizing_run,
                )
            )
        finally:
            mutation_finished.set()

    mutation = Thread(target=mutate_same_run, daemon=True)
    try:
        finalizer.start()
        assert callback_started.wait(timeout=2)
        mutation.start()
        assert mutation_finished.wait(timeout=0.5)
    finally:
        release_callback.set()
        finalizer.join(timeout=2)
        mutation.join(timeout=2)

    assert finalizer.is_alive() is False
    assert mutation.is_alive() is False
    assert finalizer_errors == []
    assert mutation_results == [False, None]
    assert adapter_interrupts == []
    assert supervisor.active(finalizing_run.task_run_id) is finalizing_run
    assert finalizing_run._generation.is_sealed() is True


def test_concurrent_interrupts_call_exact_generation_adapter_once() -> None:
    adapter_run_id = "adapter-run:concurrent-interrupt-once"
    adapter_interrupts: list[str] = []
    interrupt_results: list[bool] = []
    thread_errors: list[BaseException] = []
    start = Barrier(5)
    release_adapter = Event()

    class BlockingInterruptAdapter:
        async def interrupt(self, current_adapter_run_id):
            adapter_interrupts.append(current_adapter_run_id)
            await asyncio.to_thread(release_adapter.wait)

    supervisor = run_engine_module.RunSupervisor()
    supervised_run = supervisor.register(
        task_run_id="run:concurrent-interrupt-once",
        adapter_type="scripted_mock",
        adapter_run_id=adapter_run_id,
        adapter=BlockingInterruptAdapter(),
    )

    def interrupt_from_thread() -> None:
        try:
            start.wait(timeout=2)
            interrupt_results.append(
                asyncio.run(
                    supervisor.interrupt(
                        supervised_run.task_run_id,
                        expected=supervised_run,
                    )
                )
            )
        except BaseException as exc:
            thread_errors.append(exc)

    threads = [Thread(target=interrupt_from_thread) for _ in range(4)]
    for thread in threads:
        thread.start()
    start.wait(timeout=2)
    release_adapter.set()
    for thread in threads:
        thread.join(timeout=2)

    assert all(thread.is_alive() is False for thread in threads)
    assert thread_errors == []
    assert adapter_interrupts == [adapter_run_id]
    assert sorted(interrupt_results) == [False, False, False, True]
    assert supervised_run._generation._lost is True


def test_run_worker_recovers_terminal_holder_before_queue_reconciliation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        worker_id = "worker:terminal-holder-recovery-order"
        run = claim_task_run_for_worker(db, run.id, worker_id=worker_id)
        acquired = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=task.session_id,
            task_run_id=run.id,
            worker_id=worker_id,
            lease_expires_at=run.lease_expires_at,
        )
        assert acquired.lock is not None
        lock_id = acquired.lock.id
        run_id = run.id
        queue_entry = entry_for_task_run(db, run_id)
        assert queue_entry is not None
        queue_entry.state = "running"
        task.status = "completed"
        run.state = "completed"
        run.ended_at = utc_now()
        db.add(queue_entry)
        db.add(task)
        db.add(run)
        db.commit()

        failure_injected = False
        original_flush = db.flush

        def fail_lock_event_staging_once(objects=None) -> None:
            nonlocal failure_injected
            has_lock_event = any(
                isinstance(item, TaskRunEvent)
                and item.event_type == "target_lock.stale_released"
                for item in db.new
            )
            if has_lock_event and not failure_injected:
                failure_injected = True
                raise RuntimeError("injected worker lock event staging failure")
            original_flush(objects)

        monkeypatch.setattr(db, "flush", fail_lock_event_staging_once)
        worker = run_engine_module.RunWorker(worker_id="worker:recovery-order")
        with pytest.raises(
            RuntimeError,
            match="injected worker lock event staging failure",
        ):
            worker.recover_stale_runs(db, reason="worker_order_failure")

        db.expire_all()
        failed_lock = db.get(TargetLock, lock_id)
        failed_queue = entry_for_task_run(db, run_id)
        failed_events = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == run_id)
            .where(
                TaskRunEvent.event_type.in_(
                    {"target_lock.stale_released", "session_queue.advanced"}
                )
            )
            .order_by(TaskRunEvent.sequence)
        ).all()
        failed_state = {
            "lock_state": failed_lock.state,
            "lock_worker_id": failed_lock.worker_id,
            "lock_release_reason": failed_lock.release_reason,
            "queue_state": failed_queue.state,
            "event_types": [item.event_type for item in failed_events],
        }

        summary = worker.recover_stale_runs(db, reason="worker_order_retry")
        durable_lock = db.get(TargetLock, lock_id)
        durable_queue = entry_for_task_run(db, run_id)
        durable_events = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == run_id)
            .where(
                TaskRunEvent.event_type.in_(
                    {"target_lock.stale_released", "session_queue.advanced"}
                )
            )
            .order_by(TaskRunEvent.sequence)
        ).all()
        durable_event_records = [
            (item.event_type, item.payload_json)
            for item in durable_events
        ]

    assert failure_injected is True
    assert failed_state == {
        "lock_state": "held",
        "lock_worker_id": worker_id,
        "lock_release_reason": None,
        "queue_state": "running",
        "event_types": [],
    }
    assert summary["recoveredLockKeys"] == [
        f"target:{DEMO_FRONTEND_TARGET_ID}:write"
    ]
    assert durable_lock.state == "stale_released"
    assert durable_lock.release_reason == "terminal_holder"
    assert durable_queue.state == "completed"
    assert [item[0] for item in durable_event_records] == [
        "target_lock.stale_released",
        "session_queue.advanced",
    ]
    assert all(lock_id not in item[1] for item in durable_event_records)


@pytest.mark.parametrize(
    ("lock_lease_delta", "task_run_lease_delta", "legacy_clock_delta"),
    [
        (timedelta(seconds=-1), timedelta(seconds=1), timedelta(seconds=2)),
        (timedelta(seconds=5), timedelta(seconds=-1), timedelta()),
    ],
)
def test_run_worker_legacy_recovery_excludes_held_target_lock_owner(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    lock_lease_delta: timedelta,
    task_run_lease_delta: timedelta,
    legacy_clock_delta: timedelta,
) -> None:
    recovery_time = utc_now()
    with db_from_override() as db:
        task = db.get(Task, task_id())
        task.plan_json = json.dumps({"targetId": DEMO_FRONTEND_TARGET_ID})
        db.add(task)
        db.commit()
        run = create_task_run(db, task.id)
        worker_id = "worker:held-lock-legacy-exclusion"
        run = claim_task_run_for_worker(db, run.id, worker_id=worker_id)
        acquired = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=task.session_id,
            task_run_id=run.id,
            worker_id=worker_id,
            lease_expires_at=run.lease_expires_at,
        )
        assert acquired.lock is not None
        queue_entry = entry_for_task_run(db, run.id)
        assert queue_entry is not None
        queue_entry.state = "running"
        run.state = "streaming"
        run.last_heartbeat_at = recovery_time
        run.lease_expires_at = recovery_time + task_run_lease_delta
        acquired.lock.lease_expires_at = recovery_time + lock_lease_delta
        db.add(queue_entry)
        db.add(run)
        db.add(acquired.lock)
        db.commit()
        run_id = run.id
        lock_id = acquired.lock.id

        monkeypatch.setattr(target_locks_module, "utc_now", lambda: recovery_time)
        monkeypatch.setattr(
            task_runs_module,
            "utc_now",
            lambda: recovery_time + legacy_clock_delta,
        )
        summary = run_engine_module.RunWorker(
            worker_id="worker:held-lock-recovery"
        ).recover_stale_runs(db, reason="held_lock_legacy_exclusion")

        stored_run = db.get(TaskRun, run_id)
        stored_lock = db.get(TargetLock, lock_id)
        stored_queue = entry_for_task_run(db, run_id)

    assert summary["recoveredLockKeys"] == []
    assert summary["staleRunIds"] == []
    assert stored_run.state == "streaming"
    assert stored_lock.state == "held"
    assert stored_queue.state == "running"


def test_run_worker_recovery_marks_only_expired_active_runs(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        queued = create_task_run(db, task_id())
        active = create_task_run(db, task_id())
        transition_task_run(db, active.id, "streaming")
        active.lease_expires_at = utc_now() - timedelta(minutes=1)
        db.add(active)
        terminal = create_task_run(db, task_id())
        transition_task_run(db, terminal.id, "completed")
        db.commit()
        queued_id = queued.id
        active_id = active.id
        terminal_id = terminal.id

        summary = run_engine_module.RunWorker(worker_id="worker:test").recover_stale_runs(
            db,
            reason="worker_startup_test",
        )

        assert summary["workerId"] == "worker:test"
        assert summary["staleRunIds"] == [active_id]
        assert summary["staleRunCount"] == 1
        assert db.get(TaskRun, queued_id).state == "queued"
        assert db.get(TaskRun, active_id).state == "failed"
        assert db.get(TaskRun, active_id).error_code == "TASK_RUN_STALE"
        assert db.get(TaskRun, active_id).stale_reason == "worker_startup_test"
        assert db.get(TaskRun, terminal_id).state == "completed"


def test_retry_blocks_external_target_dirty_worktree_outside_checkpoint(
    client: TestClient,
    tmp_path: Path,
) -> None:
    external_root = tmp_path / "external-retry-app"
    (external_root / "src").mkdir(parents=True)
    (external_root / "src" / "App.tsx").write_text("export default function App() {}\n")
    subprocess.run(["git", "init"], cwd=external_root, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=external_root,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=external_root,
        check=True,
    )
    subprocess.run(["git", "add", "src/App.tsx"], cwd=external_root, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=external_root, check=True)

    with db_from_override() as db:
        workspace = db.exec(select(Workspace).where(Workspace.name == "AgentHub Demo")).one()
        register_external_project_target(
            db,
            workspace,
            ExternalWorkspaceRegistration(
                target_id="external-retry-app",
                name="External Retry App",
                root_path=str(external_root),
                project_type="vite-react",
                allowed_paths=["src"],
            ),
        )
        task = db.get(Task, task_id())
        task.plan_json = json.dumps(
            {
                "targetId": "external-retry-app",
                "safeTarget": "src",
                "files": ["src/App.tsx"],
            },
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()
        original = create_task_run(db, task.id)
        transition_task_run(
            db,
            original.id,
            "failed",
            error_code="CODEX_TEST_FAILURE",
            error_message="Codex failed before retry.",
        )
        original_id = original.id
        original_task_id = original.task_id

    (external_root / "README.md").write_text("local notes\n")

    response = client.post(f"/task-runs/{original_id}/retry")

    assert response.status_code == 400
    assert "Unsafe retry blocked" in response.json()["detail"]

    with db_from_override() as db:
        runs = db.exec(select(TaskRun).where(TaskRun.task_id == original_task_id)).all()
        assert len(runs) == 1


def test_retry_with_scripted_mock_fallback_after_codex_failure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scheduled: list[str] = []

    def fake_schedule_task_run_execution(
        background_tasks,
    ) -> None:
        scheduled.append("worker")

    monkeypatch.setattr(
        main_module,
        "schedule_task_run_execution",
        fake_schedule_task_run_execution,
    )

    original = client.post(f"/tasks/{task_id()}/runs").json()
    scheduled_after_original = len(scheduled)

    with db_from_override() as db:
        transition_task_run(
            db,
            original["id"],
            "failed",
            payload={"errorCode": "CODEX_USAGE_LIMIT"},
            error_code="CODEX_USAGE_LIMIT",
            error_message="Codex usage limit reached.",
        )

    response = client.post(f"/task-runs/{original['id']}/retry-with-fallback")

    assert response.status_code == 201
    fallback = response.json()
    assert fallback["id"] != original["id"]
    assert fallback["adapterType"] == "scripted_mock"
    assert fallback["state"] in {"queued", "failed"}
    assert fallback["metricsJson"]["fallbackFromRunId"] == original["id"]
    assert len(scheduled) == scheduled_after_original + 1

    task_response = client.get(f"/sessions/{fallback['sessionId']}/tasks")
    task = task_response.json()[0]
    assert [run["id"] for run in task["taskRuns"]] == [original["id"], fallback["id"]]


def test_force_codex_failure_queues_visible_run_through_scheduler(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scheduled: list[str] = []

    def fake_schedule_task_run_execution(
        background_tasks,
    ) -> None:
        scheduled.append("worker")

    monkeypatch.setattr(
        main_module,
        "schedule_task_run_execution",
        fake_schedule_task_run_execution,
    )

    response = client.post(f"/tasks/{task_id()}/runs/force-codex-failure")

    assert response.status_code == 201
    run = response.json()
    assert run["adapterType"] == "codex"
    assert run["state"] == "queued"
    assert run["metricsJson"]["forceFailure"] is True
    assert scheduled == ["worker"]

    task_response = client.get(f"/sessions/{run['sessionId']}/tasks")
    task = task_response.json()[0]
    assert task["status"] == "running"
    assert [task_run["id"] for task_run in task["taskRuns"]] == [run["id"]]


def test_retry_with_fallback_requires_failed_codex_run(client: TestClient) -> None:
    run = client.post(f"/tasks/{task_id()}/runs").json()

    response = client.post(f"/task-runs/{run['id']}/retry-with-fallback")

    assert response.status_code == 400
    assert "failed or interrupted Codex run" in response.json()["detail"]


def test_approval_request_is_visible_and_approve_deny_endpoints_work(
    client: TestClient,
) -> None:
    with db_from_override() as db:
        task = db.get(Task, task_id())
        approved_run = create_task_run(db, task.id)
        request_task_run_approval(
            db,
            approved_run.id,
            ApprovalRequestPayload(
                approvalType="product_confirmation",
                reason="Deploy requires confirmation.",
                requestedAction="deploy preview",
                riskLevel="medium",
            ),
        )
        denied_run = create_task_run(db, task.id)
        request_task_run_approval(
            db,
            denied_run.id,
            ApprovalRequestPayload(
                approvalType="security_approval",
                reason="Network access is disabled.",
                requestedAction="network access",
                riskLevel="high",
            ),
        )
        session_id = task.session_id
        approved_run_id = approved_run.id
        denied_run_id = denied_run.id

    task_response = client.get(f"/sessions/{session_id}/tasks")
    assert task_response.status_code == 200
    runs = {
        run["id"]: run
        for task_payload in task_response.json()
        for run in task_payload["taskRuns"]
    }
    assert runs[approved_run_id]["state"] == "waiting_approval"
    assert runs[approved_run_id]["approvalRequest"] == {
        "approvalType": "product_confirmation",
        "reason": "Deploy requires confirmation.",
        "requestedAction": "deploy preview",
        "riskLevel": "medium",
        "command": None,
        "path": None,
        "expiresAt": None,
    }

    approved_response = client.post(f"/task-runs/{approved_run_id}/approve")
    denied_response = client.post(
        f"/task-runs/{denied_run_id}/deny",
        json={"reason": "User denied network access."},
    )

    assert approved_response.status_code == 200
    assert approved_response.json()["state"] == "queued"
    assert approved_response.json()["approvalRequest"] is None
    assert denied_response.status_code == 200
    assert denied_response.json()["state"] == "failed"
    assert denied_response.json()["errorCode"] == "APPROVAL_DENIED"
    assert denied_response.json()["errorMessage"] == "User denied network access."


def test_direct_ui_start_dispatch_creates_queued_run_with_adapter_type(
    client: TestClient,
) -> None:
    response = client.post(f"/tasks/{task_id()}/runs")

    assert response.status_code == 201
    run = response.json()
    assert run["state"] == "queued"
    assert run["adapterType"] == "codex"
    assert run.get("id")

    with db_from_override() as db:
        task = db.get(Task, run["taskId"])
        assert task is not None
        assert task.status == "running"


def test_direct_ui_start_background_execution_persists_events(
    client: TestClient,
) -> None:
    """Prove background adapter dispatch runs and persists TaskRunEvents after Start."""
    import app.db as db_module

    with db_from_override() as db:
        test_engine = db.get_bind()

    original_engine = db_module.engine
    db_module.engine = test_engine
    try:
        response = client.post(f"/tasks/{task_id()}/runs")
    finally:
        db_module.engine = original_engine

    assert response.status_code == 201
    run = response.json()
    assert run["state"] == "queued"
    assert run["adapterType"] == "codex"

    with db_from_override() as db:
        events = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == run["id"])
            .order_by(TaskRunEvent.sequence)
        ).all()
        stored = db.get(TaskRun, run["id"])

    # The endpoint creates a "queued" event (sequence 1).
    # The background task invokes CodexAdapter:
    #   - If Codex CLI is installed and worktree exists: streaming/completed events
    #   - If Codex CLI is not installed or worktree missing: failed with CODEX_* error
    assert len(events) >= 2, (
        f"Background execution did not persist events beyond queued: {len(events)} events"
    )
    assert stored.state in {"failed", "streaming", "completed"}, (
        f"Background execution did not transition state past queued: {stored.state}"
    )

    # At least one event after queued must be from execution or its pre-adapter gate.
    later_events = events[1:]
    adapter_event_types = {e.event_type for e in later_events}
    assert adapter_event_types & {"error", "task.state", "completed", "message.delta"}, (
        f"No adapter lifecycle events found after queued: {adapter_event_types}"
    )

    if stored.state == "failed":
        assert stored.error_code is not None, "Failed TaskRun must have error_code"
        assert (
            "CODEX_" in (stored.error_code or "")
            or stored.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
        ), (
            f"Expected CODEX_* or scope-gate error code, got: {stored.error_code}"
        )
        assert stored.error_message is not None, "Failed TaskRun must have error_message"


def test_direct_ui_start_scripted_mock_background_execution_persists_events(
    client: TestClient,
) -> None:
    """Prove ScriptedMockAdapter background dispatch persists events after Start."""
    import app.db as db_module

    with db_from_override() as db:
        test_engine = db.get_bind()
        qa_agent_id = db.exec(select(Agent).where(Agent.role == "qa")).one().id
        session_id = db.exec(select(Task).where(Task.title == "Build login page")).one().session_id

    qa_task = Task(
        session_id=session_id,
        title="Review login page",
        intent_type="review",
        status="pending",
        assigned_agent_id=qa_agent_id,
    )
    with db_from_override() as db:
        db.add(qa_task)
        db.commit()
        qa_task_id = qa_task.id

    original_engine = db_module.engine
    db_module.engine = test_engine
    try:
        response = client.post(f"/tasks/{qa_task_id}/runs")
    finally:
        db_module.engine = original_engine

    assert response.status_code == 201
    run = response.json()
    assert run["adapterType"] == "scripted_mock"

    with db_from_override() as db:
        events = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == run["id"])
            .order_by(TaskRunEvent.sequence)
        ).all()
        stored = db.get(TaskRun, run["id"])

    assert len(events) >= 2, (
        f"Background execution did not persist events: {len(events)} events"
    )
    assert stored.state != "queued", (
        f"Background execution did not transition past queued: {stored.state}"
    )
