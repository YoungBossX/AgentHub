"""Explicit user-origin code revisions, independent of Agent execution evidence."""

import hashlib
import json
import stat
from dataclasses import asdict
from pathlib import Path
from uuid import UUID

from sqlalchemy import update
from sqlmodel import Session as DbSession, select

from app.execution_worktrees import _git, _repository_identity, requires_integration, ExecutionWorktreeError
from app.models import Artifact, ArtifactVersion, Session, SessionQueueEntry, TargetLock, Task, TaskRun, utc_now
from app.scheduler import target_id_for_task
from app.target_registry import get_target_for_workspace, TargetRegistryError
from app.user_edit_fences import USER_EDIT_TYPE, pending_user_edit
from app.user_edit_files import UserEditFiles
from app.user_patch import FileChange, UserPatchError, UserPatchConflict, digest, prepare_text_patch, render_text_patch, text_bytes, validate_path
from app.worktrees import WorktreeService

TERMINAL = {"completed", "failed", "interrupted", "cancelled"}


def _hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def _reserve(db, session_id):
    db.execute(update(Session).where(Session.id == session_id).values(updated_at=Session.updated_at)
               .execution_options(synchronize_session=False))
    db.expire_all()


def _idle(db, session_id):
    active = db.exec(select(TaskRun).join(Task, Task.id == TaskRun.task_id).where(
        Task.session_id == session_id, TaskRun.state.notin_(TERMINAL))).first()
    queue = db.exec(select(SessionQueueEntry).where(SessionQueueEntry.session_id == session_id,
                   SessionQueueEntry.state.in_({"queued", "running", "blocked"}))).first()
    lock = db.exec(select(TargetLock).where(TargetLock.session_id == session_id, TargetLock.state == "held")).first()
    if active or queue or lock:
        raise UserPatchConflict("Session has pending execution or held locks; wait before editing files.")


def _owner(db, session_id, source_id):
    source = db.get(Artifact, source_id)
    run = db.get(TaskRun, source.task_run_id) if source else None
    task = db.get(Task, run.task_id) if run else None
    session = db.get(Session, session_id)
    if source is None or source.artifact_type != "diff" or task is None or session is None or task.session_id != session_id:
        raise UserPatchError("Source Diff does not belong to this Session.")
    if run.state not in TERMINAL:
        raise UserPatchConflict("Source execution is still active.")
    try:
        target = get_target_for_workspace(db, session.workspace_id, target_id_for_task(task, db))
        root = Path(session.worktree_path)
        if (target.type == "platform" or target.requires_platform_mode or target.requires_approval
                or not root.is_absolute() or root.resolve() != root):
            raise UserPatchError("This target is not available for user edits.")
        service = WorktreeService()
        # Explicit edits currently require a canonical allocated worktree. External
        # host roots used by legacy direct execution are deliberately not writable.
        if root != service.session_path(session.workspace_id, session.id).absolute():
            raise UserPatchError("User editing requires the assigned canonical Session worktree.")
        head, common = _repository_identity(root)
        if common != _repository_identity(service.repo_root)[1]:
            raise UserPatchError("Session repository ownership changed.")
        registered = _git(service.repo_root, "worktree", "list", "--porcelain").splitlines()
        if not any(line.startswith("worktree ") and Path(line[9:]).resolve() == root for line in registered):
            raise UserPatchError("Session worktree is not registered.")
        if requires_integration(run):
            from app.dag_integration import integration_for_run
            if integration_for_run(db, run) is None:
                raise UserPatchConflict("Isolated output must be integrated before editing canonical files.")
        elif Path(run.worktree_path) != root:
            raise UserPatchError("Source execution used a different worktree.")
        foreign = db.exec(select(Session).where(Session.id != session_id, Session.worktree_path == session.worktree_path)).first()
        if foreign:
            raise UserPatchError("Worktree is shared by another Session.")
        root_stat = root.stat()
        binding = _hash({"session": session.id, "workspace": session.workspace_id, "source": source.id,
                         "run": run.id, "root": str(root), "common": str(common), "head": head,
                         "identity": [root_stat.st_dev, root_stat.st_ino], "target": asdict(target)})
        return root, target, binding, head
    except (TargetRegistryError, ExecutionWorktreeError, OSError) as exc:
        raise UserPatchError("Target or canonical worktree validation failed.") from exc


def read_source(db, session_id, source_id, path):
    validate_path(path)
    _reserve(db, session_id)
    _idle(db, session_id)
    root, target, binding, head = _owner(db, session_id, source_id)
    if not target.permits_path(path):
        raise UserPatchError("File is outside the selected target.")
    with UserEditFiles(root) as files:
        content = files.read(path)
    return {"path": path, "content": text_bytes(content) if content is not None else None,
            "sha256": digest(content), "binding": binding, "head": head, "targetId": target.target_id}


def _operation(db, session_id, operation_id):
    artifact = db.get(Artifact, operation_id)
    run = db.get(TaskRun, artifact.task_run_id) if artifact else None
    task = db.get(Task, run.task_id) if run else None
    if artifact is None or artifact.artifact_type != USER_EDIT_TYPE or task is None or task.session_id != session_id:
        raise UserPatchError("User edit does not belong to this Session.")
    return artifact


def _snapshot(db, artifact):
    version = db.exec(select(ArtifactVersion).where(ArtifactVersion.artifact_id == artifact.id,
                                                  ArtifactVersion.version == 1)).one()
    if digest(version.content_md.encode()) != version.content_hash:
        raise UserPatchError("User edit source evidence is invalid.")
    return json.loads(version.content_md)


def operation_payload(artifact):
    data = json.loads(artifact.meta_json)
    return {"id": artifact.id, "state": artifact.status, "actor": "user",
            "sourceArtifactId": data["sourceArtifactId"], "targetId": data["targetId"],
            "patch": data["patch"], "files": data["files"], "reason": data.get("reason"),
            "createdAt": artifact.created_at.isoformat(), "updatedAt": artifact.updated_at.isoformat()}


def list_operations(db, session_id):
    records = db.exec(select(Artifact).join(TaskRun, Artifact.task_run_id == TaskRun.id)
                      .join(Task, TaskRun.task_id == Task.id).where(Task.session_id == session_id,
                      Artifact.artifact_type == USER_EDIT_TYPE).order_by(Artifact.created_at.desc()).limit(50)).all()
    return [operation_payload(record) for record in records]


def _state(db, artifact, state, reason):
    data = json.loads(artifact.meta_json)
    data["reason"] = reason
    artifact.meta_json = json.dumps(data)
    artifact.status = state
    artifact.updated_at = utc_now()
    db.add(artifact)
    db.commit()
    return operation_payload(artifact)


def prepare_edit(db, session_id, source_id, operation_id, *, patch=None, path=None, content=None,
                 expected_sha256=None, expected_binding=None):
    if str(UUID(operation_id)) != operation_id:
        raise UserPatchError("An operation requires a canonical UUID.")
    request_hash = _hash([session_id, source_id, patch, path, content, expected_sha256, expected_binding])
    _reserve(db, session_id)
    existing = db.get(Artifact, operation_id)
    if existing:
        existing = _operation(db, session_id, operation_id)
        if json.loads(existing.meta_json).get("requestHash") != request_hash:
            raise UserPatchConflict("Operation ID has already been used for different content.")
        return operation_payload(existing)
    if pending_user_edit(db, session_id):
        raise UserPatchConflict("An earlier user edit still needs reconciliation.")
    _idle(db, session_id)
    root, target, binding, head = _owner(db, session_id, source_id)
    with UserEditFiles(root) as files:
        if patch is None:
            validate_path(path)
            if not target.permits_path(path) or not isinstance(content, str):
                raise UserPatchError("A permitted file and full UTF-8 content are required.")
            before = files.read(path)
            if expected_binding != binding or digest(before) != expected_sha256:
                raise UserPatchConflict("Source version changed; reload before preparing an edit.")
            changes = (FileChange(path, before, content.encode("utf-8")),)
            patch = render_text_patch(changes)
        else:
            changes = prepare_text_patch(patch, read_file=files.read, permits=target.permits_path)
            patch = render_text_patch(changes)
        snapshots = [{"path": item.path, "before": text_bytes(item.before) if item.before is not None else None,
                      "after": text_bytes(item.after) if item.after is not None else None,
                      "mode": stat.S_IMODE((root / item.path).stat().st_mode) if item.before is not None else 0o644}
                     for item in changes]
    snapshot = json.dumps({"binding": binding, "changes": snapshots}, ensure_ascii=True)
    source = db.get(Artifact, source_id)
    artifact = Artifact(id=operation_id, task_run_id=source.task_run_id, artifact_type=USER_EDIT_TYPE,
                        title="用户代码修改", status="prepared", meta_json=json.dumps({
                            "actor": "user", "sessionId": session_id, "sourceArtifactId": source_id,
                            "targetId": target.target_id, "requestHash": request_hash, "patch": patch,
                            "files": [change.metadata() for change in changes]}))
    db.add(artifact)
    db.add(ArtifactVersion(artifact_id=artifact.id, source_task_run_id=source.task_run_id,
                          parent_artifact_id=source.id, git_base_ref=head, git_head_ref=head,
                          changed_files_json=json.dumps([c.path for c in changes]), editor_source="user",
                          summary="Prepared user edit; not executed or reviewed by an Agent.",
                          content_md=snapshot, content_hash=digest(snapshot.encode())))
    db.commit()
    return operation_payload(artifact)


def _changes(snapshot):
    return tuple(FileChange(item["path"], item["before"].encode("utf-8") if item["before"] is not None else None,
                            item["after"].encode("utf-8") if item["after"] is not None else None)
                 for item in snapshot["changes"])


def apply_edit(db, session_id, operation_id):
    _reserve(db, session_id)
    artifact = _operation(db, session_id, operation_id)
    if artifact.status != "prepared":
        return operation_payload(artifact)
    if pending_user_edit(db, session_id):
        raise UserPatchConflict("An earlier user edit still needs reconciliation.")
    _idle(db, session_id)
    metadata = json.loads(artifact.meta_json)
    snapshot = _snapshot(db, artifact)
    try:
        root, target, binding, _ = _owner(db, session_id, metadata["sourceArtifactId"])
        if binding != snapshot["binding"]:
            raise UserPatchConflict("Target or repository version changed.")
        changes = _changes(snapshot)
        with UserEditFiles(root) as files:
            for change in changes:
                if not target.permits_path(change.path) or files.read(change.path, write=True) != change.before:
                    raise UserPatchConflict("Source changed after preparation; no files were written.")
                if change.before is not None and stat.S_IMODE((root / change.path).stat().st_mode) != next(
                        item["mode"] for item in snapshot["changes"] if item["path"] == change.path):
                    raise UserPatchConflict("Source file permissions changed.")
            # Durable claim precedes the first file write. A crash leaves a fence.
            _state(db, artifact, "applying", "Applying explicit user changes.")
            try:
                for change in changes:
                    files.write(change.path, change.before, change.after)
            except (OSError, UserPatchError):
                # Undo only complete outputs still equal to our intended bytes.
                # Partial or foreign content is retained for explicit resolution.
                restored = True
                for change in reversed(changes):
                    try:
                        current = files.read(change.path, write=True)
                        if current == change.after:
                            files.write(change.path, change.after, change.before)
                            if change.before is not None:
                                mode = next(item["mode"] for item in snapshot["changes"] if item["path"] == change.path)
                                files.restore_mode(change.path, mode)
                        elif current != change.before:
                            restored = False
                    except (OSError, UserPatchError):
                        restored = False
                return _state(db, artifact, "failed" if restored else "unresolved",
                              "Write failed; original content restored." if restored else
                              "Write interrupted; inspect current files before explicitly releasing the execution fence.")
        return _state(db, artifact, "applied", "User changes applied; tests and reviews have not been run for this revision.")
    except (UserPatchError, OSError):
        if artifact.status == "applying":
            return _state(db, artifact, "unresolved", "Application outcome requires reconciliation.")
        return _state(db, artifact, "conflict", "Source or ownership changed; reload and prepare a new edit.")


def reconcile_edit(db, session_id, operation_id, *, keep_current=False, startup=False):
    _reserve(db, session_id)
    artifact = _operation(db, session_id, operation_id)
    if artifact.status != "unresolved" and not (startup and artifact.status == "applying"):
        return operation_payload(artifact)
    try:
        metadata = json.loads(artifact.meta_json)
        snapshot = _snapshot(db, artifact)
        root, target, binding, _ = _owner(db, session_id, metadata["sourceArtifactId"])
        if binding != snapshot["binding"]:
            raise UserPatchConflict("Ownership changed.")
        changes = _changes(snapshot)
        with UserEditFiles(root) as files:
            values = [files.read(change.path) for change in changes]
        if all(value == change.after for value, change in zip(values, changes)):
            return _state(db, artifact, "applied", "Recovered complete user output; no files were rewritten.")
        if all(value == change.before for value, change in zip(values, changes)):
            return _state(db, artifact, "failed", "Recovered untouched inputs; no edit was applied.")
        if keep_current:
            _idle(db, session_id)
            metadata["resolution"] = {"action": "keep_current", "files": [
                {"path": change.path, "sha256": digest(value)} for change, value in zip(changes, values)]}
            artifact.meta_json = json.dumps(metadata)
            return _state(db, artifact, "resolved", "User explicitly kept the current files; partial edits are not marked applied.")
    except (UserPatchError, OSError, ValueError):
        pass
    return _state(db, artifact, "unresolved", "Current files or ownership differ; automatic recovery made no writes.")


def recover_user_edits(engine):
    with DbSession(engine) as db:
        records = db.exec(select(Artifact).where(Artifact.artifact_type == USER_EDIT_TYPE,
                                                Artifact.status == "applying")).all()
        for artifact in records:
            run = db.get(TaskRun, artifact.task_run_id)
            task = db.get(Task, run.task_id) if run else None
            if task:
                reconcile_edit(db, task.session_id, artifact.id, startup=True)
