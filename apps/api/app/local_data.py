"""Offline, local-only developer maintenance. Never used by an Agent adapter."""
import hashlib
import json
import os
import re
import shutil
import socket
import sqlite3
import stat
import subprocess
from contextlib import closing, contextmanager
from pathlib import Path, PurePosixPath

from app.maintenance_lease import database_lease

SCHEMA = "agenthub.local-snapshot.v1"
MAX_FILES, MAX_BYTES, MAX_FILE = 100_000, 4 * 1024**3, 512 * 1024**2
TERMINAL = {"completed", "failed", "interrupted", "cancelled", "denied"}
EXCLUDED = {"node_modules", ".venv", "__pycache__", ".pytest_cache", ".next", ".agenthub-maintenance"}


class DataMaintenanceError(RuntimeError):
    pass


def canonical(path):
    path = Path(path).absolute()
    if path.resolve() != path:
        raise DataMaintenanceError("Paths must not traverse symbolic links or junctions.")
    return path


def regular(path):
    path = canonical(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or getattr(info, "st_file_attributes", 0) & 0x400:
        raise DataMaintenanceError("Only single regular files can be captured or restored.")
    return info


def relative(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or "\0" in value:
        raise DataMaintenanceError("Invalid relative snapshot path.")
    parts = PurePosixPath(value).parts
    if value.startswith("/") or any(part in {".", ".."} for part in parts) or "/".join(parts) != value:
        raise DataMaintenanceError("Invalid relative snapshot path.")
    return Path(*parts)


def digest(path):
    regular(path)
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024**2), b""):
            result.update(block)
    return result.hexdigest()


def json_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


def copy_new_file(source, target):
    regular(source)
    canonical(target)
    with Path(source).open("rb") as reader, Path(target).open("xb") as writer:
        shutil.copyfileobj(reader, writer, length=1024**2)
        writer.flush()
        os.fsync(writer.fileno())


def git(root, *args):
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0", GIT_NO_REPLACE_OBJECTS="1", GIT_OPTIONAL_LOCKS="0")
    try:
        result = subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull, "-c", "core.fsmonitor=false",
            "-c", "core.untrackedCache=false", "-c", "core.quotePath=false", "-C", str(root), *args],
            env=env, capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DataMaintenanceError("Local Git verification is unavailable.") from exc
    if result.returncode:
        raise DataMaintenanceError("Local Git verification failed: " + " ".join(args[:2]))
    return result.stdout


def _tables(db):
    return {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _columns(db, table):
    return {row[1] for row in db.execute('PRAGMA table_info("' + table.replace('"', '""') + '")')}


def _check_idle(db):
    tables = _tables(db)
    for table, column, terminal in (("taskrun", "state", TERMINAL),
            ("previewdeployjob", "state", TERMINAL | {"succeeded"}),
            ("targetlock", "state", {"released"})):
        if table in tables:
            values = ",".join("?" for _ in terminal)
            if db.execute(f'SELECT 1 FROM "{table}" WHERE "{column}" NOT IN ({values}) LIMIT 1', tuple(terminal)).fetchone():
                raise DataMaintenanceError("Active execution/lock/job exists; stop or interrupt work first.")
    if "preview" in tables and {"health_status", "process_id"}.issubset(_columns(db, "preview")):
        if db.execute("SELECT 1 FROM preview WHERE process_id IS NOT NULL OR health_status IN ('healthy','starting') LIMIT 1").fetchone():
            raise DataMaintenanceError("Stop saved live previews before maintenance.")


@contextmanager
def offline(database, *, api_port=8000):
    database = canonical(database)
    regular(database)
    if not 1 <= api_port <= 65535:
        raise DataMaintenanceError("Invalid local API port.")
    with database_lease(database, exclusive=True):
        with socket.socket() as probe:
            probe.settimeout(.2)
            if probe.connect_ex(("127.0.0.1", api_port)) == 0:
                raise DataMaintenanceError("Configured API port is listening; stop the local API first.")
        db = sqlite3.connect(database.as_uri() + "?mode=rw", uri=True, timeout=1)
        try:
            # Blocks other SQLite writers, including older processes without the
            # API lifetime lease. It does not stop an independent filesystem editor.
            db.execute("BEGIN IMMEDIATE")
            _check_idle(db)
            yield db
        except sqlite3.Error as exc:
            raise DataMaintenanceError("SQLite is busy or unavailable for consistent maintenance.") from exc
        finally:
            db.rollback()
            db.close()


def roots_for(repo, db):
    repo = canonical(repo)
    if canonical(repo / ".git") != repo / ".git" or not (repo / ".git").is_dir():
        raise DataMaintenanceError("Use the primary checkout with an owned .git directory.")
    if git(repo, "rev-parse", "--show-object-format").strip() != b"sha1":
        raise DataMaintenanceError("This snapshot format supports ordinary SHA-1 Git repositories only.")
    config = dict(entry.decode("utf-8").split("\n", 1) for entry in git(repo, "config", "--null", "--local", "--list").split(b"\0") if b"\n" in entry)
    if config.get("core.repositoryformatversion", "0") != "0" or any(key.startswith("extensions.") for key in config):
        raise DataMaintenanceError("Extended Git storage/configuration needs a separate backup workflow.")
    if (repo / ".git/objects/info/alternates").exists() or (repo / ".git/modules").exists():
        raise DataMaintenanceError("External object stores and submodules need a separate backup workflow.")
    entries = git(repo, "worktree", "list", "--porcelain", "-z").split(b"\0\0")
    roots = []
    for entry in entries:
        fields = entry.split(b"\0")
        paths = [field[9:].decode("utf-8") for field in fields if field.startswith(b"worktree ")]
        if not paths:
            continue
        root = canonical(paths[0])
        if root != repo and not root.is_relative_to(repo / ".worktrees"):
            raise DataMaintenanceError("Registered worktree is outside the managed .worktrees directory.")
        if not root.is_dir() or canonical(git(root, "rev-parse", "--show-toplevel").decode().strip()) != root:
            raise DataMaintenanceError("A registered worktree is missing or has a foreign root.")
        if canonical(git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").decode().strip()) != repo / ".git":
            raise DataMaintenanceError("A registered worktree belongs to a foreign repository.")
        roots.append(root)
    known = {str(root) for root in roots}
    for table in ("session", "taskrun"):
        if table in _tables(db):
            for row in db.execute(f'SELECT DISTINCT worktree_path FROM "{table}"'):
                if str(canonical(row[0])) not in known:
                    raise DataMaintenanceError("A persisted Session/Run worktree is missing from the managed Git registry.")
    if not roots or repo not in roots:
        raise DataMaintenanceError("The primary repository is missing from its worktree registry.")
    return sorted(roots)


def _walk_files(directory):
    canonical(directory)
    count = 0
    for base, directories, names in os.walk(directory, followlinks=False):
        count += len(directories) + len(names)
        if count > MAX_FILES:
            raise DataMaintenanceError("Directory inventory exceeds limits.")
        for name in directories:
            canonical(Path(base) / name)
        for name in names:
            path = Path(base) / name
            regular(path)
            yield path


def _source_paths(repo, roots, *, database=None):
    paths = set(_walk_files(repo / ".git"))
    if any(path.name.endswith(".lock") for path in paths):
        raise DataMaintenanceError("A Git lock exists; finish Git operations before backup.")
    for root in roots:
        if root != repo:
            paths.add(root / ".git")
        tracked = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").split(b"\0")
        for name in tracked:
            if not name:
                continue
            rel = relative(name.decode("utf-8"))
            if any(part in EXCLUDED or part == "secrets" or part.startswith(".env") for part in rel.parts):
                continue
            db_suffixes = tuple(suffix + tail for suffix in (".sqlite3", ".db", ".sqlite") for tail in ("", "-wal", "-shm", "-journal"))
            if rel.parts[0] in {".git", ".worktrees"} or rel.name.endswith((*db_suffixes, ".maintenance.lock")):
                continue
            path = root / rel
            if database is not None and path in {database, *(database.with_name(database.name + suffix) for suffix in ("-wal", "-shm", "-journal", ".maintenance.lock"))}:
                continue
            if path.exists() or path.is_symlink():
                regular(path)
                paths.add(path)
    return sorted(paths)


def inventory_files(paths, root):
    entries, total = [], 0
    for path in paths:
        info = regular(path)
        total += info.st_size
        if len(entries) >= MAX_FILES or info.st_size > MAX_FILE or total > MAX_BYTES:
            raise DataMaintenanceError("Snapshot exceeds bounded file/byte limits.")
        entries.append({"path": path.relative_to(root).as_posix(), "bytes": info.st_size,
            "sha256": digest(path), "mode": stat.S_IMODE(info.st_mode)})
    return entries


def _fresh_destination(destination, repo):
    destination = canonical(destination)
    if destination.exists() or destination.is_relative_to(repo) or repo.is_relative_to(destination):
        raise DataMaintenanceError("Use a new external destination; never overwrite or nest a snapshot in the source.")
    destination.mkdir(mode=0o700, parents=True)
    return destination


def snapshot(repo, database, destination, *, api_port=8000):
    repo, database = canonical(repo), canonical(database)
    if not database.is_relative_to(repo) or database.is_relative_to(repo / ".git") or database.is_relative_to(repo / ".worktrees"):
        raise DataMaintenanceError("The SQLite file must be under the primary repository's data area.")
    with offline(database, api_port=api_port) as db:
        roots = roots_for(repo, db)
        files = inventory_files(_source_paths(repo, roots, database=database), repo)
        heads = [{"path": root.relative_to(repo).as_posix(), "head": git(root, "rev-parse", "HEAD").decode().strip(),
            "indexEntriesHash": hashlib.sha256(git(root, "ls-files", "--stage", "-z")).hexdigest()} for root in roots]
        destination = _fresh_destination(destination, repo)
        mirror = destination / "repo"
        mirror.mkdir()
        # SQLite backup uses a second read connection while the reservation above
        # excludes writers. Copying a .sqlite3 file alone would miss WAL pages.
        target_db = mirror / database.relative_to(repo)
        target_db.parent.mkdir(parents=True, exist_ok=True)
        reader = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
        output = sqlite3.connect(target_db)
        try:
            reader.backup(output)
            output.execute("PRAGMA journal_mode=DELETE")
        finally:
            output.close(); reader.close()
        for entry in files:
            source, target = repo / relative(entry["path"]), mirror / relative(entry["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            copy_new_file(source, target)
            target.chmod(entry["mode"])
            if digest(target) != entry["sha256"]:
                raise DataMaintenanceError("A file changed during snapshot capture.")
        if inventory_files(_source_paths(repo, roots, database=database), repo) != files:
            raise DataMaintenanceError("Source changed during capture; snapshot is incomplete.")
        files.append({"path": database.relative_to(repo).as_posix(), "bytes": target_db.stat().st_size,
            "sha256": digest(target_db), "mode": stat.S_IMODE(target_db.stat().st_mode)})
        files.sort(key=lambda row: row["path"])
        manifest = {"schema": SCHEMA, "originalRoot": str(repo), "database": database.relative_to(repo).as_posix(),
            "roots": heads, "files": files, "excluded": ["ignored files/build outputs/dependencies", ".env* and secrets", "external registered target source directories"],
            "activation": "same original paths only; rehearsal does not rewrite persisted evidence"}
        manifest["snapshotId"] = json_hash(manifest)
        write_json(destination / "manifest.json", manifest)
        try:
            verify_snapshot(destination)
        except Exception:
            (destination / "manifest.json").unlink()
            raise
        return {"snapshotId": manifest["snapshotId"], "files": len(files), "bytes": sum(row["bytes"] for row in files),
            "worktrees": len(roots), "destination": str(destination), "state": "verified"}


def verify_snapshot(directory):
    directory = canonical(directory)
    manifest_path = directory / "manifest.json"
    regular(manifest_path)
    if manifest_path.stat().st_size > 32 * 1024**2:
        raise DataMaintenanceError("Manifest exceeds size limit.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise DataMaintenanceError("Unsupported snapshot schema.")
    identity = manifest.get("snapshotId")
    if identity != json_hash({key: value for key, value in manifest.items() if key != "snapshotId"}):
        raise DataMaintenanceError("Snapshot manifest integrity mismatch.")
    files = manifest.get("files", [])
    if not isinstance(files, list) or not files or len(files) > MAX_FILES:
        raise DataMaintenanceError("Invalid snapshot file inventory.")
    for row in files:
        if not isinstance(row, dict) or set(row) != {"path", "bytes", "sha256", "mode"}:
            raise DataMaintenanceError("Invalid snapshot file entry.")
        relative(row["path"])
        if type(row["bytes"]) is not int or not 0 <= row["bytes"] <= MAX_FILE or type(row["mode"]) is not int or not 0 <= row["mode"] <= 0o777:
            raise DataMaintenanceError("Invalid snapshot file size/mode.")
        if not isinstance(row["sha256"], str) or not re.fullmatch("[a-f0-9]{64}", row["sha256"]):
            raise DataMaintenanceError("Invalid snapshot file hash.")
    if len({row["path"] for row in files}) != len(files):
        raise DataMaintenanceError("Duplicate snapshot path.")
    if not isinstance(manifest.get("originalRoot"), str) or not Path(manifest["originalRoot"]).is_absolute():
        raise DataMaintenanceError("Invalid original repository identity.")
    db_rel = relative(manifest.get("database"))
    if db_rel.parts[0] in {".git", ".worktrees"} or db_rel.as_posix() not in {row["path"] for row in files}:
        raise DataMaintenanceError("Invalid snapshot database location.")
    roots = manifest.get("roots")
    if not isinstance(roots, list) or not roots or len(roots) > 1000 or sum(item.get("path") == "." for item in roots if isinstance(item, dict)) != 1:
        raise DataMaintenanceError("Invalid snapshot worktree inventory.")
    known_roots = set()
    for item in roots:
        if not isinstance(item, dict) or set(item) != {"path", "head", "indexEntriesHash"}:
            raise DataMaintenanceError("Invalid snapshot worktree entry.")
        if item["path"] != "." and relative(item["path"]).parts[0] != ".worktrees":
            raise DataMaintenanceError("Worktree is outside the managed root.")
        if item["path"] in known_roots or not re.fullmatch("[a-f0-9]{40}", str(item["head"])) or not re.fullmatch("[a-f0-9]{64}", str(item["indexEntriesHash"])):
            raise DataMaintenanceError("Invalid worktree identity/hash.")
        known_roots.add(item["path"])
    mirror = canonical(directory / "repo")
    expected = inventory_files([mirror / relative(row["path"]) for row in files], mirror)
    if expected != files or set(_walk_files(mirror)) != {mirror / relative(row["path"]) for row in files}:
        raise DataMaintenanceError("Snapshot files differ from the recorded inventory.")
    db_path = mirror / relative(manifest["database"])
    with closing(sqlite3.connect(db_path.as_uri() + "?mode=ro&immutable=1", uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise DataMaintenanceError("SQLite integrity check failed.")
        if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise DataMaintenanceError("SQLite foreign-key integrity check failed.")
    return manifest


def _repair_copied_git(root, manifest):
    # The original DB and snapshot bytes remain unchanged. Repair only copied
    # administrative pointers, never call worktree repair against original paths.
    config = root / ".git/config"
    config.write_text("[core]\nrepositoryformatversion = 0\nbare = false\nfilemode = false\nautocrlf = false\n", encoding="utf-8")
    original = Path(manifest["originalRoot"])
    for item in manifest["roots"]:
        if item["path"] == ".":
            continue
        tree = root / relative(item["path"])
        marker = tree / ".git"
        old_admin = marker.read_text(encoding="utf-8").strip()
        if not old_admin.startswith("gitdir: "):
            raise DataMaintenanceError("Invalid copied worktree marker.")
        admin_rel = canonical(old_admin[8:]).relative_to(original / ".git/worktrees")
        if len(admin_rel.parts) != 1:
            raise DataMaintenanceError("Invalid copied Git administration identity.")
        admin = root / ".git/worktrees" / admin_rel
        if not admin.is_dir() or canonical(admin) != admin:
            raise DataMaintenanceError("Missing copied Git administration directory.")
        marker.write_text("gitdir: " + str(admin) + "\n", encoding="utf-8")
        (admin / "gitdir").write_text(str(marker) + "\n", encoding="utf-8")
        (admin / "commondir").write_text("../..\n", encoding="utf-8")


def restore(directory, destination, *, original_paths=False, confirm_id=None):
    manifest = verify_snapshot(directory)
    original = canonical(manifest["originalRoot"])
    destination = canonical(destination)
    if destination.exists() or destination.is_relative_to(canonical(directory)) or canonical(directory).is_relative_to(destination):
        raise DataMaintenanceError("Restore requires a new destination outside the snapshot.")
    if original_paths:
        if destination != original or confirm_id != manifest["snapshotId"]:
            raise DataMaintenanceError("Original-path restore requires the exact missing original root and explicit snapshot ID.")
    elif destination == original or destination.is_relative_to(original) or original.is_relative_to(destination):
        raise DataMaintenanceError("Rehearsal must be isolated from the original checkout.")
    destination.mkdir(mode=0o700, parents=True)
    with database_lease(destination / relative(manifest["database"]), exclusive=True):
        return _restore_files(directory, destination, manifest, original_paths=original_paths)


def _restore_files(directory, destination, manifest, *, original_paths):
    for entry in manifest["files"]:
        target = destination / relative(entry["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        copy_new_file(Path(directory) / "repo" / relative(entry["path"]), target)
        target.chmod(entry["mode"])
    if inventory_files([destination / relative(row["path"]) for row in manifest["files"]], destination) != manifest["files"]:
        raise DataMaintenanceError("Restored bytes differ from the snapshot; partial destination retained.")
    if not original_paths:
        _repair_copied_git(destination, manifest)
    for item in manifest["roots"]:
        tree = destination if item["path"] == "." else destination / relative(item["path"])
        if git(tree, "rev-parse", "HEAD").decode().strip() != item["head"]:
            raise DataMaintenanceError("Restored Git HEAD differs from the snapshot.")
        if hashlib.sha256(git(tree, "ls-files", "--stage", "-z")).hexdigest() != item["indexEntriesHash"]:
            raise DataMaintenanceError("Restored Git index differs from the snapshot.")
    git(destination, "fsck", "--full", "--no-reflogs")
    database = destination / relative(manifest["database"])
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro&immutable=1", uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise DataMaintenanceError("Restored SQLite failed integrity verification.")
    return {"snapshotId": manifest["snapshotId"], "state": "restored-original-paths" if original_paths else "rehearsal-verified",
        "destination": str(destination), "databasePathsRewritten": False, "worktrees": len(manifest["roots"]),
        "limits": "Dependencies, ignored outputs and external target sources require separate setup/backup; no runtime restart acceptance."}
