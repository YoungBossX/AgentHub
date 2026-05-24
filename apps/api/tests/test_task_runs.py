import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.context_pack import build_session_context_pack
from app.main import agent_run_request_for, app, get_db
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
from app.task_runs import TaskRunLifecycleError, create_task_run, transition_task_run
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
    assert "Session Context Pack" in request.instruction
    assert request.plan_context["sessionContext"]["originalUserRequest"] == original_request
    assert request.plan_context["sessionContext"]["safeTargetPaths"] == [
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
    assert context["ledger"]["latestChangedFiles"] == ["apps/demo/src/App.tsx"]


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

        request = agent_run_request_for(db, task_run, adapter_type="codex")

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
    original = client.post(f"/tasks/{task_id()}/runs").json()
    client.post(f"/task-runs/{original['id']}/interrupt")

    retry_response = client.post(f"/task-runs/{original['id']}/retry")

    assert retry_response.status_code == 201
    retried = retry_response.json()
    assert retried["id"] != original["id"]
    assert retried["state"] == "queued"
    assert retried["adapterType"] == "codex"
    assert retried["metricsJson"]["retryOfRunId"] == original["id"]

    with db_from_override() as db:
        previous = db.get(TaskRun, original["id"])
        runs = db.exec(select(TaskRun).where(TaskRun.task_id == previous.task_id)).all()
        assert previous.state == "interrupted"
        assert len(runs) == 2


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
