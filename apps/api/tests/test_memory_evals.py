from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine

from app.context_pack import build_session_context_pack
from app.llm_planner import build_llm_planner_input
from app.memory_evals import (
    cross_agent_consistency_rate,
    memory_precision_at_5,
    preference_recall_rate,
    prompt_injection_write_block_rate,
    snapshot_consistency_rate,
    stale_memory_injection_count,
)
from app.memory_retrieval import retrieve_relevant_memories
from app.memory_store import MemoryItemInput, create_memory_item
from app.models import Agent, Message, Session, Task, Workspace
from app.task_runs import create_task_run


def test_memory_eval_metrics_compute_expected_rates() -> None:
    assert preference_recall_rate({"a", "b"}, ["a", "c"]) == 0.5
    assert cross_agent_consistency_rate({"planner": "s1", "frontend": "s1"}) == 1.0
    assert cross_agent_consistency_rate({"planner": "s1", "frontend": "s2"}) == 0.5
    assert prompt_injection_write_block_rate(3, 4) == 0.75
    assert snapshot_consistency_rate(["s1", "s1", "s1"]) == 1.0
    assert snapshot_consistency_rate(["s1", "s2"]) == 0.5
    assert stale_memory_injection_count(
        [
            {"status": "active"},
            {"status": "archived"},
            {"status": "warm", "stale": True},
        ]
    ) == 2


def test_memory_eval_precision_at_5() -> None:
    with _db() as db:
        workspace, _session, _frontend = _seed(db)
        relevant = create_memory_item(
            db,
            MemoryItemInput(
                workspace_id=workspace.id,
                scope="user",
                memory_type="user_preference",
                source="user_explicit",
                title="Chinese replies",
                content_md="用户写中文时优先中文回复。",
                status="active",
                trust_level="user_confirmed",
            ),
        )
        results = retrieve_relevant_memories(
            db,
            query="中文 回复",
            workspace_id=workspace.id,
            limit=5,
        )

        assert memory_precision_at_5(results, {relevant.id}) == 1.0


def test_saved_preference_reaches_planner_and_coding_context_same_snapshot() -> None:
    with _db() as db:
        workspace, session, frontend = _seed(db)
        preference = create_memory_item(
            db,
            MemoryItemInput(
                workspace_id=workspace.id,
                scope="user",
                memory_type="user_preference",
                source="user_explicit",
                title="Chinese replies",
                content_md="用户写中文时优先中文回复。",
                status="active",
                trust_level="user_confirmed",
                agent_roles=("orchestrator", "frontend"),
            ),
        )
        message = Message(
            session_id=session.id,
            sender_type="user",
            content_md="请用中文说明并更新 demo frontend",
        )
        task = Task(
            session_id=session.id,
            title="Update demo frontend copy",
            intent_type="frontend_change",
            assigned_agent_id=frontend.id,
            plan_json=(
                '{"targetId":"demo-frontend","originalRequest":"请用中文说明并更新 demo frontend"}'
            ),
        )
        db.add(message)
        db.add(task)
        db.commit()
        db.refresh(message)
        db.refresh(task)

        planner_input = build_llm_planner_input(db, message)
        task_run = create_task_run(db, task.id)
        context = build_session_context_pack(db, task)

        planner_context = planner_input["canonicalSharedContext"]
        planner_snapshot = planner_context["fields"]["memorySnapshot"]["value"][
            "memorySnapshotId"
        ]
        coding_snapshot = context["memorySnapshot"]["memorySnapshotId"]
        task_run_snapshot = task_run.metrics_json

        planner_memory_ids = {
            item["id"]
            for item in planner_context["fields"]["relevantMemories"]["value"]
        }
        coding_memory_ids = {item["id"] for item in context["relevantMemories"]}

        assert preference.id in planner_memory_ids
        assert preference.id in coding_memory_ids
        assert planner_snapshot == coding_snapshot
        assert planner_snapshot in task_run_snapshot
        assert snapshot_consistency_rate([planner_snapshot, coding_snapshot]) == 1.0


@contextmanager
def _db() -> Iterator[DbSession]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as session:
        yield session


def _seed(db: DbSession) -> tuple[Workspace, Session, Agent]:
    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="Memory eval session",
        bound_branch="main",
        worktree_path=".worktrees/memory-eval-session",
    )
    frontend = Agent(
        name="Frontend Agent",
        role="frontend",
        adapter_type="codex",
        provider="local",
    )
    db.add(workspace)
    db.add(session)
    db.add(Agent(name="Orchestrator", role="orchestrator", adapter_type="scripted_mock", provider="local"))
    db.add(frontend)
    db.add(Agent(name="QA Agent", role="qa", adapter_type="scripted_mock", provider="local"))
    db.commit()
    db.refresh(workspace)
    db.refresh(session)
    db.refresh(frontend)
    return workspace, session, frontend
