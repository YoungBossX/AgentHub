import json
from dataclasses import dataclass
from typing import Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.models import AgentRuntimeConfig, utc_now

RUNTIME_CONFIG_ROLES = ("planner", "frontend", "backend", "review")
DEFAULT_FALLBACK_POLICY = "environment_default"


class AgentRuntimeConfigError(ValueError):
    pass


@dataclass(frozen=True)
class RuntimeRoleConfig:
    role: str
    agent_profile_id: Optional[str]
    provider_id: Optional[str]
    adapter_type: Optional[str]
    mode: Optional[str]
    enabled: bool
    fallback_policy: Optional[str] = DEFAULT_FALLBACK_POLICY

    def to_payload(self) -> dict[str, object]:
        return {
            "role": self.role,
            "agentProfileId": self.agent_profile_id,
            "providerId": self.provider_id,
            "adapterType": self.adapter_type,
            "mode": self.mode,
            "enabled": self.enabled,
            "fallbackPolicy": self.fallback_policy,
        }


@dataclass(frozen=True)
class RuntimeConfigSnapshot:
    workspace_id: Optional[str]
    config_source: str
    roles: dict[str, RuntimeRoleConfig]

    def to_payload(self) -> dict[str, object]:
        return {
            "workspaceId": self.workspace_id,
            "configSource": self.config_source,
            "roles": {
                role: role_config.to_payload()
                for role, role_config in self.roles.items()
            },
        }


def default_runtime_config(workspace_id: Optional[str]) -> RuntimeConfigSnapshot:
    return RuntimeConfigSnapshot(
        workspace_id=workspace_id,
        config_source="default",
        roles={
            role: RuntimeRoleConfig(
                role=role,
                agent_profile_id=None,
                provider_id=None,
                adapter_type=None,
                mode=_default_mode_for_role(role),
                enabled=False,
                fallback_policy=DEFAULT_FALLBACK_POLICY,
            )
            for role in RUNTIME_CONFIG_ROLES
        },
    )


def get_effective_runtime_config(
    db: DbSession,
    workspace_id: Optional[str],
) -> RuntimeConfigSnapshot:
    stored = _stored_config_for_workspace(db, workspace_id)
    if stored is None:
        return default_runtime_config(workspace_id)
    return RuntimeConfigSnapshot(
        workspace_id=stored.workspace_id,
        config_source=stored.scope or "workspace",
        roles=_roles_from_json(stored.roles_json),
    )


def upsert_runtime_config(
    db: DbSession,
    workspace_id: Optional[str],
    roles: dict[str, RuntimeRoleConfig],
    *,
    scope: str = "workspace",
) -> AgentRuntimeConfig:
    normalized_roles = _normalize_roles(roles)
    stored = _stored_config_for_workspace(db, workspace_id)
    now = utc_now()
    if stored is None:
        stored = AgentRuntimeConfig(
            workspace_id=workspace_id,
            scope=scope,
            roles_json=_roles_to_json(normalized_roles),
            created_at=now,
            updated_at=now,
        )
    else:
        stored.scope = scope
        stored.roles_json = _roles_to_json(normalized_roles)
        stored.updated_at = now
    db.add(stored)
    db.commit()
    db.refresh(stored)
    return stored


def _stored_config_for_workspace(
    db: DbSession,
    workspace_id: Optional[str],
) -> Optional[AgentRuntimeConfig]:
    return db.exec(
        select(AgentRuntimeConfig).where(AgentRuntimeConfig.workspace_id == workspace_id)
    ).first()


def _roles_to_json(roles: dict[str, RuntimeRoleConfig]) -> str:
    return json.dumps(
        {
            role: role_config.to_payload()
            for role, role_config in _normalize_roles(roles).items()
        },
        separators=(",", ":"),
    )


def _roles_from_json(value: str) -> dict[str, RuntimeRoleConfig]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise AgentRuntimeConfigError("Runtime config roles_json is invalid JSON.") from exc
    if not isinstance(parsed, dict):
        raise AgentRuntimeConfigError("Runtime config roles_json must be an object.")

    roles = default_runtime_config(None).roles.copy()
    for role, payload in parsed.items():
        if role not in RUNTIME_CONFIG_ROLES:
            continue
        if not isinstance(payload, dict):
            raise AgentRuntimeConfigError(f"Runtime config role `{role}` must be an object.")
        roles[role] = RuntimeRoleConfig(
            role=role,
            agent_profile_id=_optional_string(payload.get("agentProfileId")),
            provider_id=_optional_string(payload.get("providerId")),
            adapter_type=_optional_string(payload.get("adapterType")),
            mode=_optional_string(payload.get("mode")) or _default_mode_for_role(role),
            enabled=bool(payload.get("enabled", False)),
            fallback_policy=_optional_string(payload.get("fallbackPolicy"))
            or DEFAULT_FALLBACK_POLICY,
        )
    return roles


def _normalize_roles(
    roles: dict[str, RuntimeRoleConfig],
) -> dict[str, RuntimeRoleConfig]:
    normalized = default_runtime_config(None).roles.copy()
    for role, role_config in roles.items():
        if role not in RUNTIME_CONFIG_ROLES:
            raise AgentRuntimeConfigError(f"Unsupported runtime config role: {role}")
        if role_config.role != role:
            raise AgentRuntimeConfigError(
                f"Runtime config role key `{role}` does not match payload role `{role_config.role}`."
            )
        normalized[role] = role_config
    return normalized


def _default_mode_for_role(role: str) -> str:
    return "read_only" if role in {"planner", "review"} else role


def _optional_string(value: object) -> Optional[str]:
    return value if isinstance(value, str) and value.strip() else None
