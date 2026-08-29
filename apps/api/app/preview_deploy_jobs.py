import json
from typing import Any, Optional

from sqlalchemy import update
from sqlmodel import Session as DbSession
from sqlmodel import select

from app.deployments import DeployError, DeployService
from app.events import append_task_run_event
from app.models import Artifact, Preview, PreviewDeployJob, Task, TaskRun, utc_now
from app.previews import PreviewError, PreviewService
from app.task_run_scope import TaskRunScopeError
from app.task_runs import require_task_run_artifact_scope_passed


def enqueue_preview_job(db: DbSession, task_run: TaskRun) -> Optional[PreviewDeployJob]:
    require_task_run_artifact_scope_passed(db, task_run.id)
    task = db.get(Task, task_run.task_id)
    if task is None:
        return None
    existing = _job_for_source(db, task_run.id, "preview")
    if existing is not None:
        return existing
    now = utc_now()
    job = PreviewDeployJob(
        session_id=task.session_id,
        source_task_run_id=task_run.id,
        job_type="preview",
        state="queued",
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    _append_job_event(db, job, "preview_job.queued")
    return job


def enqueue_deploy_job(db: DbSession, source_task_run_id: str, preview_id: str) -> PreviewDeployJob:
    _require_deploy_preview_source(db, source_task_run_id, preview_id)
    existing = _job_for_source(db, source_task_run_id, "deploy")
    if existing is not None:
        return existing
    task_run = db.get(TaskRun, source_task_run_id)
    if task_run is None:
        raise ValueError(f"TaskRun not found: {source_task_run_id}")
    task = db.get(Task, task_run.task_id)
    if task is None:
        raise ValueError(f"Task not found for TaskRun: {source_task_run_id}")
    now = utc_now()
    job = PreviewDeployJob(
        session_id=task.session_id,
        source_task_run_id=source_task_run_id,
        job_type="deploy",
        state="queued",
        evidence_json=json.dumps({"sourcePreviewId": preview_id}, separators=(",", ":")),
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    _append_job_event(db, job, "deploy_job.queued")
    return job


def run_preview_job(
    db: DbSession,
    job: PreviewDeployJob,
    *,
    preview_service: PreviewService,
) -> PreviewDeployJob:
    try:
        require_task_run_artifact_scope_passed(db, job.source_task_run_id)
    except TaskRunScopeError as exc:
        return _mark_job_failed(db, job, exc.error_code, exc.message)
    if not _mark_job_running(db, job):
        return job
    try:
        preview = preview_service.start_task_run_preview(db, job.source_task_run_id)
    except PreviewError as exc:
        return _mark_job_failed(db, job, "PREVIEW_JOB_FAILED", str(exc))

    evidence = {
        "previewId": preview.id,
        "artifactId": preview.artifact_id,
        "url": preview.url,
        "healthStatus": preview.health_status,
        "statusReason": preview.status_reason,
    }
    if preview.health_status != "healthy":
        return _mark_job_failed(
            db,
            job,
            "PREVIEW_HEALTH_FAILED",
            preview.status_reason or "Preview did not become healthy.",
            evidence=evidence,
        )
    return _mark_job_completed(db, job, evidence)


def run_deploy_job(
    db: DbSession,
    job: PreviewDeployJob,
    *,
    deploy_service: DeployService,
) -> PreviewDeployJob:
    evidence = _evidence(job)
    preview_id = evidence.get("sourcePreviewId")
    if not isinstance(preview_id, str) or not preview_id:
        return _mark_job_failed(db, job, "DEPLOY_PREVIEW_MISSING", "Deploy job has no preview id.")
    try:
        _require_deploy_preview_source(db, job.source_task_run_id, preview_id)
    except TaskRunScopeError as exc:
        return _mark_job_failed(db, job, exc.error_code, exc.message)
    if not _mark_job_running(db, job):
        return job
    try:
        deployment = deploy_service.create_mock_deployment(db, preview_id)
    except DeployError as exc:
        return _mark_job_failed(db, job, "DEPLOY_JOB_FAILED", str(exc), evidence=evidence)
    return _mark_job_completed(
        db,
        job,
        {
            **evidence,
            "deploymentId": deployment.id,
            "provider": deployment.provider,
            "status": deployment.status,
            "mockBacked": True,
        },
    )


def _require_deploy_preview_source(
    db: DbSession,
    source_task_run_id: str,
    preview_id: str,
) -> None:
    preview = db.get(Preview, preview_id)
    artifact = db.get(Artifact, preview.artifact_id) if preview is not None else None
    if (
        preview is None
        or artifact is None
        or artifact.artifact_type != "preview"
        or artifact.task_run_id != source_task_run_id
    ):
        raise TaskRunScopeError(
            "TASK_RUN_SCOPE_UNVERIFIABLE",
            "The deploy preview source TaskRun cannot be verified.",
        )
    require_task_run_artifact_scope_passed(db, artifact.task_run_id)


def list_jobs_for_task_run(db: DbSession, task_run_id: str) -> list[PreviewDeployJob]:
    return db.exec(
        select(PreviewDeployJob)
        .where(PreviewDeployJob.source_task_run_id == task_run_id)
        .order_by(PreviewDeployJob.created_at, PreviewDeployJob.id)
    ).all()


def job_diagnostics_for_task_run(db: DbSession, task_run_id: str) -> list[dict[str, Any]]:
    return [_job_payload(job) for job in list_jobs_for_task_run(db, task_run_id)]


def _job_for_source(
    db: DbSession,
    source_task_run_id: str,
    job_type: str,
) -> Optional[PreviewDeployJob]:
    return db.exec(
        select(PreviewDeployJob)
        .where(PreviewDeployJob.source_task_run_id == source_task_run_id)
        .where(PreviewDeployJob.job_type == job_type)
        .order_by(PreviewDeployJob.created_at, PreviewDeployJob.id)
    ).first()


def _mark_job_running(db: DbSession, job: PreviewDeployJob) -> bool:
    db.refresh(job)
    if job.state != "queued":
        return False
    now = utc_now()
    result = db.execute(
        update(PreviewDeployJob)
        .where(PreviewDeployJob.id == job.id)
        .where(PreviewDeployJob.state == "queued")
        .values(
            state="running",
            started_at=job.started_at or now,
            updated_at=now,
        )
    )
    db.commit()
    db.refresh(job)
    if result.rowcount != 1:
        return False
    _append_job_event(db, job, f"{job.job_type}_job.running")
    return True


def _mark_job_completed(
    db: DbSession,
    job: PreviewDeployJob,
    evidence: dict[str, Any],
) -> PreviewDeployJob:
    db.refresh(job)
    if job.state in {"completed", "failed", "interrupted", "cancelled"}:
        return job
    now = utc_now()
    job.state = "completed"
    job.error_code = None
    job.evidence_json = json.dumps(evidence, separators=(",", ":"))
    job.finished_at = now
    job.updated_at = now
    if job.job_type == "preview" and isinstance(evidence.get("previewId"), str):
        job.port = _preview_port_from_url(evidence.get("url"))
    db.add(job)
    db.commit()
    db.refresh(job)
    _append_job_event(db, job, f"{job.job_type}_job.completed")
    return job


def _mark_job_failed(
    db: DbSession,
    job: PreviewDeployJob,
    error_code: str,
    error_message: str,
    *,
    evidence: Optional[dict[str, Any]] = None,
) -> PreviewDeployJob:
    db.refresh(job)
    if job.state in {"completed", "failed", "interrupted", "cancelled"}:
        return job
    now = utc_now()
    previous_state = job.state
    payload = {
        **_evidence(job),
        **(evidence or {}),
        "errorMessage": error_message,
    }
    result = db.execute(
        update(PreviewDeployJob)
        .where(PreviewDeployJob.id == job.id)
        .where(PreviewDeployJob.state == previous_state)
        .values(
            state="failed",
            error_code=error_code,
            evidence_json=json.dumps(payload, separators=(",", ":")),
            finished_at=now,
            updated_at=now,
        )
    )
    db.commit()
    db.refresh(job)
    if result.rowcount != 1:
        return job
    _append_job_event(db, job, f"{job.job_type}_job.failed")
    return job


def _append_job_event(db: DbSession, job: PreviewDeployJob, event_type: str) -> None:
    append_task_run_event(
        db,
        task_run_id=job.source_task_run_id,
        event_type=event_type,
        payload_json=json.dumps(_job_payload(job), separators=(",", ":")),
    )


def _job_payload(job: PreviewDeployJob) -> dict[str, Any]:
    return {
        "jobId": job.id,
        "sessionId": job.session_id,
        "sourceTaskRunId": job.source_task_run_id,
        "jobType": job.job_type,
        "state": job.state,
        "attempt": job.attempt,
        "port": job.port,
        "errorCode": job.error_code,
        "evidence": _evidence(job),
        "startedAt": job.started_at.isoformat() if job.started_at else None,
        "finishedAt": job.finished_at.isoformat() if job.finished_at else None,
    }


def _evidence(job: PreviewDeployJob) -> dict[str, Any]:
    try:
        value = json.loads(job.evidence_json)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _preview_port_from_url(url: Any) -> Optional[int]:
    if not isinstance(url, str):
        return None
    try:
        return int(url.rsplit(":", 1)[1].split("/", 1)[0])
    except (IndexError, ValueError):
        return None
