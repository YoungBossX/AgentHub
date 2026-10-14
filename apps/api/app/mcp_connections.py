"""The first declared MCP connection: bounded local documentation, Codex only."""
import json
import os
from urllib.parse import urlsplit

from sqlalchemy import update
from sqlmodel import select

from app.models import AgentProfileDraft, WorkspaceMcpConnection, utc_now
from app.skills import SkillError, ROLES, normalized_role, sha

VERSION = "agenthub.mcp.v1"
BINDING = "mcpBinding"
TOOLS = ("list_documents", "read_document")
SERVER = "agenthub_docs"
TOKEN_ENV = "AGENTHUB_MCP_TOKEN"


def connection(db, workspace_id):
    row = db.exec(select(WorkspaceMcpConnection).where(WorkspaceMcpConnection.workspace_id == workspace_id)).first()
    return {"serverId": SERVER, "enabled": False, "tools": list(TOOLS), "defaultAgents": [], "revision": 0} if row is None else {
        **json.loads(row.config_json), "revision": row.revision}


def save_connection(db, workspace_id, request):
    if (not set(request.tools).issubset(TOOLS) or len(set(request.tools)) != len(request.tools)
            or request.enabled and not request.tools):
        raise SkillError("Select declared document tools only.")
    if len(set(request.default_agents)) != len(request.default_agents):
        raise SkillError("Duplicate MCP Agent bindings.")
    for key in request.default_agents:
        if key in {"frontend", "backend"}:
            continue
        profile = db.get(AgentProfileDraft, key)
        if (profile is None or profile.workspace_id != workspace_id
                or profile.adapter_type != "codex" or normalized_role(profile.role) not in {"frontend", "backend"}):
            raise SkillError("MCP defaults require an available Codex coding Agent in this workspace.")
    current = connection(db, workspace_id)
    if current["revision"] != request.expected_revision:
        raise SkillError("MCP connection changed; reload before saving.")
    value = {"serverId": SERVER, "enabled": request.enabled, "tools": request.tools,
             "defaultAgents": request.default_agents}
    row = db.exec(select(WorkspaceMcpConnection).where(WorkspaceMcpConnection.workspace_id == workspace_id)).first()
    if row:
        result = db.execute(update(WorkspaceMcpConnection).where(WorkspaceMcpConnection.id == row.id,
            WorkspaceMcpConnection.revision == request.expected_revision).values(config_json=json.dumps(value),
                revision=request.expected_revision + 1, updated_at=utc_now()))
        if result.rowcount != 1:
            db.rollback(); raise SkillError("MCP connection changed concurrently.")
    else:
        db.add(WorkspaceMcpConnection(workspace_id=workspace_id, config_json=json.dumps(value)))
    from sqlalchemy.exc import IntegrityError
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback(); raise SkillError("MCP connection changed concurrently.") from exc
    return connection(db, workspace_id)


def capture_binding(db, workspace_id, agent_id, role, profile_id=None, previous=None):
    if previous is not None:
        stored = json.loads(previous.metrics_json).get(BINDING)
        return verify_binding(stored, workspace_id, agent_id) if stored else None
    config = connection(db, workspace_id)
    key = profile_id or normalized_role(role)
    if not config["enabled"] or key not in config["defaultAgents"]:
        return None
    value = {"schemaVersion": VERSION, "workspaceId": workspace_id, "agentId": agent_id,
             "role": normalized_role(role), "profileId": profile_id, "connection": config}
    return {**value, "sha256": sha(value)}


def verify_binding(binding, workspace_id, agent_id):
    if (not isinstance(binding, dict) or binding.get("schemaVersion") != VERSION
            or binding.get("workspaceId") != workspace_id or binding.get("agentId") != agent_id
            or binding.get("sha256") != sha({k: v for k, v in binding.items() if k != "sha256"})
            or binding.get("role") not in ROLES):
        raise SkillError("MCP connection snapshot failed identity/integrity validation.")
    config = binding.get("connection", {})
    if (config.get("serverId") != SERVER or not config.get("enabled") or not config.get("tools")
            or not set(config["tools"]).issubset(TOOLS)):
        raise SkillError("MCP tools are outside the declared connection.")
    return binding


def receipt(binding, adapter_type):
    if binding is None:
        return None
    return {"schemaVersion": VERSION, "serverId": SERVER, "revision": binding["connection"]["revision"],
            "sha256": binding["sha256"], "tools": binding["connection"]["tools"],
            "status": "configured" if adapter_type == "codex" else "unsupported_adapter"}


def gateway_url():
    origin = os.environ.get("AGENTHUB_MCP_GATEWAY_ORIGIN", "http://127.0.0.1:8000")
    parsed = urlsplit(origin)
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.username or parsed.password
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.port is None):
        raise SkillError("MCP gateway must be the server-owned 127.0.0.1 API origin.")
    return origin.rstrip("/") + "/mcp/agenthub-docs"


def config_arguments(tools):
    if not tools or len(set(tools)) != len(tools) or not set(tools).issubset(TOOLS):
        raise SkillError("Invalid Codex MCP allowlist.")
    values = {
        f"mcp_servers.{SERVER}.url": gateway_url(),
        f"mcp_servers.{SERVER}.bearer_token_env_var": TOKEN_ENV,
        f"mcp_servers.{SERVER}.enabled_tools": list(tools),
        f"mcp_servers.{SERVER}.required": True,
        f"mcp_servers.{SERVER}.tool_timeout_sec": 10,
        "shell_environment_policy.exclude": [TOKEN_ENV],
    }
    return [arg for key, value in values.items() for arg in ("-c", f"{key}={json.dumps(value, ensure_ascii=True)}")]
