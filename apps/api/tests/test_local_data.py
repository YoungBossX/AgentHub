import json
import socket
import sqlite3
import subprocess
from pathlib import Path

import pytest

from app.local_data import DataMaintenanceError, digest, git, restore, snapshot, verify_snapshot
from app.maintenance_lease import MaintenanceBusy, database_lease


@pytest.fixture
def data_workspace(tmp_path):
    repo = tmp_path / "source"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.name", "Local fixture")
    git(repo, "config", "user.email", "fixture@example.test")
    (repo / ".gitignore").write_text(".worktrees/\ndata/\nnode_modules/\n.env*\n__pycache__/\n.pytest_cache/\n", encoding="utf-8")
    (repo / "file.txt").write_text("base\n", encoding="utf-8")
    (repo / "deleted.txt").write_text("retain deletion\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "-m", "fixture")
    tree = repo / ".worktrees/session"
    git(repo, "worktree", "add", "--detach", str(tree), "HEAD")
    (tree / "file.txt").write_bytes(b"staged\r\n")
    git(tree, "add", "file.txt")
    (tree / "file.txt").write_bytes(b"unstaged\r\n")
    (tree / "deleted.txt").unlink()
    (tree / "untracked.txt").write_text("untracked 原文😀", encoding="utf-8")
    (repo / "new-source.py").write_text("value = 3\n", encoding="utf-8")
    database = repo / "data/workspace.sqlite3"
    database.parent.mkdir()
    db = sqlite3.connect(database)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE session (id TEXT PRIMARY KEY, worktree_path TEXT)")
    db.execute("CREATE TABLE taskrun (id TEXT PRIMARY KEY, worktree_path TEXT, state TEXT, metrics_json TEXT)")
    db.execute("CREATE TABLE message (id TEXT PRIMARY KEY, content_md TEXT, attachment BLOB)")
    db.execute("INSERT INTO session VALUES ('s', ?)", (str(tree),))
    db.execute("INSERT INTO taskrun VALUES ('r', ?, 'completed', '{}')", (str(tree),))
    db.execute("INSERT INTO message VALUES ('m', '完整历史😀', ?)", (b"attachment\0bytes",))
    db.commit()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    yield repo, tree, database, db, port
    db.close()


def test_wal_snapshot_rehearsal_and_missing_original_restore(data_workspace, tmp_path):
    repo, tree, database, db, port = data_workspace
    assert database.with_name(database.name + "-wal").exists()
    source_head = git(repo, "rev-parse", "HEAD")
    status = git(tree, "status", "--porcelain")
    source_index = digest(tree / git(tree, "rev-parse", "--git-path", "index").decode().strip())
    backup = tmp_path / "snapshot"
    result = snapshot(repo, database, backup, api_port=port)
    assert result["state"] == "verified"
    manifest = verify_snapshot(backup)
    with sqlite3.connect(backup / "repo/data/workspace.sqlite3") as saved:
        assert saved.execute("SELECT content_md, attachment FROM message").fetchone() == ("完整历史😀", b"attachment\0bytes")
    rehearsal = tmp_path / "rehearsal"
    assert restore(backup, rehearsal)["state"] == "rehearsal-verified"
    restored_tree = rehearsal / ".worktrees/session"
    assert git(restored_tree, "status", "--porcelain") == status
    assert (restored_tree / "file.txt").read_bytes() == b"unstaged\r\n"
    assert not (restored_tree / "deleted.txt").exists()
    assert (restored_tree / "untracked.txt").read_text(encoding="utf-8") == "untracked 原文😀"
    assert (rehearsal / "new-source.py").exists()
    assert git(repo, "rev-parse", "HEAD") == source_head
    assert digest(tree / git(tree, "rev-parse", "--git-path", "index").decode().strip()) == source_index
    with pytest.raises(DataMaintenanceError, match="new destination"):
        restore(backup, repo, original_paths=True, confirm_id=result["snapshotId"])
    db.close()
    retired = tmp_path / "retired-source"
    repo.rename(retired)
    with pytest.raises(DataMaintenanceError, match="snapshot ID"):
        restore(backup, repo, original_paths=True, confirm_id="wrong")
    restored = restore(backup, repo, original_paths=True, confirm_id=result["snapshotId"])
    assert restored["state"] == "restored-original-paths"
    assert git(tree, "status", "--porcelain") == status
    assert git(repo, "rev-parse", "HEAD") == source_head
    with sqlite3.connect(repo / manifest["database"]) as recovered:
        assert recovered.execute("SELECT worktree_path FROM session").fetchone() == (str(tree),)
        assert recovered.execute("SELECT content_md FROM message").fetchone() == ("完整历史😀",)


def test_shared_runtime_and_exclusive_maintenance_exclusion(data_workspace):
    _, _, database, _, _ = data_workspace
    with database_lease(database, exclusive=False):
        with database_lease(database, exclusive=False):
            with pytest.raises(MaintenanceBusy):
                with database_lease(database, exclusive=True):
                    pytest.fail("exclusive lease must not enter")
    with database_lease(database, exclusive=True):
        with pytest.raises(MaintenanceBusy):
            with database_lease(database, exclusive=False):
                pytest.fail("API must not enter during maintenance")
    with database_lease(database, exclusive=True):
        pass


@pytest.mark.parametrize("kind", ["active", "missing-tree", "api-port", "tamper", "linked-file", "git-lock", "existing-output"])
def test_refuses_unsafe_or_inconsistent_capture(data_workspace, tmp_path, kind):
    repo, tree, database, db, port = data_workspace
    output = tmp_path / "snapshot"
    listener = None
    if kind == "active":
        db.execute("UPDATE taskrun SET state='streaming'"); db.commit()
    elif kind == "missing-tree":
        db.execute("UPDATE session SET worktree_path=?", (str(tmp_path / "missing"),)); db.commit()
    elif kind == "api-port":
        listener = socket.socket(); listener.bind(("127.0.0.1", 0)); listener.listen()
        port = listener.getsockname()[1]
    elif kind == "linked-file":
        source = repo / "linked.txt"
        try:
            source.symlink_to(tmp_path / "outside")
        except OSError:
            pytest.skip("OS denies test symlinks")
    elif kind == "git-lock":
        (repo / ".git/index.lock").write_text("busy")
    elif kind == "existing-output":
        output.mkdir()
    try:
        if kind == "tamper":
            snapshot(repo, database, output, api_port=port)
            (output / "repo/file.txt").write_text("changed")
            with pytest.raises(DataMaintenanceError, match="inventory"):
                verify_snapshot(output)
        else:
            with pytest.raises((DataMaintenanceError, MaintenanceBusy)):
                snapshot(repo, database, output, api_port=port)
            assert not (output / "manifest.json").exists()
    finally:
        if listener:
            listener.close()


def test_cli_verify_and_manifest_corruption(data_workspace, tmp_path):
    repo, _, database, _, port = data_workspace
    output = tmp_path / "snapshot"
    snapshot(repo, database, output, api_port=port)
    import sys
    command = [sys.executable, str(Path(__file__).resolve().parents[3] / "scripts/local-data.py"), "verify", "--snapshot", str(output)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0 and json.loads(result.stdout)["state"] == "verified"
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    manifest["originalRoot"] = str(tmp_path / "elsewhere")
    (output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 1 and "integrity mismatch" in result.stderr


def test_source_changes_and_live_preview_are_not_snapshot_success(data_workspace, tmp_path, monkeypatch):
    from app import local_data
    repo, _, database, db, port = data_workspace
    db.execute("CREATE TABLE preview (health_status TEXT, process_id INTEGER)")
    db.execute("INSERT INTO preview VALUES ('unhealthy', 12345)"); db.commit()
    with pytest.raises(DataMaintenanceError, match="previews"):
        snapshot(repo, database, tmp_path / "active", api_port=port)
    db.execute("UPDATE preview SET health_status='stopped', process_id=NULL"); db.commit()
    copy = local_data.copy_new_file
    def mutate(source, target):
        result = copy(source, target)
        if source == repo / "file.txt":
            source.write_text("concurrent edit", encoding="utf-8")
        return result
    monkeypatch.setattr(local_data, "copy_new_file", mutate)
    with pytest.raises(DataMaintenanceError, match="changed"):
        snapshot(repo, database, tmp_path / "changed", api_port=port)
    assert not (tmp_path / "changed/manifest.json").exists()


def test_api_lease_excludes_an_independent_process(data_workspace):
    import os
    import sys
    _, _, database, _, _ = data_workspace
    code = "from pathlib import Path; from app.maintenance_lease import database_lease; import sys\nwith database_lease(Path(sys.argv[1]), exclusive=True): print('entered')"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    with database_lease(database, exclusive=False):
        result = subprocess.run([sys.executable, "-c", code, str(database)], env=env, capture_output=True, text=True)
        assert result.returncode != 0 and "entered" not in result.stdout and "MaintenanceBusy" in result.stderr
    result = subprocess.run([sys.executable, "-c", code, str(database)], env=env, capture_output=True, text=True)
    assert result.returncode == 0 and result.stdout.strip() == "entered"


@pytest.mark.anyio
async def test_api_lifespan_holds_and_releases_the_database_lease(data_workspace, monkeypatch):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    from app import main
    _, _, database, _, _ = data_workspace
    entered = []
    @asynccontextmanager
    async def runtime():
        entered.append(True)
        yield
    monkeypatch.setattr(main, "engine", SimpleNamespace(url="sqlite:///" + database.as_posix()))
    monkeypatch.setattr(main, "_runtime_lifespan", runtime)
    async with main.lifespan(main.app):
        assert entered == [True]
        with pytest.raises(MaintenanceBusy):
            with database_lease(database, exclusive=True):
                pytest.fail("maintenance entered while API is alive")
    with database_lease(database, exclusive=True):
        with pytest.raises(MaintenanceBusy):
            async with main.lifespan(main.app):
                pytest.fail("API entered while maintenance is active")
    assert entered == [True]


@pytest.mark.parametrize("unsafe", ["../escape", "/absolute", "C:/escape", "a/../escape", "a\\escape"])
def test_rehashed_manifest_cannot_escape_file_scope(data_workspace, tmp_path, unsafe):
    from app.local_data import json_hash
    repo, _, database, _, port = data_workspace
    output = tmp_path / "snapshot"
    snapshot(repo, database, output, api_port=port)
    path = output / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["files"][0]["path"] = unsafe
    manifest["snapshotId"] = json_hash({key: value for key, value in manifest.items() if key != "snapshotId"})
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(DataMaintenanceError, match="relative snapshot path"):
        restore(output, tmp_path / "rehearsal")
    assert not (tmp_path / "rehearsal").exists()


def test_foreign_key_failure_does_not_publish_complete_snapshot(data_workspace, tmp_path):
    repo, _, database, db, port = data_workspace
    db.execute("CREATE TABLE child (parent_id TEXT REFERENCES session(id))")
    db.execute("INSERT INTO child VALUES ('missing')"); db.commit()
    with pytest.raises(DataMaintenanceError, match="foreign-key"):
        snapshot(repo, database, tmp_path / "snapshot", api_port=port)
    assert not (tmp_path / "snapshot/manifest.json").exists()


def test_detached_execution_commit_and_saved_hooks_are_preserved_without_execution(data_workspace, tmp_path):
    repo, _, database, _, port = data_workspace
    execution = repo / ".worktrees/.executions-s/run"
    git(repo, "worktree", "add", "--detach", str(execution), "HEAD")
    (execution / "file.txt").write_text("isolated commit\n")
    git(execution, "add", "file.txt")
    git(execution, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "-m", "isolated")
    detached = git(execution, "rev-parse", "HEAD")
    sentinel = tmp_path / "hook-executed"
    hook = repo / ".git/hooks/post-checkout"
    hook.write_text("#!/bin/sh\ntouch '" + sentinel.as_posix() + "'\n")
    hook.chmod(0o755)
    snapshot(repo, database, tmp_path / "snapshot", api_port=port)
    restore(tmp_path / "snapshot", tmp_path / "rehearsal")
    copy = tmp_path / "rehearsal/.worktrees/.executions-s/run"
    assert git(copy, "rev-parse", "HEAD") == detached
    assert (copy / "file.txt").read_text() == "isolated commit\n"
    assert not sentinel.exists()


def test_restore_owns_database_lease_and_never_overwrites_a_concurrent_file(data_workspace, tmp_path, monkeypatch):
    from app import local_data
    repo, _, database, _, port = data_workspace
    backup = tmp_path / "snapshot"
    snapshot(repo, database, backup, api_port=port)
    target = tmp_path / "rehearsal"
    copy = local_data.copy_new_file
    checked = []
    def guarded(source, destination):
        with pytest.raises(MaintenanceBusy):
            with database_lease(target / database.relative_to(repo), exclusive=False):
                pytest.fail("API entered while restore is writing")
        checked.append(True)
        return copy(source, destination)
    monkeypatch.setattr(local_data, "copy_new_file", guarded)
    restore(backup, target)
    assert checked
    with database_lease(target / database.relative_to(repo), exclusive=True):
        pass
    collision = tmp_path / "collision.txt"
    collision.write_text("concurrent writer")
    with pytest.raises(FileExistsError):
        copy(repo / "file.txt", collision)
    assert collision.read_text() == "concurrent writer"
