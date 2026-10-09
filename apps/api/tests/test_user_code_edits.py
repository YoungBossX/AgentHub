import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session as DbSession, select

from app import user_code_edits as edits
from app.main import app, get_db
from app.models import Artifact, ArtifactVersion, Diff, Session, TaskRun
from app.user_edit_files import UserEditFiles
from app.user_edit_fences import pending_user_edit
from app.user_patch import FileChange, UserPatchError, UserPatchConflict, render_text_patch
from app.worktrees import WorktreeService
from test_execution_worktrees import branch_db, git, task_for

PATH = "apps/demo/src/App.tsx"


@pytest.fixture
def edit_db(branch_db, tmp_path, monkeypatch):
    db, session, repo = branch_db
    service = WorktreeService(repo_root=repo, worktrees_root=tmp_path / "worktrees")
    root = service.session_path(session.workspace_id, session.id)
    root.parent.mkdir(parents=True)
    git(repo, "worktree", "add", "--detach", str(root), "HEAD")
    # Source bytes are explicit, independent of the host Git core.autocrlf.
    (root / PATH).write_bytes(b"baseline\n")
    session.worktree_path = str(root)
    task = task_for(db, session, "frontend", isolated=False)
    task.status = "completed"
    run = TaskRun(task_id=task.id, agent_id=task.assigned_agent_id, state="completed", worktree_path=str(root))
    source = Artifact(task_run_id=run.id, artifact_type="diff", title="Original Agent Diff", status="ready")
    db.add(session); db.add(task); db.add(run); db.add(source)
    db.add(Diff(artifact_id=source.id, base_ref="base", head_ref="head", patch_text="original immutable evidence"))
    db.commit()
    monkeypatch.setattr(edits, "WorktreeService", lambda: service)
    yield db, session.id, source.id, root


def prepare(fixture, *, content="user edit\n", operation_id=None):
    db, sid, source, _ = fixture
    version = edits.read_source(db, sid, source, PATH)
    return edits.prepare_edit(db, sid, source, operation_id or str(uuid4()), path=PATH, content=content,
                              expected_sha256=version["sha256"], expected_binding=version["binding"])


def test_full_file_prepare_apply_duplicate_and_agent_evidence_immutable(edit_db):
    db, sid, source, root = edit_db
    original_run = db.get(TaskRun, db.get(Artifact, source).task_run_id).model_dump()
    original_artifact = db.get(Artifact, source).model_dump()
    operation = prepare(edit_db)
    assert (root / PATH).read_bytes() == b"baseline\n"
    assert operation["actor"] == "user" and operation["state"] == "prepared"
    assert "+user edit" in operation["patch"]
    assert edits.apply_edit(db, sid, operation["id"])["state"] == "applied"
    assert (root / PATH).read_bytes() == b"user edit\n"
    (root / PATH).write_bytes(b"later external edit\n")
    assert edits.apply_edit(db, sid, operation["id"])["state"] == "applied"
    assert (root / PATH).read_bytes() == b"later external edit\n", "Duplicate apply must never rewrite files"
    assert db.get(TaskRun, original_run["id"]).model_dump() == original_run
    assert db.get(Artifact, source).model_dump() == original_artifact
    assert db.exec(select(Diff)).one().patch_text == "original immutable evidence"
    assert db.exec(select(ArtifactVersion)).one().editor_source == "user"
    from app.diffs import collect_task_run_diff, DiffCollectionError
    from app.deployments import _ensure_deploy_prerequisites, DeployError
    with pytest.raises(DiffCollectionError, match="later user edits"): collect_task_run_diff(db, original_run["id"])
    with pytest.raises(DeployError, match="later user edits"):
        _ensure_deploy_prerequisites(db, db.get(TaskRun, original_run["id"]))


def test_patch_add_delete_modify_preserves_exact_bytes(edit_db):
    db, sid, source, root = edit_db
    extra = "apps/demo/src/extra.txt"
    (root / extra).write_bytes(b"remove\r\n")
    changes = (FileChange(PATH, b"baseline\n", "中文\r\n末行".encode()),
               FileChange(extra, b"remove\r\n", None), FileChange("apps/demo/src/new.txt", None, b""))
    operation = edits.prepare_edit(db, sid, source, str(uuid4()), patch=render_text_patch(changes))
    assert edits.apply_edit(db, sid, operation["id"])["state"] == "applied"
    for change in changes:
        assert ((root / change.path).read_bytes() if (root / change.path).exists() else None) == change.after


@pytest.mark.parametrize("change", ["content", "head", "target", "source_path", "session_path"])
def test_stale_source_or_ownership_is_conflict_without_writes(edit_db, change):
    db, sid, source, root = edit_db
    operation = prepare(edit_db)
    if change == "content": (root / PATH).write_bytes(b"external\n")
    elif change == "head":
        git(root, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--allow-empty", "-m", "new head")
    elif change == "target":
        from app.models import Task
        task = db.get(Task, db.get(TaskRun, db.get(Artifact, source).task_run_id).task_id)
        task.plan_json = json.dumps({"targetId": "agenthub-platform"}); db.add(task); db.commit()
    elif change == "source_path":
        run = db.get(TaskRun, db.get(Artifact, source).task_run_id)
        run.worktree_path = str(root.parent); db.add(run); db.commit()
    else:
        session = db.get(Session, sid)
        session.worktree_path = str(root.parent); db.add(session); db.commit()
    before = (root / PATH).read_bytes()
    assert edits.apply_edit(db, sid, operation["id"])["state"] == "conflict"
    assert (root / PATH).read_bytes() == before


def test_busy_session_and_unresolved_operations_block_preparation_and_application(edit_db):
    db, sid, source, root = edit_db
    operation = prepare(edit_db)
    run = db.get(TaskRun, db.get(Artifact, source).task_run_id)
    run.state = "queued"; db.add(run); db.commit()
    with pytest.raises(UserPatchConflict): edits.apply_edit(db, sid, operation["id"])
    db.rollback()
    run.state = "completed"; db.add(run); db.commit()
    artifact = db.get(Artifact, operation["id"])
    artifact.status = "unresolved"; db.add(artifact); db.commit()
    assert pending_user_edit(db, sid).id == operation["id"]
    with pytest.raises(UserPatchConflict): prepare(edit_db)
    db.rollback()
    from app.dag_integration import _assert_idle, IntegrationWaiting
    with pytest.raises(IntegrationWaiting): _assert_idle(db, sid)
    from app.task_runs import create_task_run, TaskRunLifecycleError
    from app.models import Task
    task = db.get(Task, run.task_id)
    new_task = task_for(db, db.get(Session, sid), "frontend", isolated=False)
    with pytest.raises(TaskRunLifecycleError, match="user code edit"): create_task_run(db, new_task.id)
    assert (root / PATH).read_bytes() == b"baseline\n"


def test_prepare_idempotency_and_foreign_session_rejected(edit_db):
    db, sid, source, root = edit_db
    op_id = str(uuid4())
    assert prepare(edit_db, operation_id=op_id) == prepare(edit_db, operation_id=op_id)
    with pytest.raises(UserPatchConflict): prepare(edit_db, operation_id=op_id, content="different")
    db.rollback()
    with pytest.raises(UserPatchError): edits.apply_edit(db, str(uuid4()), op_id)
    db.rollback()
    with pytest.raises(UserPatchError): edits.read_source(db, str(uuid4()), source, PATH)


def test_failed_second_write_rolls_back_complete_outputs(edit_db, monkeypatch):
    db, sid, source, root = edit_db
    changes = (FileChange(PATH, b"baseline\n", b"new\n"), FileChange("apps/demo/src/new.txt", None, b"added\n"))
    op = edits.prepare_edit(db, sid, source, str(uuid4()), patch=render_text_patch(changes))
    original = UserEditFiles.write
    def fail_second(self, path, before, after):
        if path.endswith("new.txt"): raise OSError("injected failure")
        return original(self, path, before, after)
    monkeypatch.setattr(UserEditFiles, "write", fail_second)
    assert edits.apply_edit(db, sid, op["id"])["state"] == "failed"
    assert (root / PATH).read_bytes() == b"baseline\n"
    assert not (root / changes[1].path).exists()
    assert pending_user_edit(db, sid) is None


@pytest.mark.parametrize("outcome,expected", [("before", "failed"), ("after", "applied"), ("partial", "unresolved"), ("foreign", "unresolved")])
def test_restart_reconciles_without_replaying_or_overwriting(edit_db, outcome, expected):
    db, sid, source, root = edit_db
    op = prepare(edit_db)
    artifact = db.get(Artifact, op["id"])
    artifact.status = "applying"; db.add(artifact); db.commit()
    value = {"before": b"baseline\n", "after": b"user edit\n", "partial": b"user", "foreign": b"external"}[outcome]
    (root / PATH).write_bytes(value)
    edits.recover_user_edits(db.get_bind())
    db.expire_all()
    assert db.get(Artifact, op["id"]).status == expected
    assert (root / PATH).read_bytes() == value
    if expected == "unresolved":
        resolved = edits.reconcile_edit(db, sid, op["id"], keep_current=True)
        assert resolved["state"] == "resolved"
        assert pending_user_edit(db, sid) is None
        assert (root / PATH).read_bytes() == value


def test_api_validation_and_lost_apply_response_recovery(edit_db):
    db, sid, source, root = edit_db
    def dependency():
        with DbSession(db.get_bind()) as connection:
            yield connection
    app.dependency_overrides[get_db] = dependency
    try:
        client = TestClient(app)
        loaded = client.get(f"/sessions/{sid}/code-edits/source", params={"sourceArtifactId": source, "path": PATH})
        assert loaded.status_code == 200
        version = loaded.json()
        request = {"operationId": str(uuid4()), "sourceArtifactId": source, "path": PATH,
                   "content": "browser revision\n", "expectedSha256": version["sha256"], "expectedBinding": version["binding"]}
        response = client.post(f"/sessions/{sid}/code-edits", json=request)
        assert response.status_code == 200
        assert client.post(f"/sessions/{sid}/code-edits", json={**request, "patch": "incompatible"}).status_code == 422
        applied = client.post(f"/sessions/{sid}/code-edits/{request['operationId']}/apply")
        assert applied.status_code == 200 and applied.json()["state"] == "applied"
        recovered = client.get(f"/sessions/{sid}/code-edits").json()
        assert recovered[0]["id"] == request["operationId"] and recovered[0]["state"] == "applied"
        assert str(root) not in json.dumps(recovered)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "directory_link", "missing_parent", "case_alias"])
def test_unsafe_filesystem_binding_never_reads_or_writes_outside(edit_db, tmp_path, kind):
    db, sid, source, root = edit_db
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside secret")
    path = root / PATH
    if kind == "symlink":
        path.unlink(); path.symlink_to(outside)
    elif kind == "hardlink":
        path.unlink(); os.link(outside, path)
    elif kind == "directory_link":
        (root / "apps/demo/link").symlink_to(tmp_path, target_is_directory=True)
        relative = "apps/demo/link/outside.txt"
        with pytest.raises(UserPatchError):
            with UserEditFiles(root) as files: files.read(relative)
        return
    elif kind == "missing_parent":
        with pytest.raises(UserPatchError):
            with UserEditFiles(root) as files: files.write("apps/demo/src/missing/a.txt", None, b"new")
        return
    elif kind == "case_alias":
        if os.name != "nt": pytest.skip("Case-insensitive Windows alias")
        with pytest.raises(UserPatchError):
            with UserEditFiles(root) as files: files.read("apps/demo/src/app.tsx")
        return
    with pytest.raises(UserPatchError): edits.read_source(db, sid, source, PATH)
    assert outside.read_bytes() == b"outside secret"


def test_concurrent_duplicate_sees_durable_claim_without_reapplying(edit_db, monkeypatch):
    db, sid, source, root = edit_db
    operation = prepare(edit_db)
    write = UserEditFiles.write
    calls = []
    def check_claim(self, *args):
        with DbSession(db.get_bind()) as second:
            assert edits.apply_edit(second, sid, operation["id"])["state"] == "applying"
        calls.append(args)
        return write(self, *args)
    monkeypatch.setattr(UserEditFiles, "write", check_claim)
    assert edits.apply_edit(db, sid, operation["id"])["state"] == "applied"
    assert len(calls) == 1


def test_crash_mid_write_persists_claim_and_restart_keeps_partial_content(edit_db, monkeypatch):
    db, sid, source, root = edit_db
    operation = prepare(edit_db)
    def crash(self, relative, before, after):
        fd = self.files[relative]
        os.lseek(fd, 0, os.SEEK_SET); os.write(fd, b"partial"); os.fsync(fd)
        raise SystemExit("simulated process exit")
    monkeypatch.setattr(UserEditFiles, "write", crash)
    with pytest.raises(SystemExit): edits.apply_edit(db, sid, operation["id"])
    partial = (root / PATH).read_bytes()
    assert partial != b"baseline\n" and partial != b"user edit\n"
    assert db.get(Artifact, operation["id"]).status == "applying"
    edits.recover_user_edits(db.get_bind()); db.expire_all()
    assert db.get(Artifact, operation["id"]).status == "unresolved"
    assert (root / PATH).read_bytes() == partial


@pytest.mark.skipif(os.name != "nt", reason="Windows sharing guarantees")
def test_windows_held_handles_block_external_writers_and_parent_replacement(edit_db):
    _, _, _, root = edit_db
    with UserEditFiles(root) as files:
        assert files.read(PATH, write=True) == b"baseline\n"
        with pytest.raises(OSError): (root / PATH).write_bytes(b"foreign")
        with pytest.raises(OSError): (root / PATH).unlink()
        with pytest.raises(OSError): (root / "apps/demo/src").rename(root / "apps/demo/replaced")
        files.write(PATH, b"baseline\n", b"own\n")
    assert (root / PATH).read_bytes() == b"own\n"


def test_source_version_conflict_does_not_create_operation(edit_db):
    db, sid, source, root = edit_db
    old = edits.read_source(db, sid, source, PATH)
    (root / PATH).write_bytes(b"changed\n")
    with pytest.raises(UserPatchConflict):
        edits.prepare_edit(db, sid, source, str(uuid4()), path=PATH, content="mine\n",
                           expected_sha256=old["sha256"], expected_binding=old["binding"])
    db.rollback()
    assert edits.list_operations(db, sid) == []
    assert (root / PATH).read_bytes() == b"changed\n"


@pytest.mark.skipif(os.name != "nt", reason="Windows named streams")
def test_named_streams_are_rejected_before_file_edit(edit_db):
    db, sid, source, root = edit_db
    stream = Path(str(root / PATH) + ":private")
    stream.write_bytes(b"stream data")
    with pytest.raises(UserPatchError): edits.read_source(db, sid, source, PATH)
    assert (root / PATH).read_bytes() == b"baseline\n"
    assert stream.read_bytes() == b"stream data"


def test_next_agent_diff_uses_actual_execution_baseline_after_user_edit(edit_db, monkeypatch):
    import asyncio
    import app.run_engine as engine
    from app.task_runs import create_task_run
    from app.diffs import list_task_run_diffs
    from test_execution_worktrees import BlockingWritingAdapter
    db, sid, _, root = edit_db
    op = prepare(edit_db)
    assert edits.apply_edit(db, sid, op["id"])["state"] == "applied"
    adapter = BlockingWritingAdapter(); adapter.release.set()
    monkeypatch.setattr(engine, "ScriptedMockAdapter", lambda: adapter)
    task = task_for(db, db.get(Session, sid), "frontend", isolated=False)
    run = create_task_run(db, task.id)
    git_base = run.base_ref
    asyncio.run(engine.BoundedRunDispatcher().run_once(db))
    db.expire_all(); run = db.get(TaskRun, run.id)
    assert run.state == "completed", run.error_message
    assert run.base_ref == git_base
    checkpoint = json.loads(run.metrics_json)["preRunCheckpoint"]
    assert checkpoint["fileSnapshot"]["files"][PATH]["content"] == "user edit\n"
    assert checkpoint["userEditBaseline"]["operationId"] == op["id"]
    diff = list_task_run_diffs(db, run.id)[-1]
    assert "-user edit" in diff.patch_text and "-baseline" not in diff.patch_text
    assert "+user edit" not in diff.patch_text
    assert diff.base_ref.startswith("filesystem-snapshot:")
