"""Bounded file access for explicit user edits; no commands or directory creation.

Windows handles deny competing writes/deletes while an operation owns files and
deny renaming ancestor directories. POSIX uses no-follow descriptors, directory
observations and content rechecks; external programs must honor advisory locks.
"""

import os
from contextlib import ExitStack, contextmanager
from pathlib import Path

from app import task_run_scope as scope
from app.user_patch import MAX_FILE_BYTES, UserPatchConflict, UserPatchError, text_bytes, validate_path


def _windows_handle(path: Path, *, directory=False, write=False, create=False):
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    open_file = kernel.CreateFileW
    open_file.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                          wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    open_file.restype = wintypes.HANDLE
    # Directory pins allow normal child IO, but not directory replacement.
    access = 0 if directory else 0x80000000 | (0x40000000 | 0x10000 if write else 0)
    sharing = 3 if directory else 1
    flags = 0x00200000 | (0x02000000 if directory else 0)
    handle = open_file(str(path), access, sharing, None, 1 if create else 3, flags, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    return handle


@contextmanager
def _pin_directory(path: Path):
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        handle = _windows_handle(path, directory=True)
        close = ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle
        close.argtypes = [wintypes.HANDLE]
        try:
            yield
        finally:
            close(handle)
    else:
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            yield
        finally:
            os.close(descriptor)


def _open_file(path: Path, *, write: bool, create=False) -> int:
    if os.name == "nt":
        import msvcrt
        handle = _windows_handle(path, write=write, create=create)
        try:
            return msvcrt.open_osfhandle(handle, os.O_BINARY | (os.O_RDWR if write else os.O_RDONLY))
        except BaseException:
            import ctypes
            from ctypes import wintypes
            close = ctypes.WinDLL("kernel32").CloseHandle
            close.argtypes = [wintypes.HANDLE]
            close(handle)
            raise
    flags = (os.O_RDWR if write else os.O_RDONLY) | os.O_NOFOLLOW | os.O_NONBLOCK
    if create:
        flags |= os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o644)
    try:
        import fcntl
        fcntl.flock(fd, (fcntl.LOCK_EX if write else fcntl.LOCK_SH) | fcntl.LOCK_NB)
    except BaseException:
        os.close(fd)
        raise
    return fd


def _delete_open_file(fd: int, path: Path):
    if os.name == "nt":
        import ctypes
        import msvcrt
        from ctypes import wintypes
        delete = ctypes.WinDLL("kernel32", use_last_error=True).SetFileInformationByHandle
        delete.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
        delete.restype = wintypes.BOOL
        disposition = wintypes.BOOL(True)
        if not delete(msvcrt.get_osfhandle(fd), 4, ctypes.byref(disposition), ctypes.sizeof(disposition)):
            raise ctypes.WinError(ctypes.get_last_error())
    else:
        os.unlink(path)


class UserEditFiles:
    def __init__(self, root: Path):
        self.root = root
        self.stack = ExitStack()
        self.parents = {}
        self.files = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        for fd in self.files.values():
            if fd is not None:
                os.close(fd)
        self.files.clear()
        self.stack.close()

    def _parents(self, relative: str):
        validate_path(relative)
        path = self.root / relative
        if relative not in self.parents:
            _, observations = scope._lexical_worktree_root(path.parent)
            for parent, _, _ in observations:
                self.stack.enter_context(_pin_directory(parent))
            scope._require_path_observations(observations)
            # Reject casing/8.3 aliases by checking actual directory entries.
            parent = self.root
            for component in relative.split("/"):
                if os.path.lexists(parent / component) and component not in os.listdir(parent):
                    raise UserPatchError("File paths must use their exact on-disk names.")
                parent /= component
            self.parents[relative] = observations
        scope._require_path_observations(self.parents[relative])
        return path

    def read(self, relative: str, *, write=False) -> bytes | None:
        try:
            path = self._parents(relative)
            observation = scope._path_observation(path, absent_allowed=True)
            if observation is None:
                if relative in self.files and self.files[relative] is not None:
                    raise UserPatchConflict("File was removed during editing.")
                return None
            if observation[0] != "file":
                raise UserPatchError("User edits require regular files, without links.")
            scope._require_no_named_streams(path)
            if relative not in self.files:
                self.files[relative] = _open_file(path, write=write)
            fd = self.files[relative]
            if fd is None:
                raise UserPatchConflict("A deleted file reappeared during editing.")
            identity = scope._descriptor_observation(fd, require_single_link=True)
            if identity != observation or os.fstat(fd).st_size > MAX_FILE_BYTES:
                raise UserPatchError("File identity or size is unsafe for editing.")
            self._parents(relative)
            os.lseek(fd, 0, os.SEEK_SET)
            before_stat = os.fstat(fd)
            content = bytearray()
            while len(content) <= MAX_FILE_BYTES:
                chunk = os.read(fd, min(65536, MAX_FILE_BYTES + 1 - len(content)))
                if not chunk:
                    break
                content.extend(chunk)
            after_stat = os.fstat(fd)
            self._parents(relative)
            scope._require_no_named_streams(path)
            if (scope._path_observation(path) != identity
                    or scope._descriptor_observation(fd, require_single_link=True) != identity
                    or (before_stat.st_size, before_stat.st_mtime_ns) != (after_stat.st_size, after_stat.st_mtime_ns)):
                raise UserPatchConflict("File changed while it was read.")
            text_bytes(bytes(content))
            return bytes(content)
        except (OSError, scope._SnapshotCaptureError) as exc:
            raise UserPatchError("File is unavailable, busy or has an unsafe filesystem binding.") from exc

    def write(self, relative: str, before: bytes | None, after: bytes | None):
        if self.read(relative, write=True) != before:
            raise UserPatchConflict("File changed after preparation.")
        path = self._parents(relative)
        if before is None:
            self.files[relative] = _open_file(path, write=True, create=True)
        fd = self.files[relative]
        if after is None:
            _delete_open_file(fd, path)
            os.close(fd)
            self.files[relative] = None
        else:
            text_bytes(after)
            os.lseek(fd, 0, os.SEEK_SET)
            remaining = memoryview(after)
            while remaining:
                count = os.write(fd, remaining)
                if not count:
                    raise OSError("File write made no progress.")
                remaining = remaining[count:]
            os.ftruncate(fd, len(after))
            os.fsync(fd)
        if self.read(relative, write=True) != after:
            raise UserPatchConflict("Written content could not be verified.")

    def restore_mode(self, relative: str, mode: int):
        if os.name != "nt":
            self._parents(relative)
            os.fchmod(self.files[relative], mode)
