"""Bounded byte handoff. No archives, links, overwrites or target-selected paths."""

import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import unicodedata

from app.validation_policy import ValidationUnavailable, digest

MAX_TRANSPORT = 48 * 1024 * 1024
MAX_TOTAL = 32 * 1024 * 1024
MAX_FILE = 5 * 1024 * 1024
HEX = re.compile(r"[0-9a-f]{64}\Z")


def portable_path(value):
    if (not isinstance(value, str) or unicodedata.normalize("NFC", value) != value or len(value.encode()) > 240
            or re.search(r'[\\:<>"|?*\x00-\x1f\x7f]', value)):
        raise ValidationUnavailable("Unsafe exported path.")
    parts = value.split("/")
    if len(parts) > 16 or any(not p or p in {".", ".."} or p.endswith((".", " ")) or len(p.encode()) > 120
        or re.match(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", p, re.I)
        or re.fullmatch(r"(?:\.git|\.env(?:\..*)?|secrets|node_modules)", p, re.I) for p in parts):
        raise ValidationUnavailable("Unsafe exported path.")
    return value


def validate_portable_paths(paths):
    """Reject file/parent collisions and differently spelled directory aliases."""
    names, directories = set(), {}
    for path in paths:
        portable_path(path)
        key = path.casefold()
        parts = path.split("/")
        parents = ["/".join(parts[:i]) for i in range(1, len(parts))]
        if (key in names or key in directories or any(parent.casefold() in names for parent in parents)
                or any(directories.get(parent.casefold(), parent) != parent for parent in parents)):
            raise ValidationUnavailable("Portable path collision.")
        names.add(key)
        directories.update((parent.casefold(), parent) for parent in parents)


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValidationUnavailable("Duplicate export JSON key.")
        value[key] = item
    return value


def _nonfinite(value):
    raise ValidationUnavailable("Non-finite export JSON value.")


def parse_export(raw, expected_source, expected_files):
    if not isinstance(raw, bytes) or len(raw) > MAX_TRANSPORT:
        raise ValidationUnavailable("Export transport budget exceeded.")
    try:
        value = json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=_unique_object, parse_constant=_nonfinite)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValidationUnavailable("Invalid export envelope.") from exc
    if (not isinstance(value, dict) or set(value) != {"schemaVersion", "sourceFingerprint", "sourceFiles", "files"}
            or value["schemaVersion"] != "agenthub.container_export.v1" or value["sourceFingerprint"] != expected_source
            or not isinstance(value["sourceFiles"], dict) or value["sourceFiles"] != dict(expected_files)
            or not isinstance(value["files"], list) or len(value["files"]) > 512):
        raise ValidationUnavailable("Export does not match frozen inputs.")
    validate_portable_paths(value["sourceFiles"])
    for path, checksum in value["sourceFiles"].items():
        if not isinstance(checksum, str) or not HEX.fullmatch(checksum):
            raise ValidationUnavailable("Invalid source checksum.")
    for item in value["files"]:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "base64"}:
            raise ValidationUnavailable("Invalid exported file descriptor.")
    validate_portable_paths(item["path"] for item in value["files"])
    decoded, fingerprints = [], {}
    total = 0
    for item in value["files"]:
        path = item["path"]
        encoded = item["base64"]
        if (not isinstance(encoded, str) or len(encoded) > ((MAX_FILE + 2) // 3) * 4
                or not isinstance(item["sha256"], str) or not HEX.fullmatch(item["sha256"])):
            raise ValidationUnavailable("Export file budget or checksum is invalid.")
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValidationUnavailable("Invalid exported file encoding.") from exc
        total += len(content)
        if (len(content) > MAX_FILE or total > MAX_TOTAL or base64.b64encode(content).decode("ascii") != encoded
                or hashlib.sha256(content).hexdigest() != item["sha256"]):
            raise ValidationUnavailable("Export byte budget or checksum mismatch.")
        decoded.append((path, content))
        fingerprints[path] = item["sha256"]
    return decoded, digest(fingerprints)


def assert_canonical_directory(path, *, must_exist=True):
    path = Path(path).absolute()
    if path.resolve() != path:
        raise ValidationUnavailable("Server directory must be canonical.")
    for parent in (path, *path.parents):
        if not parent.exists():
            if parent == path and not must_exist: continue
            raise ValidationUnavailable("Server directory parent is unavailable.")
        info = parent.lstat()
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & 0x400):
            raise ValidationUnavailable("Linked server directory is refused.")
    return path


def materialize_export(raw: bytes, destination: Path, expected_source: str, *, expected_files) -> str:
    # Validate the entire envelope before creating any output file or directory.
    decoded, fingerprint = parse_export(raw, expected_source, expected_files)
    destination = assert_canonical_directory(destination, must_exist=False)
    destination.mkdir(mode=0o700)  # intentionally exclusive
    try:
        for relative, content in decoded:
            file = destination / relative
            file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            assert_canonical_directory(file.parent)
            fd = os.open(file, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
    except BaseException:
        # This exact new directory is server-owned and has never been a mount.
        assert_canonical_directory(destination)
        shutil.rmtree(destination)
        raise
    return fingerprint
