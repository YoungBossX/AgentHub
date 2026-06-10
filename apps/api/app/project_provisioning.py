from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.external_workspaces import (
    DEFAULT_EXTERNAL_DENIED_PATHS,
    ExternalWorkspaceRegistration,
    ExternalWorkspaceRegistrationError,
    register_external_project_target,
)
from app.models import ExternalProjectTarget, Session, Workspace, utc_now
from app.project_profiles import ProjectProfile, build_project_profile


DEFAULT_REHEARSAL_ROOT = Path.home() / "Desktop" / "agenthub-rehearsals"
DEFAULT_FRONTEND_STACK = "vite-react"
DEFAULT_BACKEND_STACK = "fastapi"

ProjectKind = Literal["existing_project", "new_project"]
ProjectRole = Literal["frontend", "backend"]


@dataclass(frozen=True)
class ProvisionedTargetDraft:
    target_id: str
    role: ProjectRole
    root_path: str
    project_type: str
    allowed_paths: tuple[str, ...]
    denied_paths: tuple[str, ...]
    dev_command: str | None
    test_command: str | None
    check_command: str | None
    build_command: str | None
    preview_command: str | None
    package_manager: str
    detected_framework: str
    project_profile: ProjectProfile

    def summary(self) -> dict[str, object]:
        return {
            "targetId": self.target_id,
            "role": self.role,
            "rootPath": self.root_path,
            "projectType": self.project_type,
            "allowedPaths": list(self.allowed_paths),
            "deniedPaths": list(self.denied_paths),
            "devCommand": self.dev_command,
            "testCommand": self.test_command,
            "checkCommand": self.check_command,
            "buildCommand": self.build_command,
            "previewCommand": self.preview_command,
            "packageManager": self.package_manager,
            "detectedFramework": self.detected_framework,
            "projectProfile": self.project_profile.summary(),
        }


@dataclass(frozen=True)
class ProjectSetupStep:
    role: ProjectRole
    command: str
    cwd: str
    reason: str
    requires_approval: bool = True

    def summary(self) -> dict[str, object]:
        return {
            "role": self.role,
            "command": self.command,
            "cwd": self.cwd,
            "reason": self.reason,
            "requiresApproval": self.requires_approval,
        }


@dataclass(frozen=True)
class ProjectProvisioningPlan:
    project_kind: ProjectKind
    project_slug: str
    project_root: str
    requires_frontend: bool
    requires_backend: bool
    default_frontend_stack: str | None
    default_backend_stack: str | None
    target_drafts: tuple[ProvisionedTargetDraft, ...]
    approval_required_commands: tuple[str, ...]
    setup_steps: tuple[ProjectSetupStep, ...]
    safe_default_commands: tuple[str, ...]
    notes: tuple[str, ...]

    def summary(self) -> dict[str, object]:
        return {
            "projectKind": self.project_kind,
            "projectSlug": self.project_slug,
            "projectRoot": self.project_root,
            "requiresFrontend": self.requires_frontend,
            "requiresBackend": self.requires_backend,
            "defaultFrontendStack": self.default_frontend_stack,
            "defaultBackendStack": self.default_backend_stack,
            "targetDrafts": [draft.summary() for draft in self.target_drafts],
            "approvalRequiredCommands": list(self.approval_required_commands),
            "setupSteps": [step.summary() for step in self.setup_steps],
            "safeDefaultCommands": list(self.safe_default_commands),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class ProjectProvisioningApplyResult:
    plan: ProjectProvisioningPlan
    registered_targets: tuple[ExternalProjectTarget, ...]
    session: Session


class ProjectProvisioningApplyError(ValueError):
    pass


def plan_project_provisioning(
    *,
    user_request: str,
    existing_project_root: str | None = None,
    preferred_slug: str | None = None,
) -> ProjectProvisioningPlan:
    requires_backend = _requires_backend(user_request)
    requires_frontend = _requires_frontend(user_request) or not requires_backend
    slug = _project_slug(preferred_slug or user_request)
    project_kind: ProjectKind = "existing_project" if existing_project_root else "new_project"
    project_root = (
        str(Path(existing_project_root).expanduser().resolve(strict=False))
        if existing_project_root
        else str(DEFAULT_REHEARSAL_ROOT / slug)
    )

    target_drafts: list[ProvisionedTargetDraft] = []
    safe_commands: list[str] = []
    approval_commands: list[str] = []
    setup_steps: list[ProjectSetupStep] = []

    if requires_frontend:
        frontend = _frontend_target_draft(project_root, slug)
        target_drafts.append(frontend)
        safe_commands.extend(_configured_commands(frontend))
        approval_commands.extend(("pnpm install", "npm install"))
        setup_steps.append(
            ProjectSetupStep(
                role="frontend",
                command="pnpm install",
                cwd=frontend.root_path,
                reason="Install frontend dependencies before check, test, build, or preview.",
            )
        )

    if requires_backend:
        backend = _backend_target_draft(project_root, slug)
        target_drafts.append(backend)
        safe_commands.extend(_configured_commands(backend))
        approval_commands.extend(
            ("pip install -r requirements.txt", "uv pip install -r requirements.txt")
        )
        setup_steps.append(
            ProjectSetupStep(
                role="backend",
                command="pip install -r requirements.txt",
                cwd=backend.root_path,
                reason="Install backend dependencies before running API checks or tests.",
            )
        )

    notes = (
        "新项目请求会先形成项目边界和 provisional target，再进入 PlanValidator。",
        "默认技术栈只用于用户未指定技术栈的场景。",
        "依赖安装、网络访问和数据库迁移仍需审批；build/test/dev 仅来自 ProjectProfile。",
    )
    return ProjectProvisioningPlan(
        project_kind=project_kind,
        project_slug=slug,
        project_root=project_root,
        requires_frontend=requires_frontend,
        requires_backend=requires_backend,
        default_frontend_stack=DEFAULT_FRONTEND_STACK if requires_frontend else None,
        default_backend_stack=DEFAULT_BACKEND_STACK if requires_backend else None,
        target_drafts=tuple(target_drafts),
        approval_required_commands=tuple(dict.fromkeys(approval_commands)),
        setup_steps=tuple(setup_steps),
        safe_default_commands=tuple(dict.fromkeys(safe_commands)),
        notes=notes,
    )


def apply_project_provisioning(
    db: DbSession,
    *,
    workspace: Workspace,
    session: Session,
    user_request: str,
    selected_root_path: str,
    preferred_slug: str | None = None,
) -> ProjectProvisioningApplyResult:
    if session.workspace_id != workspace.id:
        raise ProjectProvisioningApplyError("Session does not belong to workspace")

    project_root, existing_scaffold = _validate_selected_root_for_apply(
        selected_root_path
    )
    plan = plan_project_provisioning(
        user_request=user_request,
        existing_project_root=str(project_root),
        preferred_slug=preferred_slug,
    )
    _ensure_target_ids_available(db, plan)
    if not existing_scaffold:
        _write_project_skeleton(project_root, plan)

    registered_targets: list[ExternalProjectTarget] = []
    try:
        for draft in plan.target_drafts:
            existing_target = _matching_existing_target(db, workspace, draft)
            target = existing_target or register_external_project_target(
                db,
                workspace,
                ExternalWorkspaceRegistration(
                    target_id=draft.target_id,
                    name=_target_name(plan.project_slug, draft.role),
                    root_path=draft.root_path,
                    project_type=draft.project_type,
                    allowed_paths=list(draft.allowed_paths),
                    denied_paths=list(draft.denied_paths),
                    dev_command=draft.dev_command,
                    test_command=draft.test_command,
                    check_command=draft.check_command,
                    build_command=draft.build_command,
                    preview_command=draft.preview_command,
                    package_manager=draft.package_manager,
                    detected_framework=draft.detected_framework,
                ),
            )
            registered_targets.append(target)
    except ExternalWorkspaceRegistrationError as exc:
        raise ProjectProvisioningApplyError(str(exc)) from exc

    frontend_target = next(
        (target for target in registered_targets if "-frontend-" in target.target_id),
        None,
    )
    backend_target = next(
        (target for target in registered_targets if "-backend-" in target.target_id),
        None,
    )
    if frontend_target is not None:
        session.active_frontend_target_id = frontend_target.target_id
    if backend_target is not None:
        session.active_backend_target_id = backend_target.target_id
    session.updated_at = utc_now()
    db.add(session)
    db.commit()
    db.refresh(session)

    return ProjectProvisioningApplyResult(
        plan=plan,
        registered_targets=tuple(registered_targets),
        session=session,
    )


def _frontend_target_draft(project_root: str, slug: str) -> ProvisionedTargetDraft:
    root = str(Path(project_root) / "frontend")
    commands = {
        "dev": "pnpm dev --host 127.0.0.1 --port <port>",
        "test": "pnpm test",
        "check": "pnpm check",
        "build": "pnpm build",
        "preview": "pnpm dev --host 127.0.0.1 --port <port>",
    }
    allowed_paths = (
        "src",
        "public",
        "index.html",
        "package.json",
        "pnpm-lock.yaml",
        "tsconfig.json",
        "tsconfig.app.json",
        "tsconfig.node.json",
        "vite.config.ts",
    )
    profile = build_project_profile(
        project_type="vite-react",
        detected_framework="vite-react",
        package_manager="pnpm",
        allowed_paths=allowed_paths,
        denied_paths=DEFAULT_EXTERNAL_DENIED_PATHS,
        dev_command=commands["dev"],
        test_command=commands["test"],
        check_command=commands["check"],
        build_command=commands["build"],
        preview_command=commands["preview"],
        analysis_status="planned",
        analysis_warnings=(),
        confidence="high",
    )
    return ProvisionedTargetDraft(
        target_id=f"external-frontend-{slug}",
        role="frontend",
        root_path=root,
        project_type="vite-react",
        allowed_paths=allowed_paths,
        denied_paths=DEFAULT_EXTERNAL_DENIED_PATHS,
        dev_command=commands["dev"],
        test_command=commands["test"],
        check_command=commands["check"],
        build_command=commands["build"],
        preview_command=commands["preview"],
        package_manager="pnpm",
        detected_framework="vite-react",
        project_profile=profile,
    )


def _backend_target_draft(project_root: str, slug: str) -> ProvisionedTargetDraft:
    root = str(Path(project_root) / "backend")
    commands = {
        "dev": "uvicorn app.main:app --reload --host 127.0.0.1 --port <port>",
        "test": "pytest",
        "check": "python -m compileall .",
    }
    allowed_paths = ("app", "tests", "pyproject.toml", "requirements.txt")
    profile = build_project_profile(
        project_type="fastapi",
        detected_framework="fastapi",
        package_manager="pip",
        allowed_paths=allowed_paths,
        denied_paths=DEFAULT_EXTERNAL_DENIED_PATHS,
        dev_command=commands["dev"],
        test_command=commands["test"],
        check_command=commands["check"],
        build_command=None,
        preview_command=None,
        analysis_status="planned",
        analysis_warnings=(),
        confidence="high",
    )
    return ProvisionedTargetDraft(
        target_id=f"external-backend-{slug}",
        role="backend",
        root_path=root,
        project_type="fastapi",
        allowed_paths=allowed_paths,
        denied_paths=DEFAULT_EXTERNAL_DENIED_PATHS,
        dev_command=commands["dev"],
        test_command=commands["test"],
        check_command=commands["check"],
        build_command=None,
        preview_command=None,
        package_manager="pip",
        detected_framework="fastapi",
        project_profile=profile,
    )


def _configured_commands(target: ProvisionedTargetDraft) -> tuple[str, ...]:
    return tuple(
        command
        for command in (
            target.check_command,
            target.test_command,
            target.build_command,
            target.dev_command,
        )
        if command
    )


def _requires_backend(request: str) -> bool:
    normalized = request.lower()
    return any(
        term in normalized
        for term in (
            "后端",
            "backend",
            "api",
            "数据库",
            "database",
            "前后端",
            "前后端分离",
            "全栈",
            "fullstack",
            "full-stack",
            "full stack",
        )
    )


def _requires_frontend(request: str) -> bool:
    normalized = request.lower()
    return any(
        term in normalized
        for term in (
            "前端",
            "frontend",
            "页面",
            "登录",
            "界面",
            "app",
            "应用",
            "系统",
            "前后端",
            "全栈",
            "fullstack",
            "full-stack",
            "full stack",
        )
    )


def _project_slug(value: str) -> str:
    explicit_ascii = re.findall(r"[a-zA-Z0-9]+", value.lower())
    if explicit_ascii:
        slug = "-".join(explicit_ascii[:4])
    elif "健康" in value:
        slug = "health-management-app"
    elif "记账" in value:
        slug = "bookkeeping-app"
    elif "图书" in value or "书" in value:
        slug = "library-management-app"
    else:
        slug = "agenthub-generated-app"
    slug = re.sub(r"[^a-z0-9-]+", "-", slug).strip("-")
    return slug[:48] or "agenthub-generated-app"


def _validate_selected_root_for_apply(selected_root_path: str) -> tuple[Path, bool]:
    if not selected_root_path.strip():
        raise ProjectProvisioningApplyError("Selected root path is required")
    root = Path(selected_root_path).expanduser().resolve(strict=False)
    if not root.exists() or not root.is_dir():
        raise ProjectProvisioningApplyError(
            f"Selected project root must be an existing empty directory: {root}"
        )
    existing_entries = sorted(path.name for path in root.iterdir())
    if existing_entries and _is_repairable_agenthub_scaffold(root):
        return root, True
    if existing_entries:
        preview = ", ".join(existing_entries[:5])
        raise ProjectProvisioningApplyError(
            f"Selected project root must be an empty directory; found: {preview}"
        )
    return root, False


def _ensure_target_ids_available(
    db: DbSession,
    plan: ProjectProvisioningPlan,
) -> None:
    target_ids = [draft.target_id for draft in plan.target_drafts]
    if len(target_ids) != len(set(target_ids)):
        raise ProjectProvisioningApplyError("Provisioned target IDs must be unique")

    for target_id in target_ids:
        existing = db.exec(
            select(ExternalProjectTarget).where(
                ExternalProjectTarget.target_id == target_id,
            )
        ).first()
        draft = next(
            (item for item in plan.target_drafts if item.target_id == target_id),
            None,
        )
        if existing is not None and (
            draft is None or not _target_matches_draft(existing, draft)
        ):
            raise ProjectProvisioningApplyError(
                f"External target already exists: {target_id}"
            )


def _matching_existing_target(
    db: DbSession,
    workspace: Workspace,
    draft: ProvisionedTargetDraft,
) -> ExternalProjectTarget | None:
    existing = db.exec(
        select(ExternalProjectTarget).where(
            ExternalProjectTarget.target_id == draft.target_id,
        )
    ).first()
    if existing is None:
        return None
    if existing.workspace_id != workspace.id or not _target_matches_draft(existing, draft):
        raise ExternalWorkspaceRegistrationError(
            f"External target already exists: {draft.target_id}"
        )
    return existing


def _target_matches_draft(
    target: ExternalProjectTarget,
    draft: ProvisionedTargetDraft,
) -> bool:
    return (
        Path(target.root_path).expanduser().resolve(strict=False)
        == Path(draft.root_path).expanduser().resolve(strict=False)
        and target.project_type == draft.project_type
    )


def _is_repairable_agenthub_scaffold(root: Path) -> bool:
    allowed_top_level = {
        "README.md",
        "agenthub.project.json",
        "backend",
        "docs",
        "frontend",
    }
    entries = {path.name for path in root.iterdir()}
    if not entries.issubset(allowed_top_level):
        return False
    return all(
        path.exists()
        for path in (
            root / "agenthub.project.json",
            root / "README.md",
            root / "frontend",
            root / "backend",
            root / "docs",
            root / "frontend" / "src",
            root / "backend" / "app",
            root / "backend" / "requirements.txt",
            root / "docs" / "api-contract.md",
        )
    )


def _write_project_skeleton(project_root: Path, plan: ProjectProvisioningPlan) -> None:
    (project_root / "frontend" / "src").mkdir(parents=True, exist_ok=False)
    (project_root / "frontend" / "public").mkdir(parents=True, exist_ok=False)
    (project_root / "backend" / "app").mkdir(parents=True, exist_ok=False)
    (project_root / "backend" / "tests").mkdir(parents=True, exist_ok=False)
    (project_root / "docs").mkdir(parents=True, exist_ok=False)

    _write_frontend_skeleton(project_root / "frontend", plan.project_slug)
    _write_backend_skeleton(project_root / "backend")
    (project_root / "docs" / "api-contract.md").write_text(
        _api_contract_md(),
        encoding="utf-8",
    )
    (project_root / "README.md").write_text(_readme_md(plan), encoding="utf-8")
    (project_root / "agenthub.project.json").write_text(
        json.dumps(_project_metadata(plan), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_frontend_skeleton(frontend_root: Path, slug: str) -> None:
    (frontend_root / "package.json").write_text(
        json.dumps(
            {
                "name": slug,
                "private": True,
                "version": "0.1.0",
                "type": "module",
                "scripts": {
                    "dev": "vite --host 127.0.0.1",
                    "build": "tsc -b && vite build",
                    "check": "tsc --noEmit",
                    "test": "vitest run",
                },
                "dependencies": {
                    "@vitejs/plugin-react": "latest",
                    "vite": "latest",
                    "typescript": "latest",
                    "react": "latest",
                    "react-dom": "latest",
                },
                "devDependencies": {
                    "vitest": "latest",
                    "@types/react": "latest",
                    "@types/react-dom": "latest",
                    "@types/node": "latest",
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (frontend_root / "index.html").write_text(
        '<!doctype html>\n<html lang="en">\n  <head>\n    <meta charset="UTF-8" />\n'
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
        "    <title>AgentHub Project</title>\n  </head>\n  <body>\n"
        '    <div id="root"></div>\n    <script type="module" src="/src/main.tsx"></script>\n'
        "  </body>\n</html>\n",
        encoding="utf-8",
    )
    (frontend_root / "src" / "main.tsx").write_text(
        "import React from 'react';\n"
        "import ReactDOM from 'react-dom/client';\n"
        "import App from './App';\n"
        "import './styles.css';\n\n"
        "ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(\n"
        "  <React.StrictMode>\n    <App />\n  </React.StrictMode>,\n);\n",
        encoding="utf-8",
    )
    (frontend_root / "src" / "App.tsx").write_text(
        "export default function App() {\n"
        "  return (\n"
        '    <main className="app-shell">\n'
        '      <h1>AgentHub Project</h1>\n'
        '      <p>Ready for frontend implementation.</p>\n'
        "    </main>\n"
        "  );\n"
        "}\n",
        encoding="utf-8",
    )
    (frontend_root / "src" / "styles.css").write_text(
        "body {\n"
        "  margin: 0;\n"
        "  font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "
        "'Segoe UI', sans-serif;\n"
        "  background: #f7f7f8;\n"
        "  color: #202124;\n"
        "}\n\n"
        ".app-shell {\n"
        "  min-height: 100vh;\n"
        "  display: grid;\n"
        "  place-content: center;\n"
        "  gap: 12px;\n"
        "  padding: 32px;\n"
        "  text-align: center;\n"
        "}\n",
        encoding="utf-8",
    )
    (frontend_root / "src" / "vite-env.d.ts").write_text(
        "/// <reference types=\"vite/client\" />\n",
        encoding="utf-8",
    )
    (frontend_root / "tsconfig.json").write_text(
        json.dumps(
            {
                "files": [],
                "references": [
                    {"path": "./tsconfig.app.json"},
                    {"path": "./tsconfig.node.json"},
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (frontend_root / "tsconfig.app.json").write_text(
        json.dumps(
            {
                "compilerOptions": {
                    "target": "ES2020",
                    "useDefineForClassFields": True,
                    "lib": ["ES2020", "DOM", "DOM.Iterable"],
                    "allowJs": False,
                    "skipLibCheck": True,
                    "esModuleInterop": True,
                    "allowSyntheticDefaultImports": True,
                    "strict": True,
                    "forceConsistentCasingInFileNames": True,
                    "module": "ESNext",
                    "moduleResolution": "Bundler",
                    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.app.tsbuildinfo",
                    "resolveJsonModule": True,
                    "isolatedModules": True,
                    "noEmit": True,
                    "jsx": "react-jsx",
                },
                "include": ["src"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (frontend_root / "tsconfig.node.json").write_text(
        json.dumps(
            {
                "compilerOptions": {
                    "composite": True,
                    "module": "ESNext",
                    "moduleResolution": "Bundler",
                    "lib": ["ESNext"],
                    "noEmit": True,
                    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.node.tsbuildinfo",
                    "types": ["node"],
                    "allowSyntheticDefaultImports": True,
                },
                "include": ["vite.config.ts"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (frontend_root / "vite.config.ts").write_text(
        "import { defineConfig } from 'vite';\nimport react from '@vitejs/plugin-react';\n\n"
        "export default defineConfig({\n  plugins: [react()],\n});\n",
        encoding="utf-8",
    )


def _write_backend_skeleton(backend_root: Path) -> None:
    (backend_root / "app" / "__init__.py").write_text("", encoding="utf-8")
    (backend_root / "app" / "main.py").write_text(
        "from fastapi import FastAPI\n\n"
        "app = FastAPI(title=\"AgentHub Project API\")\n\n\n"
        "@app.get('/health')\n"
        "def health() -> dict[str, str]:\n"
        "    return {'status': 'ok'}\n",
        encoding="utf-8",
    )
    (backend_root / "requirements.txt").write_text(
        "fastapi\nuvicorn[standard]\npytest\n",
        encoding="utf-8",
    )
    (backend_root / "tests" / "test_health.py").write_text(
        "from fastapi.testclient import TestClient\n\n"
        "from app.main import app\n\n\n"
        "def test_health() -> None:\n"
        "    response = TestClient(app).get('/health')\n"
        "    assert response.status_code == 200\n"
        "    assert response.json() == {'status': 'ok'}\n",
        encoding="utf-8",
    )


def _api_contract_md() -> str:
    return "# API Contract\n\nThe backend starts with `GET /health` and returns `{ \"status\": \"ok\" }`.\n"


def _readme_md(plan: ProjectProvisioningPlan) -> str:
    return (
        f"# {plan.project_slug}\n\n"
        "This project was provisioned by AgentHub as a generic fullstack workspace.\n\n"
        "## Structure\n\n"
        "- `frontend/`: Vite React TypeScript application\n"
        "- `backend/`: FastAPI application\n"
        "- `docs/api-contract.md`: API boundary notes\n"
    )


def _project_metadata(plan: ProjectProvisioningPlan) -> dict[str, object]:
    return {
        "schemaVersion": "agenthub.project.v1",
        "projectSlug": plan.project_slug,
        "projectRoot": plan.project_root,
        "frontend": {
            "stack": plan.default_frontend_stack,
            "targetId": next(
                (
                    draft.target_id
                    for draft in plan.target_drafts
                    if draft.role == "frontend"
                ),
                None,
            ),
        },
        "backend": {
            "stack": plan.default_backend_stack,
            "targetId": next(
                (
                    draft.target_id
                    for draft in plan.target_drafts
                    if draft.role == "backend"
                ),
                None,
            ),
        },
        "notes": list(plan.notes),
    }


def _target_name(slug: str, role: ProjectRole) -> str:
    label = slug.replace("-", " ").title()
    return f"{label} {role.title()}"
