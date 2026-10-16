"""Reference-aware preview and explicit quarantine of fixed developer caches."""
import importlib.util
import json
import os
from pathlib import Path
from urllib.parse import unquote

from app.local_data import (MAX_BYTES, MAX_FILES, DataMaintenanceError, _columns, _source_paths, _tables, _walk_files,
    canonical, git, inventory_files, json_hash, offline, regular, relative,
    roots_for, write_json)

PLAN_SCHEMA = "agenthub.cache-cleanup.v1"
BASES = ("apps/api/app", "apps/api/tests", "apps/demo-api/app", "apps/demo-api/tests", "scripts")
PYTEST_CACHE = (".pytest_cache", "apps/api/.pytest_cache", "apps/demo-api/.pytest_cache")


def _references(db):
    records, values, size = [], [], 0
    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, list):
            for child in value:
                yield from strings(child)
        elif isinstance(value, dict):
            for key, child in value.items():
                yield str(key)
                yield from strings(child)
    for table in sorted(_tables(db)):
        columns = sorted(column for column in _columns(db, table) if "path" in column or column.endswith(("_json", "_dir", "_url")))
        if not columns:
            continue
        quoted = lambda value: '"' + value.replace('"', '""') + '"'
        select = ",".join(map(quoted, columns))
        for row in db.execute(f"SELECT {select} FROM {quoted(table)} ORDER BY {select}"):
            for value in row:
                size += len(str(value))
            if size > 16 * 1024**2 or len(records) >= 100_000:
                raise DataMaintenanceError("Reference inventory exceeds limits; no cleanup can be approved.")
            records.append([table, *row])
            for value in row:
                if not isinstance(value, str):
                    continue
                try:
                    parsed = json.loads(value)
                except ValueError:
                    parsed = value
                values.extend(strings(parsed))
    return json_hash(records), values


def _cache_paths(repo):
    for name in PYTEST_CACHE:
        path = repo / name
        if path.exists() or path.is_symlink():
            yield path
    for name in BASES:
        base = repo / name
        if not base.exists():
            continue
        canonical(base)
        visited = 0
        for parent, directories, _ in os.walk(base, followlinks=False):
            visited += 1
            if visited > 10_000:
                raise DataMaintenanceError("Cache discovery exceeds directory limit.")
            keep = []
            for name in directories:
                path = Path(parent) / name
                if name == "__pycache__":
                    yield path
                elif name not in {"node_modules", ".git", ".venv"}:
                    canonical(path)
                    keep.append(name)
            directories[:] = keep


def _cache_files(path):
    canonical(path)
    if not path.is_dir():
        raise DataMaintenanceError("Cache is not a directory.")
    files = list(_walk_files(path))
    for parent, directories, _ in os.walk(path, followlinks=False):
        for name in directories:
            rel = (Path(parent) / name).relative_to(path).as_posix()
            if path.name == "__pycache__" or rel not in {"v", "v/cache"}:
                raise DataMaintenanceError("Unknown directory inside cache; retain it.")
    if not files:
        raise DataMaintenanceError("Empty cache is retained; no storage is reclaimed.")
    if path.name == "__pycache__":
        for file in files:
            if file.parent != path or file.suffix != ".pyc" or regular(file).st_size < 16:
                raise DataMaintenanceError("Unknown/user file inside cache; retain the directory.")
            with file.open("rb") as stream:
                if stream.read(4) != importlib.util.MAGIC_NUMBER:
                    raise DataMaintenanceError("Unknown bytecode file; retain the directory.")
    else:
        marker = path / "CACHEDIR.TAG"
        regular(marker)
        if marker.stat().st_size > 4096 or "Signature: 8a477f597d28d172789f06886806bc55" not in marker.read_text(encoding="utf-8"):
            raise DataMaintenanceError("Missing pytest cache ownership signature.")
        allowed = {"README.md", ".gitignore", "CACHEDIR.TAG", "v/cache/nodeids", "v/cache/lastfailed", "v/cache/stepwise", "v/cache/durations"}
        if any(file.relative_to(path).as_posix() not in allowed for file in files):
            raise DataMaintenanceError("Unknown/user file inside pytest cache; retain the directory.")
    return files


def _preview_locked(repo, database, db):
    roots = roots_for(repo, db)
    reference_hash, references = _references(db)
    registry = [{"path": str(root), "head": git(root, "rev-parse", "HEAD").decode().strip()} for root in roots]
    candidates, blocked = [], []
    for path in sorted(set(_cache_paths(repo))):
        rel = path.relative_to(repo).as_posix()
        try:
            canonical(path)
            if any(root != repo and (path.is_relative_to(root) or root.is_relative_to(path)) for root in roots):
                raise DataMaintenanceError("Assigned worktree is retained.")
            forms = (str(path).replace("\\", "/").casefold(), rel.casefold())
            if any(any(form in unquote(value).replace("\\", "/").casefold() for form in forms) for value in references):
                raise DataMaintenanceError("Persisted path/JSON refers to this cache; retain it.")
            if git(repo, "ls-files", "-z", "--", rel).strip(b"\0"):
                raise DataMaintenanceError("Git-tracked files are retained.")
            files = _cache_files(path)
            tree = inventory_files(sorted(files), path)
            candidates.append({"path": rel, "files": tree, "bytes": sum(row["bytes"] for row in tree)})
        except (DataMaintenanceError, OSError, UnicodeError) as exc:
            blocked.append({"path": rel, "reason": str(exc)})
    plan = {"schema": PLAN_SCHEMA, "repo": str(repo), "database": str(database), "referenceHash": reference_hash,
        "registry": registry, "candidates": candidates, "blocked": blocked,
        "retained": "All Sessions/Runs/artifacts/Git worktrees, dependencies, unknown files and user targets are retained."}
    if sum(len(row["files"]) for row in candidates) > MAX_FILES or sum(row["bytes"] for row in candidates) > MAX_BYTES:
        raise DataMaintenanceError("Combined cleanup inventory exceeds limits.")
    plan["planId"] = json_hash(plan)
    return plan


def cleanup_preview(repo, database, *, api_port=8000):
    repo, database = canonical(repo), canonical(database)
    with offline(database, api_port=api_port) as db:
        return _preview_locked(repo, database, db)


def storage_inventory(repo, database, *, api_port=8000):
    repo, database = canonical(repo), canonical(database)
    # Counts describe captured source/metadata only; never follow dependency links
    # or walk arbitrary host target roots to guess their disk usage.
    categories = []
    with offline(database, api_port=api_port) as db:
        plan = _preview_locked(repo, database, db)
        roots = roots_for(repo, db)
        source = _source_paths(repo, roots, database=database)
        sqlite_files = [path for path in (database, database.with_name(database.name + "-wal"), database.with_name(database.name + "-shm")) if path.exists()]
        groups = (("sqlite-with-sidecars", sqlite_files),
            ("git-metadata", [path for path in source if path.is_relative_to(repo / ".git")]),
            ("managed-worktree-source", [path for path in source if path.is_relative_to(repo / ".worktrees")]),
            ("development-source", [path for path in source if not path.is_relative_to(repo / ".git") and not path.is_relative_to(repo / ".worktrees")]))
        for label, files in groups:
            sizes = [regular(path).st_size for path in files]
            if len(sizes) > MAX_FILES or sum(sizes) > MAX_BYTES:
                raise DataMaintenanceError("Storage category exceeds inventory limits.")
            categories.append({"category": label, "files": len(sizes), "bytes": sum(sizes)})
    return {"schema": "agenthub.storage-inventory.v1", "categories": categories, "registeredWorktrees": len(plan["registry"]),
        "cacheCandidates": len(plan["candidates"]), "quarantinableBytes": sum(row["bytes"] for row in plan["candidates"]),
        "blocked": plan["blocked"], "scope": "Bounded primary SQLite/Git files and known developer caches; not allocated disk blocks, dependency sizes or external host storage.",
        "retained": plan["retained"]}


def _owned_quarantine(repo, plan_id):
    base = canonical(repo / ".agenthub-maintenance")
    marker = base / "owner.json"
    expected = {"schema": "agenthub.maintenance-root.v1", "repo": str(repo)}
    if not base.exists():
        base.mkdir(mode=0o700)
        write_json(marker, expected)
    regular(marker)
    if marker.stat().st_size > 4096 or json.loads(marker.read_text(encoding="utf-8")) != expected:
        raise DataMaintenanceError("Maintenance directory is not owned by this checkout.")
    parent = canonical(base / "quarantine")
    parent.mkdir(exist_ok=True)
    directory = canonical(parent / plan_id)
    directory.mkdir(mode=0o700)
    return directory


def apply_cleanup(repo, database, plan, *, confirm_id, api_port=8000):
    repo, database = canonical(repo), canonical(database)
    if not isinstance(plan, dict) or plan.get("schema") != PLAN_SCHEMA or confirm_id != plan.get("planId"):
        raise DataMaintenanceError("Explicit cleanup requires the exact preview plan ID.")
    with offline(database, api_port=api_port) as db:
        current = _preview_locked(repo, database, db)
        if current != plan:
            raise DataMaintenanceError("Cleanup preview is stale or tampered; regenerate it before applying.")
        if not current["candidates"]:
            return {"state": "nothing-to-quarantine", "planId": confirm_id, "moved": []}
        directory = _owned_quarantine(repo, current["planId"])
        receipt = {"schema": PLAN_SCHEMA, "planId": confirm_id, "state": "prepared", "moved": [], "pending": None}
        receipt_path = directory / "receipt.json"
        def save():
            temporary = directory / "receipt.next.json"
            write_json(temporary, receipt)
            os.replace(temporary, receipt_path)
        save()
        try:
            for entry in current["candidates"]:
                source = canonical(repo / relative(entry["path"]))
                if inventory_files(sorted(_cache_files(source)), source) != entry["files"]:
                    raise DataMaintenanceError("Cache changed before its move.")
                destination = canonical(directory / "files" / relative(entry["path"]))
                destination.parent.mkdir(parents=True, exist_ok=True)
                receipt["pending"] = entry["path"]; receipt["state"] = "moving"; save()
                os.rename(source, destination)
                receipt["moved"].append(entry["path"])
                receipt["pending"] = None
                if inventory_files(sorted(_cache_files(destination)), destination) != entry["files"]:
                    raise DataMaintenanceError("Moved cache bytes changed; retained in quarantine for inspection.")
                save()
            receipt["state"] = "quarantined"; save()
        except Exception as exc:
            receipt["state"] = "partial"; receipt["detail"] = str(exc); save()
            raise DataMaintenanceError("Cleanup incomplete; inspect durable receipt: " + str(receipt_path)) from exc
        return {**receipt, "receipt": str(receipt_path), "bytesMoved": sum(row["bytes"] for row in current["candidates"]),
            "diskBytesFreed": 0, "note": "Quarantine is reversible retention, not permanent disk deletion."}
