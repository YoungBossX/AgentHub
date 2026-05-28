import json
from collections.abc import Iterator

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.models import Agent, Session, Task, Workspace
from app.target_registry import DEMO_BACKEND_TARGET_ID, DEMO_FRONTEND_TARGET_ID
from app.task_runs import TaskRunLifecycleError, create_task_run


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
        agent_session = Session(
            workspace_id=workspace.id,
            title="Selection policy session",
            bound_branch="main",
            worktree_path=".worktrees/selection-policy-session",
        )
        agents = [
            Agent(name="Frontend Agent", role="frontend", adapter_type="codex", provider="local"),
            Agent(name="Backend Agent", role="backend", adapter_type="codex", provider="local"),
            Agent(name="QA Agent", role="qa", adapter_type="scripted_mock", provider="local"),
        ]
        session.add(workspace)
        session.add(agent_session)
        for agent in agents:
            session.add(agent)
        session.commit()
        yield session


def test_agent_selection_records_role_target_capability_and_safety(db: DbSession) -> None:
    task = _task_for_role(
        db,
        role="frontend",
        intent_type="frontend_change",
        plan={
            "targetId": DEMO_FRONTEND_TARGET_ID,
            "safeTarget": "apps/demo/src",
            "requiredCapabilities": ["code_write"],
        },
    )

    task_run = create_task_run(db, task.id)

    metrics = json.loads(task_run.metrics_json)
    assert metrics["agentSelection"] == {
        "role": "frontend",
        "targetId": DEMO_FRONTEND_TARGET_ID,
        "requiredMode": "frontend",
        "requiredCapabilities": ["code_write"],
        "safeForWrite": True,
        "safeForReview": False,
    }


def test_agent_selection_rejects_unsupported_target(db: DbSession) -> None:
    task = _task_for_role(
        db,
        role="frontend",
        intent_type="frontend_change",
        plan={
            "targetId": DEMO_BACKEND_TARGET_ID,
            "safeTarget": "apps/demo-api",
            "requiredCapabilities": ["code_write"],
        },
    )

    with pytest.raises(TaskRunLifecycleError, match="does not support target"):
        create_task_run(db, task.id)


def test_agent_selection_rejects_missing_capability(db: DbSession) -> None:
    task = _task_for_role(
        db,
        role="frontend",
        intent_type="frontend_change",
        plan={
            "targetId": DEMO_FRONTEND_TARGET_ID,
            "safeTarget": "apps/demo/src",
            "requiredCapabilities": ["deploy_staging"],
        },
    )

    with pytest.raises(TaskRunLifecycleError, match="missing required capability"):
        create_task_run(db, task.id)


def test_agent_selection_rejects_review_work_for_write_only_profile(db: DbSession) -> None:
    task = _task_for_role(
        db,
        role="frontend",
        intent_type="review",
        plan={
            "targetId": DEMO_FRONTEND_TARGET_ID,
            "readOnly": True,
            "requiredCapabilities": ["code_review"],
        },
    )

    with pytest.raises(TaskRunLifecycleError, match="not safe for review"):
        create_task_run(db, task.id)


def _task_for_role(
    db: DbSession,
    *,
    role: str,
    intent_type: str,
    plan: dict,
) -> Task:
    agent = db.exec(select(Agent).where(Agent.role == role)).one()
    session = db.exec(select(Session).where(Session.title == "Selection policy session")).one()
    task = Task(
        session_id=session.id,
        title=f"{role} selection policy task",
        intent_type=intent_type,
        status="pending",
        assigned_agent_id=agent.id,
        plan_json=json.dumps(plan, separators=(",", ":")),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task
