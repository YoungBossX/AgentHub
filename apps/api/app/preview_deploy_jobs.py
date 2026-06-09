import json
from typing import Any, Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.deployments import DeployError, DeployService
from app.events import append_task_run_event
from app.models import PreviewDeployJob, Task, TaskRun, utc_now
from app.previews import PreviewError, PreviewService


def enqueue_preview_job(db: DbSession, task_run: TaskRun) -> Optional[PreviewDeployJob]:
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
    _mark_job_running(db, job)
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
    _mark_job_running(db, job)
    evidence = _evidence(job)
    preview_id = evidence.get("sourcePreviewId")
    if not isinstance(preview_id, str) or not preview_id:
        return _mark_job_failed(db, job, "DEPLOY_PREVIEW_MISSING", "Deploy job has no preview id.")
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


def _mark_job_running(db: DbSession, job: PreviewDeployJob) -> None:
    now = utc_now()
    job.state = "running"
    job.started_at = job.started_at or now
    job.updated_at = now
    db.add(job)
    db.commit()
    db.refresh(job)
    _append_job_event(db, job, f"{job.job_type}_job.running")


def _mark_job_completed(
    db: DbSession,
    job: PreviewDeployJob,
    evidence: dict[str, Any],
) -> PreviewDeployJob:
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
    now = utc_now()
    payload = {**(evidence or {}), "errorMessage": error_message}
    job.state = "failed"
    job.error_code = error_code
    job.evidence_json = json.dumps(payload, separators=(",", ":"))
    job.finished_at = now
    job.updated_at = now
    db.add(job)
    db.commit()
    db.refresh(job)
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
