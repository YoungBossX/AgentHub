import pytest

from app.agent_capabilities import (
    SUPPORTED_AGENT_MODES,
    SUPPORTED_CAPABILITY_TAGS,
    validate_capability_tags,
    validate_supported_modes,
)


def test_controlled_agent_modes_and_capability_tags_are_defined() -> None:
    assert SUPPORTED_AGENT_MODES == {
        "frontend",
        "backend",
        "qa",
        "review",
        "platform_maintenance",
        "read_only",
        "debug",
    }
    assert SUPPORTED_CAPABILITY_TAGS == {
        "code_write",
        "code_review",
        "test_run",
        "diff_analysis",
        "preview",
        "deploy_staging",
        "platform_change",
    }


def test_capability_and_mode_validation_rejects_unknown_values() -> None:
    with pytest.raises(ValueError, match="Unsupported capability tag"):
        validate_capability_tags(["code_write", "marketplace_install"], source="test")

    with pytest.raises(ValueError, match="Unsupported agent mode"):
        validate_supported_modes(["frontend", "direct-chat"], source="test")
