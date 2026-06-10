import json
import subprocess
import difflib
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.artifact_versions import record_artifact_version
from app.events import append_task_run_event
from app.models import Artifact, Diff, Task, TaskRun
from app.models import Session as AgentHubSession
from app.models import utc_now
from app.provider_evidence import provider_evidence_for_task_run
from app.target_registry import TargetRegistryError, get_target_for_workspace


class DiffCollectionError(ValueError):
    pass


FILE_SNAPSHOT_SCHEMA_VERSION = "agenthub.file_snapshot.v1"
MAX_SNAPSHOT_FILE_BYTES = 512 * 1024


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


def git_diff_pathspec(
    *,
    allowed_paths: Optional[list[str]] = None,
    denied_paths: Optional[list[str]] = None,
) -> list[str]:
    roots = allowed_paths if allowed_paths else ["."]
    pathspec = list(roots)
    denied = denied_paths or []
    for denied_path in ["node_modules", "node_modules/**", "**/node_modules/**", *denied]:
        pathspec.append(f":(exclude){denied_path}")
        if not denied_path.endswith("/**") and not denied_path.endswith("*"):
            pathspec.append(f":(exclude){denied_path}/**")
    return pathspec


def _default_git_diff_pathspec() -> list[str]:
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


def capture_file_snapshot_for_worktree(
    worktree_path: str,
    *,
    allowed_paths: Optional[list[str]] = None,
    denied_paths: Optional[list[str]] = None,
) -> dict[str, Any]:
    root = Path(worktree_path)
    if not root.exists():
        return {
            "schemaVersion": FILE_SNAPSHOT_SCHEMA_VERSION,
            "available": False,
            "reason": "worktree_not_found",
            "files": {},
            "skippedFiles": [],
        }

    denied = denied_paths or []
    files: dict[str, dict[str, Any]] = {}
    skipped_files: list[dict[str, str]] = []
    for path in _snapshot_candidate_files(root, allowed_paths=allowed_paths, denied_paths=denied):
        relative_path = _relative_posix_path(root, path)
        if not relative_path or _matches_any_path(relative_path, denied):
            continue
        if path.is_symlink():
            skipped_files.append({"path": relative_path, "reason": "symlink"})
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            skipped_files.append({"path": relative_path, "reason": "read_failed"})
            continue
        if len(raw) > MAX_SNAPSHOT_FILE_BYTES:
            skipped_files.append({"path": relative_path, "reason": "too_large"})
            continue
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            skipped_files.append({"path": relative_path, "reason": "binary"})
            continue
        files[relative_path] = {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size": len(raw),
            "content": content,
        }

    snapshot_id = _snapshot_id(files)
    return {
        "schemaVersion": FILE_SNAPSHOT_SCHEMA_VERSION,
        "available": True,
        "snapshotId": snapshot_id,
        "fileCount": len(files),
        "files": files,
        "skippedFiles": skipped_files,
    }


def collect_task_run_diff(db: DbSession, task_run_id: str) -> StoredDiffArtifact:
    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        raise DiffCollectionError(f"TaskRun not found: {task_run_id}")

    worktree_path = Path(task_run.worktree_path)
    if not worktree_path.exists():
        raise DiffCollectionError(f"TaskRun worktree does not exist: {task_run.worktree_path}")

    base_ref = task_run.base_ref or capture_base_ref_for_worktree(task_run.worktree_path)
    policy = _target_diff_policy(db, task_run)
    pathspec = git_diff_pathspec(**policy)
    snapshot_result = None
    if base_ref is None:
        snapshot_result = _snapshot_diff_result(db, task_run, policy=policy)
        if snapshot_result is None:
            raise DiffCollectionError("TaskRun does not have a usable baseRef or file snapshot.")
        base_ref = snapshot_result["baseRef"]
        patch_text = snapshot_result["patchText"]
        changed_files = snapshot_result["changedFiles"]
        stats = snapshot_result["stats"]
        head_ref = snapshot_result["headRef"]
    else:
        tracked_patch = _run_git(worktree_path, ["diff", "-p", base_ref, "--", *pathspec])
        untracked_files = _untracked_files(worktree_path, pathspec)
        untracked_patch = _untracked_patch(worktree_path, untracked_files)
        patch_text = _join_patches(tracked_patch, untracked_patch)
        changed_files = _changed_files(worktree_path, base_ref, pathspec)
        changed_files = [*changed_files, *[path for path in untracked_files if path not in changed_files]]
        stats = _merge_stats(
            _diff_stats(worktree_path, base_ref, pathspec),
            _untracked_stats(worktree_path, untracked_files),
        )
        head_ref = _head_ref(worktree_path, has_worktree_changes=bool(changed_files))

    now = utc_now()
    task_run.base_ref = base_ref
    task_run.head_ref = head_ref
    task_run.updated_at = now
    provider_evidence = provider_evidence_for_task_run(
        db,
        task_run,
        changed_files=changed_files,
    )
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
                "providerEvidence": provider_evidence,
                **({"snapshotDiff": snapshot_result["metadata"]} if snapshot_result else {}),
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

    record_artifact_version(
        db,
        artifact,
        source_task_run_id=task_run.id,
        git_base_ref=base_ref,
        git_head_ref=head_ref,
        changed_files=changed_files,
        summary=f"Diff captured {len(changed_files)} changed file(s).",
    )

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
                **({"snapshotDiff": snapshot_result["metadata"]} if snapshot_result else {}),
                "providerEvidence": {
                    **provider_evidence,
                    "artifactRefs": {"diffArtifactId": artifact.id},
                },
            },
            separators=(",", ":"),
        ),
    )

    return _to_stored_diff(artifact, diff)


def record_diff_collection_failure(
    db: DbSession,
    task_run_id: str,
    exc: Exception,
) -> None:
    append_task_run_event(
        db,
        task_run_id=task_run_id,
        event_type="artifact.diff.failed",
        payload_json=json.dumps(
            {
                "status": "failed",
                "errorCode": "ARTIFACT_COLLECTION_FAILED",
                "errorMessage": str(exc),
                "message": f"Diff collection failed: {exc}",
            },
            separators=(",", ":"),
        ),
    )


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


def _snapshot_diff_result(
    db: DbSession,
    task_run: TaskRun,
    *,
    policy: Optional[dict[str, list[str]]] = None,
) -> Optional[dict[str, Any]]:
    checkpoint = _pre_run_checkpoint(task_run)
    snapshot = checkpoint.get("fileSnapshot")
    uses_empty_base = not (isinstance(snapshot, dict) and snapshot.get("available") is True)
    if uses_empty_base and not _is_external_target_task(db, task_run):
        return None
    if policy is None:
        policy = _target_diff_policy(db, task_run)
    current_snapshot = capture_file_snapshot_for_worktree(
        task_run.worktree_path,
        allowed_paths=policy.get("allowed_paths"),
        denied_paths=policy.get("denied_paths"),
    )
    if current_snapshot.get("available") is not True:
        raise DiffCollectionError(
            str(current_snapshot.get("reason") or "File snapshot capture failed.")
        )

    before_files = {} if uses_empty_base else _snapshot_files(snapshot)
    after_files = _snapshot_files(current_snapshot)
    changed_files = [
        path
        for path in sorted({*before_files.keys(), *after_files.keys()})
        if before_files.get(path, {}).get("sha256") != after_files.get(path, {}).get("sha256")
    ]
    patch_text = _snapshot_patch(before_files, after_files, changed_files)
    stats = _snapshot_stats(before_files, after_files, changed_files)
    base_ref = (
        "filesystem-snapshot:empty"
        if uses_empty_base
        else str(snapshot.get("snapshotId") or _snapshot_id(before_files))
    )
    head_ref = str(current_snapshot.get("snapshotId") or _snapshot_id(after_files))

    return {
        "baseRef": base_ref,
        "headRef": head_ref,
        "patchText": patch_text,
        "changedFiles": changed_files,
        "stats": stats,
        "metadata": {
            "schemaVersion": FILE_SNAPSHOT_SCHEMA_VERSION,
            "source": "file_snapshot_empty_base" if uses_empty_base else "file_snapshot",
            "baseSnapshotId": base_ref,
            "headSnapshotId": head_ref,
            "baseFileCount": len(before_files),
            "headFileCount": len(after_files),
            "skippedFiles": current_snapshot.get("skippedFiles", []),
        },
    }


def _is_external_target_task(db: DbSession, task_run: TaskRun) -> bool:
    task = db.get(Task, task_run.task_id)
    if task is None:
        return False
    try:
        plan = json.loads(task.plan_json)
    except json.JSONDecodeError:
        return False
    target_id = plan.get("targetId") if isinstance(plan, dict) else None
    return isinstance(target_id, str) and target_id.startswith("external-")


def _pre_run_checkpoint(task_run: TaskRun) -> dict[str, Any]:
    try:
        metrics = json.loads(task_run.metrics_json)
    except json.JSONDecodeError:
        return {}
    if not isinstance(metrics, dict):
        return {}
    checkpoint = metrics.get("preRunCheckpoint")
    return checkpoint if isinstance(checkpoint, dict) else {}


def _snapshot_files(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_files = snapshot.get("files")
    if not isinstance(raw_files, dict):
        return {}
    files: dict[str, dict[str, Any]] = {}
    for path, item in raw_files.items():
        if isinstance(path, str) and isinstance(item, dict):
            content = item.get("content")
            sha256 = item.get("sha256")
            if isinstance(content, str) and isinstance(sha256, str):
                files[_normalize_path(path)] = {**item, "content": content, "sha256": sha256}
    return files


def _snapshot_patch(
    before_files: dict[str, dict[str, Any]],
    after_files: dict[str, dict[str, Any]],
    changed_files: list[str],
) -> str:
    patches: list[str] = []
    for path in changed_files:
        before = before_files.get(path)
        after = after_files.get(path)
        before_content = before.get("content") if before is not None else None
        after_content = after.get("content") if after is not None else None
        patches.append(_unified_file_patch(path, before_content, after_content))
    return _join_patches(*patches)


def _unified_file_patch(path: str, before: Optional[str], after: Optional[str]) -> str:
    if before is None and after is None:
        return ""
    header = [f"diff --git a/{path} b/{path}"]
    from_file = f"a/{path}"
    to_file = f"b/{path}"
    if before is None:
        header.append("new file mode 100644")
        from_file = "/dev/null"
    if after is None:
        header.append("deleted file mode 100644")
        to_file = "/dev/null"
    diff_lines = difflib.unified_diff(
        (before or "").splitlines(),
        (after or "").splitlines(),
        fromfile=from_file,
        tofile=to_file,
        lineterm="",
    )
    return "\n".join([*header, *diff_lines]).rstrip() + "\n"


def _snapshot_stats(
    before_files: dict[str, dict[str, Any]],
    after_files: dict[str, dict[str, Any]],
    changed_files: list[str],
) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    additions = 0
    deletions = 0
    for path in changed_files:
        before_lines = _content_lines(before_files.get(path))
        after_lines = _content_lines(after_files.get(path))
        added, removed = _line_delta(before_lines, after_lines)
        files.append({"path": path, "additions": added, "deletions": removed})
        additions += added
        deletions += removed
    return {
        "filesChanged": len(files),
        "additions": additions,
        "deletions": deletions,
        "files": files,
    }


def _content_lines(file_item: Optional[dict[str, Any]]) -> list[str]:
    if file_item is None:
        return []
    content = file_item.get("content")
    return content.splitlines() if isinstance(content, str) else []


def _line_delta(before_lines: list[str], after_lines: list[str]) -> tuple[int, int]:
    added = 0
    removed = 0
    for line in difflib.ndiff(before_lines, after_lines):
        if line.startswith("+ "):
            added += 1
        elif line.startswith("- "):
            removed += 1
    return added, removed


def _changed_files(worktree_path: Path, base_ref: str, pathspec: list[str]) -> list[str]:
    output = _run_git(worktree_path, ["diff", "--name-only", base_ref, "--", *pathspec])
    return [line for line in output.splitlines() if line]


def _untracked_files(worktree_path: Path, pathspec: list[str]) -> list[str]:
    output = _run_git(
        worktree_path,
        ["ls-files", "--others", "--exclude-standard", "--", *pathspec],
    )
    return [line for line in output.splitlines() if line]


def _untracked_patch(worktree_path: Path, files: list[str]) -> str:
    patches: list[str] = []
    for path in files:
        output = _run_git_diff_no_index(worktree_path, ["/dev/null", path])
        if output:
            patches.append(output)
    return "\n".join(patch.rstrip() for patch in patches if patch.strip())


def _join_patches(*patches: str) -> str:
    clean = [patch.rstrip() for patch in patches if patch.strip()]
    if not clean:
        return ""
    return "\n".join(clean) + "\n"


def _diff_stats(worktree_path: Path, base_ref: str, pathspec: list[str]) -> dict[str, Any]:
    output = _run_git(worktree_path, ["diff", "--numstat", base_ref, "--", *pathspec])
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


def _untracked_stats(worktree_path: Path, files: list[str]) -> dict[str, Any]:
    file_stats = [
        {
            "path": path,
            "additions": _line_count(worktree_path / path),
            "deletions": 0,
        }
        for path in files
    ]
    return {
        "filesChanged": len(file_stats),
        "additions": sum(item["additions"] for item in file_stats),
        "deletions": 0,
        "files": file_stats,
    }


def _merge_stats(*stats_items: dict[str, Any]) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    additions = 0
    deletions = 0
    for stats in stats_items:
        stat_files = stats.get("files")
        if isinstance(stat_files, list):
            files.extend(item for item in stat_files if isinstance(item, dict))
        additions += int(stats.get("additions") or 0)
        deletions += int(stats.get("deletions") or 0)
    return {
        "filesChanged": len(files),
        "additions": additions,
        "deletions": deletions,
        "files": files,
    }


def _line_count(path: Path) -> int:
    try:
        return len(path.read_text().splitlines())
    except OSError:
        return 0


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


def _run_git_diff_no_index(worktree_path: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", "diff", "--no-index", "--", *args],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise DiffCollectionError(str(exc)) from exc
    if result.returncode not in {0, 1}:
        message = result.stderr.strip() or result.stdout.strip() or "Git command failed."
        raise DiffCollectionError(message)
    return result.stdout


def _target_diff_policy(db: DbSession, task_run: TaskRun) -> dict[str, list[str]]:
    task = db.get(Task, task_run.task_id)
    if task is None:
        return {}
    session = db.get(AgentHubSession, task.session_id)
    if session is None:
        return {}
    try:
        plan = json.loads(task.plan_json)
    except json.JSONDecodeError:
        return {}
    target_id = plan.get("targetId") if isinstance(plan, dict) else None
    if not isinstance(target_id, str):
        return {}
    try:
        target = get_target_for_workspace(db, session.workspace_id, target_id)
    except TargetRegistryError:
        return {}
    return {
        "allowed_paths": list(target.allowed_paths),
        "denied_paths": list(target.denied_paths),
    }


def _snapshot_candidate_files(
    root: Path,
    *,
    allowed_paths: Optional[list[str]],
    denied_paths: Optional[list[str]],
) -> list[Path]:
    candidates: list[Path] = []
    roots = allowed_paths or ["."]
    denied = denied_paths or []
    for allowed_path in roots:
        normalized = _normalize_path(allowed_path)
        if normalized in {"", ".", "*"}:
            candidate_root = root
        elif normalized.endswith("/*"):
            candidate_root = root / normalized[:-2]
        else:
            candidate_root = root / normalized
        if candidate_root.is_file():
            candidates.append(candidate_root)
        elif candidate_root.is_dir():
            candidates.extend(_iter_snapshot_files(root, candidate_root, denied))
    return sorted(set(candidates), key=lambda path: _relative_posix_path(root, path))


def _iter_snapshot_files(root: Path, current: Path, denied_paths: list[str]) -> list[Path]:
    files: list[Path] = []
    try:
        children = sorted(current.iterdir(), key=lambda path: path.name)
    except OSError:
        return files
    for child in children:
        relative_path = _relative_posix_path(root, child)
        if not relative_path or _matches_any_path(relative_path, denied_paths):
            continue
        if child.is_dir() and not child.is_symlink():
            files.extend(_iter_snapshot_files(root, child, denied_paths))
        elif child.is_file():
            files.append(child)
    return files


def _relative_posix_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return ""


def _matches_any_path(path: str, patterns: list[str]) -> bool:
    normalized = _normalize_path(path)
    return any(_matches_path_pattern(normalized, pattern) for pattern in patterns)


def _matches_path_pattern(path: str, pattern: str) -> bool:
    normalized_pattern = _normalize_path(pattern)
    if not normalized_pattern:
        return False
    if normalized_pattern in {".", "*"}:
        return True
    if normalized_pattern.endswith("/**"):
        prefix = normalized_pattern[:-3]
        return path == prefix or path.startswith(f"{prefix}/")
    if normalized_pattern.startswith("**/"):
        suffix = normalized_pattern[3:]
        return path == suffix or path.endswith(f"/{suffix}") or path.startswith(f"{suffix}/")
    if normalized_pattern.endswith("*"):
        return path.startswith(normalized_pattern[:-1])
    if "/" not in normalized_pattern:
        return normalized_pattern in path.split("/")
    return path == normalized_pattern or path.startswith(f"{normalized_pattern}/")


def _normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.rstrip("/")


def _snapshot_id(files: dict[str, dict[str, Any]]) -> str:
    payload = {
        path: item.get("sha256")
        for path, item in sorted(files.items())
        if isinstance(item.get("sha256"), str)
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"filesystem-snapshot:{digest}"


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
