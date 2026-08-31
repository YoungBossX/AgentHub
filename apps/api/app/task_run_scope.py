from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
from threading import RLock
from typing import Any, Callable, Literal

from app.target_registry import (
    TargetProject,
    is_canonical_repository_path,
)


SCOPE_SNAPSHOT_SCHEMA_VERSION = "agenthub.task_run_scope.v2"
SCOPE_VALIDATION_SCHEMA_VERSION = "agenthub.task_run_scope_validation.v2"

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_GIT_OID_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_GIT_MODE_RE = re.compile(r"[0-7]{6}\Z")
_SAFE_METADATA_KEYS = frozenset(
    {
        "schema_version",
        "available",
        "reason",
        "protected_categories",
        "protected_entry_count",
    }
)
_INTERNAL_METADATA_KEYS = _SAFE_METADATA_KEYS | {
    "entries",
    "protected_control_digest",
}
_PROTECTED_CATEGORIES = frozenset({".env", ".git", "node_modules", "secrets"})
_SCOPE_STATES = frozenset(
    {
        "tracked-present",
        "tracked-missing",
        "staged-added-present",
        "staged-added-missing",
        "staged-modified-present",
        "staged-modified-missing",
        "staged-deleted-present",
        "staged-deleted-missing",
        "untracked-present",
        "unmerged-present",
        "unmerged-missing",
    }
)
_GIT_COMMAND_TIMEOUT_SECONDS = 10.0
_FILE_READ_CHUNK_SIZE = 1024 * 1024
_WINDOWS_DEFAULT_DATA_STREAM = "::$DATA"
_WINDOWS_ERROR_HANDLE_EOF = 38
_WINDOWS_STREAM_NAME_LENGTH = 260 + 36
# CPython on Windows can expose this undocumented bit through
# lstat().st_file_attributes for a new directory until its first enumeration.
# GetFileAttributesW and the post-enumeration lstat both report the durable
# attributes without it. Normalize it only for directory path observations;
# descriptor and regular-file identities remain exact.
_WINDOWS_TRANSIENT_DIRECTORY_STAT_ATTRIBUTE = 0x10000000
_ABSENT_FINGERPRINT = hashlib.sha256(
    b"agenthub.task_run_scope.absent.v1"
).hexdigest()
_DIRECTORY_FINGERPRINT = hashlib.sha256(
    b"agenthub.task_run_scope.directory.v1\0"
).hexdigest()

_PathIdentity = tuple[int, int, int, int]
_PathObservation = tuple[Path, str, _PathIdentity]
_PathObservations = tuple[_PathObservation, ...]
CaseSemantics = Literal["sensitive", "insensitive", "unknown"]
CaseSemanticsResolver = Callable[[Path, _PathObservations], str]
_CASE_SEMANTICS_ALIASES = {
    "sensitive": "sensitive",
    "case-sensitive": "sensitive",
    "insensitive": "insensitive",
    "case-insensitive": "insensitive",
    "unknown": "unknown",
}
_SCOPE_RUNTIME_CONTEXT_LOCK = RLock()
_WINDOWS_STREAM_API_LOCK = RLock()
_SCOPE_RUNTIME_CONTEXTS: dict[
    tuple[str, str, str], "ScopeRuntimeContext"
] = {}
_TARGET_LOCK_ACQUISITION_CONTEXTS: dict[
    str, "TargetLockAcquisitionContext"
] = {}


def _resolve_git_executable() -> str | None:
    candidate = shutil.which("git")
    if not candidate:
        return None
    candidate_path = Path(candidate)
    if not candidate_path.is_absolute():
        return None
    try:
        resolved = candidate_path.resolve(strict=True)
        resolved_stat = resolved.stat()
    except OSError:
        return None
    if not stat.S_ISREG(resolved_stat.st_mode):
        return None
    return str(resolved)


_GIT_EXECUTABLE = _resolve_git_executable()


@dataclass(frozen=True)
class ScopeEntry:
    path: str
    status: str
    fingerprint: str


@dataclass(frozen=True)
class ScopeSnapshot:
    schema_version: str
    available: bool
    reason: str | None
    entries: tuple[ScopeEntry, ...]
    protected_control_digest: str | None
    protected_categories: tuple[str, ...] = ()
    protected_entry_count: int = 0
    _transitioned_protected_paths: tuple[str, ...] = field(
        default=(), repr=False, compare=False
    )
    _trusted_git_dir: str | None = field(default=None, repr=False, compare=False)

    def to_metadata(self, *, include_internal: bool = False) -> dict[str, object]:
        """Return redacted audit metadata by default.

        The optional internal representation is for the scope guard's durable
        evidence only; it is never suitable for external diagnostics or UI.
        """
        metadata: dict[str, object] = {
            "schema_version": self.schema_version,
            "available": self.available,
            "reason": self.reason,
            "protected_categories": list(self.protected_categories),
            "protected_entry_count": self.protected_entry_count,
        }
        if include_internal:
            metadata["entries"] = [
                {
                    "path": entry.path,
                    "status": entry.status,
                    "fingerprint": entry.fingerprint,
                }
                for entry in self.entries
            ]
            metadata["protected_control_digest"] = self.protected_control_digest
        return metadata


@dataclass(frozen=True)
class ScopeDecision:
    status: str
    error_code: str | None
    target_id: str
    changed_paths: tuple[str, ...]
    rejected_paths: tuple[str, ...]
    reason: str | None


@dataclass(frozen=True)
class ScopeRuntimeContext:
    task_run_id: str
    workspace_id: str
    target_id: str
    policy_identity: str
    baseline_identity: str
    baseline_captured_at: str
    execution_attempt_id: str = field(repr=False)
    control_key: str = field(repr=False)
    trusted_git_dir: str = field(repr=False)
    lock_id: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class TargetLockAcquisitionContext:
    task_run_id: str
    target_id: str
    session_id: str
    worker_id: str
    lock_id: str = field(repr=False)


@dataclass
class _ProtectedAudit:
    categories: set[str] = field(default_factory=set)
    entry_count: int = 0

    def record(self, category: str) -> None:
        self.categories.add(category)
        self.entry_count += 1


@dataclass(frozen=True)
class _ProtectedFootprint:
    digest: str
    categories: tuple[str, ...]
    entry_count: int
    excluded_roots: tuple[Path, ...]
    transitioned_protected_paths: tuple[str, ...]
    trusted_git_dir: Path
    trusted_git_dir_identity: tuple[tuple[int, int, int, int], ...]


@dataclass(frozen=True)
class _GitLayerEntry:
    mode: str
    oid: str
    stage: int = 0


@dataclass(frozen=True)
class _TrustedGitExecutable:
    path: Path
    observations: _PathObservations
    content_sha256: str


class TaskRunScopeError(ValueError):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


class _SnapshotCaptureError(RuntimeError):
    pass


@dataclass
class _CaseSemanticsContext:
    """Resolve directory case rules from the assigned-root observation chain."""

    resolver: CaseSemanticsResolver | None = None

    def resolve(
        self,
        directory: Path,
        observations: _PathObservations,
    ) -> CaseSemantics:
        _require_path_observations(observations)
        if not observations or observations[-1][0] != directory:
            raise _SnapshotCaptureError
        result = (
            self.resolver(directory, observations)
            if self.resolver is not None
            else _probe_case_semantics(directory, observations)
        )
        if not isinstance(result, str):
            raise _SnapshotCaptureError
        normalized = _CASE_SEMANTICS_ALIASES.get(result.strip().lower())
        if normalized is None:
            raise _SnapshotCaptureError
        _require_path_observations(observations)
        semantics: CaseSemantics = normalized  # type: ignore[assignment]
        return semantics


class _WindowsFindStreamData(ctypes.Structure):
    _fields_ = (
        ("StreamSize", ctypes.c_longlong),
        ("cStreamName", ctypes.c_wchar * _WINDOWS_STREAM_NAME_LENGTH),
    )


class _WindowsStreamApi:
    def __init__(self, kernel32: Any) -> None:
        self._find_first_stream = kernel32.FindFirstStreamW
        self._find_first_stream.argtypes = (
            wintypes.LPCWSTR,
            wintypes.INT,
            ctypes.POINTER(_WindowsFindStreamData),
            wintypes.DWORD,
        )
        self._find_first_stream.restype = wintypes.HANDLE
        self._find_next_stream = kernel32.FindNextStreamW
        self._find_next_stream.argtypes = (
            wintypes.HANDLE,
            ctypes.POINTER(_WindowsFindStreamData),
        )
        self._find_next_stream.restype = wintypes.BOOL
        self._find_close = kernel32.FindClose
        self._find_close.argtypes = (wintypes.HANDLE,)
        self._find_close.restype = wintypes.BOOL
        self._invalid_handle = wintypes.HANDLE(-1).value

    def find_first(self, path: str) -> tuple[object | None, str | None, int]:
        data = _WindowsFindStreamData()
        ctypes.set_last_error(0)
        handle = self._find_first_stream(path, 0, ctypes.byref(data), 0)
        if handle == self._invalid_handle:
            return None, None, ctypes.get_last_error()
        return handle, data.cStreamName, 0

    def find_next(self, handle: object) -> tuple[bool, str | None, int]:
        data = _WindowsFindStreamData()
        ctypes.set_last_error(0)
        found = bool(self._find_next_stream(handle, ctypes.byref(data)))
        if not found:
            return False, None, ctypes.get_last_error()
        return True, data.cStreamName, 0

    def find_close(self, handle: object) -> bool:
        ctypes.set_last_error(0)
        return bool(self._find_close(handle))


_WINDOWS_STREAM_API: _WindowsStreamApi | None = None


def _load_windows_stream_api() -> _WindowsStreamApi:
    global _WINDOWS_STREAM_API
    if os.name != "nt":
        raise _SnapshotCaptureError
    with _WINDOWS_STREAM_API_LOCK:
        if _WINDOWS_STREAM_API is None:
            try:
                kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                _WINDOWS_STREAM_API = _WindowsStreamApi(kernel32)
            except BaseException:
                raise _SnapshotCaptureError from None
        return _WINDOWS_STREAM_API


def _enumerate_windows_streams(path: Path, *, api: Any | None = None) -> None:
    try:
        stream_api = api if api is not None else _load_windows_stream_api()
        first = stream_api.find_first(str(path))
    except BaseException:
        raise _SnapshotCaptureError from None
    if not isinstance(first, tuple) or len(first) != 3:
        raise _SnapshotCaptureError
    handle, stream_name, error_code = first
    if handle is None:
        if (
            stream_name is None
            and type(error_code) is int
            and error_code == _WINDOWS_ERROR_HANDLE_EOF
        ):
            return
        raise _SnapshotCaptureError
    if type(handle) is bool or (type(handle) is int and handle == 0):
        raise _SnapshotCaptureError

    failed = False
    try:
        if (
            type(error_code) is not int
            or type(stream_name) is not str
            or error_code != 0
            or stream_name != _WINDOWS_DEFAULT_DATA_STREAM
        ):
            raise _SnapshotCaptureError
        while True:
            result = stream_api.find_next(handle)
            if not isinstance(result, tuple) or len(result) != 3:
                raise _SnapshotCaptureError
            found, stream_name, error_code = result
            if type(found) is not bool or type(error_code) is not int:
                raise _SnapshotCaptureError
            if not found:
                if (
                    stream_name is None
                    and error_code == _WINDOWS_ERROR_HANDLE_EOF
                ):
                    break
                raise _SnapshotCaptureError
            if (
                type(stream_name) is not str
                or error_code != 0
                or stream_name != _WINDOWS_DEFAULT_DATA_STREAM
            ):
                raise _SnapshotCaptureError
    except BaseException:
        failed = True
    try:
        closed = stream_api.find_close(handle)
    except BaseException:
        closed = False
    if failed or closed is not True:
        raise _SnapshotCaptureError


def _require_no_named_streams(path: Path) -> None:
    if os.name == "nt":
        _enumerate_windows_streams(path)


def new_scope_control_key() -> str:
    return secrets.token_urlsafe(32)


def store_task_run_scope_runtime_context(
    task_run_id: str,
    *,
    trusted_git_dir: str,
    workspace_id: str,
    target_id: str,
    policy_identity: str,
    baseline_identity: str,
    baseline_captured_at: str,
    execution_attempt_id: str,
    lock_id: str | None = None,
    control_key: str | None = None,
) -> ScopeRuntimeContext:
    binding_values = (
        task_run_id,
        trusted_git_dir,
        workspace_id,
        target_id,
        baseline_identity,
        baseline_captured_at,
        execution_attempt_id,
    )
    if (
        any(
            not isinstance(value, str) or not value.strip()
            for value in binding_values
        )
        or not _is_sha256(policy_identity)
        or (
            lock_id is not None
            and (
                not isinstance(lock_id, str)
                or not lock_id.strip()
            )
        )
    ):
        raise TaskRunScopeError(
            "TASK_RUN_SCOPE_UNVERIFIABLE",
            "The task run scope runtime context is unavailable.",
        )
    context = ScopeRuntimeContext(
        task_run_id=task_run_id,
        workspace_id=workspace_id,
        target_id=target_id,
        policy_identity=policy_identity,
        baseline_identity=baseline_identity,
        baseline_captured_at=baseline_captured_at,
        execution_attempt_id=execution_attempt_id,
        lock_id=lock_id,
        control_key=control_key or new_scope_control_key(),
        trusted_git_dir=trusted_git_dir,
    )
    key = (
        context.task_run_id,
        context.baseline_identity,
        context.execution_attempt_id,
    )
    with _SCOPE_RUNTIME_CONTEXT_LOCK:
        for existing_key in tuple(_SCOPE_RUNTIME_CONTEXTS):
            if existing_key[0] == task_run_id:
                _SCOPE_RUNTIME_CONTEXTS.pop(existing_key, None)
        _SCOPE_RUNTIME_CONTEXTS[key] = context
    return context


def get_task_run_scope_runtime_context(
    task_run_id: str,
    *,
    baseline_identity: str | None = None,
    execution_attempt_id: str | None = None,
) -> ScopeRuntimeContext | None:
    with _SCOPE_RUNTIME_CONTEXT_LOCK:
        if baseline_identity is not None and execution_attempt_id is not None:
            return _SCOPE_RUNTIME_CONTEXTS.get(
                (task_run_id, baseline_identity, execution_attempt_id)
            )
        if baseline_identity is not None or execution_attempt_id is not None:
            return None
        matches = [
            context
            for key, context in _SCOPE_RUNTIME_CONTEXTS.items()
            if key[0] == task_run_id
        ]
        return matches[0] if len(matches) == 1 else None


def clear_task_run_scope_runtime_context(task_run_id: str) -> None:
    with _SCOPE_RUNTIME_CONTEXT_LOCK:
        for key in tuple(_SCOPE_RUNTIME_CONTEXTS):
            if key[0] == task_run_id:
                _SCOPE_RUNTIME_CONTEXTS.pop(key, None)


def store_task_run_target_lock_acquisition_context(
    task_run_id: str,
    *,
    target_id: str,
    session_id: str,
    worker_id: str,
    lock_id: str,
) -> TargetLockAcquisitionContext:
    values = (task_run_id, target_id, session_id, worker_id, lock_id)
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise TaskRunScopeError(
            "TASK_RUN_SCOPE_UNVERIFIABLE",
            "The task run target lock context is unavailable.",
        )
    context = TargetLockAcquisitionContext(
        task_run_id=task_run_id,
        target_id=target_id,
        session_id=session_id,
        worker_id=worker_id,
        lock_id=lock_id,
    )
    with _SCOPE_RUNTIME_CONTEXT_LOCK:
        existing = _TARGET_LOCK_ACQUISITION_CONTEXTS.get(task_run_id)
        if existing is not None and existing != context:
            raise TaskRunScopeError(
                "TASK_RUN_SCOPE_UNVERIFIABLE",
                "The task run target lock context is unavailable.",
            )
        _TARGET_LOCK_ACQUISITION_CONTEXTS[task_run_id] = context
    return context


def get_task_run_target_lock_acquisition_context(
    task_run_id: str,
) -> TargetLockAcquisitionContext | None:
    with _SCOPE_RUNTIME_CONTEXT_LOCK:
        return _TARGET_LOCK_ACQUISITION_CONTEXTS.get(task_run_id)


def clear_task_run_target_lock_acquisition_context(task_run_id: str) -> None:
    with _SCOPE_RUNTIME_CONTEXT_LOCK:
        _TARGET_LOCK_ACQUISITION_CONTEXTS.pop(task_run_id, None)


def require_task_run_scope_runtime_context(
    task_run_id: str,
    *,
    workspace_id: str | None = None,
    target_id: str | None = None,
    policy_identity: str | None = None,
    baseline_identity: str | None = None,
    baseline_captured_at: str | None = None,
    execution_attempt_id: str | None = None,
    lock_id: str | None = None,
) -> ScopeRuntimeContext:
    context = get_task_run_scope_runtime_context(
        task_run_id,
        baseline_identity=baseline_identity,
        execution_attempt_id=execution_attempt_id,
    )
    if (
        context is None
        or (
            workspace_id is not None
            and context.workspace_id != workspace_id
        )
        or (
            target_id is not None
            and context.target_id != target_id
        )
        or (
            policy_identity is not None
            and context.policy_identity != policy_identity
        )
        or (
            baseline_captured_at is not None
            and context.baseline_captured_at != baseline_captured_at
        )
        or (lock_id is not None and context.lock_id != lock_id)
    ):
        raise TaskRunScopeError(
            "TASK_RUN_SCOPE_UNVERIFIABLE",
            "The task run scope runtime context is unavailable.",
        )
    return context


def capture_worktree_scope_snapshot(
    worktree_path: str | os.PathLike[str],
    *,
    control_key: str | bytes,
    runner: Callable[..., Any] | None = None,
    trusted_git_dir: str | os.PathLike[str] | None = None,
    case_semantics_resolver: CaseSemanticsResolver | None = None,
) -> ScopeSnapshot:
    """Capture a complete, content-free scope footprint for one worktree.

    `trusted_git_dir` is an execution-boundary value retained by the caller
    from the baseline capture.  When supplied after a pointer mutation, it is
    deliberately used instead of resolving the new, untrusted pointer target.
    """
    try:
        root, root_observations = _lexical_worktree_root(worktree_path)
        key = _control_key_bytes(control_key)
        case_context = _CaseSemanticsContext(case_semantics_resolver)
        _require_path_observations(root_observations)
        protected_initial = _capture_protected_control_footprint(
            root,
            key,
            trusted_git_dir=trusted_git_dir,
            root_observations=root_observations,
            case_context=case_context,
        )
        _require_path_observations(root_observations)
        entries_initial = _capture_scope_entries(
            root,
            protected_initial.trusted_git_dir,
            protected_initial.excluded_roots,
            trusted_git_dir_identity=protected_initial.trusted_git_dir_identity,
            runner=runner,
            root_observations=root_observations,
            case_context=case_context,
        )
        _require_path_observations(root_observations)
        protected_middle = _capture_protected_control_footprint(
            root,
            key,
            trusted_git_dir=protected_initial.trusted_git_dir,
            root_observations=root_observations,
            case_context=case_context,
        )
        _require_path_observations(root_observations)
        entries_final = _capture_scope_entries(
            root,
            protected_initial.trusted_git_dir,
            protected_middle.excluded_roots,
            trusted_git_dir_identity=protected_initial.trusted_git_dir_identity,
            runner=runner,
            root_observations=root_observations,
            case_context=case_context,
        )
        _require_path_observations(root_observations)
        protected_final = _capture_protected_control_footprint(
            root,
            key,
            trusted_git_dir=protected_initial.trusted_git_dir,
            root_observations=root_observations,
            case_context=case_context,
        )
        _require_path_observations(root_observations)
        entries_terminal = _capture_scope_entries(
            root,
            protected_initial.trusted_git_dir,
            protected_final.excluded_roots,
            trusted_git_dir_identity=protected_initial.trusted_git_dir_identity,
            runner=runner,
            root_observations=root_observations,
            case_context=case_context,
        )
        _require_path_observations(root_observations)
        protected_terminal = _capture_protected_control_footprint(
            root,
            key,
            trusted_git_dir=protected_initial.trusted_git_dir,
            root_observations=root_observations,
            case_context=case_context,
        )
        _require_path_observations(root_observations)
        if not (
            protected_initial
            == protected_middle
            == protected_final
            == protected_terminal
            and entries_initial == entries_final == entries_terminal
        ):
            raise _SnapshotCaptureError
        _require_path_observations(root_observations)
    except Exception:
        return _unavailable_snapshot("scope_capture_unavailable")

    return ScopeSnapshot(
        schema_version=SCOPE_SNAPSHOT_SCHEMA_VERSION,
        available=True,
        reason=None,
        entries=entries_initial,
        protected_control_digest=protected_initial.digest,
        protected_categories=protected_initial.categories,
        protected_entry_count=protected_initial.entry_count,
        _transitioned_protected_paths=protected_initial.transitioned_protected_paths,
        _trusted_git_dir=str(protected_initial.trusted_git_dir),
    )


def scope_snapshot_from_metadata(metadata: object) -> ScopeSnapshot:
    """Load only complete, canonical internal scope evidence; otherwise fail closed."""
    if not isinstance(metadata, dict) or set(metadata) != _INTERNAL_METADATA_KEYS:
        return _unavailable_snapshot("invalid_snapshot_metadata")

    schema_version = metadata.get("schema_version")
    available = metadata.get("available")
    reason = metadata.get("reason")
    raw_entries = metadata.get("entries")
    protected_digest = metadata.get("protected_control_digest")
    raw_categories = metadata.get("protected_categories")
    entry_count = metadata.get("protected_entry_count")
    if (
        schema_version != SCOPE_SNAPSHOT_SCHEMA_VERSION
        or type(available) is not bool
        or not _is_valid_audit_metadata(raw_categories, entry_count)
        or not isinstance(raw_entries, list)
    ):
        return _unavailable_snapshot("invalid_snapshot_metadata")
    categories = tuple(raw_categories)

    if not available:
        if (
            not isinstance(reason, str)
            or not reason
            or raw_entries
            or protected_digest is not None
            or categories
            or entry_count != 0
        ):
            return _unavailable_snapshot("invalid_snapshot_metadata")
        return ScopeSnapshot(
            schema_version=SCOPE_SNAPSHOT_SCHEMA_VERSION,
            available=False,
            reason=reason,
            entries=(),
            protected_control_digest=None,
        )

    if reason is not None or not _is_sha256(protected_digest):
        return _unavailable_snapshot("invalid_snapshot_metadata")

    entries: list[ScopeEntry] = []
    seen_paths: set[str] = set()
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict) or set(raw_entry) != {
            "path",
            "status",
            "fingerprint",
        }:
            return _unavailable_snapshot("invalid_snapshot_metadata")
        path = raw_entry.get("path")
        status = raw_entry.get("status")
        fingerprint = raw_entry.get("fingerprint")
        if (
            not _is_valid_repository_path(path)
            or _is_protected_repository_path(path)
            or not _is_valid_status(status)
            or not _is_sha256(fingerprint)
            or path in seen_paths
        ):
            return _unavailable_snapshot("invalid_snapshot_metadata")
        seen_paths.add(path)
        entries.append(ScopeEntry(path=path, status=status, fingerprint=fingerprint))

    ordered_entries = tuple(sorted(entries, key=_entry_sort_key))
    if tuple(entries) != ordered_entries:
        return _unavailable_snapshot("invalid_snapshot_metadata")
    return ScopeSnapshot(
        schema_version=SCOPE_SNAPSHOT_SCHEMA_VERSION,
        available=True,
        reason=None,
        entries=ordered_entries,
        protected_control_digest=protected_digest,
        protected_categories=categories,
        protected_entry_count=entry_count,
    )


def validate_scope_delta(
    target: TargetProject,
    baseline: ScopeSnapshot,
    current: ScopeSnapshot,
) -> ScopeDecision:
    if not _is_complete_snapshot(baseline) or not _is_complete_snapshot(current):
        return ScopeDecision(
            status="unverifiable",
            error_code="TASK_RUN_SCOPE_UNVERIFIABLE",
            target_id=target.target_id,
            changed_paths=(),
            rejected_paths=(),
            reason="The task run scope evidence is unavailable or invalid.",
        )

    changed_paths = _changed_paths(baseline.entries, current.entries)
    changed_paths = _exclude_newly_protected_deletions(
        changed_paths,
        baseline.entries,
        current.entries,
        current._transitioned_protected_paths,
    )
    rejected_paths = tuple(
        path for path in changed_paths if not target.permits_path(path)
    )
    if rejected_paths:
        return ScopeDecision(
            status="rejected",
            error_code="TASK_RUN_SCOPE_VIOLATION",
            target_id=target.target_id,
            changed_paths=changed_paths,
            rejected_paths=rejected_paths,
            reason="The task run changed paths outside the assigned target.",
        )

    if baseline.protected_control_digest != current.protected_control_digest:
        return ScopeDecision(
            status="rejected",
            error_code="TASK_RUN_SCOPE_VIOLATION",
            target_id=target.target_id,
            changed_paths=changed_paths,
            rejected_paths=("<protected-footprint>",),
            reason="The task run changed protected control state.",
        )

    return ScopeDecision(
        status="passed",
        error_code=None,
        target_id=target.target_id,
        changed_paths=changed_paths,
        rejected_paths=(),
        reason=None,
    )


def _unavailable_snapshot(reason: str) -> ScopeSnapshot:
    return ScopeSnapshot(
        schema_version=SCOPE_SNAPSHOT_SCHEMA_VERSION,
        available=False,
        reason=reason,
        entries=(),
        protected_control_digest=None,
    )


def _lexical_worktree_root(
    worktree_path: str | os.PathLike[str],
) -> tuple[Path, _PathObservations]:
    root = Path(worktree_path)
    if not root.is_absolute():
        raise _SnapshotCaptureError
    parts = root.parts
    if not parts:
        raise _SnapshotCaptureError

    current = Path(parts[0])
    observations: list[_PathObservation] = []
    for index, component in enumerate(parts):
        if index:
            if component in {"", ".", ".."}:
                raise _SnapshotCaptureError
            current /= component
        observation = _path_observation(current)
        if observation is None or observation[0] != "directory":
            raise _SnapshotCaptureError
        observations.append((current, observation[0], observation[1]))
    if current != root:
        raise _SnapshotCaptureError
    return root, tuple(observations)


def _control_key_bytes(control_key: str | bytes) -> bytes:
    if isinstance(control_key, str):
        key = control_key.encode("utf-8")
    elif isinstance(control_key, bytes):
        key = control_key
    else:
        raise _SnapshotCaptureError
    if not key:
        raise _SnapshotCaptureError
    return key


def _capture_protected_control_footprint(
    root: Path,
    control_key: bytes,
    *,
    trusted_git_dir: str | os.PathLike[str] | None,
    root_observations: _PathObservations,
    case_context: _CaseSemanticsContext,
) -> _ProtectedFootprint:
    _require_root_observations(root, root_observations)
    resolved_git_control = _resolve_child_entry(
        root,
        ".git",
        root_observations,
        case_context,
        absent_allowed=False,
    )
    if resolved_git_control is None:
        raise _SnapshotCaptureError
    _, git_control, git_control_observation, git_control_observations = (
        resolved_git_control
    )
    git_control_kind = git_control_observation[0]

    audit = _ProtectedAudit()
    records: list[bytes] = []
    # Keep this root lexical so an untrusted `.git` symlink cannot redirect
    # ordinary collection outside the assigned worktree.
    excluded_roots: list[Path] = [git_control]
    transitioned_protected_paths: list[str] = []
    if git_control_kind == "symlink":
        if trusted_git_dir is None:
            raise _SnapshotCaptureError
        _append_protected_record(
            records,
            audit,
            ".git",
            "symlink",
            "git-pointer",
            _sha256(
                os.fsencode(
                    _stable_readlink(git_control, git_control_observations)
                )
            ),
        )
        gitdir, gitdir_observations = _trusted_git_directory_observations(
            root,
            trusted_git_dir,
            root_observations=root_observations,
            case_context=case_context,
        )
        excluded_roots.append(gitdir)
        _collect_worktree_protected_records(
            root,
            records,
            audit,
            excluded_roots,
            root_observations=root_observations,
            case_context=case_context,
        )
        _collect_tree_records(
            gitdir,
            "resolved-gitdir",
            records,
            audit,
            ".git",
            gitdir_observations,
        )
    elif git_control_kind == "directory":
        gitdir = git_control
        gitdir_observations = git_control_observations
        excluded_roots.append(gitdir)
        _collect_worktree_protected_records(
            root,
            records,
            audit,
            excluded_roots,
            root_observations=root_observations,
            case_context=case_context,
        )
        _collect_tree_records(
            gitdir,
            "git-control",
            records,
            audit,
            ".git",
            gitdir_observations,
        )
    elif git_control_kind == "file":
        pointer_bytes = _stable_regular_file_bytes(
            git_control,
            git_control_observations,
            require_single_link=False,
        )
        _append_protected_record(
            records, audit, ".git", "file", "git-pointer", _sha256(pointer_bytes)
        )
        pointer_candidate = _gitdir_pointer_candidate_inside_root(
            root,
            pointer_bytes,
            root_observations=root_observations,
            case_context=case_context,
        )
        if pointer_candidate is not None:
            excluded_roots.append(pointer_candidate)
            transitioned_protected_paths.append(
                _relative_to_root(
                    root,
                    pointer_candidate,
                    root_observations=root_observations,
                    case_context=case_context,
                )
                or ""
            )
        gitdir_candidate = (
            Path(trusted_git_dir)
            if trusted_git_dir is not None
            else _parse_gitdir_pointer(root, pointer_bytes)
        )
        gitdir, gitdir_observations = _trusted_git_directory_observations(
            root,
            gitdir_candidate,
            root_observations=root_observations,
            case_context=case_context,
        )
        excluded_roots.append(gitdir)
        _collect_worktree_protected_records(
            root,
            records,
            audit,
            excluded_roots,
            root_observations=root_observations,
            case_context=case_context,
        )
        _collect_tree_records(
            gitdir,
            "resolved-gitdir",
            records,
            audit,
            ".git",
            gitdir_observations,
        )
    else:
        raise _SnapshotCaptureError

    mac = hmac.new(control_key, digestmod=hashlib.sha256)
    mac.update(b"agenthub.task_run_scope.protected_control.v1\0")
    for record in sorted(records):
        mac.update(len(record).to_bytes(8, "big"))
        mac.update(record)
    _require_root_observations(root, root_observations)
    _require_path_observations(gitdir_observations)
    trusted_git_dir_identity = _trusted_git_directory_identity(
        gitdir,
        observations=gitdir_observations,
    )
    _require_root_observations(root, root_observations)
    _require_path_observations(gitdir_observations)
    return _ProtectedFootprint(
        digest=mac.hexdigest(),
        categories=tuple(sorted(audit.categories)),
        entry_count=audit.entry_count,
        excluded_roots=tuple(excluded_roots),
        transitioned_protected_paths=tuple(
            path for path in transitioned_protected_paths if path
        ),
        trusted_git_dir=gitdir,
        trusted_git_dir_identity=trusted_git_dir_identity,
    )


def _trusted_git_directory_observations(
    root: Path,
    trusted_git_dir: str | os.PathLike[str],
    *,
    root_observations: _PathObservations | None,
    case_context: _CaseSemanticsContext,
) -> tuple[Path, _PathObservations]:
    root_observations = _root_observations_or_capture(root, root_observations)
    gitdir = Path(trusted_git_dir)
    if not gitdir.is_absolute():
        raise _SnapshotCaptureError
    relative_parts: tuple[str, ...] | None = None
    if _filesystem_path_equal_or_descendant_at(
        str(gitdir),
        str(root),
        directory=root,
        observations=root_observations,
        case_context=case_context,
    ):
        relative_parts = tuple(gitdir.parts[len(root.parts) :])
    if relative_parts is None:
        observations = _absolute_directory_observations(
            gitdir,
            guard_observations=root_observations,
        )
    else:
        if not relative_parts:
            raise _SnapshotCaptureError
        observations = root_observations
        current = root
        for component in relative_parts:
            if component in {"", ".", ".."}:
                raise _SnapshotCaptureError
            resolved = _resolve_child_entry(
                current,
                component,
                observations,
                case_context,
                absent_allowed=False,
            )
            if resolved is None or resolved[2][0] != "directory":
                raise _SnapshotCaptureError
            _, current, _, observations = resolved
        gitdir = current
    _require_root_observations(root, root_observations)
    _require_path_observations(observations)
    return gitdir, observations


def _trusted_git_directory_identity(
    trusted_git_dir: Path,
    *,
    observations: _PathObservations | None = None,
) -> tuple[tuple[int, int, int, int], ...]:
    if observations is None:
        captured_git_dir, observations = _lexical_worktree_root(trusted_git_dir)
        if captured_git_dir != trusted_git_dir:
            raise _SnapshotCaptureError
    _require_path_observations(observations)
    parts = trusted_git_dir.parts
    if not parts:
        raise _SnapshotCaptureError
    current = Path(parts[0])
    identities: list[tuple[int, int, int, int]] = []
    for index, component in enumerate(parts):
        if index:
            if component in {"", ".", ".."}:
                raise _SnapshotCaptureError
            current /= component
        matching_observations = tuple(
            observation
            for observation in observations
            if observation[0] == current
        )
        if not matching_observations:
            raise _SnapshotCaptureError
        _, kind, identity = matching_observations[-1]
        if kind != "directory":
            raise _SnapshotCaptureError
        if index:
            identities.append(identity)
    if not identities:
        raise _SnapshotCaptureError
    _require_path_observations(observations)
    return tuple(identities)


def _trusted_git_executable(
    root: Path,
    trusted_git_dir: Path,
    *,
    root_observations: _PathObservations | None = None,
    gitdir_observations: _PathObservations | None = None,
    case_context: _CaseSemanticsContext | None = None,
) -> _TrustedGitExecutable:
    if not isinstance(_GIT_EXECUTABLE, str) or not _GIT_EXECUTABLE:
        raise _SnapshotCaptureError
    root_observations = _root_observations_or_capture(root, root_observations)
    case_context = case_context or _CaseSemanticsContext()
    if gitdir_observations is None:
        trusted_git_dir, gitdir_observations = _trusted_git_directory_observations(
            root,
            trusted_git_dir,
            root_observations=root_observations,
            case_context=case_context,
        )
    _require_path_observations(gitdir_observations)
    executable = Path(_GIT_EXECUTABLE)
    if (
        not executable.is_absolute()
        or _filesystem_path_equal_or_descendant_at(
            str(executable),
            str(root),
            directory=root,
            observations=root_observations,
            case_context=case_context,
        )
        or _filesystem_path_equal_or_descendant_at(
            str(executable),
            str(trusted_git_dir),
            directory=trusted_git_dir,
            observations=gitdir_observations,
            case_context=case_context,
        )
    ):
        raise _SnapshotCaptureError
    parts = executable.parts
    if not parts:
        raise _SnapshotCaptureError
    current = Path(parts[0])
    executable_observations = gitdir_observations
    for index, component in enumerate(parts):
        if index:
            if component in {"", ".", ".."}:
                raise _SnapshotCaptureError
            current /= component
        executable_observations, observation = _extend_path_observations(
            executable_observations,
            current,
        )
        expected_kind = "file" if index == len(parts) - 1 else "directory"
        if observation is None or observation[0] != expected_kind:
            raise _SnapshotCaptureError
    if len(parts) == 1:
        raise _SnapshotCaptureError
    _require_path_observations(executable_observations)
    content_sha256 = _stable_regular_file_fingerprint(
        executable,
        executable_observations,
        require_single_link=False,
        allow_windows_path_execute_bits=True,
    )
    _require_path_observations(executable_observations)
    return _TrustedGitExecutable(
        path=executable,
        observations=executable_observations,
        content_sha256=content_sha256,
    )


def _require_trusted_git_executable(executable: _TrustedGitExecutable) -> None:
    _require_path_observations(executable.observations)
    observed_sha256 = _stable_regular_file_fingerprint(
        executable.path,
        executable.observations,
        require_single_link=False,
        allow_windows_path_execute_bits=True,
    )
    _require_path_observations(executable.observations)
    if not hmac.compare_digest(observed_sha256, executable.content_sha256):
        raise _SnapshotCaptureError


def _capture_scope_entries(
    root: Path,
    trusted_git_dir: Path,
    excluded_roots: tuple[Path, ...],
    *,
    trusted_git_dir_identity: tuple[tuple[int, int, int, int], ...],
    runner: Callable[..., Any] | None,
    root_observations: _PathObservations,
    case_context: _CaseSemanticsContext,
) -> tuple[ScopeEntry, ...]:
    _require_root_observations(root, root_observations)
    index_output = _run_scope_git_command(
        root,
        trusted_git_dir,
        ["ls-files", "--stage", "-z", "--"],
        trusted_git_dir_identity=trusted_git_dir_identity,
        runner=runner,
        root_observations=root_observations,
        case_context=case_context,
    )
    tree_output = _run_scope_git_command(
        root,
        trusted_git_dir,
        ["ls-tree", "-r", "-z", "--full-tree", "HEAD"],
        trusted_git_dir_identity=trusted_git_dir_identity,
        runner=runner,
        root_observations=root_observations,
        case_context=case_context,
    )
    index_entries = _parse_index_entries(
        root,
        index_output,
        excluded_roots=excluded_roots,
        root_observations=root_observations,
        case_context=case_context,
    )
    tree_entries = _parse_tree_entries(
        root,
        tree_output,
        excluded_roots=excluded_roots,
        root_observations=root_observations,
        case_context=case_context,
    )

    worktree_fingerprints = {
        path: _fingerprint_worktree_path(
            root,
            path,
            absent_allowed=False,
            root_observations=root_observations,
        )
        for path in _collect_regular_files(
            root,
            excluded_roots,
            root_observations=root_observations,
            case_context=case_context,
        )
    }
    metadata_paths = set(index_entries) | set(tree_entries)
    for path in metadata_paths - set(worktree_fingerprints):
        fingerprint = _fingerprint_worktree_path(
            root,
            path,
            absent_allowed=True,
            root_observations=root_observations,
        )
        if fingerprint != _ABSENT_FINGERPRINT:
            worktree_fingerprints[path] = fingerprint

    entries = [
        ScopeEntry(
            path=path,
            status=_scope_state(
                tree_entries.get(path),
                index_entries.get(path, ()),
                path in worktree_fingerprints,
            ),
            fingerprint=_scope_entry_fingerprint(
                path,
                tree_entries.get(path),
                index_entries.get(path, ()),
                worktree_fingerprints.get(path, _ABSENT_FINGERPRINT),
            ),
        )
        for path in sorted(metadata_paths | set(worktree_fingerprints))
    ]
    _require_root_observations(root, root_observations)
    return tuple(entries)


def _run_scope_git_command(
    root: Path,
    trusted_git_dir: Path,
    arguments: list[str],
    *,
    trusted_git_dir_identity: tuple[tuple[int, int, int, int], ...],
    runner: Callable[..., Any] | None,
    root_observations: _PathObservations,
    case_context: _CaseSemanticsContext,
) -> bytes:
    _require_root_observations(root, root_observations)
    validated_git_dir, gitdir_observations = (
        _trusted_git_directory_observations(
            root,
            trusted_git_dir,
            root_observations=root_observations,
            case_context=case_context,
        )
    )
    _require_path_observations(gitdir_observations)
    identity_before = _trusted_git_directory_identity(
        validated_git_dir,
        observations=gitdir_observations,
    )
    _require_root_observations(root, root_observations)
    _require_path_observations(gitdir_observations)
    if identity_before != trusted_git_dir_identity:
        raise _SnapshotCaptureError
    git_executable = _trusted_git_executable(
        root,
        validated_git_dir,
        root_observations=root_observations,
        gitdir_observations=gitdir_observations,
        case_context=case_context,
    )
    _require_root_observations(root, root_observations)
    _require_path_observations(gitdir_observations)
    _require_trusted_git_executable(git_executable)
    git_runner = runner or subprocess.run
    try:
        completed = git_runner(
            [
                str(git_executable.path),
                "--no-optional-locks",
                "--no-replace-objects",
                "-c",
                "core.fsmonitor=false",
                "--git-dir",
                str(validated_git_dir),
                "--work-tree",
                str(root),
                *arguments,
            ],
            cwd=str(root),
            env=_scope_git_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=_GIT_COMMAND_TIMEOUT_SECONDS,
        )
    finally:
        _require_root_observations(root, root_observations)
        _require_path_observations(gitdir_observations)
        _require_trusted_git_executable(git_executable)
    validated_after, gitdir_observations_after = (
        _trusted_git_directory_observations(
            root,
            trusted_git_dir,
            root_observations=root_observations,
            case_context=case_context,
        )
    )
    identity_after = _trusted_git_directory_identity(
        validated_after,
        observations=gitdir_observations_after,
    )
    _require_root_observations(root, root_observations)
    _require_path_observations(gitdir_observations_after)
    _require_trusted_git_executable(git_executable)
    if (
        validated_after != validated_git_dir
        or identity_after != identity_before
        or identity_after != trusted_git_dir_identity
    ):
        raise _SnapshotCaptureError
    if getattr(completed, "returncode", None) != 0:
        raise _SnapshotCaptureError
    output = getattr(completed, "stdout", None)
    if not isinstance(output, bytes):
        raise _SnapshotCaptureError
    return output


def _scope_git_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    environment.pop("XDG_CONFIG_HOME", None)
    environment.update(
        {
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_PAGER": "",
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
        }
    )
    return environment


def _parse_index_entries(
    root: Path,
    output: bytes,
    *,
    excluded_roots: tuple[Path, ...],
    root_observations: _PathObservations,
    case_context: _CaseSemanticsContext,
) -> dict[str, tuple[_GitLayerEntry, ...]]:
    parsed: dict[str, dict[int, _GitLayerEntry]] = {}
    for field in _nul_fields(output):
        metadata, raw_path = _split_git_record(field)
        try:
            mode_raw, oid_raw, stage_raw = metadata.split(b" ")
            mode = mode_raw.decode("ascii")
            oid = oid_raw.decode("ascii")
            stage_text = stage_raw.decode("ascii")
        except (UnicodeDecodeError, ValueError) as exc:
            raise _SnapshotCaptureError from exc
        if (
            _GIT_MODE_RE.fullmatch(mode) is None
            or _GIT_OID_RE.fullmatch(oid) is None
            or stage_text not in {"0", "1", "2", "3"}
        ):
            raise _SnapshotCaptureError
        path = _decode_repository_path(raw_path)
        if not _is_valid_repository_path(path):
            raise _SnapshotCaptureError
        if _is_protected_or_excluded_path(
            root,
            path,
            excluded_roots,
            root_observations=root_observations,
            case_context=case_context,
        ):
            continue
        stage = int(stage_text)
        path_entries = parsed.setdefault(path, {})
        if stage in path_entries:
            raise _SnapshotCaptureError
        path_entries[stage] = _GitLayerEntry(mode=mode, oid=oid, stage=stage)

    return {
        path: tuple(entry for _, entry in sorted(entries.items()))
        for path, entries in parsed.items()
    }


def _parse_tree_entries(
    root: Path,
    output: bytes,
    *,
    excluded_roots: tuple[Path, ...],
    root_observations: _PathObservations,
    case_context: _CaseSemanticsContext,
) -> dict[str, _GitLayerEntry]:
    entries: dict[str, _GitLayerEntry] = {}
    for field in _nul_fields(output):
        metadata, raw_path = _split_git_record(field)
        try:
            mode_raw, object_type_raw, oid_raw = metadata.split(b" ")
            mode = mode_raw.decode("ascii")
            object_type = object_type_raw.decode("ascii")
            oid = oid_raw.decode("ascii")
        except (UnicodeDecodeError, ValueError) as exc:
            raise _SnapshotCaptureError from exc
        if (
            _GIT_MODE_RE.fullmatch(mode) is None
            or object_type not in {"blob", "commit"}
            or _GIT_OID_RE.fullmatch(oid) is None
        ):
            raise _SnapshotCaptureError
        path = _decode_repository_path(raw_path)
        if not _is_valid_repository_path(path):
            raise _SnapshotCaptureError
        if _is_protected_or_excluded_path(
            root,
            path,
            excluded_roots,
            root_observations=root_observations,
            case_context=case_context,
        ):
            continue
        if path in entries:
            raise _SnapshotCaptureError
        entries[path] = _GitLayerEntry(mode=mode, oid=oid)
    return entries


def _nul_fields(output: bytes) -> tuple[bytes, ...]:
    if output and not output.endswith(b"\0"):
        raise _SnapshotCaptureError
    fields = output.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    if any(not field for field in fields):
        raise _SnapshotCaptureError
    return tuple(fields)


def _split_git_record(field: bytes) -> tuple[bytes, bytes]:
    try:
        metadata, raw_path = field.split(b"\t", 1)
    except ValueError as exc:
        raise _SnapshotCaptureError from exc
    if not metadata or not raw_path:
        raise _SnapshotCaptureError
    return metadata, raw_path


def _is_protected_or_excluded_path(
    root: Path,
    path: str,
    excluded_roots: tuple[Path, ...],
    *,
    root_observations: _PathObservations,
    case_context: _CaseSemanticsContext,
) -> bool:
    excluded_relative_roots = tuple(
        relative
        for excluded_root in excluded_roots
        if (
            relative := _relative_to_root(
                root,
                excluded_root,
                root_observations=root_observations,
                case_context=case_context,
            )
        )
        is not None
    )
    return _is_protected_repository_path_at(
        path,
        root=root,
        root_observations=root_observations,
        case_context=case_context,
    ) or _is_excluded_relative_path(
        path,
        excluded_relative_roots,
        root=root,
        root_observations=root_observations,
        case_context=case_context,
    )


def _relative_directory_observations(
    root: Path,
    components: tuple[str, ...],
    root_observations: _PathObservations,
    case_context: _CaseSemanticsContext,
) -> tuple[Path, _PathObservations]:
    observations = root_observations
    current = root
    for component in components:
        if component in {"", ".", ".."}:
            raise _SnapshotCaptureError
        resolved = _resolve_child_entry(
            current,
            component,
            observations,
            case_context,
            absent_allowed=False,
        )
        if resolved is None or resolved[2][0] != "directory":
            raise _SnapshotCaptureError
        _, current, _, observations = resolved
    return current, observations


def _protected_category_at(
    path: str,
    *,
    root: Path | None = None,
    root_observations: _PathObservations | None = None,
    directory: Path | None = None,
    observations: _PathObservations | None = None,
    case_context: _CaseSemanticsContext | None = None,
) -> str | None:
    if not isinstance(path, str):
        return None
    components = tuple(path.split("/"))
    for index, component in enumerate(components):
        exact_category = _protected_category_exact(component)
        if exact_category is not None:
            return exact_category
        if _has_protected_unicode_fold_ambiguity(component):
            raise _SnapshotCaptureError
        if not _is_case_alias_candidate(component):
            continue
        if case_context is None:
            continue
        if root is not None and root_observations is not None:
            parent, parent_observations = _relative_directory_observations(
                root,
                components[:index],
                root_observations,
                case_context,
            )
        elif directory is not None and observations is not None and index == len(components) - 1:
            parent, parent_observations = directory, observations
        else:
            raise _SnapshotCaptureError
        semantics = case_context.resolve(parent, parent_observations)
        if semantics == "unknown":
            raise _SnapshotCaptureError
        if semantics == "insensitive":
            return _protected_category_exact(_ascii_casefold(component))
    return None


def _is_protected_repository_path_at(
    path: str,
    *,
    root: Path | None = None,
    root_observations: _PathObservations | None = None,
    directory: Path | None = None,
    observations: _PathObservations | None = None,
    case_context: _CaseSemanticsContext | None = None,
) -> bool:
    return (
        _protected_category_at(
            path,
            root=root,
            root_observations=root_observations,
            directory=directory,
            observations=observations,
            case_context=case_context,
        )
        is not None
    )


def _is_case_alias_candidate(component: str) -> bool:
    folded = _ascii_casefold(component)
    return (
        folded == ".git"
        or folded == "node_modules"
        or folded == "secrets"
        or folded.startswith(".env")
    ) and component not in {".git", "node_modules", "secrets"}


def _scope_state(
    tree_entry: _GitLayerEntry | None,
    index_entries: tuple[_GitLayerEntry, ...],
    worktree_present: bool,
) -> str:
    if any(entry.stage != 0 for entry in index_entries):
        if any(entry.stage == 0 for entry in index_entries):
            raise _SnapshotCaptureError
        return "unmerged-present" if worktree_present else "unmerged-missing"

    index_entry = index_entries[0] if index_entries else None
    suffix = "present" if worktree_present else "missing"
    if tree_entry is None and index_entry is None:
        if not worktree_present:
            raise _SnapshotCaptureError
        return "untracked-present"
    if tree_entry is None:
        return f"staged-added-{suffix}"
    if index_entry is None:
        return f"staged-deleted-{suffix}"
    if (tree_entry.mode, tree_entry.oid) != (index_entry.mode, index_entry.oid):
        return f"staged-modified-{suffix}"
    return f"tracked-{suffix}"


def _scope_entry_fingerprint(
    path: str,
    tree_entry: _GitLayerEntry | None,
    index_entries: tuple[_GitLayerEntry, ...],
    worktree_fingerprint: str,
) -> str:
    digest = hashlib.sha256()
    digest.update(b"agenthub.task_run_scope.entry.v2\0")
    records = [
        f"path\0{path}",
        (
            f"tree\0{tree_entry.mode}\0{tree_entry.oid}"
            if tree_entry is not None
            else "tree\0absent"
        ),
        f"worktree\0{worktree_fingerprint}",
    ]
    records.extend(
        f"index\0{entry.stage}\0{entry.mode}\0{entry.oid}"
        for entry in index_entries
    )
    if not index_entries:
        records.append("index\0absent")
    for record in records:
        encoded = record.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _collect_regular_files(
    root: Path,
    excluded_roots: tuple[Path, ...],
    *,
    root_observations: _PathObservations | None = None,
    case_context: _CaseSemanticsContext | None = None,
) -> tuple[str, ...]:
    case_context = case_context or _CaseSemanticsContext()
    root_observations = _root_observations_or_capture(root, root_observations)
    excluded_relative_roots = tuple(
        relative
        for excluded_root in excluded_roots
        if (
            relative := _relative_to_root(
                root,
                excluded_root,
                root_observations=root_observations,
                case_context=case_context,
            )
        )
        is not None
    )
    files: list[str] = []

    def visit(
        directory: Path,
        prefix: str,
        observations: _PathObservations,
    ) -> bool:
        children = _stable_scandir(directory, observations)
        _require_path_observations(observations)
        if not children:
            _require_path_observations(observations)
            return True
        for child in children:
            _require_path_observations(observations)
            if not prefix and _is_top_level_git_name(
                child.name,
                directory,
                observations,
                case_context,
            ):
                continue
            relative = f"{prefix}/{child.name}" if prefix else child.name
            path = Path(child.path)
            if _is_excluded_relative_path(
                relative,
                excluded_relative_roots,
                root=root,
                root_observations=root_observations,
                directory=directory,
                observations=observations,
                case_context=case_context,
            ):
                continue
            if _is_protected_repository_path_at(
                relative,
                root=root,
                root_observations=root_observations,
                directory=directory,
                observations=observations,
                case_context=case_context,
            ):
                continue
            if not _is_valid_repository_path(relative):
                raise _SnapshotCaptureError
            kind, child_observations = _stable_dir_entry_observations(
                child,
                observations,
            )
            if kind == "symlink":
                raise _SnapshotCaptureError
            if kind == "file":
                _require_path_observations(child_observations)
                files.append(relative)
            elif kind == "directory":
                if visit(path, relative, child_observations):
                    _require_path_observations(child_observations)
                    files.append(relative)
        _require_path_observations(observations)
        return False

    visit(root, "", root_observations)
    _require_root_observations(root, root_observations)
    return tuple(files)


def _stable_scandir(
    directory: Path,
    observations: _PathObservations,
) -> tuple[os.DirEntry[str], ...]:
    if (
        not observations
        or observations[-1][0] != directory
        or observations[-1][1] != "directory"
    ):
        raise _SnapshotCaptureError
    _require_path_observations(observations)
    _require_no_named_streams(directory)
    _require_path_observations(observations)
    try:
        iterator = os.scandir(directory)
        try:
            children = tuple(iterator)
        finally:
            close = getattr(iterator, "close", None)
            if callable(close):
                close()
    except OSError as exc:
        raise _SnapshotCaptureError from exc
    _require_path_observations(observations)
    _require_no_named_streams(directory)
    _require_path_observations(observations)
    return tuple(sorted(children, key=lambda child: child.name))


def _probe_case_semantics(
    directory: Path,
    observations: _PathObservations,
) -> CaseSemantics:
    """Infer ASCII case behavior from a stable, read-only witness.

    No probe file is created.  A directory with no case-bearing entry cannot
    establish its rule and returns ``unknown``; callers then fail closed.
    """
    _require_path_observations(observations)
    children_before = _stable_scandir(directory, observations)
    names_before = _case_probe_child_names(children_before)
    folded_names: dict[str, list[str]] = {}
    for name in names_before:
        if _single_ascii_case_alternate(name) is not None:
            folded_names.setdefault(_ascii_casefold(name), []).append(name)

    collision_groups = tuple(
        tuple(names)
        for names in folded_names.values()
        if len(names) > 1
    )
    if collision_groups:
        collision_names = tuple(
            name
            for group in collision_groups
            for name in group
        )
        stable_observations = _stable_case_name_observations(
            directory,
            collision_names,
            names_before,
            observations,
        )
        if stable_observations is None or any(
            observation is None for observation in stable_observations
        ):
            return "unknown"
        observations_by_name = dict(zip(collision_names, stable_observations))
        for group in collision_groups:
            group_observations = tuple(
                observations_by_name[name]
                for name in group
            )
            if len(set(group_observations)) != len(group_observations):
                return "unknown"
        return "sensitive"

    witness = next(
        (
            (name, alternate)
            for name in names_before
            if (alternate := _single_ascii_case_alternate(name)) is not None
        ),
        None,
    )
    if witness is None:
        return "unknown"
    pair = _stable_case_pair_observations(
        directory,
        witness[0],
        witness[1],
        names_before,
        observations,
    )
    if pair is None:
        return "unknown"
    exact_observation, alternate_observation = pair
    if exact_observation is None:
        return "unknown"
    if alternate_observation is None:
        return "sensitive"
    if alternate_observation == exact_observation:
        return "insensitive"
    return "unknown"


def _case_probe_child_names(
    children: tuple[os.DirEntry[str], ...],
) -> tuple[str, ...]:
    names = tuple(child.name for child in children)
    if any(type(name) is not str for name in names) or len(set(names)) != len(names):
        raise _SnapshotCaptureError
    return names


def _ascii_casefold(value: str) -> str:
    return "".join(
        chr(ord(character) + 32)
        if "A" <= character <= "Z"
        else character
        for character in value
    )


def _single_ascii_case_alternate(value: str) -> str | None:
    for index, character in enumerate(value):
        if "A" <= character <= "Z":
            alternate = chr(ord(character) + 32)
        elif "a" <= character <= "z":
            alternate = chr(ord(character) - 32)
        else:
            continue
        return f"{value[:index]}{alternate}{value[index + 1:]}"
    return None


def _stable_case_pair_observations(
    directory: Path,
    exact_name: str,
    alternate_name: str,
    names_before: tuple[str, ...],
    observations: _PathObservations,
) -> tuple[
    tuple[str, _PathIdentity] | None,
    tuple[str, _PathIdentity] | None,
] | None:
    stable_observations = _stable_case_name_observations(
        directory,
        (exact_name, alternate_name),
        names_before,
        observations,
    )
    if stable_observations is None:
        return None
    return stable_observations[0], stable_observations[1]


def _stable_case_name_observations(
    directory: Path,
    names: tuple[str, ...],
    names_before: tuple[str, ...],
    observations: _PathObservations,
) -> tuple[tuple[str, _PathIdentity] | None, ...] | None:
    observations_before = tuple(
        _path_observation(directory / name, absent_allowed=True)
        for name in names
    )
    _require_path_observations(observations)
    names_after = _case_probe_child_names(
        _stable_scandir(directory, observations)
    )
    _require_path_observations(observations)
    observations_after = tuple(
        _path_observation(directory / name, absent_allowed=True)
        for name in names
    )
    _require_path_observations(observations)
    if (
        names_after != names_before
        or observations_after != observations_before
    ):
        return None
    return observations_before


def _resolve_child_entry(
    directory: Path,
    expected_name: str,
    observations: _PathObservations,
    case_context: _CaseSemanticsContext,
    *,
    absent_allowed: bool = False,
    canonicalize_exact: bool = False,
) -> tuple[str, Path, tuple[str, _PathIdentity], _PathObservations] | None:
    """Resolve one child without following links, honoring actual directory case."""
    _require_path_observations(observations)
    exact_path = directory / expected_name
    exact_observations, exact = _extend_path_observations(
        observations,
        exact_path,
        absent_allowed=True,
    )
    if exact is not None:
        if canonicalize_exact:
            return _canonicalize_existing_child(
                directory,
                expected_name,
                exact_path,
                exact,
                exact_observations,
                observations,
            )
        return expected_name, exact_path, exact, exact_observations

    semantics = case_context.resolve(directory, observations)
    if semantics == "unknown":
        raise _SnapshotCaptureError
    if semantics == "sensitive":
        if absent_allowed:
            return None
        raise _SnapshotCaptureError

    matches = tuple(
        child
        for child in _stable_scandir(directory, observations)
        if isinstance(child.name, str)
        and _ascii_casefold(child.name) == _ascii_casefold(expected_name)
    )
    if len(matches) > 1:
        raise _SnapshotCaptureError
    if not matches:
        if absent_allowed:
            return None
        raise _SnapshotCaptureError
    child = matches[0]
    kind, child_observations = _stable_dir_entry_observations(
        child,
        observations,
    )
    child_observation = child_observations[-1][1:]
    return child.name, Path(child.path), (kind, child_observation), child_observations


def _canonicalize_existing_child(
    directory: Path,
    expected_name: str,
    exact_path: Path,
    exact: tuple[str, _PathIdentity],
    exact_observations: _PathObservations,
    parent_observations: _PathObservations,
) -> tuple[str, Path, tuple[str, _PathIdentity], _PathObservations]:
    matches: list[
        tuple[str, Path, tuple[str, _PathIdentity], _PathObservations]
    ] = []
    for child in _stable_scandir(directory, parent_observations):
        kind, child_observations = _stable_dir_entry_observations(
            child,
            parent_observations,
        )
        child_observation = child_observations[-1][1:]
        if (kind, child_observation[1]) == (exact[0], exact[1]):
            matches.append(
                (
                    child.name,
                    Path(child.path),
                    (kind, child_observation),
                    child_observations,
                )
            )
    if len(matches) != 1:
        raise _SnapshotCaptureError
    _require_path_observations(exact_observations)
    return matches[0]


def _collect_worktree_protected_records(
    root: Path,
    records: list[bytes],
    audit: _ProtectedAudit,
    excluded_roots: list[Path],
    *,
    root_observations: _PathObservations,
    case_context: _CaseSemanticsContext,
) -> None:
    _require_root_observations(root, root_observations)
    excluded_relative_roots = tuple(
        relative
        for excluded_root in excluded_roots
        if (
            relative := _relative_to_root(
                root,
                excluded_root,
                root_observations=root_observations,
                case_context=case_context,
            )
        )
        is not None
    )

    def visit(
        directory: Path,
        prefix: str,
        observations: _PathObservations,
    ) -> None:
        children = _stable_scandir(directory, observations)
        for child in children:
            _require_path_observations(observations)
            if not prefix and _is_top_level_git_name(
                child.name,
                directory,
                observations,
                case_context,
            ):
                continue
            relative = f"{prefix}/{child.name}" if prefix else child.name
            path = Path(child.path)
            if _is_excluded_relative_path(
                relative,
                excluded_relative_roots,
                root=root,
                root_observations=root_observations,
                directory=directory,
                observations=observations,
                case_context=case_context,
            ):
                continue
            kind, child_observations = _stable_dir_entry_observations(
                child,
                observations,
            )
            category = _protected_category_at(
                relative,
                root=root,
                root_observations=root_observations,
                directory=directory,
                observations=observations,
                case_context=case_context,
            )
            if category is not None:
                _collect_tree_records(
                    path,
                    f"protected/{relative}",
                    records,
                    audit,
                    category,
                    child_observations,
                )
            elif kind == "directory":
                visit(path, relative, child_observations)
        _require_path_observations(observations)

    visit(root, "", root_observations)
    _require_root_observations(root, root_observations)


def _collect_tree_records(
    path: Path,
    label: str,
    records: list[bytes],
    audit: _ProtectedAudit,
    category: str,
    observations: _PathObservations,
) -> None:
    if not observations or observations[-1][0] != path:
        raise _SnapshotCaptureError
    _require_path_observations(observations)
    kind = observations[-1][1]
    if kind == "symlink":
        _append_protected_record(
            records,
            audit,
            category,
            "symlink",
            label,
            _sha256(os.fsencode(_stable_readlink(path, observations))),
        )
        return
    if kind == "file":
        _append_protected_record(
            records,
            audit,
            category,
            "file",
            label,
            _stable_regular_file_fingerprint(
                path,
                observations,
                require_single_link=False,
            ),
        )
        return
    if kind != "directory":
        raise _SnapshotCaptureError
    _require_path_observations(observations)
    _append_protected_record(records, audit, category, "directory", label, "")
    for child in _stable_scandir(path, observations):
        _, child_observations = _stable_dir_entry_observations(
            child,
            observations,
        )
        _collect_tree_records(
            Path(child.path),
            f"{label}/{child.name}",
            records,
            audit,
            category,
            child_observations,
        )
    _require_path_observations(observations)


def _append_protected_record(
    records: list[bytes],
    audit: _ProtectedAudit,
    category: str,
    kind: str,
    label: str,
    content_identity: str,
) -> None:
    records.append(_record(kind, label, content_identity))
    audit.record(category)


def _parse_gitdir_pointer(root: Path, pointer_bytes: bytes) -> Path:
    raw_gitdir = _gitdir_pointer_value(pointer_bytes)
    gitdir = Path(raw_gitdir)
    if not gitdir.is_absolute():
        gitdir = root / gitdir
    gitdir = Path(os.path.abspath(gitdir))
    if not gitdir.is_absolute() or gitdir == root:
        raise _SnapshotCaptureError
    return gitdir


def _gitdir_pointer_candidate_inside_root(
    root: Path,
    pointer_bytes: bytes,
    *,
    root_observations: _PathObservations | None = None,
    case_context: _CaseSemanticsContext | None = None,
) -> Path | None:
    raw_gitdir = _gitdir_pointer_value(pointer_bytes)
    candidate = Path(raw_gitdir)
    if not candidate.is_absolute():
        candidate = root / candidate
    if (root_observations is None) != (case_context is None):
        raise _SnapshotCaptureError
    if root_observations is not None and case_context is not None:
        inside_root = _filesystem_path_equal_or_descendant_at(
            str(candidate),
            str(root),
            directory=root,
            observations=root_observations,
            case_context=case_context,
        )
    else:
        inside_root = _filesystem_path_equal_or_descendant(
            str(candidate),
            str(root),
        )
    if not inside_root:
        return None
    relative_parts = candidate.parts[len(root.parts) :]
    if any(component in {"", ".", ".."} for component in relative_parts):
        return None
    if root_observations is not None and case_context is not None:
        observations = root_observations
        current = root
        for component in relative_parts:
            resolved = _resolve_child_entry(
                current,
                component,
                observations,
                case_context,
                absent_allowed=True,
                canonicalize_exact=True,
            )
            if resolved is None:
                break
            _, current, _, observations = resolved
        else:
            candidate = current
    return candidate


def _gitdir_pointer_value(pointer_bytes: bytes) -> str:
    try:
        text = pointer_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _SnapshotCaptureError from exc
    lines = text.splitlines()
    if len(lines) != 1 or not lines[0].startswith("gitdir: "):
        raise _SnapshotCaptureError
    raw_gitdir = lines[0][len("gitdir: ") :]
    if not raw_gitdir or "\0" in raw_gitdir:
        raise _SnapshotCaptureError
    return raw_gitdir


def _relative_to_root(
    root: Path,
    path: Path,
    *,
    root_observations: _PathObservations,
    case_context: _CaseSemanticsContext,
) -> str | None:
    """Return a relative path only after root-bound containment is proven."""
    _require_root_observations(root, root_observations)
    if not _filesystem_path_equal_or_descendant_at(
        str(path),
        str(root),
        directory=root,
        observations=root_observations,
        case_context=case_context,
    ):
        return None
    path_parts = path.parts
    root_parts = root.parts
    if len(path_parts) < len(root_parts):
        raise _SnapshotCaptureError
    relative_parts = tuple(path_parts[len(root_parts) :])
    if any(component in {"", ".", ".."} for component in relative_parts):
        raise _SnapshotCaptureError
    _require_root_observations(root, root_observations)
    return "/".join(relative_parts)


def _is_excluded_relative_path(
    path: str,
    excluded_roots: tuple[str, ...],
    *,
    root: Path | None = None,
    root_observations: _PathObservations | None = None,
    directory: Path | None = None,
    observations: _PathObservations | None = None,
    case_context: _CaseSemanticsContext | None = None,
) -> bool:
    path_parts = tuple(path.split("/"))
    for excluded_root in excluded_roots:
        root_parts = tuple(excluded_root.split("/"))
        if len(path_parts) < len(root_parts):
            continue
        matched = True
        for index, (left, right) in enumerate(zip(path_parts, root_parts)):
            if left == right:
                continue
            if _ascii_casefold(left) != _ascii_casefold(right) or case_context is None:
                matched = False
                break
            if root is not None and root_observations is not None:
                parent, parent_observations = _relative_directory_observations(
                    root,
                    path_parts[:index],
                    root_observations,
                    case_context,
                )
            elif directory is not None and observations is not None and index == len(path_parts) - 1:
                parent, parent_observations = directory, observations
            else:
                raise _SnapshotCaptureError
            semantics = case_context.resolve(parent, parent_observations)
            if semantics == "unknown":
                raise _SnapshotCaptureError
            if semantics != "insensitive":
                matched = False
                break
        if matched:
            return True
    return False


def _decode_repository_path(raw_path: bytes) -> str:
    path = raw_path.decode("utf-8")
    if not path:
        raise _SnapshotCaptureError
    return path


def _root_observations_or_capture(
    root: Path,
    root_observations: _PathObservations | None,
) -> _PathObservations:
    if root_observations is None:
        captured_root, root_observations = _lexical_worktree_root(root)
        if captured_root != root:
            raise _SnapshotCaptureError
    _require_root_observations(root, root_observations)
    return root_observations


def _require_root_observations(
    root: Path,
    observations: _PathObservations,
) -> None:
    if not observations or observations[-1][0] != root:
        raise _SnapshotCaptureError
    _require_path_observations(observations)


def _extend_path_observations(
    observations: _PathObservations,
    path: Path,
    *,
    absent_allowed: bool = False,
) -> tuple[_PathObservations, tuple[str, _PathIdentity] | None]:
    _require_path_observations(observations)
    observation = _path_observation(path, absent_allowed=absent_allowed)
    _require_path_observations(observations)
    if observation is None:
        return observations, None
    extended = observations + ((path, observation[0], observation[1]),)
    _require_path_observations(extended)
    return extended, observation


def _absolute_directory_observations(
    directory: Path,
    *,
    guard_observations: _PathObservations,
) -> _PathObservations:
    if not directory.is_absolute() or not directory.parts:
        raise _SnapshotCaptureError
    observations = guard_observations
    current = Path(directory.parts[0])
    for index, component in enumerate(directory.parts):
        if index:
            if component in {"", ".", ".."}:
                raise _SnapshotCaptureError
            current /= component
        observations, observation = _extend_path_observations(
            observations,
            current,
        )
        if observation is None or observation[0] != "directory":
            raise _SnapshotCaptureError
    if current != directory:
        raise _SnapshotCaptureError
    _require_path_observations(observations)
    return observations


def _stable_dir_entry_observations(
    entry: os.DirEntry[str],
    parent_observations: _PathObservations,
) -> tuple[str, _PathObservations]:
    _require_path_observations(parent_observations)
    kind = _dir_entry_kind(entry)
    _require_path_observations(parent_observations)
    observations, observation = _extend_path_observations(
        parent_observations,
        Path(entry.path),
    )
    if observation is None or observation[0] != kind:
        raise _SnapshotCaptureError
    return kind, observations


def _fingerprint_worktree_path(
    root: Path,
    path: str,
    *,
    absent_allowed: bool,
    root_observations: _PathObservations | None = None,
) -> str:
    root_observations = _root_observations_or_capture(root, root_observations)
    components = path.split("/")
    if not components or any(
        component in {"", ".", ".."} for component in components
    ):
        raise _SnapshotCaptureError
    candidate = root
    observations = root_observations
    for index, component in enumerate(components):
        candidate /= component
        observations_after, observation = _extend_path_observations(
            observations,
            candidate,
            absent_allowed=absent_allowed,
        )
        if observation is None:
            _require_path_observations(observations)
            return _ABSENT_FINGERPRINT
        kind, identity = observation
        if kind == "symlink":
            raise _SnapshotCaptureError
        if index < len(components) - 1 and kind != "directory":
            raise _SnapshotCaptureError
        observations = observations_after
    if kind == "file":
        return _stable_regular_file_fingerprint(
            candidate,
            observations,
            require_single_link=True,
        )
    if kind == "directory":
        _require_path_observations(observations)
        return _DIRECTORY_FINGERPRINT
    raise _SnapshotCaptureError


def _stable_regular_file_fingerprint(
    path: Path,
    observations: _PathObservations,
    *,
    require_single_link: bool,
    allow_windows_path_execute_bits: bool = False,
) -> str:
    digest = hashlib.sha256()
    _stable_regular_file_read(
        path,
        observations,
        digest.update,
        require_single_link=require_single_link,
        allow_windows_path_execute_bits=allow_windows_path_execute_bits,
    )
    return digest.hexdigest()


def _stable_regular_file_bytes(
    path: Path,
    observations: _PathObservations,
    *,
    require_single_link: bool,
) -> bytes:
    chunks: list[bytes] = []
    _stable_regular_file_read(
        path,
        observations,
        chunks.append,
        require_single_link=require_single_link,
    )
    return b"".join(chunks)


def _stable_regular_file_read(
    path: Path,
    observations: _PathObservations,
    consume: Callable[[bytes], Any],
    *,
    require_single_link: bool,
    allow_windows_path_execute_bits: bool = False,
) -> None:
    if (
        not observations
        or observations[-1][0] != path
        or observations[-1][1] != "file"
    ):
        raise _SnapshotCaptureError
    _require_path_observations(observations)
    _require_no_named_streams(path)
    _require_path_observations(observations)
    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise _SnapshotCaptureError from exc
    try:
        opened_before = _descriptor_observation(
            descriptor,
            require_single_link=require_single_link,
        )
        if not _descriptor_matches_path_observation(
            opened_before,
            ("file", observations[-1][2]),
            path=path,
            allow_windows_path_execute_bits=allow_windows_path_execute_bits,
        ):
            raise _SnapshotCaptureError
        _require_path_observations(observations)
        _require_no_named_streams(path)
        _require_path_observations(observations)
        while True:
            _require_path_observations(observations)
            if (
                _descriptor_observation(
                    descriptor,
                    require_single_link=require_single_link,
                )
                != opened_before
            ):
                raise _SnapshotCaptureError
            _require_no_named_streams(path)
            _require_path_observations(observations)
            chunk = os.read(descriptor, _FILE_READ_CHUNK_SIZE)
            opened_after_read = _descriptor_observation(
                descriptor,
                require_single_link=require_single_link,
            )
            _require_path_observations(observations)
            if opened_after_read != opened_before:
                raise _SnapshotCaptureError
            _require_no_named_streams(path)
            _require_path_observations(observations)
            if not chunk:
                break
            consume(chunk)
        opened_after = _descriptor_observation(
            descriptor,
            require_single_link=require_single_link,
        )
        _require_path_observations(observations)
        _require_no_named_streams(path)
        _require_path_observations(observations)
        if opened_after != opened_before:
            raise _SnapshotCaptureError
    except OSError as exc:
        raise _SnapshotCaptureError from exc
    finally:
        try:
            os.close(descriptor)
        except OSError as exc:
            raise _SnapshotCaptureError from exc


def _descriptor_matches_path_observation(
    descriptor_observation: tuple[str, _PathIdentity],
    path_observation: tuple[str, _PathIdentity],
    *,
    path: Path,
    allow_windows_path_execute_bits: bool,
) -> bool:
    if descriptor_observation == path_observation:
        return True
    if (
        not allow_windows_path_execute_bits
        or os.name != "nt"
        or _ascii_casefold(path.suffix) != ".exe"
        or descriptor_observation[0] != "file"
        or path_observation[0] != "file"
    ):
        return False
    descriptor_identity = descriptor_observation[1]
    path_identity = path_observation[1]
    return (
        descriptor_identity[:2] == path_identity[:2]
        and descriptor_identity[3] == path_identity[3]
        and stat.S_IFMT(descriptor_identity[2]) == stat.S_IFMT(path_identity[2])
        and path_identity[2] == (descriptor_identity[2] | 0o111)
    )


def _require_path_observations(
    observations: _PathObservations,
) -> None:
    if not observations:
        raise _SnapshotCaptureError
    for path, kind, identity in observations:
        if _path_observation(path) != (kind, identity):
            raise _SnapshotCaptureError


def _descriptor_observation(
    descriptor: int,
    *,
    require_single_link: bool,
) -> tuple[str, tuple[int, int, int, int]]:
    try:
        path_stat = os.fstat(descriptor)
    except OSError as exc:
        raise _SnapshotCaptureError from exc
    if require_single_link and path_stat.st_nlink != 1:
        raise _SnapshotCaptureError
    return _path_kind_from_stat(path_stat), _filesystem_identity(path_stat)


def _stable_readlink(path: Path, observations: _PathObservations) -> str:
    if (
        not observations
        or observations[-1][0] != path
        or observations[-1][1] != "symlink"
    ):
        raise _SnapshotCaptureError
    _require_path_observations(observations)
    try:
        target = os.readlink(path)
    except OSError as exc:
        raise _SnapshotCaptureError from exc
    _require_path_observations(observations)
    return target


def _record(kind: str, label: str, content_identity: str) -> bytes:
    return f"{kind}\0{label}\0{content_identity}".encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_reparse_point(path_stat: os.stat_result) -> bool:
    reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(getattr(path_stat, "st_file_attributes", 0) & reparse_point)


def _filesystem_identity(path_stat: os.stat_result) -> tuple[int, int, int, int]:
    return (
        int(path_stat.st_dev),
        int(path_stat.st_ino),
        int(path_stat.st_mode),
        int(getattr(path_stat, "st_file_attributes", 0)),
    )


def _path_filesystem_identity(
    path_stat: os.stat_result,
    *,
    kind: str,
) -> tuple[int, int, int, int]:
    identity = _filesystem_identity(path_stat)
    if os.name != "nt" or kind != "directory":
        return identity
    return (
        identity[0],
        identity[1],
        identity[2],
        identity[3] & ~_WINDOWS_TRANSIENT_DIRECTORY_STAT_ATTRIBUTE,
    )


def _path_observation(
    path: Path, *, absent_allowed: bool = False
) -> tuple[str, tuple[int, int, int, int]] | None:
    try:
        path_stat = path.lstat()
    except FileNotFoundError as exc:
        if absent_allowed:
            return None
        raise _SnapshotCaptureError from exc
    except OSError as exc:
        raise _SnapshotCaptureError from exc
    kind = _path_kind_from_stat(path_stat)
    return kind, _path_filesystem_identity(path_stat, kind=kind)


def _path_kind(path: Path, *, absent_allowed: bool = False) -> str | None:
    observation = _path_observation(path, absent_allowed=absent_allowed)
    return observation[0] if observation is not None else None


def _dir_entry_kind(entry: os.DirEntry[str]) -> str:
    try:
        path_stat = entry.stat(follow_symlinks=False)
    except OSError as exc:
        raise _SnapshotCaptureError from exc
    return _path_kind_from_stat(path_stat)


def _path_kind_from_stat(path_stat: os.stat_result) -> str:
    if stat.S_ISLNK(path_stat.st_mode):
        return "symlink"
    if _is_reparse_point(path_stat):
        raise _SnapshotCaptureError
    if stat.S_ISREG(path_stat.st_mode):
        return "file"
    if stat.S_ISDIR(path_stat.st_mode):
        return "directory"
    raise _SnapshotCaptureError


def _is_top_level_git_name(
    name: str,
    directory: Path,
    observations: _PathObservations,
    case_context: _CaseSemanticsContext,
) -> bool:
    if name == ".git":
        return True
    if _has_protected_unicode_fold_ambiguity(name):
        raise _SnapshotCaptureError
    if _ascii_casefold(name) != ".git":
        return False
    semantics = case_context.resolve(directory, observations)
    if semantics == "unknown":
        raise _SnapshotCaptureError
    return semantics == "insensitive"


def _filesystem_component_equal(
    left: str,
    right: str,
    *,
    case_semantics: CaseSemantics = "sensitive",
) -> bool:
    return left == right or (
        case_semantics == "insensitive"
        and _ascii_casefold(left) == _ascii_casefold(right)
    )


def _filesystem_path_equal_or_descendant(
    path: str,
    root: str,
    *,
    case_semantics: CaseSemantics = "sensitive",
) -> bool:
    path_parts = path.replace("\\", "/").split("/")
    root_parts = root.replace("\\", "/").split("/")
    if len(path_parts) < len(root_parts):
        return False
    return all(
        _filesystem_component_equal(left, right, case_semantics=case_semantics)
        for left, right in zip(path_parts, root_parts)
    )


def _filesystem_path_equal_or_descendant_at(
    path: str,
    root: str,
    *,
    directory: Path,
    observations: _PathObservations,
    case_context: _CaseSemanticsContext,
) -> bool:
    """Compare an absolute prefix using each mismatched component's parent rule."""
    _require_path_observations(observations)
    if _filesystem_path_equal_or_descendant(path, root):
        return True
    path_parts = Path(path).parts
    root_parts = Path(root).parts
    if len(path_parts) < len(root_parts):
        return False
    if not root_parts or directory.parts != Path(root).parts:
        raise _SnapshotCaptureError

    current = Path(root_parts[0])
    for index, (left, right) in enumerate(
        zip(path_parts[: len(root_parts)], root_parts)
    ):
        if left == right:
            if index:
                current /= right
            continue
        if _ascii_casefold(left) != _ascii_casefold(right):
            return False
        if index == 0:
            current = Path(right)
            continue
        parent_observations = _observations_ending_at(
            observations,
            current,
        )
        semantics = case_context.resolve(current, parent_observations)
        if semantics == "unknown":
            raise _SnapshotCaptureError
        if semantics != "insensitive":
            return False
        current /= right
    _require_path_observations(observations)
    return True


def _observations_ending_at(
    observations: _PathObservations,
    path: Path,
) -> _PathObservations:
    matching_indices = tuple(
        index
        for index, observation in enumerate(observations)
        if str(observation[0]) == str(path)
    )
    if not matching_indices:
        raise _SnapshotCaptureError
    selected = observations[: matching_indices[-1] + 1]
    _require_path_observations(selected)
    if selected[-1][0] != path:
        raise _SnapshotCaptureError
    return selected


def _is_complete_snapshot(snapshot: object) -> bool:
    if not isinstance(snapshot, ScopeSnapshot) or not snapshot.available:
        return False
    restored = scope_snapshot_from_metadata(snapshot.to_metadata(include_internal=True))
    return restored == snapshot and restored.protected_control_digest is not None


def _changed_paths(
    baseline_entries: tuple[ScopeEntry, ...], current_entries: tuple[ScopeEntry, ...]
) -> tuple[str, ...]:
    baseline_by_path = {entry.path: entry for entry in baseline_entries}
    current_by_path = {entry.path: entry for entry in current_entries}
    return tuple(
        sorted(
            path
            for path in baseline_by_path.keys() | current_by_path.keys()
            if baseline_by_path.get(path) != current_by_path.get(path)
        )
    )


def _exclude_newly_protected_deletions(
    changed_paths: tuple[str, ...],
    baseline_entries: tuple[ScopeEntry, ...],
    current_entries: tuple[ScopeEntry, ...],
    transitioned_protected_paths: tuple[str, ...],
) -> tuple[str, ...]:
    baseline_paths = {entry.path for entry in baseline_entries}
    current_paths = {entry.path for entry in current_entries}
    # The pointer transition already changes the protected control digest and
    # therefore cannot authorize a pass.  Match its private deletion redaction
    # conservatively so rootless/cross-process case ambiguity cannot disclose a
    # former gitdir spelling as an ordinary rejected path.
    return tuple(
        path
        for path in changed_paths
        if not (
            path in baseline_paths
            and path not in current_paths
            and any(
                _filesystem_path_equal_or_descendant(
                    path,
                    protected_path,
                    case_semantics="insensitive",
                )
                for protected_path in transitioned_protected_paths
            )
        )
    )


def _entry_sort_key(entry: ScopeEntry) -> tuple[str, str, str]:
    return (entry.path, entry.status, entry.fingerprint)


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


def _is_valid_status(status: object) -> bool:
    return isinstance(status, str) and status in _SCOPE_STATES


def _is_valid_audit_metadata(categories: object, entry_count: object) -> bool:
    return (
        isinstance(categories, list)
        and all(isinstance(category, str) for category in categories)
        and tuple(categories) == tuple(sorted(set(categories)))
        and set(categories).issubset(_PROTECTED_CATEGORIES)
        and type(entry_count) is int
        and entry_count >= 0
    )


def _is_valid_repository_path(path: object) -> bool:
    return is_canonical_repository_path(path)


def _protected_category_exact(component: str) -> str | None:
    if component == ".git":
        return ".git"
    if component == "node_modules":
        return "node_modules"
    if component == "secrets":
        return "secrets"
    if component.startswith(".env"):
        return ".env"
    return None


def _has_protected_unicode_fold_ambiguity(component: str) -> bool:
    """Flag Unicode-to-ASCII protected aliases without authorizing equality."""
    ascii_folded = _ascii_casefold(component)
    unicode_folded = component.casefold()
    return (
        unicode_folded != ascii_folded
        and _protected_category_exact(unicode_folded) is not None
    )


def _is_protected_repository_path(path: str) -> bool:
    """Conservatively reject aliases in persisted, rootless snapshot data."""
    return any(
        _protected_category_exact(_ascii_casefold(component)) is not None
        or _has_protected_unicode_fold_ambiguity(component)
        for component in path.split("/")
    )
