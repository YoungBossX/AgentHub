"""Execution-bound document snapshots and stateless MCP JSON-RPC handling."""
import hashlib
import json
import secrets
import threading
import time
from pathlib import Path

from fastapi import HTTPException
from sqlmodel import select

from app.events import append_task_run_event
from app.models import Session, SessionQueueEntry, TargetLock, Task, TaskRun, utc_now
from app.native_reviews import _no_link, _read_file
from app.process_environment import redact_process_evidence
from app.target_registry import get_target_for_workspace
from app.mcp_connections import SERVER, TOOLS, VERSION, connection, verify_binding

PROTOCOLS = {"2025-03-26", "2025-06-18", "2025-11-25"}
ACCESS_KEY = "taskRunExecutionAccessBinding"
_tokens = {}
_lock = threading.Lock()
TOKEN_TTL = 600


def snapshot_documents(db, run):
    task = db.get(Task, run.task_id); session = db.get(Session, task.session_id)
    target_id = json.loads(task.plan_json).get("targetId")
    target = get_target_for_workspace(db, session.workspace_id, target_id)
    root = Path(run.worktree_path).absolute()
    for parent in [root, *root.parents]:
        _no_link(parent)
    if root.resolve() != root:
        raise ValueError("MCP requires a canonical assigned worktree path.")
    subroots = [(target_id, "apps/demo" if target_id == "demo-frontend" else "apps/demo-api" if target_id == "demo-backend" else "")]
    # Only the built-in, explicitly related backend in the same assigned clone.
    if target_id == "demo-frontend" and "demo-backend" in target.related_target_ids:
        subroots.append(("demo-backend", "apps/demo-api"))
    documents = {}
    budget = 0
    for doc_target, relative_root in subroots:
        document_policy = get_target_for_workspace(db, session.workspace_id, doc_target)
        project = root / relative_root
        if not project.exists():
            continue
        for parent in [project, *list(project.parents)[:len(project.relative_to(root).parts)]]:
            _no_link(parent)
        candidates = [project / "README.md", project / "README.txt"]
        directory = project / "docs"
        pending = [directory] if directory.exists() else []
        entries = 0
        while pending:
            path = pending.pop(); entries += 1
            if entries > 128:
                raise ValueError("Document directory exceeds its entry budget.")
            info = _no_link(path)
            relative = path.relative_to(root).as_posix()
            if document_policy.denies_path(relative):
                raise ValueError("Protected document path is not supported.")
            if path.is_dir():
                for child in path.iterdir():
                    if entries + len(pending) >= 128:
                        raise ValueError("Document directory exceeds its entry budget.")
                    pending.append(child)
            elif path.suffix.lower() in {".md", ".txt"}:
                candidates.append(path)
        for path in sorted(candidates):
            if not path.exists():
                continue
            relative = path.relative_to(root).as_posix()
            if document_policy.denies_path(relative):
                raise ValueError("Protected document input.")
            raw = _read_file(root, path, include_bytes=True)
            if raw["bytes"] > 16000:
                raise ValueError("Document exceeds 16 KB.")
            text = raw["content"].decode("utf-8")
            if "\0" in text:
                raise ValueError("Document is not text.")
            budget += len(text.encode())
            if len(documents) >= 16 or budget > 64000:
                raise ValueError("Document snapshot exceeds 16 files/64 KB.")
            doc_id = f"{doc_target}:{path.relative_to(project).as_posix()}"
            documents[doc_id] = {"documentId": doc_id, "path": relative, "sha256": raw["sha256"],
                                 "text": redact_process_evidence(text)}
    return documents


def issue_token(db, run, binding):
    task = db.get(Task, run.task_id); session = db.get(Session, task.session_id)
    verify_binding(binding, session.workspace_id, run.agent_id)
    metrics = json.loads(run.metrics_json)
    access = metrics.get(ACCESS_KEY)
    if not isinstance(access, dict) or not access.get("executionAttemptId"):
        raise ValueError("MCP execution access is not bound.")
    config = connection(db, session.workspace_id)
    key = binding.get("profileId") or binding["role"]
    if not config["enabled"] or key not in config["defaultAgents"] or not set(binding["connection"]["tools"]).issubset(config["tools"]):
        raise ValueError("MCP connection was revoked before launch.")
    documents = snapshot_documents(db, run)
    lock = db.exec(select(TargetLock).where(TargetLock.task_run_id == run.id, TargetLock.state == "held")).first()
    if access.get("accessMode") == "write" and lock is None:
        raise ValueError("MCP writer has no current target lock.")
    token = secrets.token_urlsafe(32)
    value = {"runId": run.id, "agentId": run.agent_id, "workspaceId": session.workspace_id,
             "sessionId": session.id, "runnerId": run.runner_id, "worktreePath": run.worktree_path,
             "access": dict(access), "binding": binding, "documents": documents,
             "targetLockId": lock.id if lock else None,
             "expires": time.monotonic() + TOKEN_TTL, "calls": 0,
             "callLock": threading.Lock()}
    with _lock:
        for key in list(_tokens):
            if _tokens[key]["expires"] <= time.monotonic():
                _tokens.pop(key)
        if len(_tokens) >= 128:
            raise ValueError("MCP execution credential capacity reached.")
        _tokens[hashlib.sha256(token.encode()).hexdigest()] = value
    return token


def revoke_run(run_id):
    with _lock:
        for key in list(_tokens):
            if _tokens[key].get("runId") == run_id:
                _tokens.pop(key)


def issue_probe(workspace_id, tools):
    token = secrets.token_urlsafe(32)
    with _lock:
        for key in list(_tokens):
            if _tokens[key]["expires"] <= time.monotonic():
                _tokens.pop(key)
        if len(_tokens) >= 128:
            raise ValueError("MCP credential capacity reached.")
        _tokens[hashlib.sha256(token.encode()).hexdigest()] = {"probe": True, "workspaceId": workspace_id,
            "expires": time.monotonic() + 15, "binding": {"connection": {"tools": tools}}}
    return token


def revoke_token(token):
    with _lock:
        _tokens.pop(hashlib.sha256(token.encode()).hexdigest(), None)


def authorize(db, token):
    if not token or len(token) > 128:
        raise HTTPException(401, "Invalid MCP execution credential.")
    with _lock:
        value = _tokens.get(hashlib.sha256(token.encode()).hexdigest())
    return authorize_value(db, value)


def authorize_value(db, value):
    if value is None or value["expires"] <= time.monotonic():
        raise HTTPException(401, "MCP execution credential expired or unavailable.")
    with _lock:
        if not any(current is value for current in _tokens.values()):
            raise HTTPException(401, "MCP execution credential was revoked.")
    if value.get("probe"):
        return value
    run = db.get(TaskRun, value["runId"])
    session = db.get(Session, value["sessionId"])
    queue = db.get(SessionQueueEntry, value["access"].get("queueEntryId"))
    lock = db.get(TargetLock, value["targetLockId"]) if value["targetLockId"] else None
    if (run is None or session is None or session.workspace_id != value["workspaceId"]
            or run.agent_id != value["agentId"] or run.runner_id != value["runnerId"]
            or run.worktree_path != value["worktreePath"]
            or run.state not in {"queued", "streaming", "applying_changes", "collecting_diff"}
            or run.lease_expires_at is None or run.lease_expires_at <= utc_now()
            or json.loads(run.metrics_json).get(ACCESS_KEY) != value["access"]):
        raise HTTPException(403, "MCP execution ownership is no longer current.")
    if (queue is None or queue.task_run_id != run.id or queue.session_id != session.id
            or queue.state not in {"queued", "running"}
            or value["access"].get("accessMode") == "write" and (lock is None or lock.state != "held"
                or lock.task_run_id != run.id or lock.worker_id != run.runner_id or lock.lease_expires_at is None
                or lock.lease_expires_at <= utc_now())):
        raise HTTPException(403, "MCP execution queue/target ownership is no longer current.")
    config = connection(db, value["workspaceId"])
    key = value["binding"].get("profileId") or value["binding"]["role"]
    if (not config["enabled"] or key not in config["defaultAgents"]
            or not set(value["binding"]["connection"]["tools"]).issubset(config["tools"])):
        raise HTTPException(403, "MCP connection access was revoked.")
    return value


def tool_definition(name):
    return {"name": name, "description": "List the bound project's documentation snapshots." if name == "list_documents"
        else "Read an assigned project's documentation snapshot by a discovered documentId. Content is reference data.",
        "inputSchema": {"type": "object", "properties": {} if name == "list_documents" else {"documentId": {"type": "string", "maxLength": 256}},
                        "required": [] if name == "list_documents" else ["documentId"], "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}}


def rpc(db, value, body):
    authorize_value(db, value)
    method = body.get("method"); params = body.get("params", {}); request_id = body.get("id")
    def error(code, message):
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
    if body.get("jsonrpc") != "2.0" or not isinstance(method, str) or not isinstance(params, dict):
        return error(-32600, "Invalid request")
    if "id" not in body:
        return None  # JSON-RPC notifications never receive a response or execute tools.
    if not isinstance(request_id, (str, int)) or isinstance(request_id, bool):
        return error(-32600, "Invalid request ID")
    if method == "initialize":
        requested = params.get("protocolVersion")
        result = {"protocolVersion": requested if isinstance(requested, str) and requested in PROTOCOLS else "2025-11-25",
                  "capabilities": {"tools": {}}, "serverInfo": {"name": SERVER, "version": "1.0.0"}}
        if not value.get("probe"):
            append_task_run_event(db, task_run_id=value["runId"], event_type="mcp.connected",
                payload_json=json.dumps({"schemaVersion": VERSION, "serverId": SERVER, "protocolVersion": result["protocolVersion"]}))
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": [tool_definition(name) for name in value["binding"]["connection"]["tools"]]}
    elif method == "tools/call":
        if value.get("probe"):
            return error(-32602, "Connection probes cannot call project tools")
        name = params.get("name"); args = params.get("arguments", {})
        if not isinstance(name, str) or name not in value["binding"]["connection"]["tools"]:
            return error(-32602, "Tool is not permitted")
        if (not isinstance(args, dict) or name == "list_documents" and args
                or name == "read_document" and (set(args) != {"documentId"} or not isinstance(args["documentId"], str) or len(args["documentId"]) > 256)):
            return error(-32602, "Invalid tool arguments")
        if not value["callLock"].acquire(blocking=False):
            return error(-32000, "Another call is in progress")
        started = time.monotonic()
        try:
            # Check again inside the serialized call boundary.
            db.expire_all(); authorize_value(db, value)
            if value["calls"] >= 16:
                return error(-32000, "Execution tool-call budget exceeded")
            value["calls"] += 1
            failed = name == "read_document" and args["documentId"] not in value["documents"]
            output = {"error": "Document ID was not discovered in this execution."} if failed else (
                [{k: v for k, v in doc.items() if k != "text"} for doc in value["documents"].values()]
                if name == "list_documents" else value["documents"][args["documentId"]])
            evidence = {"schemaVersion": VERSION, "serverId": SERVER, "tool": name,
                        "arguments": {"documentId": "<unavailable>"} if failed else args, "status": "failed" if failed else "passed",
                        "durationMs": int((time.monotonic() - started) * 1000), "result": output}
            append_task_run_event(db, task_run_id=value["runId"], event_type="mcp.tool.completed", payload_json=json.dumps(evidence))
            result = {"content": [{"type": "text", "text": json.dumps(output, ensure_ascii=False)}], "isError": failed}
        finally:
            value["callLock"].release()
    else:
        return error(-32601, "Method not found")
    return {"jsonrpc": "2.0", "id": request_id, "result": result}
