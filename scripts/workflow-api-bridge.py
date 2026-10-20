"""Fixed in-process ASGI transport for the trusted workflow browser harness."""
import asyncio
import contextlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient


def main():
    # Node writes UTF-8 JSON to the pipe. Isolated Python ignores
    # PYTHONIOENCODING and may otherwise use the Windows legacy code page.
    sys.stdin.reconfigure(encoding="utf-8", errors="strict")
    sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    project, data = (Path(value).resolve() for value in sys.argv[1:])
    spec = importlib.util.spec_from_file_location("workflow_guards", Path(__file__).with_name("demo-backend-check.py"))
    guards = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guards)
    loop = asyncio.new_event_loop()
    try:
        guards.install_guards(project, data)
        sys.path.insert(0, str(project))
        with contextlib.redirect_stdout(sys.stderr):
            application = importlib.import_module("app.main").app
            assert isinstance(application, FastAPI)
            client = TestClient(application, backend_options={"loop_factory": lambda: loop})
            client.__enter__()
        try:
            print(json.dumps({"ready": True}), flush=True)
            while line := sys.stdin.readline(8193):
                if len(line) > 8192:
                    raise ValueError("Request exceeds the fixed transport budget.")
                request = json.loads(line)
                method, path = request["method"], request["path"]
                if method not in {"GET", "POST"} or path != "/contacts":
                    raise ValueError("Undeclared workflow transport request.")
                with contextlib.redirect_stdout(sys.stderr):
                    response = client.request(method, path, json=request.get("body"))
                    body = response.json()
                result = json.dumps({"id": request["id"], "status": response.status_code, "body": body})
                if len(result) > 24000:
                    raise ValueError("Response exceeds the fixed transport budget.")
                print(result, flush=True)
        finally:
            with contextlib.redirect_stdout(sys.stderr):
                client.__exit__(None, None, None)
    finally:
        if not loop.is_closed():
            loop.close()


if __name__ == "__main__":
    main()
