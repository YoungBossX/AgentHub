"""Trusted per-run behavior settings. Prompts never grant permissions."""

import hashlib
from typing import Any

from sqlmodel import Session as DbSession

from app.agent_runtime_config import resolve_runtime_role_config
from app.models import Agent, AgentProfileDraft

AGENT_INSTRUCTION_BINDING_KEY = "agentInstructionBinding"


def capture_agent_instruction(
    db: DbSession, *, workspace_id: str, agent: Agent, role: str,
    profile: AgentProfileDraft | None = None,
) -> dict[str, Any]:
    resolution = resolve_runtime_role_config(db, workspace_id, role)
    if profile is None and resolution and resolution.role_config.agent_profile_id:
        candidate = db.get(AgentProfileDraft, resolution.role_config.agent_profile_id)
        if candidate is not None and candidate.tool_policy:
            from app.custom_agents import require_custom_agent

            profile = require_custom_agent(db, workspace_id, candidate.id)
    override = resolution.role_config.system_prompt if resolution else None
    if profile is not None and (not resolution or resolution.role_config.agent_profile_id != profile.id):
        override = None
    text = override if override and override.strip() else (profile.system_prompt if profile else agent.system_prompt)
    return {
        "version": 1,
        "workspaceId": workspace_id,
        "agentId": agent.id,
        "role": role,
        "source": "workspace_override" if override and override.strip() else "custom_profile" if profile else "agent_default",
        "profileId": profile.id if profile else None,
        "text": text,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def bound_agent_instruction(
    value: object, *, workspace_id: str, agent_id: str,
) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or value.get("version") != 1
        or value.get("workspaceId") != workspace_id
        or value.get("agentId") != agent_id
        or not isinstance(value.get("role"), str)
        or value.get("source") not in {"workspace_override", "agent_default", "custom_profile"}
        or not isinstance(value.get("text"), str)
    ):
        raise ValueError("Agent instruction binding identity is invalid.")
    if value.get("sha256") != hashlib.sha256(value["text"].encode("utf-8")).hexdigest():
        raise ValueError("Agent instruction binding digest is invalid.")
    return dict(value)


def agent_instruction_receipt(binding: dict[str, Any]) -> dict[str, Any]:
    return {
        key: binding[key]
        for key in ("version", "workspaceId", "agentId", "role", "source", "sha256")
    } | {"characters": len(binding["text"]), "profileId": binding.get("profileId")}
