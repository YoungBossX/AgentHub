import json
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine

from app.external_evidence import record_command_evidence
from app.external_workspaces import (
    ExternalWorkspaceRegistration,
    register_external_project_target,
)
from app.models import Agent, Artifact, Diff, Session, Task, TaskRun, Workspace
from app.reviews import create_scripted_review_for_diff


def db_fixture() -> Iterator[DbSession]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as session:
        yield session


def create_external_diff_fixture(
    db: DbSession,
    tmp_path: Path,
    *,
    changed_files: list[str],
) -> str:
    external_root = tmp_path / "external-review"
    (external_root / "src").mkdir(parents=True)
    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="External review session",
        bound_branch="main",
        worktree_path=".worktrees/external-review-session",
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
            target_id="external-review-target",
            name="External Review Target",
            root_path=str(external_root),
            project_type="vite-react",
            allowed_paths=["src"],
            test_command="pnpm test",
            check_command="pnpm check",
            build_command="pnpm build",
        ),
    )
    task = Task(
        session_id=session.id,
        title="External frontend change",
        intent_type="frontend_change",
        assigned_agent_id=agent.id,
        plan_json=json.dumps(
            {
                "targetId": "external-review-target",
                "safeTarget": "src",
                "files": changed_files,
            },
            separators=(",", ":"),
        ),
    )
    task_run = TaskRun(
        task_id=task.id,
        agent_id=agent.id,
        state="completed",
        worktree_path=str(external_root),
        base_ref="base",
        head_ref="head+worktree",
    )
    artifact = Artifact(
        task_run_id=task_run.id,
        artifact_type="diff",
        title="Git diff",
        status="ready",
    )
    diff = Diff(
        artifact_id=artifact.id,
        base_ref="base",
        head_ref="head+worktree",
        patch_text="\n".join(f"diff --git a/{path} b/{path}" for path in changed_files),
        changed_files_json=json.dumps(changed_files, separators=(",", ":")),
        stats_json=json.dumps({"filesChanged": len(changed_files)}, separators=(",", ":")),
    )
    db.add(task)
    db.add(task_run)
    db.add(artifact)
    db.add(diff)
    db.commit()
    db.refresh(artifact)
    db.refresh(task_run)
    return artifact.id


def test_external_review_fails_denied_path_edits(tmp_path: Path) -> None:
    with next(db_fixture()) as db:
        diff_artifact_id = create_external_diff_fixture(
            db,
            tmp_path,
            changed_files=["src/App.tsx", ".env"],
        )

        review = create_scripted_review_for_diff(db, diff_artifact_id)

    assert review.status == "failed"
    assert review.risk_level == "high"
    assert any("denied path .env" in finding["message"] for finding in review.findings)


def test_external_review_warns_for_outside_allowed_paths_and_failed_evidence(
    tmp_path: Path,
) -> None:
    with next(db_fixture()) as db:
        diff_artifact_id = create_external_diff_fixture(
            db,
            tmp_path,
            changed_files=["src/App.tsx", "README.md"],
        )
        artifact = db.get(Artifact, diff_artifact_id)
        record_command_evidence(
            db,
            artifact.task_run_id,
            command_type="check",
            command="pnpm check",
            exit_code=0,
        )
        record_command_evidence(
            db,
            artifact.task_run_id,
            command_type="test",
            command="pnpm test",
            exit_code=1,
            stderr="tests failed",
        )

        review = create_scripted_review_for_diff(db, diff_artifact_id)

    assert review.status == "warning"
    assert review.risk_level == "medium"
    assert any("outside registered allowed paths" in finding["message"] for finding in review.findings)
    assert any("test command `pnpm test` failed" in finding["message"] for finding in review.findings)
    assert any("no evidence was recorded" in finding["message"] for finding in review.findings)


def test_external_review_passes_when_paths_and_evidence_are_clean(
    tmp_path: Path,
) -> None:
    with next(db_fixture()) as db:
        diff_artifact_id = create_external_diff_fixture(
            db,
            tmp_path,
            changed_files=["src/App.tsx"],
        )
        artifact = db.get(Artifact, diff_artifact_id)
        for command_type, command in [
            ("check", "pnpm check"),
            ("test", "pnpm test"),
            ("build", "pnpm build"),
        ]:
            record_command_evidence(
                db,
                artifact.task_run_id,
                command_type=command_type,
                command=command,
                exit_code=0,
            )

        review = create_scripted_review_for_diff(db, diff_artifact_id)

    assert review.status == "passed"
    assert review.risk_level == "low"
    assert review.findings == []
