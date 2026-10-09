import asyncio
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine

from app.adapters import AgentRunRequest, run_adapter_event_stream as _run_adapter_event_stream
from app.diffs import collect_task_run_diff
from app.models import Agent, Session, Task, TaskRun, Workspace
from app.scripted_mock import LOGIN_STYLE_END, LOGIN_STYLE_START, ScriptedMockAdapter
from app.task_runs import create_task_run as create_lifecycle_task_run


REPO_ROOT = Path(__file__).resolve().parents[3]


def _allow_test_execution_ownership(_: DbSession) -> bool:
    return True


async def run_adapter_event_stream(db, adapter, request, **kwargs):
    kwargs.setdefault("ownership_guard", _allow_test_execution_ownership)
    return await _run_adapter_event_stream(db, adapter, request, **kwargs)


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
    db: DbSession,
    task_run: TaskRun,
    instruction: str,
    plan_context: Optional[dict] = None,
) -> AgentRunRequest:
    task = db.get(Task, task_run.task_id)
    assert task is not None
    return AgentRunRequest(
        taskRunId=task_run.id,
        sessionId=task.session_id,
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
    request = run_request(db, task_run, "Build a login page for the demo app.")

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
async def test_scripted_login_preserves_existing_css_and_reports_real_files(db, demo_worktree):
    styles = demo_worktree / "apps/demo/src/styles.css"
    original = b"/* keep my CSS */\r\n.other-control { color: #123456; }\r\n"
    styles.write_bytes(original)
    run = create_task_run(db, demo_worktree)
    events = await run_adapter_event_stream(db, ScriptedMockAdapter(), run_request(
        db, run, "Build login page", {"target": "login_page"},
    ))
    assert events[-1].event_type == "completed"
    assert set(json.loads(events[-1].payload_json)["changedFiles"]) == {
        "apps/demo/src/App.tsx", "apps/demo/src/styles.css",
    }
    updated = styles.read_bytes()
    assert updated.startswith(original)
    assert updated.count(LOGIN_STYLE_START.encode()) == 1
    assert b".login-form input:focus-visible" in updated
    assert b"\r\n" in updated and b"\n" not in updated.replace(b"\r\n", b"")
    login = (demo_worktree / "apps/demo/src/App.tsx").read_text(encoding="utf-8")
    assert 'name="email" autoComplete="username"' in login
    assert 'name="password" autoComplete="current-password"' in login


@pytest.mark.anyio
async def test_login_styles_upgrade_alone_then_noop_remains_rejected(db, demo_worktree):
    styles = demo_worktree / "apps/demo/src/styles.css"
    original = styles.read_bytes()
    first = create_task_run(db, demo_worktree)
    await run_adapter_event_stream(db, ScriptedMockAdapter(), run_request(db, first, "Build login page", {"target": "login_page"}))
    app = demo_worktree / "apps/demo/src/App.tsx"
    styled_app = app.read_bytes()
    styles.write_bytes(original)
    upgrade = TaskRun(task_id=first.task_id, agent_id=first.agent_id, state="created", worktree_path=str(demo_worktree))
    db.add(upgrade); db.commit(); db.refresh(upgrade)
    events = await run_adapter_event_stream(db, ScriptedMockAdapter(), run_request(db, upgrade, "Build login page", {"target": "login_page"}))
    assert events[-1].event_type == "completed"
    assert json.loads(events[-1].payload_json)["changedFiles"] == ["apps/demo/src/styles.css"]
    assert app.read_bytes() == styled_app
    baseline = styles.read_bytes()
    noop = TaskRun(task_id=first.task_id, agent_id=first.agent_id, state="created", worktree_path=str(demo_worktree))
    db.add(noop); db.commit(); db.refresh(noop)
    events = await run_adapter_event_stream(db, ScriptedMockAdapter(), run_request(db, noop, "Build login page", {"target": "login_page"}))
    assert events[-1].event_type == "error" and "did not change" in events[-1].payload_json
    assert styles.read_bytes() == baseline and app.read_bytes() == styled_app


@pytest.mark.anyio
@pytest.mark.parametrize("markers", [
    LOGIN_STYLE_START, LOGIN_STYLE_END,
    LOGIN_STYLE_END + LOGIN_STYLE_START,
    LOGIN_STYLE_START + LOGIN_STYLE_START + LOGIN_STYLE_END,
])
async def test_ambiguous_login_css_fails_before_source_writes(db, demo_worktree, markers):
    app = demo_worktree / "apps/demo/src/App.tsx"
    styles = app.with_name("styles.css")
    styles.write_text(markers, encoding="utf-8")
    baseline = (app.read_bytes(), styles.read_bytes())
    run = create_task_run(db, demo_worktree)
    events = await run_adapter_event_stream(db, ScriptedMockAdapter(), run_request(db, run, "Build login page", {"target": "login_page"}))
    assert events[-1].event_type == "error" and "ambiguous" in events[-1].payload_json
    assert (app.read_bytes(), styles.read_bytes()) == baseline


@pytest.mark.anyio
@pytest.mark.parametrize("fail_file,missing_css", [("styles.css", False), ("App.tsx", False), ("App.tsx", True)])
async def test_login_write_failure_restores_originals(db, demo_worktree, monkeypatch, fail_file, missing_css):
    app = demo_worktree / "apps/demo/src/App.tsx"
    styles = app.with_name("styles.css")
    if missing_css:
        styles.unlink()
    baseline = (app.read_bytes(), styles.read_bytes() if styles.exists() else None)
    write = Path.write_bytes
    failed = False

    def fail_once(path, data):
        nonlocal failed
        if path.name == fail_file and not failed:
            failed = True
            write(path, data[:12])
            raise OSError("Controlled partial write failure")
        return write(path, data)

    monkeypatch.setattr(Path, "write_bytes", fail_once)
    run = create_task_run(db, demo_worktree)
    events = await run_adapter_event_stream(db, ScriptedMockAdapter(), run_request(db, run, "Build login page", {"target": "login_page"}))
    assert failed and events[-1].event_type == "error" and "original files restored" in events[-1].payload_json
    assert (app.read_bytes(), styles.read_bytes() if styles.exists() else None) == baseline


@pytest.mark.anyio
async def test_login_restoration_failure_is_reported_honestly(db, demo_worktree, monkeypatch):
    app = demo_worktree / "apps/demo/src/App.tsx"
    write = Path.write_bytes

    def fail_app(path, data):
        if path == app:
            write(path, data[:12])
            raise OSError("Controlled App write failure")
        return write(path, data)

    monkeypatch.setattr(Path, "write_bytes", fail_app)
    run = create_task_run(db, demo_worktree)
    events = await run_adapter_event_stream(db, ScriptedMockAdapter(), run_request(db, run, "Build login page", {"target": "login_page"}))
    assert events[-1].event_type == "error" and "file restoration failed" in events[-1].payload_json
    assert not any(event.event_type == "completed" for event in events)


@pytest.mark.anyio
@pytest.mark.parametrize("alias", ["symlink-outside", "symlink-inside", "hardlink"])
async def test_scripted_login_rejects_aliased_stylesheet(db, demo_worktree, tmp_path, alias):
    app = demo_worktree / "apps/demo/src/App.tsx"
    styles = app.with_name("styles.css")
    outside = tmp_path / "host.css"
    outside.write_text("/* preserve host */", encoding="utf-8")
    target = app if alias == "symlink-inside" else outside
    baseline = (app.read_bytes(), outside.read_bytes())
    styles.unlink()
    try:
        if alias == "hardlink":
            os.link(target, styles)
        else:
            styles.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"Cannot create test file alias: {exc}")
    run = create_task_run(db, demo_worktree)
    events = await run_adapter_event_stream(db, ScriptedMockAdapter(), run_request(db, run, "Build login page", {"target": "login_page"}))
    assert events[-1].event_type == "error" and "unsafe" in events[-1].payload_json
    assert (app.read_bytes(), outside.read_bytes()) == baseline


@pytest.mark.anyio
@pytest.mark.parametrize("target,text", [
    ("login_page", None),
    ("primary_action_button_text", "Sign in"),
    ("demo_heading_text", "New heading"),
    ("demo_heading_text", "欢迎回来"),
])
async def test_structured_target_overrides_conflicting_instruction_keywords(
    db: DbSession, demo_worktree: Path, target: str, text: Optional[str],
) -> None:
    task_run = create_task_run(db, demo_worktree)
    app_path = demo_worktree / "apps/demo/src/App.tsx"
    baseline = app_path.read_text(encoding="utf-8")
    persisted = await run_adapter_event_stream(db, ScriptedMockAdapter(), run_request(
        db, task_run,
        'Task title: previous heading and button change to "Wrong copy". Build a login page.',
        {"target": target, "targetText": text, "script": "heading"},
    ))
    assert persisted[-1].event_type == "completed"
    source = app_path.read_text(encoding="utf-8")
    if target == "login_page":
        assert '<form className="login-form"' in source
        assert 'type="email"' in source and 'type="password"' in source
        assert '<h1 id="demo-heading">Launchpad for a visible coding-agent change</h1>' in source
        assert "            Continue\n" in source
    elif target == "primary_action_button_text":
        assert source == baseline.replace("            Continue\n", "            Sign in\n")
    else:
        assert source == baseline.replace(
            "Launchpad for a visible coding-agent change", text,
        )


@pytest.mark.anyio
@pytest.mark.parametrize("plan", [
    {"target": "theme_accent_color", "targetText": "blue"},
    {"target": "external_target_request"},
    {"target": None},
    {"target": {"target": "login_page"}},
    {"target": "primary_action_button_text"},
    {"target": "demo_heading_text", "targetText": "  "},
    {"target": "primary_action_button_text", "targetText": 42},
])
async def test_invalid_structured_target_fails_without_mutating_demo(
    db: DbSession, demo_worktree: Path, plan: dict,
) -> None:
    task_run = create_task_run(db, demo_worktree)
    app_path = demo_worktree / "apps/demo/src/App.tsx"
    baseline = app_path.read_bytes()
    persisted = await run_adapter_event_stream(db, ScriptedMockAdapter(), run_request(
        db, task_run, 'Change the heading to "Wrong copy" and build a login page.', plan,
    ))
    assert persisted[-1].event_type == "error"
    assert "SCRIPTED_MOCK_MUTATION_FAILED" in persisted[-1].payload_json
    assert app_path.read_bytes() == baseline


@pytest.mark.anyio
async def test_scripted_mock_followup_updates_primary_button_text(
    db: DbSession,
    demo_worktree: Path,
) -> None:
    task_run = create_task_run(db, demo_worktree)
    adapter = ScriptedMockAdapter()
    request = run_request(db, task_run, 'Change the primary button text to "Sign in".')

    await run_adapter_event_stream(db, adapter, request)

    app_source = (demo_worktree / "apps/demo/src/App.tsx").read_text()
    assert "data-agenthub-target=\"primary-action-button\"" in app_source
    assert "Sign in" in app_source
    assert ">Continue<" not in app_source


COPY_LITERAL_VALUES = [
    "{agenthubCopyProbe}",
    "A &amp; B <strong>text</strong>",
    "Close </button> </h1> {x} &lt;",
    r"路径 C:\demo\1\g<1> $&",
    "首行\n第二行\r第三行\t末尾\u2028分隔\u2029段落",
    "Emoji 🚀 \"quote\" 'single' & {name}",
]


def _copy_region(source: str, target: str) -> re.Match:
    pattern = (
        r'(data-agenthub-target="primary-action-button"\s+type="button"\s*>\n)'
        r'(?P<copy>.*?)(\n\s*</button>)'
        if target == "primary_action_button_text"
        else r'(<h1\s+id="demo-heading"\s*>)(?P<copy>.*?)(</h1>)'
    )
    match = re.search(pattern, source, re.DOTALL)
    assert match is not None
    return match


@pytest.mark.anyio
@pytest.mark.parametrize("target", ["primary_action_button_text", "demo_heading_text"])
@pytest.mark.parametrize("text", COPY_LITERAL_VALUES)
async def test_scripted_copy_is_string_data_and_preserves_source(db, demo_worktree, target, text):
    app = demo_worktree / "apps/demo/src/App.tsx"
    baseline = app.read_text(encoding="utf-8")
    styles = app.with_name("styles.css").read_bytes()
    run = create_task_run(db, demo_worktree)
    events = await run_adapter_event_stream(db, ScriptedMockAdapter(), run_request(
        db, run, "Copy-only fixture", {"target": target, "targetText": text},
    ))
    assert events[-1].event_type == "completed"
    assert json.loads(events[-1].payload_json)["changedFiles"] == ["apps/demo/src/App.tsx"]
    source = app.read_text(encoding="utf-8")
    before = _copy_region(baseline, target)
    after = _copy_region(source, target)
    encoded = after.group("copy").strip()
    assert encoded.startswith("{") and encoded.endswith("}")
    assert json.loads(encoded[1:-1]) == text
    assert "</button>" not in encoded and "</h1>" not in encoded
    assert source[:after.start("copy")] == baseline[:before.start("copy")]
    assert source[after.end("copy"):] == baseline[before.end("copy"):]
    assert app.with_name("styles.css").read_bytes() == styles


@pytest.mark.anyio
@pytest.mark.parametrize("target", ["primary_action_button_text", "demo_heading_text"])
async def test_scripted_literal_copy_noop_then_plain_continuation(db, demo_worktree, target):
    app = demo_worktree / "apps/demo/src/App.tsx"
    first = create_task_run(db, demo_worktree)
    text = "Literal </button> </h1> {x} &amp;"
    await run_adapter_event_stream(db, ScriptedMockAdapter(), run_request(
        db, first, "Literal fixture", {"target": target, "targetText": text},
    ))
    original = app.read_bytes()
    second = TaskRun(task_id=first.task_id, agent_id=first.agent_id, state="created", worktree_path=str(demo_worktree))
    db.add(second); db.commit(); db.refresh(second)
    events = await run_adapter_event_stream(db, ScriptedMockAdapter(), run_request(
        db, second, "Repeated literal fixture", {"target": target, "targetText": text},
    ))
    assert events[-1].event_type == "error" and "did not change" in events[-1].payload_json
    assert app.read_bytes() == original
    third = TaskRun(task_id=first.task_id, agent_id=first.agent_id, state="created", worktree_path=str(demo_worktree))
    db.add(third); db.commit(); db.refresh(third)
    events = await run_adapter_event_stream(db, ScriptedMockAdapter(), run_request(
        db, third, "Plain fixture", {"target": target, "targetText": "Continue again"},
    ))
    assert events[-1].event_type == "completed"
    assert _copy_region(app.read_text(encoding="utf-8"), target).group("copy").strip() == "Continue again"


@pytest.mark.anyio
@pytest.mark.parametrize("target", ["primary_action_button_text", "demo_heading_text"])
async def test_plain_backslashes_stay_literal_copy(db, demo_worktree, target):
    run = create_task_run(db, demo_worktree)
    text = r"C:\demo\1"
    events = await run_adapter_event_stream(db, ScriptedMockAdapter(), run_request(
        db, run, "Plain path fixture", {"target": target, "targetText": text},
    ))
    assert events[-1].event_type == "completed"
    app = demo_worktree / "apps/demo/src/App.tsx"
    assert _copy_region(app.read_text(encoding="utf-8"), target).group("copy").strip() == text


@pytest.mark.anyio
async def test_scripted_mock_followup_updates_demo_heading_text(
    db: DbSession,
    demo_worktree: Path,
) -> None:
    task_run = create_task_run(db, demo_worktree)
    adapter = ScriptedMockAdapter()
    request = run_request(db, task_run, 'Change the demo heading text to "Welcome back".')

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
        run_request(db, first_run, "Build a login page for the demo app."),
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
        run_request(db, followup_run, 'Change the primary button text to "Sign in".'),
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
        db,
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
        db,
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
