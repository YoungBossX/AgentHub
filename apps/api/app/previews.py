import json
import socket
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Optional, Protocol

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.events import append_task_run_event
from app.models import Artifact, Preview, Task, TaskRun, Workspace, utc_now
from app.models import Session as AgentHubSession


class PreviewError(ValueError):
    pass


@dataclass(frozen=True)
class PreviewProcess:
    pid: int


@dataclass(frozen=True)
class StoredPreviewArtifact:
    id: str
    artifact_id: str
    task_run_id: str
    artifact_type: str
    title: str
    status: str
    port: int
    url: str
    command: str
    process_id: Optional[int]
    health_status: str
    status_reason: Optional[str]
    expires_at: Optional[object]
    last_checked_at: Optional[object]


class PreviewProcessRunner(Protocol):
    def start(self, command: list[str], cwd: Path) -> PreviewProcess:
        ...

    def stop(self, process_id: int) -> None:
        ...


class PreviewHealthChecker(Protocol):
    def is_healthy(self, url: str) -> bool:
        ...


class SubprocessPreviewRunner:
    def __init__(self) -> None:
        self._processes: dict[int, subprocess.Popen] = {}

    def start(self, command: list[str], cwd: Path) -> PreviewProcess:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        self._processes[process.pid] = process
        return PreviewProcess(pid=process.pid)

    def stop(self, process_id: int) -> None:
        process = self._processes.pop(process_id, None)
        if process is None:
            return
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


class UrlPreviewHealthChecker:
    def __init__(self, timeout_seconds: float = 1.5) -> None:
        self.timeout_seconds = timeout_seconds

    def is_healthy(self, url: str) -> bool:
        try:
            with urllib.request.urlopen(url, timeout=self.timeout_seconds) as response:
                return 200 <= response.status < 500
        except (OSError, urllib.error.URLError):
            return False


class PreviewService:
    def __init__(
        self,
        process_runner: Optional[PreviewProcessRunner] = None,
        health_checker: Optional[PreviewHealthChecker] = None,
        port_allocator=None,
    ) -> None:
        self.process_runner = process_runner or SubprocessPreviewRunner()
        self.health_checker = health_checker or UrlPreviewHealthChecker()
        self.port_allocator = port_allocator or reserve_preview_port

    def start_task_run_preview(self, db: DbSession, task_run_id: str) -> StoredPreviewArtifact:
        task_run = db.get(TaskRun, task_run_id)
        if task_run is None:
            raise PreviewError(f"TaskRun not found: {task_run_id}")

        demo_root = _demo_root_for_task_run(db, task_run)
        if not demo_root.exists():
            raise PreviewError(f"Vite React demo root does not exist: {demo_root}")

        port = int(self.port_allocator())
        command = preview_command(port)
        url = f"http://127.0.0.1:{port}"
        process = self.process_runner.start(command, demo_root)
        checked_at = utc_now()
        healthy = self.health_checker.is_healthy(url)
        health_status = "healthy" if healthy else "unhealthy"
        status_reason = None if healthy else "Preview did not respond to the health check."
        artifact_status = "ready" if healthy else "unhealthy"
        now = utc_now()

        artifact = Artifact(
            task_run_id=task_run.id,
            artifact_type="preview",
            title="Vite React preview",
            status=artifact_status,
            meta_json=json.dumps(
                {
                    "port": port,
                    "url": url,
                    "command": command_text(command),
                    "healthStatus": health_status,
                },
                separators=(",", ":"),
            ),
            created_at=now,
            updated_at=now,
        )
        db.add(artifact)
        db.commit()
        db.refresh(artifact)

        preview = Preview(
            artifact_id=artifact.id,
            port=port,
            url=url,
            command=command_text(command),
            process_id=process.pid,
            health_status=health_status,
            status_reason=status_reason,
            expires_at=now + timedelta(hours=2),
            last_checked_at=checked_at,
            created_at=now,
            updated_at=now,
        )
        db.add(preview)
        db.commit()
        db.refresh(preview)

        if healthy:
            append_task_run_event(
                db,
                task_run_id=task_run.id,
                event_type="artifact.preview.ready",
                payload_json=json.dumps(
                    {
                        "artifactId": artifact.id,
                        "previewId": preview.id,
                        "url": url,
                        "port": port,
                        "healthStatus": health_status,
                    },
                    separators=(",", ":"),
                ),
            )

        return _to_stored_preview(artifact, preview)

    def list_task_run_previews(
        self,
        db: DbSession,
        task_run_id: str,
    ) -> list[StoredPreviewArtifact]:
        artifacts = db.exec(
            select(Artifact)
            .where(Artifact.task_run_id == task_run_id, Artifact.artifact_type == "preview")
            .order_by(Artifact.created_at, Artifact.id)
        ).all()
        previews: list[StoredPreviewArtifact] = []
        for artifact in artifacts:
            preview = db.exec(select(Preview).where(Preview.artifact_id == artifact.id)).first()
            if preview is not None:
                previews.append(_to_stored_preview(artifact, preview))
        return previews

    def stop_preview(self, db: DbSession, preview_id: str) -> StoredPreviewArtifact:
        preview = db.get(Preview, preview_id)
        if preview is None:
            raise PreviewError(f"Preview not found: {preview_id}")

        artifact = db.get(Artifact, preview.artifact_id)
        if artifact is None:
            raise PreviewError(f"Artifact not found for Preview: {preview_id}")

        if preview.process_id is not None:
            self.process_runner.stop(preview.process_id)

        now = utc_now()
        preview.health_status = "stopped"
        preview.status_reason = "Preview process was stopped."
        preview.last_checked_at = now
        preview.updated_at = now
        artifact.status = "stopped"
        artifact.updated_at = now
        db.add(preview)
        db.add(artifact)
        db.commit()
        db.refresh(preview)
        db.refresh(artifact)
        return _to_stored_preview(artifact, preview)


def preview_command(port: int) -> list[str]:
    return ["pnpm", "dev", "--host", "127.0.0.1", "--port", str(port)]


def command_text(command: list[str]) -> str:
    return " ".join(command)


def reserve_preview_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _demo_root_for_task_run(db: DbSession, task_run: TaskRun) -> Path:
    task = db.get(Task, task_run.task_id)
    if task is None:
        raise PreviewError(f"Task not found for TaskRun: {task_run.id}")
    session = db.get(AgentHubSession, task.session_id)
    if session is None:
        raise PreviewError(f"Session not found for TaskRun: {task_run.id}")
    workspace = db.get(Workspace, session.workspace_id)
    if workspace is None:
        raise PreviewError(f"Workspace not found for Session: {session.id}")
    return Path(session.worktree_path) / workspace.root_path


def _to_stored_preview(artifact: Artifact, preview: Preview) -> StoredPreviewArtifact:
    return StoredPreviewArtifact(
        id=preview.id,
        artifact_id=artifact.id,
        task_run_id=artifact.task_run_id,
        artifact_type=artifact.artifact_type,
        title=artifact.title,
        status=artifact.status,
        port=preview.port,
        url=preview.url,
        command=preview.command,
        process_id=preview.process_id,
        health_status=preview.health_status,
        status_reason=preview.status_reason,
        expires_at=preview.expires_at,
        last_checked_at=preview.last_checked_at,
    )
