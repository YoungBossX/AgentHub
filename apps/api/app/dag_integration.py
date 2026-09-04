"""Local join coordinator: validate branch patches, stage, journal, then fast-forward."""

import hashlib
import json
import subprocess
from pathlib import Path
from uuid import UUID

from sqlmodel import Session as DbSession, select

from app.execution_worktrees import (
    ExecutionWorktreeError, _git, _repository_identity,
    requires_integration, validate_execution_worktree,
)
from app.events import stage_task_run_event
from app.models import Artifact, Diff, Session, SessionQueueEntry, TargetLock, Task, TaskRun, utc_now
from app.process_environment import project_process_env
from app.target_registry import get_target_for_workspace

TERMINAL = {"completed", "failed", "interrupted", "cancelled"}


class IntegrationError(ValueError):
    pass


class IntegrationWaiting(IntegrationError):
    pass


def _json(value: str) -> dict:
    try:
        parsed = json.loads(value)
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def latest_run(db: DbSession, task_id: str):
    return db.exec(select(TaskRun).where(TaskRun.task_id == task_id).order_by(
        TaskRun.created_at.desc(), TaskRun.id.desc(),
    )).first()


def _dependencies(db: DbSession, join: Task) -> list[TaskRun]:
    from app.scheduler import dependency_ids_for_task

    runs = []
    for task_id in dependency_ids_for_task(join):
        task = db.get(Task, task_id)
        if task is None or task.session_id != join.session_id or task.status != "completed":
            return []
        run = latest_run(db, task.id)
        if run is not None:
            if run.state != "completed":
                return []
            if requires_integration(run):
                runs.append(run)
    return sorted(runs, key=lambda run: (db.get(Task, run.task_id).priority, run.task_id))


def _records(db: DbSession, join_id: str) -> list[Artifact]:
    return [artifact for artifact in db.exec(
        select(Artifact).where(Artifact.artifact_type.in_({"integration", "conflict"}))
        .order_by(Artifact.created_at.desc(), Artifact.id.desc())
    ).all() if _json(artifact.meta_json).get("joinTaskId") == join_id]


def _candidate_path(session: Session, artifact_id: str) -> Path:
    if str(UUID(artifact_id)) != artifact_id or str(UUID(session.id)) != session.id:
        raise IntegrationError("Invalid integration ownership IDs.")
    source = Path(session.worktree_path).absolute()
    path = source.parent / f".integrations-{session.id}" / artifact_id
    if source.resolve() != source or path.resolve() != path:
        raise IntegrationError("Integration paths cannot traverse links.")
    return path


def _input_git(root: Path, args: list[str], value: str) -> str:
    result = subprocess.run(
        ["git", "-c", "core.hooksPath=", "-C", str(root), *args],
        # Binary stdin avoids Windows text-mode LF -> CRLF conversion, which
        # corrupts patches when three-way application compares Git blob bytes.
        input=value.encode("utf-8"), capture_output=True,
        env=project_process_env(), timeout=30,
    )
    if result.returncode:
        raise IntegrationError("Branch patch could not be applied without conflict.")
    return result.stdout.decode("utf-8")


def _assert_idle(db: DbSession, session_id: str) -> None:
    active = db.exec(select(TaskRun).join(Task, TaskRun.task_id == Task.id).where(
        Task.session_id == session_id, TaskRun.state.notin_(TERMINAL),
    )).first()
    queue = db.exec(select(SessionQueueEntry).where(
        SessionQueueEntry.session_id == session_id, SessionQueueEntry.state == "running",
    )).first()
    lock = db.exec(select(TargetLock).where(TargetLock.session_id == session_id, TargetLock.state == "held")).first()
    if active is not None or queue is not None or lock is not None:
        raise IntegrationWaiting("Session has an active execution; integration is waiting.")


def _patches(db: DbSession, runs: list[TaskRun]) -> list[tuple[TaskRun, Diff, dict]]:
    from app.task_runs import require_task_run_scope_passed

    result = []
    for run in runs:
        binding = validate_execution_worktree(db, run)
        require_task_run_scope_passed(db, run.id)
        artifact = db.exec(select(Artifact).where(
            Artifact.task_run_id == run.id, Artifact.artifact_type == "diff", Artifact.status == "ready",
        ).order_by(Artifact.created_at.desc(), Artifact.id.desc())).first()
        diff = db.exec(select(Diff).where(Diff.artifact_id == artifact.id)).first() if artifact else None
        if diff is None or diff.base_ref != run.base_ref:
            raise IntegrationError("Completed branch has no verified baseline Diff.")
        metadata = _json(artifact.meta_json)
        if metadata.get("executionWorktree") != binding:
            raise IntegrationError("Branch Diff ownership does not match its execution.")
        result.append((run, diff, binding))
    return result


def _source_inputs(patches) -> list[dict]:
    return [{"taskRunId": run.id, "taskId": run.task_id, "diffId": diff.id,
             "baseCommit": diff.base_ref, "targetId": binding["targetId"],
             "patchSha256": hashlib.sha256(diff.patch_text.encode("utf-8")).hexdigest()}
            for run, diff, binding in patches]


def _validate_candidate(session: Session, artifact: Artifact) -> dict:
    metadata = _json(artifact.meta_json)
    path = _candidate_path(session, artifact.id)
    source = Path(session.worktree_path).absolute()
    head, common = _repository_identity(path)
    _, source_common = _repository_identity(source)
    if (metadata.get("schemaVersion") != "agenthub.dag_integration.v1"
            or metadata.get("sessionId") != session.id or metadata.get("worktreePath") != str(path)
            or metadata.get("canonicalWorktreePath") != str(source)
            or head != metadata.get("mergeCommit") or common != source_common
            or _git(path, "status", "--porcelain", "--untracked-files=all")):
        raise IntegrationError("Integration candidate ownership or contents changed.")
    if _git(path, "rev-parse", "HEAD^") != metadata.get("sourceHead"):
        raise IntegrationError("Integration commit parent changed.")
    if not any(line.startswith("worktree ") and Path(line[9:]).resolve() == path
               for line in _git(source, "worktree", "list", "--porcelain").splitlines()):
        raise IntegrationError("Integration candidate is not a registered worktree.")
    return metadata


def integration_for_run(db: DbSession, run: TaskRun, *, delivery: bool = False):
    """Read-only proof. A mutable merged flag is never sufficient."""
    task = db.get(Task, run.task_id)
    session = db.get(Session, task.session_id) if task else None
    if session is None or run.state != "completed":
        return None
    for artifact in db.exec(select(Artifact).where(
        Artifact.artifact_type == "integration", Artifact.status == "ready",
    ).order_by(Artifact.created_at.desc(), Artifact.id.desc())).all():
        metadata = _json(artifact.meta_json)
        if run.id not in metadata.get("sourceRunIds", []):
            continue
        try:
            metadata = _validate_candidate(session, artifact)
            join = db.get(Task, metadata["joinTaskId"])
            if join is None or [item.id for item in _dependencies(db, join)] != metadata["sourceRunIds"]:
                continue
            for item in metadata.get("inputs", []):
                diff = db.get(Diff, item["diffId"])
                if diff is None or hashlib.sha256(diff.patch_text.encode("utf-8")).hexdigest() != item["patchSha256"]:
                    raise IntegrationError("Integrated input evidence changed.")
            source = Path(session.worktree_path)
            _git(source, "merge-base", "--is-ancestor", metadata["mergeCommit"], "HEAD")
            if delivery:
                _assert_idle(db, session.id)
            if delivery and (_git(source, "rev-parse", "HEAD") != metadata["mergeCommit"]
                             or _git(source, "status", "--porcelain", "--untracked-files=all")):
                continue
            return artifact
        except (ExecutionWorktreeError, IntegrationError, KeyError, ValueError):
            continue
    return None


def delivery_worktree_path(db: DbSession, run: TaskRun) -> str:
    if not requires_integration(run):
        return run.worktree_path
    artifact = integration_for_run(db, run, delivery=True)
    if artifact is None:
        raise IntegrationError("Delivery requires a verified, clean integrated Session result.")
    session = db.get(Session, db.get(Task, run.task_id).session_id)
    return session.worktree_path


def delivery_evidence(db: DbSession, run: TaskRun) -> dict:
    if not requires_integration(run):
        return {}
    artifact = integration_for_run(db, run, delivery=True)
    if artifact is None:
        raise IntegrationError("Delivery integration evidence cannot be verified.")
    metadata = _json(artifact.meta_json)
    return {"artifactId": artifact.id, "mergeCommit": metadata["mergeCommit"],
            "sourceRunIds": metadata["sourceRunIds"]}


def _promote_candidate(session: Session, artifact: Artifact) -> None:
    metadata = _validate_candidate(session, artifact)
    source = Path(session.worktree_path)
    if _git(source, "status", "--porcelain", "--untracked-files=all"):
        raise IntegrationError("Canonical Session worktree is dirty; no changes were overwritten.")
    current = _git(source, "rev-parse", "HEAD")
    if current == metadata["mergeCommit"]:
        return  # Recover a crash after Git promotion but before SQLite completion.
    if current != metadata["sourceHead"]:
        raise IntegrationError("Canonical Session HEAD changed before integration promotion.")
    _git(source, "merge", "--ff-only", "--no-edit", metadata["mergeCommit"])
    if _git(source, "rev-parse", "HEAD") != metadata["mergeCommit"]:
        raise IntegrationError("Could not verify integration promotion.")


def _record_conflict(db, join, session, runs, reason, source_head, *, candidate=None, inputs=None):
    files = []
    if candidate is not None:
        path = _candidate_path(session, candidate.id)
        if path.exists():
            files = _git(path, "diff", "--name-only", "--diff-filter=U").splitlines()
        if candidate.status == "building":
            candidate.status = "failed"
            candidate.meta_json = json.dumps({"joinTaskId": join.id, "sessionId": session.id,
                "sourceRunIds": [run.id for run in runs], "sourceHead": source_head,
                "worktreePath": str(path), "reason": reason})
            db.add(candidate)
    artifact = Artifact(
        task_run_id=runs[-1].id, artifact_type="conflict", title="DAG integration blocked", status="blocked",
        meta_json=json.dumps({"joinTaskId": join.id, "sessionId": session.id,
            "sourceRunIds": [run.id for run in runs], "sourceHead": source_head,
            "reason": reason, "conflictingFiles": files, "inputs": inputs or [],
            "candidateArtifactId": candidate.id if candidate else None,
            "worktreePath": str(_candidate_path(session, candidate.id)) if candidate else None,
            "recovery": "Retry only failed branches; retry integration after resolving canonical conflicts."}),
    )
    db.add(artifact)
    plan = _json(join.plan_json)
    plan["integration"] = {"status": "blocked", "artifactId": artifact.id, "reason": reason}
    join.plan_json = json.dumps(plan)
    join.status = "blocked"
    db.add(join)
    stage_task_run_event(db, task_run_id=runs[-1].id, event_type="artifact.conflict.ready",
                         payload_json=json.dumps({"artifactId": artifact.id, "joinTaskId": join.id, "reason": reason}))
    db.commit()
    db.refresh(artifact)
    return artifact


def integrate_join(bind, join_id: str, *, retry: bool = False):
    """Serialize coordinator/adapter launches with SQLite's existing writer lock.

    The prepared record is durable *before* canonical Git mutation. No adapter
    is launched here, and failure never rolls back or overwrites branch output.
    """
    from app.task_run_scope import TaskRunScopeError

    with DbSession(bind) as db:
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        join = db.get(Task, join_id)
        if join is None:
            raise IntegrationError("Join task not found.")
        runs = _dependencies(db, join)
        if not runs:
            return None
        session = db.get(Session, join.session_id)
        source = Path(session.worktree_path)
        records = _records(db, join.id)
        ids = [run.id for run in runs]
        source_head = _git(source, "rev-parse", "HEAD")
        for record in records:
            meta = _json(record.meta_json)
            if meta.get("sourceRunIds") != ids:
                continue
            if record.artifact_type == "integration" and record.status == "ready":
                return record if integration_for_run(db, runs[0]) is not None else None
            if (record.artifact_type == "integration" and record.status == "prepared"
                    and source_head in {meta.get("sourceHead"), meta.get("mergeCommit")}):
                candidate = record
                break
        else:
            candidate = None
        # Do not churn a blocked join without changed inputs or explicit retry.
        if not retry and records:
            last = _json(records[0].meta_json)
            already_promoted = candidate is not None and _json(candidate.meta_json).get("mergeCommit") == source_head
            if (not already_promoted and records[0].artifact_type == "conflict"
                    and last.get("sourceRunIds") == ids and last.get("sourceHead") == source_head):
                return None
        inputs = []
        try:
            _assert_idle(db, session.id)
            patches = _patches(db, runs)
            inputs = _source_inputs(patches)
            if candidate is None:
                if _git(source, "status", "--porcelain", "--untracked-files=all"):
                    raise IntegrationError("Canonical Session worktree is dirty; integration requires a clean baseline.")
                candidate = Artifact(task_run_id=runs[-1].id, artifact_type="integration",
                                     title="DAG integration", status="building")
                path = _candidate_path(session, candidate.id)
                path.parent.mkdir(parents=True, exist_ok=True)
                _git(source, "worktree", "add", "--detach", str(path), source_head)
                for run, diff, binding in patches:
                    if not diff.patch_text.strip():
                        continue
                    target = get_target_for_workspace(db, session.workspace_id, binding["targetId"])
                    records_text = _input_git(path, ["apply", "--numstat", "-z"], diff.patch_text)
                    paths = [line.split("\t", 2)[-1] for line in records_text.split("\0") if line]
                    if not paths or any(not target.permits_path(name) for name in paths):
                        raise IntegrationError("Branch patch contains a path outside its target policy.")
                    if any(mode in diff.patch_text for mode in ("mode 120000", "mode 160000")):
                        raise IntegrationError("Integration cannot introduce symlinks or submodules.")
                    before_tree = _git(path, "write-tree")
                    _input_git(path, ["apply", "--3way", "--index", "--whitespace=nowarn"], diff.patch_text)
                    actual_paths = [name for name in _git(path, "diff", "--cached", "--no-renames",
                                                         "--name-only", "-z", before_tree).split("\0") if name]
                    if any(not target.permits_path(name) for name in actual_paths):
                        raise IntegrationError("Applied branch patch escaped its target policy.")
                    entries = _git(path, "ls-files", "--stage", "--", *actual_paths).splitlines() if actual_paths else []
                    for entry in entries:
                        if entry.split(" ", 1)[0] not in {"100644", "100755"}:
                            raise IntegrationError("Integration outputs must be regular files.")
                _git(path, "-c", "user.name=AgentHub Integration", "-c", "user.email=agenthub@local.invalid",
                     "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-m",
                     f"Integrate DAG join {join.id}\n\nSource runs: {','.join(ids)}")
                metadata = {"schemaVersion": "agenthub.dag_integration.v1", "joinTaskId": join.id,
                    "sessionId": session.id, "sourceRunIds": ids, "inputs": inputs,
                    "canonicalWorktreePath": str(source.absolute()),
                    "sourceHead": source_head, "mergeCommit": _git(path, "rev-parse", "HEAD"),
                    "worktreePath": str(path), "changedFiles": _git(path, "diff", "--name-only", source_head, "HEAD").splitlines()}
                candidate.status = "prepared"
                candidate.meta_json = json.dumps(metadata)
                db.add(candidate)
                db.commit()
                db.connection().exec_driver_sql("BEGIN IMMEDIATE")
                db.refresh(join)
                db.refresh(session)
                db.refresh(candidate)
                if candidate.status == "ready":
                    return candidate
                if [run.id for run in _dependencies(db, join)] != ids:
                    raise IntegrationError("Join inputs changed before promotion.")
                _assert_idle(db, session.id)
                if _source_inputs(_patches(db, _dependencies(db, join))) != inputs:
                    raise IntegrationError("Join evidence changed before promotion.")
            elif _json(candidate.meta_json).get("inputs") != inputs:
                raise IntegrationError("Prepared integration input evidence changed.")
            _promote_candidate(session, candidate)
            candidate.status = "ready"
            candidate.updated_at = utc_now()
            plan = _json(join.plan_json)
            plan["integration"] = {"status": "ready", "artifactId": candidate.id,
                                   "mergeCommit": _json(candidate.meta_json)["mergeCommit"]}
            join.plan_json = json.dumps(plan)
            if join.status != "completed":
                join.status = "waiting_dependency"
            db.add(join)
            db.add(candidate)
            stage_task_run_event(db, task_run_id=runs[-1].id, event_type="artifact.integration.ready",
                                 payload_json=json.dumps({"artifactId": candidate.id, "joinTaskId": join.id,
                                                         "mergeCommit": _json(candidate.meta_json)["mergeCommit"]}))
            db.commit()
            db.refresh(candidate)
            return candidate
        except IntegrationWaiting:
            return None
        except (IntegrationError, ExecutionWorktreeError, TaskRunScopeError, OSError, subprocess.TimeoutExpired) as exc:
            return _record_conflict(db, join, session, runs, str(exc), source_head,
                                    candidate=candidate, inputs=inputs)


def integrate_ready_joins(db: DbSession, *, session_id: str | None = None) -> list[str]:
    """Also used by dispatcher restart recovery, independently of adapter callbacks."""
    from app.scheduler import dependency_ids_for_task

    tasks = db.exec(select(Task)).all()
    join_ids = [task.id for task in tasks if dependency_ids_for_task(task)
                and task.status != "completed" and (session_id is None or task.session_id == session_id)]
    ready = []
    db.commit()
    for join_id in join_ids:
        artifact = integrate_join(db.get_bind(), join_id)
        if artifact is not None and artifact.artifact_type == "integration" and artifact.status == "ready":
            ready.extend(_json(artifact.meta_json)["sourceRunIds"])
    db.expire_all()
    return list(dict.fromkeys(ready))


def integration_diagnostics(db: DbSession, join: Task) -> list[dict]:
    """Read-only UI projection; historical ready records are not current authority."""
    from app.scheduler import dependency_ids_for_task

    if not dependency_ids_for_task(join):
        return []
    records = _records(db, join.id)
    if not records:
        return []
    selected = _dependencies(db, join)
    verified = integration_for_run(db, selected[0]) if selected else None
    return [
        {
            "artifactId": record.id, "artifactType": record.artifact_type,
            "status": record.status, "createdAt": record.created_at.isoformat(),
            "verified": verified is not None and verified.id == record.id,
            **{key: value for key, value in _json(record.meta_json).items() if key in {
                "sourceRunIds", "mergeCommit", "sourceHead", "changedFiles",
                "conflictingFiles", "reason", "recovery", "inputs",
            }},
        }
        for record in records
    ]
