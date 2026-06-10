import json
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import BackgroundTasks
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.main import auto_start_safe_tasks
from app.external_workspaces import (
    ExternalWorkspaceRegistration,
    register_external_project_target,
)
from app.models import Agent, Artifact, Diff, Session, Task, TaskRun, TaskRunEvent, Workspace
from app.models import utc_now
from app.scheduler import (
    SCHEDULER_BLOCKED,
    SCHEDULER_READY,
    SCHEDULER_WAITING_DEPENDENCY,
    SCHEDULER_WAITING_TARGET_LOCK,
    cleanup_stale_target_locks,
    evaluate_and_apply_dependency_readiness,
    evaluate_dependency_readiness,
)
from app.session_queue import entry_for_task_run, mark_task_run_running
from app.task_runs import (
    TaskRunLifecycleError,
    claim_task_run_for_worker,
    create_task_run,
    retry_with_scripted_mock,
    transition_task_run,
)
from app.target_locks import acquire_target_lock, held_lock_for_target, lock_diagnostics_for_task_run
from app.provider_assignments import PROVIDER_ASSIGNMENT_MATRIX_ENV
from app.target_registry import (
    AGENTHUB_PLATFORM_TARGET_ID,
    DEMO_BACKEND_TARGET_ID,
    DEMO_FRONTEND_TARGET_ID,
)


def test_dependency_readiness_waits_until_upstream_task_completes() -> None:
    with scheduler_db() as db:
        _, _, upstream, downstream = seed_dependent_tasks(db)

        waiting = evaluate_dependency_readiness(db, downstream)
        assert waiting.state == SCHEDULER_WAITING_DEPENDENCY
        assert waiting.runnable is False
        assert waiting.blocking_dependency_ids == [upstream.id]

        upstream.status = "completed"
        db.add(upstream)
        db.commit()

        ready = evaluate_dependency_readiness(db, downstream)
        assert ready.state == SCHEDULER_READY
        assert ready.runnable is True
        assert ready.blocking_dependency_ids == []


def test_dependency_failure_blocks_downstream_task_with_visible_metadata() -> None:
    with scheduler_db() as db:
        _, _, upstream, downstream = seed_dependent_tasks(db)
        upstream.status = "failed"
        db.add(upstream)
        db.commit()

        decision = evaluate_and_apply_dependency_readiness(db, downstream)

        assert decision.state == SCHEDULER_BLOCKED
        assert decision.runnable is False

        stored = db.get(Task, downstream.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]
        assert stored.status == "blocked"
        assert scheduler["state"] == "blocked"
        assert scheduler["blockingDependencyIds"] == [upstream.id]


def test_auto_start_skips_task_with_incomplete_dependency() -> None:
    with scheduler_db() as db:
        _, _, upstream, downstream = seed_dependent_tasks(db, downstream_auto_start=True)

        auto_start_safe_tasks(db, [downstream], BackgroundTasks())

        runs = db.exec(select(TaskRun).where(TaskRun.task_id == downstream.id)).all()
        stored = db.get(Task, downstream.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]

        assert runs == []
        assert stored.status == "waiting_dependency"
        assert scheduler["state"] == "waiting_dependency"
        assert scheduler["blockingDependencyIds"] == [upstream.id]


def test_auto_start_runs_task_after_dependencies_complete() -> None:
    with scheduler_db() as db:
        _, _, upstream, downstream = seed_dependent_tasks(db, downstream_auto_start=True)
        upstream.status = "completed"
        db.add(upstream)
        db.commit()

        auto_start_safe_tasks(db, [downstream], BackgroundTasks())

        runs = db.exec(select(TaskRun).where(TaskRun.task_id == downstream.id)).all()
        stored = db.get(Task, downstream.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]

        assert len(runs) == 1
        assert runs[0].state == "queued"
        assert stored.status == "running"
        assert scheduler["state"] == "ready"
        assert scheduler["runnable"] is True


def test_terminal_upstream_transition_refreshes_downstream_scheduler_state() -> None:
    with scheduler_db() as db:
        _, _, upstream, downstream = seed_dependent_tasks(db)
        upstream_run = create_task_run(db, upstream.id)

        transition_task_run(
            db,
            upstream_run.id,
            "failed",
            error_code="TEST_FAILURE",
            error_message="Upstream failed in scheduler test.",
        )

        stored = db.get(Task, downstream.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]

        assert stored.status == "blocked"
        assert scheduler["state"] == "blocked"
        assert scheduler["blockingDependencyIds"] == [upstream.id]


def test_same_frontend_target_write_task_waits_for_active_lock() -> None:
    with scheduler_db() as db:
        _, session, first, second = seed_same_target_write_tasks(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            intent_type="frontend_change",
            safe_target="apps/demo/src",
        )
        first_run = create_task_run(db, first.id)

        auto_start_safe_tasks(db, [second], BackgroundTasks())

        runs = db.exec(select(TaskRun).where(TaskRun.task_id == second.id)).all()
        stored = db.get(Task, second.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]

        assert session.id == stored.session_id
        assert runs == []
        assert stored.status == "waiting_target_lock"
        assert scheduler["state"] == SCHEDULER_WAITING_TARGET_LOCK
        assert scheduler["targetId"] == DEMO_FRONTEND_TARGET_ID
        assert scheduler["lockHolderTaskRunIds"] == [first_run.id]


def test_manual_start_queues_when_same_backend_target_lock_is_active() -> None:
    with scheduler_db() as db:
        _, _, first, second = seed_same_target_write_tasks(
            db,
            target_id=DEMO_BACKEND_TARGET_ID,
            intent_type="backend_change",
            safe_target="apps/demo-api",
        )
        first_run = create_task_run(db, first.id)

        second_run = create_task_run(db, second.id)

        stored = db.get(Task, second.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]
        queue_entry = entry_for_task_run(db, second_run.id)

        assert first_run.state == "queued"
        assert second_run.state == "queued"
        assert stored.status == "running"
        assert queue_entry.state == "waiting_lock"
        assert scheduler["state"] == SCHEDULER_WAITING_TARGET_LOCK
        assert scheduler["lockHolderTaskRunIds"] == [first_run.id]


def test_terminal_run_releases_target_lock_for_waiting_task() -> None:
    with scheduler_db() as db:
        _, _, first, second = seed_same_target_write_tasks(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            intent_type="frontend_change",
            safe_target="apps/demo/src",
        )
        first_run = create_task_run(db, first.id)
        auto_start_safe_tasks(db, [second], BackgroundTasks())

        transition_task_run(db, first_run.id, "completed")

        stored = db.get(Task, second.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]

        assert stored.status == "pending"
        assert scheduler["state"] == "ready"
        assert scheduler["targetId"] == DEMO_FRONTEND_TARGET_ID
        assert scheduler["lockHolderTaskRunIds"] == []


def test_stale_target_lock_cleanup_does_not_release_active_owner() -> None:
    with scheduler_db() as db:
        _, session, first, second = seed_same_target_write_tasks(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            intent_type="frontend_change",
            safe_target="apps/demo/src",
        )
        first_run = create_task_run(db, first.id)
        auto_start_safe_tasks(db, [second], BackgroundTasks())

        released = cleanup_stale_target_locks(db, session_id=session.id)

        stored = db.get(Task, second.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]
        release_events = db.exec(
            select(TaskRunEvent).where(
                TaskRunEvent.event_type == "target_lock.released"
            )
        ).all()

        assert released == []
        assert db.get(TaskRun, first_run.id).state == "queued"
        assert stored.status == "waiting_target_lock"
        assert scheduler["lockHolderTaskRunIds"] == [first_run.id]
        assert release_events == []


def test_stale_target_lock_cleanup_releases_only_stale_owner() -> None:
    with scheduler_db() as db:
        _, session, first, second = seed_same_target_write_tasks(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            intent_type="frontend_change",
            safe_target="apps/demo/src",
        )
        first_run = create_task_run(db, first.id)
        first_run = claim_task_run_for_worker(
            db,
            first_run.id,
            worker_id="worker:stale-lock-test",
        )
        lock_result = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=session.id,
            task_run_id=first_run.id,
            worker_id="worker:stale-lock-test",
            lease_expires_at=first_run.lease_expires_at,
        )
        first_run.lease_expires_at = utc_now() - timedelta(minutes=1)
        lock_result.lock.lease_expires_at = first_run.lease_expires_at
        db.add(lock_result.lock)
        db.add(first_run)
        db.commit()
        auto_start_safe_tasks(db, [second], BackgroundTasks())

        released = cleanup_stale_target_locks(db, session_id=session.id)

        stored_run = db.get(TaskRun, first_run.id)
        stored = db.get(Task, second.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]
        release_event = db.exec(
            select(TaskRunEvent).where(
                TaskRunEvent.task_run_id == first_run.id,
                TaskRunEvent.event_type == "target_lock.stale_released",
            )
        ).one()
        payload = json.loads(release_event.payload_json)

        assert [item["taskRunId"] for item in released] == [first_run.id]
        assert stored_run.state == "failed"
        assert stored_run.error_code == "TASK_RUN_STALE"
        assert stored.status == "pending"
        assert scheduler["state"] == SCHEDULER_READY
        assert scheduler["lockHolderTaskRunIds"] == []
        assert payload["targetId"] == DEMO_FRONTEND_TARGET_ID
        assert payload["holderTaskRunId"] == first_run.id
        assert payload["releaseReason"] == "stale_lease_expired"


def test_read_only_review_task_does_not_acquire_target_write_lock() -> None:
    with scheduler_db() as db:
        _, session, first, _ = seed_same_target_write_tasks(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            intent_type="frontend_change",
            safe_target="apps/demo/src",
        )
        qa = Agent(name="QA Agent", role="qa", adapter_type="scripted_mock", provider="local")
        review = Task(
            session_id=session.id,
            title="Review frontend diff",
            intent_type="review",
            status="pending",
            assigned_agent_id=qa.id,
            plan_json=json.dumps(
                {
                    "targetId": DEMO_FRONTEND_TARGET_ID,
                    "safeTarget": "apps/demo/src",
                    "readOnly": True,
                },
                separators=(",", ":"),
            ),
        )
        db.add(qa)
        db.add(review)
        db.commit()
        db.refresh(review)
        create_task_run(db, first.id)

        review_run = create_task_run(db, review.id)

        assert review_run.state == "queued"


def test_ordinary_backend_task_cannot_acquire_platform_write_lock() -> None:
    with scheduler_db() as db:
        _, session, _, _ = seed_same_target_write_tasks(
            db,
            target_id=DEMO_BACKEND_TARGET_ID,
            intent_type="backend_change",
            safe_target="apps/demo-api",
        )
        backend = db.exec(select(Agent).where(Agent.role == "backend")).one()
        platform_task = Task(
            session_id=session.id,
            title="Unsafe platform write",
            intent_type="backend_change",
            status="pending",
            assigned_agent_id=backend.id,
            plan_json=json.dumps(
                {
                    "targetId": AGENTHUB_PLATFORM_TARGET_ID,
                    "safeTarget": "apps/api",
                },
                separators=(",", ":"),
            ),
        )
        db.add(platform_task)
        db.commit()
        db.refresh(platform_task)

        with pytest.raises(TaskRunLifecycleError, match="platform mode"):
            create_task_run(db, platform_task.id)

        stored = db.get(Task, platform_task.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]

        assert stored.status == "blocked"
        assert scheduler["state"] == "blocked"
        assert scheduler["targetId"] == AGENTHUB_PLATFORM_TARGET_ID


def test_same_external_target_write_task_queues_for_active_lock(tmp_path) -> None:
    with scheduler_db() as db:
        workspace, session, _, _ = seed_same_target_write_tasks(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            intent_type="frontend_change",
            safe_target="apps/demo/src",
        )
        external_root = tmp_path / "external-app"
        (external_root / "src").mkdir(parents=True)
        register_external_project_target(
            db,
            workspace,
            ExternalWorkspaceRegistration(
                target_id="external-vite-app",
                name="External Vite App",
                root_path=str(external_root),
                project_type="vite-react",
                allowed_paths=["src"],
            ),
        )
        frontend = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        plan = {
            "targetId": "external-vite-app",
            "safeTarget": "src",
            "autoStart": True,
            "files": ["src/App.tsx"],
        }
        first = Task(
            session_id=session.id,
            title="First external write",
            intent_type="frontend_change",
            status="pending",
            assigned_agent_id=frontend.id,
            plan_json=json.dumps(plan, separators=(",", ":")),
        )
        second = Task(
            session_id=session.id,
            title="Second external write",
            intent_type="frontend_change",
            status="pending",
            assigned_agent_id=frontend.id,
            plan_json=json.dumps(plan, separators=(",", ":")),
        )
        db.add(first)
        db.add(second)
        db.commit()
        db.refresh(first)
        db.refresh(second)
        first_run = create_task_run(db, first.id)

        second_run = create_task_run(db, second.id)

        stored = db.get(Task, second.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]
        queue_entry = entry_for_task_run(db, second_run.id)

        assert first_run.state == "queued"
        assert second_run.state == "queued"
        assert stored.status == "running"
        assert queue_entry.state == "waiting_lock"
        assert scheduler["state"] == SCHEDULER_WAITING_TARGET_LOCK
        assert scheduler["targetId"] == "external-vite-app"
        assert scheduler["lockHolderTaskRunIds"] == [first_run.id]


def test_provisioned_project_runs_use_durable_queue_and_release_target_lock(tmp_path) -> None:
    with scheduler_db() as db:
        workspace = Workspace(
            name="AgentHub Demo",
            repo_url="local://apps/demo",
            root_path="apps/demo",
            default_branch="main",
        )
        session = Session(
            workspace_id=workspace.id,
            title="Provisioned run session",
            bound_branch="main",
            worktree_path=".worktrees/provisioned-run-session",
        )
        frontend = Agent(
            name="Frontend Agent",
            role="frontend",
            adapter_type="codex",
            provider="local",
        )
        db.add(workspace)
        db.add(session)
        db.add(frontend)
        db.commit()
        frontend_root = tmp_path / "notes-app" / "frontend"
        (frontend_root / "src").mkdir(parents=True)
        (frontend_root / "src" / "App.tsx").write_text(
            "export default function App() { return null }\n"
        )
        register_external_project_target(
            db,
            workspace,
            ExternalWorkspaceRegistration(
                target_id="external-frontend-notes-app",
                name="Notes frontend",
                root_path=str(frontend_root),
                project_type="vite-react",
                allowed_paths=["src", "package.json", "vite.config.ts"],
                denied_paths=[".env", "node_modules"],
                check_command="pnpm check",
                build_command="pnpm build",
                package_manager="pnpm",
                detected_framework="vite-react",
            ),
        )
        session.active_frontend_target_id = "external-frontend-notes-app"
        plan = {
            "planner": "orchestrator_external_target_v1",
            "targetId": "external-frontend-notes-app",
            "frontendTargetId": "external-frontend-notes-app",
            "safeTarget": "src",
            "allowedPaths": ["src", "package.json", "vite.config.ts"],
            "deniedPaths": [".env", "node_modules"],
            "files": ["src/App.tsx"],
            "autoStart": True,
        }
        first = Task(
            session_id=session.id,
            title="First provisioned frontend task",
            intent_type="frontend_change",
            status="pending",
            assigned_agent_id=frontend.id,
            plan_json=json.dumps(plan, separators=(",", ":")),
        )
        second = Task(
            session_id=session.id,
            title="Second provisioned frontend task",
            intent_type="frontend_change",
            status="pending",
            assigned_agent_id=frontend.id,
            plan_json=json.dumps(plan, separators=(",", ":")),
        )
        db.add(session)
        db.add(first)
        db.add(second)
        db.commit()
        db.refresh(first)
        db.refresh(second)

        first_run = claim_task_run_for_worker(
            db,
            create_task_run(db, first.id).id,
            worker_id="worker:provisioned-first",
        )
        mark_task_run_running(
            db,
            first_run.id,
            "Session write queue entry is at the head of the queue.",
        )
        lock_result = acquire_target_lock(
            db,
            target_id="external-frontend-notes-app",
            session_id=session.id,
            task_run_id=first_run.id,
            worker_id="worker:provisioned-first",
            lease_expires_at=first_run.lease_expires_at,
        )
        second_run = create_task_run(db, second.id)
        second_entry = entry_for_task_run(db, second_run.id)

        assert lock_result.acquired is True
        assert entry_for_task_run(db, first_run.id).state == "running"
        assert second_run.state == "queued"
        assert second_entry.state == "waiting_lock"
        assert second_entry.target_id == "external-frontend-notes-app"
        assert lock_diagnostics_for_task_run(db, first_run.id)["state"] == "held"
        assert held_lock_for_target(db, "external-frontend-notes-app") is not None

        transition_task_run(db, first_run.id, "completed")

        assert held_lock_for_target(db, "external-frontend-notes-app") is None
        assert lock_diagnostics_for_task_run(db, first_run.id)["state"] == "released"
        assert entry_for_task_run(db, first_run.id).state == "completed"


def test_file_overlap_conflict_blocks_unsequenced_write_task() -> None:
    with scheduler_db() as db:
        _, _, first, second = seed_same_target_write_tasks(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            intent_type="frontend_change",
            safe_target="apps/demo/src",
        )
        first.depends_on_task_ids = "[]"
        second.depends_on_task_ids = "[]"
        db.add(first)
        db.add(second)
        db.commit()

        with pytest.raises(TaskRunLifecycleError, match="file overlap conflict"):
            create_task_run(db, second.id)

        stored = db.get(Task, second.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]

        assert stored.status == "blocked"
        assert scheduler["state"] == SCHEDULER_BLOCKED
        assert scheduler["conflictType"] == "file_overlap"
        assert scheduler["conflictingTaskIds"] == [first.id]


def test_dirty_worktree_conflict_blocks_external_write_task(tmp_path: Path) -> None:
    with scheduler_db() as db:
        workspace, session, _, _ = seed_same_target_write_tasks(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            intent_type="frontend_change",
            safe_target="apps/demo/src",
        )
        external_root = tmp_path / "external-conflict-app"
        (external_root / "src").mkdir(parents=True)
        (external_root / "src" / "App.tsx").write_text("export default function App() {}\n")
        subprocess.run(["git", "init"], cwd=external_root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=external_root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=external_root, check=True)
        subprocess.run(["git", "add", "src/App.tsx"], cwd=external_root, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=external_root, check=True)
        (external_root / "README.md").write_text("local notes\n")
        register_external_project_target(
            db,
            workspace,
            ExternalWorkspaceRegistration(
                target_id="external-conflict-app",
                name="External Conflict App",
                root_path=str(external_root),
                project_type="vite-react",
                allowed_paths=["src"],
            ),
        )
        frontend = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        task = Task(
            session_id=session.id,
            title="External write with dirty unrelated file",
            intent_type="frontend_change",
            status="pending",
            assigned_agent_id=frontend.id,
            plan_json=json.dumps(
                {
                    "targetId": "external-conflict-app",
                    "safeTarget": "src",
                    "files": ["src/App.tsx"],
                },
                separators=(",", ":"),
            ),
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        with pytest.raises(TaskRunLifecycleError, match="dirty worktree conflict"):
            create_task_run(db, task.id)

        stored = db.get(Task, task.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]

        assert stored.status == "blocked"
        assert scheduler["state"] == SCHEDULER_BLOCKED
        assert scheduler["conflictType"] == "dirty_worktree"
        assert scheduler["conflictingFiles"] == ["README.md"]


def test_downstream_write_allows_dirty_files_from_completed_dependency_diff(
    tmp_path: Path,
) -> None:
    with scheduler_db() as db:
        workspace, session, _, _ = seed_same_target_write_tasks(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            intent_type="frontend_change",
            safe_target="apps/demo/src",
        )
        external_root = tmp_path / "external-followup-app"
        (external_root / "src").mkdir(parents=True)
        (external_root / "src" / "App.tsx").write_text("export default function App() {}\n")
        (external_root / "src" / "BreakoutGame.tsx").write_text("export function BreakoutGame() {}\n")
        subprocess.run(["git", "init"], cwd=external_root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=external_root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=external_root, check=True)
        subprocess.run(["git", "add", "src/App.tsx", "src/BreakoutGame.tsx"], cwd=external_root, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=external_root, check=True)
        (external_root / "src" / "BreakoutGame.tsx").write_text(
            "export function BreakoutGame() { return null; }\n"
        )
        register_external_project_target(
            db,
            workspace,
            ExternalWorkspaceRegistration(
                target_id="external-followup-app",
                name="External Follow-up App",
                root_path=str(external_root),
                project_type="vite-react",
                allowed_paths=["src"],
            ),
        )
        frontend = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        upstream = Task(
            session_id=session.id,
            title="Initial Breakout implementation",
            intent_type="frontend_change",
            status="completed",
            assigned_agent_id=frontend.id,
            plan_json=json.dumps(
                {
                    "targetId": "external-followup-app",
                    "safeTarget": "src",
                    "files": ["src/BreakoutGame.tsx"],
                },
                separators=(",", ":"),
            ),
        )
        review = Task(
            session_id=session.id,
            title="Review Breakout implementation",
            intent_type="review",
            status="completed",
            assigned_agent_id=frontend.id,
            depends_on_task_ids=json.dumps([upstream.id], separators=(",", ":")),
            plan_json=json.dumps(
                {"targetId": "external-followup-app", "readOnly": True},
                separators=(",", ":"),
            ),
        )
        downstream = Task(
            session_id=session.id,
            title="Fix Breakout strict build",
            intent_type="frontend_change",
            status="pending",
            assigned_agent_id=frontend.id,
            depends_on_task_ids=json.dumps([review.id], separators=(",", ":")),
            plan_json=json.dumps(
                {
                    "targetId": "external-followup-app",
                    "safeTarget": "src",
                    "files": ["src/App.tsx"],
                },
                separators=(",", ":"),
            ),
        )
        db.add(upstream)
        db.add(review)
        db.add(downstream)
        db.commit()
        db.refresh(upstream)
        db.refresh(review)
        db.refresh(downstream)
        upstream_run = TaskRun(
            task_id=upstream.id,
            agent_id=frontend.id,
            state="completed",
            worktree_path=str(external_root),
            metrics_json=json.dumps({"adapterType": "claude_code"}, separators=(",", ":")),
        )
        db.add(upstream_run)
        db.commit()
        db.refresh(upstream_run)
        diff_artifact = Artifact(
            task_run_id=upstream_run.id,
            artifact_type="diff",
            title="Git diff",
            status="ready",
        )
        db.add(diff_artifact)
        db.commit()
        db.refresh(diff_artifact)
        diff = Diff(
            artifact_id=diff_artifact.id,
            base_ref="base",
            head_ref="worktree:dirty",
            patch_text="",
            changed_files_json=json.dumps(["src/BreakoutGame.tsx"], separators=(",", ":")),
        )
        db.add(diff)
        db.commit()

        run = create_task_run(db, downstream.id)

        stored = db.get(Task, downstream.id)
        scheduler = json.loads(stored.plan_json).get("scheduler", {})
        assert run.state == "queued"
        assert stored.status == "running"
        assert scheduler.get("state", SCHEDULER_READY) == SCHEDULER_READY


def test_contract_drift_conflict_blocks_stale_contract_task() -> None:
    with scheduler_db() as db:
        _, _, task, _ = seed_same_target_write_tasks(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            intent_type="frontend_change",
            safe_target="apps/demo/src",
        )
        task.plan_json = json.dumps(
            {
                "targetId": DEMO_FRONTEND_TARGET_ID,
                "safeTarget": "apps/demo/src",
                "files": ["apps/demo/src/App.tsx"],
                "contractId": "contract-a",
                "appContract": {"contractId": "contract-b"},
            },
            separators=(",", ":"),
        )
        db.add(task)
        db.commit()

        with pytest.raises(TaskRunLifecycleError, match="contract drift conflict"):
            create_task_run(db, task.id)

        stored = db.get(Task, task.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]

        assert stored.status == "blocked"
        assert scheduler["state"] == SCHEDULER_BLOCKED
        assert scheduler["conflictType"] == "contract_drift"


def test_failed_codex_coding_task_exposes_fallback_available_state() -> None:
    with scheduler_db() as db:
        _, _, task, _ = seed_same_target_write_tasks(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            intent_type="frontend_change",
            safe_target="apps/demo/src",
        )
        task_run = create_task_run(db, task.id)

        transition_task_run(
            db,
            task_run.id,
            "failed",
            error_code="CODEX_TEST_FAILURE",
            error_message="Codex failed in scheduler test.",
        )

        stored = db.get(Task, task.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]

        assert stored.status == "failed"
        assert scheduler["state"] == "fallback_available"
        assert scheduler["retryable"] is True
        assert scheduler["fallbackAvailable"] is True
        assert scheduler["adapterType"] == "codex"


def test_failed_non_codex_task_exposes_retryable_without_fallback() -> None:
    with scheduler_db() as db:
        _, _, task, _ = seed_same_target_write_tasks(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            intent_type="frontend_change",
            safe_target="apps/demo/src",
        )
        task_run = create_task_run(db, task.id, adapter_type="scripted_mock")

        transition_task_run(
            db,
            task_run.id,
            "failed",
            error_code="SCRIPTED_TEST_FAILURE",
            error_message="Scripted mock failed in scheduler test.",
        )

        stored = db.get(Task, task.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]

        assert stored.status == "failed"
        assert scheduler["state"] == "retryable"
        assert scheduler["retryable"] is True
        assert scheduler["fallbackAvailable"] is False
        assert scheduler["adapterType"] == "scripted_mock"


def test_completed_fallback_unblocks_downstream_dependency() -> None:
    with scheduler_db() as db:
        _, session, upstream, _ = seed_same_target_write_tasks(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            intent_type="frontend_change",
            safe_target="apps/demo/src",
        )
        frontend = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        downstream = Task(
            session_id=session.id,
            title="Downstream frontend write",
            intent_type="frontend_change",
            status="pending",
            assigned_agent_id=frontend.id,
            plan_json=json.dumps(
                {
                    "targetId": DEMO_FRONTEND_TARGET_ID,
                    "safeTarget": "apps/demo/src",
                    "files": ["apps/demo/src/App.tsx"],
                    "autoStart": True,
                },
                separators=(",", ":"),
            ),
            depends_on_task_ids=json.dumps([upstream.id], separators=(",", ":")),
        )
        db.add(downstream)
        db.commit()
        db.refresh(downstream)
        upstream_run = create_task_run(db, upstream.id)
        transition_task_run(db, upstream_run.id, "failed")

        blocked = db.get(Task, downstream.id)
        assert blocked.status == "blocked"

        fallback_run = retry_with_scripted_mock(db, upstream_run.id)
        transition_task_run(db, fallback_run.id, "completed")

        unblocked = db.get(Task, downstream.id)
        scheduler = json.loads(unblocked.plan_json)["scheduler"]

        assert unblocked.status == "pending"
        assert scheduler["state"] == "ready"
        assert scheduler["blockingDependencyIds"] == []


def test_mixed_provider_dependency_waits_then_frontend_uses_claude_code(
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
                }
            },
            separators=(",", ":"),
        ),
    )
    with scheduler_db() as db:
        _, _, backend_task, frontend_task = seed_mixed_provider_task_graph(db)

        auto_start_safe_tasks(db, [frontend_task], BackgroundTasks())

        assert db.exec(select(TaskRun).where(TaskRun.task_id == frontend_task.id)).all() == []
        waiting_frontend = db.get(Task, frontend_task.id)
        waiting_scheduler = json.loads(waiting_frontend.plan_json)["scheduler"]
        assert waiting_frontend.status == "waiting_dependency"
        assert waiting_scheduler["state"] == SCHEDULER_WAITING_DEPENDENCY
        assert waiting_scheduler["blockingDependencyIds"] == [backend_task.id]

        backend_run = create_task_run(db, backend_task.id)
        backend_metrics = json.loads(backend_run.metrics_json)
        assert backend_metrics["providerAssignment"]["adapterType"] == "codex"
        transition_task_run(db, backend_run.id, "completed")

        auto_start_safe_tasks(db, [frontend_task], BackgroundTasks())

        frontend_runs = db.exec(select(TaskRun).where(TaskRun.task_id == frontend_task.id)).all()
        frontend_run = frontend_runs[0]
        frontend_metrics = json.loads(frontend_run.metrics_json)
        stored_frontend = db.get(Task, frontend_task.id)
        scheduler = json.loads(stored_frontend.plan_json)["scheduler"]

        assert len(frontend_runs) == 1
        assert frontend_run.state == "queued"
        assert frontend_metrics["providerAssignment"]["adapterType"] == "claude_code"
        assert frontend_metrics["providerAssignment"]["providerId"] == "local-claude-code-cli"
        assert scheduler["state"] == SCHEDULER_READY
        assert scheduler["targetId"] == DEMO_FRONTEND_TARGET_ID


def test_target_lock_queue_is_provider_independent_for_same_frontend_target() -> None:
    with scheduler_db() as db:
        _, _, first, second = seed_same_target_write_tasks(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            intent_type="frontend_change",
            safe_target="apps/demo/src",
        )
        first_run = create_task_run(db, first.id, adapter_type="codex")

        second_run = create_task_run(db, second.id, adapter_type="claude_code")

        first_metrics = json.loads(first_run.metrics_json)
        stored_second = db.get(Task, second.id)
        scheduler = json.loads(stored_second.plan_json)["scheduler"]
        queue_entry = entry_for_task_run(db, second_run.id)

        assert first_metrics["providerAssignment"]["adapterType"] == "codex"
        assert second_run.state == "queued"
        assert stored_second.status == "running"
        assert queue_entry.state == "waiting_lock"
        assert scheduler["state"] == SCHEDULER_WAITING_TARGET_LOCK
        assert scheduler["targetId"] == DEMO_FRONTEND_TARGET_ID
        assert scheduler["lockHolderTaskRunIds"] == [first_run.id]


def test_different_targets_can_queue_with_different_providers(
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
                }
            },
            separators=(",", ":"),
        ),
    )
    with scheduler_db() as db:
        _, _, backend_task, frontend_task = seed_mixed_provider_task_graph(
            db,
            frontend_depends_on_backend=False,
        )

        backend_run = create_task_run(db, backend_task.id)
        frontend_run = create_task_run(db, frontend_task.id)

        backend_metrics = json.loads(backend_run.metrics_json)
        frontend_metrics = json.loads(frontend_run.metrics_json)

        assert backend_run.state == "queued"
        assert frontend_run.state == "queued"
        assert backend_metrics["providerAssignment"]["adapterType"] == "codex"
        assert frontend_metrics["providerAssignment"]["adapterType"] == "claude_code"


def test_failed_mixed_provider_run_preserves_provider_assignment_in_scheduler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        PROVIDER_ASSIGNMENT_MATRIX_ENV,
        json.dumps(
            {
                "roles": {
                    "frontend": {
                        "adapterType": "claude_code",
                        "providerId": "local-claude-code-cli",
                    }
                }
            },
            separators=(",", ":"),
        ),
    )
    with scheduler_db() as db:
        _, _, _, frontend_task = seed_mixed_provider_task_graph(
            db,
            frontend_depends_on_backend=False,
        )
        frontend_run = create_task_run(db, frontend_task.id)

        transition_task_run(
            db,
            frontend_run.id,
            "failed",
            error_code="CLAUDE_CODE_TEST_FAILURE",
            error_message="Claude Code failed in scheduler test.",
        )

        stored = db.get(Task, frontend_task.id)
        scheduler = json.loads(stored.plan_json)["scheduler"]

        assert stored.status == "failed"
        assert scheduler["state"] == "retryable"
        assert scheduler["adapterType"] == "claude_code"
        assert scheduler["providerId"] == "local-claude-code-cli"
        assert scheduler["providerAssignment"]["adapterType"] == "claude_code"
        assert scheduler["providerAssignment"]["providerId"] == "local-claude-code-cli"


@contextmanager
def scheduler_db() -> Iterator[DbSession]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        yield db


def seed_dependent_tasks(
    db: DbSession,
    *,
    downstream_auto_start: bool = False,
) -> tuple[Workspace, Session, Task, Task]:
    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="Scheduler session",
        bound_branch="main",
        worktree_path=".worktrees/scheduler-session",
    )
    frontend = Agent(
        name="Frontend Agent",
        role="frontend",
        adapter_type="codex",
        provider="local",
    )
    upstream = Task(
        session_id=session.id,
        title="Prepare upstream task",
        intent_type="planning",
        status="pending",
        priority=0,
        assigned_agent_id=frontend.id,
        plan_json=json.dumps({"planner": "scheduler_test"}, separators=(",", ":")),
    )
    downstream_plan = {
        "planner": "scheduler_test",
        "autoStart": downstream_auto_start,
        "safeTarget": "apps/demo/src",
        "files": ["apps/demo/src/App.tsx"],
    }
    downstream = Task(
        session_id=session.id,
        title="Run downstream frontend task",
        intent_type="frontend_change",
        status="pending",
        priority=1,
        assigned_agent_id=frontend.id,
        plan_json=json.dumps(downstream_plan, separators=(",", ":")),
        depends_on_task_ids=json.dumps([upstream.id], separators=(",", ":")),
    )
    db.add(workspace)
    db.add(session)
    db.add(frontend)
    db.add(upstream)
    db.add(downstream)
    db.commit()
    db.refresh(upstream)
    db.refresh(downstream)
    return workspace, session, upstream, downstream


def seed_same_target_write_tasks(
    db: DbSession,
    *,
    target_id: str,
    intent_type: str,
    safe_target: str,
) -> tuple[Workspace, Session, Task, Task]:
    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="Lock session",
        bound_branch="main",
        worktree_path=".worktrees/lock-session",
    )
    role = "backend" if intent_type == "backend_change" else "frontend"
    agent = Agent(
        name=f"{role.title()} Agent",
        role=role,
        adapter_type="codex",
        provider="local",
    )
    files = (
        ["apps/demo/src/App.tsx"]
        if safe_target == "apps/demo/src"
        else ["apps/demo-api/app/main.py"]
    )
    plan = {
        "targetId": target_id,
        "safeTarget": safe_target,
        "autoStart": True,
        "files": files,
    }
    first = Task(
        session_id=session.id,
        title="First write",
        intent_type=intent_type,
        status="pending",
        assigned_agent_id=agent.id,
        plan_json=json.dumps(plan, separators=(",", ":")),
    )
    second = Task(
        session_id=session.id,
        title="Second write",
        intent_type=intent_type,
        status="pending",
        assigned_agent_id=agent.id,
        plan_json=json.dumps(plan, separators=(",", ":")),
    )
    db.add(workspace)
    db.add(session)
    db.add(agent)
    db.add(first)
    db.add(second)
    db.commit()
    db.refresh(first)
    db.refresh(second)
    return workspace, session, first, second


def seed_mixed_provider_task_graph(
    db: DbSession,
    *,
    frontend_depends_on_backend: bool = True,
) -> tuple[Workspace, Session, Task, Task]:
    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="Mixed provider scheduler session",
        bound_branch="main",
        worktree_path=".worktrees/mixed-provider-session",
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
        "contractId": "contract-mini-crm",
        "appType": "mini_crm_contacts",
        "backendTargetId": DEMO_BACKEND_TARGET_ID,
        "frontendTargetId": DEMO_FRONTEND_TARGET_ID,
    }
    backend_task = Task(
        session_id=session.id,
        title="Implement mini CRM backend",
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
                "autoStart": True,
                "contractId": contract["contractId"],
                "appContract": contract,
            },
            separators=(",", ":"),
        ),
    )
    frontend_task = Task(
        session_id=session.id,
        title="Implement mini CRM frontend",
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
                "autoStart": True,
                "contractId": contract["contractId"],
                "appContract": contract,
            },
            separators=(",", ":"),
        ),
        depends_on_task_ids=json.dumps(
            [backend_task.id] if frontend_depends_on_backend else [],
            separators=(",", ":"),
        ),
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
