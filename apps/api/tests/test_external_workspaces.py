from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine

from app.external_workspaces import DEFAULT_EXTERNAL_DENIED_PATHS
from app.main import app, get_db
from app.models import Workspace
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
        db.add(workspace)
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
    assert targets["external-sample-vite"]["packageManager"] == "pnpm"


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


def test_external_registration_does_not_mutate_builtin_registry() -> None:
    targets = {target.target_id for target in list_targets()}

    assert targets == {
        DEMO_FRONTEND_TARGET_ID,
        DEMO_BACKEND_TARGET_ID,
        AGENTHUB_PLATFORM_TARGET_ID,
    }
