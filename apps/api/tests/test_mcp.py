import asyncio
import json
import subprocess
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlmodel import select

from app.models import Session, Task, TaskRunEvent, TargetLock, Workspace, utc_now
from app.mcp_connections import (BINDING, TOKEN_ENV, capture_binding, config_arguments, connection,
    save_connection, verify_binding)
from app.mcp_gateway import issue_token, issue_probe, revoke_token, revoke_run, snapshot_documents
from app.routes.mcp import ConnectionRequest
from app.task_runs import create_task_run, capture_task_run_scope_baseline, persist_task_run_execution_access_binding
from app.run_engine import _prepare_claimed_task_run_for_adapter, _claim_scope_execution_attempt
from app.guardrails import evaluate_command
from app.codex_adapter import CodexAdapter
from app.adapters import AgentRunRequest
from app.skills import SkillError
from test_task_runs import client, db_from_override, task_id
from test_codex_adapter import FakeCodexProcess


def config(enabled=True, tools=None, revision=0, agents=None):
    return ConnectionRequest(enabled=enabled, tools=tools if tools is not None else ["list_documents", "read_document"],
        defaultAgents=agents if agents is not None else ["frontend"], expectedRevision=revision)


@pytest.fixture
def running(client, tmp_path):
    with db_from_override() as db:
        task = db.get(Task, task_id()); session = db.get(Session, task.session_id)
        root = tmp_path / "source"; source = root / "apps/demo/src/App.tsx"
        source.parent.mkdir(parents=True); source.write_text('export const title = "example"', encoding="utf-8")
        (root / "apps/demo/README.md").write_text("Frontend documentation\napi_key=private_fixture", encoding="utf-8")
        backend = root / "apps/demo-api"; backend.mkdir(parents=True)
        (backend / "README.md").write_text("Backend API: GET /contacts", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "-c", "core.hooksPath=", "commit", "-qm", "mcp fixture"], check=True)
        session.worktree_path = str(root); task.plan_json = json.dumps({"targetId": "demo-frontend", "target": "demo_heading_text", "targetText": "Example"})
        db.add_all([session, task]); db.commit()
        save_connection(db, session.workspace_id, config(), )
        run = create_task_run(db, task.id)
        assert _prepare_claimed_task_run_for_adapter(db, run, run.runner_id)
        attempt = _claim_scope_execution_attempt(db, run.id)
        capture_task_run_scope_baseline(db, run.id, execution_attempt_id=attempt)
        persist_task_run_execution_access_binding(db, run.id, access_mode="write", execution_attempt_id=attempt)
        db.refresh(run)
        token = issue_token(db, run, json.loads(run.metrics_json)[BINDING])
        try:
            yield client, db, run, token, root
        finally:
            revoke_run(run.id)


def call(client, token, method, params=None, request_id=1, **headers):
    return client.post("/mcp/agenthub-docs", headers={"Authorization": "Bearer " + token, **headers},
        json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})


def output(response):
    assert response.status_code == 200, response.text
    return json.loads(response.json()["result"]["content"][0]["text"])


def test_real_json_rpc_handshake_discovery_read_and_durable_receipts(running):
    client, db, run, token, _ = running
    init = call(client, token, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "Test", "version": "1"}})
    assert init.json()["result"]["serverInfo"]["name"] == "agenthub_docs"
    notification = client.post("/mcp/agenthub-docs", headers={"Authorization": "Bearer " + token}, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert notification.status_code == 202
    tools = call(client, token, "tools/list").json()["result"]["tools"]
    assert [t["name"] for t in tools] == ["list_documents", "read_document"]
    assert all(t["annotations"]["readOnlyHint"] for t in tools)
    docs = output(call(client, token, "tools/call", {"name": "list_documents"}))
    assert len(docs) == 2 and all("text" not in doc for doc in docs)
    read = output(call(client, token, "tools/call", {"name": "read_document", "arguments": {"documentId": docs[0]["documentId"]}}))
    assert "documentation" in read["text"] and "private_fixture" not in read["text"]
    db.expire_all()
    evidence = client.get(f"/task-runs/{run.id}/mcp").json()
    assert len(evidence["events"]) == 3
    assert token not in json.dumps(evidence)
    assert all("sha256" in item for item in evidence["events"][1]["payload"]["result"])


@pytest.mark.parametrize("change", ["terminal", "runner", "generation", "lease", "lock", "queue", "revocation", "credential"])
def test_calls_fail_when_execution_or_policy_is_no_longer_current(running, change):
    client, db, run, token, _ = running
    if change == "terminal": run.state = "completed"
    elif change == "runner": run.runner_id = "other"
    elif change == "generation":
        metrics = json.loads(run.metrics_json); metrics["taskRunExecutionAccessBinding"]["executionAttemptId"] = "other"; run.metrics_json = json.dumps(metrics)
    elif change == "lease": run.lease_expires_at = utc_now() - timedelta(seconds=1)
    elif change == "lock":
        lock = db.exec(select(TargetLock).where(TargetLock.task_run_id == run.id)).first(); lock.state = "released"; db.add(lock)
    elif change == "queue":
        from app.models import SessionQueueEntry
        queue = db.exec(select(SessionQueueEntry).where(SessionQueueEntry.task_run_id == run.id)).first(); queue.state = "failed"; db.add(queue)
    elif change == "revocation":
        workspace_id = db.get(Session, db.get(Task, run.task_id).session_id).workspace_id
        save_connection(db, workspace_id, config(enabled=False, revision=1))
    elif change == "credential": revoke_run(run.id)
    db.add(run); db.commit()
    assert call(client, token, "tools/list").status_code in {401, 403}


def test_expired_tokens_and_probe_tokens_cannot_read_documents(running, monkeypatch):
    import app.mcp_gateway as module
    client, db, run, token, _ = running
    probe = issue_probe("workspace", ["read_document"])
    try:
        assert call(client, probe, "tools/call", {"name": "read_document", "arguments": {"documentId": "anything"}}).json()["error"]["code"] == -32602
    finally: revoke_token(probe)
    now = module.time.monotonic()
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: now + 601))
    assert call(client, token, "tools/list").status_code == 401


@pytest.mark.parametrize("params", [{"name": "delete_file", "arguments": {"path": ".env"}},
    {"name": "read_document", "arguments": {"path": ".env"}}, {"name": "list_documents", "arguments": {"url": "https://example.invalid"}}])
def test_unregistered_tools_and_arbitrary_paths_are_rejected(running, params):
    client, _, _, token, _ = running
    assert call(client, token, "tools/call", params).json()["error"]["code"] == -32602


def test_unknown_document_returns_failed_receipt_without_exposing_input(running):
    client, _, run, token, _ = running
    result = call(client, token, "tools/call", {"name": "read_document", "arguments": {"documentId": "../../private/.env"}})
    assert result.json()["result"]["isError"]
    evidence = client.get(f"/task-runs/{run.id}/mcp").json()
    assert evidence["events"][0]["payload"]["status"] == "failed"
    assert "private/.env" not in json.dumps(evidence)


def test_request_origin_size_protocol_batch_and_auth_boundaries(running):
    client, _, _, token, _ = running
    assert call(client, token, "tools/list", Origin="https://untrusted.invalid").status_code == 403
    assert call(client, token, "tools/list", **{"MCP-Protocol-Version": "unsupported"}).status_code == 400
    assert call(client, "invalid", "tools/list").status_code == 401
    assert client.get("/mcp/agenthub-docs").status_code == 405
    assert client.post("/mcp/agenthub-docs", headers={"Authorization": "Bearer " + token}, json=[{}]).status_code == 400
    assert client.post("/mcp/agenthub-docs", headers={"Authorization": "Bearer " + token}, content="x" * 8193).status_code == 413


def test_document_snapshot_is_frozen_and_rejects_linked_input(running):
    client, db, run, token, root = running
    (root / "apps/demo/README.md").write_text("Changed after capture")
    value = output(call(client, token, "tools/call", {"name": "read_document", "arguments": {"documentId": "demo-frontend:README.md"}}))
    assert "Changed" not in value["text"]
    linked = root / "apps/demo/docs"; linked.mkdir()
    (linked / "linked.md").symlink_to(root / "apps/demo/README.md")
    with pytest.raises(ValueError): snapshot_documents(db, run)


def test_tool_call_budget_is_enforced(running):
    client, _, _, token, _ = running
    for _ in range(16): output(call(client, token, "tools/call", {"name": "list_documents"}))
    assert call(client, token, "tools/call", {"name": "list_documents"}).json()["error"]["code"] == -32000


def test_external_document_snapshot_uses_assigned_worktree_and_honors_custom_denials(running, tmp_path):
    from app.models import ExternalProjectTarget
    _, db, run, _, root = running
    task = db.get(Task, run.task_id)
    session = db.get(Session, task.session_id)
    host = tmp_path / "unassigned-host"
    host.mkdir()
    (host / "README.md").write_text("Host-only private documentation", encoding="utf-8")
    target_id = "external-docs"
    db.add(ExternalProjectTarget(workspace_id=session.workspace_id, target_id=target_id, name="External docs",
        root_path=str(host), allowed_paths_json=json.dumps(["src"]), denied_paths_json=json.dumps(["docs/private.md"])))
    task.plan_json = json.dumps({"targetId": target_id})
    db.add(task); db.commit()
    (root / "README.md").write_text("Assigned checkout documentation", encoding="utf-8")
    docs = snapshot_documents(db, run)
    assert list(docs) == ["external-docs:README.md"]
    assert docs["external-docs:README.md"]["text"] == "Assigned checkout documentation"
    directory = root / "docs"; directory.mkdir()
    (directory / "private.md").write_text("Never expose this configured denied path", encoding="utf-8")
    with pytest.raises(ValueError, match="Protected document"):
        snapshot_documents(db, run)


def test_codex_configs_are_fixed_and_tokens_are_not_in_commands_or_public_models(running):
    _, _, run, token, root = running
    request = AgentRunRequest(taskRunId=run.id, sessionId="session", workspaceId="workspace", worktreePath=str(root),
        agentId=run.agent_id, adapterType="codex", instruction="Use docs", mcp_tools=["list_documents", "read_document"], mcp_token=token)
    adapter = CodexAdapter(codex_binary="codex.exe")
    command = adapter._build_command(request, root)
    assert token not in json.dumps(command) and token not in request.model_dump_json() and token not in repr(request)
    assert evaluate_command(command, expected_cwd=root, expected_mcp_tools=request.mcp_tools).allowed
    assert not evaluate_command(command, expected_cwd=root).allowed
    tampered = command.copy(); tampered[2] = 'mcp_servers.agenthub_docs.url="https://other.invalid"'
    assert not evaluate_command(tampered, expected_cwd=root, expected_mcp_tools=request.mcp_tools).allowed
    assert f'shell_environment_policy.exclude=["{TOKEN_ENV}"]' in command


def test_codex_runtime_credential_injection_redaction_and_cleanup(running):
    client, _, run, token, root = running
    captured = {}
    class Runner:
        def start(self, command, cwd, **kwargs):
            captured.update(kwargs)
            return FakeCodexProcess(stdout=json.dumps({"type": "message.delta", "text": token}) + "\n" + json.dumps({"type": "turn.completed"}))
    request = AgentRunRequest(taskRunId=run.id, sessionId="session", workspaceId="workspace", worktreePath=str(root),
        agentId=run.agent_id, adapterType="codex", instruction="Use docs", mcp_tools=["list_documents"], mcp_token=token)
    adapter = CodexAdapter(process_runner=Runner(), codex_binary="codex.exe")
    async def exercise():
        started = await adapter.createRun(request)
        events = [e async for e in adapter.streamEvents(started.adapter_run_id)]
        assert token not in json.dumps([e.model_dump() for e in events], default=str)
        await adapter.cleanup(started.adapter_run_id)
    asyncio.run(exercise())
    assert captured["extra_env"] == {TOKEN_ENV: token}
    assert call(client, token, "tools/list").status_code == 401


def test_connection_revision_isolation_and_unsupported_adapters(client):
    from app.mcp_connections import receipt
    with db_from_override() as db:
        w = db.exec(select(Workspace)).first()
        save_connection(db, w.id, config())
        binding = capture_binding(db, w.id, "agent", "frontend")
        assert receipt(binding, "claude_code")["status"] == "unsupported_adapter"
        with pytest.raises(SkillError): save_connection(db, w.id, config())
        with pytest.raises(SkillError): save_connection(db, w.id, config(tools=["write_file"], revision=1))
        with pytest.raises(SkillError): verify_binding(binding, "other", "agent")


def test_native_mcp_events_summarize_activity_without_echoing_document_bodies():
    from app.codex_adapter import _map_codex_json_event
    event = _map_codex_json_event({"type": "item.completed", "item": {"type": "mcp_tool_call", "server": "agenthub_docs",
        "tool": "read_document", "status": "completed", "result": {"text": "API auth uses credentials."}}}, "run", "", [])
    assert event.payload["mcpTool"] == "read_document"
    assert "credentials" not in event.payload["text"]


def test_large_codex_skill_instructions_use_private_stdin(running):
    _, _, run, token, root = running
    captured = {}
    class Runner:
        def start(self, command, cwd, **kwargs):
            captured["command"] = command; captured.update(kwargs)
            return FakeCodexProcess(stdout=json.dumps({"type": "turn.completed"}))
    request = AgentRunRequest(taskRunId=run.id, sessionId="session", workspaceId="workspace", worktreePath=str(root),
        agentId=run.agent_id, adapterType="codex", instruction="instruction " * 2000)
    adapter = CodexAdapter(process_runner=Runner(), codex_binary="codex.exe")
    asyncio.run(adapter.createRun(request))
    assert captured["command"][-1] == "-" and captured["input_text"] == request.instruction
    assert request.instruction not in captured["command"]
