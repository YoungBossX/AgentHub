import json
from dataclasses import dataclass
from typing import Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.events import append_task_run_event
from app.models import Artifact, Deployment, Preview, TaskRun, utc_now


class DeployError(ValueError):
    pass


@dataclass(frozen=True)
class StoredDeploymentArtifact:
    id: str
    artifact_id: str
    task_run_id: str
    artifact_type: str
    title: str
    status: str
    provider: str
    environment: str
    commit_sha: Optional[str]
    url: Optional[str]
    deploy_log_uri: Optional[str]
    created_at: object
    updated_at: object


class DeployService:
    def create_mock_deployment(
        self,
        db: DbSession,
        preview_id: str,
    ) -> StoredDeploymentArtifact:
        preview = db.get(Preview, preview_id)
        if preview is None:
            raise DeployError(f"Preview not found: {preview_id}")
        if preview.health_status != "healthy":
            raise DeployError("Mock deployment requires a healthy preview")

        preview_artifact = db.get(Artifact, preview.artifact_id)
        if preview_artifact is None:
            raise DeployError(f"Artifact not found for Preview: {preview_id}")

        task_run = db.get(TaskRun, preview_artifact.task_run_id)
        if task_run is None:
            raise DeployError(f"TaskRun not found for Preview: {preview_id}")

        now = utc_now()
        commit_sha = task_run.head_ref or task_run.base_ref or f"worktree:{task_run.id}"
        artifact = Artifact(
            task_run_id=task_run.id,
            artifact_type="deployment",
            title="Mock deploy",
            status="ready",
            meta_json=json.dumps(
                {
                    "previewId": preview.id,
                    "provider": "mock",
                    "environment": "preview",
                    "commitSha": commit_sha,
                },
                separators=(",", ":"),
            ),
            created_at=now,
            updated_at=now,
        )
        deployment = Deployment(
            artifact_id=artifact.id,
            provider="mock",
            environment="preview",
            commit_sha=commit_sha,
            status="ready",
            created_at=now,
            updated_at=now,
        )
        deployment.url = f"https://mock.agenthub.local/deployments/{deployment.id}"
        deployment.deploy_log_uri = f"mock://deployments/{deployment.id}/logs"

        db.add(artifact)
        db.add(deployment)
        db.commit()
        db.refresh(artifact)
        db.refresh(deployment)

        append_task_run_event(
            db,
            task_run_id=task_run.id,
            event_type="artifact.deploy.ready",
            payload_json=json.dumps(
                {
                    "artifactId": artifact.id,
                    "deploymentId": deployment.id,
                    "provider": deployment.provider,
                    "environment": deployment.environment,
                    "status": deployment.status,
                    "url": deployment.url,
                    "commitSha": deployment.commit_sha,
                },
                separators=(",", ":"),
            ),
        )

        return _to_stored_deployment(artifact, deployment)

    def list_task_run_deployments(
        self,
        db: DbSession,
        task_run_id: str,
    ) -> list[StoredDeploymentArtifact]:
        artifacts = db.exec(
            select(Artifact)
            .where(Artifact.task_run_id == task_run_id, Artifact.artifact_type == "deployment")
            .order_by(Artifact.created_at, Artifact.id)
        ).all()
        deployments: list[StoredDeploymentArtifact] = []
        for artifact in artifacts:
            deployment = db.exec(
                select(Deployment).where(Deployment.artifact_id == artifact.id)
            ).first()
            if deployment is not None:
                deployments.append(_to_stored_deployment(artifact, deployment))
        return deployments


def _to_stored_deployment(
    artifact: Artifact,
    deployment: Deployment,
) -> StoredDeploymentArtifact:
    return StoredDeploymentArtifact(
        id=deployment.id,
        artifact_id=artifact.id,
        task_run_id=artifact.task_run_id,
        artifact_type=artifact.artifact_type,
        title=artifact.title,
        status=artifact.status,
        provider=deployment.provider,
        environment=deployment.environment,
        commit_sha=deployment.commit_sha,
        url=deployment.url,
        deploy_log_uri=deployment.deploy_log_uri,
        created_at=deployment.created_at,
        updated_at=deployment.updated_at,
    )
