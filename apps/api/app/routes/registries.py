from typing import Any

from fastapi import APIRouter

from app.deployment_providers import list_deployment_providers
from app.provider_configs import ProviderConfig, list_provider_configs
from app.schemas import (
    DeploymentProviderRegistryResponse,
    DeploymentProviderResponse,
    ProviderConfigResponse,
)

router = APIRouter()


def provider_config_response(config: ProviderConfig) -> ProviderConfigResponse:
    return ProviderConfigResponse(
        providerId=config.provider_id,
        displayName=config.display_name,
        adapterType=config.adapter_type,
        authStatus=config.auth_status,
        available=config.available,
        defaultForRoles=config.default_for_roles,
        supportedModes=config.supported_modes,
    )


def deployment_provider_response(provider: Any) -> DeploymentProviderResponse:
    return DeploymentProviderResponse(
        providerId=provider.provider_id,
        displayName=provider.display_name,
        providerType=provider.provider_type,
        supportedArtifactKinds=list(provider.supported_artifact_kinds),
        supportedTargetTypes=list(provider.supported_target_types),
        authStatus=provider.auth_status,
        available=provider.available,
        requiresApproval=provider.requires_approval,
        secretEnvVars=list(provider.secret_env_vars),
        description=provider.description,
    )


@router.get("/provider-configs", response_model=list[ProviderConfigResponse])
def read_provider_configs() -> list[ProviderConfigResponse]:
    return [provider_config_response(config) for config in list_provider_configs()]


@router.get("/deployment-providers", response_model=DeploymentProviderRegistryResponse)
def read_deployment_providers() -> DeploymentProviderRegistryResponse:
    return DeploymentProviderRegistryResponse(
        providers=[
            deployment_provider_response(provider)
            for provider in list_deployment_providers()
        ],
    )
