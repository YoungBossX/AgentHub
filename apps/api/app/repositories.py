from typing import Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.models import Agent, Session, Workspace
from app.models import utc_now


def get_demo_workspace(db: DbSession) -> Workspace:
    return db.exec(select(Workspace).where(Workspace.name == "AgentHub Demo")).one()


def get_enabled_agents(db: DbSession) -> list[Agent]:
    return db.exec(select(Agent).where(Agent.enabled == True)).all()  # noqa: E712


def get_workspace(db: DbSession, workspace_id: str) -> Optional[Workspace]:
    return db.get(Workspace, workspace_id)


def list_workspace_sessions(db: DbSession, workspace_id: str) -> list[Session]:
    return db.exec(
        select(Session)
        .where(Session.workspace_id == workspace_id)
        .order_by(Session.last_message_at.desc(), Session.created_at.desc())
    ).all()


def get_session(db: DbSession, session_id: str) -> Optional[Session]:
    return db.get(Session, session_id)


def next_session_title(db: DbSession, workspace_id: str) -> str:
    count = len(list_workspace_sessions(db, workspace_id))
    return f"Session {count + 1}"


def persist_session(db: DbSession, session: Session) -> Session:
    session.updated_at = utc_now()
    db.add(session)
    db.commit()
    db.refresh(session)
    return session
