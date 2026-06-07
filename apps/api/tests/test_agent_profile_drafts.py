from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.main import app, get_db
from app.models import Agent, AgentProfileDraft, Workspace


@pytest.fixture
def client() -> Iterator[TestClient]:
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
        db.add(workspace)
        db.add(
            Agent(
                name="QA Agent",
                role="qa",
                adapter_type="scripted_mock",
                provider="local",
            )
        )
        db.add(
            Workspace(
                name="Empty Workspace",
                repo_url="local://apps/empty",
                root_path="apps/empty",
                default_branch="main",
            )
        )
        db.commit()

    def override_db() -> Iterator[DbSession]:
        with DbSession(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_safe_custom_agent_draft_is_review_only_metadata(client: TestClient) -> None:
    workspace_id = _workspace_id()

    response = client.post(
        f"/workspaces/{workspace_id}/agent-profile-drafts",
        json={
            "displayName": "Accessibility Reviewer",
            "role": "accessibility_review",
            "adapterType": "scripted_mock",
            "providerId": "local-scripted-mock",
            "capabilityTags": ["code_review", "diff_analysis"],
            "supportedTargets": ["demo-frontend"],
            "supportedModes": ["review", "read_only"],
            "description": "Reviews UI accessibility evidence without write access.",
        },
    )

    assert response.status_code == 201
    draft = response.json()
    assert draft["displayName"] == "Accessibility Reviewer"
    assert draft["status"] == "draft_only"
    assert draft["safeForWrite"] is False
    assert draft["safeForReview"] is True
    assert draft["providerId"] == "local-scripted-mock"
    assert draft["supportedTargets"] == ["demo-frontend"]

    registry_response = client.get(f"/workspaces/{workspace_id}/agent-profiles")
    assert registry_response.status_code == 200
    assert any(
        profile["displayName"] == "Accessibility Reviewer"
        and profile["status"] == "draft_only"
        for profile in registry_response.json()
    )


def test_draft_list_is_workspace_scoped_and_empty_without_save(client: TestClient) -> None:
    workspace_id = _workspace_id()
    empty_workspace_id = _workspace_id_by_name("Empty Workspace")

    before_response = client.get(f"/workspaces/{empty_workspace_id}/agent-profile-drafts")
    create_response = client.post(
        f"/workspaces/{workspace_id}/agent-profile-drafts",
        json={
            "displayName": "Read Only Auditor",
            "role": "read_only_auditor",
            "adapterType": "scripted_mock",
            "providerId": "local-scripted-mock",
            "capabilityTags": ["code_review"],
            "supportedTargets": ["demo-frontend"],
            "supportedModes": ["review", "read_only"],
            "description": "Reviews evidence only.",
        },
    )
    workspace_response = client.get(f"/workspaces/{workspace_id}/agent-profile-drafts")
    after_empty_response = client.get(f"/workspaces/{empty_workspace_id}/agent-profile-drafts")

    assert before_response.status_code == 200
    assert before_response.json() == []
    assert create_response.status_code == 201
    assert [draft["displayName"] for draft in workspace_response.json()] == [
        "Read Only Auditor"
    ]
    assert after_empty_response.json() == []


def test_draft_rejects_write_enabled_profile(client: TestClient) -> None:
    response = client.post(
        f"/workspaces/{_workspace_id()}/agent-profile-drafts",
        json={
            "displayName": "Unsafe Writer",
            "role": "unsafe_writer",
            "adapterType": "scripted_mock",
            "providerId": "local-scripted-mock",
            "capabilityTags": ["code_write"],
            "supportedTargets": ["demo-frontend"],
            "supportedModes": ["frontend"],
            "safeForWrite": True,
            "description": "Should not be allowed.",
        },
    )

    assert response.status_code == 400
    assert "not write-enabled" in response.json()["detail"]


def test_draft_rejects_shell_commands_and_unsafe_permissions(client: TestClient) -> None:
    base_payload = {
        "displayName": "Unsafe Tooling",
        "role": "unsafe_tooling",
        "adapterType": "scripted_mock",
        "providerId": "local-scripted-mock",
        "capabilityTags": ["code_review"],
        "supportedTargets": ["demo-frontend"],
        "supportedModes": ["review"],
        "description": "Should not be allowed.",
    }

    shell_response = client.post(
        f"/workspaces/{_workspace_id()}/agent-profile-drafts",
        json={**base_payload, "shellCommands": ["rm -rf ."]},
    )
    permission_response = client.post(
        f"/workspaces/{_workspace_id()}/agent-profile-drafts",
        json={**base_payload, "toolPermissions": ["host_shell"]},
    )
    filesystem_response = client.post(
        f"/workspaces/{_workspace_id()}/agent-profile-drafts",
        json={**base_payload, "unrestrictedFilesystemAccess": True},
    )

    assert shell_response.status_code == 400
    assert "cannot define shell commands" in shell_response.json()["detail"]
    assert permission_response.status_code == 400
    assert "unsafe tool permissions" in permission_response.json()["detail"]
    assert filesystem_response.status_code == 400
    assert "unrestricted filesystem" in filesystem_response.json()["detail"]

    list_response = client.get(f"/workspaces/{_workspace_id()}/agent-profile-drafts")
    assert list_response.status_code == 200
    assert list_response.json() == []


def test_draft_rejects_unknown_provider(client: TestClient) -> None:
    response = client.post(
        f"/workspaces/{_workspace_id()}/agent-profile-drafts",
        json={
            "displayName": "Unknown Provider",
            "role": "unknown_provider",
            "adapterType": "scripted_mock",
            "providerId": "local-opencode",
            "capabilityTags": ["code_review"],
            "supportedTargets": ["demo-frontend"],
            "supportedModes": ["review"],
            "description": "Should not be allowed.",
        },
    )

    assert response.status_code == 400
    assert "Unknown providerId" in response.json()["detail"]


def _workspace_id() -> str:
    return _workspace_id_by_name("AgentHub Demo")


def _workspace_id_by_name(name: str) -> str:
    with next(app.dependency_overrides[get_db]()) as db:
        workspace = db.exec(select(Workspace).where(Workspace.name == name)).one()
        return workspace.id
