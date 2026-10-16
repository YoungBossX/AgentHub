import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.local_data import DataMaintenanceError, digest, git, json_hash
from app.local_data_cleanup import apply_cleanup, cleanup_preview, storage_inventory
from test_local_data import data_workspace


def caches(repo):
    bytecode = repo / "apps/api/app/__pycache__/module.cpython-313.pyc"
    bytecode.parent.mkdir(parents=True)
    bytecode.write_bytes(importlib.util.MAGIC_NUMBER + b"\0" * 20)
    pytest_cache = repo / ".pytest_cache"
    pytest_cache.mkdir()
    (pytest_cache / "CACHEDIR.TAG").write_text("Signature: 8a477f597d28d172789f06886806bc55\n")
    (pytest_cache / "README.md").write_text("pytest cache")
    return bytecode, pytest_cache


def test_readonly_inventory_and_explicit_quarantine_keep_sources_and_sessions(data_workspace):
    repo, tree, database, db, port = data_workspace
    bytecode, pytest_cache = caches(repo)
    index = digest(repo / ".git/index")
    before_rows = db.execute("SELECT * FROM session").fetchall()
    inventory = storage_inventory(repo, database, api_port=port)
    assert inventory["registeredWorktrees"] == 2 and inventory["cacheCandidates"] == 2
    assert {item["category"] for item in inventory["categories"]} == {"sqlite-with-sidecars", "git-metadata", "managed-worktree-source", "development-source"}
    plan = cleanup_preview(repo, database, api_port=port)
    assert bytecode.exists() and pytest_cache.exists()
    assert not (repo / ".agenthub-maintenance").exists()
    assert digest(repo / ".git/index") == index
    with pytest.raises(DataMaintenanceError, match="exact preview"):
        apply_cleanup(repo, database, plan, confirm_id="wrong", api_port=port)
    result = apply_cleanup(repo, database, plan, confirm_id=plan["planId"], api_port=port)
    assert result["state"] == "quarantined" and result["diskBytesFreed"] == 0
    assert not bytecode.parent.exists() and not pytest_cache.exists()
    receipt = Path(result["receipt"])
    assert json.loads(receipt.read_text())["state"] == "quarantined"
    assert (receipt.parent / "files/apps/api/app/__pycache__/module.cpython-313.pyc").exists()
    assert db.execute("SELECT * FROM session").fetchall() == before_rows
    assert tree.exists() and (tree / "untracked.txt").exists() and (repo / "new-source.py").exists()
    assert digest(repo / ".git/index") == index


@pytest.mark.parametrize("kind", ["cache-change", "database-reference", "forged-path", "active", "foreign-owner", "linked-cache"])
def test_stale_unknown_and_unsafe_apply_are_refused(data_workspace, tmp_path, kind):
    repo, _, database, db, port = data_workspace
    bytecode, pytest_cache = caches(repo)
    plan = cleanup_preview(repo, database, api_port=port)
    if kind == "cache-change":
        bytecode.write_bytes(bytecode.read_bytes() + b"changed")
    elif kind == "database-reference":
        db.execute("UPDATE taskrun SET metrics_json=?", (json.dumps({"cache": str(bytecode.parent)}),)); db.commit()
    elif kind == "forged-path":
        plan["candidates"][0]["path"] = "../user-data"
        plan["planId"] = json_hash({key: value for key, value in plan.items() if key != "planId"})
    elif kind == "active":
        db.execute("UPDATE taskrun SET state='queued'"); db.commit()
    elif kind == "foreign-owner":
        (repo / ".agenthub-maintenance").mkdir()
        (repo / ".agenthub-maintenance/owner.json").write_text("{}")
    elif kind == "linked-cache":
        outside = tmp_path / "outside"
        bytecode.parent.rename(outside)
        try:
            bytecode.parent.symlink_to(outside, target_is_directory=True)
        except OSError:
            outside.rename(bytecode.parent)
            pytest.skip("OS denies test symlinks")
    with pytest.raises((DataMaintenanceError, OSError)):
        apply_cleanup(repo, database, plan, confirm_id=plan["planId"], api_port=port)
    assert bytecode.exists() and pytest_cache.exists()


@pytest.mark.parametrize("form", ["nested-value", "object-key", "encoded-file-url"])
def test_references_unknown_files_and_git_tracked_cache_are_retained(data_workspace, form):
    repo, _, database, db, port = data_workspace
    bytecode, pytest_cache = caches(repo)
    from urllib.parse import quote
    value = {"nested": [{"file": str(bytecode)}]} if form == "nested-value" else ({str(bytecode): "artifact"} if form == "object-key" else {"url": "file:///" + quote(str(bytecode), safe="")})
    db.execute("UPDATE taskrun SET metrics_json=?", (json.dumps(value),)); db.commit()
    (pytest_cache / "user-notes.md").write_text("must keep")
    preview = cleanup_preview(repo, database, api_port=port)
    assert preview["candidates"] == []
    assert any("Persisted" in item["reason"] for item in preview["blocked"])
    assert any("Unknown/user" in item["reason"] for item in preview["blocked"])
    db.execute("UPDATE taskrun SET metrics_json='{}'"); db.commit()
    git(repo, "add", "-f", str(bytecode))
    preview = cleanup_preview(repo, database, api_port=port)
    assert any("Git-tracked" in item["reason"] for item in preview["blocked"])
    result = apply_cleanup(repo, database, preview, confirm_id=preview["planId"], api_port=port)
    assert result["state"] == "nothing-to-quarantine" and bytecode.exists()


def test_partial_move_retains_durable_receipt_and_remaining_cache(data_workspace, monkeypatch):
    from app import local_data_cleanup
    repo, _, database, _, port = data_workspace
    bytecode, _ = caches(repo)
    plan = cleanup_preview(repo, database, api_port=port)
    rename = os.rename
    moved = []
    def fail_second(source, destination):
        if moved:
            raise OSError("injected move failure")
        rename(source, destination); moved.append(source)
    monkeypatch.setattr(local_data_cleanup.os, "rename", fail_second)
    with pytest.raises(DataMaintenanceError, match="durable receipt"):
        apply_cleanup(repo, database, plan, confirm_id=plan["planId"], api_port=port)
    receipt = repo / ".agenthub-maintenance/quarantine" / plan["planId"] / "receipt.json"
    state = json.loads(receipt.read_text())
    assert state["state"] == "partial" and len(state["moved"]) == 1
    assert bytecode.exists()


def test_cleanup_cli_preview_apply_and_inventory(data_workspace, tmp_path):
    repo, _, database, _, port = data_workspace
    caches(repo)
    script = str(Path(__file__).resolve().parents[3] / "scripts/local-data.py")
    common = ["--repo", str(repo), "--database", str(database), "--api-port", str(port)]
    output = tmp_path / "preview.json"
    preview = subprocess.run([sys.executable, script, "cleanup-preview", *common, "--output", str(output)], capture_output=True, text=True)
    assert preview.returncode == 0, preview.stderr
    plan = json.loads(output.read_text(encoding="utf-8"))
    apply = subprocess.run([sys.executable, script, "cleanup-apply", *common, "--plan", str(output), "--confirm-id", plan["planId"]], capture_output=True, text=True)
    assert apply.returncode == 0 and json.loads(apply.stdout)["state"] == "quarantined", apply.stderr
    inventory = subprocess.run([sys.executable, script, "inventory", *common], capture_output=True, text=True)
    assert inventory.returncode == 0 and json.loads(inventory.stdout)["cacheCandidates"] == 0, inventory.stderr
