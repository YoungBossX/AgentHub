import asyncio
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine

from app.adapters import AgentRunRequest, run_adapter_event_stream
from app.diffs import collect_task_run_diff
from app.models import Agent, Session, Task, TaskRun, Workspace
from app.scripted_mock import ScriptedMockAdapter
from app.task_runs import create_task_run as create_lifecycle_task_run


REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def db() -> DbSession:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with DbSession(engine) as session:
        yield session


@pytest.fixture
def demo_worktree(tmp_path: Path) -> Path:
    worktree = tmp_path / "session-worktree"
    demo_root = worktree / "apps" / "demo"
    shutil.copytree(REPO_ROOT / "apps" / "demo", demo_root, ignore=shutil.ignore_patterns("node_modules"))
    subprocess.run(["git", "init"], cwd=worktree, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=worktree, check=True)
    subprocess.run(["git", "config", "user.name", "AgentHub Test"], cwd=worktree, check=True)
    subprocess.run(["git", "add", "apps/demo"], cwd=worktree, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=worktree, check=True, capture_output=True)
    return worktree


def create_task_run(db: DbSession, worktree_path: Path) -> TaskRun:
    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="Scripted session",
        bound_branch="main",
        worktree_path=str(worktree_path),
    )
    agent = Agent(
        name="QA Agent",
        role="qa",
        adapter_type="scripted_mock",
        provider="local",
    )
    task = Task(
        session_id=session.id,
        title="Build login page",
        intent_type="frontend_change",
        assigned_agent_id=agent.id,
    )
    task_run = TaskRun(
        task_id=task.id,
        agent_id=agent.id,
        state="created",
        worktree_path=session.worktree_path,
    )

    db.add(workspace)
    db.add(session)
    db.add(agent)
    db.add(task)
    db.add(task_run)
    db.commit()
    db.refresh(task_run)
    return task_run


def run_request(
    task_run: TaskRun,
    instruction: str,
    plan_context: Optional[dict] = None,
) -> AgentRunRequest:
    return AgentRunRequest(
        taskRunId=task_run.id,
        sessionId="session-id",
        workspaceId="workspace-id",
        worktreePath=task_run.worktree_path,
        agentId=task_run.agent_id,
        adapterType="scripted_mock",
        instruction=instruction,
        planContext=plan_context or {},
    )


def test_scripted_mock_capabilities_disable_shell_and_network() -> None:
    capabilities = ScriptedMockAdapter().getCapabilities()

    assert capabilities.supports_streaming is True
    assert capabilities.supports_file_edit is True
    assert capabilities.supports_shell_command is False
    assert capabilities.supports_network is False


@pytest.mark.anyio
async def test_scripted_mock_login_page_mutates_demo_worktree_and_persists_events(
    db: DbSession,
    demo_worktree: Path,
) -> None:
    task_run = create_task_run(db, demo_worktree)
    adapter = ScriptedMockAdapter()
    request = run_request(task_run, "Build a login page for the demo app.")

    persisted = await run_adapter_event_stream(db, adapter, request)

    app_source = (demo_worktree / "apps/demo/src/App.tsx").read_text()
    status = subprocess.run(
        ["git", "status", "--short", "apps/demo/src/App.tsx"],
        cwd=demo_worktree,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "data-agenthub-target=\"login-page-slot\"" in app_source
    assert "Welcome back" in app_source
    assert "Email address" in app_source
    assert "M apps/demo/src/App.tsx" in status.stdout
    assert [event.event_type for event in persisted] == [
        "task.state",
        "message.delta",
        "task.state",
        "completed",
    ]
    assert [event.sequence for event in persisted] == [1, 2, 3, 4]


@pytest.mark.anyio
async def test_scripted_mock_followup_updates_primary_button_text(
    db: DbSession,
    demo_worktree: Path,
) -> None:
    task_run = create_task_run(db, demo_worktree)
    adapter = ScriptedMockAdapter()
    request = run_request(task_run, 'Change the primary button text to "Sign in".')

    await run_adapter_event_stream(db, adapter, request)

    app_source = (demo_worktree / "apps/demo/src/App.tsx").read_text()
    assert "data-agenthub-target=\"primary-action-button\"" in app_source
    assert "Sign in" in app_source
    assert ">Continue<" not in app_source


@pytest.mark.anyio
async def test_scripted_mock_followup_updates_demo_heading_text(
    db: DbSession,
    demo_worktree: Path,
) -> None:
    task_run = create_task_run(db, demo_worktree)
    adapter = ScriptedMockAdapter()
    request = run_request(task_run, 'Change the demo heading text to "Welcome back".')

    await run_adapter_event_stream(db, adapter, request)

    app_source = (demo_worktree / "apps/demo/src/App.tsx").read_text()
    assert '<h1 id="demo-heading">Welcome back</h1>' in app_source
    assert "Launchpad for a visible coding-agent change" not in app_source


@pytest.mark.anyio
async def test_scripted_mock_followup_run_collects_second_diff_in_same_worktree(
    db: DbSession,
    demo_worktree: Path,
) -> None:
    first_run = create_task_run(db, demo_worktree)
    adapter = ScriptedMockAdapter()
    await run_adapter_event_stream(
        db,
        adapter,
        run_request(first_run, "Build a login page for the demo app."),
    )
    first_diff = collect_task_run_diff(db, first_run.id)

    first_task = db.get(Task, first_run.task_id)
    followup_task = Task(
        session_id=first_task.session_id,
        title="Change primary button text to Sign in",
        intent_type="frontend_change",
        assigned_agent_id=first_run.agent_id,
    )
    db.add(followup_task)
    db.commit()
    db.refresh(followup_task)
    followup_run = create_lifecycle_task_run(
        db,
        followup_task.id,
        adapter_type="scripted_mock",
    )

    await run_adapter_event_stream(
        db,
        adapter,
        run_request(followup_run, 'Change the primary button text to "Sign in".'),
    )
    followup_diff = collect_task_run_diff(db, followup_run.id)

    assert first_run.worktree_path == followup_run.worktree_path
    assert first_diff.task_run_id == first_run.id
    assert followup_diff.task_run_id == followup_run.id
    assert "apps/demo/src/App.tsx" in followup_diff.changed_files
    assert "Sign in" in followup_diff.patch_text


@pytest.mark.anyio
async def test_scripted_mock_forced_failure_emits_error_without_mutation(
    db: DbSession,
    demo_worktree: Path,
) -> None:
    task_run = create_task_run(db, demo_worktree)
    baseline = (demo_worktree / "apps/demo/src/App.tsx").read_text()
    adapter = ScriptedMockAdapter()
    request = run_request(
        task_run,
        "Build a login page for the demo app.",
        {"forceFailure": True},
    )

    persisted = await run_adapter_event_stream(db, adapter, request)

    assert (demo_worktree / "apps/demo/src/App.tsx").read_text() == baseline
    assert persisted[-1].event_type == "error"
    assert "SCRIPTED_MOCK_FORCED_FAILURE" in persisted[-1].payload_json


@pytest.mark.anyio
async def test_scripted_mock_guardrail_blocks_protected_path_mutation(
    db: DbSession,
    demo_worktree: Path,
) -> None:
    task_run = create_task_run(db, demo_worktree)
    adapter = ScriptedMockAdapter()
    request = run_request(
        task_run,
        "Build a login page for the demo app.",
        {"targetPath": ".env"},
    )

    persisted = await run_adapter_event_stream(db, adapter, request)

    assert not (demo_worktree / ".env").exists()
    assert persisted[-1].event_type == "error"
    assert "GUARDRAIL_BLOCKED_PATH" in persisted[-1].payload_json


@pytest.mark.anyio
async def test_scripted_mock_supports_interruption_and_approval_simulation(
    demo_worktree: Path,
) -> None:
    adapter = ScriptedMockAdapter()
    request = AgentRunRequest(
        taskRunId="run-1",
        sessionId="session-id",
        workspaceId="workspace-id",
        worktreePath=str(demo_worktree),
        agentId="agent-id",
        adapterType="scripted_mock",
        instruction="Build a login page for the demo app.",
        planContext={"simulateApproval": True},
    )

    run = await adapter.createRun(request)
    approval_events = [event async for event in adapter.streamEvents(run.adapter_run_id)]
    second_run = await adapter.createRun(request)
    await adapter.interrupt(second_run.adapter_run_id)
    interrupted_events = [event async for event in adapter.streamEvents(second_run.adapter_run_id)]

    assert approval_events[-1].type == "approval.requested"
    assert interrupted_events[-1].type == "error"
    assert interrupted_events[-1].payload["code"] == "SCRIPTED_MOCK_INTERRUPTED"
    await adapter.cleanup(run.adapter_run_id)
    await adapter.cleanup(second_run.adapter_run_id)
