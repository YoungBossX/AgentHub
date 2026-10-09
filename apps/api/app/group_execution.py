"""Resume explicitly authorized group assignments through the existing queue."""

import asyncio
import json
import logging

from sqlmodel import Session as DbSession, select
from sqlalchemy import update

from app.models import Agent, Message, Session, Task, TaskRun
from app.repositories import create_session_message
from app.scheduler import evaluate_and_apply_scheduler_readiness
from app.target_registry import TargetRegistryError, get_target_for_workspace


logger = logging.getLogger(__name__)


def automatic_group_task(task: Task) -> bool:
    try:
        plan = json.loads(task.plan_json)
    except (TypeError, json.JSONDecodeError):
        return False
    if not isinstance(plan, dict):
        return False
    group = plan.get("groupAssignment")
    return (
        plan.get("planner") == "explicit_group_v1"
        and plan.get("autoStart") is True
        and isinstance(group, dict)
        and group.get("execution") == "automatic"
        and group.get("id") == task.created_by_message_id
        and task.intent_type in {"frontend_change", "backend_change", "review", "qa_review"}
    )


def enqueue_ready_group_tasks(db: DbSession, *, session_id: str | None = None) -> list[str]:
    from app.task_runs import TaskRunLifecycleError, create_task_run

    query = select(Task).order_by(Task.priority, Task.created_at, Task.id)
    if session_id is not None:
        query = query.where(Task.session_id == session_id)
    enqueued = []
    for task in db.exec(query).all():
        if task.status not in {"pending", "waiting_dependency", "waiting_target_lock", "blocked"} or not automatic_group_task(task):
            continue
        if db.exec(select(TaskRun).where(TaskRun.task_id == task.id)).first() is not None:
            continue
        decision = evaluate_and_apply_scheduler_readiness(db, task)
        if not decision.runnable:
            continue
        try:
            session = db.get(Session, task.session_id)
            if session is None:
                continue
            agent = db.get(Agent, task.assigned_agent_id)
            if agent is None or not agent.enabled:
                raise TaskRunLifecycleError("Selected group Agent is unavailable or disabled.")
            plan = json.loads(task.plan_json)
            target = get_target_for_workspace(db, session.workspace_id, plan.get("targetId"))
            if target.requires_approval or target.requires_platform_mode:
                raise TaskRunLifecycleError("Automatic groups cannot bypass target approval.")
            run = create_task_run(db, task.id, automatic_group=True)
        except (TaskRunLifecycleError, TargetRegistryError) as exc:
            db.rollback()
            db.refresh(task)
            # Another creator may have won while this worker was preparing.
            if automatic_group_task(task) and db.exec(select(TaskRun).where(TaskRun.task_id == task.id)).first() is None:
                _record_preparation_rejection(db, task, str(exc))
            continue
        enqueued.append(run.id)
    return enqueued


def _record_preparation_rejection(db: DbSession, task: Task, reason: str) -> None:
    # Keep only a bounded public diagnostic; provider credentials are not needed.
    from app.process_environment import redact_process_evidence

    db.execute(update(Session).where(Session.id == task.session_id).values(updated_at=Session.updated_at))
    db.refresh(task)
    if not automatic_group_task(task) or db.exec(select(TaskRun).where(TaskRun.task_id == task.id)).first() is not None:
        db.rollback()
        return
    reason = redact_process_evidence(reason)[:500]
    plan = json.loads(task.plan_json)
    plan["autoStart"] = False
    plan["groupExecutionError"] = {"code": "GROUP_PREPARATION_REJECTED", "reason": reason}
    task.plan_json = json.dumps(plan, separators=(",", ":"))
    task.status = "blocked"
    db.add(task)
    session = db.get(Session, task.session_id)
    coordinator = db.exec(select(Agent).where(Agent.role == "orchestrator")).first()
    if session is None or coordinator is None:
        db.commit()
        return
    diagnostic = Message(
        session_id=session.id, sender_type="orchestrator", sender_id=coordinator.id,
        parent_message_id=task.created_by_message_id,
        content_md=f"任务「{task.title}」自动启动被拒绝：{reason}。请修正配置后手动启动；后续依赖尚未执行。",
        context_json=json.dumps({"groupExecutionError": {"taskId": task.id, "code": "GROUP_PREPARATION_REJECTED"}}, separators=(",", ":")),
    )
    dependencies = json.loads(task.depends_on_task_ids)
    upstream = db.exec(
        select(TaskRun).join(Task, Task.id == TaskRun.task_id)
        .where(Task.session_id == task.session_id, TaskRun.task_id.in_(dependencies), TaskRun.state == "completed")
        .order_by(TaskRun.created_at.desc(), TaskRun.id.desc())
    ).first()
    event = None
    if upstream is not None:
        from app.events import stage_task_run_event

        event = stage_task_run_event(db, upstream.id, "group.task.preparation_rejected", json.dumps({"taskId": task.id, "messageId": diagnostic.id, "code": "GROUP_PREPARATION_REJECTED"}, separators=(",", ":")))
    create_session_message(db, session, diagnostic)
    if event is not None:
        from app.events import publish_task_run_event

        publish_task_run_event(db, event)


def has_pending_automatic_groups(db: DbSession) -> bool:
    for task in db.exec(select(Task).where(Task.status.notin_(["completed", "failed", "interrupted"]))).all():
        if automatic_group_task(task):
            return True
    return False


async def group_execution_loop() -> None:
    """Wake persisted automatic work; terminal attempts still require user retry."""
    from app.db import engine
    from app.run_engine import BoundedRunDispatcher

    while True:
        try:
            with DbSession(engine) as db:
                if has_pending_automatic_groups(db):
                    await BoundedRunDispatcher().run_until_idle(db)
                else:
                    from app.group_summaries import reconcile_group_summaries

                    await reconcile_group_summaries(db.get_bind())
        except asyncio.CancelledError:
            raise
        except Exception:
            # Keep the service available. A subsequent wake rechecks durable state.
            logger.error("Automatic group dispatcher wake failed; persisted work will be rechecked.")
        await asyncio.sleep(2)
