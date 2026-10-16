"""Platform-owned checks; never import target tests or start an HTTP listener.

Audit guards reduce accidental side effects. They are not an OS security sandbox.
"""

import contextlib
import asyncio
import importlib
import json
import os
from pathlib import Path
import sys
import sysconfig

SCHEMA = "agenthub.backend_contract.v2"
PREFIX = "AGENTHUB_BACKEND_RESULT="


def install_guards(project, data):
    read_roots = [project, data, Path(sys.base_prefix) / "DLLs"]
    paths = sysconfig.get_paths()
    read_roots.extend(Path(paths[key]).resolve() for key in ("stdlib", "platstdlib", "purelib", "platlib"))
    # sysconfig includes script/bin locations; do not permit reading arbitrary
    # checkout siblings merely because the interpreter lives in a shared venv.
    read_roots = [p for p in read_roots if p.is_dir()]

    def path_allowed(value, *, write=False):
        if isinstance(value, int):
            return value in {0, 1, 2}
        path = Path(os.fsdecode(value)).resolve()
        roots = [data] if write else read_roots
        return any(path == root or path.is_relative_to(root) for root in roots)

    def audit(event, args):
        if event in {"socket.__new__", "socket.connect", "socket.connect_ex", "socket.bind", "socket.getaddrinfo",
                     "socket.sendto", "socket.sendmsg",
                     "subprocess.Popen", "os.system", "os.posix_spawn", "os.fork", "os.forkpty",
                     "os.exec", "os.startfile", "os.kill", "os.killpg", "ctypes.dlopen", "ctypes.dlsym"}:
            raise PermissionError("Backend validation forbids network, process and native-loader side effects.")
        if event == "open":
            path, mode, flags = args
            write = (isinstance(mode, str) and any(c in mode for c in "wax+")) or bool(
                flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if not path_allowed(path, write=write):
                raise PermissionError("Backend validation file access is outside the temporary scope.")
        if event in {"os.listdir", "os.scandir", "os.chdir"} and not path_allowed(args[0] or "."):
            raise PermissionError("Backend validation directory access is outside the temporary scope.")
        if event in {"os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.truncate", "os.utime"}:
            if not path_allowed(args[0], write=True):
                raise PermissionError("Backend validation writes are limited to disposable data.")
        if event in {"os.rename", "os.link", "os.symlink"}:
            raise PermissionError("Backend validation does not allow file relocation or links.")

    sys.addaudithook(audit)


def api_checks(project):
    # Load the trusted HTTP client before importing any target module. Its in-
    # process transport exercises real ASGI handlers without opening sockets.
    from fastapi.testclient import TestClient
    from fastapi import FastAPI

    # Windows initializes asyncio's private wake-up socket pair using loopback
    # TCP. Allocate the trusted loop before network denial; target code never
    # gets a window with networking enabled.
    loop = asyncio.new_event_loop()
    try:
        yield from _api_checks(project, loop, FastAPI, TestClient)
    finally:
        if not loop.is_closed():
            loop.close()


def _api_checks(project, loop, FastAPI, TestClient):
    install_guards(project, Path(sys.argv[3]).resolve())
    sys.path.insert(0, str(project))
    application = importlib.import_module("app.main").app
    assert isinstance(application, FastAPI), "Expected a FastAPI application."
    with TestClient(application, backend_options={"loop_factory": lambda: loop}) as client:
        response = client.get("/health")
        assert response.status_code == 200 and response.json() == {"status": "ok", "service": "agenthub-demo-api"}, "Health contract failed."
        yield "api.health"

        response = client.get("/contacts")
        assert response.status_code == 200 and isinstance(response.json(), list), "Contact list failed."
        initial = response.json()
        assert {c["email"] for c in initial} >= {"ada@example.com", "grace@example.com"}, "Seed contacts missing."
        assert all(isinstance(c.get("id"), str) and c.get("name") and c.get("email") for c in initial), "Contact schema failed."
        yield "api.contacts_list"

        payload = {"name": "Katherine Johnson", "email": "validation-katherine@example.com", "company": "Flight Dynamics", "status": "active"}
        response = client.post("/contacts", json=payload)
        assert response.status_code == 201, "Create must return 201."
        created = response.json()
        assert isinstance(created.get("id"), str) and created["id"].startswith("contact-"), "Created contact has no ID."
        assert all(created.get(key) == value for key, value in payload.items()), "Created fields differ."
        assert client.get("/contacts").json() == initial + [created], "Create was not persisted or modified prior contacts."
        yield "api.create"

        for invalid in ({}, {"name": "", "email": "valid@example.com"}, {"name": "Valid", "email": "bad-email"},
                        {"name": "x" * 81, "email": "valid@example.com"}):
            assert client.post("/contacts", json=invalid).status_code == 422, "Invalid contact was accepted."
        assert client.get("/contacts").json() == initial + [created], "Invalid requests changed contacts."
        yield "api.validation"

        response = client.post("/contacts", json=payload)
        assert response.status_code == 409, "Duplicate email was accepted."
        assert client.get("/contacts").json() == initial + [created], "Duplicate request changed contacts."
        yield "api.duplicate"

        origin = "http://127.0.0.1:62947"
        response = client.options("/contacts", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})
        assert response.status_code == 200 and response.headers.get("access-control-allow-origin") == origin, "Local preview CORS failed."
        response = client.options("/contacts", headers={"Origin": "https://untrusted.invalid", "Access-Control-Request-Method": "GET"})
        assert response.headers.get("access-control-allow-origin") != "https://untrusted.invalid", "External origin unexpectedly trusted."
        yield "api.cors"

        response = client.get("/openapi.json")
        assert response.status_code == 200, "OpenAPI unavailable."
        paths = response.json()["paths"]
        assert "get" in paths["/health"] and {"get", "post"} <= set(paths["/contacts"]), "OpenAPI routes missing."
        yield "api.openapi"

        boundary = {"name": "n" * 80, "email": "e" * 108 + "@example.com", "company": "c" * 120, "status": "s" * 40}
        response = client.post("/contacts", json=boundary)
        assert response.status_code == 201, "Declared maximum field lengths must be accepted."
        maximum = response.json()
        assert all(maximum.get(key) == value for key, value in boundary.items()), "Boundary fields were altered."
        stable = client.get("/contacts").json()
        for key, value in boundary.items():
            invalid = {**boundary, key: value + "x"}
            assert client.post("/contacts", json=invalid).status_code == 422, f"Overlong {key} was accepted."
            assert client.get("/contacts").json() == stable, "Rejected field overflow changed records."
        yield "api.field_boundaries"

        valid = {"name": "Typed contact", "email": "typed@example.invalid"}
        for invalid in ([], None, {**valid, "name": []}, {**valid, "name": None},
                        {**valid, "email": None}, {**valid, "email": "has space@example.com"},
                        {**valid, "company": {}}, {**valid, "status": []}):
            assert client.post("/contacts", json=invalid).status_code == 422, "Invalid body/field type was accepted."
            assert client.get("/contacts").json() == stable, "Invalid body changed records."
        assert client.post("/contacts", content=b'{"name":', headers={"Content-Type": "application/json"}).status_code == 422, "Malformed JSON was accepted."
        assert client.get("/contacts").json() == stable, "Malformed JSON changed records."
        yield "api.invalid_types"

        identifiers = {contact["id"] for contact in stable}
        appended = []
        for number in range(2):
            payload = {"name": f"Default contact {number}", "email": f"default-{number}@example.invalid"}
            response = client.post("/contacts", json=payload)
            assert response.status_code == 201, "Valid minimal contact was rejected."
            contact = response.json()
            assert isinstance(contact.get("id"), str) and contact["id"] and contact["id"] not in identifiers, "Contact IDs must be unique strings."
            assert contact.get("company") is None and contact.get("status") == "lead", "Declared defaults were not preserved."
            assert all(contact.get(key) == value for key, value in payload.items()), "Contact values changed."
            identifiers.add(contact["id"])
            appended.append(contact)
        stable += appended
        assert client.get("/contacts").json() == stable, "Multiple creates overwrote/reordered records."
        assert client.get("/contacts").json() == stable, "List reads changed identities or values."
        yield "api.unique_identity"

        response = client.post("/contacts", json={"name": "Duplicate seed", "email": "ada@example.com"})
        assert response.status_code == 409, "Seeded duplicate email was accepted."
        assert client.get("/contacts").json() == stable, "Seed duplicate request changed records."
        yield "api.seed_duplicate"

        for method, path in (("PUT", "/contacts"), ("DELETE", "/contacts"), ("POST", "/health")):
            assert client.request(method, path).status_code == 405, "Unsupported mutation method was accepted."
            assert client.get("/contacts").json() == stable, "Unsupported method changed records."
        yield "api.method_contract"


def main():
    stage, raw_project, raw_data = sys.argv[1:]
    project, data = Path(raw_project).resolve(), Path(raw_data).resolve()
    checks, error = [], None
    try:
        with contextlib.redirect_stdout(sys.stderr):
            if stage == "check":
                for source in sorted((project / "app").rglob("*.py")):
                    compile(source.read_bytes(), str(source), "exec", dont_inherit=True)
                checks.append({"id": "python.syntax", "status": "passed"})
            elif stage == "test":
                checks.extend({"id": name, "status": "passed"} for name in api_checks(project))
            else:
                raise ValueError("Unsupported backend validation stage.")
    except Exception as exc:
        error = f"{type(exc).__name__}: {str(exc)[:800]}"
    print(PREFIX + json.dumps({"schemaVersion": SCHEMA, "stage": stage, "checks": checks, "error": error}), flush=True)
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
