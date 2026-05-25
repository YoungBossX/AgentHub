import json
from typing import Any, Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.models import Agent, Artifact, Task, TaskRun, utc_now
from app.scheduler import dependency_ids_for_task

HANDOFF_ARTIFACT_TYPE = "handoff"


def create_dependency_handoffs(db: DbSession, from_task_run: TaskRun) -> list[Artifact]:
    from_task = db.get(Task, from_task_run.task_id)
    if from_task is None:
        return []

    downstream_tasks = db.exec(
        select(Task)
        .where(Task.session_id == from_task.session_id)
        .order_by(Task.priority, Task.created_at, Task.id)
    ).all()
    handoffs: list[Artifact] = []
    for to_task in downstream_tasks:
        if from_task.id not in dependency_ids_for_task(to_task):
            continue
        handoffs.append(
            create_handoff_artifact(
                db,
                from_task=from_task,
                from_task_run=from_task_run,
                to_task=to_task,
            )
        )
    return handoffs


def create_handoff_artifact(
    db: DbSession,
    *,
    from_task: Task,
    from_task_run: TaskRun,
    to_task: Task,
    summary: Optional[str] = None,
    open_questions: Optional[list[str]] = None,
    risk_notes: Optional[list[str]] = None,
) -> Artifact:
    now = utc_now()
    meta = {
        "fromTaskId": from_task.id,
        "fromTaskRunId": from_task_run.id,
        "fromAgentRole": _agent_role_for_task(db, from_task),
        "toTaskId": to_task.id,
        "toAgentRole": _agent_role_for_task(db, to_task),
        "summary": summary or _default_summary(from_task, to_task),
        "changedFiles": _changed_files_from_task_plan(from_task),
        "artifactRefs": _artifact_refs_for_run(db, from_task_run.id),
        "openQuestions": open_questions or [],
        "verificationStatus": "completed",
        "riskNotes": risk_notes or [],
        "createdAt": now.isoformat(),
    }
    artifact = Artifact(
        task_run_id=from_task_run.id,
        artifact_type=HANDOFF_ARTIFACT_TYPE,
        title=f"Handoff to {to_task.title}",
        status="ready",
        meta_json=json.dumps(meta, separators=(",", ":")),
        created_at=now,
        updated_at=now,
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact


def handoff_context_for_task(db: DbSession, task: Task) -> list[dict[str, Any]]:
    dependency_ids = set(dependency_ids_for_task(task))
    if not dependency_ids:
        return []
    task_runs = db.exec(
        select(TaskRun)
        .where(TaskRun.task_id.in_(dependency_ids))
        .order_by(TaskRun.created_at, TaskRun.id)
    ).all()
    run_ids = [task_run.id for task_run in task_runs]
    if not run_ids:
        return []
    artifacts = db.exec(
        select(Artifact)
        .where(Artifact.task_run_id.in_(run_ids))
        .where(Artifact.artifact_type == HANDOFF_ARTIFACT_TYPE)
        .order_by(Artifact.created_at, Artifact.id)
    ).all()
    contexts: list[dict[str, Any]] = []
    for artifact in artifacts:
        meta = _json_dict(artifact.meta_json)
        if meta.get("toTaskId") != task.id:
            continue
        contexts.append(
            {
                "artifactId": artifact.id,
                "status": artifact.status,
                **meta,
            }
        )
    return contexts


def _agent_role_for_task(db: DbSession, task: Task) -> Optional[str]:
    if task.assigned_agent_id is None:
        return None
    agent = db.get(Agent, task.assigned_agent_id)
    return agent.role if agent is not None else None


def _changed_files_from_task_plan(task: Task) -> list[str]:
    plan = _json_dict(task.plan_json)
    files = plan.get("files", [])
    if not isinstance(files, list):
        return []
    return [path for path in files if isinstance(path, str)]


def _artifact_refs_for_run(db: DbSession, task_run_id: str) -> list[dict[str, str]]:
    artifacts = db.exec(
        select(Artifact)
        .where(Artifact.task_run_id == task_run_id)
        .where(Artifact.artifact_type != HANDOFF_ARTIFACT_TYPE)
        .order_by(Artifact.created_at, Artifact.id)
    ).all()
    return [
        {
            "artifactId": artifact.id,
            "artifactType": artifact.artifact_type,
            "status": artifact.status,
        }
        for artifact in artifacts
    ]


def _default_summary(from_task: Task, to_task: Task) -> str:
    return f"{from_task.title} completed and handed context to {to_task.title}."


def _json_dict(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
