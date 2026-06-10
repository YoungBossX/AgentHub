from app.agent_target_compatibility import supports_target_id


def test_backend_external_prefix_matches_backend_targets() -> None:
    assert supports_target_id(
        ["demo-backend", "external-backend"],
        "external-backend-agenthub-rehearsals",
        role="backend",
    )


def test_frontend_external_prefix_matches_frontend_targets() -> None:
    assert supports_target_id(
        ["demo-frontend", "external-frontend"],
        "external-frontend-health-app",
        role="frontend",
    )


def test_legacy_external_target_matches_frontend_role() -> None:
    assert supports_target_id(
        ["demo-frontend", "external-frontend"],
        "external-dashboard",
        role="frontend",
    )


def test_legacy_external_target_matches_backend_role() -> None:
    assert supports_target_id(
        ["demo-backend", "external-backend"],
        "external-fastapi",
        role="backend",
    )


def test_frontend_profile_does_not_match_external_backend_target() -> None:
    assert not supports_target_id(
        ["demo-frontend", "external-frontend"],
        "external-backend-agenthub-rehearsals",
        role="frontend",
    )


def test_backend_profile_does_not_match_external_frontend_target() -> None:
    assert not supports_target_id(
        ["demo-backend", "external-backend"],
        "external-frontend-health-app",
        role="backend",
    )


def test_generic_external_matches_external_target_for_review_like_profiles() -> None:
    assert supports_target_id(
        ["demo-frontend", "demo-backend", "external"],
        "external-backend-agenthub-rehearsals",
        role="review",
    )
