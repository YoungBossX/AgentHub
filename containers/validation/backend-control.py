#!/usr/local/bin/python
"""Image-owned backend controller; no target tests, free argv or host paths."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import unicodedata

PROFILE = "fastapi-contract-v1"
HEX = re.compile(r"[0-9a-f]{64}\Z")


def portable_path(path):
    if (not isinstance(path, str) or unicodedata.normalize("NFC", path) != path
            or len(path.encode()) > 240 or re.search(r"[\\:\x00-\x1f\x7f]", path)):
        raise ValueError("unsafe_path")
    parts = path.split("/")
    if len(parts) > 16 or any(not p or p in {".", ".."} or p.endswith((".", " ")) or len(p.encode()) > 120
        or re.match(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", p, re.I)
        or re.fullmatch(r"(?:\.git|\.env(?:\..*)?|secrets|node_modules)", p, re.I) for p in parts):
        raise ValueError("unsafe_path")
    return path


def validate_manifest(value):
    if (not isinstance(value, dict) or value.get("schemaVersion") != "agenthub.container_input.v1"
            or value.get("profile") != PROFILE or not HEX.fullmatch(str(value.get("sourceFingerprint")))
            or not isinstance(value.get("sourceFiles"), dict) or not 0 < len(value["sourceFiles"]) <= 512):
        raise ValueError("invalid_manifest")
    seen = set()
    for path, checksum in value["sourceFiles"].items():
        portable_path(path)
        if not path.startswith("apps/demo-api/") or not HEX.fullmatch(str(checksum)) or path.casefold() in seen:
            raise ValueError("invalid_manifest")
        seen.add(path.casefold())
    return value


def regular_bytes(root, path, limit):
    file = root / path
    for parent in file.parents:
        if parent == root: break
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode): raise ValueError("unsafe_directory")
    info = file.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
        raise ValueError("unsafe_file")
    fd = os.open(file, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit: raise ValueError("file_budget")
    return raw


def copy_input(input_dir, work):
    manifest = validate_manifest(json.loads(regular_bytes(input_dir, "manifest.json", 256 * 1024)))
    total = 0
    for path, checksum in manifest["sourceFiles"].items():
        raw = regular_bytes(input_dir, path, 512 * 1024)
        total += len(raw)
        if total > 16 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != checksum:
            raise ValueError("input_mismatch")
        output = work / path
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as stream: stream.write(raw)
    (work / "data").mkdir()
    return manifest


def export_result(work, manifest):
    validate_manifest(manifest)
    source_files = {}
    pending = [work / "apps/demo-api"]
    seen = 0
    while pending:
        path = pending.pop()
        seen += 1
        if seen > 1024: raise ValueError("entry_budget")
        relative = path.relative_to(work).as_posix()
        portable_path(relative)
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            pending.extend(path.iterdir())
        else:
            raw = regular_bytes(work, relative, 512 * 1024)
            source_files[relative] = hashlib.sha256(raw).hexdigest()
    if source_files != manifest["sourceFiles"]: raise ValueError("source_changed")
    return {"schemaVersion": "agenthub.container_export.v1", "sourceFingerprint": manifest["sourceFingerprint"],
            "sourceFiles": source_files, "files": []}


def stage_command(stage):
    if stage not in {"check", "test"}: raise ValueError("unsupported_stage")
    return ["/usr/local/bin/python", "-I", "-B", "/opt/agenthub/scripts/demo-backend-check.py",
            stage, "/work/apps/demo-api", "/work/data"]


def assert_no_background_processes():
    keepers = 0
    for path in Path("/proc").iterdir():
        if not path.name.isdigit() or int(path.name) in {1, os.getpid()}: continue
        try:
            command = [c.decode() for c in (path / "cmdline").read_bytes().split(b"\0") if c]
            executable = os.readlink(path / "exe")
        except FileNotFoundError: continue
        if (len(command) == 3 and command[1:] == ["/opt/agenthub/control", "hold"]
                and executable.startswith("/usr/local/bin/python")):
            keepers += 1
        else: raise ValueError("unexpected_process")
    if keepers != 1: raise ValueError("keeper_missing")


def main(args):
    if len(args) != 1 or args[0] not in {"hold", "prepare", "check", "test", "export"}:
        print("unsupported_stage", file=sys.stderr)
        return 2
    stage = args[0]
    if stage == "hold": time.sleep(180); return 0
    if stage == "prepare": copy_input(Path("/input"), Path("/work")); return 0
    if stage == "export":
        assert_no_background_processes()
        manifest = json.loads(regular_bytes(Path("/input"), "manifest.json", 256 * 1024))
        print(json.dumps(export_result(Path("/work"), manifest), separators=(",", ":")))
        return 0
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "CI": "1", "HOME": "/work/data", "TMPDIR": "/work/data",
           "PYTHONIOENCODING": "utf-8", "LANG": "C.UTF-8"}
    return subprocess.run(stage_command(stage), cwd="/work/apps/demo-api", env=env, timeout=60, check=False).returncode


if __name__ == "__main__":
    try: sys.exit(main(sys.argv[1:]))
    except Exception:
        print("controller_failed", file=sys.stderr)
        sys.exit(1)
