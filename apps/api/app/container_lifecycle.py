"""Private journals and a separate cross-process per-daemon validation slot."""

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time

from app.container_exports import assert_canonical_directory
from app.sandbox_cli import context_is_local
from app.validation_policy import RUNTIME_POLICY_ID, ValidationUnavailable, valid_context_name, valid_image_id

WAIT_SECONDS = 30
HEX = re.compile(r"[0-9a-f]{64}\Z")
NONCE = re.compile(r"[0-9a-f]{32}\Z")


def state_root():
    user = hashlib.sha256(str(Path.home()).encode()).hexdigest()[:16]
    return Path(tempfile.gettempdir()).resolve() / ("agenthub-container-validation-" + user)


def _private_directory(path):
    path.mkdir(mode=0o700, exist_ok=True)
    assert_canonical_directory(path)
    info = path.stat()
    if os.name != "nt" and (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077):
        raise ValidationUnavailable("cleanup_required: container state is not private.")


def _regular(path):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or getattr(info, "st_file_attributes", 0) & 0x400
            or os.name != "nt" and (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077)):
        raise ValidationUnavailable("cleanup_required: invalid private journal.")
    return info


def process_identity(pid):
    """A PID alone cannot identify an owner; permission errors remain unknown."""
    if not isinstance(pid, int) or pid <= 0:
        raise ValidationUnavailable("cleanup_required: invalid process identity.")
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            if ctypes.get_last_error() in {87, 1168}: return None
            raise ValidationUnavailable("cleanup_required: process ownership is unknown.")
        try:
            creation, exit_time, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
            if not kernel.GetProcessTimes(handle, *[ctypes.byref(t) for t in (creation, exit_time, kernel_time, user_time)]):
                raise ValidationUnavailable("cleanup_required: process ownership is unknown.")
            return str((creation.dwHighDateTime << 32) | creation.dwLowDateTime)
        finally: kernel.CloseHandle(handle)
    try:
        value = Path(f"/proc/{pid}/stat").read_text()
        start = value[value.rindex(")") + 2:].split()[19]
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        return boot + ":" + start
    except FileNotFoundError:
        return None
    except (OSError, IndexError, ValueError) as exc:
        raise ValidationUnavailable("cleanup_required: process ownership is unknown.") from exc


def owner_reclaimable(record):
    current = process_identity(record["ownerPid"])
    if current is None: return True
    if current != record["ownerStart"]: return False  # PID reuse is ambiguous; never guess
    return time.time() > record["expiresAt"]


@dataclass(frozen=True)
class OwnedContainer:
    container_id: str
    operation_id: str
    context_name: str
    journal_path: Path


@dataclass(frozen=True)
class ValidationSlot:
    directory: Path

    def journal_path(self, operation_id):
        if not NONCE.fullmatch(operation_id):
            raise ValidationUnavailable("cleanup_required: invalid operation identity.")
        return self.directory / (operation_id + ".json")

    def load(self, path):
        try:
            if path.parent != self.directory or not NONCE.fullmatch(path.stem) or path.suffix != ".json":
                raise ValueError("journal path")
            if _regular(path).st_size > 64 * 1024: raise ValueError("journal budget")
            value = json.loads(path.read_text(encoding="utf-8"))
            required = {"schemaVersion", "operationId", "contextName", "contextFingerprint", "imageId", "recipeFingerprint",
                        "profile", "taskRunId", "adapterRunId", "executionAttemptId", "generationFingerprint", "inputDir",
                        "ownerPid", "ownerStart", "expiresAt", "containerId", "state", "runtimePolicyId", "daemonFingerprint",
                        "endpoint", "createAttempted"}
            if (not isinstance(value, dict) or set(value) != required or value["schemaVersion"] != "agenthub.container_journal.v1"
                    or value["operationId"] != path.stem or value["runtimePolicyId"] != RUNTIME_POLICY_ID
                    or not valid_context_name(value["contextName"]) or not valid_image_id(value["imageId"])
                    or not context_is_local(value["endpoint"]) or type(value["createAttempted"]) is not bool
                    or not all(HEX.fullmatch(str(value[k])) for k in ("contextFingerprint", "recipeFingerprint", "generationFingerprint", "daemonFingerprint"))
                    or value["daemonFingerprint"] != self.directory.name
                    or value["containerId"] is not None and not HEX.fullmatch(str(value["containerId"]))
                    or value["inputDir"] != str(self.directory / path.stem / "input")
                    or type(value["ownerPid"]) is not int or not isinstance(value["ownerStart"], str)
                    or type(value["expiresAt"]) not in {float, int} or not 0 < value["expiresAt"] < 1e12
                    or value["state"] not in {"reserved", "creating", "created", "running", "exporting", "cleanup_required"}):
                raise ValueError("journal contents")
            return value
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ValidationUnavailable("cleanup_required: invalid private journal.") from exc

    def save(self, record):
        path = self.journal_path(record["operationId"])
        temporary = path.with_suffix(".pending")
        fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(record, stream, separators=(",", ":"), allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists(): _regular(path)
        os.replace(temporary, path)
        return path

    def pending_journals(self):
        records = []
        entries = list(self.directory.iterdir())
        if len(entries) > 16: raise ValidationUnavailable("cleanup_required: state budget exceeded.")
        for path in entries:
            if path.name == "capacity.lock": continue
            if path.suffix == ".json": records.append((path, self.load(path)))
            elif path.suffix == ".pending":
                # Never trust partial bytes. A valid prior intention remains
                # authoritative; owner expiry is checked before discarding it.
                if not NONCE.fullmatch(path.stem) or not path.with_suffix(".json").exists():
                    raise ValidationUnavailable("cleanup_required: interrupted private journal write.")
                _regular(path)
                self.load(path.with_suffix(".json"))
            elif not path.is_dir() or not NONCE.fullmatch(path.name):
                raise ValidationUnavailable("cleanup_required: unknown private state.")
            elif not self.journal_path(path.name).exists():
                raise ValidationUnavailable("cleanup_required: orphan input directory.")
        return records

    def discard_interrupted_update(self, path):
        self.load(path)
        pending = path.with_suffix(".pending")
        if pending.exists():
            _regular(pending)
            pending.unlink()  # exact private operation file, never an authority source


@contextmanager
def acquire_validation_slot(context_fingerprint, cancelled):
    if not isinstance(context_fingerprint, str) or not HEX.fullmatch(context_fingerprint):
        raise ValidationUnavailable("Invalid daemon capacity identity.")
    root = state_root()
    _private_directory(root)
    directory = root / context_fingerprint
    _private_directory(directory)
    path = directory / "capacity.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    stream = os.fdopen(fd, "r+b")
    release = None
    started = time.monotonic()
    try:
        _regular(path)
        if path.stat().st_size == 0:
            stream.write(b"0"); stream.flush()
        while True:
            if cancelled.is_set(): raise ValidationUnavailable("cancelled: capacity wait interrupted.")
            try:
                if os.name == "nt":
                    import msvcrt
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    def release():
                        stream.seek(0)
                        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    release = lambda: fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
                break
            except OSError:
                if time.monotonic() - started >= WAIT_SECONDS:
                    raise ValidationUnavailable("capacity_unavailable: validation slot is busy.")
                cancelled.wait(0.05)
        yield ValidationSlot(directory)
    finally:
        if release: release()
        stream.close()
