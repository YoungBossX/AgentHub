from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from app.guardrails import evaluate_network_access, evaluate_target_path
from app.project_command_policy import evaluate_project_command
from app.target_registry import TargetProject


class PolicyOutcome(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    REQUIRE_ELEVATED_APPROVAL = "require_elevated_approval"


class PolicyCategory(str, Enum):
    COMMAND = "command"
    PATH = "path"
    NETWORK = "network"
    COST = "cost"
    DESTRUCTIVE_CHANGE = "destructive_change"
    DEPLOY = "deploy"
    PLATFORM_MAINTENANCE = "platform_maintenance"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ApprovalType(str, Enum):
    PRODUCT_CONFIRMATION = "product_confirmation"
    SECURITY_APPROVAL = "security_approval"
    ELEVATED_SECURITY_APPROVAL = "elevated_security_approval"


SECRET_KEYS = {
    "api_key",
    "apikey",
    "apiKey",
    "token",
    "secret",
    "password",
    "authorization",
}


@dataclass(frozen=True)
class PolicyDecision:
    category: PolicyCategory
    outcome: PolicyOutcome
    reason: str
    risk_level: RiskLevel = RiskLevel.LOW
    approval_type: Optional[ApprovalType] = None
    target_id: Optional[str] = None
    command_type: Optional[str] = None
    requested_action: Optional[str] = None
    safe_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.outcome == PolicyOutcome.ALLOW

    def to_evidence(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "outcome": self.outcome.value,
            "reason": self.reason,
            "riskLevel": self.risk_level.value,
            "approvalType": self.approval_type.value if self.approval_type else None,
            "targetId": self.target_id,
            "commandType": self.command_type,
            "requestedAction": self.requested_action,
            "metadata": redact_policy_metadata(self.safe_metadata),
        }


def allow(
    category: PolicyCategory,
    reason: str,
    *,
    target_id: Optional[str] = None,
    command_type: Optional[str] = None,
    requested_action: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> PolicyDecision:
    return PolicyDecision(
        category=category,
        outcome=PolicyOutcome.ALLOW,
        reason=reason,
        target_id=target_id,
        command_type=command_type,
        requested_action=requested_action,
        safe_metadata=redact_policy_metadata(metadata or {}),
    )


def deny(
    category: PolicyCategory,
    reason: str,
    *,
    risk_level: RiskLevel = RiskLevel.HIGH,
    target_id: Optional[str] = None,
    command_type: Optional[str] = None,
    requested_action: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> PolicyDecision:
    return PolicyDecision(
        category=category,
        outcome=PolicyOutcome.DENY,
        reason=reason,
        risk_level=risk_level,
        target_id=target_id,
        command_type=command_type,
        requested_action=requested_action,
        safe_metadata=redact_policy_metadata(metadata or {}),
    )


def require_approval(
    category: PolicyCategory,
    reason: str,
    *,
    risk_level: RiskLevel = RiskLevel.MEDIUM,
    approval_type: ApprovalType = ApprovalType.PRODUCT_CONFIRMATION,
    target_id: Optional[str] = None,
    command_type: Optional[str] = None,
    requested_action: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> PolicyDecision:
    return PolicyDecision(
        category=category,
        outcome=PolicyOutcome.REQUIRE_APPROVAL,
        reason=reason,
        risk_level=risk_level,
        approval_type=approval_type,
        target_id=target_id,
        command_type=command_type,
        requested_action=requested_action,
        safe_metadata=redact_policy_metadata(metadata or {}),
    )


def require_elevated_approval(
    category: PolicyCategory,
    reason: str,
    *,
    target_id: Optional[str] = None,
    command_type: Optional[str] = None,
    requested_action: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> PolicyDecision:
    return PolicyDecision(
        category=category,
        outcome=PolicyOutcome.REQUIRE_ELEVATED_APPROVAL,
        reason=reason,
        risk_level=RiskLevel.HIGH,
        approval_type=ApprovalType.ELEVATED_SECURITY_APPROVAL,
        target_id=target_id,
        command_type=command_type,
        requested_action=requested_action,
        safe_metadata=redact_policy_metadata(metadata or {}),
    )


def evaluate_command_policy(
    *,
    target: TargetProject,
    command_type: str,
    command: str,
) -> PolicyDecision:
    decision = evaluate_project_command(
        target=target,
        command_type=command_type,
        command=command,
    )
    metadata = {
        "command": command,
        "targetId": target.target_id,
        "projectType": target.project_type,
        "projectProfileId": (
            target.project_profile.profile_id if target.project_profile else None
        ),
    }
    if decision.allowed:
        return allow(
            PolicyCategory.COMMAND,
            decision.reason,
            target_id=target.target_id,
            command_type=decision.command_type,
            requested_action=decision.command,
            metadata=metadata,
        )
    return deny(
        PolicyCategory.COMMAND,
        decision.reason,
        risk_level=RiskLevel.HIGH,
        target_id=target.target_id,
        command_type=decision.command_type,
        requested_action=decision.command,
        metadata=metadata,
    )


def evaluate_path_policy(
    *,
    target: TargetProject,
    path: str,
    worktree_path: str,
    platform_maintenance_approved: bool = False,
) -> PolicyDecision:
    metadata = {
        "path": path,
        "targetId": target.target_id,
        "targetType": target.type,
    }
    if target.requires_platform_mode and not platform_maintenance_approved:
        return require_elevated_approval(
            PolicyCategory.PLATFORM_MAINTENANCE,
            "AgentHub platform maintenance requires elevated approval.",
            target_id=target.target_id,
            requested_action=f"modify {target.target_id}",
            metadata=metadata,
        )

    decision = evaluate_target_path(
        path,
        worktree_path,
        allowed_paths=target.allowed_paths,
        denied_paths=target.denied_paths,
    )
    if decision.allowed:
        return allow(
            PolicyCategory.PATH,
            "Path is allowed by the registered target policy.",
            target_id=target.target_id,
            requested_action=f"access {path}",
            metadata=metadata,
        )
    reason = decision.approval.reason if decision.approval else "Path is not allowed."
    return deny(
        PolicyCategory.PATH,
        reason,
        target_id=target.target_id,
        requested_action=f"access {path}",
        metadata=metadata,
    )


def evaluate_network_policy(*, network_approved: bool = False) -> PolicyDecision:
    decision = evaluate_network_access(network_approved=network_approved)
    if decision.allowed:
        return allow(
            PolicyCategory.NETWORK,
            "Network access has an explicit approval context.",
            requested_action="network access",
        )
    reason = decision.approval.reason if decision.approval else "Network access requires approval."
    return require_approval(
        PolicyCategory.NETWORK,
        reason,
        approval_type=ApprovalType.SECURITY_APPROVAL,
        risk_level=RiskLevel.MEDIUM,
        requested_action="network access",
    )


def evaluate_deploy_policy(
    *,
    provider_id: str,
    environment: str,
    target: TargetProject,
    approved: bool = False,
) -> PolicyDecision:
    metadata = {
        "providerId": provider_id,
        "environment": environment,
        "targetId": target.target_id,
    }
    if environment == "production":
        return deny(
            PolicyCategory.DEPLOY,
            "Production deploy is outside the local AgentHub reliability scope.",
            target_id=target.target_id,
            requested_action=f"deploy {provider_id} to production",
            metadata=metadata,
        )
    if provider_id in {"mock", "local_staging"}:
        return allow(
            PolicyCategory.DEPLOY,
            "Local or mock deployment follows existing AgentHub deploy gates.",
            target_id=target.target_id,
            requested_action=f"deploy via {provider_id}",
            metadata=metadata,
        )
    if approved:
        return allow(
            PolicyCategory.DEPLOY,
            "External deployment has explicit approval context.",
            target_id=target.target_id,
            requested_action=f"deploy via {provider_id}",
            metadata=metadata,
        )
    return require_approval(
        PolicyCategory.DEPLOY,
        "External deployment requires approval and must not be claimed as ready without evidence.",
        approval_type=ApprovalType.PRODUCT_CONFIRMATION,
        risk_level=RiskLevel.MEDIUM,
        target_id=target.target_id,
        requested_action=f"deploy via {provider_id}",
        metadata=metadata,
    )


def evaluate_platform_maintenance_policy(
    *,
    target: TargetProject,
    approved: bool = False,
) -> PolicyDecision:
    if not target.requires_platform_mode:
        return allow(
            PolicyCategory.PLATFORM_MAINTENANCE,
            "Target does not require platform maintenance approval.",
            target_id=target.target_id,
            requested_action=f"use {target.target_id}",
        )
    if approved:
        return allow(
            PolicyCategory.PLATFORM_MAINTENANCE,
            "Platform maintenance approval is present.",
            target_id=target.target_id,
            requested_action=f"use {target.target_id}",
        )
    return require_elevated_approval(
        PolicyCategory.PLATFORM_MAINTENANCE,
        "AgentHub platform maintenance requires elevated approval.",
        target_id=target.target_id,
        requested_action=f"use {target.target_id}",
    )


def redact_policy_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        str(key): _redact_value(str(key), value)
        for key, value in metadata.items()
    }


def _redact_value(key: str, value: Any) -> Any:
    if _is_secret_key(key):
        return "[redacted]"
    if isinstance(value, dict):
        return redact_policy_metadata(value)
    if isinstance(value, list):
        return [_redact_sequence_value(item) for item in value]
    if isinstance(value, str):
        return _redact_string(value)
    return value


def _redact_sequence_value(value: Any) -> Any:
    if isinstance(value, dict):
        return redact_policy_metadata(value)
    if isinstance(value, str):
        return _redact_string(value)
    return value


def _is_secret_key(key: str) -> bool:
    normalized = key.replace("-", "_").lower()
    return normalized in {secret.lower() for secret in SECRET_KEYS}


def _redact_string(value: str) -> str:
    if ".env" in value or "secrets/" in value or "secrets\\" in value:
        return "[redacted]"
    expanded = Path(value).expanduser()
    if expanded.is_absolute() and any(part in {".git", "node_modules"} for part in expanded.parts):
        return "[redacted]"
    if len(value) > 500:
        return f"{value[:497].rstrip()}..."
    return value
