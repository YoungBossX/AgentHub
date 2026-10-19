from typing import Iterator

from sqlmodel import Session as DbSession
from sqlalchemy.exc import OperationalError

from app.db import engine
from app.events import raise_event_write_conflict
from app.deployments import DeployService
from app.previews import PreviewService
from app.worktrees import WorktreeService


def get_db() -> Iterator[DbSession]:
    with DbSession(engine) as session:
        try:
            yield session
        except OperationalError as error:
            session.rollback()
            raise_event_write_conflict(error)


def get_worktree_service() -> WorktreeService:
    return WorktreeService()


_preview_service = PreviewService()
_deploy_service = DeployService()


def get_preview_service() -> PreviewService:
    return _preview_service


def get_deploy_service() -> DeployService:
    return _deploy_service
