from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session as DbSession

from app.artifact_versions import (
    ArtifactVersionError,
    StoredArtifactVersion,
    list_artifact_versions,
)
from app.artifact_workbench import (
    ArtifactVersionWorkbenchMetadata,
    ArtifactWorkbenchError,
    ArtifactWorkbenchMetadata,
    artifact_workbench_metadata_for_id,
    artifact_workbench_version_for_id,
    list_artifact_workbench_versions,
    list_session_artifact_workbench,
    save_artifact_workbench_edit,
)
from app.dependencies import get_db, get_deploy_service, get_preview_service
from app.deployments import DeployError, DeployService, StoredDeploymentArtifact
from app.diffs import (
    DiffCollectionError,
    StoredDiffArtifact,
    collect_task_run_diff,
    list_task_run_diffs,
    record_diff_collection_failure,
)
from app.external_evidence import (
    ExternalEvidenceError,
    StoredCommandEvidence,
    list_task_run_command_evidence,
    record_command_evidence,
)
from app.ledger import refresh_session_ledger_for_task_run
from app.models import Artifact, Preview, TaskRun
from app.models import Session as AgentHubSession
from app.previews import PreviewError, PreviewService, StoredPreviewArtifact
from app.reviews import (
    ReviewError,
    StoredReviewArtifact,
    create_scripted_review_for_task_run,
    list_task_run_reviews,
    record_review_collection_failure,
)
from app.schemas import (
    ArtifactVersionResponse,
    ArtifactWorkbenchArtifactResponse,
    ArtifactWorkbenchEditRequest,
    ArtifactWorkbenchSessionResponse,
    ArtifactWorkbenchVersionResponse,
    CommandEvidenceCreateRequest,
    CommandEvidenceResponse,
    DeploymentCreateRequest,
    DeploymentResponse,
    DiffArtifactResponse,
    PreviewResponse,
    ReviewArtifactResponse,
)
from app.task_run_scope import TaskRunScopeError
from app.task_runs import require_task_run_artifact_scope_passed


router = APIRouter()


def diff_artifact_response(diff_artifact: StoredDiffArtifact) -> DiffArtifactResponse:
    return DiffArtifactResponse(
        id=diff_artifact.id,
        artifactId=diff_artifact.artifact_id,
        taskRunId=diff_artifact.task_run_id,
        artifactType=diff_artifact.artifact_type,
        title=diff_artifact.title,
        status=diff_artifact.status,
        baseRef=diff_artifact.base_ref,
        headRef=diff_artifact.head_ref,
        patchText=diff_artifact.patch_text,
        changedFiles=diff_artifact.changed_files,
        stats=diff_artifact.stats,
    )


def artifact_version_response(version: StoredArtifactVersion) -> ArtifactVersionResponse:
    return ArtifactVersionResponse(
        id=version.id,
        artifactId=version.artifact_id,
        version=version.version,
        sourceTaskRunId=version.source_task_run_id,
        parentArtifactId=version.parent_artifact_id,
        gitBaseRef=version.git_base_ref,
        gitHeadRef=version.git_head_ref,
        changedFiles=version.changed_files,
        summary=version.summary,
        createdAt=version.created_at,
    )


def artifact_workbench_version_response(
    version: ArtifactVersionWorkbenchMetadata,
) -> ArtifactWorkbenchVersionResponse:
    return ArtifactWorkbenchVersionResponse(
        id=version.id,
        artifactId=version.artifact_id,
        version=version.version,
        parentVersionId=version.parent_version_id,
        sourceTaskRunId=version.source_task_run_id,
        parentArtifactId=version.parent_artifact_id,
        gitBaseRef=version.git_base_ref,
        gitHeadRef=version.git_head_ref,
        changedFiles=version.changed_files,
        summary=version.summary,
        contentMd=version.content_md,
        contentHash=version.content_hash,
        editorSource=version.editor_source,
        createdAt=version.created_at,
    )


def artifact_workbench_response(
    metadata: ArtifactWorkbenchMetadata,
) -> ArtifactWorkbenchArtifactResponse:
    return ArtifactWorkbenchArtifactResponse(
        artifactId=metadata.artifact_id,
        taskRunId=metadata.task_run_id,
        artifactType=metadata.artifact_type,
        title=metadata.title,
        status=metadata.status,
        version=metadata.version,
        rendererKind=metadata.renderer_kind,
        editable=metadata.editable,
        contentHash=metadata.content_hash,
        safeMeta=metadata.safe_meta,
        versions=[
            artifact_workbench_version_response(version)
            for version in metadata.versions
        ],
        createdAt=metadata.created_at,
        updatedAt=metadata.updated_at,
    )


def review_response(review: StoredReviewArtifact) -> ReviewArtifactResponse:
    return ReviewArtifactResponse(
        id=review.id,
        artifactId=review.artifact_id,
        taskRunId=review.task_run_id,
        reviewedDiffArtifactId=review.reviewed_diff_artifact_id,
        artifactType=review.artifact_type,
        title=review.title,
        status=review.status,
        riskLevel=review.risk_level,
        summary=review.summary,
        filesReviewed=review.files_reviewed,
        findings=review.findings,
        suggestedChanges=review.suggested_changes,
        adapterType=review.adapter_type,
    )


def preview_response(preview: StoredPreviewArtifact) -> PreviewResponse:
    return PreviewResponse(
        id=preview.id,
        artifactId=preview.artifact_id,
        taskRunId=preview.task_run_id,
        artifactType=preview.artifact_type,
        title=preview.title,
        status=preview.status,
        port=preview.port,
        url=preview.url,
        command=preview.command,
        processId=preview.process_id,
        healthStatus=preview.health_status,
        statusReason=preview.status_reason,
        expiresAt=preview.expires_at,
        lastCheckedAt=preview.last_checked_at,
    )


def deployment_response(deployment: StoredDeploymentArtifact) -> DeploymentResponse:
    return DeploymentResponse(
        id=deployment.id,
        artifactId=deployment.artifact_id,
        taskRunId=deployment.task_run_id,
        artifactType=deployment.artifact_type,
        title=deployment.title,
        status=deployment.status,
        provider=deployment.provider,
        environment=deployment.environment,
        commitSha=deployment.commit_sha,
        url=deployment.url,
        deployLogUri=deployment.deploy_log_uri,
        providerType=deployment.provider_type,
        targetId=deployment.target_id,
        sourcePreviewId=deployment.source_preview_id,
        sourceDiffArtifactId=deployment.source_diff_artifact_id,
        sourceReviewArtifactId=deployment.source_review_artifact_id,
        logs=list(deployment.logs),
        statusHistory=list(deployment.status_history),
        createdAt=deployment.created_at,
        updatedAt=deployment.updated_at,
    )


def command_evidence_response(evidence: StoredCommandEvidence) -> CommandEvidenceResponse:
    return CommandEvidenceResponse(
        id=evidence.id,
        artifactId=evidence.artifact_id,
        taskRunId=evidence.task_run_id,
        artifactType=evidence.artifact_type,
        title=evidence.title,
        status=evidence.status,
        commandType=evidence.command_type,
        command=evidence.command,
        exitCode=evidence.exit_code,
        stdout=evidence.stdout,
        stderr=evidence.stderr,
        targetId=evidence.target_id,
        createdAt=evidence.created_at,
    )


@router.post(
    "/task-runs/{task_run_id}/diff",
    response_model=DiffArtifactResponse,
    status_code=status.HTTP_201_CREATED,
)
def collect_diff_for_task_run(
    task_run_id: str,
    db: DbSession = Depends(get_db),
) -> DiffArtifactResponse:
    if db.get(TaskRun, task_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TaskRun not found")
    _require_artifact_scope_passed(db, task_run_id)
    try:
        diff_artifact = collect_task_run_diff(db, task_run_id)
        create_scripted_review_for_task_run(db, task_run_id)
        refresh_session_ledger_for_task_run(db, task_run_id)
    except DiffCollectionError as exc:
        record_diff_collection_failure(db, task_run_id, exc)
        record_review_collection_failure(db, task_run_id, ReviewError("No diff artifact found for review."), skipped=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ReviewError as exc:
        record_review_collection_failure(db, task_run_id, exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return diff_artifact_response(diff_artifact)


@router.get("/task-runs/{task_run_id}/diffs", response_model=list[DiffArtifactResponse])
def read_task_run_diffs(
    task_run_id: str,
    db: DbSession = Depends(get_db),
) -> list[DiffArtifactResponse]:
    if db.get(TaskRun, task_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TaskRun not found")
    return [diff_artifact_response(diff) for diff in list_task_run_diffs(db, task_run_id)]


@router.get(
    "/sessions/{session_id}/artifact-workbench",
    response_model=ArtifactWorkbenchSessionResponse,
)
def read_session_artifact_workbench(
    session_id: str,
    db: DbSession = Depends(get_db),
) -> ArtifactWorkbenchSessionResponse:
    if db.get(AgentHubSession, session_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    try:
        artifacts = list_session_artifact_workbench(db, session_id)
    except ArtifactWorkbenchError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ArtifactWorkbenchSessionResponse(
        sessionId=session_id,
        artifacts=[artifact_workbench_response(artifact) for artifact in artifacts],
    )


@router.get(
    "/artifacts/{artifact_id}/workbench",
    response_model=ArtifactWorkbenchArtifactResponse,
)
def read_artifact_workbench(
    artifact_id: str,
    db: DbSession = Depends(get_db),
) -> ArtifactWorkbenchArtifactResponse:
    try:
        metadata = artifact_workbench_metadata_for_id(db, artifact_id)
    except ArtifactWorkbenchError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return artifact_workbench_response(metadata)


@router.get(
    "/artifacts/{artifact_id}/workbench/versions",
    response_model=list[ArtifactWorkbenchVersionResponse],
)
def read_artifact_workbench_versions(
    artifact_id: str,
    db: DbSession = Depends(get_db),
) -> list[ArtifactWorkbenchVersionResponse]:
    try:
        versions = list_artifact_workbench_versions(db, artifact_id)
        artifact = artifact_workbench_metadata_for_id(db, artifact_id)
    except ArtifactWorkbenchError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    version_metadata = {version.id: version for version in artifact.versions}
    return [
        artifact_workbench_version_response(version_metadata[version.id])
        for version in versions
        if version.id in version_metadata
    ]


@router.get(
    "/artifacts/{artifact_id}/workbench/versions/{version_id}",
    response_model=ArtifactWorkbenchVersionResponse,
)
def read_artifact_workbench_version(
    artifact_id: str,
    version_id: str,
    db: DbSession = Depends(get_db),
) -> ArtifactWorkbenchVersionResponse:
    try:
        version = artifact_workbench_version_for_id(db, artifact_id, version_id)
    except ArtifactWorkbenchError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return artifact_workbench_version_response(version)


@router.post(
    "/artifacts/{artifact_id}/workbench/edits",
    response_model=ArtifactWorkbenchVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_artifact_workbench_edit_route(
    artifact_id: str,
    request: ArtifactWorkbenchEditRequest,
    db: DbSession = Depends(get_db),
) -> ArtifactWorkbenchVersionResponse:
    try:
        version = save_artifact_workbench_edit(
            db,
            artifact_id,
            content_md=request.content_md,
            summary=request.summary,
            editor_source=request.editor_source,
        )
    except ArtifactWorkbenchError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if str(exc).startswith("Artifact not found")
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return artifact_workbench_version_response(version)


@router.get("/artifacts/{artifact_id}/versions", response_model=list[ArtifactVersionResponse])
def read_artifact_versions(
    artifact_id: str,
    db: DbSession = Depends(get_db),
) -> list[ArtifactVersionResponse]:
    try:
        versions = list_artifact_versions(db, artifact_id)
    except ArtifactVersionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [artifact_version_response(version) for version in versions]


@router.post(
    "/task-runs/{task_run_id}/review",
    response_model=ReviewArtifactResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_review_for_task_run(
    task_run_id: str,
    db: DbSession = Depends(get_db),
) -> ReviewArtifactResponse:
    if db.get(TaskRun, task_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TaskRun not found")
    _require_artifact_scope_passed(db, task_run_id)
    try:
        review = create_scripted_review_for_task_run(db, task_run_id)
        refresh_session_ledger_for_task_run(db, task_run_id)
    except ReviewError as exc:
        record_review_collection_failure(db, task_run_id, exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return review_response(review)


@router.get("/task-runs/{task_run_id}/reviews", response_model=list[ReviewArtifactResponse])
def read_task_run_reviews(
    task_run_id: str,
    db: DbSession = Depends(get_db),
) -> list[ReviewArtifactResponse]:
    if db.get(TaskRun, task_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TaskRun not found")
    return [review_response(review) for review in list_task_run_reviews(db, task_run_id)]


@router.post(
    "/task-runs/{task_run_id}/command-evidence",
    response_model=CommandEvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_command_evidence_for_task_run(
    task_run_id: str,
    request: CommandEvidenceCreateRequest,
    db: DbSession = Depends(get_db),
) -> CommandEvidenceResponse:
    try:
        evidence = record_command_evidence(
            db,
            task_run_id,
            command_type=request.command_type,
            command=request.command,
            exit_code=request.exit_code,
            stdout=request.stdout,
            stderr=request.stderr,
            target_id=request.target_id,
        )
    except ExternalEvidenceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return command_evidence_response(evidence)


@router.get(
    "/task-runs/{task_run_id}/command-evidence",
    response_model=list[CommandEvidenceResponse],
)
def read_task_run_command_evidence(
    task_run_id: str,
    db: DbSession = Depends(get_db),
) -> list[CommandEvidenceResponse]:
    if db.get(TaskRun, task_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TaskRun not found")
    return [
        command_evidence_response(evidence)
        for evidence in list_task_run_command_evidence(db, task_run_id)
    ]


@router.post(
    "/task-runs/{task_run_id}/preview",
    response_model=PreviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_preview_for_task_run(
    task_run_id: str,
    db: DbSession = Depends(get_db),
    previews: PreviewService = Depends(get_preview_service),
) -> PreviewResponse:
    _require_artifact_scope_passed(db, task_run_id)
    try:
        preview = previews.start_task_run_preview(db, task_run_id)
        if preview.health_status == "healthy":
            refresh_session_ledger_for_task_run(db, task_run_id)
    except PreviewError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return preview_response(preview)


@router.get("/task-runs/{task_run_id}/previews", response_model=list[PreviewResponse])
def read_task_run_previews(
    task_run_id: str,
    db: DbSession = Depends(get_db),
    previews: PreviewService = Depends(get_preview_service),
) -> list[PreviewResponse]:
    if db.get(TaskRun, task_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TaskRun not found")
    stored_previews = previews.list_task_run_previews(db, task_run_id)
    if any(preview.health_status == "healthy" for preview in stored_previews):
        refresh_session_ledger_for_task_run(db, task_run_id)
    return [
        preview_response(preview)
        for preview in stored_previews
    ]


@router.post("/previews/{preview_id}/stop", response_model=PreviewResponse)
def stop_existing_preview(
    preview_id: str,
    db: DbSession = Depends(get_db),
    previews: PreviewService = Depends(get_preview_service),
) -> PreviewResponse:
    try:
        preview = previews.stop_preview(db, preview_id)
    except PreviewError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return preview_response(preview)


@router.post(
    "/previews/{preview_id}/deploy",
    response_model=DeploymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_mock_deployment_for_preview(
    preview_id: str,
    request: DeploymentCreateRequest = DeploymentCreateRequest(),
    db: DbSession = Depends(get_db),
    deployments: DeployService = Depends(get_deploy_service),
) -> DeploymentResponse:
    source_task_run_id = _source_task_run_id_for_preview(db, preview_id)
    _require_artifact_scope_passed(db, source_task_run_id)
    try:
        deployment = deployments.create_deployment(
            db,
            preview_id,
            provider_id=request.provider_id,
            environment=request.environment,
        )
        refresh_session_ledger_for_task_run(db, deployment.task_run_id)
    except DeployError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return deployment_response(deployment)


def _require_artifact_scope_passed(db: DbSession, task_run_id: str) -> None:
    if db.get(TaskRun, task_run_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TaskRun not found",
        )
    try:
        require_task_run_artifact_scope_passed(db, task_run_id)
    except TaskRunScopeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{exc.error_code}: {exc.message}",
        ) from exc


def _source_task_run_id_for_preview(
    db: DbSession,
    preview_id: str,
) -> str:
    preview = db.get(Preview, preview_id)
    if preview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preview not found",
        )
    artifact = db.get(Artifact, preview.artifact_id)
    if artifact is None or artifact.artifact_type != "preview":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Preview source evidence is unavailable.",
        )
    if db.get(TaskRun, artifact.task_run_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Preview source TaskRun is unavailable.",
        )
    return artifact.task_run_id


@router.get("/task-runs/{task_run_id}/deployments", response_model=list[DeploymentResponse])
def read_task_run_deployments(
    task_run_id: str,
    db: DbSession = Depends(get_db),
    deployments: DeployService = Depends(get_deploy_service),
) -> list[DeploymentResponse]:
    if db.get(TaskRun, task_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TaskRun not found")
    return [
        deployment_response(deployment)
        for deployment in deployments.list_task_run_deployments(db, task_run_id)
    ]
