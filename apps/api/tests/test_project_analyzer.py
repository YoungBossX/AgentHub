from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine

from app.main import app, get_db
from app.models import Workspace
from app.project_analyzer import analyze_external_project


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


def test_analyzer_detects_vite_react_project(tmp_path: Path) -> None:
    project = tmp_path / "vite-app"
    (project / "src").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n")
    (project / "vite.config.ts").write_text("import react from '@vitejs/plugin-react'\n")
    (project / "package.json").write_text(
        """
        {
          "scripts": {
            "dev": "vite",
            "test": "vitest",
            "check": "tsc --noEmit",
            "build": "vite build"
          },
          "dependencies": {"@vitejs/plugin-react": "latest", "react": "latest"},
          "devDependencies": {"vite": "latest", "vitest": "latest"}
        }
        """
    )

    analysis = analyze_external_project(str(project))

    assert analysis.analysis_status == "ready"
    assert analysis.project_type == "vite-react"
    assert analysis.detected_framework == "vite-react"
    assert analysis.package_manager == "pnpm"
    assert analysis.allowed_paths == ("src", "tests")
    assert analysis.dev_command == "pnpm dev"
    assert analysis.test_command == "pnpm test"
    assert analysis.check_command == "pnpm check"
    assert analysis.build_command == "pnpm build"
    assert analysis.preview_command == "pnpm dev"
    assert analysis.project_profile.profile_id == "vite-react"
    assert analysis.project_profile.preview_strategy == "vite-dev-server"
    assert analysis.project_profile.commands.build == "pnpm build"
    assert "node_modules" in analysis.denied_paths
    assert "dist" in analysis.denied_paths


def test_analyzer_detects_nextjs_project(tmp_path: Path) -> None:
    project = tmp_path / "next-app"
    (project / "app").mkdir(parents=True)
    (project / "components").mkdir()
    (project / "package-lock.json").write_text("{}\n")
    (project / "next.config.js").write_text("module.exports = {}\n")
    (project / "package.json").write_text(
        """
        {
          "scripts": {"dev": "next dev", "test": "vitest", "build": "next build"},
          "dependencies": {"next": "latest", "react": "latest"}
        }
        """
    )

    analysis = analyze_external_project(str(project))

    assert analysis.analysis_status == "ready"
    assert analysis.project_type == "nextjs"
    assert analysis.package_manager == "npm"
    assert analysis.project_profile.profile_id == "nextjs-react"
    assert analysis.project_profile.preview_strategy == "next-dev-server"
    assert analysis.allowed_paths == ("app", "components")
    assert analysis.dev_command == "npm run dev"
    assert analysis.test_command == "npm run test"
    assert analysis.build_command == "npm run build"


def test_analyzer_detects_fastapi_project(tmp_path: Path) -> None:
    project = tmp_path / "api"
    (project / "app").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "requirements.txt").write_text("fastapi\nuvicorn\npytest\n")
    (project / "app" / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n"
    )

    analysis = analyze_external_project(str(project))

    assert analysis.analysis_status == "ready"
    assert analysis.project_type == "fastapi"
    assert analysis.package_manager == "pip"
    assert analysis.project_profile.profile_id == "fastapi-python"
    assert analysis.project_profile.preview_strategy == "python-api"
    assert analysis.allowed_paths == ("app", "tests")
    assert analysis.dev_command == (
        "uvicorn app.main:app --reload --host 127.0.0.1 --port <port>"
    )
    assert analysis.test_command == "pytest"
    assert analysis.check_command == "python -m compileall ."
    assert analysis.preview_command is None


def test_analyzer_detects_node_api_project(tmp_path: Path) -> None:
    project = tmp_path / "node-api"
    (project / "src").mkdir(parents=True)
    (project / "src" / "server.ts").write_text("export const server = true\n")
    (project / "package.json").write_text(
        """
        {
          "scripts": {"dev": "tsx src/server.ts", "test": "vitest"},
          "dependencies": {"express": "latest"}
        }
        """
    )

    analysis = analyze_external_project(str(project))

    assert analysis.analysis_status == "ready"
    assert analysis.project_type == "node-api"
    assert analysis.project_profile.profile_id == "generic-repo"
    assert analysis.package_manager == "npm"
    assert analysis.allowed_paths == ("src",)
    assert analysis.dev_command == "npm run dev"
    assert analysis.test_command == "npm run test"


def test_analyzer_detects_python_package_project(tmp_path: Path) -> None:
    project = tmp_path / "python-package"
    (project / "src").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "pyproject.toml").write_text("[project]\nname = 'sample'\n")
    (project / "uv.lock").write_text("version = 1\n")

    analysis = analyze_external_project(str(project))

    assert analysis.analysis_status == "ready"
    assert analysis.project_type == "python-package"
    assert analysis.project_profile.profile_id == "generic-repo"
    assert analysis.package_manager == "uv"
    assert analysis.allowed_paths == ("src", "tests")
    assert analysis.test_command == "pytest"
    assert analysis.check_command == "python -m compileall ."


def test_analyzer_marks_unknown_project_as_needing_confirmation(
    tmp_path: Path,
) -> None:
    project = tmp_path / "unknown"
    project.mkdir()
    (project / "README.md").write_text("no recognizable project markers\n")

    analysis = analyze_external_project(str(project))

    assert analysis.analysis_status == "needs_confirmation"
    assert analysis.project_type == "unknown"
    assert analysis.package_manager == "unknown"
    assert analysis.project_profile.profile_id == "generic-repo"
    assert analysis.project_profile.status == "needs_confirmation"
    assert analysis.allowed_paths == ()
    assert analysis.confidence == "low"
    assert "Project type could not be inferred from known markers." in analysis.analysis_warnings


def test_analyzer_api_returns_analysis_result(
    client: TestClient,
    tmp_path: Path,
) -> None:
    project = tmp_path / "vite-app"
    (project / "src").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "package.json").write_text(
        """
        {
          "scripts": {"dev": "vite", "test": "vitest"},
          "dependencies": {"react": "latest"},
          "devDependencies": {"vite": "latest"}
        }
        """
    )
    workspace = client.get("/workspaces/demo").json()

    response = client.post(
        f"/workspaces/{workspace['id']}/external-targets/analyze",
        json={"rootPath": str(project)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["projectType"] == "vite-react"
    assert body["analysisStatus"] == "ready"
    assert body["allowedPaths"] == ["src", "tests"]
    assert body["testCommand"] == "npm run test"
    assert body["projectProfile"]["profileId"] == "vite-react"
    assert body["projectProfile"]["previewStrategy"] == "vite-dev-server"
