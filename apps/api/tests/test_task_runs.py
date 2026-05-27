import json
import subprocess
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.context_pack import build_session_context_pack
from app.external_workspaces import (
    ExternalWorkspaceRegistration,
    register_external_project_target,
)
from app.instruction_adapters import adapter_for_provider
from app.main import agent_run_request_for, app, get_db, task_run_response
from app.guardrails import ApprovalRequestPayload, request_task_run_approval
from app.reviews import create_scripted_review_for_task_run
from app.models import (
    Agent,
    Artifact,
    Deployment,
    Diff,
    Message,
    Preview,
    Review,
    Session,
    Task,
    TaskRun,
    TaskRunEvent,
    Workspace,
)
from app.models import utc_now
from app.task_runs import (
    TaskRunLifecycleError,
    create_task_run,
    mark_stale_task_runs,
    refresh_task_run_heartbeat,
    transition_task_run,
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


def task_id() -> str:
    with db_from_override() as db:
        return db.exec(select(Task).where(Task.title == "Build login page")).one().id


def test_create_task_run_persists_queued_state_before_event(client: TestClient) -> None:
    response = client.post(f"/tasks/{task_id()}/runs")

    assert response.status_code == 201
    run = response.json()
    assert run["state"] == "queued"
    assert run["adapterType"] == "codex"
    assert run["worktreePath"] == ".worktrees/taskrun-session"

    with db_from_override() as db:
        stored = db.get(TaskRun, run["id"])
        event = db.exec(select(TaskRunEvent).where(TaskRunEvent.task_run_id == run["id"])).one()
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


def test_mark_stale_task_runs_ignores_unexpired_active_run(client: TestClient) -> None:
    with db_from_override() as db:
        task_run = create_task_run(db, task_id())

        stale_runs = mark_stale_task_runs(db)

        assert stale_runs == []

        stored = db.get(TaskRun, task_run.id)
        assert stored.state == "queued"
        assert stored.stale_detected_at is None
        assert stored.stale_reason is None


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
        assert payload["checkpoint"]["targetId"] == DEMO_FRONTEND_TARGET_ID


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
            select(TaskRunEvent).where(TaskRunEvent.task_run_id == task_run.id)
        ).one()

        assert json.loads(task_run.metrics_json)["adapterType"] == "claude_code"
        assert json.loads(event.payload_json)["adapterType"] == "claude_code"


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
        user_message = Message(
            session_id=task.session_id,
            sender_type="user",
            content_md="Build a dashboard",
        )
        assistant_message = Message(
            session_id=task.session_id,
            sender_type="orchestrator",
            content_md="Routing to the Frontend Agent.",
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
    assert "not supported in P12" in reference["reason"]


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

        upstream_run = create_task_run(db, upstream.id)
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

    assert handoff_status == "ready"
    assert handoff_meta["fromTaskId"] == upstream_id
    assert handoff_meta["fromTaskRunId"] == upstream_run_id
    assert handoff_meta["fromAgentRole"] == "frontend"
    assert handoff_meta["toTaskId"] == downstream_id
    assert handoff_meta["toAgentRole"] == "qa"
    assert handoff_meta["changedFiles"] == ["apps/demo/src/App.tsx"]
    assert handoff_meta["verificationStatus"] == "completed"
    assert context["handoffNotes"][0]["artifactId"] == handoff_id
    assert context["canonicalContext"]["fields"]["handoffNotes"]["value"][0][
        "toTaskId"
    ] == downstream_id


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
    assert "Do not edit AgentHub platform backend `apps/api`" in request.instruction
    assert "safe demo backend target" not in request.instruction


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

    assert review.status == "failed"
    assert review.risk_level == "high"
    assert any("expected task target demo-backend" in finding["message"] for finding in review.findings)


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
) -> None:
    original = client.post(f"/tasks/{task_id()}/runs").json()

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

    task_response = client.get(f"/sessions/{fallback['sessionId']}/tasks")
    task = task_response.json()[0]
    assert [run["id"] for run in task["taskRuns"]] == [original["id"], fallback["id"]]


def test_force_codex_failure_creates_failed_visible_run(client: TestClient) -> None:
    response = client.post(f"/tasks/{task_id()}/runs/force-codex-failure")

    assert response.status_code == 201
    run = response.json()
    assert run["adapterType"] == "codex"
    assert run["state"] == "failed"
    assert run["errorCode"] == "CODEX_DEMO_FORCED_FAILURE"

    task_response = client.get(f"/sessions/{run['sessionId']}/tasks")
    task = task_response.json()[0]
    assert task["status"] == "failed"
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

    # At least one event after queued must be from CodexAdapter execution
    later_events = events[1:]
    adapter_event_types = {e.event_type for e in later_events}
    assert adapter_event_types & {"error", "task.state", "completed", "message.delta"}, (
        f"No adapter lifecycle events found after queued: {adapter_event_types}"
    )

    if stored.state == "failed":
        assert stored.error_code is not None, "Failed TaskRun must have error_code"
        assert "CODEX_" in (stored.error_code or ""), (
            f"Expected CODEX_* error code, got: {stored.error_code}"
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
