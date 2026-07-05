from typing import Iterator

from sqlmodel import Session as DbSession

from app.db import engine
from app.deployments import DeployService
from app.previews import PreviewService
from app.worktrees import WorktreeService


def get_db() -> Iterator[DbSession]:
    with DbSession(engine) as session:
        yield session


def get_worktree_service() -> WorktreeService:
    return WorktreeService()


_preview_service = PreviewService()
_deploy_service = DeployService()


def get_preview_service() -> PreviewService:
    return _preview_service


def get_deploy_service() -> DeployService:
    return _deploy_service
