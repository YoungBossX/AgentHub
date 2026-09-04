"""Opt-in, server-owned write branches with separately verified integration."""

import json
import subprocess
from pathlib import Path
from typing import Optional
from uuid import UUID

from sqlmodel import Session as DbSession

from app.models import Session, Task, TaskRun
from app.process_environment import project_process_env
from app.target_registry import DEMO_BACKEND_TARGET_ID, DEMO_FRONTEND_TARGET_ID

ISOLATED_WRITE_MODE = "isolated_write"
EXECUTION_WORKTREE_KEY = "executionWorktree"
BUILTIN_WRITE_TARGETS = {DEMO_BACKEND_TARGET_ID, DEMO_FRONTEND_TARGET_ID}


class ExecutionWorktreeError(ValueError):
    pass


def isolation_requested(task: Task) -> bool:
    return _object(task.plan_json).get("executionMode") == ISOLATED_WRITE_MODE


def execution_binding(run: TaskRun) -> Optional[dict]:
    value = _object(run.metrics_json).get(EXECUTION_WORKTREE_KEY)
    return value if isinstance(value, dict) else None


def requires_integration(run: TaskRun) -> bool:
    # Identify isolated origins, even after integration. Callers must validate
    # dag_integration.integration_for_run rather than trust a "merged" flag.
    return EXECUTION_WORKTREE_KEY in _object(run.metrics_json)


def _object(value: str) -> dict:
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-c", "core.hooksPath=", "-C", str(root), *args],
            env=project_process_env(), capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ExecutionWorktreeError("Execution worktree Git operation unavailable.") from exc
    if result.returncode:
        raise ExecutionWorktreeError("Execution worktree Git validation/operation failed.")
    return result.stdout.strip()


def _paths(session: Session, run_id: str) -> tuple[Path, Path, str]:
    # IDs, not user-supplied branch/path metadata, define ownership.
    try:
        if str(UUID(session.id)) != session.id or str(UUID(run_id)) != run_id:
            raise ValueError
    except ValueError as exc:
        raise ExecutionWorktreeError("Execution worktree ownership requires canonical UUIDs.") from exc
    source = Path(session.worktree_path).absolute()
    root = source.parent / f".executions-{session.id}"
    destination = root / run_id
    for path in (source, root, destination):
        if path.resolve() != path:
            raise ExecutionWorktreeError("Execution worktree paths must not traverse links.")
    return source, destination, f"codex/agenthub-execution/{session.id}/{run_id}"


def _repository_identity(source: Path) -> tuple[str, Path]:
    if Path(_git(source, "rev-parse", "--show-toplevel")).resolve() != source:
        raise ExecutionWorktreeError("Session path is not a Git worktree root.")
    base = _git(source, "rev-parse", "HEAD")
    common = Path(_git(source, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve()
    return base, common


def allocate_execution_worktree(
    db: DbSession, *, task: Task, session: Session, run_id: str,
    target_id: Optional[str], access_mode: str, previous_run_id: Optional[str] = None,
) -> tuple[Optional[dict], Optional[str]]:
    """Return a verified binding or a conservative preflight fallback reason.

    Once allocation starts (or when retrying an isolated run), failures are
    fatal: never silently move an attempt back onto the canonical worktree.
    """
    previous = db.get(TaskRun, previous_run_id) if previous_run_id else None
    retry_isolated = previous is not None and requires_integration(previous)
    if not isolation_requested(task) and not retry_isolated:
        return None, None
    try:
        if (access_mode != "write" or target_id not in BUILTIN_WRITE_TARGETS
                or task.intent_type not in {"frontend_change", "backend_change"}):
            raise ExecutionWorktreeError("Isolation supports built-in demo write targets only.")
        source, destination, branch = _paths(session, run_id)
        base, _ = _repository_identity(source)
        if _git(source, "status", "--porcelain", "--untracked-files=all"):
            raise ExecutionWorktreeError("Session worktree is dirty; retaining serial execution.")
        if retry_isolated:
            prior = validate_execution_worktree(db, previous)
            if previous.task_id != task.id or prior["baseCommit"] != base:
                raise ExecutionWorktreeError("Isolated retry baseline or task ownership changed.")
        if destination.exists():
            raise ExecutionWorktreeError("Execution worktree destination already exists.")
    except ExecutionWorktreeError as exc:
        if retry_isolated:
            raise
        return None, str(exc)

    destination.parent.mkdir(parents=True, exist_ok=True)
    _git(source, "worktree", "add", "-b", branch, str(destination), base)
    binding = {
        "schemaVersion": "agenthub.execution_worktree.v1",
        "mode": ISOLATED_WRITE_MODE,
        "taskRunId": run_id, "taskId": task.id,
        "sessionId": session.id, "workspaceId": session.workspace_id,
        "targetId": target_id, "sessionWorktreePath": str(source),
        "worktreePath": str(destination), "branch": branch, "baseCommit": base,
        "previousRunId": previous_run_id, "integrationStatus": "unmerged",
        "outputFormat": "diff_patch",
    }
    return binding, None


def validate_execution_worktree(db: DbSession, run: TaskRun) -> dict:
    binding = execution_binding(run)
    task = db.get(Task, run.task_id)
    session = db.get(Session, task.session_id) if task else None
    if binding is None or task is None or session is None:
        raise ExecutionWorktreeError("Execution worktree ownership record is missing.")
    source, destination, branch = _paths(session, run.id)
    from app.scheduler import target_id_for_task

    target_id = target_id_for_task(task, db)
    expected = {
        "schemaVersion": "agenthub.execution_worktree.v1", "mode": ISOLATED_WRITE_MODE,
        "taskRunId": run.id, "taskId": task.id, "sessionId": session.id,
        "workspaceId": session.workspace_id, "targetId": target_id,
        "sessionWorktreePath": str(source), "worktreePath": str(destination),
        "branch": branch, "baseCommit": run.base_ref,
    }
    if (target_id not in BUILTIN_WRITE_TARGETS
            or run.worktree_path != str(destination)
            or any(binding.get(key) != value for key, value in expected.items())):
        raise ExecutionWorktreeError("Execution worktree binding does not match its owner.")
    _, source_common = _repository_identity(source)
    head, common = _repository_identity(destination)
    if (common != source_common or head != run.base_ref
            or _git(destination, "symbolic-ref", "--short", "HEAD") != branch):
        raise ExecutionWorktreeError("Execution branch baseline or repository ownership changed.")
    # A copied directory/.git pointer must not masquerade as a registered worktree.
    registered = _git(source, "worktree", "list", "--porcelain").splitlines()
    if not any(line.startswith("worktree ") and Path(line[9:]).resolve() == destination
               for line in registered):
        raise ExecutionWorktreeError("Execution worktree is not registered to this repository.")
    return binding


def can_overlap_writes(db: DbSession, left: TaskRun, right: TaskRun) -> bool:
    try:
        first = validate_execution_worktree(db, left)
        second = validate_execution_worktree(db, right)
    except ExecutionWorktreeError:
        return False
    return (
        first["sessionId"] == second["sessionId"]
        and first["baseCommit"] == second["baseCommit"]
        and first["targetId"] != second["targetId"]
        and first["worktreePath"] != second["worktreePath"]
    )
