from dataclasses import dataclass

from app.agent_capabilities import validate_supported_modes


@dataclass(frozen=True)
class ProviderConfig:
    provider_id: str
    display_name: str
    adapter_type: str
    auth_status: str
    available: bool
    default_for_roles: list[str]
    supported_modes: list[str]

    def __post_init__(self) -> None:
        validate_supported_modes(
            self.supported_modes,
            source=f"ProviderConfig:{self.provider_id}",
        )


BUILT_IN_PROVIDER_CONFIGS: tuple[ProviderConfig, ...] = (
    ProviderConfig(
        provider_id="local-claude-code-cli",
        display_name="Claude Code CLI",
        adapter_type="claude_code",
        auth_status="unchecked",
        available=True,
        default_for_roles=["frontend", "backend"],
        supported_modes=["frontend", "backend", "review", "debug"],
    ),
    ProviderConfig(
        provider_id="local-codex-cli",
        display_name="Codex CLI",
        adapter_type="codex",
        auth_status="unchecked",
        available=True,
        default_for_roles=["frontend", "backend"],
        supported_modes=["frontend", "backend", "debug"],
    ),
    ProviderConfig(
        provider_id="local-scripted-mock",
        display_name="Scripted Mock",
        adapter_type="scripted_mock",
        auth_status="not_required",
        available=True,
        default_for_roles=["orchestrator", "qa", "review", "fallback"],
        supported_modes=["qa", "review", "read_only", "frontend"],
    ),
)


def list_provider_configs() -> list[ProviderConfig]:
    return list(BUILT_IN_PROVIDER_CONFIGS)
