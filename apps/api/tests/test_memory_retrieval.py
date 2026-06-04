from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta

from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine

from app.context_pack import build_session_context_pack
from app.llm_planner import build_llm_planner_input
from app.memory_retrieval import (
    memory_precision_at_k,
    retrieve_relevant_memories,
)
from app.memory_store import MemoryItemInput, create_memory_item
from app.models import Agent, Message, Session, Task, Workspace, utc_now
from app.target_registry import DEMO_BACKEND_TARGET_ID, DEMO_FRONTEND_TARGET_ID


def test_memory_retrieval_precision_status_target_role_and_stale_filters() -> None:
    with _db() as db:
        workspace, session, frontend = _seed(db)
        relevant_a = create_memory_item(
            db,
            MemoryItemInput(
                workspace_id=workspace.id,
                scope="user",
                memory_type="user_preference",
                source="user_explicit",
                title="Chinese replies",
                content_md="用户写中文时，回复也使用中文，并先给结论。",
                status="active",
                trust_level="user_confirmed",
                agent_roles=("orchestrator", "frontend"),
                importance=90,
            ),
        )
        relevant_b = create_memory_item(
            db,
            MemoryItemInput(
                workspace_id=workspace.id,
                scope="project",
                memory_type="project_rule",
                source="user_explicit",
                title="Validation evidence",
                content_md="代码变更后记录验证命令和结果。",
                status="active",
                trust_level="user_confirmed",
                target_ids=(DEMO_FRONTEND_TARGET_ID,),
                agent_roles=("frontend",),
                importance=80,
            ),
        )
        create_memory_item(
            db,
            MemoryItemInput(
                workspace_id=workspace.id,
                scope="project",
                memory_type="project_rule",
                source="user_explicit",
                title="Backend only",
                content_md="后端接口变更后运行 demo-api tests。",
                status="active",
                trust_level="user_confirmed",
                target_ids=(DEMO_BACKEND_TARGET_ID,),
                agent_roles=("backend",),
            ),
        )
        create_memory_item(
            db,
            MemoryItemInput(
                workspace_id=workspace.id,
                scope="project",
                memory_type="pattern",
                source="build_failure",
                title="Archived stale issue",
                content_md="很旧的中文验证问题。",
                status="archived",
                trust_level="system",
            ),
        )
        stale = create_memory_item(
            db,
            MemoryItemInput(
                workspace_id=workspace.id,
                scope="project",
                memory_type="pattern",
                source="build_failure",
                title="Very old pattern",
                content_md="中文验证历史问题。",
                status="warm",
                trust_level="system",
            ),
        )
        stale.updated_at = utc_now() - timedelta(days=900)
        db.add(stale)
        db.commit()

        results = retrieve_relevant_memories(
            db,
            query="中文 回复 验证",
            workspace_id=workspace.id,
            target_id=DEMO_FRONTEND_TARGET_ID,
            agent_role="frontend",
            limit=5,
        )

        result_ids = [result.memory_item.id for result in results]
        assert relevant_a.id in result_ids
        assert relevant_b.id in result_ids
        assert stale.id not in result_ids
        assert memory_precision_at_k(results, {relevant_a.id, relevant_b.id}, k=5) >= 0.4

        task = Task(
            session_id=session.id,
            title="Update Chinese dashboard copy",
            intent_type="frontend_change",
            assigned_agent_id=frontend.id,
            plan_json=(
                '{"targetId":"demo-frontend","originalRequest":"中文 dashboard 验证"}'
            ),
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        context = build_session_context_pack(db, task)
        context_ids = {memory["id"] for memory in context["relevantMemories"]}
        assert relevant_a.id in context_ids
        assert relevant_b.id in context_ids


def test_planner_request_includes_relevant_memory_context() -> None:
    with _db() as db:
        workspace, session, _frontend = _seed(db)
        memory = create_memory_item(
            db,
            MemoryItemInput(
                workspace_id=workspace.id,
                scope="user",
                memory_type="user_preference",
                source="user_explicit",
                title="Chinese replies",
                content_md="用户写中文时优先用中文回复。",
                status="active",
                trust_level="user_confirmed",
                agent_roles=("orchestrator",),
            ),
        )
        message = Message(
            session_id=session.id,
            sender_type="user",
            content_md="请用中文告诉我你能做什么",
        )
        db.add(message)
        db.commit()
        db.refresh(message)

        planner_input = build_llm_planner_input(db, message)
        memories = planner_input["canonicalSharedContext"]["fields"]["relevantMemories"]["value"]

        assert [item["id"] for item in memories] == [memory.id]
        assert memories[0]["score"] > 0


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
        title="Memory retrieval session",
        bound_branch="main",
        worktree_path=".worktrees/memory-retrieval-session",
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
