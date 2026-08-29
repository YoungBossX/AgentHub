import asyncio
import json
from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

import app.main as main_module
import app.run_engine as run_engine_module
import app.task_runs as task_runs_module
from app.models import (
    Agent,
    Artifact,
    Deployment,
    Preview,
    PreviewDeployJob,
    Session,
    SessionQueueEntry,
    Task,
    TaskRun,
    TaskRunEvent,
    Workspace,
)
from app.preview_deploy_jobs import (
    enqueue_deploy_job,
    enqueue_preview_job,
    run_deploy_job,
    run_preview_job,
)
from app.task_run_scope import (
    SCOPE_SNAPSHOT_SCHEMA_VERSION,
    SCOPE_VALIDATION_SCHEMA_VERSION,
    TaskRunScopeError,
)
from app.target_registry import (
    EFFECTIVE_WRITE_SCOPE_SCHEMA_VERSION,
    effective_write_scope_identity,
    get_target,
)


@pytest.fixture
def db() -> Iterator[DbSession]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as session:
        yield session


def _scope_policy_binding(db: DbSession, task_run: TaskRun) -> dict[str, str]:
    task = db.get(Task, task_run.task_id)
    session = db.get(Session, task.session_id)
    return {
        "workspaceId": session.workspace_id,
        "scopePolicySchemaVersion": EFFECTIVE_WRITE_SCOPE_SCHEMA_VERSION,
        "scopePolicyIdentity": effective_write_scope_identity(
            get_target("demo-frontend")
        ),
    }


@pytest.fixture
def legacy_artifact_source(db: DbSession) -> tuple[TaskRun, Preview]:
    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="Legacy artifact scope session",
        bound_branch="main",
        worktree_path=".worktrees/legacy-artifact-scope",
    )
    agent = Agent(
        name="Frontend Agent",
        role="frontend",
        adapter_type="scripted_mock",
        provider="local",
    )
    task = Task(
        session_id=session.id,
        title="Legacy completed frontend task",
        intent_type="frontend_change",
        assigned_agent_id=agent.id,
        plan_json=json.dumps({"targetId": "demo-frontend"}),
    )
    task_run = TaskRun(
        task_id=task.id,
        agent_id=agent.id,
        state="completed",
        worktree_path=session.worktree_path,
        base_ref="legacy-base",
        head_ref="legacy-head",
        metrics_json="{}",
    )
    preview_artifact = Artifact(
        task_run_id=task_run.id,
        artifact_type="preview",
        title="Legacy preview",
        status="ready",
    )
    preview = Preview(
        artifact_id=preview_artifact.id,
        port=4317,
        url="http://127.0.0.1:4317",
        command="pnpm dev --host 127.0.0.1 --port 4317",
        process_id=4242,
        health_status="healthy",
    )
    db.add(workspace)
    db.add(session)
    db.add(agent)
    db.add(task)
    db.add(task_run)
    db.add(preview_artifact)
    db.add(preview)
    db.commit()
    db.refresh(task_run)
    db.refresh(preview)
    return task_run, preview


def _add_launched_queue_entry(
    db: DbSession,
    task_run: TaskRun,
    *,
    access_mode: str,
    task_id: str | None = None,
) -> SessionQueueEntry:
    task = db.get(Task, task_run.task_id)
    assert task is not None
    target_id = "demo-frontend"
    entry = SessionQueueEntry(
        session_id=task.session_id,
        task_id=task_id or task.id,
        task_run_id=task_run.id,
        access_mode=access_mode,
        target_id=target_id,
        target_lock_key=(
            f"target:{target_id}:write" if access_mode == "write" else None
        ),
        position=1,
        state="running",
        started_at=task_run.created_at,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@pytest.mark.parametrize("artifact_kind", ("diff", "review", "preview", "deploy"))
def test_manual_artifact_routes_reject_write_run_reclassified_readonly(
    db: DbSession,
    legacy_artifact_source: tuple[TaskRun, Preview],
    monkeypatch: pytest.MonkeyPatch,
    artifact_kind: str,
) -> None:
    task_run, preview = legacy_artifact_source
    _add_launched_queue_entry(db, task_run, access_mode="write")
    task = db.get(Task, task_run.task_id)
    task.intent_type = "review"
    task.plan_json = json.dumps(
        {"targetId": "demo-frontend", "readOnly": True},
        separators=(",", ":"),
    )
    db.add(task)
    db.commit()
    artifact_count = len(db.exec(select(Artifact)).all())
    preview_count = len(db.exec(select(Preview)).all())

    def unexpected(*args, **kwargs):
        pytest.fail("scope guard did not stop manual artifact production")

    if artifact_kind == "diff":
        monkeypatch.setattr(main_module, "collect_task_run_diff", unexpected)
        invoke = lambda: main_module.collect_diff_for_task_run(task_run.id, db)
    elif artifact_kind == "review":
        monkeypatch.setattr(
            main_module, "create_scripted_review_for_task_run", unexpected
        )
        invoke = lambda: main_module.create_review_for_task_run(task_run.id, db)
    elif artifact_kind == "preview":
        class UnexpectedPreviewService:
            start_task_run_preview = unexpected

        invoke = lambda: main_module.start_preview_for_task_run(
            task_run.id, db, UnexpectedPreviewService()
        )
    else:
        class UnexpectedDeployService:
            create_deployment = unexpected

        invoke = lambda: main_module.create_mock_deployment_for_preview(
            preview.id,
            main_module.DeploymentCreateRequest(),
            db,
            UnexpectedDeployService(),
        )

    for _attempt in range(2):
        with pytest.raises(HTTPException) as exc_info:
            invoke()

    assert exc_info.value.status_code == 400
    assert "TASK_RUN_SCOPE_UNVERIFIABLE" in str(exc_info.value.detail)
    assert len(db.exec(select(Artifact)).all()) == artifact_count
    assert len(db.exec(select(Preview)).all()) == preview_count
    assert db.exec(select(Deployment)).all() == []
    refusal_events = db.exec(
        select(TaskRunEvent)
        .where(TaskRunEvent.task_run_id == task_run.id)
        .where(TaskRunEvent.event_type == "task.artifact_scope_refused")
        .order_by(TaskRunEvent.sequence)
    ).all()
    assert len(refusal_events) == 1
    assert refusal_events[0].sequence == 1
    payload = json.loads(refusal_events[0].payload_json)
    assert payload["result"] == "unverifiable"
    assert payload["errorCode"] == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert payload["taskRunId"] == task_run.id


def test_failed_scope_marker_refusal_event_keeps_only_safe_aggregate_evidence(
    db: DbSession,
    legacy_artifact_source: tuple[TaskRun, Preview],
) -> None:
    task_run, _preview = legacy_artifact_source
    baseline_timestamp = "2026-07-18T08:00:00+00:00"
    decision_timestamp = "2026-07-18T08:00:01+00:00"
    raw_control_digest = "d" * 64
    raw_fingerprint = "f" * 64
    policy_binding = _scope_policy_binding(db, task_run)
    task_run.metrics_json = json.dumps(
        {
            "adapterType": "scripted_mock",
            "preRunCheckpoint": {
                "targetId": "demo-frontend",
                "scopeBaseline": {
                    "schema_version": SCOPE_SNAPSHOT_SCHEMA_VERSION,
                    "available": True,
                    "reason": None,
                    "entries": [
                        {
                            "path": "apps/demo/src/App.tsx",
                            "status": "tracked-present",
                            "fingerprint": raw_fingerprint,
                        }
                    ],
                    "protected_control_digest": raw_control_digest,
                    "protected_categories": [".git", "secrets"],
                    "protected_entry_count": 2,
                },
                "scopeBaselineTaskRunId": task_run.id,
                "scopeBaselineIdentity": "baseline-safe-id",
                "scopeBaselineCapturedAt": baseline_timestamp,
                "scopeExecutionAttemptId": "attempt-safe-id",
                "scopeWorkspaceId": policy_binding["workspaceId"],
                "scopePolicySchemaVersion": policy_binding[
                    "scopePolicySchemaVersion"
                ],
                "scopePolicyIdentity": policy_binding["scopePolicyIdentity"],
                "collectorHostPath": "Z:\\private-host\\scope-fixture\\.git\\private",
                "secretValue": "sk-secret-value",
            },
            "taskRunScopeDecision": {
                "schemaVersion": SCOPE_VALIDATION_SCHEMA_VERSION,
                "taskRunId": task_run.id,
                "targetId": "demo-frontend",
                **policy_binding,
                "baselineSchemaVersion": SCOPE_SNAPSHOT_SCHEMA_VERSION,
                "baselineIdentity": "baseline-safe-id",
                "baselineCapturedAt": baseline_timestamp,
                "executionAttemptId": "attempt-safe-id",
                "status": "rejected",
                "changedPathCount": 2,
                "timestamp": decision_timestamp,
                "errorCode": "TASK_RUN_SCOPE_VIOLATION",
                "reason": "The task run changed protected control state.",
            },
        },
        separators=(",", ":"),
    )
    db.add(task_run)
    db.commit()

    for _attempt in range(2):
        with pytest.raises(HTTPException) as exc_info:
            main_module._require_artifact_scope_passed(db, task_run.id)

    assert exc_info.value.status_code == 400
    assert "TASK_RUN_SCOPE_VIOLATION" in str(exc_info.value.detail)
    events = db.exec(
        select(TaskRunEvent)
        .where(TaskRunEvent.task_run_id == task_run.id)
        .where(TaskRunEvent.event_type == "task.artifact_scope_refused")
    ).all()
    assert len(events) == 1
    payload = json.loads(events[0].payload_json)
    assert payload == {
        "result": "violation",
        "errorCode": "TASK_RUN_SCOPE_VIOLATION",
        "taskRunId": task_run.id,
        "targetId": "demo-frontend",
        "snapshotVersion": SCOPE_SNAPSHOT_SCHEMA_VERSION,
        "changedPathCount": 2,
        "protectedEntryCount": 2,
        "protectedCategories": [".git", "secrets"],
        "reasonCategory": "scope_violation",
    }
    exposed = json.dumps(payload, sort_keys=True)
    assert "X:" not in exposed
    assert "C:" not in exposed
    assert "sk-secret-value" not in exposed
    assert raw_fingerprint not in exposed
    assert raw_control_digest not in exposed
    assert policy_binding["scopePolicyIdentity"] not in exposed
    assert "fingerprint" not in exposed.lower()
    assert "protectedcontroldigest" not in exposed.lower()


def test_real_scope_pass_marker_allows_manual_preview_without_refusal_event(
    db: DbSession,
    legacy_artifact_source: tuple[TaskRun, Preview],
) -> None:
    task_run, preview = legacy_artifact_source
    queue_entry = _add_launched_queue_entry(db, task_run, access_mode="write")
    task = db.get(Task, task_run.task_id)
    task_run.runner_id = "runner:scope-pass-fixture"
    task_run.adapter_run_id = "adapter-run:scope-pass-fixture"
    task_run.started_at = task_run.created_at
    baseline_timestamp = "2026-07-18T08:00:00+00:00"
    decision_timestamp = "2026-07-18T08:00:01+00:00"
    policy_binding = _scope_policy_binding(db, task_run)
    decision = {
        "schemaVersion": SCOPE_VALIDATION_SCHEMA_VERSION,
        "taskRunId": task_run.id,
        "targetId": "demo-frontend",
        **policy_binding,
        "baselineSchemaVersion": SCOPE_SNAPSHOT_SCHEMA_VERSION,
        "baselineIdentity": "baseline-safe-id",
        "baselineCapturedAt": baseline_timestamp,
        "executionAttemptId": "attempt-safe-id",
        "status": "passed",
        "changedPathCount": 0,
        "timestamp": decision_timestamp,
        "errorCode": None,
        "reason": None,
    }
    task_run.metrics_json = json.dumps(
        {
            "adapterType": "scripted_mock",
            "preRunCheckpoint": {
                "targetId": "demo-frontend",
                "scopeBaseline": {
                    "schema_version": SCOPE_SNAPSHOT_SCHEMA_VERSION,
                    "available": True,
                    "reason": None,
                    "entries": [],
                    "protected_control_digest": "a" * 64,
                    "protected_categories": [],
                    "protected_entry_count": 0,
                },
                "scopeBaselineTaskRunId": task_run.id,
                "scopeBaselineIdentity": "baseline-safe-id",
                "scopeBaselineCapturedAt": baseline_timestamp,
                "scopeExecutionAttemptId": "attempt-safe-id",
                "scopeWorkspaceId": policy_binding["workspaceId"],
                "scopePolicySchemaVersion": policy_binding[
                    "scopePolicySchemaVersion"
                ],
                "scopePolicyIdentity": policy_binding["scopePolicyIdentity"],
            },
            "taskRunScopeDecision": decision,
                "taskRunScopeGuard": {
                key: decision[key]
                for key in (
                    "schemaVersion",
                    "taskRunId",
                    "targetId",
                    "workspaceId",
                    "scopePolicySchemaVersion",
                    "scopePolicyIdentity",
                    "baselineSchemaVersion",
                    "baselineIdentity",
                    "baselineCapturedAt",
                    "executionAttemptId",
                    "status",
                    "changedPathCount",
                        "timestamp",
                    )
                },
                "taskRunExecutionAccessBinding": {
                    "taskRunId": task_run.id,
                    "taskId": task_run.task_id,
                    "sessionId": task.session_id,
                    "queueEntryId": queue_entry.id,
                    "accessMode": "write",
                    "runnerId": task_run.runner_id,
                    "executionAttemptId": "attempt-safe-id",
                },
            },
        separators=(",", ":"),
    )
    db.add(task_run)
    db.commit()

    class ExistingPreviewService:
        def start_task_run_preview(self, db, task_run_id):
            return main_module.StoredPreviewArtifact(
                id=preview.id,
                artifact_id=preview.artifact_id,
                task_run_id=task_run.id,
                artifact_type="preview",
                title="Legacy preview",
                status="ready",
                port=preview.port,
                url=preview.url,
                command=preview.command,
                process_id=preview.process_id,
                health_status=preview.health_status,
                status_reason=preview.status_reason,
                expires_at=preview.expires_at,
                last_checked_at=preview.last_checked_at,
            )

    response = main_module.start_preview_for_task_run(
        task_run.id,
        db,
        ExistingPreviewService(),
    )
    refusal_events = db.exec(
        select(TaskRunEvent)
        .where(TaskRunEvent.task_run_id == task_run.id)
        .where(TaskRunEvent.event_type == "task.artifact_scope_refused")
    ).all()

    assert response.id == preview.id
    assert task_runs_module.require_task_run_artifact_scope_passed(
        db,
        task_run.id,
    ).status == "passed"
    assert refusal_events == []


def test_legacy_automatic_finalizer_rejects_before_artifacts_or_side_effects(
    db: DbSession,
    legacy_artifact_source: tuple[TaskRun, Preview],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task_run, _ = legacy_artifact_source

    def unexpected(*args, **kwargs):
        pytest.fail("scope guard did not stop automatic artifact production")

    async def unexpected_async(*args, **kwargs):
        pytest.fail("scope guard did not stop downstream scheduling")

    monkeypatch.setattr(run_engine_module, "collect_task_run_diff", unexpected)
    monkeypatch.setattr(
        run_engine_module, "create_scripted_review_for_task_run", unexpected
    )
    monkeypatch.setattr(
        run_engine_module, "refresh_session_ledger_for_task_run", unexpected
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

    with pytest.raises(TaskRunScopeError) as exc_info:
        asyncio.run(run_engine_module.finalize_completed_task_run(db, task_run))

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


def test_legacy_run_cannot_enqueue_preview_or_deploy_jobs(
    db: DbSession,
    legacy_artifact_source: tuple[TaskRun, Preview],
) -> None:
    task_run, preview = legacy_artifact_source

    with pytest.raises(TaskRunScopeError) as preview_error:
        enqueue_preview_job(db, task_run)
    with pytest.raises(TaskRunScopeError) as deploy_error:
        enqueue_deploy_job(db, task_run.id, preview.id)

    assert preview_error.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert deploy_error.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert db.exec(select(PreviewDeployJob)).all() == []


def test_scope_passed_run_can_enqueue_preview_and_deploy_jobs(
    db: DbSession,
    legacy_artifact_source: tuple[TaskRun, Preview],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.preview_deploy_jobs as jobs_module

    task_run, preview = legacy_artifact_source
    monkeypatch.setattr(
        jobs_module,
        "require_task_run_artifact_scope_passed",
        lambda db, task_run_id: None,
    )

    preview_job = enqueue_preview_job(db, task_run)
    deploy_job = enqueue_deploy_job(db, task_run.id, preview.id)

    assert preview_job is not None
    assert preview_job.state == "queued"
    assert deploy_job.state == "queued"


def test_deploy_job_rejects_preview_from_different_task_run(
    db: DbSession,
    legacy_artifact_source: tuple[TaskRun, Preview],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.preview_deploy_jobs as jobs_module

    preview_task_run, preview = legacy_artifact_source
    claimed_source = TaskRun(
        task_id=preview_task_run.task_id,
        agent_id=preview_task_run.agent_id,
        state="completed",
        worktree_path=preview_task_run.worktree_path,
    )
    db.add(claimed_source)
    db.commit()
    monkeypatch.setattr(
        jobs_module,
        "require_task_run_artifact_scope_passed",
        lambda db, task_run_id: None,
    )

    with pytest.raises(TaskRunScopeError) as exc_info:
        enqueue_deploy_job(db, claimed_source.id, preview.id)

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert db.exec(select(PreviewDeployJob)).all() == []

    task = db.get(Task, claimed_source.task_id)
    mismatched_job = PreviewDeployJob(
        session_id=task.session_id,
        source_task_run_id=claimed_source.id,
        job_type="deploy",
        evidence_json=json.dumps({"sourcePreviewId": preview.id}),
    )
    db.add(mismatched_job)
    db.commit()

    class UnexpectedDeployService:
        def create_mock_deployment(self, *args, **kwargs):
            pytest.fail("mismatched deploy job reached deploy service")

    result = run_deploy_job(
        db, mismatched_job, deploy_service=UnexpectedDeployService()
    )

    assert result.state == "failed"
    assert result.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert db.exec(select(Deployment)).all() == []


def test_write_adapter_completion_cannot_be_reclassified_readonly(
    db: DbSession,
    legacy_artifact_source: tuple[TaskRun, Preview],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task_run, _ = legacy_artifact_source
    _add_launched_queue_entry(db, task_run, access_mode="write")
    task = db.get(Task, task_run.task_id)
    task.intent_type = "review"
    task.plan_json = json.dumps(
        {"targetId": "demo-frontend", "readOnly": True},
        separators=(",", ":"),
    )
    task_run.state = "collecting_diff"
    db.add(task)
    db.add(task_run)
    db.commit()
    calls: list[str] = []

    monkeypatch.setattr(
        run_engine_module,
        "collect_task_run_diff",
        lambda db, task_run_id: calls.append("diff"),
    )
    monkeypatch.setattr(
        run_engine_module,
        "create_scripted_review_for_task_run",
        lambda db, task_run_id: calls.append("review"),
    )
    monkeypatch.setattr(
        run_engine_module,
        "refresh_session_ledger_for_task_run",
        lambda db, task_run_id: calls.append("ledger"),
    )
    monkeypatch.setattr(
        run_engine_module,
        "_complete_ready_pipeline_review_tasks",
        lambda db, task_id: calls.append("review-tasks") or [],
    )
    monkeypatch.setattr(
        run_engine_module,
        "_maybe_auto_preview_and_mock_deploy",
        lambda db, task_run: calls.append("preview"),
    )

    async def downstream(db, task_id):
        calls.append("downstream")
        return None

    monkeypatch.setattr(
        run_engine_module, "_auto_start_next_pipeline_task", downstream
    )

    result = asyncio.run(
        run_engine_module.finalize_adapter_completed_task_run(db, task_run)
    )

    db.refresh(task_run)
    assert result.state == "failed"
    assert task_run.state == "failed"
    assert task_run.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert calls == []


def test_synthetic_readonly_launch_evidence_fails_closed(
    db: DbSession,
    legacy_artifact_source: tuple[TaskRun, Preview],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task_run, _ = legacy_artifact_source
    task = db.get(Task, task_run.task_id)
    task.intent_type = "review"
    task.plan_json = json.dumps(
        {"targetId": "demo-frontend", "readOnly": True},
        separators=(",", ":"),
    )
    task_run.state = "collecting_diff"
    db.add(task)
    db.add(task_run)
    db.commit()
    _add_launched_queue_entry(db, task_run, access_mode="readonly")
    calls: list[str] = []

    monkeypatch.setattr(
        run_engine_module,
        "collect_task_run_diff",
        lambda db, task_run_id: calls.append("diff"),
    )
    monkeypatch.setattr(
        run_engine_module,
        "create_scripted_review_for_task_run",
        lambda db, task_run_id: calls.append("review"),
    )
    monkeypatch.setattr(
        run_engine_module,
        "refresh_session_ledger_for_task_run",
        lambda db, task_run_id: calls.append("ledger"),
    )
    monkeypatch.setattr(
        run_engine_module,
        "_complete_ready_pipeline_review_tasks",
        lambda db, task_id: calls.append("review-tasks") or [],
    )
    monkeypatch.setattr(
        run_engine_module,
        "_maybe_auto_preview_and_mock_deploy",
        lambda db, task_run: calls.append("preview"),
    )

    async def downstream(db, task_id):
        calls.append("downstream")
        return None

    monkeypatch.setattr(
        run_engine_module, "_auto_start_next_pipeline_task", downstream
    )

    result = asyncio.run(
        run_engine_module.finalize_adapter_completed_task_run(db, task_run)
    )

    db.refresh(task_run)
    assert result.state == "failed"
    assert task_run.state == "failed"
    assert task_run.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert calls == []


@pytest.mark.parametrize(
    "evidence_kind",
    ("missing_queue", "queue_task_mismatch", "write_checkpoint_conflict"),
)
def test_readonly_scope_bypass_requires_bound_launch_evidence(
    db: DbSession,
    legacy_artifact_source: tuple[TaskRun, Preview],
    evidence_kind: str,
) -> None:
    task_run, _ = legacy_artifact_source
    task = db.get(Task, task_run.task_id)
    task.intent_type = "review"
    task.plan_json = json.dumps(
        {"targetId": "demo-frontend", "readOnly": True},
        separators=(",", ":"),
    )
    db.add(task)
    db.commit()

    if evidence_kind == "queue_task_mismatch":
        other_task = Task(
            session_id=task.session_id,
            title="Different readonly task",
            intent_type="review",
            assigned_agent_id=task.assigned_agent_id,
            plan_json=task.plan_json,
        )
        db.add(other_task)
        db.commit()
        _add_launched_queue_entry(
            db,
            task_run,
            access_mode="readonly",
            task_id=other_task.id,
        )
    elif evidence_kind == "write_checkpoint_conflict":
        _add_launched_queue_entry(db, task_run, access_mode="readonly")
        task_run.metrics_json = json.dumps(
            {
                "preRunCheckpoint": {
                    "scopeExecutionAttemptId": "write-attempt-evidence",
                    "scopeBaselineTaskRunId": task_run.id,
                }
            },
            separators=(",", ":"),
        )
        db.add(task_run)
        db.commit()

    with pytest.raises(TaskRunScopeError) as exc_info:
        task_runs_module.require_task_run_artifact_scope_passed(db, task_run.id)

    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


def test_completion_and_artifact_guard_share_execution_access_mode_classifier() -> None:
    assert (
        run_engine_module.require_task_run_execution_access_mode
        is task_runs_module.require_task_run_execution_access_mode
    )


def test_legacy_queued_jobs_fail_scope_before_services_run(
    db: DbSession,
    legacy_artifact_source: tuple[TaskRun, Preview],
) -> None:
    task_run, preview = legacy_artifact_source
    task = db.get(Task, task_run.task_id)
    preview_job = PreviewDeployJob(
        session_id=task.session_id,
        source_task_run_id=task_run.id,
        job_type="preview",
    )
    deploy_job = PreviewDeployJob(
        session_id=task.session_id,
        source_task_run_id=task_run.id,
        job_type="deploy",
        evidence_json=json.dumps({"sourcePreviewId": preview.id}),
    )
    db.add(preview_job)
    db.add(deploy_job)
    db.commit()

    class UnexpectedPreviewService:
        def start_task_run_preview(self, *args, **kwargs):
            pytest.fail("legacy preview job reached preview service")

    class UnexpectedDeployService:
        def create_mock_deployment(self, *args, **kwargs):
            pytest.fail("legacy deploy job reached deploy service")

    preview_result = run_preview_job(
        db, preview_job, preview_service=UnexpectedPreviewService()
    )
    deploy_result = run_deploy_job(
        db, deploy_job, deploy_service=UnexpectedDeployService()
    )

    assert preview_result.state == "failed"
    assert preview_result.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert deploy_result.state == "failed"
    assert deploy_result.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


def test_completed_preview_and_deploy_jobs_are_not_replayed(
    db: DbSession,
    legacy_artifact_source: tuple[TaskRun, Preview],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.preview_deploy_jobs as jobs_module

    task_run, preview = legacy_artifact_source
    task = db.get(Task, task_run.task_id)
    monkeypatch.setattr(
        jobs_module,
        "require_task_run_artifact_scope_passed",
        lambda db, task_run_id: None,
    )
    preview_job = PreviewDeployJob(
        session_id=task.session_id,
        source_task_run_id=task_run.id,
        job_type="preview",
    )
    deploy_job = PreviewDeployJob(
        session_id=task.session_id,
        source_task_run_id=task_run.id,
        job_type="deploy",
        evidence_json=json.dumps({"sourcePreviewId": preview.id}),
    )
    db.add(preview_job)
    db.add(deploy_job)
    db.commit()
    calls = {"preview": 0, "deploy": 0}

    class PreviewService:
        def start_task_run_preview(self, *args, **kwargs):
            calls["preview"] += 1
            return SimpleNamespace(
                id="preview-result",
                artifact_id="preview-artifact-result",
                url="http://127.0.0.1:4318",
                health_status="healthy",
                status_reason=None,
            )

    class DeployService:
        def create_mock_deployment(self, *args, **kwargs):
            calls["deploy"] += 1
            return SimpleNamespace(
                id="deployment-result",
                provider="mock",
                status="ready",
            )

    run_preview_job(db, preview_job, preview_service=PreviewService())
    run_preview_job(db, preview_job, preview_service=PreviewService())
    run_deploy_job(db, deploy_job, deploy_service=DeployService())
    run_deploy_job(db, deploy_job, deploy_service=DeployService())

    assert calls == {"preview": 1, "deploy": 1}


def test_orphaned_preview_job_fails_scope_without_calling_service(
    db: DbSession,
    legacy_artifact_source: tuple[TaskRun, Preview],
) -> None:
    task_run, _ = legacy_artifact_source
    task = db.get(Task, task_run.task_id)
    job = PreviewDeployJob(
        session_id=task.session_id,
        source_task_run_id="missing-task-run",
        job_type="preview",
    )
    db.add(job)
    db.commit()

    class UnexpectedPreviewService:
        def start_task_run_preview(self, *args, **kwargs):
            pytest.fail("orphaned preview job reached preview service")

    result = run_preview_job(
        db, job, preview_service=UnexpectedPreviewService()
    )

    assert result.state == "failed"
    assert result.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
