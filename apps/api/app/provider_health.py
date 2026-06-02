from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

from app.agent_runtime_config import RuntimeRoleConfig
from app.planner_providers import (
    PlannerProviderError,
    get_planner_provider_preset,
    resolve_planner_api_key,
    validate_planner_provider_base_url,
)
from app.provider_configs import ProviderConfig


CLI_COMMANDS_BY_ADAPTER = {
    "claude_cli": "claude",
    "claude_code": "claude",
    "codex": "codex",
}


@dataclass(frozen=True)
class ProviderHealthCheckResult:
    role: str
    provider_id: str | None
    adapter_type: str | None
    auth_status: str
    availability: str
    available: bool
    message: str


def check_runtime_role_provider(
    role_config: RuntimeRoleConfig,
    *,
    providers: list[ProviderConfig],
) -> ProviderHealthCheckResult:
    if role_config.role == "planner" and role_config.provider_preset_id:
        return _check_planner_api(role_config)

    provider = next(
        (
            item
            for item in providers
            if item.provider_id == role_config.provider_id
        ),
        None,
    )
    if provider is None:
        return ProviderHealthCheckResult(
            role=role_config.role,
            provider_id=role_config.provider_id,
            adapter_type=role_config.adapter_type,
            auth_status="unavailable",
            availability="unavailable",
            available=False,
            message="未找到这个提供方配置。",
        )

    if provider.auth_status == "not_required" or provider.adapter_type == "scripted_mock":
        return ProviderHealthCheckResult(
            role=role_config.role,
            provider_id=provider.provider_id,
            adapter_type=provider.adapter_type,
            auth_status="not_required",
            availability="not_required",
            available=True,
            message=f"{provider.display_name} 无需认证，可用于回退或本地模拟路径。",
        )

    command = CLI_COMMANDS_BY_ADAPTER.get(provider.adapter_type)
    if command is None:
        return ProviderHealthCheckResult(
            role=role_config.role,
            provider_id=provider.provider_id,
            adapter_type=provider.adapter_type,
            auth_status="unavailable",
            availability="unavailable",
            available=False,
            message=f"{provider.display_name} 暂无可用性检测规则。",
        )

    executable = shutil.which(command)
    if executable is None:
        return ProviderHealthCheckResult(
            role=role_config.role,
            provider_id=provider.provider_id,
            adapter_type=provider.adapter_type,
            auth_status="unavailable",
            availability="unavailable",
            available=False,
            message=f"未找到本地命令 `{command}`，请先安装或确认 PATH。",
        )

    try:
        subprocess.run(
            [executable, "--version"],
            capture_output=True,
            check=True,
            text=True,
            timeout=3,
        )
    except (subprocess.SubprocessError, OSError):
        return ProviderHealthCheckResult(
            role=role_config.role,
            provider_id=provider.provider_id,
            adapter_type=provider.adapter_type,
            auth_status="unavailable",
            availability="unavailable",
            available=False,
            message=f"已找到 `{command}`，但版本检测失败，请确认它可以正常运行。",
        )

    return ProviderHealthCheckResult(
        role=role_config.role,
        provider_id=provider.provider_id,
        adapter_type=provider.adapter_type,
        auth_status="available",
        availability="available",
        available=True,
        message=f"{provider.display_name} 已检测可用。",
    )


def _check_planner_api(
    role_config: RuntimeRoleConfig,
) -> ProviderHealthCheckResult:
    preset = get_planner_provider_preset(role_config.provider_preset_id or "")
    if preset is None:
        return ProviderHealthCheckResult(
            role=role_config.role,
            provider_id=role_config.provider_preset_id,
            adapter_type=role_config.protocol,
            auth_status="unavailable",
            availability="unavailable",
            available=False,
            message="未找到这个规划 API 预设。",
        )

    try:
        validate_planner_provider_base_url(
            preset_id=preset.preset_id,
            base_url=role_config.base_url or preset.default_base_url,
        )
        key_resolution = resolve_planner_api_key(
            role_config.api_key_env or preset.api_key_env,
            provider_id=preset.preset_id,
        )
    except PlannerProviderError as exc:
        return ProviderHealthCheckResult(
            role=role_config.role,
            provider_id=preset.preset_id,
            adapter_type=preset.protocol,
            auth_status="unavailable",
            availability="unavailable",
            available=False,
            message=exc.summary,
        )

    if key_resolution.availability == "missing_key":
        return ProviderHealthCheckResult(
            role=role_config.role,
            provider_id=preset.preset_id,
            adapter_type=preset.protocol,
            auth_status="missing_key",
            availability="missing_key",
            available=False,
            message=f"缺少环境变量 {key_resolution.api_key_env}。",
        )

    return ProviderHealthCheckResult(
        role=role_config.role,
        provider_id=preset.preset_id,
        adapter_type=preset.protocol,
        auth_status="configured",
        availability="configured",
        available=True,
        message=f"{preset.display_name} 已配置密钥环境变量。",
    )
