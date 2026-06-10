import asyncio
import shutil
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.main import app, get_db, get_preview_service
from app.models import Agent, Artifact, Deployment, Diff, Session, Task, TaskRun, Workspace
from app.previews import PreviewProcess, PreviewService
from app import run_engine as run_engine_module


REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass
class StartedPreview:
    command: list[str]
    cwd: Path


class RecordingPreviewRunner:
    def __init__(self) -> None:
        self.started: list[StartedPreview] = []

    def start(self, command: list[str], cwd: Path) -> PreviewProcess:
        self.started.append(StartedPreview(command=command, cwd=cwd))
        return PreviewProcess(pid=4242)

    def stop(self, process_id: int) -> None:
        return None


class HealthyPreview:
    def is_healthy(self, url: str) -> bool:
        return True


def create_demo_worktree(tmp_path: Path) -> Path:
    worktree = tmp_path / "session-worktree"
    shutil.copytree(
        REPO_ROOT / "apps" / "demo",
        worktree / "apps" / "demo",
        ignore=shutil.ignore_patterns("node_modules"),
    )
    subprocess.run(["git", "init"], cwd=worktree, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=worktree, check=True)
    subprocess.run(["git", "config", "user.name", "AgentHub Test"], cwd=worktree, check=True)
    subprocess.run(["git", "add", "apps/demo"], cwd=worktree, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=worktree, check=True, capture_output=True)
    return worktree


def seed_codex_task(db: DbSession, worktree_path: Path) -> str:
    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="Recovery session",
        bound_branch="main",
        worktree_path=str(worktree_path),
    )
    agent = Agent(
        name="Frontend Agent",
        role="frontend",
        adapter_type="codex",
        provider="local",
    )
    task = Task(
        session_id=session.id,
        title="Build login page",
        intent_type="frontend_change",
        assigned_agent_id=agent.id,
    )
    db.add(workspace)
    db.add(session)
    db.add(agent)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task.id


def test_forced_codex_failure_recovers_through_scripted_diff_preview_and_deploy(
    tmp_path: Path,
) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    worktree = create_demo_worktree(tmp_path)

    with DbSession(engine) as db:
        task_id = seed_codex_task(db, worktree)

    def override_db() -> Iterator[DbSession]:
        with DbSession(engine) as db:
            yield db

    preview_runner = RecordingPreviewRunner()
    preview_service = PreviewService(
        process_runner=preview_runner,
        health_checker=HealthyPreview(),
        port_allocator=lambda: 4555,
    )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_preview_service] = lambda: preview_service
    try:
        client = TestClient(app)
        failed = client.post(f"/tasks/{task_id}/runs/force-codex-failure").json()
        with DbSession(engine) as db:
            asyncio.run(run_engine_module.RunWorker(worker_id="worker:forced-failure").run_once(db))
            failed_run = db.get(TaskRun, failed["id"])
            failed["state"] = failed_run.state
            failed["errorCode"] = failed_run.error_code

        fallback = client.post(f"/task-runs/{failed['id']}/retry-with-fallback").json()
        with DbSession(engine) as db:
            asyncio.run(run_engine_module.RunWorker(worker_id="worker:fallback").run_once(db))
            fallback_run = db.get(TaskRun, fallback["id"])
            fallback["state"] = fallback_run.state

        preview = client.post(f"/task-runs/{fallback['id']}/preview").json()
        deployment = client.post(f"/previews/{preview['id']}/deploy").json()
        task = client.get(f"/sessions/{fallback['sessionId']}/tasks").json()[0]
    finally:
        app.dependency_overrides.clear()

    app_source = (worktree / "apps/demo/src/App.tsx").read_text()
    status = subprocess.run(
        ["git", "status", "--short", "apps/demo/src/App.tsx"],
        cwd=worktree,
        check=True,
        capture_output=True,
        text=True,
    )

    assert failed["state"] == "failed"
    assert failed["errorCode"] == "CODEX_DEMO_FORCED_FAILURE"
    assert fallback["state"] == "completed"
    assert fallback["adapterType"] == "scripted_mock"
    assert "Welcome back" in app_source
    assert "M apps/demo/src/App.tsx" in status.stdout
    assert [run["id"] for run in task["taskRuns"]] == [failed["id"], fallback["id"]]
    assert task["taskRuns"][0]["state"] == "failed"
    assert task["taskRuns"][1]["state"] == "completed"
    assert preview["healthStatus"] == "healthy"
    assert deployment["provider"] == "mock"

    with DbSession(engine) as db:
        diff_artifact = db.exec(
            select(Artifact).where(
                Artifact.task_run_id == fallback["id"],
                Artifact.artifact_type == "diff",
            )
        ).one()
        diff = db.exec(select(Diff).where(Diff.artifact_id == diff_artifact.id)).one()
        deploy = db.exec(select(Deployment)).one()
        assert "Welcome back" in diff.patch_text
        assert deploy.artifact_id == deployment["artifactId"]
