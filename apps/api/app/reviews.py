import json
from dataclasses import dataclass
from typing import Any, Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.events import append_task_run_event
from app.models import Artifact, Diff, Review, utc_now


SCRIPTED_REVIEW_ADAPTER = "scripted_mock"


class ReviewError(ValueError):
    pass


@dataclass(frozen=True)
class StoredReviewArtifact:
    id: str
    artifact_id: str
    task_run_id: str
    reviewed_diff_artifact_id: str
    artifact_type: str
    title: str
    status: str
    risk_level: str
    summary: str
    files_reviewed: list[str]
    findings: list[dict[str, Any]]
    suggested_changes: list[str]
    adapter_type: str


def create_scripted_review_for_task_run(
    db: DbSession,
    task_run_id: str,
) -> StoredReviewArtifact:
    diff_artifact = _latest_diff_artifact(db, task_run_id)
    if diff_artifact is None:
        raise ReviewError(f"No diff artifact found for TaskRun: {task_run_id}")
    return create_scripted_review_for_diff(db, diff_artifact.id)


def create_scripted_review_for_diff(
    db: DbSession,
    diff_artifact_id: str,
) -> StoredReviewArtifact:
    diff_artifact = db.get(Artifact, diff_artifact_id)
    if diff_artifact is None or diff_artifact.artifact_type != "diff":
        raise ReviewError(f"Diff artifact not found: {diff_artifact_id}")

    existing = db.exec(
        select(Review).where(Review.reviewed_diff_artifact_id == diff_artifact.id)
    ).first()
    if existing is not None:
        artifact = db.get(Artifact, existing.artifact_id)
        if artifact is not None:
            return _to_stored_review(artifact, existing)

    diff = db.exec(select(Diff).where(Diff.artifact_id == diff_artifact.id)).first()
    if diff is None:
        raise ReviewError(f"Diff record not found for artifact: {diff_artifact.id}")

    files_reviewed = _json_list(diff.changed_files_json)
    findings, suggested_changes = _scripted_findings(files_reviewed, diff.patch_text)
    status = "passed" if not findings else "warning"
    risk_level = "low" if status == "passed" else "medium"
    summary = _summary_for(status, risk_level, files_reviewed, findings)
    now = utc_now()

    artifact = Artifact(
        task_run_id=diff_artifact.task_run_id,
        artifact_type="review",
        title="Review Agent report",
        status=status,
        meta_json=json.dumps(
            {
                "reviewedDiffArtifactId": diff_artifact.id,
                "status": status,
                "riskLevel": risk_level,
                "adapterType": SCRIPTED_REVIEW_ADAPTER,
            },
            separators=(",", ":"),
        ),
        created_at=now,
        updated_at=now,
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    review = Review(
        artifact_id=artifact.id,
        reviewed_diff_artifact_id=diff_artifact.id,
        reviewer_agent_id=None,
        adapter_type=SCRIPTED_REVIEW_ADAPTER,
        status=status,
        risk_level=risk_level,
        summary=summary,
        files_reviewed_json=json.dumps(files_reviewed, separators=(",", ":")),
        findings_json=json.dumps(findings, separators=(",", ":")),
        suggested_changes_json=json.dumps(suggested_changes, separators=(",", ":")),
        created_at=now,
        updated_at=now,
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    append_task_run_event(
        db,
        task_run_id=artifact.task_run_id,
        event_type="artifact.review.ready",
        payload_json=json.dumps(
            {
                "artifactId": artifact.id,
                "reviewId": review.id,
                "reviewedDiffArtifactId": diff_artifact.id,
                "status": status,
                "riskLevel": risk_level,
                "adapterType": SCRIPTED_REVIEW_ADAPTER,
            },
            separators=(",", ":"),
        ),
    )
    return _to_stored_review(artifact, review)


def list_task_run_reviews(
    db: DbSession,
    task_run_id: str,
) -> list[StoredReviewArtifact]:
    artifacts = db.exec(
        select(Artifact)
        .where(Artifact.task_run_id == task_run_id, Artifact.artifact_type == "review")
        .order_by(Artifact.created_at, Artifact.id)
    ).all()
    reviews: list[StoredReviewArtifact] = []
    for artifact in artifacts:
        review = db.exec(select(Review).where(Review.artifact_id == artifact.id)).first()
        if review is not None:
            reviews.append(_to_stored_review(artifact, review))
    return reviews


def latest_review_for_task_runs(
    db: DbSession,
    task_run_ids: list[str],
) -> Optional[StoredReviewArtifact]:
    if not task_run_ids:
        return None
    artifact = db.exec(
        select(Artifact)
        .where(Artifact.task_run_id.in_(task_run_ids))
        .where(Artifact.artifact_type == "review")
        .order_by(Artifact.created_at.desc(), Artifact.id.desc())
    ).first()
    if artifact is None:
        return None
    review = db.exec(select(Review).where(Review.artifact_id == artifact.id)).first()
    if review is None:
        return None
    return _to_stored_review(artifact, review)


def _latest_diff_artifact(db: DbSession, task_run_id: str) -> Optional[Artifact]:
    return db.exec(
        select(Artifact)
        .where(Artifact.task_run_id == task_run_id, Artifact.artifact_type == "diff")
        .order_by(Artifact.created_at.desc(), Artifact.id.desc())
    ).first()


def _scripted_findings(
    files_reviewed: list[str],
    patch_text: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    findings: list[dict[str, Any]] = []
    suggested_changes: list[str] = []
    if not files_reviewed:
        findings.append(
            {
                "severity": "medium",
                "file": None,
                "message": "No changed files were present in the reviewed diff.",
            }
        )
        suggested_changes.append("Confirm the coding run produced the intended file changes.")

    if "console.log" in patch_text:
        findings.append(
            {
                "severity": "low",
                "file": _first_file(files_reviewed),
                "message": "The diff contains console logging; remove it if it is not intentional.",
            }
        )
        suggested_changes.append("Remove temporary console logging before a production path.")

    return findings, suggested_changes


def _summary_for(
    status: str,
    risk_level: str,
    files_reviewed: list[str],
    findings: list[dict[str, Any]],
) -> str:
    file_count = len(files_reviewed)
    if status == "passed":
        return (
            f"Scripted Review Agent passed {file_count} changed file"
            f"{'' if file_count == 1 else 's'} with low risk."
        )
    return (
        f"Scripted Review Agent found {len(findings)} advisory finding"
        f"{'' if len(findings) == 1 else 's'} with {risk_level} risk."
    )


def _first_file(files_reviewed: list[str]) -> Optional[str]:
    return files_reviewed[0] if files_reviewed else None


def _to_stored_review(artifact: Artifact, review: Review) -> StoredReviewArtifact:
    return StoredReviewArtifact(
        id=review.id,
        artifact_id=artifact.id,
        task_run_id=artifact.task_run_id,
        reviewed_diff_artifact_id=review.reviewed_diff_artifact_id,
        artifact_type=artifact.artifact_type,
        title=artifact.title,
        status=review.status,
        risk_level=review.risk_level,
        summary=review.summary,
        files_reviewed=_json_list(review.files_reviewed_json),
        findings=_json_dict_list(review.findings_json),
        suggested_changes=_json_list(review.suggested_changes_json),
        adapter_type=review.adapter_type,
    )


def _json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str)]


def _json_dict_list(value: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]
