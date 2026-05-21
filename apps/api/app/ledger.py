import json
from typing import Any, Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.models import (
    Agent,
    Artifact,
    Deployment,
    Diff,
    Message,
    Preview,
    SessionExecutionLedger,
    Task,
    TaskRun,
    utc_now,
)


def get_or_create_session_ledger(
    db: DbSession,
    session_id: str,
) -> SessionExecutionLedger:
    ledger = db.exec(
        select(SessionExecutionLedger).where(
            SessionExecutionLedger.session_id == session_id
        )
    ).first()
    if ledger is not None:
        return ledger

    now = utc_now()
    ledger = SessionExecutionLedger(
        session_id=session_id,
        summary_md="No goal captured yet.",
        created_at=now,
        updated_at=now,
    )
    db.add(ledger)
    db.commit()
    db.refresh(ledger)
    return ledger


def refresh_session_ledger(
    db: DbSession,
    session_id: str,
) -> SessionExecutionLedger:
    ledger = get_or_create_session_ledger(db, session_id)
    tasks = db.exec(
        select(Task)
        .where(Task.session_id == session_id)
        .order_by(Task.priority, Task.created_at, Task.id)
    ).all()
    task_runs = _task_runs_for_tasks(db, tasks)
    latest_task = tasks[-1] if tasks else None
    latest_task_run = task_runs[-1] if task_runs else None
    latest_diff = _latest_diff_for_runs(db, task_runs)
    latest_preview = _latest_preview_for_runs(db, task_runs)
    latest_deployment = _latest_deployment_for_runs(db, task_runs)
    last_successful_run = next(
        (task_run for task_run in reversed(task_runs) if task_run.state == "completed"),
        None,
    )

    now = utc_now()
    ledger.current_goal = _latest_user_goal(db, session_id)
    ledger.active_agents_json = json.dumps(
        _active_agent_roles(db, tasks),
        separators=(",", ":"),
    )
    ledger.latest_task_id = latest_task.id if latest_task is not None else None
    ledger.latest_task_run_id = (
        latest_task_run.id if latest_task_run is not None else None
    )
    ledger.latest_diff_artifact_id = (
        latest_diff["artifact"].id if latest_diff is not None else None
    )
    ledger.latest_changed_files_json = json.dumps(
        latest_diff["changed_files"] if latest_diff is not None else [],
        separators=(",", ":"),
    )
    ledger.latest_preview_id = (
        latest_preview["preview"].id if latest_preview is not None else None
    )
    ledger.latest_preview_url = (
        latest_preview["preview"].url if latest_preview is not None else None
    )
    ledger.latest_preview_health = (
        latest_preview["preview"].health_status if latest_preview is not None else None
    )
    ledger.latest_deployment_id = (
        latest_deployment["deployment"].id if latest_deployment is not None else None
    )
    ledger.latest_deployment_provider = (
        latest_deployment["deployment"].provider if latest_deployment is not None else None
    )
    ledger.latest_deployment_status = (
        latest_deployment["deployment"].status if latest_deployment is not None else None
    )
    ledger.last_successful_adapter = (
        adapter_type_for_task_run(db, last_successful_run)
        if last_successful_run is not None
        else None
    )
    ledger.summary_md = _summary_md(ledger)
    ledger.updated_at = now
    db.add(ledger)
    db.commit()
    db.refresh(ledger)
    return ledger


def refresh_session_ledger_for_task_run(
    db: DbSession,
    task_run_id: str,
) -> Optional[SessionExecutionLedger]:
    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        return None
    task = db.get(Task, task_run.task_id)
    if task is None:
        return None
    return refresh_session_ledger(db, task.session_id)


def active_agents_for_ledger(ledger: SessionExecutionLedger) -> list[str]:
    return _json_list(ledger.active_agents_json)


def changed_files_for_ledger(ledger: SessionExecutionLedger) -> list[str]:
    return _json_list(ledger.latest_changed_files_json)


def adapter_type_for_task_run(db: DbSession, task_run: TaskRun) -> str:
    metrics = _json_dict(task_run.metrics_json)
    adapter_type = metrics.get("adapterType")
    if isinstance(adapter_type, str) and adapter_type:
        return adapter_type

    agent = db.get(Agent, task_run.agent_id)
    return agent.adapter_type if agent is not None else "unknown"


def _latest_user_goal(db: DbSession, session_id: str) -> Optional[str]:
    message = db.exec(
        select(Message)
        .where(Message.session_id == session_id)
        .where(Message.sender_type == "user")
        .order_by(Message.created_at.desc(), Message.id.desc())
    ).first()
    return message.content_md if message is not None else None


def _active_agent_roles(db: DbSession, tasks: list[Task]) -> list[str]:
    roles: list[str] = []
    for task in tasks:
        if task.assigned_agent_id is None:
            continue
        agent = db.get(Agent, task.assigned_agent_id)
        if agent is not None and agent.role not in roles:
            roles.append(agent.role)
    return roles


def _task_runs_for_tasks(db: DbSession, tasks: list[Task]) -> list[TaskRun]:
    task_ids = [task.id for task in tasks]
    if not task_ids:
        return []
    return db.exec(
        select(TaskRun)
        .where(TaskRun.task_id.in_(task_ids))
        .order_by(TaskRun.created_at, TaskRun.id)
    ).all()


def _latest_diff_for_runs(
    db: DbSession,
    task_runs: list[TaskRun],
) -> Optional[dict[str, Any]]:
    run_ids = [task_run.id for task_run in task_runs]
    if not run_ids:
        return None
    artifact = db.exec(
        select(Artifact)
        .where(Artifact.task_run_id.in_(run_ids))
        .where(Artifact.artifact_type == "diff")
        .order_by(Artifact.created_at.desc(), Artifact.id.desc())
    ).first()
    if artifact is None:
        return None
    diff = db.exec(select(Diff).where(Diff.artifact_id == artifact.id)).first()
    return {
        "artifact": artifact,
        "diff": diff,
        "changed_files": _json_list(diff.changed_files_json) if diff is not None else [],
    }


def _latest_preview_for_runs(
    db: DbSession,
    task_runs: list[TaskRun],
) -> Optional[dict[str, Any]]:
    run_ids = [task_run.id for task_run in task_runs]
    if not run_ids:
        return None
    artifact = db.exec(
        select(Artifact)
        .where(Artifact.task_run_id.in_(run_ids))
        .where(Artifact.artifact_type == "preview")
        .order_by(Artifact.created_at.desc(), Artifact.id.desc())
    ).first()
    if artifact is None:
        return None
    preview = db.exec(select(Preview).where(Preview.artifact_id == artifact.id)).first()
    if preview is None:
        return None
    return {"artifact": artifact, "preview": preview}


def _latest_deployment_for_runs(
    db: DbSession,
    task_runs: list[TaskRun],
) -> Optional[dict[str, Any]]:
    run_ids = [task_run.id for task_run in task_runs]
    if not run_ids:
        return None
    artifact = db.exec(
        select(Artifact)
        .where(Artifact.task_run_id.in_(run_ids))
        .where(Artifact.artifact_type == "deployment")
        .order_by(Artifact.created_at.desc(), Artifact.id.desc())
    ).first()
    if artifact is None:
        return None
    deployment = db.exec(
        select(Deployment).where(Deployment.artifact_id == artifact.id)
    ).first()
    if deployment is None:
        return None
    return {"artifact": artifact, "deployment": deployment}


def _summary_md(ledger: SessionExecutionLedger) -> str:
    lines = []
    if ledger.current_goal:
        lines.append(f"Current goal: {ledger.current_goal}")
    active_agents = active_agents_for_ledger(ledger)
    if active_agents:
        lines.append(f"Active agents: {', '.join('@' + role for role in active_agents)}")
    if ledger.latest_changed_files_json != "[]":
        changed_files = changed_files_for_ledger(ledger)
        if changed_files:
            lines.append(f"Changed files: {', '.join(changed_files)}")
    if ledger.latest_preview_url:
        lines.append(
            f"Preview: {ledger.latest_preview_url} ({ledger.latest_preview_health})"
        )
    if ledger.latest_deployment_id:
        lines.append(
            "Deployment: "
            f"{ledger.latest_deployment_provider} ({ledger.latest_deployment_status})"
        )
    if ledger.last_successful_adapter:
        lines.append(f"Last successful adapter: {ledger.last_successful_adapter}")
    return "\n".join(lines) if lines else "No goal captured yet."


def _json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str)]


def _json_dict(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
