import pytest

from app import user_patch
from app.target_registry import get_target
from app.user_patch import FileChange, UserPatchConflict, UserPatchError, prepare_text_patch, render_text_patch

PATH = "apps/demo/src/App.tsx"
PERMITS = get_target("demo-frontend").permits_path


def prepare(patch, files):
    return prepare_text_patch(patch, read_file=files.get, permits=PERMITS)


def test_exact_multi_file_patch_add_modify_delete_and_no_newline_round_trip():
    changes = (
        FileChange(PATH, b"one\r\ntwo\r\nlast", b"one\r\nNEW\r\nlast"),
        FileChange("apps/demo/src/new.txt", None, "中文\n末行".encode()),
        FileChange("apps/demo/src/old.txt", b"delete\n", None),
    )
    files = {item.path: item.before for item in changes}
    patch = render_text_patch(changes)
    assert "\\ No newline at end of file" in patch
    assert prepare(patch, files) == changes
    assert files == {item.path: item.before for item in changes}, "Preparation must not mutate input storage"
    assert changes[1].metadata()["beforeSha256"] is None
    assert changes[2].metadata()["afterSha256"] is None


@pytest.mark.parametrize("before,after", [
    (None, b""), (b"", None), (b"", b"new"), (b"last", b"last\n"),
    (b"last\n", b"last"), (b"a\r\nb\r\n", b"a\r\nB\r\n"),
    ("line\u0085data\vkeep\n".encode(), "line\u0085data\vKEEP\n".encode()),
    (b"a\n" * 12, b"a\nfirst\n" + b"a\n" * 10 + b"last\na\n"),
])
def test_preserves_utf8_and_precise_line_endings(before, after):
    change = FileChange(PATH, before, after)
    assert prepare(render_text_patch((change,)), {PATH: before}) == (change,)


def test_real_unified_patch_applies_exact_offsets_without_fuzzy_search():
    patch = "--- a/apps/demo/src/App.tsx\n+++ b/apps/demo/src/App.tsx\n@@ -2,2 +2,2 @@ function\n keep\n-old\n+new\n"
    assert prepare(patch, {PATH: b"untouched\nkeep\nold\ntail\n"})[0].after == b"untouched\nkeep\nnew\ntail\n"
    for changed in [b"shifted\nuntouched\nkeep\nold\ntail\n", b"untouched\nkeep\nchanged\ntail\n"]:
        with pytest.raises(UserPatchConflict): prepare(patch, {PATH: changed})


@pytest.mark.parametrize("path", [
    "../outside", "apps/demo/src/../outside", "apps/demo/.env", "apps/demo/.ENV.local",
    "apps/demo/src/a:stream", "apps/demo/src/nul.txt", "apps/demo/node_modules/pkg/a.js",
    "apps/demo/src/a\tfile", "C:/host", ".git/config", "apps/demo/src/secrets/key.txt",
    "apps/demo/src/COM1.log", "apps/demo/src/LPT².txt", "apps/demo/src/conin$",
    "apps/demo/src/NUL .txt", "apps/demo/src/a.", "apps/demo/src/a /b", "apps/demo/src/SECRET~1/key",
])
def test_unsafe_paths_rejected_before_read(path):
    patch = f"--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n-old\n+new\n"
    reads = []
    with pytest.raises(UserPatchError): prepare_text_patch(patch, read_file=lambda p: reads.append(p), permits=lambda p: True)
    assert not reads


def test_foreign_target_late_in_patch_blocks_every_read():
    patch = render_text_patch((FileChange(PATH, b"old\n", b"new\n"), FileChange("apps/api/app/main.py", b"old\n", b"new\n")))
    reads = []
    with pytest.raises(UserPatchError, match="outside"): prepare_text_patch(patch, read_file=lambda p: reads.append(p), permits=PERMITS)
    assert not reads


@pytest.mark.parametrize("fragment", [
    "GIT binary patch\nliteral 10\nabc\n", "old mode 100644\nnew mode 100755\n",
    "new file mode 120000\n", "similarity index 100%\nrename from x\nrename to y\n",
    "index abc..def 120000\n--- a/apps/demo/src/App.tsx\n+++ b/apps/demo/src/App.tsx\n@@ -1 +1 @@\n-a\n+b\n",
])
def test_unsupported_git_patch_metadata_is_rejected(fragment):
    with pytest.raises(UserPatchError): prepare("diff --git a/apps/demo/src/App.tsx b/apps/demo/src/App.tsx\n" + fragment, {PATH: b"a\n"})


@pytest.mark.parametrize("body", [
    "@@ -1,2 +1 @@\n-old\n+new\n", "@@ -0 +1 @@\n-old\n+new\n",
    "@@ -1 +3 @@\n-old\n+new\n", "@@ -1 +1 @@\n-old\n+new\n+extra\n",
    "@@ -1 +1 @@\n-old\n+new", "@@ -1 +1 @@\n-old\n+new\n\\ No newline at end of file\n\\ No newline at end of file\n",
    "@@ -1 +1 @@\n-old\n+new\n@@ -1 +1 @@\n-old\n+twice\n",
])
def test_malformed_counts_positions_and_markers_are_rejected(body):
    with pytest.raises(UserPatchError): prepare(f"--- a/{PATH}\n+++ b/{PATH}\n" + body, {PATH: b"old\n"})


def test_duplicate_paths_binary_empty_edits_and_existing_add_are_not_applied():
    patch = render_text_patch((FileChange(PATH, b"old\n", b"new\n"),))
    with pytest.raises(UserPatchError): prepare(patch + patch, {PATH: b"old\n"})
    with pytest.raises(UserPatchError): prepare(patch, {PATH: b"\x00old\n"})
    with pytest.raises(UserPatchError): render_text_patch((FileChange(PATH, b"same", b"same"),))
    add = render_text_patch((FileChange(PATH, None, b"new\n"),))
    with pytest.raises(UserPatchConflict): prepare(add, {PATH: b"old\n"})
    with pytest.raises(UserPatchConflict): prepare(patch, {})


def test_no_newline_in_middle_cannot_merge_source_lines_silently():
    patch = f"--- a/{PATH}\n+++ b/{PATH}\n@@ -1 +1 @@\n-old\n+new\n\\ No newline at end of file\n"
    with pytest.raises(UserPatchError, match="end of the resulting file"): prepare(patch, {PATH: b"old\ntail\n"})


def test_file_count_size_and_total_budgets(monkeypatch):
    with pytest.raises(UserPatchError): render_text_patch(tuple(FileChange(f"apps/demo/src/f{i}.txt", None, b"a\n") for i in range(17)))
    patch = render_text_patch((FileChange(PATH, b"old\n", b"new\n"),))
    monkeypatch.setattr(user_patch, "MAX_FILE_BYTES", 3)
    with pytest.raises(UserPatchError): prepare(patch, {PATH: b"old\n"})
    monkeypatch.setattr(user_patch, "MAX_FILE_BYTES", 512 * 1024)
    monkeypatch.setattr(user_patch, "MAX_TOTAL_BYTES", 7)
    with pytest.raises(UserPatchError): prepare(patch, {PATH: b"old\n"})
