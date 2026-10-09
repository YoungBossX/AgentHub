"""Exact, bounded text patches. This module never writes files or runs Git."""

import difflib
import hashlib
import re
from dataclasses import dataclass
from typing import Callable

from app.target_registry import is_canonical_repository_path, protected_repository_path_category

MAX_PATCH_BYTES = 2 * 1024 * 1024
MAX_FILE_BYTES = 512 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024
MAX_PATCH_FILES = 16
HUNK = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?:[^\r\n]*)\Z")
INDEX = re.compile(r"index [0-9a-f]{1,64}\.\.[0-9a-f]{1,64}(?: 100(?:644|755))?\Z")
NO_NEWLINE = "\\ No newline at end of file"
WINDOWS_DEVICE = re.compile(r"(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[1-9¹²³]|LPT[1-9¹²³])\Z", re.IGNORECASE)


class UserPatchError(ValueError):
    pass


class UserPatchConflict(UserPatchError):
    pass


@dataclass(frozen=True)
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class FilePatch:
    path: str
    operation: str
    hunks: tuple[Hunk, ...]


@dataclass(frozen=True)
class FileChange:
    path: str
    before: bytes | None
    after: bytes | None

    def metadata(self) -> dict:
        return {
            "path": self.path,
            "operation": "add" if self.before is None else "delete" if self.after is None else "modify",
            "beforeSha256": digest(self.before), "afterSha256": digest(self.after),
            "beforeBytes": len(self.before) if self.before is not None else None,
            "afterBytes": len(self.after) if self.after is not None else None,
        }


def digest(value: bytes | None) -> str | None:
    return hashlib.sha256(value).hexdigest() if value is not None else None


def _lines(value: str) -> list[str]:
    # splitlines() also splits Unicode NEL/vertical-tab, which are source data.
    parts = value.split("\n")
    return [part + "\n" for part in parts[:-1]] + ([parts[-1]] if parts[-1] else [])


def text_bytes(value: bytes) -> str:
    if len(value) > MAX_FILE_BYTES or b"\x00" in value:
        raise UserPatchError("Only bounded UTF-8 text files are supported.")
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UserPatchError("Only UTF-8 text files are supported.") from exc


def validate_path(path: str) -> None:
    if (not is_canonical_repository_path(path)
            or protected_repository_path_category(path, case_sensitive=False) is not None
            or any(part != part.rstrip(" .") or any(c in part for c in '<>"|~')
                   for part in path.split("/"))
            or any(WINDOWS_DEVICE.fullmatch(part.split(".", 1)[0].rstrip(" "))
                   for part in path.split("/"))):
        raise UserPatchError("Patch contains an invalid or protected path.")


def _path(header: str, prefix: str) -> str | None:
    value = header[4:]
    if value == "/dev/null":
        return None
    if not value.startswith(prefix):
        raise UserPatchError("Patch paths must use unquoted a/ and b/ repository paths.")
    path = value[len(prefix):]
    validate_path(path)
    return path


def parse_text_patch(patch: str) -> tuple[FilePatch, ...]:
    if not isinstance(patch, str) or not patch or len(patch.encode("utf-8")) > MAX_PATCH_BYTES or "\x00" in patch:
        raise UserPatchError("Patch is empty, binary or exceeds the size limit.")
    lines = _lines(patch)
    if not lines[-1].endswith("\n"):
        raise UserPatchError("Patch lines must end in a newline; use the standard no-newline marker for source EOF.")
    files: list[FilePatch] = []
    seen: set[str] = set()
    i = 0

    def header(index: int) -> str:
        return lines[index].removesuffix("\n").removesuffix("\r")

    while i < len(lines):
        git_header = None
        declared = None
        if header(i).startswith("diff --git "):
            git_header = header(i); i += 1
            if i < len(lines) and header(i).startswith(("new file mode ", "deleted file mode ")):
                mode = header(i)
                if mode == "new file mode 100644":
                    declared = "add"
                elif mode in {"deleted file mode 100644", "deleted file mode 100755"}:
                    declared = "delete"
                else:
                    raise UserPatchError("Links and permission-changing patches are unsupported.")
                i += 1
            if i < len(lines) and INDEX.fullmatch(header(i)):
                i += 1
        if i + 1 >= len(lines) or not header(i).startswith("--- ") or not header(i + 1).startswith("+++ "):
            raise UserPatchError("Expected complete unified text file headers; binary, rename and mode-only patches are unsupported.")
        old_path, new_path = _path(header(i), "a/"), _path(header(i + 1), "b/")
        if old_path is None and new_path is None or old_path and new_path and old_path != new_path:
            raise UserPatchError("A patch must have one target path; renames are unsupported.")
        path = old_path or new_path
        assert path is not None
        operation = "add" if old_path is None else "delete" if new_path is None else "modify"
        if (declared is not None and declared != operation) or (git_header is not None and git_header != f"diff --git a/{path} b/{path}"):
            raise UserPatchError("Patch file headers disagree.")
        if path.casefold() in seen or len(files) >= MAX_PATCH_FILES:
            raise UserPatchError("Duplicate patch path or too many files.")
        seen.add(path.casefold()); i += 2
        hunks: list[Hunk] = []
        while i < len(lines) and header(i).startswith("@@ "):
            match = HUNK.fullmatch(header(i))
            if match is None:
                raise UserPatchError("Malformed hunk header.")
            start_old, count_old, start_new, count_new = [int(value) if value is not None else 1 for value in match.groups()]
            if count_old and not start_old or count_new and not start_new:
                raise UserPatchError("Invalid hunk start.")
            i += 1; old_used = new_used = 0
            content: list[tuple[str, str]] = []
            while i < len(lines):
                if header(i) == NO_NEWLINE:
                    if not content or not content[-1][1].endswith("\n"):
                        raise UserPatchError("Unexpected no-newline marker.")
                    tag, text = content[-1]
                    content[-1] = tag, text[:-1]; i += 1
                    continue
                if old_used == count_old and new_used == count_new:
                    break
                line = lines[i]
                if line[0] not in {" ", "+", "-"}:
                    raise UserPatchError("Hunk body ended before its declared line counts.")
                tag = line[0]
                old_used += tag != "+"; new_used += tag != "-"
                if old_used > count_old or new_used > count_new:
                    raise UserPatchError("Hunk body exceeds its declared line counts.")
                content.append((tag, line[1:])); i += 1
            if old_used != count_old or new_used != count_new:
                raise UserPatchError("Incomplete hunk body.")
            hunks.append(Hunk(start_old, count_old, start_new, count_new, tuple(content)))
        if not hunks:
            raise UserPatchError("Patch has no text hunks.")
        files.append(FilePatch(path, operation, tuple(hunks)))
    return tuple(files)


def _apply_file(patch: FilePatch, before: bytes | None) -> FileChange:
    if patch.operation == "add" and before is not None:
        raise UserPatchConflict("The file to add already exists.")
    if patch.operation != "add" and before is None:
        raise UserPatchConflict("A patch source file no longer exists.")
    original = _lines(text_bytes(before)) if before is not None else []
    output: list[str] = []
    cursor = 0
    for hunk in patch.hunks:
        start = hunk.old_start - 1 if hunk.old_count else hunk.old_start
        if start < cursor or start > len(original):
            raise UserPatchConflict("Hunk offsets overlap or exceed current source.")
        output.extend(original[cursor:start]); cursor = start
        new_start = hunk.new_start - 1 if hunk.new_count else hunk.new_start
        if new_start != len(output):
            raise UserPatchConflict("New hunk position does not match the exact output.")
        for tag, text in hunk.lines:
            if tag != "+":
                if cursor >= len(original) or original[cursor] != text:
                    raise UserPatchConflict("Hunk context does not match the current source; reload instead of forcing the patch.")
                cursor += 1
            if tag != "-":
                output.append(text)
    output.extend(original[cursor:])
    # Non-final unterminated lines would silently concatenate two logical lines.
    if any(not line.endswith("\n") for line in output[:-1]):
        raise UserPatchError("A no-newline marker is only valid at the end of the resulting file.")
    after = "".join(output).encode("utf-8")
    text_bytes(after)
    if patch.operation == "delete":
        if after:
            raise UserPatchError("A deletion patch must remove the complete file.")
        result = None
    else:
        result = after
    if result == before:
        raise UserPatchError("The patch does not change file content.")
    return FileChange(patch.path, before, result)


def prepare_text_patch(patch: str, *, read_file: Callable[[str], bytes | None], permits: Callable[[str], bool]) -> tuple[FileChange, ...]:
    files = parse_text_patch(patch)
    # Validate every path before the first file read, including a later unsafe
    # member of an otherwise valid multi-file patch.
    if any(not permits(item.path) for item in files):
        raise UserPatchError("A patch path is outside the selected target.")
    changes = []
    total = 0
    for item in files:
        change = _apply_file(item, read_file(item.path))
        total += sum(len(value) for value in (change.before, change.after) if value is not None)
        if total > MAX_TOTAL_BYTES:
            raise UserPatchError("The patch exceeds the total source/output budget.")
        changes.append(change)
    return tuple(changes)


def render_text_patch(changes: tuple[FileChange, ...]) -> str:
    parts: list[str] = []
    for change in changes:
        if change.before == change.after:
            raise UserPatchError("Empty file change.")
        validate_path(change.path)
        old = text_bytes(change.before) if change.before is not None else ""
        new = text_bytes(change.after) if change.after is not None else ""
        old_name = f"a/{change.path}" if change.before is not None else "/dev/null"
        new_name = f"b/{change.path}" if change.after is not None else "/dev/null"
        parts.append(f"diff --git a/{change.path} b/{change.path}\n")
        if change.before is None:
            parts.append("new file mode 100644\n")
        if change.after is None:
            parts.append("deleted file mode 100644\n")
        diff = list(difflib.unified_diff(_lines(old), _lines(new), fromfile=old_name, tofile=new_name))
        if not diff:
            diff = [f"--- {old_name}\n", f"+++ {new_name}\n", "@@ -0,0 +0,0 @@\n"]
        for line in diff:
            parts.append(line if line.endswith("\n") else line + "\n" + NO_NEWLINE + "\n")
    result = "".join(parts)
    parse_text_patch(result)
    return result
