import json
from dataclasses import dataclass
from typing import Optional

from app.agent_profiles import AgentProfile
from sqlmodel import Session as DbSession
from sqlmodel import select

from app.models import AgentRuntimeConfig, utc_now
from app.planner_providers import (
    API_KEY_ENV_PATTERN,
    PlannerProviderError,
    get_planner_provider_preset,
    resolve_planner_api_key,
    validate_planner_provider_base_url,
)
from app.provider_configs import ProviderConfig

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
    provider_preset_id: Optional[str] = None
    protocol: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    timeout_seconds: Optional[int] = None
    api_key_env: Optional[str] = None

    def to_payload(self) -> dict[str, object]:
        return {
            "role": self.role,
            "agentProfileId": self.agent_profile_id,
            "providerId": self.provider_id,
            "adapterType": self.adapter_type,
            "mode": self.mode,
            "enabled": self.enabled,
            "fallbackPolicy": self.fallback_policy,
            "providerPresetId": self.provider_preset_id,
            "protocol": self.protocol,
            "model": self.model,
            "baseUrl": self.base_url,
            "timeoutSeconds": self.timeout_seconds,
            "apiKeyEnv": self.api_key_env,
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


@dataclass(frozen=True)
class RuntimeConfigValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class RuntimeRoleResolution:
    role_config: RuntimeRoleConfig
    config_source: str

    def to_metadata(self) -> dict[str, object]:
        return {
            "role": self.role_config.role,
            "agentProfileId": self.role_config.agent_profile_id,
            "providerId": self.role_config.provider_id,
            "adapterType": self.role_config.adapter_type,
            "mode": self.role_config.mode,
            "enabled": self.role_config.enabled,
            "fallbackPolicy": self.role_config.fallback_policy,
            "configSource": self.config_source,
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
            provider_preset_id=None,
            protocol=None,
            model=None,
            base_url=None,
            timeout_seconds=None,
            api_key_env=None,
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


def resolve_runtime_role_config(
    db: DbSession,
    workspace_id: Optional[str],
    role: str,
) -> Optional[RuntimeRoleResolution]:
    if role not in RUNTIME_CONFIG_ROLES:
        return None
    snapshot = get_effective_runtime_config(db, workspace_id)
    role_config = snapshot.roles.get(role)
    if role_config is None or not role_config.enabled:
        return None
    return RuntimeRoleResolution(
        role_config=role_config,
        config_source=snapshot.config_source,
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


def validate_runtime_config(
    roles: dict[str, RuntimeRoleConfig],
    *,
    profiles: list[AgentProfile],
    providers: list[ProviderConfig],
) -> RuntimeConfigValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        normalized = _normalize_roles(roles)
    except AgentRuntimeConfigError as exc:
        return RuntimeConfigValidationResult(valid=False, errors=[str(exc)], warnings=[])

    profiles_by_id = {profile.id: profile for profile in profiles}
    providers_by_id = {provider.provider_id: provider for provider in providers}

    for role, role_config in normalized.items():
        if not role_config.enabled:
            continue
        if role == "planner" and role_config.provider_preset_id:
            _validate_planner_api_runtime_role(role_config, errors, warnings)
            continue

        missing_fields = [
            field_name
            for field_name, value in {
                "agentProfileId": role_config.agent_profile_id,
                "providerId": role_config.provider_id,
                "adapterType": role_config.adapter_type,
                "mode": role_config.mode,
            }.items()
            if not value
        ]
        if missing_fields:
            errors.append(
                f"Runtime config role `{role}` is enabled but missing {', '.join(missing_fields)}."
            )
            continue

        profile = profiles_by_id.get(role_config.agent_profile_id or "")
        if profile is None:
            errors.append(
                f"Runtime config role `{role}` references unknown agent profile `{role_config.agent_profile_id}`."
            )
            continue

        provider = providers_by_id.get(role_config.provider_id or "")
        if provider is None:
            errors.append(
                f"Runtime config role `{role}` references unknown provider `{role_config.provider_id}`."
            )
            continue

        if not provider.available:
            errors.append(
                f"Runtime config role `{role}` references unavailable provider `{provider.provider_id}`."
            )
        if not _mode_allowed_for_runtime_role(role, role_config.mode):
            errors.append(
                f"Runtime config role `{role}` cannot use mode `{role_config.mode}`."
            )
        if role_config.adapter_type != provider.adapter_type:
            errors.append(
                f"Runtime config role `{role}` adapter `{role_config.adapter_type}` does not match provider `{provider.adapter_type}`."
            )
        if role_config.adapter_type != profile.adapter_type:
            warnings.append(
                f"Runtime config role `{role}` uses provider adapter `{role_config.adapter_type}` with agent profile adapter `{profile.adapter_type}`."
            )
        if role_config.mode not in provider.supported_modes:
            errors.append(
                f"Runtime config role `{role}` mode `{role_config.mode}` is not supported by provider `{provider.provider_id}`."
            )
        if role_config.mode not in profile.supported_modes:
            errors.append(
                f"Runtime config role `{role}` mode `{role_config.mode}` is not supported by agent profile `{profile.id}`."
            )
        if not _profile_supports_runtime_role(profile, role):
            errors.append(
                f"Runtime config role `{role}` is not supported by agent profile `{profile.id}`."
            )
        if role in {"frontend", "backend"} and not profile.safe_for_write:
            errors.append(
                f"Runtime config role `{role}` requires a write-safe agent profile."
            )
        if role in {"planner", "review"} and not profile.safe_for_review:
            errors.append(
                f"Runtime config role `{role}` requires a review-safe agent profile."
            )
        if role not in provider.default_for_roles:
            warnings.append(
                f"Provider `{provider.provider_id}` is not a default provider for role `{role}`."
            )

    return RuntimeConfigValidationResult(
        valid=not errors,
        errors=errors,
        warnings=warnings,
    )


def _validate_planner_api_runtime_role(
    role_config: RuntimeRoleConfig,
    errors: list[str],
    warnings: list[str],
) -> None:
    preset = get_planner_provider_preset(role_config.provider_preset_id or "")
    if preset is None:
        errors.append(
            f"Runtime config role `planner` references unknown planner provider preset `{role_config.provider_preset_id}`."
        )
        return

    if role_config.protocol and role_config.protocol != preset.protocol:
        errors.append(
            f"Runtime config role `planner` protocol `{role_config.protocol}` does not match preset `{preset.protocol}`."
        )
    if not (role_config.model or preset.default_model):
        errors.append("Runtime config role `planner` requires a Planner model.")
    try:
        validate_planner_provider_base_url(
            preset_id=preset.preset_id,
            base_url=role_config.base_url or preset.default_base_url,
        )
    except PlannerProviderError as exc:
        errors.append(f"Runtime config role `planner` baseUrl is invalid: {exc.summary}")

    api_key_env = role_config.api_key_env or preset.api_key_env
    try:
        key_resolution = resolve_planner_api_key(
            api_key_env,
            provider_id=preset.preset_id,
        )
    except PlannerProviderError as exc:
        errors.append(f"Runtime config role `planner` apiKeyEnv is invalid: {exc.summary}")
        return
    if key_resolution.availability == "missing_key":
        warnings.append(
            f"Planner provider preset `{preset.preset_id}` availability is missing_key for env `{api_key_env}`."
        )


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
            provider_preset_id=_optional_string(payload.get("providerPresetId")),
            protocol=_optional_string(payload.get("protocol")),
            model=_optional_string(payload.get("model")),
            base_url=_optional_string(payload.get("baseUrl")),
            timeout_seconds=_optional_int(payload.get("timeoutSeconds")),
            api_key_env=_optional_string(payload.get("apiKeyEnv")),
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
        if role_config.api_key_env and not API_KEY_ENV_PATTERN.fullmatch(role_config.api_key_env):
            raise AgentRuntimeConfigError(
                f"Runtime config role `{role}` apiKeyEnv must be an uppercase environment variable name."
            )
        normalized[role] = role_config
    return normalized


def _default_mode_for_role(role: str) -> str:
    return "read_only" if role in {"planner", "review"} else role


def _optional_string(value: object) -> Optional[str]:
    return value if isinstance(value, str) and value.strip() else None


def _optional_int(value: object) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _profile_supports_runtime_role(profile: AgentProfile, role: str) -> bool:
    accepted_roles = {
        role,
        "orchestrator" if role == "planner" else role,
        "manager" if role == "planner" else role,
        "qa" if role == "review" else role,
    }
    return bool(accepted_roles.intersection(profile.supported_roles))


def _mode_allowed_for_runtime_role(role: str, mode: Optional[str]) -> bool:
    if mode is None:
        return False
    allowed_modes = {
        "planner": {"read_only"},
        "frontend": {"frontend"},
        "backend": {"backend"},
        "review": {"review", "qa", "read_only"},
    }
    return mode in allowed_modes.get(role, set())
