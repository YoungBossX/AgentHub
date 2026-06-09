from app.policy_engine import (
    ApprovalType,
    PolicyCategory,
    PolicyOutcome,
    RiskLevel,
    allow,
    deny,
    redact_policy_metadata,
    require_approval,
    require_elevated_approval,
)


def test_policy_decision_allow_contract() -> None:
    decision = allow(
        PolicyCategory.COMMAND,
        "Command matches the target profile.",
        target_id="external-vite",
        command_type="build",
        requested_action="pnpm build",
        metadata={"command": "pnpm build"},
    )

    assert decision.allowed is True
    assert decision.outcome == PolicyOutcome.ALLOW
    assert decision.to_evidence() == {
        "category": "command",
        "outcome": "allow",
        "reason": "Command matches the target profile.",
        "riskLevel": "low",
        "approvalType": None,
        "targetId": "external-vite",
        "commandType": "build",
        "requestedAction": "pnpm build",
        "metadata": {"command": "pnpm build"},
    }


def test_policy_decision_deny_contract() -> None:
    decision = deny(
        PolicyCategory.PATH,
        "Path is protected.",
        requested_action="edit .env",
        metadata={"path": "/tmp/project/.env"},
    )

    evidence = decision.to_evidence()

    assert decision.allowed is False
    assert decision.outcome == PolicyOutcome.DENY
    assert evidence["riskLevel"] == "high"
    assert evidence["metadata"]["path"] == "[redacted]"


def test_policy_decision_requires_approval_contract() -> None:
    decision = require_approval(
        PolicyCategory.NETWORK,
        "Network access requires approval.",
        approval_type=ApprovalType.SECURITY_APPROVAL,
        risk_level=RiskLevel.MEDIUM,
        requested_action="network access",
    )

    assert decision.outcome == PolicyOutcome.REQUIRE_APPROVAL
    assert decision.approval_type == ApprovalType.SECURITY_APPROVAL
    assert decision.risk_level == RiskLevel.MEDIUM


def test_policy_decision_requires_elevated_approval_contract() -> None:
    decision = require_elevated_approval(
        PolicyCategory.PLATFORM_MAINTENANCE,
        "AgentHub platform maintenance requires elevated approval.",
        target_id="agenthub-platform",
    )

    assert decision.outcome == PolicyOutcome.REQUIRE_ELEVATED_APPROVAL
    assert decision.approval_type == ApprovalType.ELEVATED_SECURITY_APPROVAL
    assert decision.risk_level == RiskLevel.HIGH


def test_policy_metadata_redacts_secret_keys_and_protected_paths() -> None:
    metadata = redact_policy_metadata(
        {
            "apiKey": "sk-live-secret",
            "nested": {"token": "abc"},
            "paths": ["/tmp/project/.git/config", "/tmp/project/src/App.tsx"],
            "message": "safe",
        }
    )

    assert metadata["apiKey"] == "[redacted]"
    assert metadata["nested"]["token"] == "[redacted]"
    assert metadata["paths"] == ["[redacted]", "/tmp/project/src/App.tsx"]
    assert metadata["message"] == "safe"
