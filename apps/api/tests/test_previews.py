import json
import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.main import app, get_db, get_preview_service
from app.external_workspaces import ExternalWorkspaceRegistration, register_external_project_target
from app.models import Agent, Artifact, Preview, Session, Task, TaskRun, TaskRunEvent, Workspace
from app.previews import PreviewError, PreviewProcess, PreviewService


REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def demo_worktree(tmp_path: Path) -> Path:
    worktree = tmp_path / "session-worktree"
    shutil.copytree(
        REPO_ROOT / "apps" / "demo",
        worktree / "apps" / "demo",
        ignore=shutil.ignore_patterns("node_modules"),
    )
    return worktree


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


@dataclass
class StartedCommand:
    command: list[str]
    cwd: Path


class RecordingRunner:
    def __init__(self) -> None:
        self.started: list[StartedCommand] = []
        self.stopped: list[int] = []

    def start(self, command: list[str], cwd: Path) -> PreviewProcess:
        self.started.append(StartedCommand(command=command, cwd=cwd))
        return PreviewProcess(pid=4242)

    def stop(self, process_id: int) -> None:
        self.stopped.append(process_id)


class StaticHealthChecker:
    def __init__(self, healthy: bool = True) -> None:
        self.healthy = healthy
        self.checked_urls: list[str] = []

    def is_healthy(self, url: str) -> bool:
        self.checked_urls.append(url)
        return self.healthy


def create_task_run_fixture(db: DbSession, worktree_path: Path) -> str:
    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="Preview session",
        bound_branch="main",
        worktree_path=str(worktree_path),
    )
    agent = Agent(
        name="Frontend Agent",
        role="frontend",
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
        state="completed",
        worktree_path=session.worktree_path,
    )
    db.add(workspace)
    db.add(session)
    db.add(agent)
    db.add(task)
    db.add(task_run)
    db.commit()
    db.refresh(task_run)
    return task_run.id


def create_external_task_run_fixture(
    db: DbSession,
    *,
    workspace_worktree: Path,
    external_root: Path,
) -> str:
    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    register_external_project_target(
        db,
        workspace,
        ExternalWorkspaceRegistration(
            target_id="external-vite-app",
            name="External Vite App",
            root_path=str(external_root),
            project_type="vite-react",
            allowed_paths=["src", "package.json", "index.html"],
            dev_command="pnpm dev --host 127.0.0.1 --port <port>",
            check_command="pnpm check",
            build_command="pnpm build",
            preview_command="pnpm dev --host 127.0.0.1 --port <port>",
            staging_output_dir="dist",
            staging_serve_command=(
                "python -m http.server <port> --bind 127.0.0.1 --directory dist"
            ),
            deploy_provider_ids=["local_staging"],
            package_manager="pnpm",
            detected_framework="vite-react",
        ),
    )
    session = Session(
        workspace_id=workspace.id,
        title="External preview session",
        bound_branch="main",
        worktree_path=str(workspace_worktree),
    )
    agent = Agent(
        name="Frontend Agent",
        role="frontend",
        adapter_type="codex",
        provider="local",
    )
    task = Task(
        session_id=session.id,
        title="Build external Vite app",
        intent_type="frontend_change",
        assigned_agent_id=agent.id,
        plan_json=json.dumps({"targetId": "external-vite-app"}, separators=(",", ":")),
    )
    task_run = TaskRun(
        task_id=task.id,
        agent_id=agent.id,
        state="completed",
        worktree_path=str(external_root),
    )
    db.add(session)
    db.add(agent)
    db.add(task)
    db.add(task_run)
    db.commit()
    db.refresh(task_run)
    return task_run.id


def test_start_preview_persists_vite_command_health_and_ready_event(
    db: DbSession,
    demo_worktree: Path,
) -> None:
    task_run_id = create_task_run_fixture(db, demo_worktree)
    runner = RecordingRunner()
    health = StaticHealthChecker(healthy=True)
    service = PreviewService(
        process_runner=runner,
        health_checker=health,
        port_allocator=lambda: 4317,
        health_attempts=1,
    )

    stored = service.start_task_run_preview(db, task_run_id)

    preview = db.get(Preview, stored.id)
    artifact = db.get(Artifact, stored.artifact_id)
    event = db.exec(
        select(TaskRunEvent).where(
            TaskRunEvent.task_run_id == task_run_id,
            TaskRunEvent.event_type == "artifact.preview.ready",
        )
    ).one()

    assert preview is not None
    assert artifact is not None
    assert artifact.artifact_type == "preview"
    assert artifact.status == "ready"
    assert preview.port == 4317
    assert preview.url == "http://127.0.0.1:4317"
    assert preview.command == "pnpm dev --host 127.0.0.1 --port 4317"
    assert preview.process_id == 4242
    assert preview.health_status == "healthy"
    assert preview.last_checked_at is not None
    metadata = json.loads(artifact.meta_json)
    payload = json.loads(event.payload_json)
    assert metadata["providerEvidence"]["taskRunId"] == task_run_id
    assert metadata["providerEvidence"]["adapterType"] == "scripted_mock"
    assert payload["providerEvidence"]["adapterType"] == "scripted_mock"
    assert runner.started == [
        StartedCommand(
            command=["pnpm", "dev", "--host", "127.0.0.1", "--port", "4317"],
            cwd=demo_worktree / "apps" / "demo",
        )
    ]
    assert "install" not in runner.started[0].command
    assert health.checked_urls == ["http://127.0.0.1:4317"]
    assert json.loads(event.payload_json)["previewId"] == preview.id


def test_start_preview_uses_external_target_root(
    db: DbSession,
    tmp_path: Path,
) -> None:
    external_root = tmp_path / "external-vite-app"
    external_root.mkdir()
    task_run_id = create_external_task_run_fixture(
        db,
        workspace_worktree=tmp_path / "session-worktree",
        external_root=external_root,
    )
    runner = RecordingRunner()
    service = PreviewService(
        process_runner=runner,
        health_checker=StaticHealthChecker(healthy=True),
        port_allocator=lambda: 4323,
        health_attempts=1,
    )

    stored = service.start_task_run_preview(db, task_run_id)

    assert stored.health_status == "healthy"
    assert runner.started == [
        StartedCommand(
            command=["pnpm", "dev", "--host", "127.0.0.1", "--port", "4323"],
            cwd=external_root.resolve(),
        )
    ]


def test_preview_api_starts_lists_and_stops_preview(
    db: DbSession,
    demo_worktree: Path,
) -> None:
    task_run_id = create_task_run_fixture(db, demo_worktree)
    runner = RecordingRunner()
    service = PreviewService(
        process_runner=runner,
        health_checker=StaticHealthChecker(healthy=True),
        port_allocator=lambda: 4318,
        health_attempts=1,
    )

    def override_db() -> Iterator[DbSession]:
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_preview_service] = lambda: service
    try:
        client = TestClient(app)
        create_response = client.post(f"/task-runs/{task_run_id}/preview")
        list_response = client.get(f"/task-runs/{task_run_id}/previews")
        task_run = db.get(TaskRun, task_run_id)
        assert task_run is not None
        task = db.get(Task, task_run.task_id)
        assert task is not None
        ledger_response = client.get(f"/sessions/{task.session_id}/ledger")
        preview_id = create_response.json()["id"]
        stop_response = client.post(f"/previews/{preview_id}/stop")
    finally:
        app.dependency_overrides.clear()

    assert create_response.status_code == 201
    assert list_response.status_code == 200
    assert stop_response.status_code == 200
    assert create_response.json()["healthStatus"] == "healthy"
    assert list_response.json()[0]["url"] == "http://127.0.0.1:4318"
    assert ledger_response.status_code == 200
    assert ledger_response.json()["latestPreviewId"] == preview_id
    assert ledger_response.json()["latestPreviewUrl"] == "http://127.0.0.1:4318"
    assert ledger_response.json()["latestPreviewHealth"] == "healthy"
    assert stop_response.json()["healthStatus"] == "stopped"
    assert runner.stopped == [4242]


def test_unhealthy_preview_persists_health_status_without_ready_event(
    db: DbSession,
    demo_worktree: Path,
) -> None:
    task_run_id = create_task_run_fixture(db, demo_worktree)
    service = PreviewService(
        process_runner=RecordingRunner(),
        health_checker=StaticHealthChecker(healthy=False),
        port_allocator=lambda: 4319,
        health_attempts=1,
    )

    stored = service.start_task_run_preview(db, task_run_id)

    preview = db.get(Preview, stored.id)
    ready_events = db.exec(
        select(TaskRunEvent).where(
            TaskRunEvent.task_run_id == task_run_id,
            TaskRunEvent.event_type == "artifact.preview.ready",
        )
    ).all()

    assert preview is not None
    assert preview.health_status == "unhealthy"
    assert preview.status_reason == "Preview did not respond to the health check."
    assert ready_events == []


def test_preview_rejects_failed_task_run(
    db: DbSession,
    demo_worktree: Path,
) -> None:
    task_run_id = create_task_run_fixture(db, demo_worktree)
    task_run = db.get(TaskRun, task_run_id)
    assert task_run is not None
    task_run.state = "failed"
    db.add(task_run)
    db.commit()
    service = PreviewService(
        process_runner=RecordingRunner(),
        health_checker=StaticHealthChecker(healthy=True),
        port_allocator=lambda: 4321,
        health_attempts=1,
    )

    with pytest.raises(PreviewError, match="completed TaskRun"):
        service.start_task_run_preview(db, task_run_id)


def test_preview_rejects_failed_dependency_prerequisite(
    db: DbSession,
    demo_worktree: Path,
) -> None:
    task_run_id = create_task_run_fixture(db, demo_worktree)
    task_run = db.get(TaskRun, task_run_id)
    assert task_run is not None
    task = db.get(Task, task_run.task_id)
    assert task is not None
    upstream = Task(
        session_id=task.session_id,
        title="Failed upstream",
        intent_type="backend_change",
        status="failed",
        assigned_agent_id=task.assigned_agent_id,
    )
    db.add(upstream)
    db.commit()
    db.refresh(upstream)
    task.depends_on_task_ids = json.dumps([upstream.id], separators=(",", ":"))
    db.add(task)
    db.commit()
    service = PreviewService(
        process_runner=RecordingRunner(),
        health_checker=StaticHealthChecker(healthy=True),
        port_allocator=lambda: 4322,
        health_attempts=1,
    )

    with pytest.raises(PreviewError, match="failed prerequisite"):
        service.start_task_run_preview(db, task_run_id)


def test_listing_preview_refreshes_health_and_emits_ready_event(
    db: DbSession,
    demo_worktree: Path,
) -> None:
    task_run_id = create_task_run_fixture(db, demo_worktree)
    health = StaticHealthChecker(healthy=False)
    service = PreviewService(
        process_runner=RecordingRunner(),
        health_checker=health,
        port_allocator=lambda: 4320,
        health_attempts=1,
    )
    created = service.start_task_run_preview(db, task_run_id)

    health.healthy = True
    listed = service.list_task_run_previews(db, task_run_id)

    preview = db.get(Preview, created.id)
    artifact = db.get(Artifact, created.artifact_id)
    ready_events = db.exec(
        select(TaskRunEvent).where(
            TaskRunEvent.task_run_id == task_run_id,
            TaskRunEvent.event_type == "artifact.preview.ready",
        )
    ).all()
    assert listed[0].health_status == "healthy"
    assert preview is not None
    assert preview.health_status == "healthy"
    assert artifact is not None
    assert artifact.status == "ready"
    assert len(ready_events) == 1
