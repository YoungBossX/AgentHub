import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session as DbSession, select

from app.dependencies import get_db
from app.models import TaskRun, TaskRunEvent
from app.mcp_connections import connection, save_connection, gateway_url, SERVER
from app.mcp_gateway import authorize, rpc, PROTOCOLS
from app.routes.skills import require_workspace
from app.skills import SkillError

router = APIRouter()


class ConnectionRequest(BaseModel):
    enabled: bool
    tools: list[str] = Field(max_length=2)
    default_agents: list[str] = Field(default_factory=list, alias="defaultAgents", max_length=16)
    expected_revision: int = Field(default=0, alias="expectedRevision", ge=0)
    model_config = ConfigDict(extra="forbid")


@router.get("/workspaces/{workspace_id}/mcp")
def read_connection(workspace_id: str, db: DbSession = Depends(get_db)):
    require_workspace(db, workspace_id)
    return {**connection(db, workspace_id), "transport": "streamable_http", "supportedAdapters": ["codex"]}


@router.put("/workspaces/{workspace_id}/mcp")
def write_connection(workspace_id: str, request: ConnectionRequest, db: DbSession = Depends(get_db)):
    require_workspace(db, workspace_id)
    try:
        return save_connection(db, workspace_id, request)
    except SkillError as exc:
        raise HTTPException(409 if "changed" in str(exc) else 400, str(exc)) from exc


@router.post("/workspaces/{workspace_id}/mcp/probe")
def probe_connection(workspace_id: str, db: DbSession = Depends(get_db)):
    import httpx
    from app.mcp_gateway import issue_probe, revoke_token

    require_workspace(db, workspace_id)
    config = connection(db, workspace_id)
    token = issue_probe(workspace_id, config["tools"])
    try:
        with httpx.Client(timeout=5, trust_env=False, follow_redirects=False) as client:
            headers = {"Authorization": "Bearer " + token, "Accept": "application/json, text/event-stream"}
            init = client.post(gateway_url(), headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "AgentHub probe", "version": "1"}}})
            init.raise_for_status(); result = init.json()["result"]
            headers["MCP-Protocol-Version"] = result["protocolVersion"]
            client.post(gateway_url(), headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"}).raise_for_status()
            response = client.post(gateway_url(), headers=headers, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            response.raise_for_status()
            names = [tool["name"] for tool in response.json()["result"]["tools"]]
            if result["serverInfo"]["name"] != SERVER or names != config["tools"]:
                raise ValueError("Unexpected MCP server tool catalog.")
            return {"status": "ready", "protocolVersion": result["protocolVersion"], "tools": names}
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return {"status": "unavailable", "reason": "MCP gateway handshake failed. Check the API gateway origin and running server."}
    finally:
        revoke_token(token)


@router.get("/task-runs/{run_id}/mcp")
def run_evidence(run_id: str, db: DbSession = Depends(get_db)):
    run = db.get(TaskRun, run_id)
    if run is None:
        raise HTTPException(404, "TaskRun not found")
    events = db.exec(select(TaskRunEvent).where(TaskRunEvent.task_run_id == run_id,
        TaskRunEvent.event_type.in_(["mcp.connected", "mcp.tool.completed"])).order_by(TaskRunEvent.sequence)).all()
    return {"connection": json.loads(run.metrics_json).get("mcp"),
            "events": [{"id": e.id, "type": e.event_type, "createdAt": e.created_at.isoformat(), "payload": json.loads(e.payload_json)} for e in events]}


@router.post("/mcp/agenthub-docs")
async def gateway(request: Request, db: DbSession = Depends(get_db)):
    from starlette.concurrency import run_in_threadpool
    origin = request.headers.get("origin")
    if origin and origin != gateway_url().removesuffix("/mcp/agenthub-docs"):
        raise HTTPException(403, "MCP request Origin is not allowed.")
    version = request.headers.get("mcp-protocol-version")
    if version and version not in PROTOCOLS:
        raise HTTPException(400, "Unsupported MCP protocol version.")
    authorization = request.headers.get("authorization", "")
    value = await run_in_threadpool(authorize, db, authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else "")
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 8192:
            raise HTTPException(413, "MCP request exceeds 8 KB.")
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeError):
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Batch requests are not supported"}}, status_code=400)
    result = await run_in_threadpool(rpc, db, value, body)
    return Response(status_code=202) if result is None else JSONResponse(result)


@router.api_route("/mcp/agenthub-docs", methods=["GET", "DELETE"])
def unsupported_stream():
    return Response(status_code=405, headers={"Allow": "POST"})
