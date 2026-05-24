import json
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.events import append_task_run_event
from app.models import Artifact, Deployment, Preview, Task, TaskRun, Workspace, new_id, utc_now
from app.models import Session as AgentHubSession
from app.previews import UrlPreviewHealthChecker, reserve_preview_port
from app.scheduler import DEPENDENCY_COMPLETE_STATUSES, dependency_ids_for_task
from app.target_registry import (
    DEMO_FRONTEND_TARGET_ID,
    TargetProject,
    TargetRegistryError,
    get_target_for_workspace,
    resolve_deploy_config,
)


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


@dataclass(frozen=True)
class DeployProviderResult:
    provider_id: str
    provider_type: str
    target_id: str
    build_command: Optional[str]
    deploy_command: Optional[str]
    output_url: Optional[str]
    status: str
    logs: tuple[str, ...]
    environment: str = "staging"

    def to_metadata(self) -> dict[str, object]:
        return {
            "providerId": self.provider_id,
            "providerType": self.provider_type,
            "targetId": self.target_id,
            "buildCommand": self.build_command,
            "deployCommand": self.deploy_command,
            "outputUrl": self.output_url,
            "status": self.status,
            "logs": list(self.logs),
            "environment": self.environment,
        }


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class StagingServerProcess:
    pid: int
    url: str
    command: str


class SubprocessCommandRunner:
    def run(self, command: str, cwd: Path) -> CommandResult:
        process = subprocess.run(
            shlex.split(command),
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        return CommandResult(
            exit_code=process.returncode,
            stdout=process.stdout,
            stderr=process.stderr,
        )


class StaticDirectoryServer:
    def start(self, output_dir: Path, port: int) -> StagingServerProcess:
        command = [
            "python",
            "-m",
            "http.server",
            str(port),
            "--bind",
            "127.0.0.1",
            "--directory",
            str(output_dir),
        ]
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return StagingServerProcess(
            pid=process.pid,
            url=f"http://127.0.0.1:{port}",
            command=" ".join(command),
        )


class MockDeployProvider:
    provider_id = "mock"
    provider_type = "mock"

    def deploy(
        self,
        *,
        db: DbSession,
        preview: Preview,
        preview_artifact: Artifact,
        task_run: TaskRun,
        deployment_id: str,
    ) -> DeployProviderResult:
        return DeployProviderResult(
            provider_id=self.provider_id,
            provider_type=self.provider_type,
            target_id=DEMO_FRONTEND_TARGET_ID,
            build_command=None,
            deploy_command="mock deploy preview",
            output_url=f"https://mock.agenthub.local/deployments/{deployment_id}",
            status="ready",
            logs=(
                f"Mock deploy accepted healthy preview {preview.id}.",
                f"Source TaskRun {task_run.id} was completed.",
            ),
            environment="preview",
        )


class LocalStagingDeployProvider:
    provider_id = "local_staging"
    provider_type = "local_staging"

    def __init__(
        self,
        *,
        command_runner: Optional[object] = None,
        static_server: Optional[object] = None,
        health_checker: Optional[object] = None,
        port_allocator=None,
        health_attempts: int = 20,
        health_interval_seconds: float = 0.25,
    ) -> None:
        self.command_runner = command_runner or SubprocessCommandRunner()
        self.static_server = static_server or StaticDirectoryServer()
        self.health_checker = health_checker or UrlPreviewHealthChecker()
        self.port_allocator = port_allocator or reserve_preview_port
        self.health_attempts = health_attempts
        self.health_interval_seconds = health_interval_seconds

    def deploy(
        self,
        *,
        db: DbSession,
        preview: Preview,
        preview_artifact: Artifact,
        task_run: TaskRun,
        deployment_id: str,
    ) -> DeployProviderResult:
        target = _target_for_task_run(db, task_run)
        config = resolve_deploy_config(target)
        target_root = _target_root_for_task_run(target, task_run)
        logs = [
            f"Local staging deploy requested for preview {preview.id}.",
            f"Target: {target.target_id} ({target.root}).",
            f"Build command: {config.build_command}",
        ]

        build = self.command_runner.run(config.build_command, target_root)
        if build.stdout:
            logs.append(build.stdout)
        if build.stderr:
            logs.append(build.stderr)
        if build.exit_code != 0:
            return DeployProviderResult(
                provider_id=self.provider_id,
                provider_type=self.provider_type,
                target_id=target.target_id,
                build_command=config.build_command,
                deploy_command=config.serve_command,
                output_url=None,
                status="failed",
                logs=tuple([*logs, f"Build command failed with exit code {build.exit_code}."]),
                environment="staging",
            )

        output_dir = _output_dir_for_target(target_root, config.output_dir)
        if not output_dir.exists() or not output_dir.is_dir():
            return DeployProviderResult(
                provider_id=self.provider_id,
                provider_type=self.provider_type,
                target_id=target.target_id,
                build_command=config.build_command,
                deploy_command=config.serve_command,
                output_url=None,
                status="failed",
                logs=tuple([*logs, f"Staging output directory missing: {output_dir}."]),
                environment="staging",
            )

        port = int(self.port_allocator())
        server = self.static_server.start(output_dir, port)
        logs.append(f"Serving {output_dir} at {server.url}.")
        healthy = self._wait_until_healthy(server.url)
        if not healthy:
            return DeployProviderResult(
                provider_id=self.provider_id,
                provider_type=self.provider_type,
                target_id=target.target_id,
                build_command=config.build_command,
                deploy_command=server.command,
                output_url=server.url,
                status="failed",
                logs=tuple([*logs, "Staging URL did not pass health check."]),
                environment="staging",
            )

        return DeployProviderResult(
            provider_id=self.provider_id,
            provider_type=self.provider_type,
            target_id=target.target_id,
            build_command=config.build_command,
            deploy_command=server.command,
            output_url=server.url,
            status="ready",
            logs=tuple([*logs, "Local staging deploy is ready."]),
            environment="staging",
        )

    def _wait_until_healthy(self, url: str) -> bool:
        attempts = max(1, self.health_attempts)
        for index in range(attempts):
            if self.health_checker.is_healthy(url):
                return True
            if index < attempts - 1:
                time.sleep(self.health_interval_seconds)
        return False


class DeployService:
    def __init__(self, providers: Optional[Iterable[object]] = None) -> None:
        configured_providers = (
            tuple(providers)
            if providers is not None
            else (MockDeployProvider(), LocalStagingDeployProvider())
        )
        self._providers = {
            str(provider.provider_id): provider for provider in configured_providers
        }

    def create_deployment(
        self,
        db: DbSession,
        preview_id: str,
        *,
        provider_id: str = "mock",
    ) -> StoredDeploymentArtifact:
        provider = self._providers.get(provider_id)
        if provider is None:
            raise DeployError(f"Unknown deploy provider: {provider_id}")

        preview, preview_artifact, task_run = _load_deploy_context(db, preview_id)
        _ensure_deploy_prerequisites(db, task_run)

        deployment_id = new_id()
        provider_result = provider.deploy(
            db=db,
            preview=preview,
            preview_artifact=preview_artifact,
            task_run=task_run,
            deployment_id=deployment_id,
        )
        if provider_result.status != "ready":
            reason = provider_result.logs[-1] if provider_result.logs else provider_result.status
            raise DeployError(
                f"Deploy provider {provider_result.provider_id} failed with status "
                f"{provider_result.status}: {reason}"
            )

        return self._persist_provider_deployment(
            db,
            preview=preview,
            preview_artifact=preview_artifact,
            task_run=task_run,
            deployment_id=deployment_id,
            provider_result=provider_result,
        )

    def create_mock_deployment(
        self,
        db: DbSession,
        preview_id: str,
    ) -> StoredDeploymentArtifact:
        return self.create_deployment(db, preview_id, provider_id="mock")

    def _persist_provider_deployment(
        self,
        db: DbSession,
        *,
        preview: Preview,
        preview_artifact: Artifact,
        task_run: TaskRun,
        deployment_id: str,
        provider_result: DeployProviderResult,
    ) -> StoredDeploymentArtifact:
        now = utc_now()
        commit_sha = task_run.head_ref or task_run.base_ref or f"worktree:{task_run.id}"
        artifact = Artifact(
            task_run_id=task_run.id,
            artifact_type="deployment",
            title="Mock deploy" if provider_result.provider_id == "mock" else "Staging deploy",
            status=provider_result.status,
            meta_json=json.dumps(
                {
                    "previewId": preview.id,
                    "previewArtifactId": preview_artifact.id,
                    "provider": provider_result.provider_id,
                    "providerType": provider_result.provider_type,
                    "targetId": provider_result.target_id,
                    "environment": provider_result.environment,
                    "commitSha": commit_sha,
                    "providerResult": provider_result.to_metadata(),
                },
                separators=(",", ":"),
            ),
            created_at=now,
            updated_at=now,
        )
        deployment = Deployment(
            id=deployment_id,
            artifact_id=artifact.id,
            provider=provider_result.provider_id,
            environment=provider_result.environment,
            commit_sha=commit_sha,
            status=provider_result.status,
            created_at=now,
            updated_at=now,
        )
        deployment.url = provider_result.output_url
        deployment.deploy_log_uri = f"{provider_result.provider_id}://deployments/{deployment.id}/logs"

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
                    "providerType": provider_result.provider_type,
                    "targetId": provider_result.target_id,
                    "environment": deployment.environment,
                    "status": deployment.status,
                    "url": deployment.url,
                    "commitSha": deployment.commit_sha,
                    "logs": list(provider_result.logs),
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


def _load_deploy_context(
    db: DbSession,
    preview_id: str,
) -> tuple[Preview, Artifact, TaskRun]:
    preview = db.get(Preview, preview_id)
    if preview is None:
        raise DeployError(f"Preview not found: {preview_id}")
    if preview.health_status != "healthy":
        raise DeployError("Deployment requires a healthy preview")

    preview_artifact = db.get(Artifact, preview.artifact_id)
    if preview_artifact is None:
        raise DeployError(f"Artifact not found for Preview: {preview_id}")

    task_run = db.get(TaskRun, preview_artifact.task_run_id)
    if task_run is None:
        raise DeployError(f"TaskRun not found for Preview: {preview_id}")
    return preview, preview_artifact, task_run


def _target_for_task_run(db: DbSession, task_run: TaskRun) -> TargetProject:
    task = db.get(Task, task_run.task_id)
    if task is None:
        raise DeployError(f"Task not found for TaskRun: {task_run.id}")
    session = db.get(AgentHubSession, task.session_id)
    if session is None:
        raise DeployError(f"Session not found for TaskRun: {task_run.id}")
    workspace = db.get(Workspace, session.workspace_id)
    if workspace is None:
        raise DeployError(f"Workspace not found for Session: {session.id}")

    target_id = _target_id_for_task(task)
    try:
        return get_target_for_workspace(db, workspace.id, target_id)
    except TargetRegistryError as exc:
        raise DeployError(str(exc)) from exc


def _target_id_for_task(task: Task) -> str:
    try:
        plan = json.loads(task.plan_json)
    except json.JSONDecodeError:
        plan = {}
    if isinstance(plan, dict):
        target_id = plan.get("targetId") or plan.get("frontendTargetId")
        if isinstance(target_id, str) and target_id:
            return target_id
    return DEMO_FRONTEND_TARGET_ID


def _target_root_for_task_run(target: TargetProject, task_run: TaskRun) -> Path:
    root = Path(target.root)
    if root.is_absolute():
        return root
    return Path(task_run.worktree_path) / root


def _output_dir_for_target(target_root: Path, output_dir: str) -> Path:
    path = Path(output_dir)
    if path.is_absolute():
        return path
    return target_root / path


def _ensure_deploy_prerequisites(db: DbSession, task_run: TaskRun) -> None:
    if task_run.state != "completed":
        raise DeployError("Deployment requires a completed TaskRun.")

    task = db.get(Task, task_run.task_id)
    if task is None:
        raise DeployError(f"Task not found for TaskRun: {task_run.id}")

    incomplete_dependencies: list[str] = []
    for dependency_id in dependency_ids_for_task(task):
        dependency = db.get(Task, dependency_id)
        if dependency is None or dependency.status not in DEPENDENCY_COMPLETE_STATUSES:
            incomplete_dependencies.append(dependency_id)
    if incomplete_dependencies:
        raise DeployError(
            "Deployment blocked by failed prerequisite or incomplete dependency: "
            + ", ".join(incomplete_dependencies)
        )


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
