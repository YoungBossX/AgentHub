import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.events import append_task_run_event
from app.models import Artifact, Diff, TaskRun, utc_now


class DiffCollectionError(ValueError):
    pass


@dataclass(frozen=True)
class StoredDiffArtifact:
    id: str
    artifact_id: str
    task_run_id: str
    artifact_type: str
    title: str
    status: str
    base_ref: str
    head_ref: str
    patch_text: str
    changed_files: list[str]
    stats: dict[str, Any]


def git_diff_pathspec() -> list[str]:
    return [
        ".",
        ":(exclude)node_modules",
        ":(exclude)node_modules/**",
        ":(exclude)**/node_modules/**",
    ]


def capture_base_ref_for_worktree(worktree_path: str) -> Optional[str]:
    try:
        return _run_git(Path(worktree_path), ["rev-parse", "HEAD"]).strip()
    except DiffCollectionError:
        return None


def collect_task_run_diff(db: DbSession, task_run_id: str) -> StoredDiffArtifact:
    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        raise DiffCollectionError(f"TaskRun not found: {task_run_id}")

    worktree_path = Path(task_run.worktree_path)
    if not worktree_path.exists():
        raise DiffCollectionError(f"TaskRun worktree does not exist: {task_run.worktree_path}")

    base_ref = task_run.base_ref or capture_base_ref_for_worktree(task_run.worktree_path)
    if base_ref is None:
        raise DiffCollectionError("TaskRun does not have a usable baseRef.")

    patch_text = _run_git(worktree_path, ["diff", "-p", base_ref, "--", *git_diff_pathspec()])
    changed_files = _changed_files(worktree_path, base_ref)
    stats = _diff_stats(worktree_path, base_ref)
    head_ref = _head_ref(worktree_path, has_worktree_changes=bool(patch_text))

    now = utc_now()
    task_run.base_ref = base_ref
    task_run.head_ref = head_ref
    task_run.updated_at = now
    artifact = Artifact(
        task_run_id=task_run.id,
        artifact_type="diff",
        title="Git diff",
        status="ready",
        meta_json=json.dumps(
            {
                "baseRef": base_ref,
                "headRef": head_ref,
                "changedFiles": changed_files,
                "stats": stats,
            },
            separators=(",", ":"),
        ),
        created_at=now,
        updated_at=now,
    )
    db.add(task_run)
    db.add(artifact)
    db.commit()
    db.refresh(task_run)
    db.refresh(artifact)

    diff = Diff(
        artifact_id=artifact.id,
        base_ref=base_ref,
        head_ref=head_ref,
        patch_text=patch_text,
        changed_files_json=json.dumps(changed_files, separators=(",", ":")),
        stats_json=json.dumps(stats, separators=(",", ":")),
        created_at=now,
    )
    db.add(diff)
    db.commit()
    db.refresh(diff)

    append_task_run_event(
        db,
        task_run_id=task_run.id,
        event_type="artifact.diff.ready",
        payload_json=json.dumps(
            {
                "artifactId": artifact.id,
                "diffId": diff.id,
                "baseRef": base_ref,
                "headRef": head_ref,
                "changedFiles": changed_files,
                "stats": stats,
            },
            separators=(",", ":"),
        ),
    )

    return _to_stored_diff(artifact, diff)


def list_task_run_diffs(db: DbSession, task_run_id: str) -> list[StoredDiffArtifact]:
    artifacts = db.exec(
        select(Artifact)
        .where(Artifact.task_run_id == task_run_id, Artifact.artifact_type == "diff")
        .order_by(Artifact.created_at, Artifact.id)
    ).all()
    stored: list[StoredDiffArtifact] = []
    for artifact in artifacts:
        diff = db.exec(select(Diff).where(Diff.artifact_id == artifact.id)).first()
        if diff is not None:
            stored.append(_to_stored_diff(artifact, diff))
    return stored


def _changed_files(worktree_path: Path, base_ref: str) -> list[str]:
    output = _run_git(worktree_path, ["diff", "--name-only", base_ref, "--", *git_diff_pathspec()])
    return [line for line in output.splitlines() if line]


def _diff_stats(worktree_path: Path, base_ref: str) -> dict[str, Any]:
    output = _run_git(worktree_path, ["diff", "--numstat", base_ref, "--", *git_diff_pathspec()])
    files: list[dict[str, Any]] = []
    additions = 0
    deletions = 0
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added = _parse_numstat_value(parts[0])
        removed = _parse_numstat_value(parts[1])
        path = parts[2]
        files.append({"path": path, "additions": added, "deletions": removed})
        additions += added
        deletions += removed
    return {
        "filesChanged": len(files),
        "additions": additions,
        "deletions": deletions,
        "files": files,
    }


def _parse_numstat_value(value: str) -> int:
    if value == "-":
        return 0
    return int(value)


def _head_ref(worktree_path: Path, has_worktree_changes: bool) -> str:
    head = _run_git(worktree_path, ["rev-parse", "HEAD"]).strip()
    if has_worktree_changes:
        return f"{head}+worktree"
    return head


def _run_git(worktree_path: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise DiffCollectionError(str(exc)) from exc
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Git command failed."
        raise DiffCollectionError(message)
    return result.stdout


def _to_stored_diff(artifact: Artifact, diff: Diff) -> StoredDiffArtifact:
    return StoredDiffArtifact(
        id=diff.id,
        artifact_id=artifact.id,
        task_run_id=artifact.task_run_id,
        artifact_type=artifact.artifact_type,
        title=artifact.title,
        status=artifact.status,
        base_ref=diff.base_ref,
        head_ref=diff.head_ref,
        patch_text=diff.patch_text,
        changed_files=json.loads(diff.changed_files_json),
        stats=json.loads(diff.stats_json),
    )
