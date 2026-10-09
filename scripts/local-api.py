"""Run a fixed local API with graceful shutdown over its launcher's stdin pipe."""

import argparse
import asyncio
import os
import sys
import threading
from pathlib import Path

import uvicorn


def launcher_input():
    """Keep the control pipe private; Git/CLI children must receive null stdin."""
    control_fd = os.dup(sys.stdin.fileno())
    os.set_inheritable(control_fd, False)
    with open(os.devnull, "rb") as null_input:
        # Only the private control descriptor must be non-inheritable. POSIX
        # closes non-inheritable stdin at exec, instead of delivering null EOF.
        os.dup2(null_input.fileno(), sys.stdin.fileno(), inheritable=True)
    if sys.platform == "win32":
        # subprocess uses GetStdHandle on Windows, independently of Python's
        # sys.stdin object. Update it as well as the CRT descriptor.
        import ctypes
        import msvcrt
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.SetStdHandle.argtypes = [wintypes.DWORD, wintypes.HANDLE]
        kernel.SetStdHandle.restype = wintypes.BOOL
        if not kernel.SetStdHandle(-10, msvcrt.get_osfhandle(sys.stdin.fileno())):
            raise ctypes.WinError(ctypes.get_last_error())
    return os.fdopen(control_fd, "r", encoding="utf-8")


async def serve(service: str, port: int, ready_token: str) -> None:
    directory = Path(__file__).resolve().parents[1] / "apps" / service
    # The Node launcher fixes cwd as well, so .env and relative SQLite paths
    # retain the same meaning as the existing development command.
    sys.path.insert(0, str(directory))
    server = uvicorn.Server(uvicorn.Config(
        "app.main:app", host="127.0.0.1", port=port,
        timeout_graceful_shutdown=5,
    ))
    loop = asyncio.get_running_loop()
    control = launcher_input()

    def watch_launcher() -> None:
        with control:
            for line in control:
                if line.strip() == "stop":
                    break
        # EOF also stops the API if the owning launcher disappears.
        if not loop.is_closed():
            loop.call_soon_threadsafe(setattr, server, "should_exit", True)

    threading.Thread(target=watch_launcher, daemon=True).start()

    async def report_ready() -> None:
        while not server.started and not server.should_exit:
            await asyncio.sleep(0.05)
        if server.started:
            print(f"[agenthub-ready:{ready_token}]", flush=True)

    reporter = asyncio.create_task(report_ready())
    try:
        await server.serve()
    finally:
        reporter.cancel()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--service", choices=("api", "demo-api"), required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--ready-token", required=True)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    asyncio.run(serve(args.service, args.port, args.ready_token))
