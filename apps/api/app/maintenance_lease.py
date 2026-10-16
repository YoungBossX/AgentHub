"""Cross-process shared API / exclusive maintenance lease; no stale lock deletion."""
import os
from contextlib import contextmanager
from pathlib import Path


class MaintenanceBusy(RuntimeError):
    pass


@contextmanager
def database_lease(path: Path, *, exclusive: bool):
    path = Path(path).absolute()
    lock = path.with_name(path.name + ".maintenance.lock")
    if lock.resolve() != lock or (lock.exists() and (not lock.is_file() or lock.stat().st_nlink != 1)):
        raise MaintenanceBusy("Maintenance lease must be a regular, unlinked local file.")
    lock.parent.mkdir(parents=True, exist_ok=True)
    stream = lock.open("a+b")
    release = None
    try:
        if os.name == "nt":
            import ctypes
            import msvcrt
            from ctypes import wintypes

            class Overlapped(ctypes.Structure):
                _fields_ = [("Internal", ctypes.c_size_t), ("InternalHigh", ctypes.c_size_t),
                            ("Offset", wintypes.DWORD), ("OffsetHigh", wintypes.DWORD), ("hEvent", wintypes.HANDLE)]

            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.LockFileEx.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(Overlapped)]
            kernel.UnlockFileEx.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(Overlapped)]
            kernel.LockFileEx.restype = kernel.UnlockFileEx.restype = wintypes.BOOL
            handle, overlapped = msvcrt.get_osfhandle(stream.fileno()), Overlapped()
            if not kernel.LockFileEx(handle, 1 | (2 if exclusive else 0), 0, 1, 0, ctypes.byref(overlapped)):
                raise MaintenanceBusy("API or another maintenance process owns this database; stop it first.")
            release = lambda: kernel.UnlockFileEx(handle, 0, 1, 0, ctypes.byref(overlapped))
        else:
            import fcntl
            try:
                fcntl.flock(stream, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise MaintenanceBusy("API or another maintenance process owns this database; stop it first.") from exc
            release = lambda: fcntl.flock(stream, fcntl.LOCK_UN)
        yield
    finally:
        if release:
            release()
        stream.close()
