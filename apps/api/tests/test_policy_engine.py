from typing import Optional

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
    evaluate_command_policy,
    evaluate_deploy_policy,
    evaluate_network_policy,
    evaluate_path_policy,
    evaluate_platform_maintenance_policy,
)
from app.project_profiles import build_project_profile
from app.target_registry import AGENTHUB_PLATFORM_TARGET_ID, get_target, TargetProject


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


def test_policy_engine_evaluates_configured_command() -> None:
    target = _target(check_command="pnpm check")

    allowed = evaluate_command_policy(
        target=target,
        command_type="check",
        command="pnpm check",
    )
    denied = evaluate_command_policy(
        target=target,
        command_type="build",
        command="pnpm build",
    )

    assert allowed.outcome == PolicyOutcome.ALLOW
    assert denied.outcome == PolicyOutcome.DENY
    assert denied.command_type == "build"


def test_policy_engine_evaluates_target_paths(tmp_path) -> None:
    worktree = tmp_path / "worktree"
    (worktree / "src").mkdir(parents=True)
    target = _target()

    allowed = evaluate_path_policy(
        target=target,
        path="src/App.tsx",
        worktree_path=str(worktree),
    )
    denied = evaluate_path_policy(
        target=target,
        path=".env",
        worktree_path=str(worktree),
    )

    assert allowed.outcome == PolicyOutcome.ALLOW
    assert denied.outcome == PolicyOutcome.DENY
    assert denied.to_evidence()["metadata"]["path"] == "[redacted]"


def test_policy_engine_network_defaults_to_approval() -> None:
    denied = evaluate_network_policy()
    approved = evaluate_network_policy(network_approved=True)

    assert denied.outcome == PolicyOutcome.REQUIRE_APPROVAL
    assert approved.outcome == PolicyOutcome.ALLOW


def test_policy_engine_deploy_policy_is_conservative() -> None:
    target = _target()

    local = evaluate_deploy_policy(
        provider_id="local_staging",
        environment="staging",
        target=target,
    )
    external = evaluate_deploy_policy(
        provider_id="vercel",
        environment="staging",
        target=target,
    )
    production = evaluate_deploy_policy(
        provider_id="vercel",
        environment="production",
        target=target,
    )

    assert local.outcome == PolicyOutcome.ALLOW
    assert external.outcome == PolicyOutcome.REQUIRE_APPROVAL
    assert production.outcome == PolicyOutcome.DENY


def test_policy_engine_platform_maintenance_requires_elevated_approval() -> None:
    platform = get_target(AGENTHUB_PLATFORM_TARGET_ID)
    denied = evaluate_platform_maintenance_policy(target=platform)
    approved = evaluate_platform_maintenance_policy(target=platform, approved=True)

    assert denied.outcome == PolicyOutcome.REQUIRE_ELEVATED_APPROVAL
    assert approved.outcome == PolicyOutcome.ALLOW


def _target(*, check_command: Optional[str] = None) -> TargetProject:
    profile = build_project_profile(
        project_type="vite-react",
        detected_framework="vite-react",
        package_manager="pnpm",
        allowed_paths=("src",),
        dev_command="pnpm dev",
        check_command=check_command,
        analysis_status="manual",
        analysis_warnings=(),
        confidence="high",
    )
    return TargetProject(
        target_id="external-vite",
        name="External Vite",
        type="frontend",
        root="/tmp/external-vite",
        allowed_paths=("src",),
        denied_paths=(".env", ".env.*", ".git", "node_modules", "secrets"),
        allowed_agents=("frontend", "qa", "review"),
        check_command=check_command,
        package_manager="pnpm",
        detected_framework="vite-react",
        project_type="vite-react",
        analysis_status="manual",
        project_profile=profile,
    )
