from typing import Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.models import Agent, Message, Session, Task, Workspace
from app.models import utc_now


def get_demo_workspace(db: DbSession) -> Workspace:
    return db.exec(select(Workspace).where(Workspace.name == "AgentHub Demo")).one()


def get_enabled_agents(db: DbSession) -> list[Agent]:
    return db.exec(  # noqa: E712
        select(Agent).where(Agent.enabled == True).order_by(Agent.role)
    ).all()


def get_workspace(db: DbSession, workspace_id: str) -> Optional[Workspace]:
    return db.get(Workspace, workspace_id)


def list_workspace_sessions(db: DbSession, workspace_id: str, *, view: str = "all") -> list[Session]:
    query = select(Session).where(Session.workspace_id == workspace_id)
    if view == "active":
        query = query.where(Session.archived_at.is_(None))
    elif view == "archived":
        query = query.where(Session.archived_at.is_not(None))
    elif view != "all":
        raise ValueError("Invalid session list view.")
    return db.exec(query.order_by(Session.archived_at.is_not(None), Session.pinned_at.desc(), Session.last_message_at.desc(), Session.created_at.desc(), Session.id)).all()


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


def list_session_messages(db: DbSession, session_id: str) -> list[Message]:
    return db.exec(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at, Message.id)
    ).all()


def create_session_message(
    db: DbSession,
    session: Session,
    message: Message,
) -> Message:
    message.created_at = utc_now()
    session.last_message_at = message.created_at
    session.updated_at = message.created_at
    db.add(message)
    db.add(session)
    db.commit()
    db.refresh(message)
    return message


def list_session_tasks(db: DbSession, session_id: str) -> list[Task]:
    return db.exec(
        select(Task)
        .where(Task.session_id == session_id)
        .order_by(Task.priority, Task.created_at, Task.id)
    ).all()
