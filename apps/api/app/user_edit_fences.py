"""Shared execution fence for persisted, unresolved user file operations."""

from sqlmodel import Session as DbSession, select

from app.models import Artifact, Task, TaskRun

USER_EDIT_TYPE = "user_code_edit"
UNRESOLVED_STATES = {"applying", "unresolved"}


def pending_user_edit(db: DbSession, session_id: str):
    return db.exec(select(Artifact).join(TaskRun, Artifact.task_run_id == TaskRun.id)
                   .join(Task, TaskRun.task_id == Task.id).where(
                       Task.session_id == session_id, Artifact.artifact_type == USER_EDIT_TYPE,
                       Artifact.status.in_(UNRESOLVED_STATES))).first()


def user_revision_after_run(db: DbSession, run: TaskRun):
    task = db.get(Task, run.task_id)
    if task is None:
        return None
    return db.exec(select(Artifact).join(TaskRun, Artifact.task_run_id == TaskRun.id)
                   .join(Task, TaskRun.task_id == Task.id).where(
                       Task.session_id == task.session_id, Artifact.artifact_type == USER_EDIT_TYPE,
                       Artifact.status.in_({"applied", "resolved", "applying", "unresolved"}),
                       Artifact.updated_at > run.created_at)
                   .order_by(Artifact.updated_at.desc(), Artifact.id.desc())).first()


def latest_session_user_revision(db: DbSession, session_id: str):
    return db.exec(select(Artifact).join(TaskRun, Artifact.task_run_id == TaskRun.id)
                   .join(Task, TaskRun.task_id == Task.id).where(
                       Task.session_id == session_id, Artifact.artifact_type == USER_EDIT_TYPE,
                       Artifact.status.in_({"applied", "resolved"}))
                   .order_by(Artifact.updated_at.desc(), Artifact.id.desc())).first()
