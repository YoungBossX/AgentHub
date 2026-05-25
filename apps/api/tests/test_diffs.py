import json
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.artifact_versions import record_artifact_version
from app.diffs import (
    _head_ref,
    _parse_numstat_value,
    capture_base_ref_for_worktree,
    collect_task_run_diff,
    git_diff_pathspec,
)
from app.external_workspaces import (
    ExternalWorkspaceRegistration,
    register_external_project_target,
)
from app.main import app, get_db
from app.models import (
    Agent,
    Artifact,
    ArtifactVersion,
    Diff,
    Review,
    Session,
    Task,
    TaskRun,
    TaskRunEvent,
    Workspace,
)
from app.task_runs import create_task_run


REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def demo_worktree(tmp_path: Path) -> Path:
    worktree = tmp_path / "session-worktree"
    demo_root = worktree / "apps" / "demo"
    shutil.copytree(REPO_ROOT / "apps" / "demo", demo_root, ignore=shutil.ignore_patterns("node_modules"))
    subprocess.run(["git", "init"], cwd=worktree, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=worktree, check=True)
    subprocess.run(["git", "config", "user.name", "AgentHub Test"], cwd=worktree, check=True)
    subprocess.run(["git", "add", "apps/demo"], cwd=worktree, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=worktree, check=True, capture_output=True)
    return worktree


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


@pytest.fixture
def client(db: DbSession) -> Iterator[TestClient]:
    def override_db() -> Iterator[DbSession]:
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def create_run_fixture(db: DbSession, worktree_path: Path) -> str:
    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="Diff session",
        bound_branch="main",
        worktree_path=str(worktree_path),
    )
    agent = Agent(
        name="Frontend Agent",
        role="frontend",
        adapter_type="scripted_mock",
        provider="local",
    )
    task = Task(
        session_id=session.id,
        title="Build login page",
        intent_type="frontend_change",
        assigned_agent_id=agent.id,
    )
    db.add(workspace)
    db.add(session)
    db.add(agent)
    db.add(task)
    db.commit()

    task_run = create_task_run(db, task.id, adapter_type="scripted_mock")
    assert task_run.base_ref is not None
    return task_run.id


def mutate_worktree(worktree_path: Path) -> None:
    app_source = worktree_path / "apps/demo/src/App.tsx"
    app_source.write_text(
        app_source.read_text().replace(
            "Launchpad for a visible coding-agent change",
            "AgentHub Login Demo",
        ),
    )
    node_modules_file = worktree_path / "apps/demo/node_modules/transient-cache.txt"
    node_modules_file.parent.mkdir(parents=True, exist_ok=True)
    node_modules_file.write_text("this must not appear in stored diffs\n")


def expected_git_patch(worktree_path: Path, base_ref: str) -> str:
    return subprocess.run(
        ["git", "diff", "-p", base_ref, "--", *git_diff_pathspec()],
        cwd=worktree_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def test_collect_task_run_diff_stores_git_patch_and_excludes_node_modules(
    db: DbSession,
    demo_worktree: Path,
) -> None:
    task_run_id = create_run_fixture(db, demo_worktree)
    task_run = db.get(TaskRun, task_run_id)
    assert task_run is not None
    base_ref = task_run.base_ref
    assert base_ref is not None
    mutate_worktree(demo_worktree)

    diff_artifact = collect_task_run_diff(db, task_run_id)

    stored_run = db.get(TaskRun, task_run_id)
    artifact = db.get(Artifact, diff_artifact.artifact_id)
    stored_diff = db.get(Diff, diff_artifact.id)
    event = db.exec(
        select(TaskRunEvent).where(
            TaskRunEvent.task_run_id == task_run_id,
            TaskRunEvent.event_type == "artifact.diff.ready",
        )
    ).one()

    assert artifact is not None
    assert stored_diff is not None
    assert stored_run is not None
    assert artifact.artifact_type == "diff"
    assert artifact.status == "ready"
    assert stored_diff.base_ref == base_ref
    assert stored_diff.head_ref == stored_run.head_ref
    assert stored_diff.patch_text == expected_git_patch(demo_worktree, base_ref)
    assert "AgentHub Login Demo" in stored_diff.patch_text
    assert "node_modules" not in stored_diff.patch_text
    assert json.loads(stored_diff.changed_files_json) == ["apps/demo/src/App.tsx"]
    assert json.loads(stored_diff.stats_json)["filesChanged"] == 1
    assert json.loads(event.payload_json)["artifactId"] == artifact.id

    version = db.exec(
        select(ArtifactVersion).where(ArtifactVersion.artifact_id == artifact.id)
    ).one()
    assert version.version == 1
    assert version.source_task_run_id == task_run_id
    assert version.git_base_ref == base_ref
    assert version.git_head_ref == stored_run.head_ref
    assert json.loads(version.changed_files_json) == ["apps/demo/src/App.tsx"]
    assert "Diff captured 1 changed file" in version.summary


def test_external_task_run_diff_uses_allowed_paths_and_excludes_denied(
    db: DbSession,
    tmp_path: Path,
) -> None:
    external_root = tmp_path / "external-app"
    (external_root / "src").mkdir(parents=True)
    (external_root / "src" / "App.tsx").write_text("export default 'before'\n")
    subprocess.run(["git", "init"], cwd=external_root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=external_root, check=True)
    subprocess.run(["git", "config", "user.name", "AgentHub Test"], cwd=external_root, check=True)
    subprocess.run(["git", "add", "."], cwd=external_root, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=external_root, check=True, capture_output=True)

    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="External diff session",
        bound_branch="main",
        worktree_path=".worktrees/external-diff-session",
    )
    agent = Agent(name="Frontend Agent", role="frontend", adapter_type="codex", provider="local")
    db.add(workspace)
    db.add(session)
    db.add(agent)
    db.commit()
    db.refresh(workspace)
    register_external_project_target(
        db,
        workspace,
        ExternalWorkspaceRegistration(
            target_id="external-diff-app",
            name="External Diff App",
            root_path=str(external_root),
            project_type="vite-react",
            allowed_paths=["src"],
        ),
    )
    task = Task(
        session_id=session.id,
        title="External frontend change",
        intent_type="frontend_change",
        assigned_agent_id=agent.id,
        plan_json=json.dumps(
            {
                "targetId": "external-diff-app",
                "safeTarget": "src",
                "files": ["src/App.tsx"],
            },
            separators=(",", ":"),
        ),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    task_run = create_task_run(db, task.id)
    (external_root / "src" / "App.tsx").write_text("export default 'after'\n")
    (external_root / ".env").write_text("SECRET=hidden\n")

    diff_artifact = collect_task_run_diff(db, task_run.id)

    assert task_run.worktree_path == str(external_root.resolve())
    assert diff_artifact.changed_files == ["src/App.tsx"]
    assert ".env" not in diff_artifact.patch_text
    assert "export default 'after'" in diff_artifact.patch_text


def test_diff_api_returns_stored_diff_artifacts(
    client: TestClient,
    db: DbSession,
    demo_worktree: Path,
) -> None:
    task_run_id = create_run_fixture(db, demo_worktree)
    mutate_worktree(demo_worktree)

    create_response = client.post(f"/task-runs/{task_run_id}/diff")
    list_response = client.get(f"/task-runs/{task_run_id}/diffs")
    reviews_response = client.get(f"/task-runs/{task_run_id}/reviews")
    manual_review_response = client.post(f"/task-runs/{task_run_id}/review")

    assert create_response.status_code == 201
    assert list_response.status_code == 200
    assert reviews_response.status_code == 200
    assert manual_review_response.status_code == 201
    created = create_response.json()
    listed = list_response.json()
    reviews = reviews_response.json()
    assert created["artifactType"] == "diff"
    assert created["changedFiles"] == ["apps/demo/src/App.tsx"]
    assert created["patchText"] == listed[0]["patchText"]
    assert "node_modules" not in created["patchText"]
    assert len(reviews) == 1
    assert reviews[0]["artifactType"] == "review"
    assert reviews[0]["reviewedDiffArtifactId"] == created["artifactId"]
    assert reviews[0]["status"] == "passed"
    assert reviews[0]["riskLevel"] == "low"
    assert reviews[0]["adapterType"] == "scripted_mock"
    assert reviews[0]["filesReviewed"] == ["apps/demo/src/App.tsx"]
    assert manual_review_response.json()["id"] == reviews[0]["id"]

    task_run = db.get(TaskRun, task_run_id)
    assert task_run is not None
    task = db.get(Task, task_run.task_id)
    assert task is not None
    ledger_response = client.get(f"/sessions/{task.session_id}/ledger")
    assert ledger_response.status_code == 200
    ledger = ledger_response.json()
    assert ledger["latestTaskRunId"] == task_run_id
    assert ledger["latestDiffArtifactId"] == created["artifactId"]
    assert ledger["latestChangedFiles"] == ["apps/demo/src/App.tsx"]
    assert "Review: Scripted Review Agent passed" in ledger["summaryMd"]

    stored_review = db.get(Review, reviews[0]["id"])
    assert stored_review is not None
    assert stored_review.reviewed_diff_artifact_id == created["artifactId"]

    versions_response = client.get(f"/artifacts/{created['artifactId']}/versions")
    assert versions_response.status_code == 200
    versions = versions_response.json()
    assert versions[0]["artifactId"] == created["artifactId"]
    assert versions[0]["version"] == 1
    assert versions[0]["changedFiles"] == ["apps/demo/src/App.tsx"]


def test_artifact_versions_support_followup_v2_parent_chain(
    client: TestClient,
    db: DbSession,
    demo_worktree: Path,
) -> None:
    task_run_id = create_run_fixture(db, demo_worktree)
    mutate_worktree(demo_worktree)
    first_diff = collect_task_run_diff(db, task_run_id)
    task_run = db.get(TaskRun, task_run_id)
    assert task_run is not None

    followup_artifact = Artifact(
        task_run_id=task_run_id,
        artifact_type="diff",
        title="Follow-up diff",
        status="ready",
        version=2,
    )
    db.add(followup_artifact)
    db.commit()
    db.refresh(followup_artifact)

    followup_version = record_artifact_version(
        db,
        followup_artifact,
        parent_artifact_id=first_diff.artifact_id,
        source_task_run_id=task_run_id,
        git_base_ref=task_run.base_ref,
        git_head_ref="followup-head",
        changed_files=["apps/demo/src/App.tsx"],
        summary="Follow-up artifact version for v2 evidence.",
    )

    response = client.get(f"/artifacts/{followup_artifact.id}/versions")

    assert response.status_code == 200
    assert followup_version.version == 2
    payload = response.json()
    assert payload == [
        {
            "id": followup_version.id,
            "artifactId": followup_artifact.id,
            "version": 2,
            "sourceTaskRunId": task_run_id,
            "parentArtifactId": first_diff.artifact_id,
            "gitBaseRef": task_run.base_ref,
            "gitHeadRef": "followup-head",
            "changedFiles": ["apps/demo/src/App.tsx"],
            "summary": "Follow-up artifact version for v2 evidence.",
            "createdAt": payload[0]["createdAt"],
        }
    ]


def test_parse_numstat_value_handles_binary_and_normal() -> None:
    assert _parse_numstat_value("0") == 0
    assert _parse_numstat_value("42") == 42
    assert _parse_numstat_value("-") == 0
    with pytest.raises(ValueError):
        _parse_numstat_value("")
    with pytest.raises(ValueError):
        _parse_numstat_value("not-a-number")


def test_head_ref_appends_worktree_suffix_when_changes_present(
    demo_worktree: Path,
) -> None:
    head = _head_ref(demo_worktree, has_worktree_changes=False)
    assert "+worktree" not in head
    assert len(head) == 40

    head_with_changes = _head_ref(demo_worktree, has_worktree_changes=True)
    assert head_with_changes.endswith("+worktree")
    assert head_with_changes.startswith(head)


def test_capture_base_ref_for_worktree_succeeds_in_git_repo(
    demo_worktree: Path,
) -> None:
    ref = capture_base_ref_for_worktree(str(demo_worktree))
    assert ref is not None
    assert len(ref) == 40


def test_capture_base_ref_for_worktree_returns_none_for_non_git_dir(
    tmp_path: Path,
) -> None:
    ref = capture_base_ref_for_worktree(str(tmp_path))
    assert ref is None
