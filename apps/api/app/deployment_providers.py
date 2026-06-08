from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DeploymentProviderMetadata:
    provider_id: str
    display_name: str
    provider_type: str
    supported_artifact_kinds: tuple[str, ...]
    supported_target_types: tuple[str, ...]
    auth_status: str
    available: bool
    requires_approval: bool
    secret_env_vars: tuple[str, ...] = ()
    description: str = ""

    def to_payload(self) -> dict[str, Any]:
        return {
            "providerId": self.provider_id,
            "displayName": self.display_name,
            "providerType": self.provider_type,
            "supportedArtifactKinds": list(self.supported_artifact_kinds),
            "supportedTargetTypes": list(self.supported_target_types),
            "authStatus": self.auth_status,
            "available": self.available,
            "requiresApproval": self.requires_approval,
            "secretEnvVars": list(self.secret_env_vars),
            "description": self.description,
        }


def list_deployment_providers() -> list[DeploymentProviderMetadata]:
    return [
        DeploymentProviderMetadata(
            provider_id="local_staging",
            display_name="Local Staging",
            provider_type="local_static",
            supported_artifact_kinds=("preview", "web_preview"),
            supported_target_types=("frontend",),
            auth_status="configured",
            available=True,
            requires_approval=False,
            description="Serve a built frontend target from the local machine.",
        ),
        DeploymentProviderMetadata(
            provider_id="manual_external",
            display_name="Manual External Handoff",
            provider_type="manual_handoff",
            supported_artifact_kinds=("deployment", "preview", "web_preview"),
            supported_target_types=("frontend",),
            auth_status="configured",
            available=True,
            requires_approval=True,
            description="Create a handoff card for a user-managed external deploy.",
        ),
        _external_provider(
            provider_id="vercel",
            display_name="Vercel",
            env_vars=("VERCEL_TOKEN",),
        ),
        _external_provider(
            provider_id="netlify",
            display_name="Netlify",
            env_vars=("NETLIFY_AUTH_TOKEN",),
        ),
        _external_provider(
            provider_id="custom_static_host",
            display_name="Custom Static Host",
            env_vars=("AGENTHUB_CUSTOM_STATIC_HOST_TOKEN",),
        ),
    ]


def get_deployment_provider(provider_id: str) -> DeploymentProviderMetadata | None:
    return next(
        (
            provider
            for provider in list_deployment_providers()
            if provider.provider_id == provider_id
        ),
        None,
    )


def _external_provider(
    *,
    provider_id: str,
    display_name: str,
    env_vars: tuple[str, ...],
) -> DeploymentProviderMetadata:
    configured = all(bool(os.environ.get(env_var)) for env_var in env_vars)
    return DeploymentProviderMetadata(
        provider_id=provider_id,
        display_name=display_name,
        provider_type="external_static",
        supported_artifact_kinds=("preview", "web_preview", "deployment"),
        supported_target_types=("frontend",),
        auth_status="configured" if configured else "missing_key",
        available=configured,
        requires_approval=True,
        secret_env_vars=env_vars,
        description=(
            f"{display_name} deployment provider metadata. Real deploy execution "
            "requires configured credentials and approval."
        ),
    )
