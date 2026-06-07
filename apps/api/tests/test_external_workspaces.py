from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine

from app.external_workspaces import DEFAULT_EXTERNAL_DENIED_PATHS
from app.main import app, get_db
from app.models import Session, Workspace
from app.target_registry import (
    AGENTHUB_PLATFORM_TARGET_ID,
    DEMO_BACKEND_TARGET_ID,
    DEMO_FRONTEND_TARGET_ID,
    list_targets,
)


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
        session = Session(
            workspace_id=workspace.id,
            title="External target session",
            bound_branch="main",
            worktree_path=".worktrees/external-target-session",
        )
        db.add(workspace)
        db.add(session)
        db.commit()

    def override_db() -> Iterator[DbSession]:
        with DbSession(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_register_external_project_target(client: TestClient, tmp_path: Path) -> None:
    project = tmp_path / "sample-vite"
    (project / "src").mkdir(parents=True)
    (project / "src" / "App.tsx").write_text("export default function App() { return null }\n")
    (project / "package.json").write_text('{"scripts":{"dev":"vite","test":"vitest"}}\n')
    workspace = client.get("/workspaces/demo").json()

    response = client.post(
        f"/workspaces/{workspace['id']}/external-targets",
        json={
            "targetId": "external-sample-vite",
            "name": "Sample Vite",
            "rootPath": str(project),
            "projectType": "vite-react",
            "allowedPaths": ["src"],
            "devCommand": "pnpm dev",
            "testCommand": "pnpm test",
            "checkCommand": "pnpm check",
            "buildCommand": "pnpm build",
            "previewCommand": "pnpm dev --host 127.0.0.1 --port <port>",
            "stagingOutputDir": "dist",
            "stagingServeCommand": "python -m http.server <port> --bind 127.0.0.1 --directory dist",
            "deployProviderIds": ["local_staging"],
            "packageManager": "pnpm",
            "detectedFramework": "vite-react",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["workspaceId"] == workspace["id"]
    assert body["targetId"] == "external-sample-vite"
    assert body["rootPath"] == str(project.resolve())
    assert body["projectType"] == "vite-react"
    assert body["allowedPaths"] == ["src"]
    assert body["devCommand"] == "pnpm dev"
    assert body["testCommand"] == "pnpm test"
    assert body["checkCommand"] == "pnpm check"
    assert body["buildCommand"] == "pnpm build"
    assert body["previewCommand"] == "pnpm dev --host 127.0.0.1 --port <port>"
    assert body["stagingOutputDir"] == "dist"
    assert body["stagingServeCommand"] == "python -m http.server <port> --bind 127.0.0.1 --directory dist"
    assert body["deployProviderIds"] == ["local_staging"]
    assert body["packageManager"] == "pnpm"
    assert body["detectedFramework"] == "vite-react"
    assert body["analysisStatus"] == "manual"
    for denied_path in DEFAULT_EXTERNAL_DENIED_PATHS:
        assert denied_path in body["deniedPaths"]

    list_response = client.get(f"/workspaces/{workspace['id']}/external-targets")
    assert list_response.status_code == 200
    assert [target["targetId"] for target in list_response.json()] == [
        "external-sample-vite"
    ]

    read_response = client.get(
        f"/workspaces/{workspace['id']}/external-targets/external-sample-vite"
    )
    assert read_response.status_code == 200
    assert read_response.json()["targetId"] == "external-sample-vite"

    targets_response = client.get(f"/workspaces/{workspace['id']}/targets")
    assert targets_response.status_code == 200
    targets = {target["targetId"]: target for target in targets_response.json()}
    assert {
        DEMO_FRONTEND_TARGET_ID,
        DEMO_BACKEND_TARGET_ID,
        AGENTHUB_PLATFORM_TARGET_ID,
        "external-sample-vite",
    } == set(targets)
    assert targets["external-sample-vite"]["root"] == str(project.resolve())
    assert targets["external-sample-vite"]["allowedPaths"] == ["src"]
    assert targets["external-sample-vite"]["stagingOutputDir"] == "dist"
    assert targets["external-sample-vite"]["deployProviderIds"] == ["local_staging"]
    assert targets["external-sample-vite"]["packageManager"] == "pnpm"

    session = client.get(f"/workspaces/{workspace['id']}/sessions").json()[0]
    selection_response = client.patch(
        f"/sessions/{session['id']}/target-selection",
        json={"frontendTargetId": "external-sample-vite"},
    )
    assert selection_response.status_code == 200
    assert selection_response.json()["activeFrontendTargetId"] == "external-sample-vite"


def test_register_external_project_target_can_allow_selected_folder_scope(
    client: TestClient,
    tmp_path: Path,
) -> None:
    project = tmp_path / "plain-folder"
    project.mkdir()
    workspace = client.get("/workspaces/demo").json()

    response = client.post(
        f"/workspaces/{workspace['id']}/external-targets",
        json={
            "targetId": "external-plain-folder",
            "name": "Plain Folder",
            "rootPath": str(project),
            "projectType": "unknown",
            "allowedPaths": ["*"],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["rootPath"] == str(project.resolve())
    assert body["projectType"] == "unknown"
    assert body["allowedPaths"] == ["*"]
    assert ".git" in body["deniedPaths"]
    assert "node_modules" in body["deniedPaths"]


def test_register_selected_folder_scope_can_create_backend_target(
    client: TestClient,
    tmp_path: Path,
) -> None:
    project = tmp_path / "plain-backend"
    project.mkdir()
    workspace = client.get("/workspaces/demo").json()

    response = client.post(
        f"/workspaces/{workspace['id']}/external-targets",
        json={
            "targetId": "external-backend-plain-folder",
            "name": "Backend Folder",
            "rootPath": str(project),
            "projectType": "external-backend",
            "allowedPaths": ["*"],
        },
    )
    targets_response = client.get(f"/workspaces/{workspace['id']}/targets")

    assert response.status_code == 201
    targets = {target["targetId"]: target for target in targets_response.json()}
    assert targets["external-backend-plain-folder"]["type"] == "backend"
    assert targets["external-backend-plain-folder"]["allowedAgents"] == [
        "backend",
        "qa",
        "review",
    ]


def test_session_target_selection_rejects_wrong_or_unknown_target(
    client: TestClient,
    tmp_path: Path,
) -> None:
    project = tmp_path / "sample-api"
    (project / "app").mkdir(parents=True)
    workspace = client.get("/workspaces/demo").json()
    create_response = client.post(
        f"/workspaces/{workspace['id']}/external-targets",
        json={
            "targetId": "external-sample-api",
            "name": "Sample API",
            "rootPath": str(project),
            "projectType": "fastapi",
            "allowedPaths": ["app"],
        },
    )
    assert create_response.status_code == 201
    session = client.get(f"/workspaces/{workspace['id']}/sessions").json()[0]

    wrong_type = client.patch(
        f"/sessions/{session['id']}/target-selection",
        json={"frontendTargetId": "external-sample-api"},
    )
    unknown = client.patch(
        f"/sessions/{session['id']}/target-selection",
        json={"backendTargetId": "external-missing"},
    )

    assert wrong_type.status_code == 400
    assert unknown.status_code == 400


def test_registration_rejects_unsafe_roots(
    client: TestClient,
    tmp_path: Path,
) -> None:
    workspace = client.get("/workspaces/demo").json()
    unsafe_roots = [Path.home(), Path("/")]

    for root in unsafe_roots:
        response = client.post(
            f"/workspaces/{workspace['id']}/external-targets",
            json={
                "name": f"Unsafe {root}",
                "rootPath": str(root),
                "allowedPaths": ["src"],
            },
        )
        assert response.status_code == 400

    missing = tmp_path / "missing-project"
    missing_response = client.post(
        f"/workspaces/{workspace['id']}/external-targets",
        json={
            "name": "Missing",
            "rootPath": str(missing),
            "allowedPaths": ["src"],
        },
    )
    assert missing_response.status_code == 400


def test_registration_requires_bounded_relative_allowed_paths(
    client: TestClient,
    tmp_path: Path,
) -> None:
    project = tmp_path / "sample"
    (project / "src").mkdir(parents=True)
    workspace = client.get("/workspaces/demo").json()

    for allowed_paths in ([], ["."], ["../other"], [str(project / "src")]):
        response = client.post(
            f"/workspaces/{workspace['id']}/external-targets",
            json={
                "name": "Unsafe paths",
                "rootPath": str(project),
                "allowedPaths": allowed_paths,
            },
        )
        assert response.status_code == 400


def test_browse_external_target_folders_lists_starts_and_children(
    client: TestClient,
    tmp_path: Path,
) -> None:
    project = tmp_path / "plain-folder"
    (project / "app").mkdir(parents=True)
    (project / "node_modules").mkdir()
    (project / ".git").mkdir()
    (project / "README.md").write_text("not a folder\n")
    workspace = client.get("/workspaces/demo").json()

    starts_response = client.get(
        f"/workspaces/{workspace['id']}/external-targets/folders"
    )
    children_response = client.get(
        f"/workspaces/{workspace['id']}/external-targets/folders",
        params={"path": str(project)},
    )

    assert starts_response.status_code == 200
    starts_body = starts_response.json()
    assert "starts" in starts_body
    assert any(start["label"] == "工作区附近" for start in starts_body["starts"])

    assert children_response.status_code == 200
    children_body = children_response.json()
    assert children_body["currentPath"] == str(project.resolve())
    assert children_body["parentPath"] == str(project.parent.resolve())
    assert [child["name"] for child in children_body["children"]] == ["app"]


def test_browse_external_target_folders_rejects_unknown_workspace(
    client: TestClient,
    tmp_path: Path,
) -> None:
    response = client.get(
        "/workspaces/missing/external-targets/folders",
        params={"path": str(tmp_path)},
    )

    assert response.status_code == 404


def test_external_registration_does_not_mutate_builtin_registry() -> None:
    targets = {target.target_id for target in list_targets()}

    assert targets == {
        DEMO_FRONTEND_TARGET_ID,
        DEMO_BACKEND_TARGET_ID,
        AGENTHUB_PLATFORM_TARGET_ID,
    }
