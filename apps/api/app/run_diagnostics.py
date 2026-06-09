import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.models import Agent, Artifact, Deployment, Diff, Preview, Review, Task, TaskRun, TaskRunEvent
from app.schemas import (
    RunDiagnosticsArtifactReferenceResponse,
    RunDiagnosticsFailureResponse,
    RunDiagnosticsHealthSummaryResponse,
    RunDiagnosticsResponse,
    RunDiagnosticsSuggestionResponse,
    RunDiagnosticsSummaryResponse,
    RunDiagnosticsTimelineItemResponse,
    SessionRunDiagnosticsItemResponse,
    SessionRunDiagnosticsSummaryResponse,
)
from app.task_runs import adapter_type_for_run, metrics_for_run


FAILURE_CATEGORIES = {
    "provider_auth",
    "provider_quota",
    "provider_unavailable",
    "adapter_timeout",
    "adapter_interrupted",
    "adapter_error",
    "queue_stale",
    "queue_blocked",
    "lock_timeout",
    "worktree_dirty",
    "validation_failed",
    "approval_denied",
    "preview_failed",
    "deploy_failed",
    "deploy_blocked",
    "artifact_collection_failed",
    "unknown",
}

TIMELINE_PHASES = {
    "queued",
    "scheduler_check",
    "dependency_wait",
    "lock_wait",
    "approval_wait",
    "validation",
    "provider_check",
    "worker_claim",
    "adapter_start",
    "adapter_stream",
    "adapter_finish",
    "artifact_collection",
    "diff",
    "review",
    "preview",
    "deploy",
    "finalize",
    "recovery",
}

_CATEGORY_COPY: dict[str, tuple[str, str, bool]] = {
    "provider_auth": ("Provider credentials need attention.", "error", True),
    "provider_quota": ("Provider quota or rate limit stopped the run.", "warning", True),
    "provider_unavailable": ("The configured provider was unavailable.", "error", True),
    "adapter_timeout": ("The coding adapter timed out before finishing.", "error", True),
    "adapter_interrupted": ("The run was interrupted before completion.", "warning", True),
    "adapter_error": ("The coding adapter failed with an execution error.", "error", True),
    "queue_stale": ("The worker lease expired and stale recovery marked the run failed.", "error", True),
    "queue_blocked": ("The run is blocked by queue, dependency, scheduler, or approval state.", "warning", True),
    "lock_timeout": ("The target lock was not available before timeout.", "warning", True),
    "worktree_dirty": ("Dirty worktree state blocked safe execution or collection.", "warning", True),
    "validation_failed": ("Validation or policy checks rejected the run.", "error", False),
    "approval_denied": ("The required approval was denied or expired.", "warning", True),
    "preview_failed": ("Preview build, server, or health check failed.", "warning", True),
    "deploy_failed": ("Deployment evidence ended in a failed state.", "warning", True),
    "deploy_blocked": ("Deployment is blocked by unavailable configuration or manual handoff.", "warning", True),
    "artifact_collection_failed": ("Diff, review, or artifact collection failed.", "warning", True),
    "unknown": ("There is not enough safe evidence to classify the failure.", "unknown", True),
}

_CATEGORY_PRIORITY = [
    "provider_auth",
    "provider_quota",
    "provider_unavailable",
    "adapter_timeout",
    "adapter_interrupted",
    "queue_stale",
    "lock_timeout",
    "validation_failed",
    "approval_denied",
    "worktree_dirty",
    "artifact_collection_failed",
    "preview_failed",
    "deploy_blocked",
    "deploy_failed",
    "queue_blocked",
    "adapter_error",
    "unknown",
]

_CATEGORY_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("provider_auth", ("unauthorized", "forbidden", "invalid credential", "missing credential", "api key", "apikey", "auth", "token invalid", "401")),
    ("provider_quota", ("quota", "rate limit", "rate_limit", "too many requests", "billing", "payment", "429")),
    ("provider_unavailable", ("provider unavailable", "provider_unavailable", "not configured", "binary missing", "command not found", "health check failed", "unavailable")),
    ("adapter_timeout", ("timeout", "timed out", "max runtime", "idle timeout", "deadline exceeded")),
    ("adapter_interrupted", ("interrupted", "interrupt", "cancelled", "canceled", "user_interrupt")),
    ("queue_stale", ("stale", "lease expired", "heartbeat lease", "task_run_stale")),
    ("lock_timeout", ("lock timeout", "target lock", "lock unavailable", "lock wait")),
    ("worktree_dirty", ("dirty worktree", "worktree dirty", "uncommitted", "git status dirty")),
    ("validation_failed", ("validation", "planvalidator", "policy", "protected path", "allowlist", "target registry", "path denied", "command denied")),
    ("approval_denied", ("approval denied", "approval rejected", "denied approval", "approval expired")),
    ("preview_failed", ("preview", "vite", "dev server", "health check", "build failed")),
    ("deploy_blocked", ("deploy blocked", "deployment blocked", "manual handoff", "external provider", "provider not configured")),
    ("deploy_failed", ("deploy failed", "deployment failed", "staging failed")),
    ("artifact_collection_failed", ("artifact collection", "diff collection", "review collection", "collect", "no diff artifact")),
    ("queue_blocked", ("dependency blocked", "queue blocked", "scheduler blocked", "waiting dependency", "not ready")),
    ("adapter_error", ("adapter", "non-zero", "exit code", "subprocess", "parse error")),
]

_SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|token|secret|password|credential|authorization|bearer|private)",
    re.IGNORECASE,
)
_SECRET_VALUE_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]+|gh[pousr]_[A-Za-z0-9_]+|xox[baprs]-[A-Za-z0-9-]+|"
    r"bearer\s+[A-Za-z0-9._-]+|"
    r"(api[_-]?key|token|secret|password)\s*[:=]\s*[^,\s)]+)",
    re.IGNORECASE,
)
_HOST_PATH_RE = re.compile(r"(/Users/[^\s'\"`,)]+|/private/[^\s'\"`,)]+|/var/folders/[^\s'\"`,)]+)")
_PROTECTED_PATH_RE = re.compile(r"(\.env(?:\.[A-Za-z0-9_-]+)?|node_modules|secrets/)", re.IGNORECASE)


@dataclass(frozen=True)
class _FailureEvidence:
    category: str
    reason: str
    raw_error_code: Optional[str]
    source: str
    occurred_at: Optional[datetime]
    evidence: dict[str, Any]


def build_task_run_diagnostics(db: DbSession, task_run: TaskRun) -> RunDiagnosticsResponse:
    task = db.get(Task, task_run.task_id)
    session_id = task.session_id if task is not None else ""
    events = _events_for_run(db, task_run.id)
    artifacts = _artifacts_for_run(db, task_run.id)
    previews = _previews_for_artifacts(db, artifacts)
    deployments = _deployments_for_artifacts(db, artifacts)
    reviews = _reviews_for_artifacts(db, artifacts)
    diffs = _diffs_for_artifacts(db, artifacts)

    primary, contributing = classify_run_failure(
        task_run,
        events=events,
        artifacts=artifacts,
        previews=previews,
        deployments=deployments,
    )
    summary = _summary_for_run(task_run, primary, contributing)
    timeline = build_run_timeline(
        task_run,
        events=events,
        artifacts=artifacts,
        previews=previews,
        deployments=deployments,
        reviews=reviews,
        diffs=diffs,
    )
    health = _health_summary(
        db,
        task_run,
        events=events,
        artifacts=artifacts,
        previews=previews,
        deployments=deployments,
        primary=primary,
        contributing=contributing,
    )
    return RunDiagnosticsResponse(
        taskRunId=task_run.id,
        taskId=task_run.task_id,
        sessionId=session_id,
        summary=summary,
        primaryFailure=_failure_response(primary) if primary is not None else None,
        contributingFactors=[_failure_response(item) for item in contributing],
        downstreamImpact=[],
        timeline=timeline,
        healthSummary=health,
        suggestions=_suggestions_for(primary, contributing, artifacts),
    )


def build_session_run_diagnostics_summary(
    db: DbSession,
    session_id: str,
) -> SessionRunDiagnosticsSummaryResponse:
    tasks = db.exec(select(Task).where(Task.session_id == session_id)).all()
    task_ids = [task.id for task in tasks]
    if not task_ids:
        return SessionRunDiagnosticsSummaryResponse(
            sessionId=session_id,
            totalRuns=0,
            states={},
            categories={},
            runs=[],
        )

    runs = db.exec(
        select(TaskRun)
        .where(TaskRun.task_id.in_(task_ids))
        .order_by(TaskRun.updated_at.desc(), TaskRun.created_at.desc(), TaskRun.id)
    ).all()
    items: list[SessionRunDiagnosticsItemResponse] = []
    states: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    for run in runs:
        diagnostics = build_task_run_diagnostics(db, run)
        states[run.state] += 1
        categories[diagnostics.summary.primary_category] += 1
        items.append(
            SessionRunDiagnosticsItemResponse(
                taskRunId=run.id,
                taskId=run.task_id,
                state=run.state,
                primaryCategory=diagnostics.summary.primary_category,
                severity=diagnostics.summary.severity,
                retryable=diagnostics.summary.retryable,
                summary=diagnostics.summary.description,
                updatedAt=run.updated_at,
            )
        )
    return SessionRunDiagnosticsSummaryResponse(
        sessionId=session_id,
        totalRuns=len(runs),
        states=dict(states),
        categories=dict(categories),
        runs=items,
    )


def classify_run_failure(
    task_run: TaskRun,
    *,
    events: list[TaskRunEvent],
    artifacts: list[Artifact],
    previews: list[Preview],
    deployments: list[Deployment],
) -> tuple[Optional[_FailureEvidence], list[_FailureEvidence]]:
    candidates: list[_FailureEvidence] = []
    if task_run.error_code or task_run.error_message or task_run.state in {"failed", "interrupted", "waiting_approval"}:
        candidates.append(_failure_from_text(
            "task_run",
            " ".join(_compact_strings([task_run.state, task_run.error_code, task_run.error_message])),
            raw_error_code=task_run.error_code,
            occurred_at=task_run.ended_at or task_run.updated_at,
            evidence={"state": task_run.state},
        ))
    if task_run.stale_detected_at is not None:
        candidates.append(_failure("queue_stale", "TaskRun stale recovery evidence was recorded.", task_run.error_code, "task_run", task_run.stale_detected_at, {"staleReason": task_run.stale_reason}))

    for event in events:
        payload = _json_dict(event.payload_json)
        text = " ".join(_compact_strings([event.event_type, json.dumps(payload, default=str)]))
        category = _category_from_text(text)
        if event.event_type == "task.stale":
            category = "queue_stale"
        elif event.event_type == "approval.requested":
            category = "queue_blocked"
        elif event.event_type == "recovery.action":
            category = category if category != "unknown" else "queue_stale"
        elif event.event_type.startswith("artifact.preview") and _payload_status_failed(payload, "healthStatus"):
            category = "preview_failed"
        elif event.event_type.startswith("artifact.deploy"):
            category = _deploy_category(str(payload.get("status") or event.event_type))
        elif event.event_type == "error" and category == "unknown":
            category = "adapter_error"
        if category != "unknown":
            candidates.append(_failure(category, _reason_for_category(category), _string_value(payload.get("errorCode")) or task_run.error_code, "event", event.created_at, {"eventType": event.event_type, **payload}))

    for preview in previews:
        if preview.health_status not in {"healthy", "ready", "running"}:
            candidates.append(_failure("preview_failed", _reason_for_category("preview_failed"), None, "preview", preview.updated_at, {"previewId": preview.id, "healthStatus": preview.health_status, "statusReason": preview.status_reason}))

    for deployment in deployments:
        category = _deploy_category(deployment.status)
        if category in {"deploy_failed", "deploy_blocked"}:
            candidates.append(_failure(category, _reason_for_category(category), None, "deploy", deployment.updated_at, {"deploymentId": deployment.id, "status": deployment.status, "provider": deployment.provider}))

    for artifact in artifacts:
        if artifact.status in {"failed", "blocked"}:
            category = _artifact_failure_category(artifact)
            candidates.append(_failure(category, _reason_for_category(category), None, "artifact", artifact.updated_at, {"artifactId": artifact.id, "artifactType": artifact.artifact_type, "status": artifact.status}))

    if task_run.state in {"completed", "queued", "streaming", "applying_changes"}:
        primary = None
    else:
        primary = _select_primary(candidates)
        if primary is None:
            primary = _failure("unknown", _reason_for_category("unknown"), task_run.error_code, "task_run", task_run.ended_at or task_run.updated_at, {"state": task_run.state})

    contributing = _dedupe_failures([candidate for candidate in candidates if candidate != primary])
    return primary, contributing


def build_run_timeline(
    task_run: TaskRun,
    *,
    events: list[TaskRunEvent],
    artifacts: list[Artifact],
    previews: list[Preview],
    deployments: list[Deployment],
    reviews: list[Review],
    diffs: list[Diff],
) -> list[RunDiagnosticsTimelineItemResponse]:
    artifact_by_id = {artifact.id: artifact for artifact in artifacts}
    items = [
        RunDiagnosticsTimelineItemResponse(
            id=f"task-run-{task_run.id}-queued",
            timestamp=task_run.created_at,
            phase="queued",
            status="success" if task_run.state != "queued" else "pending",
            title="Run queued",
            description="TaskRun was created and queued for local execution.",
            source="task_run",
            metadata=_safe_metadata({"state": task_run.state, "adapterRunId": task_run.adapter_run_id}),
        )
    ]
    if task_run.started_at is not None:
        items.append(_timeline_item(
            f"task-run-{task_run.id}-adapter-start",
            task_run.started_at,
            "adapter_start",
            "running" if task_run.state not in {"completed", "failed", "interrupted"} else "success",
            "Adapter started",
            "The coding adapter entered an active execution state.",
            "task_run",
            {"runnerId": task_run.runner_id},
        ))

    for event in events:
        items.append(_event_timeline_item(event, artifact_by_id))

    for diff in diffs:
        artifact = artifact_by_id.get(diff.artifact_id)
        items.append(_artifact_timeline_item("diff", diff.created_at, artifact, {"diffId": diff.id, "changedFiles": _json_list(diff.changed_files_json), "stats": _json_dict(diff.stats_json)}))
    for review in reviews:
        artifact = artifact_by_id.get(review.artifact_id)
        items.append(_artifact_timeline_item("review", review.created_at, artifact, {"reviewId": review.id, "status": review.status, "riskLevel": review.risk_level}))
    for preview in previews:
        artifact = artifact_by_id.get(preview.artifact_id)
        status = "success" if preview.health_status == "healthy" else "failed"
        items.append(_artifact_timeline_item("preview", preview.updated_at, artifact, {"previewId": preview.id, "healthStatus": preview.health_status, "statusReason": preview.status_reason, "url": preview.url}, status=status))
    for deployment in deployments:
        artifact = artifact_by_id.get(deployment.artifact_id)
        status = "success" if deployment.status in {"ready", "deployed"} else "failed" if deployment.status in {"failed", "blocked"} else "warning"
        items.append(_artifact_timeline_item("deploy", deployment.updated_at, artifact, {"deploymentId": deployment.id, "provider": deployment.provider, "environment": deployment.environment, "status": deployment.status, "url": deployment.url}, status=status))

    if task_run.ended_at is not None:
        items.append(_timeline_item(
            f"task-run-{task_run.id}-finalize",
            task_run.ended_at,
            "finalize",
            "success" if task_run.state == "completed" else "failed",
            "Run finalized",
            f"TaskRun reached terminal state: {task_run.state}.",
            "task_run",
            {"state": task_run.state, "errorCode": task_run.error_code, "errorMessage": task_run.error_message},
        ))
    return _dedupe_timeline(sorted(items, key=lambda item: (item.timestamp, item.id)))


def _health_summary(
    db: DbSession,
    task_run: TaskRun,
    *,
    events: list[TaskRunEvent],
    artifacts: list[Artifact],
    previews: list[Preview],
    deployments: list[Deployment],
    primary: Optional[_FailureEvidence],
    contributing: list[_FailureEvidence],
) -> RunDiagnosticsHealthSummaryResponse:
    metrics = metrics_for_run(task_run)
    assignment = metrics.get("providerAssignment") if isinstance(metrics.get("providerAssignment"), dict) else {}
    agent = db.get(Agent, task_run.agent_id)
    adapter_type = adapter_type_for_run(db, task_run)
    provider_id = _string_value(assignment.get("providerId")) or (agent.provider if agent is not None else None)
    categories = {item.category for item in [primary, *contributing] if item is not None}
    fallback_from = _string_value(metrics.get("fallbackFromRunId"))
    real_provider_success = task_run.state == "completed" and adapter_type != "scripted_mock" and fallback_from is None

    provider_status = "failed" if categories & {"provider_auth", "provider_quota", "provider_unavailable"} else "healthy" if real_provider_success else "degraded" if fallback_from else "unknown"
    queue_status = "failed" if "queue_stale" in categories else "blocked" if task_run.state in {"queued", "waiting_approval"} or "queue_blocked" in categories else "healthy" if task_run.state == "completed" else "unknown"
    lock_status = "failed" if "lock_timeout" in categories else "blocked" if _has_lock_wait(events) else "unknown"
    latest_preview = _latest(previews, key=lambda preview: preview.updated_at)
    latest_deploy = _latest(deployments, key=lambda deploy: deploy.updated_at)

    preview_status = "unknown"
    if latest_preview is not None:
        preview_status = "healthy" if latest_preview.health_status == "healthy" else "failed"
    elif "preview_failed" in categories:
        preview_status = "failed"
    deploy_status = "unknown"
    if latest_deploy is not None:
        deploy_status = "healthy" if latest_deploy.status in {"ready", "deployed"} else "blocked" if latest_deploy.status == "blocked" else "failed"
    elif "deploy_blocked" in categories:
        deploy_status = "blocked"
    elif "deploy_failed" in categories:
        deploy_status = "failed"

    return RunDiagnosticsHealthSummaryResponse(
        provider=_safe_metadata({
            "status": provider_status,
            "providerId": provider_id,
            "adapterType": adapter_type,
            "authStatus": _auth_status(categories),
            "available": provider_status not in {"failed", "unknown"},
            "fallbackUsed": fallback_from is not None,
            "fallbackFromRunId": fallback_from,
            "realProviderSuccess": real_provider_success,
        }),
        queue=_safe_metadata({
            "status": queue_status,
            "queuedDurationMs": _duration_ms(task_run.created_at, task_run.started_at or task_run.updated_at),
            "runnerId": task_run.runner_id,
            "lastHeartbeatAt": task_run.last_heartbeat_at.isoformat() if task_run.last_heartbeat_at else None,
            "leaseExpiresAt": task_run.lease_expires_at.isoformat() if task_run.lease_expires_at else None,
            "staleDetectedAt": task_run.stale_detected_at.isoformat() if task_run.stale_detected_at else None,
            "staleReason": task_run.stale_reason,
        }),
        lock=_safe_metadata({
            "status": lock_status,
            "targetId": _first_event_value(events, "targetId"),
            "lockOwnerTaskRunIds": _first_event_value(events, "lockHolderTaskRunIds") or _first_event_value(events, "ownerTaskRunId"),
            "timeout": "lock_timeout" in categories,
        }),
        preview=_safe_metadata({
            "status": preview_status,
            "previewId": latest_preview.id if latest_preview else None,
            "healthStatus": latest_preview.health_status if latest_preview else None,
            "url": latest_preview.url if latest_preview and latest_preview.health_status == "healthy" else None,
            "statusReason": latest_preview.status_reason if latest_preview else None,
            "sourceArtifact": latest_preview.artifact_id if latest_preview else None,
        }),
        deploy=_safe_metadata({
            "status": deploy_status,
            "deploymentId": latest_deploy.id if latest_deploy else None,
            "provider": latest_deploy.provider if latest_deploy else None,
            "environment": latest_deploy.environment if latest_deploy else None,
            "url": latest_deploy.url if latest_deploy and latest_deploy.status in {"ready", "deployed"} else None,
            "sourceArtifact": latest_deploy.artifact_id if latest_deploy else None,
        }),
    )


def _suggestions_for(
    primary: Optional[_FailureEvidence],
    contributing: list[_FailureEvidence],
    artifacts: list[Artifact],
) -> list[RunDiagnosticsSuggestionResponse]:
    categories = [item.category for item in [primary, *contributing] if item is not None]
    category = categories[0] if categories else "unknown"
    artifact_targets = {artifact.artifact_type: artifact.id for artifact in artifacts}
    suggestions: list[RunDiagnosticsSuggestionResponse] = []

    def add(action_id: str, label: str, description: str, kind: str, enabled: bool = True, target: Optional[dict[str, Any]] = None, disabled_reason: Optional[str] = None) -> None:
        suggestions.append(RunDiagnosticsSuggestionResponse(actionId=action_id, label=label, description=description, kind=kind, enabled=enabled, disabledReason=disabled_reason, target=_safe_metadata(target or {}) if target else None))

    if category in {"provider_auth", "provider_unavailable"}:
        add("open-runtime-settings", "Check provider settings", "Review runtime provider credentials and availability before retrying.", "open_settings")
        add("choose-scripted-fallback", "Use demo fallback", "Switch to ScriptedMock fallback for demo continuity; this is not real provider success.", "choose_fallback")
    elif category == "provider_quota":
        add("wait-for-provider-quota", "Wait for quota", "Wait for provider quota or rate limits to recover, then retry.", "wait")
        add("choose-scripted-fallback", "Use demo fallback", "Use ScriptedMock fallback only as a clearly marked demo path.", "choose_fallback")
    elif category == "adapter_timeout":
        add("retry-smaller-run", "Retry smaller scope", "Retry with a narrower request and inspect adapter timeline for long-running commands.", "retry")
    elif category == "adapter_interrupted":
        add("retry-interrupted-run", "Retry run", "Retry after confirming the interruption was intentional or resolved.", "retry")
    elif category == "queue_stale":
        add("retry-after-recovery", "Retry after recovery", "The stale worker lease was recovered; retry the run if the target is still valid.", "retry")
    elif category in {"queue_blocked", "lock_timeout"}:
        add("wait-for-queue", "Wait for readiness", "Wait for dependency, queue, or target lock readiness before retrying.", "wait")
    elif category == "worktree_dirty":
        add("open-diff", "Inspect diff", "Review current diff evidence before retrying or creating a new Session.", "open_artifact", enabled="diff" in artifact_targets, target={"artifactId": artifact_targets.get("diff")}, disabled_reason=None if "diff" in artifact_targets else "No diff artifact is available.")
    elif category == "validation_failed":
        add("change-request", "Adjust request", "Modify the request to avoid protected paths, unsupported targets, or blocked commands.", "change_request")
    elif category == "approval_denied":
        add("request-approval", "Request approval", "Ask for approval again after narrowing or clarifying the requested action.", "request_approval")
    elif category == "preview_failed":
        add("open-preview-artifact", "Open preview evidence", "Inspect preview logs and health status before retrying preview.", "open_artifact", enabled="preview" in artifact_targets, target={"artifactId": artifact_targets.get("preview")}, disabled_reason=None if "preview" in artifact_targets else "No preview artifact is available.")
    elif category == "deploy_blocked":
        add("manual-handoff", "Use manual handoff", "Complete provider configuration or use manual handoff/local staging without claiming production success.", "manual_handoff")
    elif category == "deploy_failed":
        add("open-deploy-artifact", "Open deployment evidence", "Inspect deployment logs and status history before retrying deployment.", "open_artifact", enabled="deployment" in artifact_targets, target={"artifactId": artifact_targets.get("deployment")}, disabled_reason=None if "deployment" in artifact_targets else "No deployment artifact is available.")
    elif category == "artifact_collection_failed":
        add("retry-artifact-collection", "Retry collection", "Retry diff/review/artifact collection after checking the timeline.", "retry")
    else:
        add("inspect-timeline", "Inspect timeline", "Review available run events; evidence is limited, so retry only after checking context.", "open_artifact", enabled=False, disabled_reason="No specific artifact is available for an unknown failure.")
        add("retry-unknown-run", "Retry run", "Retry if the request and target still look safe.", "retry")

    if not any(suggestion.kind == "retry" for suggestion in suggestions) and category not in {"validation_failed", "approval_denied", "deploy_blocked"}:
        add("retry-run", "Retry run", "Retry the TaskRun after checking the diagnostic summary.", "retry")
    return suggestions[:4]


def _failure_from_text(
    source: str,
    text: str,
    *,
    raw_error_code: Optional[str],
    occurred_at: Optional[datetime],
    evidence: dict[str, Any],
) -> _FailureEvidence:
    category = _category_from_error_code(raw_error_code) or _category_from_text(text)
    return _failure(category, _reason_for_category(category), raw_error_code, source, occurred_at, evidence)


def _failure(
    category: str,
    reason: str,
    raw_error_code: Optional[str],
    source: str,
    occurred_at: Optional[datetime],
    evidence: dict[str, Any],
) -> _FailureEvidence:
    if category not in FAILURE_CATEGORIES:
        category = "unknown"
    return _FailureEvidence(
        category=category,
        reason=reason,
        raw_error_code=raw_error_code,
        source=source,
        occurred_at=occurred_at,
        evidence=_safe_metadata(evidence),
    )


def _select_primary(candidates: list[_FailureEvidence]) -> Optional[_FailureEvidence]:
    if not candidates:
        return None
    priority = {category: index for index, category in enumerate(_CATEGORY_PRIORITY)}
    return sorted(candidates, key=lambda item: (priority.get(item.category, 999), item.occurred_at or datetime.min))[0]


def _dedupe_failures(candidates: list[_FailureEvidence]) -> list[_FailureEvidence]:
    seen: set[str] = set()
    output: list[_FailureEvidence] = []
    for candidate in candidates:
        if candidate.category in seen:
            continue
        seen.add(candidate.category)
        output.append(candidate)
    return output


def _failure_response(item: _FailureEvidence) -> RunDiagnosticsFailureResponse:
    _reason, severity, retryable = _CATEGORY_COPY[item.category]
    return RunDiagnosticsFailureResponse(
        category=item.category,
        reason=item.reason,
        severity=severity,
        retryable=retryable,
        rawErrorCode=item.raw_error_code,
        source=item.source,
        occurredAt=item.occurred_at,
        evidence=item.evidence,
    )


def _summary_for_run(
    task_run: TaskRun,
    primary: Optional[_FailureEvidence],
    contributing: list[_FailureEvidence],
) -> RunDiagnosticsSummaryResponse:
    category = primary.category if primary is not None else "none"
    if primary is None and contributing:
        description = "Run completed, with post-run issues recorded."
        severity = "warning"
        retryable = True
        evidence_status = "partial"
    elif primary is None:
        description = "Run has no classified failure evidence."
        severity = "info"
        retryable = False
        evidence_status = "available"
    else:
        _copy, severity, retryable = _CATEGORY_COPY[primary.category]
        description = primary.reason
        evidence_status = "limited" if primary.category == "unknown" else "available"
    return RunDiagnosticsSummaryResponse(
        state=task_run.state,
        statusLabel=_status_label(task_run.state),
        severity=severity,
        retryable=retryable,
        primaryCategory=category,
        description=description,
        evidenceStatus=evidence_status,
        fallbackUsed=_json_dict(task_run.metrics_json).get("fallbackFromRunId") is not None,
    )


def _event_timeline_item(
    event: TaskRunEvent,
    artifact_by_id: dict[str, Artifact],
) -> RunDiagnosticsTimelineItemResponse:
    payload = _json_dict(event.payload_json)
    phase = _phase_for_event(event.event_type, payload)
    status = _status_for_event(event.event_type, payload)
    artifact = artifact_by_id.get(_string_value(payload.get("artifactId")) or "")
    return _timeline_item(
        f"event-{event.sequence}-{phase}-{event.id}",
        event.created_at,
        phase,
        status,
        _title_for_phase(phase, event.event_type),
        _description_for_event(event.event_type, payload),
        _source_for_phase(phase, event.event_type),
        {"eventType": event.event_type, **payload},
        _artifact_reference(artifact) if artifact is not None else None,
    )


def _artifact_timeline_item(
    phase: str,
    timestamp: datetime,
    artifact: Optional[Artifact],
    metadata: dict[str, Any],
    *,
    status: str = "success",
) -> RunDiagnosticsTimelineItemResponse:
    artifact_id = artifact.id if artifact is not None else str(metadata.get(f"{phase}Id") or phase)
    return _timeline_item(
        f"artifact-{phase}-{artifact_id}",
        timestamp,
        phase,
        status,
        f"{phase.replace('_', ' ').title()} evidence",
        f"{phase.replace('_', ' ')} evidence was recorded.",
        phase if phase in {"preview", "deploy"} else "artifact",
        metadata,
        _artifact_reference(artifact) if artifact is not None else None,
    )


def _timeline_item(
    item_id: str,
    timestamp: datetime,
    phase: str,
    status: str,
    title: str,
    description: str,
    source: str,
    metadata: dict[str, Any],
    artifact_reference: Optional[RunDiagnosticsArtifactReferenceResponse] = None,
) -> RunDiagnosticsTimelineItemResponse:
    if phase not in TIMELINE_PHASES:
        phase = "adapter_stream"
    return RunDiagnosticsTimelineItemResponse(
        id=item_id,
        timestamp=timestamp,
        phase=phase,
        status=status if status in {"pending", "running", "success", "warning", "failed", "skipped"} else "warning",
        title=title,
        description=_safe_string(description, max_length=220),
        source=source,
        metadata=_safe_metadata(metadata),
        artifactReference=artifact_reference,
    )


def _dedupe_timeline(
    items: list[RunDiagnosticsTimelineItemResponse],
) -> list[RunDiagnosticsTimelineItemResponse]:
    seen: set[tuple[str, str, Optional[str]]] = set()
    output: list[RunDiagnosticsTimelineItemResponse] = []
    for item in items:
        artifact_id = item.artifact_reference.artifact_id if item.artifact_reference else None
        key = (item.phase, item.source, artifact_id)
        if artifact_id is not None and key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def _artifact_reference(
    artifact: Optional[Artifact],
) -> Optional[RunDiagnosticsArtifactReferenceResponse]:
    if artifact is None:
        return None
    return RunDiagnosticsArtifactReferenceResponse(
        artifactId=artifact.id,
        artifactType=artifact.artifact_type,
        title=_safe_string(artifact.title),
        status=artifact.status,
        targetId=_string_value(_json_dict(artifact.meta_json).get("targetId")),
    )


def _category_from_text(text: str) -> str:
    lowered = text.lower()
    for category, patterns in _CATEGORY_PATTERNS:
        if any(pattern in lowered for pattern in patterns):
            return category
    return "unknown"


def _category_from_error_code(error_code: Optional[str]) -> Optional[str]:
    if not error_code:
        return None
    normalized = error_code.lower()
    normalized = normalized.replace("-", "_").replace(".", "_")
    exact = {
        "provider_auth": "provider_auth",
        "provider_auth_missing": "provider_auth",
        "provider_quota": "provider_quota",
        "provider_quota_exceeded": "provider_quota",
        "provider_unavailable": "provider_unavailable",
        "adapter_timeout": "adapter_timeout",
        "adapter_max_runtime_timeout": "adapter_timeout",
        "adapter_idle_timeout": "adapter_timeout",
        "adapter_interrupted": "adapter_interrupted",
        "task_run_stale": "queue_stale",
        "queue_stale": "queue_stale",
        "queue_blocked": "queue_blocked",
        "lock_timeout": "lock_timeout",
        "target_lock_timeout": "lock_timeout",
        "worktree_dirty": "worktree_dirty",
        "validation_failed": "validation_failed",
        "approval_denied": "approval_denied",
        "preview_failed": "preview_failed",
        "deploy_failed": "deploy_failed",
        "deploy_blocked": "deploy_blocked",
        "artifact_collection_failed": "artifact_collection_failed",
    }
    if normalized in exact:
        return exact[normalized]
    for category in FAILURE_CATEGORIES:
        if category != "unknown" and category in normalized:
            return category
    if "timeout" in normalized and "lock" in normalized:
        return "lock_timeout"
    if "timeout" in normalized:
        return "adapter_timeout"
    return None


def _reason_for_category(category: str) -> str:
    return _CATEGORY_COPY.get(category, _CATEGORY_COPY["unknown"])[0]


def _deploy_category(status_text: str) -> str:
    lowered = status_text.lower()
    if "blocked" in lowered or "manual" in lowered or "handoff" in lowered:
        return "deploy_blocked"
    if "failed" in lowered or "error" in lowered:
        return "deploy_failed"
    return "unknown"


def _artifact_failure_category(artifact: Artifact) -> str:
    if artifact.artifact_type == "preview":
        return "preview_failed"
    if artifact.artifact_type == "deployment":
        return "deploy_blocked" if artifact.status == "blocked" else "deploy_failed"
    if artifact.artifact_type in {"diff", "review", "command_evidence"}:
        return "artifact_collection_failed"
    return "unknown"


def _phase_for_event(event_type: str, payload: dict[str, Any]) -> str:
    state = _string_value(payload.get("state"))
    if event_type == "run.claimed":
        return "worker_claim"
    if event_type == "task.heartbeat":
        return "worker_claim"
    if event_type == "task.stale" or event_type == "recovery.action":
        return "recovery"
    if event_type.startswith("delivery."):
        if event_type in {"delivery.rolled_back", "delivery.rollback_refused"}:
            return "recovery"
        if event_type in {"delivery.accepted"}:
            return "finalize"
        return "validation"
    if event_type == "approval.requested" or state == "waiting_approval":
        return "approval_wait"
    if event_type.startswith("artifact.diff"):
        return "diff"
    if event_type.startswith("artifact.review"):
        return "review"
    if event_type.startswith("artifact.preview"):
        return "preview"
    if event_type.startswith("artifact.deploy"):
        return "deploy"
    if event_type.startswith("artifact."):
        return "artifact_collection"
    if event_type == "target_lock.released" or "lock" in event_type:
        return "lock_wait"
    if state == "queued":
        return "queued"
    if state in {"streaming", "applying_changes"}:
        return "adapter_stream"
    if state in {"completed", "failed", "interrupted"} or event_type in {"completed", "error"}:
        return "adapter_finish"
    if "provider" in event_type:
        return "provider_check"
    if "dependency" in event_type:
        return "dependency_wait"
    if "validation" in event_type or "policy" in event_type:
        return "validation"
    if "scheduler" in event_type:
        return "scheduler_check"
    return "adapter_stream"


def _status_for_event(event_type: str, payload: dict[str, Any]) -> str:
    status_text = " ".join(_compact_strings([payload.get("status"), payload.get("state"), payload.get("healthStatus"), event_type])).lower()
    if any(term in status_text for term in ("failed", "error", "denied", "timeout", "blocked", "review_required")):
        return "failed"
    if any(term in status_text for term in ("stale", "warning", "degraded", "interrupted")):
        return "warning"
    if any(term in status_text for term in ("completed", "ready", "healthy", "success")):
        return "success"
    if any(term in status_text for term in ("queued", "requested", "waiting")):
        return "pending"
    return "running"


def _title_for_phase(phase: str, event_type: str) -> str:
    titles = {
        "queued": "Run queued",
        "scheduler_check": "Scheduler check",
        "dependency_wait": "Dependency wait",
        "lock_wait": "Target lock",
        "approval_wait": "Approval wait",
        "validation": "Validation",
        "provider_check": "Provider check",
        "worker_claim": "Worker claim",
        "adapter_start": "Adapter start",
        "adapter_stream": "Adapter event",
        "adapter_finish": "Adapter finished",
        "artifact_collection": "Artifact collection",
        "diff": "Diff ready",
        "review": "Review ready",
        "preview": "Preview evidence",
        "deploy": "Deploy evidence",
        "finalize": "Finalize",
        "recovery": "Recovery",
    }
    return titles.get(phase, event_type)


def _description_for_event(event_type: str, payload: dict[str, Any]) -> str:
    message = _string_value(payload.get("message")) or _string_value(payload.get("errorMessage")) or _string_value(payload.get("reason"))
    if message:
        return message
    state = _string_value(payload.get("state"))
    if state:
        return f"TaskRun state changed to {state}."
    return f"Recorded event {event_type}."


def _source_for_phase(phase: str, event_type: str) -> str:
    if phase in {"preview", "deploy"}:
        return phase
    if phase in {"diff", "review", "artifact_collection"}:
        return "artifact"
    if phase in {"scheduler_check", "dependency_wait", "lock_wait", "approval_wait"}:
        return "scheduler"
    if phase == "provider_check":
        return "provider"
    return "event" if event_type != "task.state" else "task_run"


def _payload_status_failed(payload: dict[str, Any], key: str) -> bool:
    value = _string_value(payload.get(key))
    return value is not None and value not in {"healthy", "ready", "success", "completed"}


def _has_lock_wait(events: list[TaskRunEvent]) -> bool:
    return any(_phase_for_event(event.event_type, _json_dict(event.payload_json)) == "lock_wait" for event in events)


def _auth_status(categories: set[str]) -> str:
    if "provider_auth" in categories:
        return "invalid"
    if categories & {"provider_unavailable", "provider_quota"}:
        return "unknown"
    return "configured"


def _first_event_value(events: list[TaskRunEvent], key: str) -> Any:
    for event in events:
        payload = _json_dict(event.payload_json)
        if key in payload:
            return payload[key]
    return None


def _safe_metadata(value: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        return "[truncated]"
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 20:
                output["truncated"] = True
                break
            safe_key = _safe_string(str(key), max_length=80)
            output[safe_key] = "[redacted]" if _SECRET_KEY_RE.search(str(key)) else _safe_metadata(item, depth=depth + 1)
        return output
    if isinstance(value, list):
        return [_safe_metadata(item, depth=depth + 1) for item in value[:12]]
    if isinstance(value, tuple):
        return [_safe_metadata(item, depth=depth + 1) for item in list(value)[:12]]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return _safe_string(value)
    return value


def _safe_string(value: str, *, max_length: int = 240) -> str:
    safe = _SECRET_VALUE_RE.sub("[redacted]", value)
    safe = _HOST_PATH_RE.sub("[redacted-path]", safe)
    safe = _PROTECTED_PATH_RE.sub("[redacted-path]", safe)
    if len(safe) > max_length:
        return safe[: max_length - 15].rstrip() + "...[truncated]"
    return safe


def _status_label(state: str) -> str:
    labels = {
        "queued": "Queued",
        "waiting_approval": "Waiting for approval",
        "streaming": "Running",
        "applying_changes": "Applying changes",
        "completed": "Completed",
        "failed": "Failed",
        "interrupted": "Interrupted",
    }
    return labels.get(state, state.replace("_", " ").title())


def _duration_ms(start: Optional[datetime], end: Optional[datetime]) -> Optional[int]:
    if start is None or end is None:
        return None
    return max(0, int((end - start).total_seconds() * 1000))


def _latest(items: list[Any], *, key: Any) -> Optional[Any]:
    if not items:
        return None
    return sorted(items, key=key)[-1]


def _events_for_run(db: DbSession, task_run_id: str) -> list[TaskRunEvent]:
    return db.exec(
        select(TaskRunEvent)
        .where(TaskRunEvent.task_run_id == task_run_id)
        .order_by(TaskRunEvent.created_at, TaskRunEvent.sequence, TaskRunEvent.id)
    ).all()


def _artifacts_for_run(db: DbSession, task_run_id: str) -> list[Artifact]:
    return db.exec(
        select(Artifact)
        .where(Artifact.task_run_id == task_run_id)
        .order_by(Artifact.created_at, Artifact.id)
    ).all()


def _diffs_for_artifacts(db: DbSession, artifacts: list[Artifact]) -> list[Diff]:
    ids = [artifact.id for artifact in artifacts]
    if not ids:
        return []
    return db.exec(select(Diff).where(Diff.artifact_id.in_(ids)).order_by(Diff.created_at, Diff.id)).all()


def _reviews_for_artifacts(db: DbSession, artifacts: list[Artifact]) -> list[Review]:
    ids = [artifact.id for artifact in artifacts]
    if not ids:
        return []
    return db.exec(select(Review).where(Review.artifact_id.in_(ids)).order_by(Review.created_at, Review.id)).all()


def _previews_for_artifacts(db: DbSession, artifacts: list[Artifact]) -> list[Preview]:
    ids = [artifact.id for artifact in artifacts]
    if not ids:
        return []
    return db.exec(select(Preview).where(Preview.artifact_id.in_(ids)).order_by(Preview.created_at, Preview.id)).all()


def _deployments_for_artifacts(db: DbSession, artifacts: list[Artifact]) -> list[Deployment]:
    ids = [artifact.id for artifact in artifacts]
    if not ids:
        return []
    return db.exec(select(Deployment).where(Deployment.artifact_id.in_(ids)).order_by(Deployment.created_at, Deployment.id)).all()


def _json_dict(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_list(value: str) -> list[Any]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _string_value(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and value else None


def _compact_strings(values: list[Any]) -> list[str]:
    return [str(value) for value in values if value is not None and str(value)]
