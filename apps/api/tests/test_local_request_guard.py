import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.local_request_guard import LocalRequestGuard, is_loopback_host


@pytest.fixture
def guarded_client():
    app = FastAPI()
    changes = []
    app.add_middleware(LocalRequestGuard, frontend_origins={"http://127.0.0.1:3000"})

    @app.api_route("/control", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def control():
        changes.append("entered")
        return {"ok": True}

    with TestClient(app) as client:
        yield client, changes


@pytest.mark.parametrize("origin", ["https://untrusted.invalid", "http://127.0.0.1:57860", "null", "http://127.0.0.1:3000.evil.test"])
@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
def test_untrusted_origins_never_enter_routes(guarded_client, origin, method):
    client, changes = guarded_client
    assert client.request(method, "/control", headers={"Origin": origin}).status_code == 403
    assert changes == []


@pytest.mark.parametrize("host", ["untrusted.invalid:8000", "127.0.0.1.evil.test", "localhost@evil.test", "localhost/path", "[::1]:99999"])
def test_untrusted_hosts_never_enter_routes(guarded_client, host):
    client, changes = guarded_client
    assert client.post("/control", headers={"Host": host}).status_code == 403
    assert changes == []


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_missing_control_header_never_enters_route(guarded_client, method):
    client, changes = guarded_client
    del client.headers["x-agenthub-control"]
    assert client.request(method, "/control", headers={"Origin": "http://127.0.0.1:3000"}).status_code == 403
    assert changes == []


def test_explicit_local_clients_and_trusted_workbench_remain_usable(guarded_client):
    client, changes = guarded_client
    assert client.post("/control").status_code == 200
    assert client.post("/control", headers={"Origin": "http://127.0.0.1:3000"}).status_code == 200
    assert len(changes) == 2


def test_actual_task_interrupt_rejects_preview_origin_without_side_effect(client, monkeypatch):
    from test_task_runs import db_from_override
    from sqlmodel import select
    from app.models import Task, TaskRun
    import app.main as main

    calls = []
    async def interrupt(run_id):
        calls.append(run_id)
    monkeypatch.setattr(main, "interrupt_supervised_task_run", interrupt)
    with db_from_override() as db:
        task = db.exec(select(Task)).first()
        run = TaskRun(task_id=task.id, agent_id=task.assigned_agent_id, state="queued", worktree_path="unused")
        db.add(run); db.commit(); run_id = run.id
    response = client.post(f"/task-runs/{run_id}/interrupt", headers={"Origin": "http://127.0.0.1:57860"})
    assert response.status_code == 403
    with db_from_override() as db:
        assert db.get(TaskRun, run_id).state == "queued"
    assert calls == []


@pytest.mark.parametrize("host", ["127.0.0.1:8000", "localhost:8000", "[::1]:8000"])
def test_loopback_hosts(host):
    assert is_loopback_host(host)


# Reuse the isolated lifecycle database, never a running developer Session.
from test_task_runs import client
