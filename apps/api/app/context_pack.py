import json
from typing import Any, Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.ledger import (
    active_agents_for_ledger,
    changed_files_for_ledger,
    refresh_session_ledger,
)
from app.models import (
    Artifact,
    Deployment,
    Diff,
    Message,
    Preview,
    Review,
    Task,
    TaskRun,
)
from app.models import Session as AgentHubSession

RECENT_MESSAGE_LIMIT = 8
RECENT_MESSAGE_CHAR_LIMIT = 700


def build_session_context_pack(
    db: DbSession,
    task: Task,
    *,
    plan_context: Optional[dict[str, Any]] = None,
    recent_message_limit: int = RECENT_MESSAGE_LIMIT,
) -> dict[str, Any]:
    plan = _json_dict(task.plan_json)
    merged_context = dict(plan)
    if plan_context:
        merged_context.update(plan_context)

    session = db.get(AgentHubSession, task.session_id)
    ledger = refresh_session_ledger(db, task.session_id)
    task_runs = _task_runs_for_session(db, task.session_id)
    latest_diff = _latest_diff_context(db, task_runs)
    latest_review = _latest_review_context(db, task_runs)
    latest_preview = _latest_preview_context(db, task_runs)
    latest_deployment = _latest_deployment_context(db, task_runs)
    original_request = _original_request_for_task(db, task, merged_context)
    selected_artifact = _selected_artifact_context(db, task.session_id, merged_context)
    app_contract = _app_contract_context(merged_context)

    return {
        "version": "session_context_pack_v1",
        "sessionId": task.session_id,
        "workspaceId": session.workspace_id if session is not None else None,
        "currentGoal": ledger.current_goal,
        "originalUserRequest": original_request,
        "currentTask": {
            "id": task.id,
            "title": task.title,
            "intentType": task.intent_type,
            "description": _task_description(task, merged_context),
            "plan": merged_context,
        },
        "recentMessages": _recent_messages(db, task.session_id, recent_message_limit),
        "ledger": {
            "summaryMd": ledger.summary_md,
            "activeAgents": active_agents_for_ledger(ledger),
            "latestTaskId": ledger.latest_task_id,
            "latestTaskRunId": ledger.latest_task_run_id,
            "latestDiffArtifactId": ledger.latest_diff_artifact_id,
            "latestChangedFiles": changed_files_for_ledger(ledger),
            "latestPreviewId": ledger.latest_preview_id,
            "latestPreviewUrl": ledger.latest_preview_url,
            "latestPreviewHealth": ledger.latest_preview_health,
            "latestDeploymentId": ledger.latest_deployment_id,
            "latestDeploymentProvider": ledger.latest_deployment_provider,
            "latestDeploymentStatus": ledger.latest_deployment_status,
            "lastSuccessfulAdapter": ledger.last_successful_adapter,
        },
        "latestChangedFiles": changed_files_for_ledger(ledger),
        "latestDiff": latest_diff,
        "latestReview": latest_review,
        "latestPreview": latest_preview,
        "latestDeployment": latest_deployment,
        "selectedArtifact": selected_artifact,
        "appContract": app_contract,
        "safeTargetPaths": _safe_target_paths(task, merged_context),
        "validationExpectations": _validation_expectations(task, merged_context),
    }


def _recent_messages(
    db: DbSession,
    session_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    messages = db.exec(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": message.id,
            "senderType": message.sender_type,
            "senderId": message.sender_id,
            "messageKind": message.message_kind,
            "contentMd": _truncate(message.content_md, RECENT_MESSAGE_CHAR_LIMIT),
            "createdAt": message.created_at.isoformat(),
        }
        for message in reversed(messages)
    ]


def _task_runs_for_session(db: DbSession, session_id: str) -> list[TaskRun]:
    tasks = db.exec(
        select(Task)
        .where(Task.session_id == session_id)
        .order_by(Task.created_at, Task.id)
    ).all()
    task_ids = [task.id for task in tasks]
    if not task_ids:
        return []
    return db.exec(
        select(TaskRun)
        .where(TaskRun.task_id.in_(task_ids))
        .order_by(TaskRun.created_at, TaskRun.id)
    ).all()


def _latest_diff_context(
    db: DbSession,
    task_runs: list[TaskRun],
) -> Optional[dict[str, Any]]:
    artifact = _latest_artifact(db, task_runs, "diff")
    if artifact is None:
        return None
    diff = db.exec(select(Diff).where(Diff.artifact_id == artifact.id)).first()
    meta = _json_dict(artifact.meta_json)
    return {
        "artifactId": artifact.id,
        "taskRunId": artifact.task_run_id,
        "status": artifact.status,
        "baseRef": diff.base_ref if diff is not None else meta.get("baseRef"),
        "headRef": diff.head_ref if diff is not None else meta.get("headRef"),
        "changedFiles": (
            _json_list(diff.changed_files_json)
            if diff is not None
            else _json_list(json.dumps(meta.get("changedFiles", [])))
        ),
        "stats": diff_stats(diff) if diff is not None else meta.get("stats", {}),
    }


def _latest_review_context(
    db: DbSession,
    task_runs: list[TaskRun],
) -> Optional[dict[str, Any]]:
    artifact = _latest_artifact(db, task_runs, "review")
    if artifact is None:
        return None
    review = db.exec(select(Review).where(Review.artifact_id == artifact.id)).first()
    if review is None:
        return None
    return {
        "artifactId": artifact.id,
        "taskRunId": artifact.task_run_id,
        "status": review.status,
        "riskLevel": review.risk_level,
        "summary": review.summary,
        "filesReviewed": _json_list(review.files_reviewed_json),
        "findings": _json_value(review.findings_json, []),
        "suggestedChanges": _json_value(review.suggested_changes_json, []),
        "adapterType": review.adapter_type,
        "reviewedDiffArtifactId": review.reviewed_diff_artifact_id,
    }


def _latest_preview_context(
    db: DbSession,
    task_runs: list[TaskRun],
) -> Optional[dict[str, Any]]:
    artifact = _latest_artifact(db, task_runs, "preview")
    if artifact is None:
        return None
    preview = db.exec(select(Preview).where(Preview.artifact_id == artifact.id)).first()
    if preview is None:
        return None
    return {
        "artifactId": artifact.id,
        "taskRunId": artifact.task_run_id,
        "previewId": preview.id,
        "status": artifact.status,
        "url": preview.url,
        "healthStatus": preview.health_status,
        "port": preview.port,
    }


def _latest_deployment_context(
    db: DbSession,
    task_runs: list[TaskRun],
) -> Optional[dict[str, Any]]:
    artifact = _latest_artifact(db, task_runs, "deployment")
    if artifact is None:
        return None
    deployment = db.exec(
        select(Deployment).where(Deployment.artifact_id == artifact.id)
    ).first()
    if deployment is None:
        return None
    return {
        "artifactId": artifact.id,
        "taskRunId": artifact.task_run_id,
        "deploymentId": deployment.id,
        "status": deployment.status,
        "provider": deployment.provider,
        "environment": deployment.environment,
        "url": deployment.url,
    }


def _latest_artifact(
    db: DbSession,
    task_runs: list[TaskRun],
    artifact_type: str,
) -> Optional[Artifact]:
    run_ids = [task_run.id for task_run in task_runs]
    if not run_ids:
        return None
    return db.exec(
        select(Artifact)
        .where(Artifact.task_run_id.in_(run_ids))
        .where(Artifact.artifact_type == artifact_type)
        .order_by(Artifact.created_at.desc(), Artifact.id.desc())
    ).first()


def _selected_artifact_context(
    db: DbSession,
    session_id: str,
    context: dict[str, Any],
) -> Optional[dict[str, Any]]:
    artifact_id = _selected_artifact_id(context)
    if artifact_id is None:
        return None

    artifact = db.get(Artifact, artifact_id)
    if artifact is None:
        return {
            "artifactId": artifact_id,
            "valid": False,
            "reason": "Selected artifact was not found.",
        }
    task_run = db.get(TaskRun, artifact.task_run_id)
    task = db.get(Task, task_run.task_id) if task_run is not None else None
    if task is None or task.session_id != session_id:
        return {
            "artifactId": artifact_id,
            "valid": False,
            "reason": "Selected artifact does not belong to this session.",
        }
    return {
        "artifactId": artifact.id,
        "artifactType": artifact.artifact_type,
        "taskRunId": artifact.task_run_id,
        "title": artifact.title,
        "status": artifact.status,
        "valid": True,
        "meta": _json_dict(artifact.meta_json),
    }


def _selected_artifact_id(context: dict[str, Any]) -> Optional[str]:
    value = context.get("selectedArtifactId")
    if isinstance(value, str) and value:
        return value
    selected = context.get("selectedArtifact")
    if isinstance(selected, dict):
        nested = selected.get("artifactId") or selected.get("id")
        if isinstance(nested, str) and nested:
            return nested
    return None


def _app_contract_context(context: dict[str, Any]) -> Optional[dict[str, Any]]:
    contract = context.get("appContract")
    if isinstance(contract, dict):
        return contract
    return None


def _original_request_for_task(
    db: DbSession,
    task: Task,
    context: dict[str, Any],
) -> str:
    original = context.get("originalRequest") or context.get("goal")
    if isinstance(original, str) and original.strip():
        return original.strip()
    if task.created_by_message_id:
        message = db.get(Message, task.created_by_message_id)
        if message is not None:
            return message.content_md
    return task.title


def _task_description(task: Task, context: dict[str, Any]) -> str:
    summary = context.get("summary") or context.get("target")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    return task.title


def _safe_target_paths(task: Task, context: dict[str, Any]) -> list[str]:
    safe_target = context.get("safeTarget")
    paths: list[str] = []
    if isinstance(safe_target, str) and safe_target:
        paths.append(safe_target)
    files = context.get("files")
    if isinstance(files, list):
        paths.extend(path for path in files if isinstance(path, str))
    if task.intent_type == "backend_change" and "apps/demo-api" not in paths:
        paths.append("apps/demo-api")
    if task.intent_type in {"review", "qa_review"}:
        paths.append("read-only current session artifacts")
    return _dedupe(paths)


def _validation_expectations(task: Task, context: dict[str, Any]) -> list[str]:
    expectations = ["Keep the existing P4/P5 diff, review, preview, and mock deploy flow intact."]
    if isinstance(context.get("appContract"), dict):
        expectations.append("Use the shared app contract for backend, frontend, and review decisions.")
    expected_artifacts = context.get("expectedArtifactTypes")
    if isinstance(expected_artifacts, list) and "diff" in expected_artifacts:
        expectations.append("Produce a focused git diff in the assigned safe target.")
    if task.intent_type == "frontend_change":
        expectations.append("The Vite React demo preview should remain startable.")
    if task.intent_type == "backend_change":
        expectations.append("Do not modify AgentHub platform backend code under apps/api.")
    if task.intent_type in {"review", "qa_review"}:
        expectations.append("Review is advisory and read-oriented by default.")
    return expectations


def diff_stats(diff: Diff) -> dict[str, Any]:
    value = _json_value(diff.stats_json, {})
    return value if isinstance(value, dict) else {}


def _json_value(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _json_dict(value: str) -> dict[str, Any]:
    parsed = _json_value(value, {})
    return parsed if isinstance(parsed, dict) else {}


def _json_list(value: str) -> list[str]:
    parsed = _json_value(value, [])
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str)]


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1].rstrip()}..."


def _dedupe(paths: list[str]) -> list[str]:
    result: list[str] = []
    for path in paths:
        if path not in result:
            result.append(path)
    return result
