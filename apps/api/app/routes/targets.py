from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session as DbSession

from app.dependencies import get_db
from app.external_workspaces import (
    ExternalWorkspaceRegistration,
    ExternalWorkspaceRegistrationError,
    allowed_paths_for,
    denied_paths_for,
    deploy_provider_ids_for,
    get_external_project_target,
    list_external_project_targets,
    register_external_project_target,
)
from app.local_folders import (
    LocalFolderBrowseError,
    LocalFolderListing,
    list_local_folders,
)
from app.models import ExternalProjectTarget
from app.project_analyzer import ProjectAnalysisResult, analyze_external_project
from app.project_provisioning import (
    ProjectProvisioningApplyError,
    ProjectProvisioningApplyResult,
    ProjectProvisioningPlan,
    apply_project_provisioning,
    plan_project_provisioning,
)
from app.repositories import get_session, get_workspace
from app.schemas import (
    ExternalProjectAnalysisRequest,
    ExternalProjectAnalysisResponse,
    ExternalProjectTargetCreateRequest,
    ExternalProjectTargetResponse,
    LocalFolderEntryResponse,
    LocalFolderListingResponse,
    LocalFolderStartResponse,
    ProjectProvisioningApplyRequest,
    ProjectProvisioningApplyResponse,
    ProjectProvisioningRequest,
    ProjectProvisioningResponse,
    TargetProjectResponse,
)
from app.target_registry import (
    TargetProject,
    external_target_to_project,
    list_targets_for_workspace,
)

router = APIRouter()


def external_target_response(
    target: ExternalProjectTarget,
) -> ExternalProjectTargetResponse:
    return ExternalProjectTargetResponse(
        id=target.id,
        workspaceId=target.workspace_id,
        targetId=target.target_id,
        name=target.name,
        rootPath=target.root_path,
        projectType=target.project_type,
        allowedPaths=allowed_paths_for(target),
        deniedPaths=denied_paths_for(target),
        devCommand=target.dev_command,
        testCommand=target.test_command,
        checkCommand=target.check_command,
        buildCommand=target.build_command,
        previewCommand=target.preview_command,
        stagingOutputDir=target.staging_output_dir,
        stagingServeCommand=target.staging_serve_command,
        deployProviderIds=deploy_provider_ids_for(target),
        packageManager=target.package_manager,
        detectedFramework=target.detected_framework,
        analysisStatus=target.analysis_status,
        projectProfile=external_target_to_project(target).project_profile.summary(),
        createdAt=target.created_at,
        updatedAt=target.updated_at,
    )


def external_project_analysis_response(
    analysis: ProjectAnalysisResult,
) -> ExternalProjectAnalysisResponse:
    return ExternalProjectAnalysisResponse(
        rootPath=analysis.root_path,
        projectType=analysis.project_type,
        detectedFramework=analysis.detected_framework,
        packageManager=analysis.package_manager,
        allowedPaths=list(analysis.allowed_paths),
        deniedPaths=list(analysis.denied_paths),
        devCommand=analysis.dev_command,
        testCommand=analysis.test_command,
        checkCommand=analysis.check_command,
        buildCommand=analysis.build_command,
        previewCommand=analysis.preview_command,
        analysisStatus=analysis.analysis_status,
        analysisWarnings=list(analysis.analysis_warnings),
        confidence=analysis.confidence,
        projectProfile=analysis.project_profile.summary(),
    )


def project_provisioning_response(
    plan: ProjectProvisioningPlan,
) -> ProjectProvisioningResponse:
    summary = plan.summary()
    return ProjectProvisioningResponse(
        projectKind=str(summary["projectKind"]),
        projectSlug=str(summary["projectSlug"]),
        projectRoot=str(summary["projectRoot"]),
        requiresFrontend=bool(summary["requiresFrontend"]),
        requiresBackend=bool(summary["requiresBackend"]),
        defaultFrontendStack=(
            summary["defaultFrontendStack"]
            if isinstance(summary["defaultFrontendStack"], str)
            else None
        ),
        defaultBackendStack=(
            summary["defaultBackendStack"]
            if isinstance(summary["defaultBackendStack"], str)
            else None
        ),
        targetDrafts=list(summary["targetDrafts"]),
        approvalRequiredCommands=list(summary["approvalRequiredCommands"]),
        setupSteps=list(summary["setupSteps"]),
        safeDefaultCommands=list(summary["safeDefaultCommands"]),
        notes=list(summary["notes"]),
    )


def project_provisioning_apply_response(
    result: ProjectProvisioningApplyResult,
) -> ProjectProvisioningApplyResponse:
    return ProjectProvisioningApplyResponse(
        plan=project_provisioning_response(result.plan),
        registeredTargets=[
            external_target_response(target) for target in result.registered_targets
        ],
        session=result.session,
    )


def local_folder_listing_response(
    listing: LocalFolderListing,
) -> LocalFolderListingResponse:
    return LocalFolderListingResponse(
        currentPath=listing.current_path,
        parentPath=listing.parent_path,
        starts=[
            LocalFolderStartResponse(label=start.label, path=start.path)
            for start in listing.starts
        ],
        children=[
            LocalFolderEntryResponse(name=child.name, path=child.path)
            for child in listing.children
        ],
    )


def target_project_response(target: TargetProject) -> TargetProjectResponse:
    return TargetProjectResponse(
        targetId=target.target_id,
        name=target.name,
        type=target.type,
        root=target.root,
        allowedPaths=list(target.allowed_paths),
        deniedPaths=list(target.denied_paths),
        devCommand=target.dev_command,
        testCommand=target.test_command,
        checkCommand=target.check_command,
        buildCommand=target.build_command,
        previewCommand=target.preview_command,
        stagingOutputDir=target.staging_output_dir,
        stagingServeCommand=target.staging_serve_command,
        deployProviderIds=list(target.deploy_provider_ids),
        baseUrl=target.base_url,
        packageManager=target.package_manager,
        detectedFramework=target.detected_framework,
        projectType=target.project_type,
        analysisStatus=target.analysis_status,
        projectProfile=(
            target.project_profile.summary() if target.project_profile is not None else None
        ),
        allowedAgents=list(target.allowed_agents),
        requiresPlatformMode=target.requires_platform_mode,
        requiresApproval=target.requires_approval,
        relatedTargetIds=list(target.related_target_ids),
    )


@router.get(
    "/workspaces/{workspace_id}/targets",
    response_model=list[TargetProjectResponse],
)
def read_workspace_targets(
    workspace_id: str,
    db: DbSession = Depends(get_db),
) -> list[TargetProjectResponse]:
    if get_workspace(db, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return [
        target_project_response(target)
        for target in list_targets_for_workspace(db, workspace_id)
    ]


@router.post(
    "/workspaces/{workspace_id}/external-targets/analyze",
    response_model=ExternalProjectAnalysisResponse,
)
def analyze_external_target(
    workspace_id: str,
    request: ExternalProjectAnalysisRequest,
    db: DbSession = Depends(get_db),
) -> ExternalProjectAnalysisResponse:
    if get_workspace(db, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return external_project_analysis_response(
        analyze_external_project(request.root_path)
    )


@router.post(
    "/workspaces/{workspace_id}/project-provisioning/plan",
    response_model=ProjectProvisioningResponse,
)
def plan_workspace_project_provisioning(
    workspace_id: str,
    request: ProjectProvisioningRequest,
    db: DbSession = Depends(get_db),
) -> ProjectProvisioningResponse:
    if get_workspace(db, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return project_provisioning_response(
        plan_project_provisioning(
            user_request=request.user_request,
            existing_project_root=request.existing_project_root,
            preferred_slug=request.preferred_slug,
        )
    )


@router.post(
    "/workspaces/{workspace_id}/project-provisioning/apply",
    response_model=ProjectProvisioningApplyResponse,
    status_code=status.HTTP_201_CREATED,
)
def apply_workspace_project_provisioning(
    workspace_id: str,
    request: ProjectProvisioningApplyRequest,
    db: DbSession = Depends(get_db),
) -> ProjectProvisioningApplyResponse:
    workspace = get_workspace(db, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    session = get_session(db, request.session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    try:
        result = apply_project_provisioning(
            db,
            workspace=workspace,
            session=session,
            user_request=request.user_request,
            selected_root_path=request.selected_root_path,
            preferred_slug=request.preferred_slug,
        )
    except ProjectProvisioningApplyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return project_provisioning_apply_response(result)


@router.get(
    "/workspaces/{workspace_id}/external-targets/folders",
    response_model=LocalFolderListingResponse,
)
def browse_external_target_folders(
    workspace_id: str,
    path: Optional[str] = Query(default=None),
    db: DbSession = Depends(get_db),
) -> LocalFolderListingResponse:
    workspace = get_workspace(db, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    try:
        return local_folder_listing_response(
            list_local_folders(
                workspace_root=workspace.root_path,
                requested_path=path,
            )
        )
    except LocalFolderBrowseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/workspaces/{workspace_id}/external-targets",
    response_model=ExternalProjectTargetResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_external_target(
    workspace_id: str,
    request: ExternalProjectTargetCreateRequest,
    db: DbSession = Depends(get_db),
) -> ExternalProjectTargetResponse:
    workspace = get_workspace(db, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    try:
        target = register_external_project_target(
            db,
            workspace,
            ExternalWorkspaceRegistration(
                target_id=request.target_id,
                name=request.name,
                root_path=request.root_path,
                project_type=request.project_type,
                allowed_paths=request.allowed_paths,
                denied_paths=request.denied_paths,
                dev_command=request.dev_command,
                test_command=request.test_command,
                check_command=request.check_command,
                build_command=request.build_command,
                preview_command=request.preview_command,
                staging_output_dir=request.staging_output_dir,
                staging_serve_command=request.staging_serve_command,
                deploy_provider_ids=request.deploy_provider_ids,
                package_manager=request.package_manager,
                detected_framework=request.detected_framework,
            ),
        )
    except ExternalWorkspaceRegistrationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return external_target_response(target)


@router.get(
    "/workspaces/{workspace_id}/external-targets",
    response_model=list[ExternalProjectTargetResponse],
)
def read_external_targets(
    workspace_id: str,
    db: DbSession = Depends(get_db),
) -> list[ExternalProjectTargetResponse]:
    if get_workspace(db, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return [
        external_target_response(target)
        for target in list_external_project_targets(db, workspace_id)
    ]


@router.get(
    "/workspaces/{workspace_id}/external-targets/{target_id}",
    response_model=ExternalProjectTargetResponse,
)
def read_external_target(
    workspace_id: str,
    target_id: str,
    db: DbSession = Depends(get_db),
) -> ExternalProjectTargetResponse:
    if get_workspace(db, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    target = get_external_project_target(db, workspace_id, target_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="External target not found",
        )
    return external_target_response(target)
