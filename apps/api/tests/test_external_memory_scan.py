from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine

from app.external_memory_scan import (
    planned_external_memory_sources,
    scan_repo_external_memory,
)
from app.memory_store import (
    MemoryFilter,
    MemoryItemInput,
    create_memory_item,
    list_memory_items,
)
from app.models import Agent, Session, Workspace


def test_scan_repo_agents_and_claude_md_creates_pending_suggestions(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "AGENTS.md").write_text("Use concise Chinese replies.", encoding="utf-8")
    (repo / "CLAUDE.md").write_text("Refer to AGENTS.md.", encoding="utf-8")

    with _db() as db:
        workspace, session = _seed(db)
        result = scan_repo_external_memory(db, session=session, repo_root=repo)

        assert len(result.suggestions) == 2
        assert {item.status for item in result.suggestions} == {"pending_review"}
        assert {item.memory_type for item in result.suggestions} == {"external_suggestion"}
        assert {item.trust_level for item in result.suggestions} == {"external"}
        assert all(item.source == "external_memory" for item in result.suggestions)
        assert any(source["status"] == "planned" for source in result.planned_sources)

        active_items = list_memory_items(
            db,
            MemoryFilter(workspace_id=workspace.id, status="active"),
        )
        assert active_items == []


def test_external_memory_scan_detects_conflicts_without_auto_override(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "AGENTS.md").write_text("English only. 不要使用中文。", encoding="utf-8")

    with _db() as db:
        workspace, session = _seed(db)
        active = create_memory_item(
            db,
            MemoryItemInput(
                workspace_id=workspace.id,
                scope="user",
                memory_type="user_preference",
                source="user_explicit",
                title="Chinese preference",
                content_md="用户写中文时，优先使用中文回复。",
                status="active",
                trust_level="user_confirmed",
            ),
        )

        result = scan_repo_external_memory(db, session=session, repo_root=repo)

        assert len(result.suggestions) == 1
        assert result.suggestions[0].status == "pending_review"
        assert result.conflicts == (
            {
                "activeMemoryId": active.id,
                "suggestionMemoryId": result.suggestions[0].id,
                "reason": "external suggestion conflicts with active Chinese-language preference",
            },
        )
        db.refresh(active)
        assert active.status == "active"


def test_planned_external_memory_sources_include_claude_and_codex_future_scans() -> None:
    sources = planned_external_memory_sources()

    assert {
        "claude_code_local_auto_memory",
        "codex_global_or_repo_instructions",
    }.issubset({source["source"] for source in sources})
    assert all("pending_suggestion" in source["policy"] for source in sources)


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


def _seed(db: DbSession) -> tuple[Workspace, Session]:
    workspace = Workspace(
        name="AgentHub Demo",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title="External memory scan session",
        bound_branch="main",
        worktree_path=".worktrees/external-memory-scan-session",
    )
    db.add(workspace)
    db.add(session)
    db.add(Agent(name="Orchestrator", role="orchestrator", adapter_type="scripted_mock", provider="local"))
    db.commit()
    db.refresh(workspace)
    db.refresh(session)
    return workspace, session
