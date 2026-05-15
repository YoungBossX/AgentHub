import json
from pathlib import Path

from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine

from app.guardrails import (
    ApprovalRequestPayload,
    approve_task_run,
    deny_task_run,
    evaluate_command,
    evaluate_network_access,
    evaluate_path,
    request_task_run_approval,
)
from app.models import Agent, Session, Task, TaskRun, Workspace


def create_db() -> DbSession:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return DbSession(engine)


def create_task_run(db: DbSession, role: str = "frontend") -> tuple[Task, TaskRun]:
    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title=f"Guardrail session {role}",
        bound_branch="main",
        worktree_path=f".worktrees/guardrail-session-{role}",
    )
    agent = Agent(
        name="Frontend Agent",
        role=role,
        adapter_type="codex",
        provider="local",
    )
    task = Task(
        session_id=session.id,
        title="Build login page",
        intent_type="frontend_change",
        status="running",
        assigned_agent_id=agent.id,
    )
    task_run = TaskRun(
        task_id=task.id,
        agent_id=agent.id,
        state="streaming",
        worktree_path=session.worktree_path,
    )
    db.add(workspace)
    db.add(session)
    db.add(agent)
    db.add(task)
    db.add(task_run)
    db.commit()
    db.refresh(task)
    db.refresh(task_run)
    return task, task_run


def test_command_policy_allows_p0_commands_and_requires_approval_for_risky_ones() -> None:
    allowed = evaluate_command(["pnpm", "test"])
    git_with_cwd = evaluate_command(["git", "-C", "/tmp/worktree", "status"])
    codex_app_path = evaluate_command(
        [
            "/Applications/Codex.app/Contents/Resources/codex",
            "--ask-for-approval",
            "never",
            "exec",
            "--json",
            "--cd",
            "/tmp/worktree",
            "--sandbox",
            "workspace-write",
            "Make the button text more friendly.",
        ]
    )
    blocked = evaluate_command(["bash", "-lc", "rm -rf apps/demo"])
    push = evaluate_command(["git", "push", "origin", "main"])

    assert allowed.allowed is True
    assert allowed.approval is None
    assert git_with_cwd.allowed is True
    assert codex_app_path.allowed is True

    assert blocked.allowed is False
    assert blocked.approval is not None
    assert blocked.approval.approval_type == "security_approval"
    assert blocked.approval.risk_level == "high"
    assert blocked.approval.command == "bash -lc 'rm -rf apps/demo'"

    assert push.allowed is False
    assert push.approval is not None
    assert push.approval.requested_action == "git push origin main"


def test_path_policy_protects_sensitive_and_out_of_worktree_paths() -> None:
    worktree = Path("/tmp/agenthub-session")
    allowed = evaluate_path(worktree / "apps/demo/src/App.tsx", worktree)
    private_worktree_allowed = evaluate_path(
        "/private/tmp/session/apps/demo/src/App.tsx",
        "/private/tmp/session",
    )
    traversal = evaluate_path("../outside.txt", worktree)
    protected = [
        worktree / ".git/config",
        worktree / ".env",
        worktree / ".env.local",
        worktree / "secrets/token.txt",
        worktree / "apps/demo/node_modules/react/index.js",
        Path("/etc/passwd"),
    ]

    assert allowed.allowed is True
    assert private_worktree_allowed.allowed is True
    assert traversal.allowed is False

    for path in protected:
        decision = evaluate_path(path, worktree)
        assert decision.allowed is False
        assert decision.approval is not None
        assert decision.approval.path == str(path.resolve(strict=False))


def test_network_policy_defaults_to_approval_required() -> None:
    denied = evaluate_network_access()
    approved = evaluate_network_access(network_approved=True)

    assert denied.allowed is False
    assert denied.approval is not None
    assert denied.approval.requested_action == "network access"
    assert approved.allowed is True


def test_approval_payload_uses_public_event_shape() -> None:
    payload = ApprovalRequestPayload(
        approvalType="security_approval",
        reason="Command is outside the P0 allowlist.",
        requestedAction="curl https://example.com",
        riskLevel="high",
        command="curl https://example.com",
    )

    assert payload.model_dump(by_alias=True, exclude_none=True) == {
        "approvalType": "security_approval",
        "reason": "Command is outside the P0 allowlist.",
        "requestedAction": "curl https://example.com",
        "riskLevel": "high",
        "command": "curl https://example.com",
    }


def test_approval_request_sets_waiting_state_and_persists_event() -> None:
    with create_db() as db:
        task, task_run = create_task_run(db)
        payload = ApprovalRequestPayload(
            approvalType="security_approval",
            reason="Protected path edit requires approval.",
            requestedAction="edit .env",
            riskLevel="high",
            path=".env",
        )

        event = request_task_run_approval(db, task_run.id, payload)

        db.refresh(task)
        db.refresh(task_run)
        assert task.status == "waiting_approval"
        assert task_run.state == "waiting_approval"
        assert event.event_type == "approval.requested"
        assert event.sequence == 1
        assert json.loads(event.payload_json)["approvalType"] == "security_approval"


def test_approve_and_deny_service_methods_update_waiting_task_run() -> None:
    with create_db() as db:
        approved_task, approved_run = create_task_run(db)
        denied_task, denied_run = create_task_run(db, role="qa")

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
        request_task_run_approval(
            db,
            denied_run.id,
            ApprovalRequestPayload(
                approvalType="security_approval",
                reason="Network is disabled by default.",
                requestedAction="network access",
                riskLevel="high",
            ),
        )

        approve_task_run(db, approved_run.id)
        deny_task_run(db, denied_run.id, reason="User denied network access.")

        db.refresh(approved_task)
        db.refresh(approved_run)
        db.refresh(denied_task)
        db.refresh(denied_run)

        assert approved_task.status == "running"
        assert approved_run.state == "queued"
        assert denied_task.status == "failed"
        assert denied_run.state == "failed"
        assert denied_run.error_code == "APPROVAL_DENIED"
        assert denied_run.error_message == "User denied network access."
