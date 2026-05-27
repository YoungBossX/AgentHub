import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

import pytest
from app.deployments import (
    CommandResult,
    DeployService,
    LocalStagingDeployProvider,
    MockDeployProvider,
    StagingServerProcess,
)
from app.diffs import collect_task_run_diff
from app.handoffs import create_handoff_artifact
from app.mission_trace import build_session_mission_trace
from app.models import Agent, Artifact, Session, Task, TaskRun, Workspace
from app.previews import PreviewProcess, PreviewService
from app.provider_assignments import PROVIDER_ASSIGNMENT_MATRIX_ENV
from app.reviews import create_scripted_review_for_task_run
from app.scheduler import evaluate_and_apply_scheduler_readiness
from app.target_registry import DEMO_BACKEND_TARGET_ID, DEMO_FRONTEND_TARGET_ID
from app.task_runs import create_task_run, transition_task_run


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


class RecordingPreviewRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], Path]] = []

    def start(self, command: list[str], cwd: Path) -> PreviewProcess:
        self.calls.append((command, cwd))
        return PreviewProcess(pid=6130)

    def stop(self, process_id: int) -> None:
        pass


class StaticHealthChecker:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def is_healthy(self, url: str) -> bool:
        self.urls.append(url)
        return True


class RecordingBuildRunner:
    def __init__(self) -> None:
        self.commands: list[tuple[str, Path]] = []

    def run(self, command: str, cwd: Path) -> CommandResult:
        self.commands.append((command, cwd))
        output = cwd / "dist"
        output.mkdir(parents=True, exist_ok=True)
        (output / "index.html").write_text("<h1>mixed provider staging</h1>\n")
        return CommandResult(exit_code=0, stdout="build ok", stderr="")


class RecordingStaticServer:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, int]] = []

    def start(self, output_dir: Path, port: int) -> StagingServerProcess:
        self.calls.append((output_dir, port))
        return StagingServerProcess(
            pid=6131,
            url=f"http://127.0.0.1:{port}",
            command=f"python -m http.server {port} --directory {output_dir}",
        )


def test_p13_mixed_provider_rehearsal_records_shared_contract_and_artifacts(
    db: DbSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        PROVIDER_ASSIGNMENT_MATRIX_ENV,
        json.dumps(
            {
                "roles": {
                    "backend": {
                        "adapterType": "codex",
                        "providerId": "local-codex-cli",
                    },
                    "frontend": {
                        "adapterType": "claude_code",
                        "providerId": "local-claude-code-cli",
                    },
                    "review": {
                        "adapterType": "scripted_mock",
                        "providerId": "local-scripted-review",
                    },
                }
            },
            separators=(",", ":"),
        ),
    )
    worktree = _init_demo_worktree(tmp_path / "mixed-provider-worktree")
    workspace, session, backend_task, frontend_task = _seed_mixed_provider_graph(
        db,
        worktree,
    )

    backend_run = create_task_run(db, backend_task.id)
    _write_backend_contacts_api(worktree)
    transition_task_run(db, backend_run.id, "completed")
    backend_diff = collect_task_run_diff(db, backend_run.id)
    backend_review = create_scripted_review_for_task_run(db, backend_run.id)
    handoff = create_handoff_artifact(
        db,
        from_task=backend_task,
        from_task_run=backend_run,
        to_task=frontend_task,
    )
    _commit_worktree(worktree, "backend implementation")

    decision = evaluate_and_apply_scheduler_readiness(db, frontend_task)
    frontend_run = create_task_run(db, frontend_task.id)
    _write_frontend_contacts_ui(worktree)
    transition_task_run(db, frontend_run.id, "completed")
    frontend_diff = collect_task_run_diff(db, frontend_run.id)
    frontend_review = create_scripted_review_for_task_run(db, frontend_run.id)

    preview_runner = RecordingPreviewRunner()
    preview_service = PreviewService(
        process_runner=preview_runner,
        health_checker=StaticHealthChecker(),
        port_allocator=lambda: 46130,
        health_attempts=1,
    )
    preview = preview_service.start_task_run_preview(db, frontend_run.id)

    build_runner = RecordingBuildRunner()
    static_server = RecordingStaticServer()
    deploy_service = DeployService(
        providers=(
            MockDeployProvider(),
            LocalStagingDeployProvider(
                command_runner=build_runner,
                static_server=static_server,
                health_checker=StaticHealthChecker(),
                port_allocator=lambda: 46131,
                health_attempts=1,
            ),
        )
    )
    deployment = deploy_service.create_deployment(
        db,
        preview.id,
        provider_id="local_staging",
    )
    mission_trace = build_session_mission_trace(db, session.id)

    backend_metrics = json.loads(backend_run.metrics_json)
    frontend_metrics = json.loads(frontend_run.metrics_json)
    handoff_meta = json.loads(handoff.meta_json)
    frontend_diff_artifact = db.get(Artifact, frontend_diff.artifact_id)
    deployment_artifact = db.get(Artifact, deployment.artifact_id)
    assert frontend_diff_artifact is not None
    assert deployment_artifact is not None
    diff_meta = json.loads(frontend_diff_artifact.meta_json)
    deploy_meta = json.loads(deployment_artifact.meta_json)

    assert workspace.id == session.workspace_id
    assert backend_metrics["providerAssignment"]["adapterType"] == "codex"
    assert frontend_metrics["providerAssignment"]["adapterType"] == "claude_code"
    assert decision.runnable is True
    assert frontend_task.id in [item.id for item in db.exec(select(Task)).all()]
    assert backend_task.id in json.loads(frontend_task.depends_on_task_ids)
    assert backend_diff.changed_files == ["apps/demo-api/app/main.py"]
    assert backend_review.artifact_type == "review"
    assert handoff_meta["fromProviderId"] == "local-codex-cli"
    assert handoff_meta["toProviderId"] == "local-claude-code-cli"
    assert {
        "artifactId": backend_diff.artifact_id,
        "artifactType": "diff",
        "status": "ready",
    } in handoff_meta["artifactRefs"]
    assert "apps/demo/src/App.tsx" in frontend_diff.changed_files
    assert frontend_review.artifact_type == "review"
    assert diff_meta["providerEvidence"]["adapterType"] == "claude_code"
    assert preview.health_status == "healthy"
    assert preview.url == "http://127.0.0.1:46130"
    assert deployment.provider == "local_staging"
    assert deployment.status == "ready"
    assert deploy_meta["providerEvidence"]["adapterType"] == "claude_code"
    assert deploy_meta["providerEvidence"]["artifactRefs"]["previewId"] == preview.id
    assert [call[1] for call in preview_runner.calls] == [worktree / "apps" / "demo"]
    assert build_runner.commands[0][1] == worktree / "apps" / "demo"
    assert static_server.calls[0][1] == 46131
    assert {run["adapterType"] for run in mission_trace.task_runs} == {
        "codex",
        "claude_code",
    }
    assert any(artifact["artifactType"] == "handoff" for artifact in mission_trace.artifacts)


def _seed_mixed_provider_graph(
    db: DbSession,
    worktree: Path,
) -> tuple[Workspace, Session, Task, Task]:
    workspace = Workspace(
        name="P13 Mixed Provider Workspace",
        repo_url="local://p13-rehearsal",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="P13 mixed-provider rehearsal",
        bound_branch="main",
        worktree_path=str(worktree),
    )
    backend = Agent(
        name="Backend Agent",
        role="backend",
        adapter_type="codex",
        provider="local",
    )
    frontend = Agent(
        name="Frontend Agent",
        role="frontend",
        adapter_type="codex",
        provider="local",
    )
    contract = {
        "contractId": "p13-mini-crm-contract",
        "appName": "Mini CRM",
        "appType": "mini_crm_contacts",
        "backendTargetId": DEMO_BACKEND_TARGET_ID,
        "frontendTargetId": DEMO_FRONTEND_TARGET_ID,
        "demoApiBaseUrl": "http://127.0.0.1:5174",
        "apiRoutes": [{"method": "GET", "path": "/contacts"}],
    }
    backend_task = Task(
        session_id=session.id,
        title="Backend Agent implements contacts API",
        intent_type="backend_change",
        status="pending",
        priority=1,
        assigned_agent_id=backend.id,
        plan_json=json.dumps(
            {
                "planner": "contract_first_v1",
                "targetId": DEMO_BACKEND_TARGET_ID,
                "safeTarget": "apps/demo-api",
                "files": ["apps/demo-api/app/main.py"],
                "contractId": contract["contractId"],
                "appContract": contract,
            },
            separators=(",", ":"),
        ),
    )
    frontend_task = Task(
        session_id=session.id,
        title="Frontend Agent implements contacts UI",
        intent_type="frontend_change",
        status="pending",
        priority=2,
        assigned_agent_id=frontend.id,
        plan_json=json.dumps(
            {
                "planner": "contract_first_v1",
                "targetId": DEMO_FRONTEND_TARGET_ID,
                "safeTarget": "apps/demo/src",
                "files": ["apps/demo/src/App.tsx"],
                "contractId": contract["contractId"],
                "appContract": contract,
            },
            separators=(",", ":"),
        ),
        depends_on_task_ids=json.dumps([backend_task.id], separators=(",", ":")),
    )
    db.add(workspace)
    db.add(session)
    db.add(backend)
    db.add(frontend)
    db.add(backend_task)
    db.add(frontend_task)
    db.commit()
    db.refresh(backend_task)
    db.refresh(frontend_task)
    return workspace, session, backend_task, frontend_task


def _init_demo_worktree(root: Path) -> Path:
    (root / "apps" / "demo" / "src").mkdir(parents=True)
    (root / "apps" / "demo-api" / "app").mkdir(parents=True)
    (root / "apps" / "demo" / "src" / "App.tsx").write_text(
        "export default function App() { return <main>Demo</main>; }\n"
    )
    (root / "apps" / "demo-api" / "app" / "main.py").write_text(
        "from fastapi import FastAPI\n\napp = FastAPI()\n"
    )
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "AgentHub Test"], cwd=root, check=True)
    _commit_worktree(root, "baseline")
    return root


def _commit_worktree(root: Path, message: str) -> None:
    subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=root, check=True, capture_output=True)


def _write_backend_contacts_api(root: Path) -> None:
    (root / "apps" / "demo-api" / "app" / "main.py").write_text(
        "\n".join(
            [
                "from fastapi import FastAPI",
                "",
                "app = FastAPI()",
                "",
                "CONTACTS = [{'id': '1', 'name': 'Ada Lovelace', 'note': 'VIP lead'}]",
                "",
                "@app.get('/contacts')",
                "def list_contacts():",
                "    return CONTACTS",
                "",
            ]
        )
    )


def _write_frontend_contacts_ui(root: Path) -> None:
    (root / "apps" / "demo" / "src" / "App.tsx").write_text(
        "\n".join(
            [
                "const API_BASE = 'http://127.0.0.1:5174';",
                "",
                "export default function App() {",
                "  return (",
                "    <main>",
                "      <h1>Mini CRM</h1>",
                "      <p>Contacts load from {API_BASE}/contacts.</p>",
                "    </main>",
                "  );",
                "}",
                "",
            ]
        )
    )
