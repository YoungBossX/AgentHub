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
