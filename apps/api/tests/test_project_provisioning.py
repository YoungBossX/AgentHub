import json
from collections.abc import Iterator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine

from app.dependencies import get_db, get_worktree_service
from app.main import app
from app.models import Workspace
from app.project_provisioning import plan_project_provisioning
from app.worktrees import safe_path_segment


class FakeWorktreeService:
    def __init__(self, root: Path) -> None:
        self.root = root

    def session_path(self, workspace_id: str, session_id: str) -> Path:
        segment = safe_path_segment(session_id) if session_id else "pending"
        return self.root / safe_path_segment(workspace_id) / segment

    def create_session_worktree(self, workspace: Workspace, session_id: str) -> Path:
        path = self.session_path(workspace.id, session_id)
        path.mkdir(parents=True, exist_ok=True)
        (path / ".git").write_text("fake test worktree\n", encoding="utf-8")
        return path.resolve()


def test_project_provisioning_api_returns_dry_run_plan() -> None:
    client = TestClient(_app_with_memory_db())
    try:
        workspace = client.get("/workspaces/demo").json()

        response = client.post(
            f"/workspaces/{workspace['id']}/project-provisioning/plan",
            json={
                "userRequest": "帮我做一个健康管理系统，有登录、健康登记，需要有前后端，数据库任意",
                "preferredSlug": "health-management",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["projectKind"] == "new_project"
        assert body["defaultFrontendStack"] == "vite-react"
        assert body["defaultBackendStack"] == "fastapi"
        assert [target["role"] for target in body["targetDrafts"]] == [
            "frontend",
            "backend",
        ]
        assert body["targetDrafts"][0]["projectProfile"]["commands"]["build"] == "pnpm build"
        assert "pnpm install" in body["approvalRequiredCommands"]
        assert body["setupSteps"][0] == {
            "role": "frontend",
            "command": "pnpm install",
            "cwd": str(Path(body["projectRoot"]) / "frontend"),
            "reason": "Install frontend dependencies before check, test, build, or preview.",
            "requiresApproval": True,
        }
        assert body["setupSteps"][1] == {
            "role": "backend",
            "command": "pip install -r requirements.txt",
            "cwd": str(Path(body["projectRoot"]) / "backend"),
            "reason": "Install backend dependencies before running API checks or tests.",
            "requiresApproval": True,
        }
    finally:
        app.dependency_overrides.clear()


def test_project_provisioning_apply_scaffolds_registers_targets_and_activates_session(
    tmp_path: Path,
) -> None:
    client = TestClient(_app_with_memory_db(tmp_path / "worktrees"))
    try:
        workspace = client.get("/workspaces/demo").json()
        session = client.post(
            f"/workspaces/{workspace['id']}/sessions",
            json={"title": "Provisioning session"},
        ).json()
        selected_root = tmp_path / "selected-empty-project"
        selected_root.mkdir()

        response = client.post(
            f"/workspaces/{workspace['id']}/project-provisioning/apply",
            json={
                "userRequest": "Build a simple fullstack notes app with frontend and backend API",
                "selectedRootPath": str(selected_root),
                "sessionId": session["id"],
                "preferredSlug": "notes-app",
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["plan"]["projectKind"] == "existing_project"
        assert body["plan"]["projectRoot"] == str(selected_root.resolve())
        assert (selected_root / "frontend" / "src" / "App.tsx").exists()
        assert (selected_root / "frontend" / "vite.config.ts").exists()
        package_json = json.loads((selected_root / "frontend" / "package.json").read_text())
        app_tsconfig = json.loads((selected_root / "frontend" / "tsconfig.app.json").read_text())
        node_tsconfig = json.loads((selected_root / "frontend" / "tsconfig.node.json").read_text())
        assert "@types/node" in package_json["devDependencies"]
        assert (selected_root / "frontend" / "src" / "vite-env.d.ts").exists()
        assert app_tsconfig["compilerOptions"]["moduleResolution"] == "Bundler"
        assert app_tsconfig["compilerOptions"]["tsBuildInfoFile"] == (
            "./node_modules/.tmp/tsconfig.app.tsbuildinfo"
        )
        assert node_tsconfig["compilerOptions"]["moduleResolution"] == "Bundler"
        assert node_tsconfig["compilerOptions"]["noEmit"] is True
        assert node_tsconfig["compilerOptions"]["tsBuildInfoFile"] == (
            "./node_modules/.tmp/tsconfig.node.tsbuildinfo"
        )
        assert node_tsconfig["compilerOptions"]["types"] == ["node"]
        assert (selected_root / "backend" / "app" / "main.py").exists()
        assert (selected_root / "backend" / "requirements.txt").exists()
        assert (selected_root / "docs" / "api-contract.md").exists()
        assert (selected_root / "README.md").exists()
        assert (selected_root / "agenthub.project.json").exists()
        metadata = (selected_root / "agenthub.project.json").read_text()
        assert "notes-app" in metadata
        assert "Pomodoro" not in metadata

        targets = body["registeredTargets"]
        assert [target["targetId"] for target in targets] == [
            "external-frontend-notes-app",
            "external-backend-notes-app",
        ]
        assert targets[0]["rootPath"] == str((selected_root / "frontend").resolve())
        assert targets[1]["rootPath"] == str((selected_root / "backend").resolve())
        assert ".env" in targets[0]["deniedPaths"]
        assert "node_modules" in targets[1]["deniedPaths"]
        assert targets[0]["projectProfile"]["commands"]["build"] == "pnpm build"
        assert targets[1]["projectProfile"]["commands"]["check"] == "python -m compileall ."
        assert body["session"]["activeFrontendTargetId"] == "external-frontend-notes-app"
        assert body["session"]["activeBackendTargetId"] == "external-backend-notes-app"
        assert body["plan"]["setupSteps"][0]["cwd"] == str(
            (selected_root / "frontend").resolve()
        )
        assert body["plan"]["setupSteps"][0]["command"] == "pnpm install"
        assert body["plan"]["setupSteps"][1]["cwd"] == str(
            (selected_root / "backend").resolve()
        )
        assert body["plan"]["setupSteps"][1]["command"] == "pip install -r requirements.txt"
    finally:
        app.dependency_overrides.clear()


def test_project_provisioning_apply_chinese_fullstack_request_registers_backend_target(
    tmp_path: Path,
) -> None:
    client = TestClient(_app_with_memory_db(tmp_path / "worktrees"))
    try:
        workspace = client.get("/workspaces/demo").json()
        session = client.post(
            f"/workspaces/{workspace['id']}/sessions",
            json={"title": "Chinese fullstack provisioning session"},
        ).json()
        selected_root = tmp_path / "selected-empty-project"
        selected_root.mkdir()

        response = client.post(
            f"/workspaces/{workspace['id']}/project-provisioning/apply",
            json={
                "userRequest": "新建全栈项目",
                "selectedRootPath": str(selected_root),
                "sessionId": session["id"],
                "preferredSlug": "pomodoro-app",
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert [target["targetId"] for target in body["registeredTargets"]] == [
            "external-frontend-pomodoro-app",
            "external-backend-pomodoro-app",
        ]
        assert body["session"]["activeFrontendTargetId"] == "external-frontend-pomodoro-app"
        assert body["session"]["activeBackendTargetId"] == "external-backend-pomodoro-app"
    finally:
        app.dependency_overrides.clear()


def test_project_provisioning_apply_repairs_agenthub_scaffold_missing_backend_target(
    tmp_path: Path,
) -> None:
    client = TestClient(_app_with_memory_db(tmp_path / "worktrees"))
    try:
        workspace = client.get("/workspaces/demo").json()
        session = client.post(
            f"/workspaces/{workspace['id']}/sessions",
            json={"title": "Repair provisioning session"},
        ).json()
        selected_root = tmp_path / "pomodoro-app"
        (selected_root / "frontend" / "src").mkdir(parents=True)
        (selected_root / "frontend" / "src" / "App.tsx").write_text(
            "export default function App() { return null }\n"
        )
        (selected_root / "backend" / "app").mkdir(parents=True)
        (selected_root / "backend" / "app" / "main.py").write_text(
            "from fastapi import FastAPI\n"
        )
        (selected_root / "backend" / "tests").mkdir(parents=True)
        (selected_root / "backend" / "requirements.txt").write_text("fastapi\n")
        (selected_root / "docs").mkdir()
        (selected_root / "docs" / "api-contract.md").write_text("# API Contract\n")
        (selected_root / "README.md").write_text("# pomodoro-app\n")
        (selected_root / "agenthub.project.json").write_text(
            '{"schemaVersion":"agenthub.project.v1","projectSlug":"pomodoro-app"}\n'
        )
        frontend_response = client.post(
            f"/workspaces/{workspace['id']}/external-targets",
            json={
                "targetId": "external-frontend-pomodoro-app",
                "name": "Pomodoro App Frontend",
                "rootPath": str(selected_root / "frontend"),
                "projectType": "vite-react",
                "allowedPaths": ["src"],
            },
        )
        assert frontend_response.status_code == 201

        response = client.post(
            f"/workspaces/{workspace['id']}/project-provisioning/apply",
            json={
                "userRequest": "新建全栈项目",
                "selectedRootPath": str(selected_root),
                "sessionId": session["id"],
                "preferredSlug": "pomodoro-app",
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert [target["targetId"] for target in body["registeredTargets"]] == [
            "external-frontend-pomodoro-app",
            "external-backend-pomodoro-app",
        ]
        assert body["session"]["activeFrontendTargetId"] == "external-frontend-pomodoro-app"
        assert body["session"]["activeBackendTargetId"] == "external-backend-pomodoro-app"
        targets = client.get(f"/workspaces/{workspace['id']}/external-targets").json()
        assert [target["targetId"] for target in targets] == [
            "external-frontend-pomodoro-app",
            "external-backend-pomodoro-app",
        ]
    finally:
        app.dependency_overrides.clear()


def test_project_provisioning_apply_rejects_non_empty_folder(tmp_path: Path) -> None:
    client = TestClient(_app_with_memory_db(tmp_path / "worktrees"))
    try:
        workspace = client.get("/workspaces/demo").json()
        session = client.post(
            f"/workspaces/{workspace['id']}/sessions",
            json={"title": "Rejected provisioning session"},
        ).json()
        selected_root = tmp_path / "non-empty-project"
        selected_root.mkdir()
        (selected_root / "existing.txt").write_text("do not overwrite\n")

        response = client.post(
            f"/workspaces/{workspace['id']}/project-provisioning/apply",
            json={
                "userRequest": "Build a simple fullstack task tracker",
                "selectedRootPath": str(selected_root),
                "sessionId": session["id"],
                "preferredSlug": "task-tracker",
            },
        )

        assert response.status_code == 400
        assert "empty directory" in response.json()["detail"]
        assert not (selected_root / "frontend").exists()
        targets = client.get(f"/workspaces/{workspace['id']}/external-targets").json()
        assert targets == []
        updated_session = client.get(f"/sessions/{session['id']}").json()
        assert updated_session["activeFrontendTargetId"] is None
        assert updated_session["activeBackendTargetId"] is None
    finally:
        app.dependency_overrides.clear()


def test_project_provisioning_apply_rejects_target_id_conflict_before_writing(
    tmp_path: Path,
) -> None:
    client = TestClient(_app_with_memory_db(tmp_path / "worktrees"))
    try:
        workspace = client.get("/workspaces/demo").json()
        session = client.post(
            f"/workspaces/{workspace['id']}/sessions",
            json={"title": "Conflict provisioning session"},
        ).json()
        existing_target_root = tmp_path / "existing-frontend"
        existing_target_root.mkdir()
        conflict_response = client.post(
            f"/workspaces/{workspace['id']}/external-targets",
            json={
                "targetId": "external-frontend-conflict-app",
                "name": "Existing frontend",
                "rootPath": str(existing_target_root),
                "projectType": "vite-react",
                "allowedPaths": ["src"],
            },
        )
        assert conflict_response.status_code == 201

        selected_root = tmp_path / "selected-empty-project"
        selected_root.mkdir()
        response = client.post(
            f"/workspaces/{workspace['id']}/project-provisioning/apply",
            json={
                "userRequest": "Build a simple fullstack app",
                "selectedRootPath": str(selected_root),
                "sessionId": session["id"],
                "preferredSlug": "conflict-app",
            },
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]
        assert list(selected_root.iterdir()) == []
        targets = client.get(f"/workspaces/{workspace['id']}/external-targets").json()
        assert [target["targetId"] for target in targets] == [
            "external-frontend-conflict-app",
        ]
    finally:
        app.dependency_overrides.clear()


def test_new_fullstack_request_plans_frontend_and_backend_boundaries() -> None:
    plan = plan_project_provisioning(
        user_request="帮我做一个健康管理系统，有登录、健康登记，需要有前后端，数据库任意",
        preferred_slug="health-management",
    )

    assert plan.project_kind == "new_project"
    assert plan.project_slug == "health-management"
    assert Path(plan.project_root) == (
        Path.home() / "Desktop" / "agenthub-rehearsals" / "health-management"
    )
    assert plan.requires_frontend is True
    assert plan.requires_backend is True
    assert plan.default_frontend_stack == "vite-react"
    assert plan.default_backend_stack == "fastapi"
    assert [draft.role for draft in plan.target_drafts] == ["frontend", "backend"]
    assert plan.target_drafts[0].target_id == "external-frontend-health-management"
    assert plan.target_drafts[0].project_profile.profile_id == "vite-react"
    assert plan.target_drafts[1].target_id == "external-backend-health-management"
    assert plan.target_drafts[1].project_profile.profile_id == "fastapi-python"
    assert "pnpm build" in plan.safe_default_commands
    assert "pytest" in plan.safe_default_commands
    assert "pnpm install" in plan.approval_required_commands
    assert "pip install -r requirements.txt" in plan.approval_required_commands


def test_existing_project_root_keeps_existing_project_kind(tmp_path: Path) -> None:
    existing = tmp_path / "already-here"
    existing.mkdir()

    plan = plan_project_provisioning(
        user_request="帮我改一下当前前端项目",
        existing_project_root=str(existing),
        preferred_slug="existing-app",
    )

    assert plan.project_kind == "existing_project"
    assert plan.project_root == str(existing.resolve())
    assert plan.requires_frontend is True
    assert plan.requires_backend is False
    assert len(plan.target_drafts) == 1
    assert plan.target_drafts[0].role == "frontend"


def _app_with_memory_db(worktrees_root: Path | None = None):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        db.add(
            Workspace(
                name="AgentHub Demo",
                repo_url="local://apps/demo",
                root_path="apps/demo",
                default_branch="main",
            )
        )
        db.commit()

    def override_db() -> Iterator[DbSession]:
        with DbSession(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    if worktrees_root is not None:
        app.dependency_overrides[get_worktree_service] = lambda: FakeWorktreeService(
            worktrees_root
        )
    return app
