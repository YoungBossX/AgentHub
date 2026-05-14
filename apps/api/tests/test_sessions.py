import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.main import app, get_db, get_worktree_service
from app.models import Agent, Session, Task, TaskRun, Workspace
from app.worktrees import WorktreeService


def run_git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
    run_git(repo, "config", "user.email", "demo@agenthub.local")
    run_git(repo, "config", "user.name", "AgentHub Test")

    demo_root = repo / "apps" / "demo"
    demo_root.mkdir(parents=True)
    (demo_root / "README.md").write_text("demo app\n")
    run_git(repo, "add", ".")
    run_git(repo, "commit", "-m", "seed demo")
    run_git(repo, "branch", "-M", "main")
    return repo


@pytest.fixture
def client(temp_repo: Path) -> Iterator[TestClient]:
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
        agent = Agent(
            name="Frontend Agent",
            role="frontend",
            adapter_type="codex",
            provider="local",
            enabled=True,
        )
        db.add(workspace)
        db.add(agent)
        db.commit()

    def override_db() -> Iterator[DbSession]:
        with DbSession(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_worktree_service] = lambda: WorktreeService(
        repo_root=temp_repo,
        worktrees_root=temp_repo / ".worktrees",
    )

    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_create_three_sessions_persists_unique_worktree_paths(
    client: TestClient,
) -> None:
    workspace_response = client.get("/workspaces/demo")

    assert workspace_response.status_code == 200
    workspace = workspace_response.json()
    assert workspace["rootPath"] == "apps/demo"

    created = []
    for index in range(1, 4):
        response = client.post(
            f"/workspaces/{workspace['id']}/sessions",
            json={"title": f"Demo session {index}"},
        )
        assert response.status_code == 201
        created.append(response.json())

    worktree_paths = {session["worktreePath"] for session in created}
    assert len(worktree_paths) == 3

    for path in worktree_paths:
        worktree = Path(path)
        assert worktree.exists()
        assert (worktree / ".git").exists()

    list_response = client.get(f"/workspaces/{workspace['id']}/sessions")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert {session["id"] for session in listed} == {session["id"] for session in created}
    assert {session["worktreePath"] for session in listed} == worktree_paths


def test_task_run_can_reuse_session_worktree_path(client: TestClient) -> None:
    workspace = client.get("/workspaces/demo").json()
    created_session = client.post(
        f"/workspaces/{workspace['id']}/sessions",
        json={"title": "Reusable worktree"},
    ).json()

    db_override = app.dependency_overrides[get_db]
    db_generator = db_override()
    db = next(db_generator)
    try:
        session = db.exec(
            select(Session).where(Session.id == created_session["id"])
        ).one()
        agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        task = Task(
            session_id=session.id,
            title="Future frontend task",
            intent_type="frontend_change",
            assigned_agent_id=agent.id,
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        task_run = TaskRun(
            task_id=task.id,
            agent_id=agent.id,
            state="created",
            worktree_path=session.worktree_path,
        )
        db.add(task_run)
        db.commit()
        db.refresh(task_run)

        assert task_run.worktree_path == session.worktree_path
        assert task_run.worktree_path == created_session["worktreePath"]
    finally:
        db_generator.close()
