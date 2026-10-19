"""Own validation subprocess trees; no process-name scans or unrelated kills."""

import os
import signal
import subprocess


class _WindowsJob:
    def __init__(self):
        import ctypes
        from ctypes import wintypes as w
        self.ctypes, self.w = ctypes, w
        self.kernel = k = ctypes.WinDLL("kernel32", use_last_error=True)
        class Basic(ctypes.Structure):
            _fields_ = [("processTime", ctypes.c_longlong), ("jobTime", ctypes.c_longlong), ("flags", w.DWORD),
                ("minWorkingSet", ctypes.c_size_t), ("maxWorkingSet", ctypes.c_size_t), ("activeProcesses", w.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", w.DWORD), ("scheduling", w.DWORD)]
        class Counters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in ("readOps", "writeOps", "otherOps", "readBytes", "writeBytes", "otherBytes")]
        class Extended(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", Counters), ("processMemory", ctypes.c_size_t), ("jobMemory", ctypes.c_size_t),
                       ("peakProcessMemory", ctypes.c_size_t), ("peakJobMemory", ctypes.c_size_t)]
        k.CreateJobObjectW.argtypes, k.CreateJobObjectW.restype = [ctypes.c_void_p, w.LPCWSTR], w.HANDLE
        k.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        k.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        k.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
        k.CloseHandle.argtypes = [w.HANDLE]
        self.handle = k.CreateJobObjectW(None, None)
        if not self.handle: raise ctypes.WinError(ctypes.get_last_error())
        limits = Extended(); limits.basic.flags = 0x2000  # KILL_ON_JOB_CLOSE; no breakaway
        if not k.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.get_last_error(); self.close(); raise ctypes.WinError(error)

    def attach_and_resume(self, process):
        c, w, k = self.ctypes, self.w, self.kernel
        if not k.AssignProcessToJobObject(self.handle, w.HANDLE(int(process._handle))):
            raise c.WinError(c.get_last_error())
        # Popen closes the primary thread handle. Enumerate only threads owned
        # by this still-suspended PID, then resume after job assignment.
        class ThreadEntry(c.Structure):
            _fields_ = [("size", w.DWORD), ("usage", w.DWORD), ("id", w.DWORD), ("owner", w.DWORD),
                       ("basePriority", w.LONG), ("deltaPriority", w.LONG), ("flags", w.DWORD)]
        k.CreateToolhelp32Snapshot.argtypes, k.CreateToolhelp32Snapshot.restype = [w.DWORD, w.DWORD], w.HANDLE
        k.Thread32First.argtypes = k.Thread32Next.argtypes = [w.HANDLE, c.POINTER(ThreadEntry)]
        k.OpenThread.argtypes, k.OpenThread.restype = [w.DWORD, w.BOOL, w.DWORD], w.HANDLE
        k.ResumeThread.argtypes, k.ResumeThread.restype = [w.HANDLE], w.DWORD
        snapshot = k.CreateToolhelp32Snapshot(4, 0)
        if snapshot == w.HANDLE(-1).value: raise c.WinError(c.get_last_error())
        try:
            entry = ThreadEntry(); entry.size = c.sizeof(entry)
            valid, threads = k.Thread32First(snapshot, c.byref(entry)), []
            while valid:
                if entry.owner == process.pid: threads.append(entry.id)
                valid = k.Thread32Next(snapshot, c.byref(entry))
            if len(threads) != 1: raise OSError("Suspended validation process has an unexpected primary thread.")
            handle = k.OpenThread(2, False, threads[0])  # THREAD_SUSPEND_RESUME
            if not handle: raise c.WinError(c.get_last_error())
            try:
                if k.ResumeThread(handle) != 1: raise OSError("Validation primary thread did not resume exactly once.")
            finally: k.CloseHandle(handle)
        finally: k.CloseHandle(snapshot)

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None

    def terminate(self):
        if self.handle and not self.kernel.TerminateJobObject(self.handle, 1):
            raise self.ctypes.WinError(self.ctypes.get_last_error())


def start_process(argv, **kwargs):
    kwargs["shell"] = False
    if os.name != "nt":
        kwargs["start_new_session"] = True
        return subprocess.Popen(argv, **kwargs)
    job = _WindowsJob()
    process = None
    try:
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | 0x4 | 0x08000000  # SUSPENDED, NO_WINDOW
        process = subprocess.Popen(argv, **kwargs)
        job.attach_and_resume(process)
        process._agenthub_validation_job = job
        return process
    except BaseException:
        if process is not None:
            process.kill(); process.wait(timeout=10)
            for stream in (process.stdout, process.stderr):
                if stream is not None: stream.close()
        job.close()
        raise


def stop_process(process):
    if os.name == "nt":
        job = getattr(process, "_agenthub_validation_job", None)
        if job is None: raise OSError("Validation subprocess has no owned process job.")
        try: job.terminate()
        finally: job.close()
    else:
        try: os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError: pass
    if process.poll() is None: process.kill()
    process.wait(timeout=10)
