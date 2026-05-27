import json
from typing import Any, Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.models import Agent, Artifact, Diff, Task, TaskRun, utc_now
from app.provider_assignments import resolve_profile_provider_assignment
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
        "fromProviderId": _provider_id_for_run(db, from_task_run),
        "fromAdapterType": _adapter_type_for_run(from_task_run),
        "toTaskId": to_task.id,
        "toAgentRole": _agent_role_for_task(db, to_task),
        "toProviderId": _provider_id_for_task(db, to_task),
        "toAdapterType": _adapter_type_for_task(db, to_task),
        "summary": summary or _default_summary(from_task, to_task),
        "changedFiles": _changed_files_from_run_or_task(db, from_task_run, from_task),
        "implementedRoutes": _implemented_routes_from_task(from_task),
        "implementedComponents": _implemented_components_from_files(
            _changed_files_from_run_or_task(db, from_task_run, from_task)
        ),
        "artifactRefs": _artifact_refs_for_run(db, from_task_run.id),
        "openQuestions": open_questions or [],
        "warnings": _warnings_from_run(db, from_task_run.id),
        "suggestedFollowUpScope": _suggested_changes_from_run(db, from_task_run.id),
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


def _provider_id_for_run(db: DbSession, task_run: TaskRun) -> Optional[str]:
    assignment = _provider_assignment_from_run(task_run)
    provider_id = assignment.get("providerId")
    if isinstance(provider_id, str) and provider_id:
        return provider_id
    agent = db.get(Agent, task_run.agent_id)
    return agent.provider if agent is not None else None


def _adapter_type_for_run(task_run: TaskRun) -> Optional[str]:
    metrics = _json_dict(task_run.metrics_json)
    adapter_type = metrics.get("adapterType")
    return adapter_type if isinstance(adapter_type, str) and adapter_type else None


def _provider_assignment_from_run(task_run: TaskRun) -> dict[str, Any]:
    metrics = _json_dict(task_run.metrics_json)
    assignment = metrics.get("providerAssignment")
    return assignment if isinstance(assignment, dict) else {}


def _provider_id_for_task(db: DbSession, task: Task) -> Optional[str]:
    assignment = _profile_assignment_for_task(db, task)
    return assignment.provider_id if assignment is not None else None


def _adapter_type_for_task(db: DbSession, task: Task) -> Optional[str]:
    assignment = _profile_assignment_for_task(db, task)
    return assignment.adapter_type if assignment is not None else None


def _profile_assignment_for_task(db: DbSession, task: Task):
    if task.assigned_agent_id is None:
        return None
    agent = db.get(Agent, task.assigned_agent_id)
    if agent is None:
        return None
    return resolve_profile_provider_assignment(agent.role, agent)


def _changed_files_from_run_or_task(
    db: DbSession,
    task_run: TaskRun,
    task: Task,
) -> list[str]:
    changed_files = _changed_files_from_diff_artifact(db, task_run.id)
    if changed_files:
        return changed_files
    return _changed_files_from_task_plan(task)


def _changed_files_from_diff_artifact(db: DbSession, task_run_id: str) -> list[str]:
    artifact = db.exec(
        select(Artifact)
        .where(Artifact.task_run_id == task_run_id)
        .where(Artifact.artifact_type == "diff")
        .order_by(Artifact.created_at.desc(), Artifact.id.desc())
    ).first()
    if artifact is None:
        return []
    diff = db.exec(select(Diff).where(Diff.artifact_id == artifact.id)).first()
    if diff is not None:
        return _json_list(diff.changed_files_json)
    meta = _json_dict(artifact.meta_json)
    changed_files = meta.get("changedFiles")
    return [path for path in changed_files if isinstance(path, str)] if isinstance(changed_files, list) else []


def _changed_files_from_task_plan(task: Task) -> list[str]:
    plan = _json_dict(task.plan_json)
    files = plan.get("files", [])
    if not isinstance(files, list):
        return []
    return [path for path in files if isinstance(path, str)]


def _implemented_routes_from_task(task: Task) -> list[str]:
    plan = _json_dict(task.plan_json)
    contract = plan.get("appContract")
    routes = contract.get("apiRoutes") if isinstance(contract, dict) else plan.get("apiRoutes")
    if not isinstance(routes, list):
        return []
    implemented: list[str] = []
    for route in routes:
        if isinstance(route, str):
            implemented.append(route)
        elif isinstance(route, dict):
            method = route.get("method")
            path = route.get("path")
            if isinstance(method, str) and isinstance(path, str):
                implemented.append(f"{method.upper()} {path}")
            elif isinstance(path, str):
                implemented.append(path)
    return implemented


def _implemented_components_from_files(changed_files: list[str]) -> list[str]:
    return [
        path
        for path in changed_files
        if path.endswith((".tsx", ".jsx", ".ts", ".js"))
        and ("/src/" in path or path.startswith("src/") or path.startswith("apps/demo/src"))
    ]


def _warnings_from_run(db: DbSession, task_run_id: str) -> list[str]:
    warnings: list[str] = []
    for artifact in _artifacts_for_run(db, task_run_id, artifact_type="review"):
        meta = _json_dict(artifact.meta_json)
        findings = meta.get("findings")
        if not isinstance(findings, list):
            continue
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            severity = str(finding.get("severity") or "").lower()
            message = finding.get("message")
            if severity in {"warning", "failed", "high", "medium"} and isinstance(message, str):
                warnings.append(message)
    return warnings


def _suggested_changes_from_run(db: DbSession, task_run_id: str) -> list[str]:
    suggestions: list[str] = []
    for artifact in _artifacts_for_run(db, task_run_id, artifact_type="review"):
        meta = _json_dict(artifact.meta_json)
        values = meta.get("suggestedChanges")
        if isinstance(values, list):
            suggestions.extend([value for value in values if isinstance(value, str)])
    return suggestions


def _artifact_refs_for_run(db: DbSession, task_run_id: str) -> list[dict[str, str]]:
    artifacts = _artifacts_for_run(db, task_run_id)
    return [
        {
            "artifactId": artifact.id,
            "artifactType": artifact.artifact_type,
            "status": artifact.status,
        }
        for artifact in artifacts
    ]


def _artifacts_for_run(
    db: DbSession,
    task_run_id: str,
    *,
    artifact_type: Optional[str] = None,
) -> list[Artifact]:
    query = (
        select(Artifact)
        .where(Artifact.task_run_id == task_run_id)
        .where(Artifact.artifact_type != HANDOFF_ARTIFACT_TYPE)
        .order_by(Artifact.created_at, Artifact.id)
    )
    if artifact_type is not None:
        query = query.where(Artifact.artifact_type == artifact_type)
    return db.exec(query).all()


def _default_summary(from_task: Task, to_task: Task) -> str:
    return f"{from_task.title} completed and handed context to {to_task.title}."


def _json_dict(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str)]
