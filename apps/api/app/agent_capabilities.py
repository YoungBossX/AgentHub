SUPPORTED_AGENT_MODES = {
    "frontend",
    "backend",
    "qa",
    "review",
    "platform_maintenance",
    "read_only",
    "debug",
}

SUPPORTED_CAPABILITY_TAGS = {
    "code_write",
    "code_review",
    "test_run",
    "diff_analysis",
    "preview",
    "deploy_staging",
    "platform_change",
}


def validate_supported_modes(modes: list[str], *, source: str) -> list[str]:
    unsupported = sorted(set(modes).difference(SUPPORTED_AGENT_MODES))
    if unsupported:
        raise ValueError(
            f"Unsupported agent mode(s) for {source}: {', '.join(unsupported)}"
        )
    return modes


def validate_capability_tags(tags: list[str], *, source: str) -> list[str]:
    unsupported = sorted(set(tags).difference(SUPPORTED_CAPABILITY_TAGS))
    if unsupported:
        raise ValueError(
            f"Unsupported capability tag(s) for {source}: {', '.join(unsupported)}"
        )
    return tags
