import json
from dataclasses import dataclass
from typing import Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.events import append_task_run_event
from app.models import Artifact, Session as AgentHubSession, Task, TaskRun, utc_now
from app.project_command_policy import evaluate_project_command
from app.target_registry import TargetRegistryError, get_target_for_workspace


COMMAND_EVIDENCE_TYPES = {"check", "test", "build"}
MAX_COMMAND_OUTPUT_CHARS = 12000


class ExternalEvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class StoredCommandEvidence:
    id: str
    artifact_id: str
    task_run_id: str
    artifact_type: str
    title: str
    status: str
    command_type: str
    command: str
    exit_code: int
    stdout: str
    stderr: str
    target_id: Optional[str]
    created_at: object


def record_command_evidence(
    db: DbSession,
    task_run_id: str,
    *,
    command_type: str,
    command: str,
    exit_code: int,
    stdout: str = "",
    stderr: str = "",
    target_id: Optional[str] = None,
) -> StoredCommandEvidence:
    task_run = db.get(TaskRun, task_run_id)
    if task_run is None:
        raise ExternalEvidenceError(f"TaskRun not found: {task_run_id}")
    normalized_type = command_type.strip().lower()
    if normalized_type not in COMMAND_EVIDENCE_TYPES:
        raise ExternalEvidenceError(
            "Command evidence type must be one of: check, test, build"
        )
    if not command.strip():
        raise ExternalEvidenceError("Command evidence requires a command string")

    resolved_target_id = _resolve_target_id(db, task_run, target_id)
    if resolved_target_id is not None:
        task = db.get(Task, task_run.task_id)
        session = db.get(AgentHubSession, task.session_id) if task is not None else None
        if task is None or session is None:
            raise ExternalEvidenceError("Command evidence target validation requires task context")
        try:
            target = get_target_for_workspace(db, session.workspace_id, resolved_target_id)
        except TargetRegistryError as exc:
            raise ExternalEvidenceError(str(exc)) from exc
        decision = evaluate_project_command(
            target=target,
            command_type=normalized_type,
            command=command,
        )
        if not decision.allowed:
            raise ExternalEvidenceError(decision.reason)

    now = utc_now()
    status = "passed" if exit_code == 0 else "failed"
    artifact = Artifact(
        task_run_id=task_run.id,
        artifact_type="command_evidence",
        title=f"{normalized_type.title()} command evidence",
        status=status,
        meta_json=json.dumps(
            {
                "commandType": normalized_type,
                "command": command,
                "exitCode": exit_code,
                "stdout": _truncate(stdout),
                "stderr": _truncate(stderr),
                "targetId": resolved_target_id,
            },
            separators=(",", ":"),
        ),
        created_at=now,
        updated_at=now,
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    append_task_run_event(
        db,
        task_run_id=task_run.id,
        event_type="artifact.command_evidence.ready",
        payload_json=json.dumps(
            {
                "artifactId": artifact.id,
                "commandType": normalized_type,
                "command": command,
                "exitCode": exit_code,
                "status": status,
                "targetId": resolved_target_id,
            },
            separators=(",", ":"),
        ),
    )
    return _to_stored_command_evidence(artifact)


def list_task_run_command_evidence(
    db: DbSession,
    task_run_id: str,
) -> list[StoredCommandEvidence]:
    artifacts = db.exec(
        select(Artifact)
        .where(Artifact.task_run_id == task_run_id)
        .where(Artifact.artifact_type == "command_evidence")
        .order_by(Artifact.created_at, Artifact.id)
    ).all()
    return [_to_stored_command_evidence(artifact) for artifact in artifacts]


def _to_stored_command_evidence(artifact: Artifact) -> StoredCommandEvidence:
    meta = _json_dict(artifact.meta_json)
    return StoredCommandEvidence(
        id=artifact.id,
        artifact_id=artifact.id,
        task_run_id=artifact.task_run_id,
        artifact_type=artifact.artifact_type,
        title=artifact.title,
        status=artifact.status,
        command_type=str(meta.get("commandType") or ""),
        command=str(meta.get("command") or ""),
        exit_code=int(meta.get("exitCode") or 0),
        stdout=str(meta.get("stdout") or ""),
        stderr=str(meta.get("stderr") or ""),
        target_id=_string_or_none(meta.get("targetId")),
        created_at=artifact.created_at,
    )


def _json_dict(value: str) -> dict:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _truncate(value: str) -> str:
    if len(value) <= MAX_COMMAND_OUTPUT_CHARS:
        return value
    return f"{value[:MAX_COMMAND_OUTPUT_CHARS - 1].rstrip()}..."


def _resolve_target_id(
    db: DbSession,
    task_run: TaskRun,
    explicit_target_id: Optional[str],
) -> Optional[str]:
    if isinstance(explicit_target_id, str) and explicit_target_id.strip():
        return explicit_target_id.strip()
    task = db.get(Task, task_run.task_id)
    if task is None:
        return None
    plan = _json_dict(task.plan_json)
    target_id = plan.get("targetId")
    return target_id if isinstance(target_id, str) and target_id.strip() else None


def _string_or_none(value: object) -> Optional[str]:
    return value if isinstance(value, str) and value else None
