from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.agent_runtime_config import RuntimeRoleConfig, upsert_runtime_config
from app.main import app, get_db
from app.models import Agent, AgentProfileDraft, Workspace


def test_agent_directory_lists_builtins_drafts_runtime_selection_and_provider_state() -> None:
    with _client() as client:
        workspace_id = _workspace_id()

        response = client.get(f"/workspaces/{workspace_id}/agent-directory")

        assert response.status_code == 200
        entries = response.json()["entries"]
        frontend = _entry_by_role(entries, "frontend")
        assert frontend["entryType"] == "built_in"
        assert frontend["displayName"] == "Frontend Agent"
        assert frontend["providerId"] == "local-codex-cli"
        assert frontend["adapterType"] == "codex"
        assert frontend["authStatus"] == "unchecked"
        assert frontend["available"] is True
        assert "code_write" in frontend["capabilityTags"]
        assert "frontend" in frontend["supportedModes"]
        assert frontend["safeForWrite"] is True
        assert frontend["runtimeSelectedForRoles"] == ["frontend"]
        assert frontend["compatibility"]["compatible"] is True
        assert frontend["compatibility"]["reasons"] == []

        draft = next(entry for entry in entries if entry["entryType"] == "draft")
        assert draft["displayName"] == "Accessibility Reviewer"
        assert draft["status"] == "draft_only"
        assert draft["available"] is False
        assert draft["safeForWrite"] is False
        assert draft["safeForReview"] is True

        serialized = str(response.json())
        forbidden = ["apiKey", "api_key", "secret", "token", "credential"]
        assert all(value not in serialized for value in forbidden)


def test_agent_directory_rejects_unknown_workspace() -> None:
    with _client() as client:
        response = client.get("/workspaces/missing-workspace/agent-directory")

        assert response.status_code == 404


def test_agent_directory_compatibility_check_reports_reasons() -> None:
    with _client() as client:
        workspace_id = _workspace_id()
        entries = client.get(f"/workspaces/{workspace_id}/agent-directory").json()["entries"]
        frontend = _entry_by_role(entries, "frontend")
        draft = next(entry for entry in entries if entry["entryType"] == "draft")

        compatible = client.post(
            f"/workspaces/{workspace_id}/agent-directory/check-compatibility",
            json={
                "agentProfileId": frontend["agentProfileId"],
                "providerId": "local-codex-cli",
                "adapterType": "codex",
                "role": "frontend",
                "targetId": "demo-frontend",
                "mode": "frontend",
                "requiredCapabilities": ["code_write"],
            },
        )
        incompatible = client.post(
            f"/workspaces/{workspace_id}/agent-directory/check-compatibility",
            json={
                "agentProfileId": draft["agentProfileId"],
                "providerId": "local-scripted-mock",
                "adapterType": "scripted_mock",
                "role": "frontend",
                "targetId": "demo-frontend",
                "mode": "frontend",
                "requiredCapabilities": ["code_write"],
            },
        )

        assert compatible.status_code == 200
        assert compatible.json()["compatible"] is True
        assert incompatible.status_code == 200
        assert incompatible.json()["compatible"] is False
        reasons = " ".join(incompatible.json()["reasons"])
        assert "role" in reasons
        assert "mode" in reasons
        assert "capability" in reasons
        assert "write-safe" in reasons


@contextmanager
def _client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        workspace = Workspace(
            name="AgentHub Demo",
            repo_url="local://apps/demo",
            root_path="apps/demo",
            default_branch="main",
        )
        frontend = Agent(
            name="Frontend Agent",
            role="frontend",
            adapter_type="claude_code",
            provider="local",
        )
        backend = Agent(
            name="Backend Agent",
            role="backend",
            adapter_type="codex",
            provider="local",
        )
        orchestrator = Agent(
            name="Orchestrator",
            role="orchestrator",
            adapter_type="scripted_mock",
            provider="local",
        )
        draft = AgentProfileDraft(
            workspace_id=workspace.id,
            display_name="Accessibility Reviewer",
            avatar_initials="AR",
            role="accessibility_review",
            adapter_type="scripted_mock",
            provider_id="local-scripted-mock",
            capability_tags_json='["code_review","diff_analysis"]',
            supported_targets_json='["demo-frontend"]',
            supported_modes_json='["review","read_only"]',
            safe_for_write=False,
            safe_for_review=True,
            description="Review-only draft.",
            status="draft_only",
        )
        db.add(workspace)
        db.add(frontend)
        db.add(backend)
        db.add(orchestrator)
        db.add(draft)
        db.commit()
        upsert_runtime_config(
            db,
            workspace.id,
            {
                "frontend": RuntimeRoleConfig(
                    role="frontend",
                    agent_profile_id=frontend.id,
                    provider_id="local-claude-code-cli",
                    adapter_type="claude_code",
                    mode="frontend",
                    enabled=True,
                )
            },
        )

    def override_db() -> Iterator[DbSession]:
        with DbSession(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _workspace_id() -> str:
    with next(app.dependency_overrides[get_db]()) as db:
        workspace = db.exec(select(Workspace).where(Workspace.name == "AgentHub Demo")).one()
        return workspace.id


def _entry_by_role(entries: list[dict[str, object]], role: str) -> dict[str, object]:
    return next(entry for entry in entries if entry["role"] == role)
