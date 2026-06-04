from collections.abc import Iterator

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine
from sqlmodel import select

from app.memory_snapshots import create_memory_snapshot
from app.memory_store import (
    MemoryFilter,
    MemoryItemInput,
    MemoryStoreError,
    create_memory_item,
    list_memory_items,
    memory_agent_roles,
    memory_collection_versions,
    memory_target_ids,
    supersede_memory_item,
    transition_memory_item,
)
from app.models import Workspace


@pytest.fixture
def db() -> Iterator[DbSession]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as session:
        workspace = Workspace(
            name="AgentHub Demo",
            repo_url="local://apps/demo",
            root_path="apps/demo",
            default_branch="main",
        )
        session.add(workspace)
        session.commit()
        session.refresh(workspace)
        yield session


def test_memory_item_schema_status_transition_and_scope_filters(
    db: DbSession,
) -> None:
    workspace = _workspace(db)
    item = create_memory_item(
        db,
        MemoryItemInput(
            workspace_id=workspace.id,
            scope="project",
            memory_type="project_rule",
            source="user",
            title="Prefer Chinese",
            content_md="用户使用中文时，面向用户的说明优先中文。",
            status="pending_review",
            trust_level="user_confirmed",
            target_ids=("demo-frontend",),
            agent_roles=("planner", "frontend"),
            importance=125,
        ),
    )

    assert item.status == "pending_review"
    assert item.importance == 100
    assert memory_target_ids(item) == ["demo-frontend"]
    assert memory_agent_roles(item) == ["planner", "frontend"]

    active = transition_memory_item(db, item.id, "active")
    assert active.status == "active"
    assert active.updated_at >= item.created_at

    scoped = list_memory_items(
        db,
        MemoryFilter(
            workspace_id=workspace.id,
            scope="project",
            status="active",
            target_id="demo-frontend",
            agent_role="frontend",
        ),
    )
    assert [memory.id for memory in scoped] == [item.id]

    assert list_memory_items(
        db,
        MemoryFilter(workspace_id=workspace.id, target_id="demo-backend"),
    ) == []


def test_memory_item_rejects_invalid_schema_values(db: DbSession) -> None:
    workspace = _workspace(db)

    with pytest.raises(MemoryStoreError, match="Unsupported memory status"):
        create_memory_item(
            db,
            MemoryItemInput(
                workspace_id=workspace.id,
                scope="project",
                memory_type="project_rule",
                source="user",
                title="Bad status",
                content_md="bad",
                status="trusted_forever",
            ),
        )

    with pytest.raises(MemoryStoreError, match="Unsupported memory type"):
        create_memory_item(
            db,
            MemoryItemInput(
                workspace_id=workspace.id,
                scope="project",
                memory_type="secret_override",
                source="tool_output",
                title="Bad type",
                content_md="bad",
            ),
        )


def test_supersession_archives_old_memory_with_superseded_by(
    db: DbSession,
) -> None:
    workspace = _workspace(db)
    original = create_memory_item(
        db,
        MemoryItemInput(
            workspace_id=workspace.id,
            scope="user",
            memory_type="user_preference",
            source="user",
            title="Tone",
            content_md="Keep answers concise.",
            status="active",
            trust_level="user_confirmed",
        ),
    )

    archived, replacement = supersede_memory_item(
        db,
        original.id,
        MemoryItemInput(
            workspace_id=workspace.id,
            scope="user",
            memory_type="user_preference",
            source="user",
            title="Tone",
            content_md="Keep answers concise and include validation results.",
            status="active",
            trust_level="user_confirmed",
        ),
    )

    assert archived.status == "archived"
    assert archived.superseded_by == replacement.id
    assert replacement.version == 1
    assert archived.content_hash != replacement.content_hash


def test_memory_versions_reflect_active_project_and_preference_items(
    db: DbSession,
) -> None:
    workspace = _workspace(db)
    before = memory_collection_versions(db, workspace.id)
    first_snapshot = create_memory_snapshot(
        db,
        workspace_id=workspace.id,
        reason="test_before_memory",
    )

    create_memory_item(
        db,
        MemoryItemInput(
            workspace_id=workspace.id,
            scope="project",
            memory_type="project_rule",
            source="user",
            title="Validation",
            content_md="Always record validation evidence.",
            status="active",
            trust_level="user_confirmed",
        ),
    )
    create_memory_item(
        db,
        MemoryItemInput(
            workspace_id=workspace.id,
            scope="user",
            memory_type="user_preference",
            source="user",
            title="Language",
            content_md="Reply in Chinese when the user writes Chinese.",
            status="active",
            trust_level="user_confirmed",
        ),
    )

    after = memory_collection_versions(db, workspace.id)
    second_snapshot = create_memory_snapshot(
        db,
        workspace_id=workspace.id,
        reason="test_after_memory",
    )

    assert before.project_memory_version != after.project_memory_version
    assert before.user_preference_version != after.user_preference_version
    assert first_snapshot.project_memory_version == before.project_memory_version
    assert second_snapshot.project_memory_version == after.project_memory_version
    assert second_snapshot.user_preference_version == after.user_preference_version


def _workspace(db: DbSession) -> Workspace:
    return db.exec(select(Workspace)).one()
