import json
from dataclasses import dataclass

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.events import append_task_run_event
from app.models import Artifact, TaskRun, utc_now


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
