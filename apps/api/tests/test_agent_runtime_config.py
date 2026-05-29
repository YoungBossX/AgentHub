from collections.abc import Iterator

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine

from app.agent_runtime_config import (
    AgentRuntimeConfigError,
    RuntimeRoleConfig,
    default_runtime_config,
    get_effective_runtime_config,
    upsert_runtime_config,
)
from app.models import Workspace


@pytest.fixture
def db() -> Iterator[DbSession]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as session:
        yield session


def test_default_runtime_config_preserves_existing_behavior(db: DbSession) -> None:
    workspace = _workspace(db)

    config = get_effective_runtime_config(db, workspace.id)
    payload = config.to_payload()

    assert config.config_source == "default"
    assert payload["workspaceId"] == workspace.id
    assert set(payload["roles"]) == {"planner", "frontend", "backend", "review"}
    assert payload["roles"]["planner"] == {
        "role": "planner",
        "agentProfileId": None,
        "providerId": None,
        "adapterType": None,
        "mode": "read_only",
        "enabled": False,
        "fallbackPolicy": "environment_default",
    }
    assert payload["roles"]["frontend"]["enabled"] is False
    assert payload["roles"]["backend"]["mode"] == "backend"


def test_runtime_config_round_trips_workspace_role_defaults(db: DbSession) -> None:
    workspace = _workspace(db)

    upsert_runtime_config(
        db,
        workspace.id,
        {
            "planner": RuntimeRoleConfig(
                role="planner",
                agent_profile_id="orchestrator-profile",
                provider_id="claude-cli-planner",
                adapter_type="claude_cli",
                mode="read_only",
                enabled=True,
                fallback_policy="deterministic",
            ),
            "frontend": RuntimeRoleConfig(
                role="frontend",
                agent_profile_id="frontend-profile",
                provider_id="local-claude-code-cli",
                adapter_type="claude_code",
                mode="frontend",
                enabled=True,
                fallback_policy="explicit_only",
            ),
        },
    )

    config = get_effective_runtime_config(db, workspace.id)
    payload = config.to_payload()

    assert config.config_source == "workspace"
    assert payload["roles"]["planner"]["providerId"] == "claude-cli-planner"
    assert payload["roles"]["planner"]["fallbackPolicy"] == "deterministic"
    assert payload["roles"]["frontend"]["agentProfileId"] == "frontend-profile"
    assert payload["roles"]["backend"]["enabled"] is False
    assert payload["roles"]["review"]["mode"] == "read_only"


def test_runtime_config_rejects_unknown_role(db: DbSession) -> None:
    workspace = _workspace(db)

    with pytest.raises(AgentRuntimeConfigError, match="Unsupported runtime config role"):
        upsert_runtime_config(
            db,
            workspace.id,
            {
                "shell": RuntimeRoleConfig(
                    role="shell",
                    agent_profile_id="unsafe",
                    provider_id="local-shell",
                    adapter_type="shell",
                    mode="debug",
                    enabled=True,
                )
            },
        )


def test_default_runtime_config_payload_is_serializable() -> None:
    payload = default_runtime_config("workspace-1").to_payload()

    assert payload["configSource"] == "default"
    assert payload["roles"]["review"]["fallbackPolicy"] == "environment_default"


def _workspace(db: DbSession) -> Workspace:
    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace
