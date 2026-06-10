import http.client
import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.parse
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Optional, Protocol

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.artifact_versions import record_artifact_version
from app.events import append_task_run_event
from app.models import Artifact, Preview, Task, TaskRun, Workspace, utc_now
from app.models import Session as AgentHubSession
from app.provider_evidence import provider_evidence_for_task_run
from app.scheduler import DEPENDENCY_COMPLETE_STATUSES, dependency_ids_for_task
from app.target_registry import (
    DEMO_FRONTEND_TARGET_ID,
    TargetProject,
    TargetRegistryError,
    get_target_for_workspace,
)


class PreviewError(ValueError):
    pass


@dataclass(frozen=True)
class PreviewProcess:
    pid: int
    log_path: Optional[Path] = None


@dataclass(frozen=True)
class PreviewProcessDiagnostics:
    running: bool
    exit_code: Optional[int] = None
    output_tail: str = ""
    log_path: Optional[Path] = None


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

    def diagnostics(self, process_id: int) -> PreviewProcessDiagnostics:
        ...


class PreviewHealthChecker(Protocol):
    def is_healthy(self, url: str) -> bool:
        ...


class SubprocessPreviewRunner:
    def __init__(self) -> None:
        self._processes: dict[int, subprocess.Popen] = {}
        self._log_paths: dict[int, Path] = {}
        self._log_files: dict[int, object] = {}

    def start(self, command: list[str], cwd: Path) -> PreviewProcess:
        log_file = tempfile.NamedTemporaryFile(
            mode="w+",
            encoding="utf-8",
            prefix="agenthub-preview-",
            suffix=".log",
            delete=False,
        )
        log_path = Path(log_file.name)
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=_preview_process_env(),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except OSError:
            try:
                log_file.close()
            except OSError:
                pass
            try:
                if log_path.exists():
                    log_path.unlink()
            except OSError:
                pass
            raise
        self._processes[process.pid] = process
        self._log_paths[process.pid] = log_path
        self._log_files[process.pid] = log_file
        return PreviewProcess(pid=process.pid, log_path=log_path)

    def stop(self, process_id: int) -> None:
        process = self._processes.pop(process_id, None)
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        self._close_log_file(process_id)

    def diagnostics(self, process_id: int) -> PreviewProcessDiagnostics:
        process = self._processes.get(process_id)
        self._flush_log_file(process_id)
        log_path = self._log_paths.get(process_id)
        if process is None:
            return PreviewProcessDiagnostics(
                running=False,
                output_tail=_read_log_tail(log_path),
                log_path=log_path,
            )
        exit_code = process.poll()
        return PreviewProcessDiagnostics(
            running=exit_code is None,
            exit_code=exit_code,
            output_tail=_read_log_tail(log_path),
            log_path=log_path,
        )

    def _close_log_file(self, process_id: int) -> None:
        self._flush_log_file(process_id)
        log_file = self._log_files.pop(process_id, None)
        if log_file is not None:
            try:
                log_file.close()
            except OSError:
                pass

    def _flush_log_file(self, process_id: int) -> None:
        log_file = self._log_files.get(process_id)
        if log_file is not None:
            try:
                log_file.flush()
            except OSError:
                pass


class UrlPreviewHealthChecker:
    def __init__(self, timeout_seconds: float = 1.5) -> None:
        self.timeout_seconds = timeout_seconds

    def is_healthy(self, url: str) -> bool:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "http" or parsed.hostname is None or parsed.port is None:
            return False
        connection = http.client.HTTPConnection(
            parsed.hostname,
            parsed.port,
            timeout=self.timeout_seconds,
        )
        try:
            connection.request("HEAD", parsed.path or "/")
            response = connection.getresponse()
            return 200 <= response.status < 500
        except OSError:
            return False
        finally:
            connection.close()


class PreviewService:
    def __init__(
        self,
        process_runner: Optional[PreviewProcessRunner] = None,
        health_checker: Optional[PreviewHealthChecker] = None,
        port_allocator=None,
        health_attempts: int = 60,
        health_interval_seconds: float = 0.25,
    ) -> None:
        self.process_runner = process_runner or SubprocessPreviewRunner()
        self.health_checker = health_checker or UrlPreviewHealthChecker()
        self.port_allocator = port_allocator or reserve_preview_port
        self.health_attempts = health_attempts
        self.health_interval_seconds = health_interval_seconds

    def start_task_run_preview(self, db: DbSession, task_run_id: str) -> StoredPreviewArtifact:
        task_run = db.get(TaskRun, task_run_id)
        if task_run is None:
            raise PreviewError(f"TaskRun not found: {task_run_id}")
        _ensure_preview_prerequisites(db, task_run)

        preview_target = _preview_target_for_task_run(db, task_run)
        _ensure_previewable_target(preview_target)
        preview_root = _target_root_for_preview(preview_target, task_run)
        if not preview_root.exists():
            raise PreviewError(f"Vite React preview root does not exist: {preview_root}")

        port = int(self.port_allocator())
        command = preview_command(port)
        url = f"http://127.0.0.1:{port}"
        try:
            process = self.process_runner.start(command, preview_root)
        except OSError as exc:
            raise PreviewError(f"Preview process could not start: {exc}") from exc
        checked_at = utc_now()
        healthy = self._wait_until_healthy(url, process.pid)
        diagnostics = self.process_runner.diagnostics(process.pid)
        healthy = healthy and diagnostics.running
        health_status = "healthy" if healthy else "unhealthy"
        status_reason = None if healthy else _preview_failure_reason(diagnostics)
        artifact_status = "ready" if healthy else "failed"
        process_id = process.pid if healthy else None
        if not healthy:
            self.process_runner.stop(process.pid)
        now = utc_now()
        provider_evidence = provider_evidence_for_task_run(
            db,
            task_run,
            logs=_preview_evidence_logs(health_status, diagnostics),
        )

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
                    "statusReason": status_reason,
                    "processDiagnostics": _diagnostics_metadata(diagnostics),
                    "providerEvidence": provider_evidence,
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
            process_id=process_id,
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

        record_artifact_version(
            db,
            artifact,
            source_task_run_id=task_run.id,
            git_base_ref=task_run.base_ref,
            git_head_ref=task_run.head_ref,
            summary=f"Preview became {health_status} at {url}.",
        )

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
                        "providerEvidence": {
                            **provider_evidence,
                            "artifactRefs": {"previewArtifactId": artifact.id},
                        },
                    },
                    separators=(",", ":"),
                ),
            )

        if not healthy:
            append_task_run_event(
                db,
                task_run_id=task_run.id,
                event_type="artifact.preview.failed",
                payload_json=json.dumps(
                    {
                        "artifactId": artifact.id,
                        "previewId": preview.id,
                        "url": url,
                        "port": port,
                        "healthStatus": health_status,
                        "statusReason": status_reason,
                        "processDiagnostics": _diagnostics_metadata(diagnostics),
                        "providerEvidence": {
                            **provider_evidence,
                            "artifactRefs": {"previewArtifactId": artifact.id},
                        },
                    },
                    separators=(",", ":"),
                ),
            )

        return _to_stored_preview(artifact, preview)

    def _wait_until_healthy(self, url: str, process_id: Optional[int] = None) -> bool:
        attempts = max(1, self.health_attempts)
        for index in range(attempts):
            if process_id is not None and not self.process_runner.diagnostics(process_id).running:
                return False
            if self.health_checker.is_healthy(url):
                return True
            if index < attempts - 1:
                time.sleep(self.health_interval_seconds)
        return False

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
                self._refresh_preview_health(db, artifact, preview)
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

    def _refresh_preview_health(
        self,
        db: DbSession,
        artifact: Artifact,
        preview: Preview,
    ) -> None:
        if preview.health_status == "stopped" or preview.process_id is None:
            return

        checked_at = utc_now()
        diagnostics = self.process_runner.diagnostics(preview.process_id)
        if not diagnostics.running:
            self.process_runner.stop(preview.process_id)
            preview.process_id = None
            preview.health_status = "unhealthy"
            preview.status_reason = _preview_failure_reason(diagnostics)
            preview.last_checked_at = checked_at
            preview.updated_at = checked_at
            artifact.status = "failed"
            artifact.updated_at = checked_at
            db.add(preview)
            db.add(artifact)
            db.commit()
            db.refresh(preview)
            db.refresh(artifact)
            append_task_run_event(
                db,
                task_run_id=artifact.task_run_id,
                event_type="artifact.preview.failed",
                payload_json=json.dumps(
                    {
                        "artifactId": artifact.id,
                        "previewId": preview.id,
                        "url": preview.url,
                        "port": preview.port,
                        "healthStatus": preview.health_status,
                        "statusReason": preview.status_reason,
                        "processDiagnostics": _diagnostics_metadata(diagnostics),
                    },
                    separators=(",", ":"),
                ),
            )
            return

        healthy = self.health_checker.is_healthy(preview.url)
        if healthy and preview.health_status != "healthy":
            preview.health_status = "healthy"
            preview.status_reason = None
            preview.last_checked_at = checked_at
            preview.updated_at = checked_at
            artifact.status = "ready"
            artifact.updated_at = checked_at
            db.add(preview)
            db.add(artifact)
            db.commit()
            db.refresh(preview)
            db.refresh(artifact)
            append_task_run_event(
                db,
                task_run_id=artifact.task_run_id,
                event_type="artifact.preview.ready",
                payload_json=json.dumps(
                    {
                        "artifactId": artifact.id,
                        "previewId": preview.id,
                        "url": preview.url,
                        "port": preview.port,
                        "healthStatus": preview.health_status,
                    },
                    separators=(",", ":"),
                ),
            )
            return

        if not healthy:
            self.process_runner.stop(preview.process_id)
            preview.process_id = None
            preview.health_status = "unhealthy"
            preview.status_reason = _preview_failure_reason(diagnostics)
            preview.last_checked_at = checked_at
            preview.updated_at = checked_at
            artifact.status = "failed"
            artifact.updated_at = checked_at
            db.add(preview)
            db.add(artifact)
            db.commit()
            db.refresh(preview)
            db.refresh(artifact)
            append_task_run_event(
                db,
                task_run_id=artifact.task_run_id,
                event_type="artifact.preview.failed",
                payload_json=json.dumps(
                    {
                        "artifactId": artifact.id,
                        "previewId": preview.id,
                        "url": preview.url,
                        "port": preview.port,
                        "healthStatus": preview.health_status,
                        "statusReason": preview.status_reason,
                        "processDiagnostics": _diagnostics_metadata(diagnostics),
                    },
                    separators=(",", ":"),
                ),
            )


def preview_command(port: int) -> list[str]:
    return ["pnpm", "dev", "--host", "127.0.0.1", "--port", str(port)]


def command_text(command: list[str]) -> str:
    return " ".join(command)


def _preview_process_env(base_env: Optional[Mapping[str, str]] = None) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    env.pop("NODE", None)

    current_path = env.get("PATH", "")
    path_candidates = [
        str(Path.home() / ".npm-global" / "bin"),
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
        *current_path.split(os.pathsep),
    ]
    deduped_paths: list[str] = []
    for item in path_candidates:
        if not item or _is_codex_bundled_runtime_path(item) or item in deduped_paths:
            continue
        deduped_paths.append(item)
    env["PATH"] = os.pathsep.join(deduped_paths)
    return env


def _is_codex_bundled_runtime_path(path: str) -> bool:
    return "/Applications/Codex.app/Contents/Resources" in path


def reserve_preview_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _read_log_tail(log_path: Optional[Path], limit: int = 2000) -> str:
    if log_path is None or not log_path.exists():
        return ""
    try:
        return log_path.read_text(encoding="utf-8", errors="replace")[-limit:].strip()
    except OSError:
        return ""


def _preview_failure_reason(diagnostics: PreviewProcessDiagnostics) -> str:
    if diagnostics.exit_code is not None:
        base = f"Preview process exited before becoming healthy (exit code {diagnostics.exit_code})."
    elif not diagnostics.running:
        base = "Preview process exited before becoming healthy."
    else:
        base = "Preview did not respond to the health check."
    output = _compact_log_excerpt(diagnostics.output_tail)
    if output:
        return f"{base} Recent preview output: {output}"
    return base


def _preview_evidence_logs(
    health_status: str,
    diagnostics: PreviewProcessDiagnostics,
) -> list[str]:
    logs = [f"Preview health status: {health_status}."]
    output = _compact_log_excerpt(diagnostics.output_tail)
    if output:
        logs.append(f"Preview output: {output}")
    return logs


def _diagnostics_metadata(diagnostics: PreviewProcessDiagnostics) -> dict[str, object]:
    return {
        "running": diagnostics.running,
        "exitCode": diagnostics.exit_code,
        "outputTail": _compact_log_excerpt(diagnostics.output_tail),
    }


def _compact_log_excerpt(value: str, limit: int = 1000) -> str:
    text = " ".join(value.replace("\r", "\n").split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _preview_target_for_task_run(db: DbSession, task_run: TaskRun) -> TargetProject:
    task = db.get(Task, task_run.task_id)
    if task is None:
        raise PreviewError(f"Task not found for TaskRun: {task_run.id}")
    session = db.get(AgentHubSession, task.session_id)
    if session is None:
        raise PreviewError(f"Session not found for TaskRun: {task_run.id}")
    workspace = db.get(Workspace, session.workspace_id)
    if workspace is None:
        raise PreviewError(f"Workspace not found for Session: {session.id}")

    target_id = _target_id_for_task(task)
    try:
        target = get_target_for_workspace(db, workspace.id, target_id)
    except TargetRegistryError as exc:
        raise PreviewError(str(exc)) from exc
    return target


def _ensure_previewable_target(target: TargetProject) -> None:
    if target.type != "frontend" or not target.preview_command:
        raise PreviewError(
            f"Target {target.target_id} does not support Vite preview. "
            "Start preview from a frontend Vite target instead."
        )
    framework = (target.detected_framework or target.project_type or "").lower()
    if framework and "vite" not in framework:
        raise PreviewError(
            f"Target {target.target_id} does not support Vite preview "
            f"(detected framework: {framework})."
        )


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


def _target_root_for_preview(target: TargetProject, task_run: TaskRun) -> Path:
    root = Path(target.root)
    if root.is_absolute():
        return root
    return Path(task_run.worktree_path) / root


def _ensure_preview_prerequisites(db: DbSession, task_run: TaskRun) -> None:
    if task_run.state != "completed":
        raise PreviewError("Preview requires a completed TaskRun.")

    task = db.get(Task, task_run.task_id)
    if task is None:
        raise PreviewError(f"Task not found for TaskRun: {task_run.id}")

    incomplete_dependencies: list[str] = []
    for dependency_id in dependency_ids_for_task(task):
        dependency = db.get(Task, dependency_id)
        if dependency is None or dependency.status not in DEPENDENCY_COMPLETE_STATUSES:
            incomplete_dependencies.append(dependency_id)
    if incomplete_dependencies:
        raise PreviewError(
            "Preview blocked by failed prerequisite or incomplete dependency: "
            + ", ".join(incomplete_dependencies)
        )


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
