from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


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
