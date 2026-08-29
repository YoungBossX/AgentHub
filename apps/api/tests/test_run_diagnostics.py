import json
from collections.abc import Iterator
from datetime import timedelta
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.events import append_task_run_event
from app.main import app, get_db
from app.models import Agent, Artifact, Deployment, Diff, Preview, Review, Session, Task, TaskRun, Workspace
from app.models import utc_now
from app.run_diagnostics import build_task_run_diagnostics, classify_run_failure


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
            title="Diagnostics session",
            bound_branch="main",
            worktree_path=".worktrees/diagnostics-session",
        )
        agent = Agent(
            name="Frontend Agent",
            role="frontend",
            adapter_type="codex",
            provider="openai",
        )
        task = Task(
            session_id=session.id,
            title="Build login page",
            intent_type="frontend_change",
            status="pending",
            assigned_agent_id=agent.id,
        )
        db.add(workspace)
        db.add(session)
        db.add(agent)
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


def _db() -> DbSession:
    override = app.dependency_overrides[get_db]
    return next(override())


def _task_and_agent(db: DbSession) -> tuple[Task, Agent]:
    task = db.exec(select(Task).where(Task.title == "Build login page")).one()
    agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
    return task, agent


def _run(
    db: DbSession,
    *,
    state: str = "failed",
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    metrics: Optional[dict] = None,
) -> TaskRun:
    task, agent = _task_and_agent(db)
    now = utc_now()
    run = TaskRun(
        task_id=task.id,
        agent_id=agent.id,
        state=state,
        started_at=now - timedelta(seconds=30) if state != "queued" else None,
        ended_at=now if state in {"completed", "failed", "interrupted"} else None,
        runner_id="local:test-worker" if state != "queued" else None,
        last_heartbeat_at=now - timedelta(seconds=5) if state != "queued" else None,
        lease_expires_at=now + timedelta(seconds=55) if state not in {"completed", "failed", "interrupted", "queued"} else None,
        worktree_path="/Users/luotianhang/Desktop/agenthub/.worktrees/diagnostics",
        base_ref="base",
        head_ref="head",
        error_code=error_code,
        error_message=error_message,
        metrics_json=json.dumps(metrics or {"providerAssignment": {"providerId": "openai", "adapterType": "codex"}}),
        created_at=now - timedelta(seconds=60),
        updated_at=now,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _artifact(
    db: DbSession,
    run: TaskRun,
    artifact_type: str,
    *,
    status: str = "ready",
    title: Optional[str] = None,
    meta: Optional[dict] = None,
) -> Artifact:
    artifact = Artifact(
        task_run_id=run.id,
        artifact_type=artifact_type,
        title=title or f"{artifact_type.title()} artifact",
        status=status,
        meta_json=json.dumps(meta or {}),
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact


def test_classifier_prefers_primary_failure_and_keeps_postprocessing_factor(client: TestClient) -> None:
    with _db() as db:
        run = _run(
            db,
            error_code="ADAPTER_MAX_RUNTIME_TIMEOUT",
            error_message="Adapter max runtime timeout while editing files.",
        )
        preview_artifact = _artifact(db, run, "preview", status="failed")
        preview = Preview(
            artifact_id=preview_artifact.id,
            port=5173,
            url="http://127.0.0.1:5173",
            command="pnpm dev --host 127.0.0.1 --port 5173",
            health_status="failed",
            status_reason="Preview build failed with token=sk-secret",
        )
        db.add(preview)
        db.commit()

        primary, factors = classify_run_failure(
            run,
            events=[],
            artifacts=[preview_artifact],
            previews=[preview],
            deployments=[],
        )

    assert primary is not None
    assert primary.category == "adapter_timeout"
    assert {factor.category for factor in factors} == {"preview_failed"}


def test_classifier_returns_unknown_for_legacy_failed_run_without_evidence(client: TestClient) -> None:
    with _db() as db:
        run = _run(db, error_message=None, error_code=None)
        diagnostics = build_task_run_diagnostics(db, run)

    assert diagnostics.summary.primary_category == "unknown"
    assert diagnostics.primary_failure is not None
    assert diagnostics.primary_failure.category == "unknown"
    assert diagnostics.summary.evidence_status == "limited"


def test_delivery_review_required_event_appears_in_validation_timeline(client: TestClient) -> None:
    with _db() as db:
        run = _run(db, state="completed")
        append_task_run_event(
            db,
            task_run_id=run.id,
            event_type="delivery.review_required",
            payload_json=json.dumps(
                {
                    "state": "review_required",
                    "reason": "Delivery validation found failed evidence.",
                },
                separators=(",", ":"),
            ),
        )
        diagnostics = build_task_run_diagnostics(db, run)

    item = next(item for item in diagnostics.timeline if item.phase == "validation")
    assert item.status == "failed"
    assert item.title == "Validation"


@pytest.mark.parametrize(
    "error_code",
    ("TASK_RUN_SCOPE_VIOLATION", "TASK_RUN_SCOPE_UNVERIFIABLE"),
)
def test_scope_guard_error_codes_are_classified_as_validation_failed(
    client: TestClient,
    error_code: str,
) -> None:
    with _db() as db:
        run = _run(
            db,
            error_code=error_code,
            error_message="The TaskRun scope guard refused the operation.",
        )
        diagnostics = build_task_run_diagnostics(db, run)

    assert diagnostics.primary_failure is not None
    assert diagnostics.primary_failure.category == "validation_failed"
    assert diagnostics.summary.primary_category == "validation_failed"


def test_artifact_scope_refusal_is_safe_validation_timeline_evidence(
    client: TestClient,
) -> None:
    with _db() as db:
        run = _run(db, state="completed")
        append_task_run_event(
            db,
            run.id,
            "task.artifact_scope_refused",
            json.dumps(
                {
                    "result": "violation",
                    "errorCode": "TASK_RUN_SCOPE_VIOLATION",
                    "taskRunId": run.id,
                    "targetId": "demo-frontend",
                    "snapshotVersion": "agenthub.task_run_scope.v1",
                    "changedPathCount": 2,
                    "protectedEntryCount": 3,
                    "protectedCategories": [".git", "secrets"],
                    "reasonCategory": "scope_violation",
                },
                separators=(",", ":"),
            ),
        )
        diagnostics = build_task_run_diagnostics(db, run)

    factor = next(
        factor
        for factor in diagnostics.contributing_factors
        if factor.category == "validation_failed"
    )
    assert factor.raw_error_code == "TASK_RUN_SCOPE_VIOLATION"
    item = next(
        item
        for item in diagnostics.timeline
        if item.metadata.get("eventType") == "task.artifact_scope_refused"
    )
    assert item.phase == "validation"
    assert item.status == "failed"
    assert item.metadata["result"] == "violation"
    assert item.metadata["changedPathCount"] == 2
    assert item.metadata["protectedEntryCount"] == 3
    assert item.metadata["protectedCategories"] == [".git", "secrets"]


def test_scope_validation_passed_is_success_evidence_not_a_failure(
    client: TestClient,
) -> None:
    with _db() as db:
        run = _run(db, state="completed")
        append_task_run_event(
            db,
            run.id,
            "task.scope_validation.passed",
            json.dumps(
                {
                    "result": "passed",
                    "taskRunId": run.id,
                },
                separators=(",", ":"),
            ),
        )
        diagnostics = build_task_run_diagnostics(db, run)

    assert diagnostics.primary_failure is None
    assert diagnostics.contributing_factors == []
    item = next(
        item
        for item in diagnostics.timeline
        if item.metadata.get("eventType") == "task.scope_validation.passed"
    )
    assert item.phase == "validation"
    assert item.status == "success"


@pytest.mark.parametrize(
    "event_type",
    ("task.checkpoint.created", "task.scope_validation.passed"),
)
@pytest.mark.parametrize(
    ("error_code", "expected_category"),
    (
        pytest.param(None, "unknown", id="text-only"),
        pytest.param(
            "TASK_RUN_SCOPE_UNVERIFIABLE",
            "validation_failed",
            id="scope-error",
        ),
        pytest.param(
            "PROVIDER_UNAVAILABLE",
            "provider_unavailable",
            id="provider-error",
        ),
    ),
)
def test_informational_scope_events_suppress_only_text_failure_inference(
    client: TestClient,
    event_type: str,
    error_code: Optional[str],
    expected_category: str,
) -> None:
    with _db() as db:
        run = _run(db)
        payload = {
            "reason": "The scope snapshot is unavailable.",
            "taskRunId": run.id,
        }
        if error_code is not None:
            payload["errorCode"] = error_code
        append_task_run_event(
            db,
            run.id,
            event_type,
            json.dumps(payload, separators=(",", ":")),
        )
        diagnostics = build_task_run_diagnostics(db, run)

    assert diagnostics.primary_failure is not None
    assert diagnostics.primary_failure.category == expected_category


def test_scope_diagnostics_redact_host_and_raw_control_evidence(
    client: TestClient,
) -> None:
    raw_fingerprint = "a" * 64
    raw_control_digest = "b" * 64
    unc_path = r"\\server\share\repo\.git\config"
    scope_control_key = "scope-control-key-must-not-leak"
    control_key = "control-key-must-not-leak"
    with _db() as db:
        run = _run(db, state="completed")
        append_task_run_event(
            db,
            run.id,
            "task.artifact_scope_refused",
            json.dumps(
                {
                    "result": "unverifiable",
                    "errorCode": "TASK_RUN_SCOPE_UNVERIFIABLE",
                    "taskRunId": run.id,
                    "targetId": "demo-frontend",
                    "snapshotVersion": "agenthub.task_run_scope.v1",
                    "referenceUrl": "https://example.test/safe/path",
                    "protectedEntryCount": 4,
                    "protectedCategories": [
                        ".env",
                        ".git",
                        "node_modules",
                        "secrets",
                    ],
                    "unsafeEvidence": {
                        "hostPath": "Z:\\private-host\\scope-fixture\\.git\\config",
                        "linuxPath": "/home/agent/private/.git/config",
                        "tempPath": "/tmp/agenthub/private-control",
                        "rootPath": "/root/private/.git/config",
                        "optPath": "/opt/agenthub/private-control",
                        "workspacePath": "/workspace/repo/.git/config",
                        "uncPath": unc_path,
                        "fingerprint": raw_fingerprint,
                        "protectedControlDigest": raw_control_digest,
                        "scopeControlKey": scope_control_key,
                        "controlKey": control_key,
                        "protectedRecords": [
                            {
                                "path": "/workspace/repo/.git/HEAD",
                                "content": "PROTECTED-RECORD-CONTENT",
                            }
                        ],
                        "protectedTreeRecords": [
                            {
                                "path": unc_path,
                                "content": "PROTECTED-TREE-CONTENT",
                            }
                        ],
                        "fileContents": "TOP-SECRET-CONTENT",
                    },
                },
                separators=(",", ":"),
            ),
        )
        diagnostics = build_task_run_diagnostics(db, run)

    exposed = json.dumps(diagnostics.model_dump(by_alias=True), default=str)
    assert "X:" not in exposed
    assert "/home/agent" not in exposed
    assert "/tmp/agenthub" not in exposed
    assert "/root/private" not in exposed
    assert "/opt/agenthub" not in exposed
    assert "/workspace/repo" not in exposed
    assert "server" not in exposed
    assert ".git/config" not in exposed
    assert raw_fingerprint not in exposed
    assert raw_control_digest not in exposed
    assert scope_control_key not in exposed
    assert control_key not in exposed
    assert "PROTECTED-RECORD-CONTENT" not in exposed
    assert "PROTECTED-TREE-CONTENT" not in exposed
    assert "TOP-SECRET-CONTENT" not in exposed
    assert "https://example.test/safe/path" in exposed
    item = next(
        item
        for item in diagnostics.timeline
        if item.metadata.get("eventType") == "task.artifact_scope_refused"
    )
    assert item.metadata["targetId"] == "demo-frontend"
    assert item.metadata["protectedEntryCount"] == 4
    assert item.metadata["referenceUrl"] == "https://example.test/safe/path"
    assert item.metadata["protectedCategories"] == [
        ".env",
        ".git",
        "node_modules",
        "secrets",
    ]


def test_scope_diagnostics_fully_redact_spaced_and_cwd_host_paths(
    client: TestClient,
) -> None:
    safe_url = "https://example.test/safe/path"
    safe_categories = [".env", ".git", "node_modules", "secrets"]
    locations = {
        "windowsLocation": r"C:\Users\Jane Doe\Agent Hub\.git\config",
        "uncLocation": r"\\server\Shared Repo\Agent Hub\.git\config",
        "posixLocation": "/Users/Jane Doe/Agent Hub/.git/config",
        "cwdLocation": "cwd:/Users/Jane Doe/Agent Hub/.git/config",
        "rootLocation": "root:/home/alice/Agent Hub/.git/config",
        "worktreeLocation": "worktree:/Users/Jane Doe/Agent Hub/.git/config",
        "fileUriLocation": "file:///home/alice/Agent Hub/.git/config",
    }
    with _db() as db:
        run = _run(db, state="completed")
        append_task_run_event(
            db,
            run.id,
            "task.artifact_scope_refused",
            json.dumps(
                {
                    "result": "unverifiable",
                    "errorCode": "TASK_RUN_SCOPE_UNVERIFIABLE",
                    "taskRunId": run.id,
                    "referenceUrl": safe_url,
                    "protectedCategories": safe_categories,
                    **locations,
                },
                separators=(",", ":"),
            ),
        )
        diagnostics = build_task_run_diagnostics(db, run)

    item = next(
        item
        for item in diagnostics.timeline
        if item.metadata.get("eventType") == "task.artifact_scope_refused"
    )
    for key in locations:
        assert item.metadata[key] == "[redacted-path]"
    assert item.metadata["referenceUrl"] == safe_url
    assert item.metadata["protectedCategories"] == safe_categories


def test_timeline_covers_successful_run_with_artifact_references(client: TestClient) -> None:
    with _db() as db:
        run = _run(db, state="completed")
        append_task_run_event(db, run.id, "run.claimed", json.dumps({"workerId": "worker-1"}))
        append_task_run_event(db, run.id, "task.state", json.dumps({"state": "streaming"}))
        diff_artifact = _artifact(db, run, "diff")
        review_artifact = _artifact(db, run, "review")
        preview_artifact = _artifact(db, run, "preview")
        deploy_artifact = _artifact(db, run, "deployment")
        db.add(Diff(artifact_id=diff_artifact.id, base_ref="base", head_ref="head", patch_text="diff", changed_files_json='["src/App.tsx"]'))
        db.add(Review(artifact_id=review_artifact.id, reviewed_diff_artifact_id=diff_artifact.id, adapter_type="scripted_mock", status="ready", risk_level="low", summary="Looks good."))
        db.add(Preview(artifact_id=preview_artifact.id, port=5173, url="http://127.0.0.1:5173", command="pnpm dev --host 127.0.0.1 --port 5173", health_status="healthy"))
        db.add(Deployment(artifact_id=deploy_artifact.id, provider="mock", environment="preview", status="ready", url="http://127.0.0.1:4173"))
        db.commit()

        diagnostics = build_task_run_diagnostics(db, run)

    phases = [item.phase for item in diagnostics.timeline]
    assert "queued" in phases
    assert "worker_claim" in phases
    assert "adapter_stream" in phases
    assert "diff" in phases
    assert "review" in phases
    assert "preview" in phases
    assert "deploy" in phases
    assert "finalize" in phases
    assert diagnostics.primary_failure is None
    assert any(item.artifact_reference and item.artifact_reference.artifact_type == "diff" for item in diagnostics.timeline)


def test_timeline_and_health_cover_provider_timeout_preview_and_recovery(client: TestClient) -> None:
    with _db() as db:
        run = _run(
            db,
            error_code="PROVIDER_QUOTA_EXCEEDED",
            error_message="Provider rate limit quota exceeded.",
        )
        run.stale_detected_at = utc_now()
        run.stale_reason = "lease_expired"
        db.add(run)
        db.commit()
        append_task_run_event(db, run.id, "task.stale", json.dumps({"reason": "lease_expired"}))
        append_task_run_event(db, run.id, "error", json.dumps({"code": "ADAPTER_IDLE_TIMEOUT", "message": "idle timeout"}))
        preview_artifact = _artifact(db, run, "preview", status="failed")
        db.add(Preview(artifact_id=preview_artifact.id, port=5174, url="http://127.0.0.1:5174", command="pnpm dev --host 127.0.0.1 --port 5174", health_status="failed", status_reason="health check failed"))
        db.commit()

        diagnostics = build_task_run_diagnostics(db, run)

    assert diagnostics.primary_failure is not None
    assert diagnostics.primary_failure.category == "provider_quota"
    assert "recovery" in [item.phase for item in diagnostics.timeline]
    assert diagnostics.health_summary.provider["status"] == "failed"
    assert diagnostics.health_summary.queue["status"] == "failed"
    assert diagnostics.health_summary.preview["status"] == "failed"


def test_connection_refused_provider_failure_is_not_reported_as_quota(client: TestClient) -> None:
    with _db() as db:
        run = _run(
            db,
            error_code="CLAUDE_CODE_EXIT_ERROR",
            error_message="API Error: Unable to connect to API (ConnectionRefused)",
            metrics={
                "providerAssignment": {
                    "providerId": "local-claude-code-cli",
                    "adapterType": "claude_code",
                }
            },
        )
        append_task_run_event(
            db,
            run.id,
            "error",
            json.dumps(
                {
                    "code": "CLAUDE_CODE_EXIT_ERROR",
                    "message": "API Error: Unable to connect to API (ConnectionRefused)",
                    "adapter": "claude_code",
                    "command": ["claude", "--print", "--max-budget-usd", "1.00"],
                    "context": {
                        "recentMessageId": "29ab2980-96b4-429b-9c9c-4f5dfd808c39",
                    },
                }
            ),
        )
        diagnostics = build_task_run_diagnostics(db, run)

    assert diagnostics.primary_failure is not None
    assert diagnostics.primary_failure.category == "provider_unavailable"
    assert diagnostics.summary.primary_category == "provider_unavailable"
    assert diagnostics.health_summary.provider["status"] == "failed"


def test_health_and_suggestions_cover_provider_approval_dirty_and_deploy_cases(client: TestClient) -> None:
    with _db() as db:
        provider_run = _run(db, error_code="PROVIDER_AUTH_MISSING", error_message="Missing API key.")
        approval_run = _run(db, error_code="APPROVAL_DENIED", error_message="Approval denied by user.")
        dirty_run = _run(db, error_code="WORKTREE_DIRTY", error_message="Dirty worktree blocked retry.")
        _artifact(db, dirty_run, "diff")
        deploy_run = _run(db, state="completed")
        deploy_artifact = _artifact(db, deploy_run, "deployment", status="blocked")
        db.add(Deployment(artifact_id=deploy_artifact.id, provider="vercel", environment="production", status="blocked", deploy_log_uri="vercel://logs"))
        db.commit()

        provider = build_task_run_diagnostics(db, provider_run)
        approval = build_task_run_diagnostics(db, approval_run)
        dirty = build_task_run_diagnostics(db, dirty_run)
        deploy = build_task_run_diagnostics(db, deploy_run)

    assert provider.primary_failure is not None
    assert provider.primary_failure.category == "provider_auth"
    assert {suggestion.kind for suggestion in provider.suggestions} >= {"open_settings", "choose_fallback"}
    assert approval.primary_failure is not None
    assert approval.primary_failure.category == "approval_denied"
    assert any(suggestion.kind == "request_approval" for suggestion in approval.suggestions)
    assert dirty.primary_failure is not None
    assert dirty.primary_failure.category == "worktree_dirty"
    assert any(suggestion.kind == "open_artifact" and suggestion.enabled for suggestion in dirty.suggestions)
    assert deploy.primary_failure is None
    assert [factor.category for factor in deploy.contributing_factors] == ["deploy_blocked"]
    assert deploy.health_summary.deploy["status"] == "blocked"
    assert any(suggestion.kind == "manual_handoff" for suggestion in deploy.suggestions)


def test_diagnostics_api_redacts_sensitive_metadata_and_paths(client: TestClient) -> None:
    with _db() as db:
        run = _run(
            db,
            error_code="VALIDATION_FAILED",
            error_message=(
                "PlanValidator rejected /Users/luotianhang/Desktop/agenthub/.env "
                "with apiKey=sk-secret123 and token=ghp_abcdef."
            ),
        )
        append_task_run_event(
            db,
            run.id,
            "task.state",
            json.dumps(
                {
                    "state": "failed",
                    "errorMessage": "Cannot edit /Users/luotianhang/Desktop/agenthub/secrets/api.txt",
                    "providerOutput": "Bearer abc.def.ghi",
                }
            ),
        )
        run_id = run.id

    response = client.get(f"/task-runs/{run_id}/diagnostics")

    assert response.status_code == 200
    body_text = json.dumps(response.json())
    assert "sk-secret123" not in body_text
    assert "ghp_abcdef" not in body_text
    assert "Bearer abc.def.ghi" not in body_text
    assert "/Users/luotianhang" not in body_text
    assert ".env" not in body_text
    assert "secrets/api.txt" not in body_text
    assert response.json()["primaryFailure"]["category"] == "validation_failed"


def test_diagnostics_api_404_and_session_summary_are_stable(client: TestClient) -> None:
    missing = client.get("/task-runs/missing-run/diagnostics")
    assert missing.status_code == 404

    with _db() as db:
        task, _agent = _task_and_agent(db)
        failed = _run(db, error_code="LOCK_TIMEOUT", error_message="Target lock timeout.")
        completed = _run(db, state="completed")
        session_id = task.session_id
        run_ids = {failed.id, completed.id}

    response = client.get(f"/sessions/{session_id}/run-diagnostics-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["sessionId"] == session_id
    assert body["totalRuns"] == 2
    assert body["states"] == {"completed": 1, "failed": 1}
    assert body["categories"]["lock_timeout"] == 1
    assert {item["taskRunId"] for item in body["runs"]} == run_ids
