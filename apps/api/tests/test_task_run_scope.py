import hashlib
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from app.target_registry import get_target
from types import SimpleNamespace

import app.task_run_scope as task_run_scope
import pytest
from app.task_run_scope import (
    SCOPE_SNAPSHOT_SCHEMA_VERSION,
    ScopeEntry,
    ScopeSnapshot,
    capture_worktree_scope_snapshot,
    scope_snapshot_from_metadata,
    validate_scope_delta,
)


def _snapshot(*entries: ScopeEntry) -> ScopeSnapshot:
    return ScopeSnapshot(
        schema_version=SCOPE_SNAPSHOT_SCHEMA_VERSION,
        available=True,
        reason=None,
        entries=entries,
        protected_control_digest="a" * 64,
    )


_VALID_RUNTIME_BINDING = {
    "workspace_id": "workspace-runtime-context",
    "target_id": "target-runtime-context",
    "policy_identity": "b" * 64,
    "baseline_identity": "baseline-runtime-context",
    "baseline_captured_at": "2026-07-18T00:00:00+00:00",
    "execution_attempt_id": "attempt-runtime-context",
}


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    (
        pytest.param("workspace_id", "", id="workspace-empty"),
        pytest.param("workspace_id", None, id="workspace-none"),
        pytest.param("target_id", " ", id="target-whitespace"),
        pytest.param("policy_identity", "", id="policy-empty"),
        pytest.param("policy_identity", "not-a-sha256", id="policy-nonhex"),
        pytest.param("baseline_identity", "", id="baseline-empty"),
        pytest.param("baseline_captured_at", "", id="capture-time-empty"),
        pytest.param("execution_attempt_id", "", id="attempt-empty"),
    ),
)
def test_store_runtime_scope_context_rejects_invalid_authorization_binding(
    field_name: str,
    invalid_value: object,
) -> None:
    task_run_id = f"run-invalid-{field_name}"
    binding = dict(_VALID_RUNTIME_BINDING)
    binding[field_name] = invalid_value
    task_run_scope.clear_task_run_scope_runtime_context(task_run_id)

    try:
        with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
            task_run_scope.store_task_run_scope_runtime_context(
                task_run_id,
                trusted_git_dir="trusted-gitdir",
                **binding,
            )
        assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    finally:
        task_run_scope.clear_task_run_scope_runtime_context(task_run_id)


def test_runtime_scope_context_keeps_trusted_gitdir_out_of_metadata(
    tmp_path,
) -> None:
    task_run_id = "run-runtime-context"
    git_pointer = tmp_path / ".git"
    git_pointer.write_text("gitdir: trusted-gitdir-a\n")
    task_run_scope.clear_task_run_scope_runtime_context(task_run_id)

    assert task_run_scope.get_task_run_scope_runtime_context(task_run_id) is None
    task_run_scope.store_task_run_scope_runtime_context(
        task_run_id,
        trusted_git_dir="trusted-gitdir-a",
        **_VALID_RUNTIME_BINDING,
    )
    git_pointer.write_text("gitdir: untrusted-gitdir-b\n")

    context = task_run_scope.get_task_run_scope_runtime_context(task_run_id)
    assert context is not None
    assert context.trusted_git_dir == "trusted-gitdir-a"
    assert "trusted-gitdir-a" not in str(_snapshot().to_metadata(include_internal=True))

    task_run_scope.clear_task_run_scope_runtime_context(task_run_id)
    assert task_run_scope.get_task_run_scope_runtime_context(task_run_id) is None
    with pytest.raises(task_run_scope.TaskRunScopeError) as exc_info:
        task_run_scope.require_task_run_scope_runtime_context(task_run_id)
    assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


def test_snapshot_keeps_trusted_gitdir_only_in_internal_runtime_field(
    tmp_path, monkeypatch
) -> None:
    _write_git_control_state(tmp_path, gitdir_name="trusted-gitdir-a")
    _stub_git_status(monkeypatch, b"")

    snapshot = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")

    assert snapshot._trusted_git_dir == str((tmp_path / "trusted-gitdir-a").resolve())
    assert "trusted-gitdir-a" not in str(snapshot.to_metadata(include_internal=True))


def test_frontend_scope_delta_allows_demo_source_file() -> None:
    baseline = _snapshot()
    current = _snapshot(
        ScopeEntry(
            path="apps/demo/src/App.tsx",
            status="tracked-present",
            fingerprint="1" * 64,
        )
    )

    decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)

    assert decision.status == "passed"
    assert decision.changed_paths == ("apps/demo/src/App.tsx",)


def test_frontend_scope_delta_rejects_package_json() -> None:
    baseline = _snapshot()
    current = _snapshot(
        ScopeEntry(path="package.json", status="tracked-present", fingerprint="2" * 64)
    )

    decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)

    assert decision.status == "rejected"
    assert decision.error_code == "TASK_RUN_SCOPE_VIOLATION"
    assert decision.rejected_paths == ("package.json",)


def test_frontend_scope_ignores_unchanged_backend_baseline_entry() -> None:
    backend_entry = ScopeEntry(
        path="apps/demo-api/app/main.py", status="tracked-present", fingerprint="3" * 64
    )
    baseline = _snapshot(backend_entry)
    current = _snapshot(
        backend_entry,
        ScopeEntry(
            path="apps/demo/src/Login.tsx", status="untracked-present", fingerprint="4" * 64
        ),
    )

    decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)

    assert decision.status == "passed"
    assert decision.changed_paths == ("apps/demo/src/Login.tsx",)


def test_scope_delta_detects_changed_fingerprint_with_same_status() -> None:
    baseline = _snapshot(
        ScopeEntry(path="apps/demo/src/App.tsx", status="tracked-present", fingerprint="5" * 64)
    )
    current = _snapshot(
        ScopeEntry(path="apps/demo/src/App.tsx", status="tracked-present", fingerprint="6" * 64)
    )

    decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)

    assert decision.status == "passed"
    assert decision.changed_paths == ("apps/demo/src/App.tsx",)


def test_unavailable_or_invalid_metadata_is_unverifiable() -> None:
    current = _snapshot()
    unavailable = ScopeSnapshot(
        schema_version=SCOPE_SNAPSHOT_SCHEMA_VERSION,
        available=False,
        reason="git_status_failed",
        entries=(),
        protected_control_digest=None,
    )
    malformed = scope_snapshot_from_metadata(
        {
            "schema_version": SCOPE_SNAPSHOT_SCHEMA_VERSION,
            "available": True,
            "reason": None,
            "entries": [
                {
                    "path": "../outside.txt",
                    "status": "tracked-present",
                    "fingerprint": "7" * 64,
                }
            ],
            "protected_control_digest": "a" * 64,
        }
    )

    assert malformed.available is False
    for baseline in (unavailable, malformed):
        decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)
        assert decision.status == "unverifiable"
        assert decision.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


def test_rename_source_and_destination_are_both_scope_checked(tmp_path, monkeypatch) -> None:
    _write_git_control_state(tmp_path)
    destination = tmp_path / "apps/demo/src/New.tsx"
    destination.parent.mkdir(parents=True)
    destination.write_text("export const New = true;", encoding="utf-8")
    _stub_git_layers(
        monkeypatch,
        index_output=_git_index_record("apps/demo/src/New.tsx"),
        tree_output=_git_tree_record("package.json"),
    )

    current = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")
    decision = validate_scope_delta(get_target("demo-frontend"), _snapshot(), current)

    assert current.available is True
    assert {entry.path for entry in current.entries} == {
        "apps/demo/src/New.tsx",
        "package.json",
    }
    assert decision.status == "rejected"
    assert decision.rejected_paths == ("package.json",)


def test_protected_control_change_rejects_without_leaking_gitdir_path(
    tmp_path, monkeypatch
) -> None:
    _write_git_control_state(tmp_path, gitdir_name="private-git-control")
    protected_file = tmp_path / "apps/demo/.env.local"
    protected_file.parent.mkdir(parents=True)
    protected_file.write_text("TOKEN=first", encoding="utf-8")
    _stub_git_status(monkeypatch, b"")
    baseline = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")

    protected_file.write_text("TOKEN=second", encoding="utf-8")
    current = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")
    decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)

    assert baseline.available is True
    assert current.available is True
    assert baseline.protected_control_digest != current.protected_control_digest
    assert decision.status == "rejected"
    assert decision.rejected_paths == ("<protected-footprint>",)
    assert "private-git-control" not in str(current.to_metadata())
    assert "private-git-control" not in (decision.reason or "")


def test_envrc_content_change_is_a_redacted_protected_violation(
    tmp_path, monkeypatch
) -> None:
    _write_git_control_state(tmp_path)
    envrc = tmp_path / ".envrc"
    envrc.write_text("TOKEN=first\n", encoding="utf-8")
    _stub_git_status(monkeypatch, b"")

    baseline = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")
    envrc.write_text("TOKEN=second\n", encoding="utf-8")
    current = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")
    decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)

    assert ".envrc" not in {entry.path for entry in baseline.entries}
    assert ".envrc" not in {entry.path for entry in current.entries}
    assert baseline.protected_categories == current.protected_categories == (".env", ".git")
    assert baseline.protected_entry_count == current.protected_entry_count
    assert decision.status == "rejected"
    assert decision.rejected_paths == ("<protected-footprint>",)


@pytest.mark.parametrize(
    "path",
    (
        pytest.param("apps/demo/src/\x01App.tsx", id="control-character"),
        pytest.param(" apps/demo/src/App.tsx", id="leading-whitespace"),
        pytest.param("apps/demo/src/App.tsx ", id="trailing-whitespace"),
        pytest.param("apps/demo/src/App*.tsx", id="asterisk"),
        pytest.param("apps/demo/src/App?.tsx", id="question-mark"),
    ),
)
def test_snapshot_metadata_rejects_noncanonical_repository_paths(path: str) -> None:
    snapshot = scope_snapshot_from_metadata(
        {
            "schema_version": SCOPE_SNAPSHOT_SCHEMA_VERSION,
            "available": True,
            "reason": None,
            "entries": [
                {
                    "path": path,
                    "status": "tracked-present",
                    "fingerprint": "a" * 64,
                }
            ],
            "protected_control_digest": "b" * 64,
            "protected_categories": [],
            "protected_entry_count": 0,
        }
    )

    assert snapshot.available is False


def test_snapshot_metadata_accepts_canonical_unicode_repository_path() -> None:
    snapshot = scope_snapshot_from_metadata(
        {
            "schema_version": SCOPE_SNAPSHOT_SCHEMA_VERSION,
            "available": True,
            "reason": None,
            "entries": [
                {
                    "path": "apps/demo/src/\u4f60\u597d.tsx",
                    "status": "tracked-present",
                    "fingerprint": "a" * 64,
                }
            ],
            "protected_control_digest": "b" * 64,
            "protected_categories": [],
            "protected_entry_count": 0,
        }
    )

    assert snapshot.available is True
    assert snapshot.entries[0].path == "apps/demo/src/\u4f60\u597d.tsx"


def test_regular_file_collection_fails_closed_for_unsupported_directory_entry(
    tmp_path, monkeypatch
) -> None:
    class UnsupportedDirEntry:
        name = "unsupported"
        path = str(tmp_path / "unsupported")

        def stat(self, *, follow_symlinks: bool = True):
            return SimpleNamespace(st_mode=0, st_file_attributes=0)

        def is_symlink(self) -> bool:
            return False

        def is_file(self, *, follow_symlinks: bool = True) -> bool:
            return False

        def is_dir(self, *, follow_symlinks: bool = True) -> bool:
            return False

    _write_git_control_state(tmp_path)
    _stub_git_status(monkeypatch, b"")
    original_scandir = task_run_scope.os.scandir

    def scandir_with_unsupported_root_entry(directory):
        if Path(directory) == tmp_path:
            return [UnsupportedDirEntry()]
        return original_scandir(directory)

    monkeypatch.setattr(
        task_run_scope.os, "scandir", scandir_with_unsupported_root_entry
    )
    snapshot = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")

    assert snapshot.available is False
    assert snapshot.entries == ()
    assert snapshot.protected_control_digest is None
    assert str(tmp_path) not in (snapshot.reason or "")


@pytest.mark.skipif(os.name != "nt", reason="Windows junction semantics")
def test_capture_fails_closed_for_regular_directory_junction(tmp_path, monkeypatch) -> None:
    _write_git_control_state(tmp_path)
    external_directory = tmp_path.parent / f"{tmp_path.name}-junction-target"
    external_directory.mkdir()
    (external_directory / "outside.txt").write_text("outside", encoding="utf-8")
    link = tmp_path / "apps/demo/src/linked-dir"
    link.parent.mkdir(parents=True)
    _create_windows_junction(link, external_directory)
    _stub_git_status(monkeypatch, b"")

    snapshot = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")

    assert snapshot.available is False
    assert snapshot.entries == ()
    assert snapshot.protected_control_digest is None
    assert str(external_directory) not in (snapshot.reason or "")


@pytest.mark.skipif(os.name != "nt", reason="Windows junction semantics")
def test_capture_fails_closed_for_secrets_directory_junction(tmp_path, monkeypatch) -> None:
    _write_git_control_state(tmp_path)
    external_directory = tmp_path.parent / f"{tmp_path.name}-secret-junction-target"
    external_directory.mkdir()
    (external_directory / "token.txt").write_text("outside-secret", encoding="utf-8")
    _create_windows_junction(tmp_path / "secrets", external_directory)
    _stub_git_status(monkeypatch, b"")

    snapshot = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")

    assert snapshot.available is False
    assert snapshot.entries == ()
    assert snapshot.protected_control_digest is None
    assert str(external_directory) not in (snapshot.reason or "")


@pytest.mark.skipif(os.name != "nt", reason="Windows reparse-point semantics")
def test_capture_fails_closed_for_simulated_non_symlink_reparse_entry(
    tmp_path, monkeypatch
) -> None:
    _write_git_control_state(tmp_path)
    simulated_directory = tmp_path / "linked-dir"
    simulated_directory.mkdir()
    (simulated_directory / "outside.txt").write_text("outside", encoding="utf-8")
    _stub_git_status(monkeypatch, b"")
    original_scandir = task_run_scope.os.scandir

    class ReparseDirectoryEntry:
        name = "linked-dir"
        path = str(simulated_directory)

        def stat(self, *, follow_symlinks: bool = True):
            return SimpleNamespace(
                st_mode=stat.S_IFDIR,
                st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT,
            )

        def is_symlink(self) -> bool:
            return False

        def is_file(self, *, follow_symlinks: bool = True) -> bool:
            return False

        def is_dir(self, *, follow_symlinks: bool = True) -> bool:
            return True

    def scandir_with_reparse_root_entry(directory):
        if Path(directory) == tmp_path:
            return [ReparseDirectoryEntry()]
        return original_scandir(directory)

    monkeypatch.setattr(task_run_scope.os, "scandir", scandir_with_reparse_root_entry)
    snapshot = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")

    assert snapshot.available is False
    assert snapshot.entries == ()
    assert snapshot.protected_control_digest is None
    assert str(simulated_directory) not in (snapshot.reason or "")


def _write_named_ads(path: Path, *, stream_name: str, content: str) -> Path:
    stream_path = Path(f"{path}:{stream_name}")
    stream_path.write_text(content, encoding="utf-8")
    return stream_path


def _assert_unavailable_ads_snapshot(
    snapshot: ScopeSnapshot,
    *,
    root: Path,
    stream_name: str,
    secret: str,
    touched_path: Path,
) -> None:
    assert snapshot.available is False
    assert snapshot.reason == "scope_capture_unavailable"
    assert snapshot.entries == ()
    assert snapshot.protected_control_digest is None
    public_metadata = snapshot.to_metadata()
    internal_metadata = snapshot.to_metadata(include_internal=True)
    serialized = str(public_metadata) + str(internal_metadata)
    assert stream_name not in serialized
    assert secret not in serialized
    assert str(root) not in serialized
    assert str(touched_path) not in serialized


@pytest.mark.skipif(os.name != "nt", reason="Windows NTFS named streams")
def test_snapshot_rejects_named_ads_on_ordinary_file(tmp_path, monkeypatch) -> None:
    _write_git_control_state(tmp_path)
    ordinary_file = tmp_path / "ordinary.txt"
    ordinary_file.write_text("ordinary", encoding="utf-8")
    stream_name = "agenthub_ads_ordinary"
    secret = "ordinary-stream-secret"
    _write_named_ads(ordinary_file, stream_name=stream_name, content=secret)
    _stub_git_status(monkeypatch, b"")

    snapshot = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="scope-test-key",
    )

    _assert_unavailable_ads_snapshot(
        snapshot,
        root=tmp_path,
        stream_name=stream_name,
        secret=secret,
        touched_path=ordinary_file,
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows NTFS named streams")
@pytest.mark.parametrize("directory_kind", ("assigned-root", "empty-child"))
def test_snapshot_rejects_named_ads_on_empty_ordinary_directory(
    tmp_path, monkeypatch, directory_kind: str
) -> None:
    _write_git_control_state(tmp_path)
    if directory_kind == "assigned-root":
        ordinary_directory = tmp_path
    else:
        ordinary_directory = tmp_path / "empty-directory"
        ordinary_directory.mkdir()
    stream_name = f"agenthub_ads_directory_{directory_kind}"
    secret = f"{directory_kind}-stream-secret"
    _write_named_ads(ordinary_directory, stream_name=stream_name, content=secret)
    _stub_git_status(monkeypatch, b"")

    snapshot = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="scope-test-key",
    )

    _assert_unavailable_ads_snapshot(
        snapshot,
        root=tmp_path,
        stream_name=stream_name,
        secret=secret,
        touched_path=ordinary_directory,
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows NTFS named streams")
def test_snapshot_rejects_named_ads_on_protected_env_file(tmp_path, monkeypatch) -> None:
    _write_git_control_state(tmp_path)
    protected_file = tmp_path / ".env.local"
    protected_file.write_text("TOKEN=ordinary", encoding="utf-8")
    stream_name = "agenthub_ads_protected_env"
    secret = "protected-env-stream-secret"
    _write_named_ads(protected_file, stream_name=stream_name, content=secret)
    _stub_git_status(monkeypatch, b"")

    snapshot = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="scope-test-key",
    )

    _assert_unavailable_ads_snapshot(
        snapshot,
        root=tmp_path,
        stream_name=stream_name,
        secret=secret,
        touched_path=protected_file,
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows NTFS named streams")
@pytest.mark.parametrize(
    "target_kind",
    ("pointer", "git-directory", "resolved-head", "resolved-directory"),
)
def test_snapshot_rejects_named_ads_on_git_control_surface(
    tmp_path, monkeypatch, target_kind: str
) -> None:
    if target_kind == "git-directory":
        gitdir = tmp_path / ".git"
        gitdir.mkdir()
        (gitdir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        touched_path = gitdir
    else:
        _write_git_control_state(tmp_path)
        gitdir = tmp_path / "git-control"
        if target_kind == "pointer":
            touched_path = tmp_path / ".git"
        elif target_kind == "resolved-head":
            touched_path = gitdir / "HEAD"
        else:
            touched_path = gitdir
    stream_name = f"agenthub_ads_gitdir_{target_kind}"
    secret = f"resolved-gitdir-{target_kind}-stream-secret"
    _write_named_ads(touched_path, stream_name=stream_name, content=secret)
    _stub_git_status(monkeypatch, b"")

    snapshot = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="scope-test-key",
    )

    _assert_unavailable_ads_snapshot(
        snapshot,
        root=tmp_path,
        stream_name=stream_name,
        secret=secret,
        touched_path=touched_path,
    )


class _FakeWindowsStreamApi:
    def __init__(
        self,
        *,
        first: tuple[object | None, str | None, int],
        next_results: tuple[tuple[bool, str | None, int], ...] = (),
        close_result: bool = True,
        close_error: BaseException | None = None,
    ) -> None:
        self.first = first
        self.next_results = list(next_results)
        self.close_result = close_result
        self.close_error = close_error
        self.first_paths: list[str] = []
        self.next_handles: list[object] = []
        self.closed_handles: list[object] = []

    def find_first(self, path: str):
        self.first_paths.append(path)
        return self.first

    def find_next(self, handle: object):
        self.next_handles.append(handle)
        if not self.next_results:
            raise AssertionError("unexpected FindNextStreamW call")
        return self.next_results.pop(0)

    def find_close(self, handle: object) -> bool:
        self.closed_handles.append(handle)
        if self.close_error is not None:
            raise self.close_error
        return self.close_result


def _enumerate_windows_streams_for_test(path: Path, api: _FakeWindowsStreamApi) -> None:
    helper = getattr(task_run_scope, "_enumerate_windows_streams", None)
    assert helper is not None, "Windows stream helper is not implemented"
    helper(path, api=api)


def test_windows_stream_helper_accepts_only_default_stream_and_next_eof() -> None:
    path = Path("C:/assigned/ordinary.txt")
    api = _FakeWindowsStreamApi(
        first=("handle-1", "::$DATA", 0),
        next_results=((False, None, 38),),
    )

    _enumerate_windows_streams_for_test(path, api)

    assert api.first_paths == [str(path)]
    assert api.next_handles == ["handle-1"]
    assert api.closed_handles == ["handle-1"]


def test_windows_stream_helper_accepts_initial_eof_without_a_handle() -> None:
    api = _FakeWindowsStreamApi(first=(None, None, 38))

    _enumerate_windows_streams_for_test(Path("C:/assigned/empty"), api)

    assert api.closed_handles == []


@pytest.mark.parametrize(
    "invalid_handle",
    (pytest.param(False, id="bool-false"), pytest.param(0, id="integer-zero")),
)
def test_windows_stream_helper_rejects_invalid_initial_handle_before_followup(
    invalid_handle: object,
) -> None:
    path = Path("C:/assigned/ordinary.txt")
    api = _FakeWindowsStreamApi(
        first=(invalid_handle, "::$DATA", 0),
        next_results=((False, None, 38),),
    )

    with pytest.raises(task_run_scope._SnapshotCaptureError) as exc_info:
        _enumerate_windows_streams_for_test(path, api)

    assert str(path) not in str(exc_info.value)
    assert "::$DATA" not in str(exc_info.value)
    assert api.next_handles == []
    assert api.closed_handles == []


def test_windows_stream_helper_rejects_str_subclass_next_stream_name() -> None:
    class StreamName(str):
        pass

    path = Path("C:/assigned/ordinary.txt")
    stream_name = StreamName("::$DATA")
    api = _FakeWindowsStreamApi(
        first=("handle-subclass", "::$DATA", 0),
        next_results=(
            (True, stream_name, 0),
            (False, None, 38),
        ),
    )

    with pytest.raises(task_run_scope._SnapshotCaptureError) as exc_info:
        _enumerate_windows_streams_for_test(path, api)

    assert str(path) not in str(exc_info.value)
    assert str(stream_name) not in str(exc_info.value)
    assert api.next_handles == ["handle-subclass"]
    assert api.closed_handles == ["handle-subclass"]


def test_windows_stream_helper_rejects_malformed_first_error_code() -> None:
    api = _FakeWindowsStreamApi(
        first=("handle-malformed", "::$DATA", False),
        next_results=((False, None, 38),),
    )

    with pytest.raises(task_run_scope._SnapshotCaptureError):
        _enumerate_windows_streams_for_test(Path("C:/assigned/ordinary.txt"), api)

    assert api.closed_handles == ["handle-malformed"]


@pytest.mark.parametrize("phase", ("initial", "next"))
def test_windows_stream_helper_rejects_named_stream_without_leaking_evidence(
    phase: str,
) -> None:
    stream_name = ":agenthub_secret:$DATA"
    secret = "named-stream-secret"
    path = Path("C:/assigned/ordinary.txt")
    if phase == "initial":
        api = _FakeWindowsStreamApi(first=("handle-2", stream_name, 0))
    else:
        api = _FakeWindowsStreamApi(
            first=("handle-2", "::$DATA", 0),
            next_results=((True, stream_name, 0),),
        )

    with pytest.raises(task_run_scope._SnapshotCaptureError) as exc_info:
        _enumerate_windows_streams_for_test(path, api)

    assert stream_name not in str(exc_info.value)
    assert secret not in str(exc_info.value)
    assert str(path) not in str(exc_info.value)
    assert api.closed_handles == ["handle-2"]


@pytest.mark.parametrize("phase", ("initial", "next"))
def test_windows_stream_helper_fails_closed_on_unexpected_api_error(phase: str) -> None:
    if phase == "initial":
        api = _FakeWindowsStreamApi(first=(None, None, 5))
    else:
        api = _FakeWindowsStreamApi(
            first=("handle-3", "::$DATA", 0),
            next_results=((False, None, 5),),
        )

    with pytest.raises(task_run_scope._SnapshotCaptureError):
        _enumerate_windows_streams_for_test(Path("C:/assigned/ordinary.txt"), api)

    if phase == "next":
        assert api.closed_handles == ["handle-3"]
    else:
        assert api.closed_handles == []


@pytest.mark.parametrize(
    ("close_result", "close_error"),
    (
        (False, None),
        (True, RuntimeError("close failed")),
    ),
)
def test_windows_stream_helper_requires_reliable_handle_close(
    close_result: bool, close_error: BaseException | None
) -> None:
    api = _FakeWindowsStreamApi(
        first=("handle-4", "::$DATA", 0),
        next_results=((False, None, 38),),
        close_result=close_result,
        close_error=close_error,
    )

    with pytest.raises(task_run_scope._SnapshotCaptureError):
        _enumerate_windows_streams_for_test(Path("C:/assigned/ordinary.txt"), api)
    assert api.closed_handles == ["handle-4"]


def test_symlink_and_reparse_paths_do_not_call_stream_enumerator(
    tmp_path, monkeypatch
) -> None:
    calls: list[Path] = []
    monkeypatch.setattr(
        task_run_scope,
        "_enumerate_windows_streams",
        lambda path, **kwargs: calls.append(Path(path)),
        raising=False,
    )
    target = tmp_path / "target.txt"
    target.write_text("target", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        os.symlink(target, link)
    except OSError as exc:
        pytest.skip(f"the test environment cannot create a file-system symlink: {exc}")

    root, observations = task_run_scope._lexical_worktree_root(tmp_path)
    link_observations, observation = task_run_scope._extend_path_observations(
        observations,
        link,
    )
    assert observation is not None and observation[0] == "symlink"
    task_run_scope._stable_readlink(link, link_observations)

    reparse_path = tmp_path / "reparse-directory"
    reparse_path.mkdir()

    class SimulatedReparseEntry:
        name = "reparse-directory"
        path = str(reparse_path)

        def stat(self, *, follow_symlinks: bool = True):
            return SimpleNamespace(
                st_mode=stat.S_IFDIR,
                st_file_attributes=getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400),
            )

    with pytest.raises(task_run_scope._SnapshotCaptureError):
        task_run_scope._stable_dir_entry_observations(
            SimulatedReparseEntry(),
            observations,
        )

    assert calls == []


@pytest.mark.skipif(os.name != "nt", reason="Windows protected-path semantics")
@pytest.mark.parametrize(
    ("relative_path", "category"),
    (
        (".ENV", ".env"),
        (".Env.Local", ".env"),
        ("NODE_MODULES/package/index.js", "node_modules"),
        ("SECRETS/token", "secrets"),
    ),
)
def test_windows_case_insensitive_protected_paths_are_redacted_and_compared(
    tmp_path, monkeypatch, relative_path: str, category: str
) -> None:
    _write_git_control_state(tmp_path)
    protected_file = tmp_path.joinpath(*relative_path.split("/"))
    protected_file.parent.mkdir(parents=True, exist_ok=True)
    protected_file.write_text("first", encoding="utf-8")
    _stub_git_status(monkeypatch, b"")

    baseline = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")
    protected_file.write_text("second", encoding="utf-8")
    current = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")
    decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)

    assert relative_path not in {entry.path for entry in baseline.entries}
    assert relative_path not in {entry.path for entry in current.entries}
    assert category in baseline.protected_categories
    assert baseline.protected_categories == current.protected_categories
    assert baseline.protected_entry_count == current.protected_entry_count
    assert decision.rejected_paths == ("<protected-footprint>",)


def test_injected_case_insensitive_semantics_protects_top_level_git_alias(
    tmp_path,
) -> None:
    """A root-bound resolver must classify a case alias without platform guessing."""
    gitdir = tmp_path / "git-control"
    gitdir.mkdir()
    (gitdir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    # POSIX normally treats this as an ordinary entry; the injected resolver
    # models a case-insensitive mount without changing the real volume.
    (tmp_path / ".GIT").write_text("gitdir: git-control\n", encoding="utf-8")

    snapshot = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="case-alias-key",
        runner=_layer_runner(index_output=b"", tree_output=b""),
        case_semantics_resolver=lambda _directory, _observations: "insensitive",
    )

    assert snapshot.available is True
    assert ".GIT" not in {entry.path for entry in snapshot.entries}
    assert ".git" in snapshot.protected_categories


def test_injected_case_insensitive_semantics_excludes_gitdir_case_alias(
    tmp_path,
) -> None:
    gitdir = tmp_path / "git-control"
    gitdir.mkdir()
    (gitdir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    # The pointer deliberately uses a different spelling from the observed
    # directory. A case-insensitive resolver must bind it to the observed tree.
    (tmp_path / ".git").write_text("gitdir: GIT-CONTROL\n", encoding="utf-8")

    snapshot = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="case-alias-key",
        runner=_layer_runner(
            index_output=_git_index_record("GIT-CONTROL/HEAD"),
            tree_output=_git_tree_record("GIT-CONTROL/HEAD"),
        ),
        case_semantics_resolver=lambda _directory, _observations: "insensitive",
    )

    assert snapshot.available is True
    assert "GIT-CONTROL/HEAD" not in {entry.path for entry in snapshot.entries}
    assert "git-control/HEAD" not in {entry.path for entry in snapshot.entries}


def test_unknown_case_semantics_fails_closed_without_guessing(tmp_path) -> None:
    gitdir = tmp_path / "git-control"
    gitdir.mkdir()
    (gitdir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (tmp_path / ".GIT").write_text("gitdir: git-control\n", encoding="utf-8")

    snapshot = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="case-alias-key",
        runner=_layer_runner(index_output=b"", tree_output=b""),
        case_semantics_resolver=lambda _directory, _observations: "unknown",
    )

    assert snapshot.available is False
    assert snapshot.reason == "scope_capture_unavailable"
    assert snapshot.entries == ()
    assert snapshot.protected_control_digest is None


def test_posix_exact_case_semantics_keeps_distinct_git_spelling_ordinary(
    tmp_path,
) -> None:
    if os.name == "nt":
        pytest.skip("exact-case POSIX semantics regression")
    _write_git_control_state(tmp_path)
    ordinary_alias = tmp_path / ".GIT"
    ordinary_alias.write_text("ordinary", encoding="utf-8")

    snapshot = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="case-sensitive-key",
        runner=_layer_runner(index_output=b"", tree_output=b""),
        case_semantics_resolver=lambda _directory, _observations: "sensitive",
    )

    assert snapshot.available is True
    assert ".GIT" in {entry.path for entry in snapshot.entries}


@pytest.mark.parametrize(
    "protected_alias",
    (
        ".GIT/notes.txt",
        ".Env.Local",
        "NODE_MODULES/package/index.js",
        "SECRETS/token.txt",
    ),
)
def test_sensitive_root_snapshot_alias_without_persisted_case_binding_fails_closed(
    protected_alias: str,
) -> None:
    """Rootless v2 metadata cannot safely preserve per-directory case evidence."""
    snapshot = _snapshot(
        ScopeEntry(
            path=protected_alias,
            status="tracked-present",
            fingerprint="c" * 64,
        )
    )

    assert task_run_scope._is_complete_snapshot(snapshot) is False


def test_sensitive_parent_does_not_reinterpret_trusted_gitdir_case_alias(
    tmp_path,
    monkeypatch,
) -> None:
    root = tmp_path / "assigned-root"
    root.mkdir()
    actual_gitdir = root / "git-control"
    actual_gitdir.mkdir()
    root_observations = task_run_scope._lexical_worktree_root(root)[1]
    alias_gitdir = Path(str(root).swapcase()) / "git-control"
    case_context = task_run_scope._CaseSemanticsContext(
        lambda _directory, _observations: "sensitive"
    )
    external_calls: list[Path] = []

    def reject_external_alias(directory: Path, **_kwargs):
        external_calls.append(directory)
        raise task_run_scope._SnapshotCaptureError

    monkeypatch.setattr(
        task_run_scope,
        "_absolute_directory_observations",
        reject_external_alias,
    )

    with pytest.raises(task_run_scope._SnapshotCaptureError):
        task_run_scope._trusted_git_directory_observations(
            root,
            alias_gitdir,
            root_observations=root_observations,
            case_context=case_context,
        )

    assert external_calls == [alias_gitdir]


def test_sensitive_parent_does_not_treat_pointer_root_alias_as_inside(
    tmp_path,
) -> None:
    root = tmp_path / "assigned-root"
    root.mkdir()
    actual_gitdir = root / "git-control"
    actual_gitdir.mkdir()
    root_observations = task_run_scope._lexical_worktree_root(root)[1]
    alias_gitdir = Path(str(root).swapcase()) / "git-control"
    case_context = task_run_scope._CaseSemanticsContext(
        lambda _directory, _observations: "sensitive"
    )

    candidate = task_run_scope._gitdir_pointer_candidate_inside_root(
        root,
        f"gitdir: {alias_gitdir}\n".encode(),
        root_observations=root_observations,
        case_context=case_context,
    )

    assert candidate is None


@pytest.mark.skipif(os.name != "nt", reason="WindowsPath case-folding regression")
def test_external_case_alias_gitdir_does_not_exclude_ordinary_root_subtree(
    tmp_path,
) -> None:
    root = tmp_path / "Repo"
    ordinary = root / "git-control" / "ordinary.txt"
    ordinary.parent.mkdir(parents=True)
    ordinary.write_text("ordinary", encoding="utf-8")
    external_gitdir = root.with_name("repo") / "git-control"
    root_observations = task_run_scope._lexical_worktree_root(root)[1]
    case_context = task_run_scope._CaseSemanticsContext(
        lambda _directory, _observations: "sensitive"
    )

    files = task_run_scope._collect_regular_files(
        root,
        (external_gitdir,),
        root_observations=root_observations,
        case_context=case_context,
    )

    assert "git-control/ordinary.txt" in files


@pytest.mark.skipif(os.name != "nt", reason="WindowsPath case-folding regression")
def test_external_case_alias_gitdir_does_not_hide_protected_root_subtree(
    tmp_path,
) -> None:
    root = tmp_path / "Repo"
    secret = root / "git-control" / "secrets" / "token.txt"
    secret.parent.mkdir(parents=True)
    secret.write_text("secret", encoding="utf-8")
    external_gitdir = root.with_name("repo") / "git-control"
    root_observations = task_run_scope._lexical_worktree_root(root)[1]
    case_context = task_run_scope._CaseSemanticsContext(
        lambda _directory, _observations: "sensitive"
    )
    records: list[bytes] = []
    audit = task_run_scope._ProtectedAudit()

    task_run_scope._collect_worktree_protected_records(
        root,
        records,
        audit,
        [external_gitdir],
        root_observations=root_observations,
        case_context=case_context,
    )

    assert audit.categories == {"secrets"}
    assert audit.entry_count == 2
    assert records


@pytest.mark.skipif(os.name != "nt", reason="WindowsPath case-folding regression")
def test_external_case_alias_gitdir_does_not_filter_root_git_metadata(
    tmp_path,
) -> None:
    root = tmp_path / "Repo"
    (root / "git-control").mkdir(parents=True)
    external_gitdir = root.with_name("repo") / "git-control"
    root_observations = task_run_scope._lexical_worktree_root(root)[1]
    case_context = task_run_scope._CaseSemanticsContext(
        lambda _directory, _observations: "sensitive"
    )

    excluded = task_run_scope._is_protected_or_excluded_path(
        root,
        "git-control/ordinary.txt",
        (external_gitdir,),
        root_observations=root_observations,
        case_context=case_context,
    )

    assert excluded is False


def test_default_case_probe_rejects_dual_spelling_same_inode(
    tmp_path,
    monkeypatch,
) -> None:
    root, observations = task_run_scope._lexical_worktree_root(tmp_path)
    identity = (1, 2, stat.S_IFREG, 0)
    exact = root / ".GIT"
    alternate = root / ".git"
    original_observation = task_run_scope._path_observation
    monkeypatch.setattr(
        task_run_scope,
        "_stable_scandir",
        lambda _directory, _observations: (
            SimpleNamespace(name=".GIT", path=str(exact)),
            SimpleNamespace(name=".git", path=str(alternate)),
        ),
    )

    def hardlink_observation(path: Path, *, absent_allowed: bool = False):
        if str(path) in {str(exact), str(alternate)}:
            return "file", identity
        return original_observation(path, absent_allowed=absent_allowed)

    monkeypatch.setattr(task_run_scope, "_path_observation", hardlink_observation)

    assert task_run_scope._CaseSemanticsContext().resolve(root, observations) == "unknown"


def test_default_case_probe_rejects_exact_to_alternate_rename_race(
    tmp_path,
    monkeypatch,
) -> None:
    root, observations = task_run_scope._lexical_worktree_root(tmp_path)
    identity = (1, 3, stat.S_IFREG, 0)
    exact = root / "A"
    alternate = root / "a"
    original_observation = task_run_scope._path_observation
    alternate_reads = 0
    monkeypatch.setattr(
        task_run_scope,
        "_stable_scandir",
        lambda _directory, _observations: (
            SimpleNamespace(name="A", path=str(exact)),
        ),
    )

    def racing_observation(path: Path, *, absent_allowed: bool = False):
        nonlocal alternate_reads
        if str(path) == str(exact):
            return "file", identity
        if str(path) == str(alternate):
            alternate_reads += 1
            return ("file", identity) if alternate_reads == 1 else None
        return original_observation(path, absent_allowed=absent_allowed)

    monkeypatch.setattr(task_run_scope, "_path_observation", racing_observation)

    assert task_run_scope._CaseSemanticsContext().resolve(root, observations) == "unknown"


def test_default_case_probe_rechecks_observations_after_final_child_scan(
    tmp_path,
    monkeypatch,
) -> None:
    root, observations = task_run_scope._lexical_worktree_root(tmp_path)
    exact = root / "A"
    alternate = root / "a"
    identity_before = (1, 30, stat.S_IFREG, 0)
    identity_after = (1, 31, stat.S_IFREG, 0)
    original_observation = task_run_scope._path_observation
    scan_count = 0
    replaced = False

    def replacing_final_scan(_directory, _observations):
        nonlocal scan_count, replaced
        scan_count += 1
        if scan_count == 2:
            replaced = True
        return (SimpleNamespace(name="A", path=str(exact)),)

    def switched_observation(path: Path, *, absent_allowed: bool = False):
        if str(path) in {str(exact), str(alternate)}:
            identity = identity_after if replaced else identity_before
            return "file", identity
        return original_observation(path, absent_allowed=absent_allowed)

    monkeypatch.setattr(task_run_scope, "_stable_scandir", replacing_final_scan)
    monkeypatch.setattr(task_run_scope, "_path_observation", switched_observation)

    assert task_run_scope._CaseSemanticsContext().resolve(root, observations) == "unknown"
    assert scan_count == 2


def test_default_case_probe_checks_every_spelling_in_ascii_collision_group(
    tmp_path,
    monkeypatch,
) -> None:
    root, observations = task_run_scope._lexical_worktree_root(tmp_path)
    names = ("AB", "Ab", "aB")
    identities = {
        "AB": (1, 40, stat.S_IFREG, 0),
        "Ab": (1, 41, stat.S_IFREG, 0),
        "aB": (1, 40, stat.S_IFREG, 0),
    }
    original_observation = task_run_scope._path_observation
    monkeypatch.setattr(
        task_run_scope,
        "_stable_scandir",
        lambda _directory, _observations: tuple(
            SimpleNamespace(name=name, path=str(root / name)) for name in names
        ),
    )

    def collision_observation(path: Path, *, absent_allowed: bool = False):
        if path.name in identities and path.parent == root:
            return "file", identities[path.name]
        return original_observation(path, absent_allowed=absent_allowed)

    monkeypatch.setattr(task_run_scope, "_path_observation", collision_observation)

    assert task_run_scope._CaseSemanticsContext().resolve(root, observations) == "unknown"


def test_default_case_probe_revalidates_cached_witness(
    tmp_path,
    monkeypatch,
) -> None:
    root, observations = task_run_scope._lexical_worktree_root(tmp_path)
    identity = (1, 4, stat.S_IFREG, 0)
    exact = root / "A"
    alternate = root / "a"
    original_observation = task_run_scope._path_observation
    dual_spelling = False

    def changing_children(_directory, _observations):
        children = [SimpleNamespace(name="A", path=str(exact))]
        if dual_spelling:
            children.append(SimpleNamespace(name="a", path=str(alternate)))
        return tuple(children)

    def same_inode_observation(path: Path, *, absent_allowed: bool = False):
        if str(path) in {str(exact), str(alternate)}:
            return "file", identity
        return original_observation(path, absent_allowed=absent_allowed)

    monkeypatch.setattr(task_run_scope, "_stable_scandir", changing_children)
    monkeypatch.setattr(task_run_scope, "_path_observation", same_inode_observation)
    context = task_run_scope._CaseSemanticsContext()

    assert context.resolve(root, observations) == "insensitive"
    dual_spelling = True
    assert context.resolve(root, observations) == "unknown"


def test_default_case_probe_ignores_non_ascii_case_mapping(
    tmp_path,
    monkeypatch,
) -> None:
    root, observations = task_run_scope._lexical_worktree_root(tmp_path)
    monkeypatch.setattr(
        task_run_scope,
        "_stable_scandir",
        lambda _directory, _observations: (
            SimpleNamespace(name="ß", path=str(root / "ß")),
        ),
    )
    original_observation = task_run_scope._path_observation

    def no_child_probe(path: Path, *, absent_allowed: bool = False):
        if str(path) in {str(root / "ß"), str(root / "SS")}:
            pytest.fail("non-ASCII names must not become case witnesses")
        return original_observation(path, absent_allowed=absent_allowed)

    monkeypatch.setattr(task_run_scope, "_path_observation", no_child_probe)

    assert task_run_scope._CaseSemanticsContext().resolve(root, observations) == "unknown"


def test_default_case_probe_never_writes_probe_entry(
    tmp_path,
    monkeypatch,
) -> None:
    witness = tmp_path / "A"
    witness.write_text("witness", encoding="utf-8")
    root, observations = task_run_scope._lexical_worktree_root(tmp_path)

    def reject_write(*_args, **_kwargs):
        pytest.fail("case probing must remain read-only")

    monkeypatch.setattr(Path, "touch", reject_write)
    monkeypatch.setattr(Path, "write_text", reject_write)
    monkeypatch.setattr(Path, "mkdir", reject_write)
    monkeypatch.setattr(task_run_scope.os, "open", reject_write)
    monkeypatch.setattr(task_run_scope.os, "mkdir", reject_write)
    monkeypatch.setattr(task_run_scope.os, "rename", reject_write)
    monkeypatch.setattr(task_run_scope.os, "replace", reject_write)
    monkeypatch.setattr(task_run_scope.os, "unlink", reject_write)

    result = task_run_scope._CaseSemanticsContext().resolve(root, observations)

    assert result in {"sensitive", "insensitive"}


def test_exact_protected_and_empty_ordinary_paths_do_not_probe_case_semantics(
    tmp_path,
) -> None:
    empty = tmp_path / "empty-directory"
    empty.mkdir()
    root, observations = task_run_scope._lexical_worktree_root(tmp_path)
    context = task_run_scope._CaseSemanticsContext(
        lambda *_args: pytest.fail("exact and unrelated empty paths must not probe")
    )

    assert task_run_scope._protected_category_at(
        ".git/config",
        root=root,
        root_observations=observations,
        case_context=context,
    ) == ".git"
    assert task_run_scope._collect_regular_files(
        root,
        (),
        root_observations=observations,
        case_context=context,
    ) == ("empty-directory",)


def test_absolute_containment_uses_each_parent_case_semantics(tmp_path) -> None:
    outer = tmp_path / "Outer"
    root = outer / "Repo"
    root.mkdir(parents=True)
    root_observations = task_run_scope._lexical_worktree_root(root)[1]
    alias = tmp_path / "oUTER" / "rEPO" / "bin" / "git"
    queried: list[str] = []

    def mixed_semantics(directory: Path, _observations) -> str:
        queried.append(str(directory))
        if str(directory) == str(tmp_path):
            return "insensitive"
        if str(directory) == str(outer):
            return "sensitive"
        pytest.fail(f"unexpected case query: {directory}")

    result = task_run_scope._filesystem_path_equal_or_descendant_at(
        str(alias),
        str(root),
        directory=root,
        observations=root_observations,
        case_context=task_run_scope._CaseSemanticsContext(mixed_semantics),
    )

    assert result is False
    assert queried == [str(tmp_path), str(outer)]


@pytest.mark.skipif(os.name != "nt", reason="NTFS Unicode casefold regression")
def test_unicode_casefold_alias_is_not_filesystem_containment(tmp_path) -> None:
    root = tmp_path / "ßroot" / "repo"
    root.mkdir(parents=True)
    external_gitdir = tmp_path / "ssroot" / "repo" / "gitdir"
    external_gitdir.mkdir(parents=True)
    root_observations = task_run_scope._lexical_worktree_root(root)[1]
    case_context = task_run_scope._CaseSemanticsContext(
        lambda _directory, _observations: "insensitive"
    )

    contained = task_run_scope._filesystem_path_equal_or_descendant_at(
        str(external_gitdir),
        str(root),
        directory=root,
        observations=root_observations,
        case_context=case_context,
    )

    assert contained is False


@pytest.mark.skipif(os.name != "nt", reason="NTFS Unicode casefold regression")
def test_unicode_casefold_alias_keeps_external_trusted_gitdir_identity(tmp_path) -> None:
    root = tmp_path / "ßroot" / "repo"
    internal_gitdir = root / "gitdir"
    internal_gitdir.mkdir(parents=True)
    external_gitdir = tmp_path / "ssroot" / "repo" / "gitdir"
    external_gitdir.mkdir(parents=True)
    root_observations = task_run_scope._lexical_worktree_root(root)[1]
    case_context = task_run_scope._CaseSemanticsContext(
        lambda _directory, _observations: "insensitive"
    )
    internal_identity = task_run_scope._path_observation(internal_gitdir)
    external_identity = task_run_scope._path_observation(external_gitdir)
    assert internal_identity != external_identity

    resolved, observations = task_run_scope._trusted_git_directory_observations(
        root,
        external_gitdir,
        root_observations=root_observations,
        case_context=case_context,
    )

    assert str(resolved) == str(external_gitdir)
    assert observations[-1][2] == external_identity[1]


@pytest.mark.skipif(os.name != "nt", reason="NTFS Unicode casefold regression")
def test_unicode_casefold_alias_does_not_resolve_an_ascii_child(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    unicode_child = root / "ßgit"
    unicode_child.mkdir()
    root_observations = task_run_scope._lexical_worktree_root(root)[1]
    case_context = task_run_scope._CaseSemanticsContext(
        lambda _directory, _observations: "insensitive"
    )

    resolved = task_run_scope._resolve_child_entry(
        root,
        "ssgit",
        root_observations,
        case_context,
        absent_allowed=True,
    )

    assert resolved is None


@pytest.mark.parametrize("path", ("ſecrets/token", "node_moduleſ/package.json"))
def test_live_unicode_folded_protected_alias_is_unverifiable(
    tmp_path,
    path: str,
) -> None:
    root, observations = task_run_scope._lexical_worktree_root(tmp_path)
    case_context = task_run_scope._CaseSemanticsContext(
        lambda _directory, _observations: "insensitive"
    )

    with pytest.raises(task_run_scope._SnapshotCaptureError):
        task_run_scope._protected_category_at(
            path,
            root=root,
            root_observations=observations,
            case_context=case_context,
        )


@pytest.mark.parametrize("path", ("ſecrets/token", "node_moduleſ/package.json"))
def test_rootless_unicode_folded_protected_alias_remains_conservative(
    path: str,
) -> None:
    assert task_run_scope._is_protected_repository_path(path) is True


def test_trusted_gitdir_handles_git_symlink_without_following_its_target(
    tmp_path, monkeypatch
) -> None:
    trusted_gitdir = tmp_path / "trusted-gitdir"
    trusted_gitdir.mkdir()
    (trusted_gitdir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    untrusted_gitdir = tmp_path.parent / f"{tmp_path.name}-untrusted-gitdir"
    untrusted_gitdir.mkdir()
    (untrusted_gitdir / "HEAD").write_text("ref: refs/heads/attacker\n", encoding="utf-8")
    git_control = tmp_path / ".git"
    git_control.write_text(f"gitdir: {trusted_gitdir}\n", encoding="utf-8")
    _stub_git_status(monkeypatch, b"")
    control_key = "scope-test-key"
    baseline = capture_worktree_scope_snapshot(tmp_path, control_key=control_key)

    git_control.unlink()
    os.symlink(untrusted_gitdir, git_control)
    original_exists = Path.exists
    original_collect_tree_records = task_run_scope._collect_tree_records
    runner_calls: list[tuple[list[str], dict[str, object]]] = []

    def exists_without_git_symlink_follow(path: Path) -> bool:
        if path == git_control:
            pytest.fail("post-run .git symlink must not be stat-followed")
        return original_exists(path)

    def collect_without_untrusted_target(path, *args) -> None:
        assert Path(path) != untrusted_gitdir
        original_collect_tree_records(path, *args)

    def trusted_status_runner(command: list[str], **kwargs):
        runner_calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(Path, "exists", exists_without_git_symlink_follow)
    monkeypatch.setattr(
        task_run_scope, "_collect_tree_records", collect_without_untrusted_target
    )
    current = capture_worktree_scope_snapshot(
        tmp_path,
        control_key=control_key,
        trusted_git_dir=trusted_gitdir,
        runner=trusted_status_runner,
    )
    decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)

    assert current.available is True
    assert str(untrusted_gitdir) not in str(current.to_metadata(include_internal=True))
    assert len(runner_calls) == 6
    assert [call[0][-4:] for call in runner_calls] == [
        ["ls-files", "--stage", "-z", "--"],
        ["-r", "-z", "--full-tree", "HEAD"],
        ["ls-files", "--stage", "-z", "--"],
        ["-r", "-z", "--full-tree", "HEAD"],
        ["ls-files", "--stage", "-z", "--"],
        ["-r", "-z", "--full-tree", "HEAD"],
    ]
    for command, kwargs in runner_calls:
        assert Path(command[0]).is_absolute()
        assert kwargs["timeout"] == task_run_scope._GIT_COMMAND_TIMEOUT_SECONDS
        assert kwargs["env"]["GIT_NO_LAZY_FETCH"] == "1"
        assert kwargs["stdin"] == subprocess.DEVNULL
    assert decision.status == "rejected"
    assert decision.rejected_paths == ("<protected-footprint>",)


def test_worktree_local_absolute_git_executable_fails_before_runner(
    tmp_path, monkeypatch
) -> None:
    _write_git_control_state(tmp_path)
    fake_git = tmp_path / ("git.exe" if os.name == "nt" else "git")
    fake_git.write_bytes(b"fake git executable")
    marker = tmp_path / "runner-marker"
    runner_calls = 0

    def recording_runner(*args, **kwargs):
        nonlocal runner_calls
        runner_calls += 1
        marker.write_text("executed", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(task_run_scope, "_GIT_EXECUTABLE", str(fake_git.absolute()))
    snapshot = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="scope-test-key",
        runner=recording_runner,
    )

    assert snapshot.available is False
    assert snapshot.entries == ()
    assert snapshot.protected_control_digest is None
    assert runner_calls == 0
    assert not marker.exists()


def test_git_executable_case_alias_inside_assigned_root_is_rejected(
    tmp_path,
    monkeypatch,
) -> None:
    root = tmp_path / "assigned-root"
    root.mkdir()
    gitdir = root / "git-control"
    gitdir.mkdir()
    root_observations = task_run_scope._lexical_worktree_root(root)[1]
    gitdir_observations, gitdir_observation = task_run_scope._extend_path_observations(
        root_observations,
        gitdir,
    )
    assert gitdir_observation is not None
    context = task_run_scope._CaseSemanticsContext(
        lambda _directory, _observations: "insensitive"
    )
    alias_root = Path(str(root).swapcase())
    monkeypatch.setattr(
        task_run_scope,
        "_GIT_EXECUTABLE",
        str(alias_root / "bin" / "git"),
    )
    monkeypatch.setattr(
        task_run_scope,
        "_path_kind",
        lambda *_args, **_kwargs: pytest.fail(
            "case-alias containment must reject before filesystem traversal"
        ),
    )

    with pytest.raises(task_run_scope._SnapshotCaptureError):
        task_run_scope._trusted_git_executable(
            root,
            gitdir,
            root_observations=root_observations,
            gitdir_observations=gitdir_observations,
            case_context=context,
        )


@pytest.mark.parametrize("replacement", ("ancestor", "leaf"))
@pytest.mark.parametrize("phase", ("before-runner", "runner-entry"))
def test_git_executable_observation_chain_rejects_replacement(
    tmp_path,
    monkeypatch,
    replacement: str,
    phase: str,
) -> None:
    _write_git_control_state(tmp_path)
    executable_parent = tmp_path.parent / f"{tmp_path.name}-git-bin-{replacement}-{phase}"
    executable_parent.mkdir()
    executable = executable_parent / ("git.exe" if os.name == "nt" else "git")
    executable.write_bytes(b"trusted git executable")
    moved = executable_parent.with_name(f"{executable_parent.name}-moved")
    mutated = False
    runner_calls = 0

    def replace_executable() -> None:
        nonlocal mutated
        if mutated:
            return
        mutated = True
        if replacement == "leaf":
            executable.rename(moved)
            executable.write_bytes(b"replacement git executable")
        else:
            executable_parent.rename(moved)
            executable_parent.mkdir()
            executable.write_bytes(b"replacement git executable")

    original_trusted_executable = task_run_scope._trusted_git_executable
    if phase == "before-runner":
        def replace_after_validation(*args, **kwargs):
            result = original_trusted_executable(*args, **kwargs)
            replace_executable()
            return result

        monkeypatch.setattr(
            task_run_scope,
            "_trusted_git_executable",
            replace_after_validation,
        )

    def recording_runner(*_args, **_kwargs):
        nonlocal runner_calls
        runner_calls += 1
        if phase == "runner-entry":
            replace_executable()
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(task_run_scope, "_GIT_EXECUTABLE", str(executable))
    snapshot = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="executable-observation-key",
        runner=recording_runner,
    )

    assert snapshot.available is False
    assert snapshot.entries == ()
    assert snapshot.protected_control_digest is None
    assert runner_calls == (0 if phase == "before-runner" else 1)


def test_git_executable_content_binding_rejects_in_place_runner_mutation(
    tmp_path,
    monkeypatch,
) -> None:
    _write_git_control_state(tmp_path)
    executable_parent = tmp_path.parent / f"{tmp_path.name}-git-bin-content"
    executable_parent.mkdir()
    executable = executable_parent / ("git.exe" if os.name == "nt" else "git")
    executable.write_bytes(b"trusted git executable")
    runner_calls = 0

    def mutating_runner(*_args, **_kwargs):
        nonlocal runner_calls
        runner_calls += 1
        identity_before = task_run_scope._path_observation(executable)
        executable.write_bytes(b"mutated git executable")
        identity_after = task_run_scope._path_observation(executable)
        assert identity_after == identity_before
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(task_run_scope, "_GIT_EXECUTABLE", str(executable))
    snapshot = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="executable-content-key",
        runner=mutating_runner,
    )

    assert snapshot.available is False
    assert snapshot.entries == ()
    assert snapshot.protected_control_digest is None
    assert runner_calls == 1


def test_multi_link_git_executable_is_accepted_when_content_is_stable(
    tmp_path,
    monkeypatch,
) -> None:
    _write_git_control_state(tmp_path)
    executable_parent = tmp_path.parent / f"{tmp_path.name}-git-bin-hardlink"
    executable_parent.mkdir()
    executable = executable_parent / ("git.exe" if os.name == "nt" else "git")
    executable.write_bytes(b"trusted git executable")
    executable_alias = executable_parent / "git-hardlink-alias"
    try:
        os.link(executable, executable_alias)
    except OSError as exc:
        pytest.skip(f"the test environment cannot create a hardlink: {exc}")
    assert executable.stat().st_nlink > 1
    runner_calls = 0

    def recording_runner(*_args, **_kwargs):
        nonlocal runner_calls
        runner_calls += 1
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(task_run_scope, "_GIT_EXECUTABLE", str(executable))
    snapshot = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="multi-link-executable-key",
        runner=recording_runner,
    )

    assert snapshot.available is True
    assert runner_calls > 0


def test_git_executable_content_binding_rejects_hardlink_alias_mutation(
    tmp_path,
    monkeypatch,
) -> None:
    _write_git_control_state(tmp_path)
    executable_parent = tmp_path.parent / f"{tmp_path.name}-git-bin-alias-mutation"
    executable_parent.mkdir()
    executable = executable_parent / ("git.exe" if os.name == "nt" else "git")
    executable.write_bytes(b"trusted git executable")
    executable_alias = executable_parent / "git-hardlink-alias"
    try:
        os.link(executable, executable_alias)
    except OSError as exc:
        pytest.skip(f"the test environment cannot create a hardlink: {exc}")
    assert executable.stat().st_nlink > 1
    runner_calls = 0

    def mutating_runner(*_args, **_kwargs):
        nonlocal runner_calls
        runner_calls += 1
        executable_alias.write_bytes(b"mutated git executable")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(task_run_scope, "_GIT_EXECUTABLE", str(executable))
    snapshot = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="multi-link-alias-mutation-key",
        runner=mutating_runner,
    )

    assert snapshot.available is False
    assert snapshot.entries == ()
    assert snapshot.protected_control_digest is None
    assert runner_calls == 1


@pytest.mark.skipif(os.name != "nt", reason="Windows .exe mode synthesis regression")
@pytest.mark.parametrize(
    ("path", "descriptor_mode", "path_mode", "expected"),
    (
        pytest.param(
            Path("git.ExE"),
            stat.S_IFREG | 0o666,
            stat.S_IFREG | 0o777,
            True,
            id="exe-complete-forward-delta",
        ),
        pytest.param(
            Path("git.exe"),
            stat.S_IFREG | 0o666,
            stat.S_IFREG | 0o766,
            False,
            id="exe-partial-owner-delta",
        ),
        pytest.param(
            Path("git.exe"),
            stat.S_IFREG | 0o666,
            stat.S_IFREG | 0o677,
            False,
            id="exe-partial-group-other-delta",
        ),
        pytest.param(
            Path("git.exe"),
            stat.S_IFREG | 0o777,
            stat.S_IFREG | 0o666,
            False,
            id="exe-reversed-delta",
        ),
        pytest.param(
            Path("git"),
            stat.S_IFREG | 0o666,
            stat.S_IFREG | 0o777,
            False,
            id="non-exe-complete-delta",
        ),
    ),
)
def test_descriptor_path_execute_bit_normalization_is_exact_for_windows_exe(
    path: Path,
    descriptor_mode: int,
    path_mode: int,
    expected: bool,
) -> None:
    descriptor_observation = ("file", (11, 22, descriptor_mode, 33))
    path_observation = ("file", (11, 22, path_mode, 33))

    assert task_run_scope._descriptor_matches_path_observation(
        descriptor_observation,
        path_observation,
        path=path,
        allow_windows_path_execute_bits=True,
    ) is expected


@pytest.mark.skipif(os.name != "nt", reason="Windows .exe mode synthesis regression")
@pytest.mark.parametrize(
    "path_identity",
    (
        pytest.param((12, 22, stat.S_IFREG | 0o777, 33), id="device"),
        pytest.param((11, 23, stat.S_IFREG | 0o777, 33), id="inode"),
        pytest.param((11, 22, stat.S_IFDIR | 0o777, 33), id="file-type"),
        pytest.param((11, 22, stat.S_IFREG | 0o777, 34), id="attributes"),
    ),
)
def test_descriptor_path_execute_bit_normalization_keeps_identity_strict(
    path_identity: tuple[int, int, int, int],
) -> None:
    descriptor_observation = ("file", (11, 22, stat.S_IFREG | 0o666, 33))

    assert task_run_scope._descriptor_matches_path_observation(
        descriptor_observation,
        ("file", path_identity),
        path=Path("git.exe"),
        allow_windows_path_execute_bits=True,
    ) is False


@pytest.mark.parametrize("link_kind", ("leaf", "ancestor"))
def test_symlinked_git_executable_fails_before_runner(
    tmp_path, monkeypatch, link_kind: str
) -> None:
    _write_git_control_state(tmp_path)
    executable_name = "git.exe" if os.name == "nt" else "git"
    real_parent = tmp_path.parent / f"{tmp_path.name}-real-git-parent"
    real_parent.mkdir()
    real_git = real_parent / executable_name
    real_git.write_bytes(b"real git executable")
    try:
        if link_kind == "leaf":
            candidate = tmp_path.parent / f"{tmp_path.name}-git-link"
            os.symlink(real_git, candidate)
        else:
            linked_parent = tmp_path.parent / f"{tmp_path.name}-git-parent-link"
            os.symlink(real_parent, linked_parent, target_is_directory=True)
            candidate = linked_parent / executable_name
    except (NotImplementedError, OSError):
        pytest.skip("the test environment cannot create a file-system symlink")

    marker = tmp_path / "runner-marker"
    runner_calls = 0

    def recording_runner(*args, **kwargs):
        nonlocal runner_calls
        runner_calls += 1
        marker.write_text("executed", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(task_run_scope, "_GIT_EXECUTABLE", str(candidate.absolute()))
    snapshot = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="scope-test-key",
        runner=recording_runner,
    )

    assert snapshot.available is False
    assert snapshot.entries == ()
    assert snapshot.protected_control_digest is None
    assert runner_calls == 0
    assert not marker.exists()


def test_protected_gitdir_mutation_during_capture_is_unavailable(tmp_path) -> None:
    _write_git_control_state(tmp_path)
    gitdir = tmp_path / "git-control"
    baseline = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="scope-stability-key",
        runner=_layer_runner(index_output=b"", tree_output=b""),
    )
    runner_calls = 0

    def mutating_runner(command, **kwargs):
        nonlocal runner_calls
        runner_calls += 1
        if runner_calls == 1:
            (gitdir / "HEAD").write_text(
                "ref: refs/heads/attacker\n", encoding="utf-8"
            )
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    current = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="scope-stability-key",
        runner=mutating_runner,
    )
    decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)

    assert current.available is False
    assert current.entries == ()
    assert current.protected_control_digest is None
    assert decision.status == "unverifiable"
    assert decision.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert str(gitdir) not in (current.reason or "")
    assert runner_calls == 6


@pytest.mark.parametrize("mutation_kind", ("index", "worktree"))
def test_scope_composite_view_must_be_stable_between_reads(
    tmp_path, mutation_kind: str
) -> None:
    _write_git_control_state(tmp_path)
    changed_path = tmp_path / "apps/demo/src/Changed.tsx"
    index_output = _git_index_record("apps/demo/src/Changed.tsx")
    runner_calls = 0

    def unstable_runner(command, **kwargs):
        nonlocal runner_calls
        runner_calls += 1
        if runner_calls == 3:
            if mutation_kind == "index" and "ls-files" in command:
                return SimpleNamespace(
                    returncode=0, stdout=index_output, stderr=b""
                )
            if mutation_kind == "worktree":
                changed_path.parent.mkdir(parents=True, exist_ok=True)
                changed_path.write_text("changed", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    snapshot = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="scope-stability-key",
        runner=unstable_runner,
    )

    assert snapshot.available is False
    assert snapshot.entries == ()
    assert snapshot.protected_control_digest is None
    assert str(tmp_path) not in (snapshot.reason or "")
    assert runner_calls == 6


def test_tail_worktree_write_during_third_protected_capture_is_unavailable(
    tmp_path, monkeypatch
) -> None:
    _write_git_control_state(tmp_path)
    package_json = tmp_path / "package.json"
    protected_calls = 0
    runner_calls = 0
    original_capture = task_run_scope._capture_protected_control_footprint

    def tail_writing_capture(*args, **kwargs):
        nonlocal protected_calls
        result = original_capture(*args, **kwargs)
        protected_calls += 1
        if protected_calls == 3:
            package_json.write_text("{}", encoding="utf-8")
        return result

    def recording_runner(*args, **kwargs):
        nonlocal runner_calls
        runner_calls += 1
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(
        task_run_scope,
        "_capture_protected_control_footprint",
        tail_writing_capture,
    )
    snapshot = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="tail-stability-key",
        runner=recording_runner,
    )

    assert snapshot.available is False
    assert snapshot.entries == ()
    assert snapshot.protected_control_digest is None
    assert protected_calls == 4
    assert runner_calls == 6
    assert str(package_json) not in (snapshot.reason or "")


def test_trusted_gitdir_replacement_is_rejected_before_next_git_read(
    tmp_path, monkeypatch
) -> None:
    _write_git_control_state(tmp_path)
    trusted_gitdir = tmp_path / "git-control"
    protected_calls = 0
    runner_calls = 0
    original_capture = task_run_scope._capture_protected_control_footprint

    def replace_gitdir() -> None:
        moved = tmp_path.parent / f"{tmp_path.name}-moved-git-control"
        trusted_gitdir.rename(moved)
        trusted_gitdir.mkdir()
        (trusted_gitdir / "HEAD").write_text(
            "ref: refs/heads/main\n", encoding="utf-8"
        )

    def wrapped_capture(*args, **kwargs):
        nonlocal protected_calls
        result = original_capture(*args, **kwargs)
        protected_calls += 1
        if protected_calls == 2:
            replace_gitdir()
        return result

    def recording_runner(*args, **kwargs):
        nonlocal runner_calls
        runner_calls += 1
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(
        task_run_scope,
        "_capture_protected_control_footprint",
        wrapped_capture,
    )
    snapshot = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="gitdir-replacement-key",
        runner=recording_runner,
    )

    assert snapshot.available is False
    assert snapshot.entries == ()
    assert snapshot.protected_control_digest is None
    assert runner_calls == 2
    assert str(tmp_path.parent / f"{tmp_path.name}-moved-git-control") not in (
        snapshot.reason or ""
    )


def test_trusted_gitdir_replacement_at_runner_entry_is_post_checked(
    tmp_path,
) -> None:
    _write_git_control_state(tmp_path)
    trusted_gitdir = tmp_path / "git-control"
    runner_calls = 0

    def replace_gitdir() -> None:
        moved = tmp_path.parent / f"{tmp_path.name}-entry-moved-git-control"
        trusted_gitdir.rename(moved)
        trusted_gitdir.mkdir()
        (trusted_gitdir / "HEAD").write_text(
            "ref: refs/heads/main\n", encoding="utf-8"
        )

    def replacing_runner(*args, **kwargs):
        nonlocal runner_calls
        runner_calls += 1
        if runner_calls == 1:
            replace_gitdir()
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    snapshot = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="gitdir-entry-replacement-key",
        runner=replacing_runner,
    )

    assert snapshot.available is False
    assert snapshot.entries == ()
    assert snapshot.protected_control_digest is None
    assert runner_calls == 1
    assert str(tmp_path.parent / f"{tmp_path.name}-entry-moved-git-control") not in (
        snapshot.reason or ""
    )


def test_replaced_trusted_gitdir_symlink_fails_before_status_runner(
    tmp_path, monkeypatch
) -> None:
    _write_git_control_state(tmp_path, gitdir_name="trusted-gitdir")
    trusted_gitdir = tmp_path / "trusted-gitdir"
    _stub_git_status(monkeypatch, b"")
    baseline = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")
    trusted_gitdir.rename(tmp_path / "trusted-gitdir-before-replacement")
    untrusted_gitdir = tmp_path.parent / f"{tmp_path.name}-untrusted-gitdir"
    untrusted_gitdir.mkdir()
    (untrusted_gitdir / "HEAD").write_text("ref: refs/heads/attacker\n", encoding="utf-8")
    os.symlink(untrusted_gitdir, trusted_gitdir)

    def runner_must_not_be_called(*args, **kwargs):
        pytest.fail("status runner must not execute after trusted gitdir replacement")

    snapshot = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="scope-test-key",
        trusted_git_dir=trusted_gitdir,
        runner=runner_must_not_be_called,
    )

    assert baseline.available is True
    assert snapshot.available is False
    assert snapshot.entries == ()
    assert snapshot.protected_control_digest is None
    assert str(untrusted_gitdir) not in (snapshot.reason or "")


def test_replaced_trusted_gitdir_ancestor_symlink_fails_before_status_runner(
    tmp_path,
) -> None:
    trusted_parent = tmp_path / "trusted-parent"
    trusted_gitdir = trusted_parent / "git-control"
    trusted_gitdir.mkdir(parents=True)
    (trusted_gitdir / "HEAD").write_text(
        "ref: refs/heads/main\n", encoding="utf-8"
    )
    (tmp_path / ".git").write_text(
        f"gitdir: {trusted_gitdir}\n", encoding="utf-8"
    )
    successful_runner = lambda *args, **kwargs: SimpleNamespace(
        returncode=0, stdout=b"", stderr=b""
    )
    baseline = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="scope-test-key",
        runner=successful_runner,
    )

    trusted_parent.rename(tmp_path / "trusted-parent-before-replacement")
    untrusted_parent = tmp_path.parent / f"{tmp_path.name}-untrusted-parent"
    untrusted_gitdir = untrusted_parent / "git-control"
    untrusted_gitdir.mkdir(parents=True)
    (untrusted_gitdir / "HEAD").write_text(
        "ref: refs/heads/attacker\n", encoding="utf-8"
    )
    os.symlink(untrusted_parent, trusted_parent, target_is_directory=True)
    runner_calls = 0

    def recording_runner(*args, **kwargs):
        nonlocal runner_calls
        runner_calls += 1
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    snapshot = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="scope-test-key",
        trusted_git_dir=trusted_gitdir,
        runner=recording_runner,
    )

    assert baseline.available is True
    assert snapshot.available is False
    assert snapshot.entries == ()
    assert snapshot.protected_control_digest is None
    assert runner_calls == 0
    assert str(untrusted_parent) not in (snapshot.reason or "")


@pytest.mark.skipif(os.name != "nt", reason="Windows junction semantics")
def test_replaced_trusted_gitdir_ancestor_junction_fails_before_status_runner(
    tmp_path,
) -> None:
    trusted_parent = tmp_path / "trusted-parent"
    trusted_gitdir = trusted_parent / "git-control"
    trusted_gitdir.mkdir(parents=True)
    (trusted_gitdir / "HEAD").write_text(
        "ref: refs/heads/main\n", encoding="utf-8"
    )
    (tmp_path / ".git").write_text(
        f"gitdir: {trusted_gitdir}\n", encoding="utf-8"
    )
    successful_runner = lambda *args, **kwargs: SimpleNamespace(
        returncode=0, stdout=b"", stderr=b""
    )
    baseline = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="scope-test-key",
        runner=successful_runner,
    )

    trusted_parent.rename(tmp_path / "trusted-parent-before-replacement")
    untrusted_parent = tmp_path.parent / f"{tmp_path.name}-untrusted-parent"
    untrusted_gitdir = untrusted_parent / "git-control"
    untrusted_gitdir.mkdir(parents=True)
    (untrusted_gitdir / "HEAD").write_text(
        "ref: refs/heads/attacker\n", encoding="utf-8"
    )
    _create_windows_junction(trusted_parent, untrusted_parent)
    runner_calls = 0

    def recording_runner(*args, **kwargs):
        nonlocal runner_calls
        runner_calls += 1
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    snapshot = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="scope-test-key",
        trusted_git_dir=trusted_gitdir,
        runner=recording_runner,
    )

    assert baseline.available is True
    assert snapshot.available is False
    assert snapshot.entries == ()
    assert snapshot.protected_control_digest is None
    assert runner_calls == 0
    assert str(untrusted_parent) not in (snapshot.reason or "")


def test_allowed_empty_directory_creation_is_captured_and_passes_scope(
    tmp_path, monkeypatch
) -> None:
    _write_git_control_state(tmp_path)
    parent = tmp_path / "apps/demo/src"
    parent.mkdir(parents=True)
    _stub_git_status(monkeypatch, b"")
    baseline = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")

    empty_directory = parent / "empty-feature"
    empty_directory.mkdir()
    current = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")
    decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)

    entries_by_path = {entry.path: entry for entry in current.entries}
    path = "apps/demo/src/empty-feature"
    assert path in entries_by_path
    assert entries_by_path[path].status == "untracked-present"
    assert len(entries_by_path[path].fingerprint) == 64
    assert decision.status == "passed"
    assert decision.changed_paths == ("apps/demo/src", path)


def test_out_of_scope_empty_directory_creation_is_rejected(
    tmp_path, monkeypatch
) -> None:
    _write_git_control_state(tmp_path)
    parent = tmp_path / "apps/demo-api/generated"
    parent.mkdir(parents=True)
    _stub_git_status(monkeypatch, b"")
    baseline = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")

    empty_directory = parent / "empty-output"
    empty_directory.mkdir()
    current = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")
    decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)

    path = "apps/demo-api/generated/empty-output"
    assert path in {entry.path for entry in current.entries}
    assert decision.status == "rejected"
    assert decision.error_code == "TASK_RUN_SCOPE_VIOLATION"
    assert decision.rejected_paths == ("apps/demo-api/generated", path)


def test_out_of_scope_empty_directory_deletion_is_rejected(
    tmp_path, monkeypatch
) -> None:
    _write_git_control_state(tmp_path)
    empty_directory = tmp_path / "apps/demo-api/generated/empty-output"
    empty_directory.mkdir(parents=True)
    _stub_git_status(monkeypatch, b"")
    baseline = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")

    empty_directory.rmdir()
    current = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")
    decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)

    path = "apps/demo-api/generated/empty-output"
    assert path in {entry.path for entry in baseline.entries}
    assert path not in {entry.path for entry in current.entries}
    assert decision.status == "rejected"
    assert decision.error_code == "TASK_RUN_SCOPE_VIOLATION"
    assert decision.rejected_paths == ("apps/demo-api/generated", path)


def test_capture_fails_closed_for_noncanonical_regular_path(tmp_path, monkeypatch) -> None:
    _write_git_control_state(tmp_path)
    (tmp_path / " leading-space.txt").write_text("unsafe", encoding="utf-8")
    _stub_git_status(monkeypatch, b"")

    snapshot = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")

    assert snapshot.available is False
    assert snapshot.entries == ()
    assert snapshot.protected_control_digest is None
    assert str(tmp_path) not in (snapshot.reason or "")


def test_git_symlink_without_trusted_baseline_is_unavailable(tmp_path, monkeypatch) -> None:
    untrusted_gitdir = tmp_path.parent / f"{tmp_path.name}-untrusted-gitdir"
    untrusted_gitdir.mkdir()
    (untrusted_gitdir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    os.symlink(untrusted_gitdir, tmp_path / ".git")
    _stub_git_status(monkeypatch, b"")

    snapshot = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")

    assert snapshot.available is False


def test_snapshot_metadata_round_trip_does_not_expose_control_key(
    tmp_path, monkeypatch
) -> None:
    _write_git_control_state(tmp_path)
    source = tmp_path / "apps/demo/src/App.tsx"
    source.parent.mkdir(parents=True)
    source.write_text("export default function App() { return null; }", encoding="utf-8")
    _stub_git_layers(
        monkeypatch,
        index_output=_git_index_record("apps/demo/src/App.tsx"),
    )

    snapshot = capture_worktree_scope_snapshot(
        tmp_path, control_key="this-control-key-must-never-persist"
    )
    metadata = snapshot.to_metadata(include_internal=True)
    restored = scope_snapshot_from_metadata(metadata)

    assert restored == snapshot
    assert "this-control-key-must-never-persist" not in str(metadata)
    assert set(metadata) == {
        "schema_version",
        "available",
        "reason",
        "entries",
        "protected_control_digest",
        "protected_categories",
        "protected_entry_count",
    }


def test_resolved_gitdir_content_change_is_redacted_protected_violation(
    tmp_path, monkeypatch
) -> None:
    gitdir = tmp_path / "private-resolved-gitdir"
    gitdir.mkdir()
    head = gitdir / "HEAD"
    head.write_text("ref: refs/heads/main\n", encoding="utf-8")
    (tmp_path / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
    _stub_git_status(monkeypatch, b"")

    control_key = "resolved-gitdir-control-key"
    baseline = capture_worktree_scope_snapshot(tmp_path, control_key=control_key)
    head.write_text("ref: refs/heads/devv\n", encoding="utf-8")
    current = capture_worktree_scope_snapshot(tmp_path, control_key=control_key)
    decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)

    assert baseline.protected_categories == current.protected_categories
    assert baseline.protected_entry_count == current.protected_entry_count
    assert decision.status == "rejected"
    assert decision.error_code == "TASK_RUN_SCOPE_VIOLATION"
    assert decision.rejected_paths == ("<protected-footprint>",)
    exposed = f"{baseline.to_metadata()} {current.to_metadata()} {decision}"
    assert str(gitdir) not in exposed
    assert control_key not in exposed


def test_git_pointer_target_change_is_redacted_protected_violation(
    tmp_path, monkeypatch
) -> None:
    gitdir_a = tmp_path / "private-gitdir-a"
    gitdir_b = tmp_path / "private-gitdir-b"
    for gitdir in (gitdir_a, gitdir_b):
        gitdir.mkdir()
        (gitdir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    git_pointer = tmp_path / ".git"
    git_pointer.write_text(f"gitdir: {gitdir_a}\n", encoding="utf-8")
    _stub_git_status(monkeypatch, b"")

    control_key = "git-pointer-control-key"
    baseline = capture_worktree_scope_snapshot(tmp_path, control_key=control_key)
    assert "private-gitdir-b/HEAD" in {entry.path for entry in baseline.entries}
    git_pointer.write_text(f"gitdir: {gitdir_b}\n", encoding="utf-8")
    current = capture_worktree_scope_snapshot(
        tmp_path,
        control_key=control_key,
        trusted_git_dir=gitdir_a,
    )
    decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)

    assert "private-gitdir-b/HEAD" not in {entry.path for entry in current.entries}
    assert baseline.protected_categories == current.protected_categories
    assert baseline.protected_entry_count == current.protected_entry_count
    assert decision.status == "rejected"
    assert decision.error_code == "TASK_RUN_SCOPE_VIOLATION"
    assert decision.rejected_paths == ("<protected-footprint>",)
    exposed = f"{baseline.to_metadata()} {current.to_metadata()} {decision}"
    assert str(gitdir_a) not in exposed
    assert str(gitdir_b) not in exposed
    assert control_key not in exposed


@pytest.mark.skipif(os.name != "nt", reason="Windows pointer path semantics")
def test_case_variant_pointer_transition_hides_former_gitdir_entries(
    tmp_path, monkeypatch
) -> None:
    gitdir_a = tmp_path / "private-gitdir-a"
    gitdir_b = tmp_path / "PRIVATE-GITDIR-B"
    for gitdir in (gitdir_a, gitdir_b):
        gitdir.mkdir()
        (gitdir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    git_pointer = tmp_path / ".git"
    git_pointer.write_text("gitdir: private-gitdir-a\n", encoding="utf-8")
    _stub_git_status(monkeypatch, b"")
    control_key = "case-variant-pointer-control-key"
    baseline = capture_worktree_scope_snapshot(tmp_path, control_key=control_key)

    git_pointer.write_text("gitdir: private-gitdir-b\n", encoding="utf-8")
    current = capture_worktree_scope_snapshot(
        tmp_path,
        control_key=control_key,
        trusted_git_dir=gitdir_a,
    )
    decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)

    assert "PRIVATE-GITDIR-B/HEAD" in {entry.path for entry in baseline.entries}
    assert "PRIVATE-GITDIR-B/HEAD" not in {entry.path for entry in current.entries}
    assert decision.status == "rejected"
    assert decision.rejected_paths == ("<protected-footprint>",)
    safe_evidence = f"{baseline.to_metadata()} {current.to_metadata()} {decision}"
    assert "PRIVATE-GITDIR-B" not in safe_evidence
    assert "private-gitdir-b" not in safe_evidence


def test_newly_protected_deletion_filter_hides_case_alias_without_binding(
) -> None:
    protected_entry = ScopeEntry(
        path="PRIVATE-GITDIR-B/HEAD",
        status="tracked-present",
        fingerprint="d" * 64,
    )
    baseline = _snapshot(protected_entry)
    current = ScopeSnapshot(
        schema_version=SCOPE_SNAPSHOT_SCHEMA_VERSION,
        available=True,
        reason=None,
        entries=(),
        protected_control_digest="b" * 64,
        _transitioned_protected_paths=("private-gitdir-b",),
    )

    decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)

    assert decision.status == "rejected"
    assert decision.changed_paths == ()
    assert decision.rejected_paths == ("<protected-footprint>",)
    assert "PRIVATE-GITDIR-B" not in str(decision)


def test_pointer_boundary_transition_does_not_hide_unrelated_regular_delta(
    tmp_path, monkeypatch
) -> None:
    gitdir_a = tmp_path / "private-gitdir-a"
    gitdir_b = tmp_path / "private-gitdir-b"
    for gitdir in (gitdir_a, gitdir_b):
        gitdir.mkdir()
        (gitdir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    git_pointer = tmp_path / ".git"
    git_pointer.write_text(f"gitdir: {gitdir_a}\n", encoding="utf-8")
    _stub_git_status(monkeypatch, b"")

    baseline = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")
    git_pointer.write_text(f"gitdir: {gitdir_b}\n", encoding="utf-8")
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    current = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="scope-test-key",
        trusted_git_dir=gitdir_a,
    )
    decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)

    assert decision.status == "rejected"
    assert decision.error_code == "TASK_RUN_SCOPE_VIOLATION"
    assert decision.rejected_paths == ("package.json",)


def test_nested_node_modules_content_change_is_protected_violation(
    tmp_path, monkeypatch
) -> None:
    _write_git_control_state(tmp_path)
    protected_file = tmp_path / "apps/demo/node_modules/package/index.js"
    protected_file.parent.mkdir(parents=True)
    protected_file.write_text("module.exports=1;", encoding="utf-8")
    _stub_git_status(monkeypatch, b"")

    baseline = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")
    protected_file.write_text("module.exports=2;", encoding="utf-8")
    current = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")
    decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)

    assert decision.status == "rejected"
    assert decision.error_code == "TASK_RUN_SCOPE_VIOLATION"
    assert decision.rejected_paths == ("<protected-footprint>",)


def test_nested_secrets_content_change_is_protected_violation(
    tmp_path, monkeypatch
) -> None:
    _write_git_control_state(tmp_path)
    protected_file = tmp_path / "apps/demo/secrets/runtime/token.txt"
    protected_file.parent.mkdir(parents=True)
    protected_file.write_text("token-one", encoding="utf-8")
    _stub_git_status(monkeypatch, b"")

    baseline = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")
    protected_file.write_text("token-two", encoding="utf-8")
    current = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")
    decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)

    assert decision.status == "rejected"
    assert decision.error_code == "TASK_RUN_SCOPE_VIOLATION"
    assert decision.rejected_paths == ("<protected-footprint>",)


def test_ignored_regular_file_outside_frontend_scope_is_rejected(
    tmp_path, monkeypatch
) -> None:
    _write_git_control_state(tmp_path)
    _stub_git_status(monkeypatch, b"")
    baseline = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")

    ignored_file = tmp_path / "apps/demo/dist/unsafe.js"
    ignored_file.parent.mkdir(parents=True)
    ignored_file.write_text("export const unsafe = true;", encoding="utf-8")
    current = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")
    decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)

    assert current.available is True
    assert decision.status == "rejected"
    assert decision.error_code == "TASK_RUN_SCOPE_VIOLATION"
    assert decision.rejected_paths == ("apps/demo/dist/unsafe.js",)


@pytest.mark.parametrize(
    "link_case",
    ("external-file", "external-directory", "dangling", "inside-root-file"),
)
def test_ordinary_symlink_makes_scope_capture_unavailable(
    tmp_path, monkeypatch, link_case: str
) -> None:
    _write_git_control_state(tmp_path)
    _stub_git_status(monkeypatch, b"")

    if link_case == "external-file":
        target = tmp_path.parent / f"{tmp_path.name}-external-target.txt"
        target.write_text("external target content", encoding="utf-8")
    elif link_case == "external-directory":
        target = tmp_path.parent / f"{tmp_path.name}-external-target-dir"
        target.mkdir()
        (target / "outside.txt").write_text("outside", encoding="utf-8")
    elif link_case == "dangling":
        target = tmp_path.parent / f"{tmp_path.name}-missing-target"
    else:
        target = tmp_path / "inside-target.txt"
        target.write_text("inside target content", encoding="utf-8")

    link = tmp_path / "apps/demo/dist/unsafe-link"
    link.parent.mkdir(parents=True)
    try:
        os.symlink(target, link, target_is_directory=link_case == "external-directory")
    except OSError as exc:
        pytest.skip(f"the test environment cannot create a file-system symlink: {exc}")

    baseline = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")
    if link_case == "external-file":
        target.write_text("changed external target content", encoding="utf-8")
    elif link_case == "external-directory":
        (target / "outside.txt").write_text("changed outside", encoding="utf-8")
    current = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")
    decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)

    for snapshot in (baseline, current):
        assert snapshot.available is False
        assert snapshot.reason == "scope_capture_unavailable"
        assert snapshot.entries == ()
        assert snapshot.protected_control_digest is None
        assert str(target) not in str(snapshot.reason)
        assert str(target) not in str(snapshot.to_metadata(include_internal=True))
    assert decision.status == "unverifiable"
    assert decision.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
    assert str(target) not in str(decision)


def test_capture_rejects_ordinary_hardlink_without_reading_alias_inode(
    tmp_path, monkeypatch
) -> None:
    root = tmp_path / "assigned-root"
    root.mkdir()
    _write_git_control_state(root)
    ordinary_file = root / "ordinary.txt"
    ordinary_file.write_text("ordinary", encoding="utf-8")
    external_file = tmp_path.parent / f"{tmp_path.name}-external-ordinary.txt"
    try:
        os.link(ordinary_file, external_file)
    except OSError as exc:
        pytest.skip(f"the test environment cannot create a hardlink: {exc}")

    _stub_git_status(monkeypatch, b"")
    external_identity = task_run_scope._filesystem_identity(external_file.stat())
    original_read = task_run_scope.os.read
    external_reads = 0

    def track_external_read(descriptor: int, size: int) -> bytes:
        nonlocal external_reads
        if (
            task_run_scope._filesystem_identity(os.fstat(descriptor))
            == external_identity
        ):
            external_reads += 1
        return original_read(descriptor, size)

    monkeypatch.setattr(task_run_scope.os, "read", track_external_read)

    snapshot = capture_worktree_scope_snapshot(root, control_key="scope-test-key")

    assert (snapshot.available, external_reads) == (False, 0)
    assert snapshot.reason == "scope_capture_unavailable"
    assert snapshot.entries == ()
    assert snapshot.protected_control_digest is None
    assert str(external_file) not in str(snapshot.to_metadata(include_internal=True))


def test_capture_rejects_hardlink_created_after_open_before_first_read(
    tmp_path, monkeypatch
) -> None:
    root = tmp_path / "assigned-root"
    root.mkdir()
    _write_git_control_state(root)
    ordinary_file = root / "ordinary.txt"
    ordinary_file.write_text("ordinary", encoding="utf-8")
    external_file = tmp_path.parent / f"{tmp_path.name}-external-race.txt"
    _stub_git_status(monkeypatch, b"")

    original_open = task_run_scope.os.open
    original_read = task_run_scope.os.read
    ordinary_identity = task_run_scope._filesystem_identity(ordinary_file.stat())
    alias_created = False
    external_reads = 0

    def open_then_create_alias(path, flags, *args, **kwargs):
        nonlocal alias_created
        descriptor = original_open(path, flags, *args, **kwargs)
        if Path(path) == ordinary_file and not alias_created:
            try:
                os.link(ordinary_file, external_file)
            except OSError as exc:
                os.close(descriptor)
                pytest.skip(
                    f"the test environment cannot create a hardlink: {exc}"
                )
            alias_created = True
        return descriptor

    def track_ordinary_read(descriptor: int, size: int) -> bytes:
        nonlocal external_reads
        if (
            task_run_scope._filesystem_identity(os.fstat(descriptor))
            == ordinary_identity
        ):
            external_reads += 1
        return original_read(descriptor, size)

    monkeypatch.setattr(task_run_scope.os, "open", open_then_create_alias)
    monkeypatch.setattr(task_run_scope.os, "read", track_ordinary_read)

    snapshot = capture_worktree_scope_snapshot(root, control_key="scope-test-key")

    assert alias_created is True
    assert (snapshot.available, external_reads) == (False, 0)
    assert snapshot.reason == "scope_capture_unavailable"
    assert snapshot.entries == ()
    assert snapshot.protected_control_digest is None
    assert str(external_file) not in str(snapshot.to_metadata(include_internal=True))


def test_capture_rejects_assigned_root_replaced_by_external_symlink(
    tmp_path, monkeypatch
) -> None:
    assigned_root = tmp_path / "assigned-root"
    assigned_root.mkdir()
    original_root = tmp_path / "assigned-root-original"
    external_root = tmp_path / "external-root"
    external_root.mkdir()
    trusted_gitdir = tmp_path / "trusted-gitdir"
    trusted_gitdir.mkdir()
    (trusted_gitdir / "HEAD").write_text(
        "ref: refs/heads/main\n", encoding="utf-8"
    )
    for root in (assigned_root, external_root):
        (root / ".git").write_text("gitdir: ../trusted-gitdir\n", encoding="utf-8")
        source = root / "apps/demo/src/App.tsx"
        source.parent.mkdir(parents=True)
        source.write_text("export const App = true;\n", encoding="utf-8")
    _stub_git_status(monkeypatch, b"")
    control_key = "assigned-root-control-key"
    baseline = capture_worktree_scope_snapshot(
        assigned_root,
        control_key=control_key,
    )

    assigned_root.rename(original_root)
    try:
        os.symlink(external_root, assigned_root, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"the test environment cannot create a file-system symlink: {exc}")

    current = capture_worktree_scope_snapshot(
        assigned_root,
        control_key=control_key,
        trusted_git_dir=baseline._trusted_git_dir,
    )
    decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)

    assert baseline.available is True
    assert current.available is False
    assert current.reason == "scope_capture_unavailable"
    assert current.entries == ()
    assert current.protected_control_digest is None
    assert decision.status == "unverifiable"
    exposed = f"{current.to_metadata(include_internal=True)} {decision}"
    assert str(original_root) not in exposed
    assert str(external_root) not in exposed
    assert str(trusted_gitdir) not in exposed


def test_capture_rejects_worktree_with_symlink_ancestor(tmp_path, monkeypatch) -> None:
    physical_parent = tmp_path / "physical-parent"
    physical_root = physical_parent / "assigned-root"
    physical_root.mkdir(parents=True)
    _write_git_control_state(physical_root)
    linked_parent = tmp_path / "linked-parent"
    try:
        os.symlink(physical_parent, linked_parent, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"the test environment cannot create a file-system symlink: {exc}")
    _stub_git_status(monkeypatch, b"")

    snapshot = capture_worktree_scope_snapshot(
        linked_parent / "assigned-root",
        control_key="scope-test-key",
    )

    assert snapshot.available is False
    assert snapshot.reason == "scope_capture_unavailable"
    exposed = str(snapshot.to_metadata(include_internal=True))
    assert str(physical_parent) not in exposed
    assert str(linked_parent) not in exposed


def test_capture_rejects_relative_worktree_path(tmp_path, monkeypatch) -> None:
    root = tmp_path / "relative-root"
    root.mkdir()
    _write_git_control_state(root)
    _stub_git_status(monkeypatch, b"")
    monkeypatch.chdir(tmp_path)

    snapshot = capture_worktree_scope_snapshot(
        Path("relative-root"),
        control_key="scope-test-key",
    )

    assert snapshot.available is False
    assert snapshot.reason == "scope_capture_unavailable"
    assert snapshot.entries == ()
    assert snapshot.protected_control_digest is None


def test_capture_rechecks_root_before_ordinary_file_fingerprint(
    tmp_path, monkeypatch
) -> None:
    root = tmp_path / "assigned-root"
    root.mkdir()
    original_root = tmp_path / "assigned-root-original"
    external_root = tmp_path / "external-root"
    external_root.mkdir()
    _write_git_control_state(root)
    local_file = root / "ordinary.txt"
    local_file.write_text("local", encoding="utf-8")
    external_file = external_root / "ordinary.txt"
    external_file.write_text("external", encoding="utf-8")
    external_identity = task_run_scope._filesystem_identity(external_file.stat())
    _stub_git_status(monkeypatch, b"")
    original_fingerprint = task_run_scope._fingerprint_worktree_path
    original_read = task_run_scope.os.read
    external_reads = 0

    def swap_root() -> None:
        root.rename(original_root)
        os.symlink(external_root, root, target_is_directory=True)

    def restore_root() -> None:
        root.unlink()
        original_root.rename(root)

    def fingerprint_during_root_swap(root_path, path, *args, **kwargs):
        if path != "ordinary.txt":
            return original_fingerprint(root_path, path, *args, **kwargs)
        swap_root()
        try:
            return original_fingerprint(root_path, path, *args, **kwargs)
        finally:
            restore_root()

    def track_external_read(descriptor: int, size: int) -> bytes:
        nonlocal external_reads
        if task_run_scope._filesystem_identity(os.fstat(descriptor)) == external_identity:
            external_reads += 1
        return original_read(descriptor, size)

    monkeypatch.setattr(
        task_run_scope,
        "_fingerprint_worktree_path",
        fingerprint_during_root_swap,
    )
    monkeypatch.setattr(task_run_scope.os, "read", track_external_read)

    snapshot = capture_worktree_scope_snapshot(root, control_key="scope-test-key")

    assert external_reads == 0
    assert snapshot.available is False
    assert snapshot.reason == "scope_capture_unavailable"
    assert str(external_root) not in str(snapshot.to_metadata(include_internal=True))


def test_capture_rechecks_assigned_root_parent_before_ordinary_fingerprint(
    tmp_path, monkeypatch
) -> None:
    assigned_parent = tmp_path / "assigned-parent"
    root = assigned_parent / "assigned-root"
    root.mkdir(parents=True)
    original_parent = tmp_path / "assigned-parent-original"
    external_parent = tmp_path / "external-parent"
    external_root = external_parent / "assigned-root"
    external_root.mkdir(parents=True)
    symlink_probe = tmp_path / "directory-symlink-probe"
    try:
        os.symlink(external_parent, symlink_probe, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"the test environment cannot create a file-system symlink: {exc}")
    symlink_probe.unlink()

    _write_git_control_state(root)
    local_file = root / "ordinary.txt"
    local_file.write_text("local", encoding="utf-8")
    external_file = external_root / "ordinary.txt"
    external_file.write_text("external", encoding="utf-8")
    external_identity = task_run_scope._filesystem_identity(external_file.stat())
    _stub_git_status(monkeypatch, b"")
    original_fingerprint = task_run_scope._fingerprint_worktree_path
    original_read = task_run_scope.os.read
    external_reads = 0

    def fingerprint_during_parent_swap(root_path, path, *args, **kwargs):
        if path != "ordinary.txt":
            return original_fingerprint(root_path, path, *args, **kwargs)
        assigned_parent.rename(original_parent)
        os.symlink(external_parent, assigned_parent, target_is_directory=True)
        try:
            return original_fingerprint(root_path, path, *args, **kwargs)
        finally:
            assigned_parent.unlink()
            original_parent.rename(assigned_parent)

    def track_external_read(descriptor: int, size: int) -> bytes:
        nonlocal external_reads
        if task_run_scope._filesystem_identity(os.fstat(descriptor)) == external_identity:
            external_reads += 1
        return original_read(descriptor, size)

    monkeypatch.setattr(
        task_run_scope,
        "_fingerprint_worktree_path",
        fingerprint_during_parent_swap,
    )
    monkeypatch.setattr(task_run_scope.os, "read", track_external_read)

    snapshot = capture_worktree_scope_snapshot(root, control_key="scope-test-key")

    assert external_reads == 0
    assert snapshot.available is False
    assert snapshot.reason == "scope_capture_unavailable"
    assert snapshot.entries == ()
    assert snapshot.protected_control_digest is None
    exposed = str(snapshot.to_metadata(include_internal=True))
    assert str(external_parent) not in exposed
    assert str(external_file) not in exposed


@pytest.mark.parametrize("entry_case", ("absent", "directory"))
def test_capture_rechecks_root_before_ordinary_early_return(
    tmp_path, monkeypatch, entry_case: str
) -> None:
    root = tmp_path / "assigned-root"
    root.mkdir()
    original_root = tmp_path / "assigned-root-original"
    external_root = tmp_path / "external-root"
    external_root.mkdir()
    _write_git_control_state(root)
    if entry_case == "directory":
        (root / "empty-directory").mkdir()
        (external_root / "empty-directory").mkdir()
        target_path = "empty-directory"
        _stub_git_status(monkeypatch, b"")
    else:
        target_path = "missing.txt"
        _stub_git_layers(
            monkeypatch,
            index_output=_git_index_record(target_path),
            tree_output=_git_tree_record(target_path),
        )
    original_fingerprint = task_run_scope._fingerprint_worktree_path
    accepted_early_returns = 0

    def fingerprint_during_root_swap(root_path, path, *args, **kwargs):
        nonlocal accepted_early_returns
        if path != target_path:
            return original_fingerprint(root_path, path, *args, **kwargs)
        root.rename(original_root)
        os.symlink(external_root, root, target_is_directory=True)
        try:
            result = original_fingerprint(root_path, path, *args, **kwargs)
            accepted_early_returns += 1
            return result
        finally:
            root.unlink()
            original_root.rename(root)

    monkeypatch.setattr(
        task_run_scope,
        "_fingerprint_worktree_path",
        fingerprint_during_root_swap,
    )

    snapshot = capture_worktree_scope_snapshot(root, control_key="scope-test-key")

    assert accepted_early_returns == 0
    assert snapshot.available is False
    assert snapshot.reason == "scope_capture_unavailable"


def test_protected_file_swap_does_not_read_external_content(
    tmp_path, monkeypatch
) -> None:
    root = tmp_path / "assigned-root"
    root.mkdir()
    _write_git_control_state(root)
    protected_file = root / ".env.local"
    protected_file.write_text("LOCAL_TOKEN=local", encoding="utf-8")
    protected_backup = root / ".env.local-original"
    external_file = tmp_path / "external-secret.txt"
    external_file.write_text("EXTERNAL_TOKEN=external", encoding="utf-8")
    external_identity = task_run_scope._filesystem_identity(external_file.stat())
    _stub_git_status(monkeypatch, b"")
    original_read_bytes = Path.read_bytes
    original_open = task_run_scope.os.open
    original_read = task_run_scope.os.read
    external_reads = 0

    def swap_file() -> None:
        protected_file.rename(protected_backup)
        os.symlink(external_file, protected_file)

    def restore_file() -> None:
        protected_file.unlink()
        protected_backup.rename(protected_file)

    def read_bytes_during_swap(path: Path) -> bytes:
        nonlocal external_reads
        if path != protected_file:
            return original_read_bytes(path)
        swap_file()
        try:
            content = original_read_bytes(path)
            external_reads += 1
            return content
        finally:
            restore_file()

    def open_during_swap(path, flags, *args, **kwargs):
        if Path(path) != protected_file:
            return original_open(path, flags, *args, **kwargs)
        swap_file()
        try:
            return original_open(path, flags, *args, **kwargs)
        finally:
            restore_file()

    def track_external_read(descriptor: int, size: int) -> bytes:
        nonlocal external_reads
        if task_run_scope._filesystem_identity(os.fstat(descriptor)) == external_identity:
            external_reads += 1
        return original_read(descriptor, size)

    monkeypatch.setattr(Path, "read_bytes", read_bytes_during_swap)
    monkeypatch.setattr(task_run_scope.os, "open", open_during_swap)
    monkeypatch.setattr(task_run_scope.os, "read", track_external_read)

    snapshot = capture_worktree_scope_snapshot(root, control_key="scope-test-key")

    assert external_reads == 0
    assert snapshot.available is False
    exposed = str(snapshot.to_metadata(include_internal=True))
    assert str(external_file) not in exposed
    assert "EXTERNAL_TOKEN" not in exposed


def test_protected_root_scan_swap_back_does_not_read_external_content(
    tmp_path, monkeypatch
) -> None:
    root = tmp_path / "assigned-root"
    root.mkdir()
    original_root = tmp_path / "assigned-root-original"
    external_root = tmp_path / "external-root"
    external_secret = external_root / "secrets/token.txt"
    external_secret.parent.mkdir(parents=True)
    external_secret.write_text("external-secret", encoding="utf-8")
    external_identity = task_run_scope._filesystem_identity(external_secret.stat())
    trusted_gitdir = tmp_path / "trusted-gitdir"
    trusted_gitdir.mkdir()
    (trusted_gitdir / "HEAD").write_text(
        "ref: refs/heads/main\n", encoding="utf-8"
    )
    (root / ".git").write_text("gitdir: ../trusted-gitdir\n", encoding="utf-8")
    local_secret = root / "secrets/token.txt"
    local_secret.parent.mkdir()
    local_secret.write_text("local-secret", encoding="utf-8")
    _stub_git_status(monkeypatch, b"")
    original_collect = task_run_scope._collect_worktree_protected_records
    original_scandir = task_run_scope.os.scandir
    original_read_bytes = Path.read_bytes
    original_read = task_run_scope.os.read
    inside_protected_walk = False
    root_swapped = False
    external_reads = 0

    def restore_root() -> None:
        nonlocal root_swapped
        if root_swapped:
            root.unlink()
            original_root.rename(root)
            root_swapped = False

    def collect_with_root_restore(*args, **kwargs):
        nonlocal inside_protected_walk
        inside_protected_walk = True
        try:
            return original_collect(*args, **kwargs)
        finally:
            restore_root()
            inside_protected_walk = False

    def scandir_during_root_swap(path):
        nonlocal root_swapped
        if inside_protected_walk and Path(path) == root and not root_swapped:
            root.rename(original_root)
            os.symlink(external_root, root, target_is_directory=True)
            root_swapped = True
        return original_scandir(path)

    def read_bytes_while_swapped(path: Path) -> bytes:
        nonlocal external_reads
        content = original_read_bytes(path)
        if root_swapped and path == root / "secrets/token.txt":
            external_reads += 1
        return content

    def track_external_read(descriptor: int, size: int) -> bytes:
        nonlocal external_reads
        if task_run_scope._filesystem_identity(os.fstat(descriptor)) == external_identity:
            external_reads += 1
        return original_read(descriptor, size)

    monkeypatch.setattr(
        task_run_scope,
        "_collect_worktree_protected_records",
        collect_with_root_restore,
    )
    monkeypatch.setattr(task_run_scope.os, "scandir", scandir_during_root_swap)
    monkeypatch.setattr(Path, "read_bytes", read_bytes_while_swapped)
    monkeypatch.setattr(task_run_scope.os, "read", track_external_read)

    snapshot = capture_worktree_scope_snapshot(root, control_key="scope-test-key")

    assert external_reads == 0
    assert snapshot.available is False
    exposed = str(snapshot.to_metadata(include_internal=True))
    assert str(external_root) not in exposed
    assert "external-secret" not in exposed


def test_git_directory_swap_does_not_follow_external_gitdir(
    tmp_path, monkeypatch
) -> None:
    root = tmp_path / "assigned-root"
    root.mkdir()
    git_control = root / ".git"
    git_control.mkdir()
    local_head = git_control / "HEAD"
    local_head.write_text("ref: refs/heads/main\n", encoding="utf-8")
    git_backup = root / ".git-original"
    external_gitdir = tmp_path / "external-gitdir"
    external_gitdir.mkdir()
    external_head = external_gitdir / "HEAD"
    external_head.write_text("ref: refs/heads/main\n", encoding="utf-8")
    external_identity = task_run_scope._filesystem_identity(external_head.stat())
    _stub_git_status(monkeypatch, b"")
    original_capture = task_run_scope._capture_protected_control_footprint
    original_lstat = Path.lstat
    original_read_bytes = Path.read_bytes
    original_read = task_run_scope.os.read
    inside_protected_capture = False
    git_swapped = False
    external_reads = 0

    def restore_git_control() -> None:
        nonlocal git_swapped
        if git_swapped:
            git_control.unlink()
            git_backup.rename(git_control)
            git_swapped = False

    def capture_with_git_restore(*args, **kwargs):
        nonlocal inside_protected_capture
        inside_protected_capture = True
        try:
            return original_capture(*args, **kwargs)
        finally:
            restore_git_control()
            inside_protected_capture = False

    def lstat_then_swap_git(path: Path):
        nonlocal git_swapped
        path_stat = original_lstat(path)
        if inside_protected_capture and path == git_control and not git_swapped:
            git_control.rename(git_backup)
            os.symlink(external_gitdir, git_control, target_is_directory=True)
            git_swapped = True
        return path_stat

    def track_external_read_bytes(path: Path) -> bytes:
        nonlocal external_reads
        content = original_read_bytes(path)
        if path == external_head:
            external_reads += 1
        return content

    def track_external_read(descriptor: int, size: int) -> bytes:
        nonlocal external_reads
        if task_run_scope._filesystem_identity(os.fstat(descriptor)) == external_identity:
            external_reads += 1
        return original_read(descriptor, size)

    monkeypatch.setattr(
        task_run_scope,
        "_capture_protected_control_footprint",
        capture_with_git_restore,
    )
    monkeypatch.setattr(Path, "lstat", lstat_then_swap_git)
    monkeypatch.setattr(Path, "read_bytes", track_external_read_bytes)
    monkeypatch.setattr(task_run_scope.os, "read", track_external_read)

    snapshot = capture_worktree_scope_snapshot(root, control_key="scope-test-key")

    assert external_reads == 0
    assert snapshot.available is False
    exposed = str(snapshot.to_metadata(include_internal=True))
    assert str(external_gitdir) not in exposed


@pytest.mark.skipif(os.name != "nt", reason="Windows reparse-point semantics")
def test_internal_fingerprint_rechecks_simulated_root_reparse(
    tmp_path, monkeypatch
) -> None:
    root = tmp_path / "assigned-root"
    root.mkdir()
    _write_git_control_state(root)
    (root / "ordinary.txt").write_text("ordinary", encoding="utf-8")
    _stub_git_status(monkeypatch, b"")
    original_fingerprint = task_run_scope._fingerprint_worktree_path
    original_lstat = Path.lstat
    simulate_reparse = False
    accepted_fingerprints = 0

    def lstat_with_simulated_root_reparse(path: Path):
        path_stat = original_lstat(path)
        if simulate_reparse and path == root:
            return SimpleNamespace(
                st_dev=path_stat.st_dev,
                st_ino=path_stat.st_ino,
                st_mode=path_stat.st_mode,
                st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT,
            )
        return path_stat

    def fingerprint_with_simulated_reparse(root_path, path, *args, **kwargs):
        nonlocal simulate_reparse, accepted_fingerprints
        if path != "ordinary.txt":
            return original_fingerprint(root_path, path, *args, **kwargs)
        simulate_reparse = True
        try:
            result = original_fingerprint(root_path, path, *args, **kwargs)
            accepted_fingerprints += 1
            return result
        finally:
            simulate_reparse = False

    monkeypatch.setattr(Path, "lstat", lstat_with_simulated_root_reparse)
    monkeypatch.setattr(
        task_run_scope,
        "_fingerprint_worktree_path",
        fingerprint_with_simulated_reparse,
    )

    snapshot = capture_worktree_scope_snapshot(root, control_key="scope-test-key")

    assert accepted_fingerprints == 0
    assert snapshot.available is False


def test_fingerprint_rejects_ordinary_symlink_without_reading_target(
    tmp_path, monkeypatch
) -> None:
    target = tmp_path.parent / f"{tmp_path.name}-fingerprint-target.txt"
    target.write_text("target", encoding="utf-8")
    link = tmp_path / "ordinary-link"
    tmp_path.mkdir(exist_ok=True)
    try:
        os.symlink(target, link)
    except OSError as exc:
        pytest.skip(f"the test environment cannot create a file-system symlink: {exc}")

    monkeypatch.setattr(
        task_run_scope.os,
        "readlink",
        lambda _path: pytest.fail("ordinary symlink target must not be read"),
    )
    with pytest.raises(task_run_scope._SnapshotCaptureError):
        task_run_scope._fingerprint_worktree_path(
            tmp_path, "ordinary-link", absent_allowed=False
        )


def test_fingerprint_rejects_symlink_ancestor_without_reading_external_file(
    tmp_path, monkeypatch
) -> None:
    external_directory = tmp_path.parent / f"{tmp_path.name}-external-directory"
    external_directory.mkdir()
    (external_directory / "outside.txt").write_text("outside", encoding="utf-8")
    link = tmp_path / "ordinary-link"
    try:
        os.symlink(external_directory, link, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"the test environment cannot create a file-system symlink: {exc}")

    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda _path: pytest.fail("external file must not be read through a symlink"),
    )
    with pytest.raises(task_run_scope._SnapshotCaptureError):
        task_run_scope._fingerprint_worktree_path(
            tmp_path, "ordinary-link/outside.txt", absent_allowed=False
        )


def test_fingerprint_fails_closed_when_file_becomes_symlink_before_open(
    tmp_path, monkeypatch
) -> None:
    candidate = tmp_path / "ordinary.txt"
    candidate.write_text("ordinary", encoding="utf-8")
    external_file = tmp_path.parent / f"{tmp_path.name}-external-file.txt"
    external_file.write_text("external", encoding="utf-8")
    original_read_bytes = Path.read_bytes
    original_open = task_run_scope.os.open
    replaced = False

    def replace_candidate() -> None:
        nonlocal replaced
        if replaced:
            return
        candidate.unlink()
        os.symlink(external_file, candidate)
        replaced = True

    def read_bytes_after_replacement(path: Path) -> bytes:
        if path == candidate:
            replace_candidate()
        return original_read_bytes(path)

    def open_after_replacement(path, flags, *args, **kwargs):
        if Path(path) == candidate:
            replace_candidate()
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", read_bytes_after_replacement)
    monkeypatch.setattr(task_run_scope.os, "open", open_after_replacement)
    monkeypatch.setattr(
        task_run_scope.os,
        "read",
        lambda *_args, **_kwargs: pytest.fail("external content must not be read"),
    )

    with pytest.raises(task_run_scope._SnapshotCaptureError):
        task_run_scope._fingerprint_worktree_path(
            tmp_path, "ordinary.txt", absent_allowed=False
        )
    assert replaced is True


def test_missing_fingerprint_rechecks_parent_after_symlink_replacement(
    tmp_path, monkeypatch
) -> None:
    parent = tmp_path / "ordinary-parent"
    parent.mkdir()
    external_directory = tmp_path.parent / f"{tmp_path.name}-external-directory"
    external_directory.mkdir()
    original_lstat = Path.lstat
    replaced = False

    def lstat_then_replace(path: Path):
        nonlocal replaced
        path_stat = original_lstat(path)
        if path == parent and not replaced:
            parent.rmdir()
            os.symlink(external_directory, parent, target_is_directory=True)
            replaced = True
        return path_stat

    monkeypatch.setattr(Path, "lstat", lstat_then_replace)
    monkeypatch.setattr(
        task_run_scope.os,
        "open",
        lambda *_args, **_kwargs: pytest.fail("external content must not be opened"),
    )
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda _path: pytest.fail("external content must not be read"),
    )

    with pytest.raises(task_run_scope._SnapshotCaptureError):
        task_run_scope._fingerprint_worktree_path(
            tmp_path, "ordinary-parent/missing.txt", absent_allowed=True
        )
    assert replaced is True


def test_directory_fingerprint_rechecks_parent_after_symlink_replacement(
    tmp_path, monkeypatch
) -> None:
    parent = tmp_path / "ordinary-parent"
    parent.mkdir()
    external_directory = tmp_path.parent / f"{tmp_path.name}-external-directory"
    external_directory.mkdir()
    (external_directory / "leaf-directory").mkdir()
    original_lstat = Path.lstat
    replaced = False

    def lstat_then_replace(path: Path):
        nonlocal replaced
        path_stat = original_lstat(path)
        if path == parent and not replaced:
            parent.rmdir()
            os.symlink(external_directory, parent, target_is_directory=True)
            replaced = True
        return path_stat

    monkeypatch.setattr(Path, "lstat", lstat_then_replace)
    monkeypatch.setattr(
        task_run_scope.os,
        "scandir",
        lambda *_args, **_kwargs: pytest.fail(
            "external directory must not be scanned"
        ),
    )

    with pytest.raises(task_run_scope._SnapshotCaptureError):
        task_run_scope._fingerprint_worktree_path(
            tmp_path, "ordinary-parent/leaf-directory", absent_allowed=False
        )
    assert replaced is True


def test_regular_collection_discards_scan_when_directory_becomes_symlink(
    tmp_path, monkeypatch
) -> None:
    directory = tmp_path / "ordinary-directory"
    directory.mkdir()
    external_directory = tmp_path.parent / f"{tmp_path.name}-external-directory"
    external_directory.mkdir()
    (external_directory / "outside.txt").write_text("outside", encoding="utf-8")
    original_scandir = task_run_scope.os.scandir
    original_entry_kind = task_run_scope._dir_entry_kind
    replaced = False

    def scandir_after_replacement(path):
        nonlocal replaced
        if Path(path) == directory and not replaced:
            directory.rmdir()
            os.symlink(external_directory, directory, target_is_directory=True)
            replaced = True
        return original_scandir(path)

    def reject_external_entry(entry):
        if entry.name == "outside.txt":
            pytest.fail("external directory entries must be discarded")
        return original_entry_kind(entry)

    monkeypatch.setattr(task_run_scope.os, "scandir", scandir_after_replacement)
    monkeypatch.setattr(task_run_scope, "_dir_entry_kind", reject_external_entry)

    with pytest.raises(task_run_scope._SnapshotCaptureError):
        task_run_scope._collect_regular_files(tmp_path, ())
    assert replaced is True


def test_regular_collection_rechecks_ancestors_before_recursive_scan(
    tmp_path, monkeypatch
) -> None:
    ancestor = tmp_path / "ancestor"
    child_directory = ancestor / "child"
    child_directory.mkdir(parents=True)
    original_ancestor = tmp_path / "ancestor-original"
    external_ancestor = tmp_path.parent / f"{tmp_path.name}-external-ancestor"
    external_child = external_ancestor / "child"
    external_child.mkdir(parents=True)
    (external_child / "outside.txt").write_text("outside", encoding="utf-8")
    original_entry_kind = task_run_scope._dir_entry_kind
    replaced = False

    def replace_ancestor_after_child_classification(entry):
        nonlocal replaced
        kind = original_entry_kind(entry)
        if Path(entry.path) == child_directory and not replaced:
            ancestor.rename(original_ancestor)
            os.symlink(external_ancestor, ancestor, target_is_directory=True)
            replaced = True
        if entry.name == "outside.txt":
            pytest.fail("external directory entries must not be accepted")
        return kind

    monkeypatch.setattr(
        task_run_scope,
        "_dir_entry_kind",
        replace_ancestor_after_child_classification,
    )

    with pytest.raises(task_run_scope._SnapshotCaptureError):
        task_run_scope._collect_regular_files(tmp_path, ())
    assert replaced is True


def test_trusted_gitdir_prevents_following_changed_pointer_target(
    tmp_path, monkeypatch
) -> None:
    gitdir_a = tmp_path / "private-gitdir-a"
    gitdir_b = tmp_path / "private-gitdir-b"
    for gitdir in (gitdir_a, gitdir_b):
        gitdir.mkdir()
        (gitdir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    git_pointer = tmp_path / ".git"
    git_pointer.write_text(f"gitdir: {gitdir_a}\n", encoding="utf-8")
    _stub_git_status(monkeypatch, b"")
    control_key = "trusted-pointer-control-key"
    baseline = capture_worktree_scope_snapshot(tmp_path, control_key=control_key)

    git_pointer.write_text(f"gitdir: {gitdir_b}\n", encoding="utf-8")
    _stub_git_layers(
        monkeypatch,
        index_output=_git_index_record("private-gitdir-b/HEAD"),
    )
    original_collect_tree_records = task_run_scope._collect_tree_records
    original_fingerprint = task_run_scope._fingerprint_worktree_path

    def collect_without_new_target(path, *args) -> None:
        assert path.resolve() != gitdir_b
        original_collect_tree_records(path, *args)

    def fingerprint_without_new_target(
        root,
        path,
        *,
        absent_allowed,
        root_observations=None,
    ):
        assert not path.startswith("private-gitdir-b/")
        return original_fingerprint(
            root,
            path,
            absent_allowed=absent_allowed,
            root_observations=root_observations,
        )

    monkeypatch.setattr(
        task_run_scope, "_collect_tree_records", collect_without_new_target
    )
    monkeypatch.setattr(
        task_run_scope, "_fingerprint_worktree_path", fingerprint_without_new_target
    )
    current = capture_worktree_scope_snapshot(
        tmp_path,
        control_key=control_key,
        trusted_git_dir=gitdir_a,
    )
    decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)

    assert current.available is True
    assert "private-gitdir-b/HEAD" not in {entry.path for entry in current.entries}
    assert decision.status == "rejected"
    assert decision.error_code == "TASK_RUN_SCOPE_VIOLATION"
    assert decision.rejected_paths == ("<protected-footprint>",)
    exposed = f"{baseline.to_metadata()} {current.to_metadata()} {decision}"
    assert str(gitdir_a) not in exposed
    assert str(gitdir_b) not in exposed
    assert control_key not in exposed


def test_trusted_pointer_excludes_candidate_at_both_rename_endpoints(
    tmp_path, monkeypatch
) -> None:
    cases = (
        (
            "candidate-destination",
            _git_index_record("private-gitdir-b/HEAD"),
            _git_tree_record("apps/demo/src/Old.tsx"),
            None,
        ),
        (
            "candidate-source",
            _git_index_record("apps/demo/src/New.tsx"),
            _git_tree_record("private-gitdir-b/HEAD"),
            "apps/demo/src/New.tsx",
        ),
    )
    for case_name, index_output, tree_output, destination_path in cases:
        root = tmp_path / case_name
        root.mkdir()
        gitdir_a = root / "private-gitdir-a"
        gitdir_b = root / "private-gitdir-b"
        for gitdir in (gitdir_a, gitdir_b):
            gitdir.mkdir()
            (gitdir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        pointer = root / ".git"
        pointer.write_text(f"gitdir: {gitdir_a}\n", encoding="utf-8")

        baseline = capture_worktree_scope_snapshot(
            root,
            control_key="scope-test-key",
            runner=lambda *args, **kwargs: SimpleNamespace(
                returncode=0, stdout=b"", stderr=b""
            ),
        )
        pointer.write_text(f"gitdir: {gitdir_b}\n", encoding="utf-8")
        if destination_path is not None:
            destination = root / destination_path
            destination.parent.mkdir(parents=True)
            destination.write_text("export const New = true;", encoding="utf-8")

        original_fingerprint = task_run_scope._fingerprint_worktree_path

        def fingerprint_without_new_target(
            root_path,
            path,
            *,
            absent_allowed,
            root_observations=None,
        ):
            assert not path.startswith("private-gitdir-b/")
            return original_fingerprint(
                root_path,
                path,
                absent_allowed=absent_allowed,
                root_observations=root_observations,
            )

        with monkeypatch.context() as post_patch:
            post_patch.setattr(
                task_run_scope,
                "_fingerprint_worktree_path",
                fingerprint_without_new_target,
            )
            current = capture_worktree_scope_snapshot(
                root,
                control_key="scope-test-key",
                trusted_git_dir=gitdir_a,
                runner=_layer_runner(
                    index_output=index_output,
                    tree_output=tree_output,
                ),
            )
        decision = validate_scope_delta(get_target("demo-frontend"), baseline, current)

        assert current.available is True
        assert "private-gitdir-b/HEAD" not in {entry.path for entry in current.entries}
        assert "private-gitdir-b" not in str(current.to_metadata())
        assert decision.status == "rejected"
        assert decision.rejected_paths == ("<protected-footprint>",)


def test_forged_porcelain_status_metadata_is_unverifiable() -> None:
    current = _snapshot()
    for status in ("?!", "!!", "  ", "M!", "??", " M", "A ", "UU"):
        restored = scope_snapshot_from_metadata(
            {
                "schema_version": SCOPE_SNAPSHOT_SCHEMA_VERSION,
                "available": True,
                "reason": None,
                "entries": [
                    {
                        "path": "apps/demo/src/App.tsx",
                        "status": status,
                        "fingerprint": "b" * 64,
                    }
                ],
                "protected_control_digest": "a" * 64,
                "protected_categories": [],
                "protected_entry_count": 0,
            }
        )

        assert restored.available is False
        decision = validate_scope_delta(get_target("demo-frontend"), restored, current)
        assert decision.status == "unverifiable"
        assert decision.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"


def test_timeout_runner_returns_redacted_unavailable_snapshot(tmp_path) -> None:
    _write_git_control_state(tmp_path)
    runner_calls: list[tuple[list[str], dict[str, object]]] = []

    def timeout_runner(command: list[str], **kwargs):
        runner_calls.append((command, kwargs))
        raise subprocess.TimeoutExpired("git status", 1)

    snapshot = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="scope-test-key",
        runner=timeout_runner,
    )

    assert snapshot.available is False
    assert snapshot.entries == ()
    assert snapshot.protected_control_digest is None
    assert str(tmp_path) not in (snapshot.reason or "")
    assert len(runner_calls) == 1
    command, kwargs = runner_calls[0]
    assert Path(command[0]).is_absolute()
    assert isinstance(kwargs.get("timeout"), (int, float))
    assert 0 < kwargs["timeout"] <= 30


def test_capture_does_not_execute_repository_process_filter(tmp_path) -> None:
    git = shutil.which("git")
    if not git:
        pytest.skip("git is required for the filter-isolation regression")

    def run_git(*args: str) -> None:
        completed = subprocess.run(
            [git, *args],
            cwd=tmp_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
        )
        assert completed.returncode == 0, completed.stderr.decode(
            "utf-8", errors="replace"
        )

    run_git("init", "--quiet")
    run_git("config", "user.email", "scope-test@example.invalid")
    run_git("config", "user.name", "scope-test")
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("one\n", encoding="utf-8")
    run_git("add", "tracked.txt")
    run_git("commit", "--quiet", "-m", "initial")
    (tmp_path / ".gitattributes").write_text(
        "tracked.txt filter=evil\n", encoding="utf-8"
    )
    run_git("add", ".gitattributes")
    run_git("commit", "--quiet", "-m", "attributes")

    marker = tmp_path.parent / f"{tmp_path.name}-filter-marker"
    filter_script = tmp_path.parent / f"{tmp_path.name}-filter.py"
    filter_script.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "Path(sys.argv[1]).write_text('executed', encoding='utf-8')\n",
        encoding="utf-8",
    )
    filter_command = (
        f'"{sys.executable}" "{filter_script}" "{marker}"'
    )
    run_git("config", "filter.evil.process", filter_command)
    run_git("config", "filter.evil.required", "true")
    run_git("config", "core.trustctime", "false")

    original_stat = tracked.stat()
    tracked.write_text("two\n", encoding="utf-8")
    os.utime(
        tracked,
        ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
    )

    snapshot = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="real-filter-isolation-key",
    )

    assert not marker.exists(), "repository process filter was executed"
    assert snapshot.available is True
    assert any(entry.path == "tracked.txt" for entry in snapshot.entries)


def test_safe_scope_state_covers_git_and_worktree_layers(tmp_path) -> None:
    git = shutil.which("git")
    if not git:
        pytest.skip("git is required for the scope-state regression")

    def run_git(*args: str) -> None:
        completed = subprocess.run(
            [git, *args],
            cwd=tmp_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
        )
        assert completed.returncode == 0, completed.stderr.decode(
            "utf-8", errors="replace"
        )

    run_git("init", "--quiet")
    run_git("config", "user.email", "scope-test@example.invalid")
    run_git("config", "user.name", "scope-test")
    for name in (
        "unstaged.txt",
        "deleted.txt",
        "staged.txt",
        "rename-old.txt",
    ):
        (tmp_path / name).write_text(f"{name}-one\n", encoding="utf-8")
    run_git("add", ".")
    run_git("commit", "--quiet", "-m", "initial")
    baseline = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="scope-state-key",
    )

    (tmp_path / "unstaged.txt").write_text("unstaged-two\n", encoding="utf-8")
    (tmp_path / "deleted.txt").unlink()
    (tmp_path / "staged.txt").write_text("staged-two\n", encoding="utf-8")
    run_git("add", "staged.txt")
    run_git("mv", "rename-old.txt", "rename-new.txt")
    (tmp_path / "untracked.txt").write_text("untracked\n", encoding="utf-8")
    current = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="scope-state-key",
    )

    assert baseline.available is True
    assert current.available is True
    entries = {entry.path: entry for entry in current.entries}
    assert entries["unstaged.txt"].status == "tracked-present"
    assert entries["deleted.txt"].status == "tracked-missing"
    assert entries["staged.txt"].status == "staged-modified-present"
    assert entries["rename-old.txt"].status == "staged-deleted-missing"
    assert entries["rename-new.txt"].status == "staged-added-present"
    assert entries["untracked.txt"].status == "untracked-present"
    baseline_entries = {entry.path: entry for entry in baseline.entries}
    assert (
        baseline_entries["unstaged.txt"].fingerprint
        != entries["unstaged.txt"].fingerprint
    )


def test_index_only_change_updates_entry_and_rejects_protected_digest(
    tmp_path,
) -> None:
    git = shutil.which("git")
    if not git:
        pytest.skip("git is required for the index-only regression")

    def run_git(*args: str) -> None:
        completed = subprocess.run(
            [git, *args],
            cwd=tmp_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
        )
        assert completed.returncode == 0, completed.stderr.decode(
            "utf-8", errors="replace"
        )

    run_git("init", "--quiet")
    run_git("config", "user.email", "scope-test@example.invalid")
    run_git("config", "user.name", "scope-test")
    tracked = tmp_path / "apps/demo/src/App.tsx"
    tracked.parent.mkdir(parents=True)
    tracked.write_text("export const value = 'one';\n", encoding="utf-8")
    run_git("add", "apps/demo/src/App.tsx")
    run_git("commit", "--quiet", "-m", "initial")
    baseline = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="index-only-key",
    )

    tracked.write_text("export const value = 'two';\n", encoding="utf-8")
    run_git("add", "apps/demo/src/App.tsx")
    tracked.write_text("export const value = 'one';\n", encoding="utf-8")
    current = capture_worktree_scope_snapshot(
        tmp_path,
        control_key="index-only-key",
    )
    decision = validate_scope_delta(
        get_target("demo-frontend"),
        baseline,
        current,
    )

    assert baseline.available is True
    assert current.available is True
    baseline_entry = next(
        entry
        for entry in baseline.entries
        if entry.path == "apps/demo/src/App.tsx"
    )
    current_entry = next(
        entry
        for entry in current.entries
        if entry.path == "apps/demo/src/App.tsx"
    )
    assert baseline_entry.fingerprint != current_entry.fingerprint
    assert decision.status == "rejected"
    assert decision.rejected_paths == ("<protected-footprint>",)


def test_safe_audit_metadata_only_exposes_protected_categories_and_count(
    tmp_path, monkeypatch
) -> None:
    _write_git_control_state(tmp_path)
    protected_file = tmp_path / "apps/demo/node_modules/package/index.js"
    protected_file.parent.mkdir(parents=True)
    protected_file.write_text("module.exports=1;", encoding="utf-8")
    _stub_git_status(monkeypatch, b"")

    snapshot = capture_worktree_scope_snapshot(tmp_path, control_key="scope-test-key")
    metadata = snapshot.to_metadata()

    assert set(metadata) == {
        "schema_version",
        "available",
        "reason",
        "protected_categories",
        "protected_entry_count",
    }
    assert metadata["protected_categories"] == [".git", "node_modules"]
    assert type(metadata["protected_entry_count"]) is int
    assert metadata["protected_entry_count"] > 0
    assert "protected_control_digest" not in metadata
    assert str(protected_file) not in str(metadata)

    internal_metadata = snapshot.to_metadata(include_internal=True)
    restored = scope_snapshot_from_metadata(internal_metadata)
    assert restored == snapshot
    invalid_count = dict(internal_metadata)
    invalid_count["protected_entry_count"] = "not-an-int"
    assert scope_snapshot_from_metadata(invalid_count).available is False


def _write_git_control_state(tmp_path, gitdir_name: str = "git-control") -> None:
    gitdir = tmp_path / gitdir_name
    gitdir.mkdir()
    (gitdir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (tmp_path / ".git").write_text(f"gitdir: {gitdir_name}\n", encoding="utf-8")


def _stub_git_status(monkeypatch, output: bytes) -> None:
    _stub_git_layers(
        monkeypatch,
        index_output=output,
        tree_output=output,
    )


def _stub_git_layers(
    monkeypatch,
    *,
    index_output: bytes = b"",
    tree_output: bytes = b"",
) -> None:
    def run(command, **kwargs):
        output = tree_output if "ls-tree" in command else index_output
        return SimpleNamespace(returncode=0, stdout=output, stderr=b"")

    monkeypatch.setattr(
        "app.task_run_scope.subprocess.run",
        run,
    )


def _layer_runner(*, index_output: bytes, tree_output: bytes):
    def run(command, **kwargs):
        output = tree_output if "ls-tree" in command else index_output
        return SimpleNamespace(returncode=0, stdout=output, stderr=b"")

    return run


def _git_index_record(path: str, *, oid: str = "a" * 40) -> bytes:
    return f"100644 {oid} 0\t{path}".encode("utf-8") + b"\0"


def _git_tree_record(path: str, *, oid: str = "b" * 40) -> bytes:
    return f"100644 blob {oid}\t{path}".encode("utf-8") + b"\0"


def _create_windows_junction(link: Path, target: Path) -> None:
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        pytest.skip("the test environment cannot create a Windows directory junction")
