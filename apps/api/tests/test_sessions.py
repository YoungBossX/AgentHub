import subprocess
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.dependencies import get_db, get_worktree_service
from app.main import app
from app.models import Agent, MemorySnapshot, Session, Task, TaskRun, Workspace
from app.scheduler import evaluate_scheduler_readiness
from app.task_run_scope import capture_worktree_scope_snapshot
from app.guardrails import evaluate_path
from app.repositories import next_session_title
from app.worktrees import WorktreeError, WorktreeService, safe_path_segment


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
        assert created[-1]["memorySnapshotId"]

    worktree_paths = {session["worktreePath"] for session in created}
    assert len(worktree_paths) == 3

    for path in worktree_paths:
        worktree = Path(path)
        assert worktree.exists()
        assert (worktree / ".git").exists()

    db_override = app.dependency_overrides[get_db]
    db_generator = db_override()
    db = next(db_generator)
    try:
        snapshot_ids = {session["memorySnapshotId"] for session in created}
        snapshots = db.exec(
            select(MemorySnapshot).where(MemorySnapshot.id.in_(snapshot_ids))
        ).all()
        assert len(snapshots) == 3
        assert all(snapshot.agents_md_hash for snapshot in snapshots)
        assert all(snapshot.context_pack_hash for snapshot in snapshots)
    finally:
        db_generator.close()

    list_response = client.get(f"/workspaces/{workspace['id']}/sessions")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert {session["id"] for session in listed} == {session["id"] for session in created}
    assert {session["worktreePath"] for session in listed} == worktree_paths


def test_session_worktree_reuses_setup_time_dependency_links(temp_repo: Path) -> None:
    (temp_repo / "node_modules").mkdir()
    (temp_repo / "apps/demo/node_modules").mkdir()
    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    service = WorktreeService(
        repo_root=temp_repo,
        worktrees_root=temp_repo / ".worktrees",
    )

    worktree = service.create_session_worktree(workspace, "dependency-links")

    assert (worktree / "node_modules").is_symlink()
    assert (worktree / "apps/demo/node_modules").is_symlink()
    assert (worktree / "node_modules").resolve() == (temp_repo / "node_modules")
    assert (worktree / "apps/demo/node_modules").resolve() == (
        temp_repo / "apps/demo/node_modules"
    )


def test_dependency_links_keep_historical_worktree_clean_and_scope_guarded(
    client: TestClient, temp_repo: Path,
) -> None:
    (temp_repo / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    run_git(temp_repo, "add", ".gitignore")
    run_git(temp_repo, "commit", "-m", "historical directory-only ignore")
    for relative in ("node_modules", "apps/demo/node_modules"):
        (temp_repo / relative).mkdir()
        (temp_repo / relative / "setup-marker.txt").write_text("preinstalled\n")
    excludes = temp_repo / ".git/info/exclude"
    original_excludes = excludes.read_bytes()
    workspace = client.get("/workspaces/demo").json()
    response = client.post(f"/workspaces/{workspace['id']}/sessions", json={"title": "Dependency setup"})
    assert response.status_code == 201
    created = response.json()
    worktree = Path(created["worktreePath"])
    status = subprocess.run(
        ["git", "-C", str(worktree), "status", "--porcelain", "--untracked-files=all"],
        check=True, capture_output=True, text=True,
    )
    assert status.stdout == ""
    assert excludes.read_bytes().startswith(original_excludes)
    assert (worktree / ".gitignore").read_text() == "node_modules/\n"
    before_links = {
        relative: (worktree / relative).lstat()
        for relative in ("node_modules", "apps/demo/node_modules")
    }
    excludes_after_setup = excludes.read_bytes()
    service = WorktreeService(repo_root=temp_repo, worktrees_root=temp_repo / ".worktrees")
    db_generator = app.dependency_overrides[get_db]()
    with next(db_generator) as db:
        stored_workspace = db.get(Workspace, workspace["id"])
        assert service.create_session_worktree(stored_workspace, created["id"]) == worktree
        assert excludes.read_bytes() == excludes_after_setup
        for relative, identity in before_links.items():
            assert (worktree / relative).lstat().st_ino == identity.st_ino
            assert (worktree / relative).is_symlink()
            assert evaluate_path(relative + "/setup-marker.txt", str(worktree)).allowed is False
        agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        task = Task(
            session_id=created["id"], title="Scoped write", intent_type="frontend_change",
            assigned_agent_id=agent.id,
            plan_json='{"targetId":"demo-frontend","safeTarget":"apps/demo/src","files":["apps/demo/src/App.tsx"]}',
        )
        db.add(task)
        db.commit()
        assert evaluate_scheduler_readiness(db, task).runnable is True
        baseline = capture_worktree_scope_snapshot(worktree, control_key="dependency-ignore-test")
        assert baseline.available is True
        (worktree / "unrelated.txt").write_text("unrelated dirty file\n")
        decision = evaluate_scheduler_readiness(db, task)
        assert decision.runnable is False
        assert decision.conflict_type == "dirty_worktree"
        # Change a protected link itself, without following or deleting it.
        (worktree / "secrets").mkdir()
        (worktree / "node_modules").rename(worktree / "secrets/old-dependency-link")
        alternate = temp_repo / "alternate-dependencies"
        alternate.mkdir()
        (worktree / "node_modules").symlink_to(alternate, target_is_directory=True)
        after = capture_worktree_scope_snapshot(worktree, control_key="dependency-ignore-test")
        assert after.available is True
        assert after.protected_control_digest != baseline.protected_control_digest


def test_dependency_setup_rejects_foreign_worktree_without_metadata_write(
    temp_repo: Path, tmp_path: Path,
) -> None:
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    run_git(foreign, "init")
    service = WorktreeService(repo_root=temp_repo, worktrees_root=tmp_path / "worktrees")
    workspace = Workspace(name="Demo", root_path="apps/demo", repo_url="local://apps/demo")
    destination = service.session_path(workspace.id, "foreign-session")
    destination.parent.mkdir(parents=True)
    # A foreign repository placed at a Session path must not gain setup writes.
    foreign.rename(destination)
    excludes = destination / ".git/info/exclude"
    original = excludes.read_bytes()
    with pytest.raises(WorktreeError, match="repository"):
        service.create_session_worktree(workspace, "foreign-session")
    assert excludes.read_bytes() == original
    assert not (destination / "node_modules").exists()


def test_dependency_setup_repairs_existing_links_without_replacing_them(temp_repo: Path) -> None:
    workspace = Workspace(name="Demo", root_path="apps/demo", repo_url="local://apps/demo")
    service = WorktreeService(repo_root=temp_repo, worktrees_root=temp_repo / ".worktrees")
    destination = service.session_path(workspace.id, "legacy-session")
    destination.parent.mkdir(parents=True)
    run_git(temp_repo, "worktree", "add", "--detach", str(destination), "HEAD")
    identities = {}
    for relative in ("node_modules", "apps/demo/node_modules"):
        (temp_repo / relative).mkdir()
        link = destination / relative
        link.symlink_to(temp_repo / relative, target_is_directory=True)
        identities[relative] = link.lstat().st_ino
    before = subprocess.run(
        ["git", "-C", str(destination), "status", "--porcelain"],
        check=True, capture_output=True, text=True,
    ).stdout
    assert "?? node_modules" in before
    assert service.create_session_worktree(workspace, "legacy-session") == destination
    after = subprocess.run(
        ["git", "-C", str(destination), "status", "--porcelain"],
        check=True, capture_output=True, text=True,
    ).stdout
    assert after == ""
    assert all((destination / relative).lstat().st_ino == identity for relative, identity in identities.items())


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_dependency_setup_rejects_redirected_exclude_file(
    temp_repo: Path, tmp_path: Path, link_kind: str,
) -> None:
    outside = tmp_path / "unassigned-exclude"
    outside.write_bytes(b"unassigned-content\n")
    excludes = temp_repo / ".git/info/exclude"
    excludes.rename(temp_repo / ".git/info/exclude.original")
    if link_kind == "symlink":
        excludes.symlink_to(outside)
    else:
        os.link(outside, excludes)
    workspace = Workspace(name="Demo", root_path="apps/demo", repo_url="local://apps/demo")
    service = WorktreeService(repo_root=temp_repo, worktrees_root=temp_repo / ".worktrees")
    with pytest.raises(WorktreeError, match="repository metadata must"):
        service.create_session_worktree(workspace, "redirected-exclude")
    assert outside.read_bytes() == b"unassigned-content\n"
    assert excludes.read_bytes() == b"unassigned-content\n"


def test_dependency_setup_ignores_inherited_git_repository_override(
    temp_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    foreign = tmp_path / "foreign-env"
    foreign.mkdir()
    run_git(foreign, "init")
    excludes = foreign / ".git/info/exclude"
    original = excludes.read_bytes()
    monkeypatch.setenv("GIT_DIR", str(foreign / ".git"))
    workspace = Workspace(name="Demo", root_path="apps/demo", repo_url="local://apps/demo")
    service = WorktreeService(repo_root=temp_repo, worktrees_root=temp_repo / ".worktrees")
    worktree = service.create_session_worktree(workspace, "git-env-override")
    assert (worktree / "apps/demo/README.md").read_text() == "demo app\n"
    assert excludes.read_bytes() == original
    assert b"/apps/demo/node_modules" in (temp_repo / ".git/info/exclude").read_bytes()


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


def test_safe_path_segment_preserves_valid_characters() -> None:
    assert safe_path_segment("abc123") == "abc123"
    assert safe_path_segment("session-1_test.v2") == "session-1_test.v2"
    assert safe_path_segment("ABCDEF") == "ABCDEF"


def test_safe_path_segment_replaces_special_characters() -> None:
    assert safe_path_segment("hello world") == "hello-world"
    assert safe_path_segment("path/to/file") == "path-to-file"
    assert safe_path_segment("a@b#c$d") == "a-b-c-d"
    assert safe_path_segment("  spaces  ") == "spaces"


def test_safe_path_segment_returns_fallback_for_all_special_input() -> None:
    assert safe_path_segment("") == "session"
    assert safe_path_segment("@@@") == "session"
    assert safe_path_segment("---") == "session"


def test_next_session_title_counts_existing_sessions(client: TestClient) -> None:
    db_override = app.dependency_overrides[get_db]
    db_generator = db_override()
    db = next(db_generator)
    try:
        workspace_response = client.get("/workspaces/demo").json()
        workspace_id = workspace_response["id"]

        # With zero sessions, next title should be "Session 1"
        title = next_session_title(db, workspace_id)
        assert title == "Session 1"

        # Create a session and verify increment
        client.post(
            f"/workspaces/{workspace_id}/sessions",
            json={"title": "Demo session"},
        )
        title2 = next_session_title(db, workspace_id)
        assert title2 == "Session 2"
    finally:
        db_generator.close()
