import json
import re
from dataclasses import dataclass
from typing import Any, Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.artifact_versions import record_artifact_version
from app.events import append_task_run_event
from app.external_evidence import list_task_run_command_evidence
from app.models import Artifact, Diff, Review, Task, TaskRun, utc_now
from app.models import Session as AgentHubSession
from app.provider_evidence import provider_evidence_for_task_run, scripted_provider_evidence
from app.target_registry import (
    DEMO_BACKEND_TARGET_ID,
    DEMO_FRONTEND_TARGET_ID,
    TargetProject,
    TargetRegistryError,
    get_related_backend_target,
    get_target,
    get_target_for_workspace,
)


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


def record_review_collection_failure(
    db: DbSession,
    task_run_id: str,
    exc: Exception,
    *,
    skipped: bool = False,
) -> None:
    append_task_run_event(
        db,
        task_run_id=task_run_id,
        event_type="artifact.review.failed",
        payload_json=json.dumps(
            {
                "status": "skipped" if skipped else "failed",
                "errorCode": "ARTIFACT_COLLECTION_FAILED",
                "errorMessage": str(exc),
                "message": f"Review collection {'skipped' if skipped else 'failed'}: {exc}",
            },
            separators=(",", ":"),
        ),
    )


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
    plan = _plan_for_diff_artifact(db, diff_artifact)
    contract = plan.get("appContract") if isinstance(plan.get("appContract"), dict) else None
    external_target = _external_target_for_plan(db, diff_artifact, plan)
    command_evidence = list_task_run_command_evidence(db, diff_artifact.task_run_id)
    findings, suggested_changes = _scripted_findings(
        files_reviewed,
        diff.patch_text,
        contract=contract,
        plan=plan,
        external_target=external_target,
        command_evidence=command_evidence,
    )
    status, risk_level = _status_and_risk_for(findings)
    summary = _summary_for(status, risk_level, files_reviewed, findings, contract=contract)
    now = utc_now()
    task_run = db.get(TaskRun, diff_artifact.task_run_id)
    if task_run is None:
        raise ReviewError(f"TaskRun not found for diff artifact: {diff_artifact.id}")
    origin_provider_evidence = provider_evidence_for_task_run(
        db,
        task_run,
        changed_files=files_reviewed,
        artifact_refs={"diffArtifactId": diff_artifact.id},
    )
    review_provider_evidence = scripted_provider_evidence(origin_provider_evidence)

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
                "contractId": contract.get("contractId") if contract else None,
                "providerEvidence": review_provider_evidence,
                "originProviderEvidence": origin_provider_evidence,
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

    record_artifact_version(
        db,
        artifact,
        source_task_run_id=artifact.task_run_id,
        parent_artifact_id=diff_artifact.id,
        changed_files=files_reviewed,
        summary=summary,
    )

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
                "providerEvidence": {
                    **review_provider_evidence,
                    "artifactRefs": {
                        **review_provider_evidence.get("artifactRefs", {}),
                        "reviewArtifactId": artifact.id,
                    },
                },
                "originProviderEvidence": origin_provider_evidence,
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
    *,
    contract: Optional[dict[str, Any]] = None,
    plan: Optional[dict[str, Any]] = None,
    external_target: Optional[TargetProject] = None,
    command_evidence: Optional[list] = None,
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

    if contract is not None:
        contract_findings, contract_suggestions = _contract_consistency_findings(
            files_reviewed,
            contract,
            patch_text,
            plan=plan or {},
        )
        findings.extend(contract_findings)
        suggested_changes.extend(contract_suggestions)

    if external_target is not None:
        external_findings, external_suggestions = _external_target_findings(
            files_reviewed,
            external_target,
            command_evidence or [],
        )
        findings.extend(external_findings)
        suggested_changes.extend(external_suggestions)

    return findings, suggested_changes


def _external_target_findings(
    files_reviewed: list[str],
    target: TargetProject,
    command_evidence: list,
) -> tuple[list[dict[str, Any]], list[str]]:
    findings: list[dict[str, Any]] = []
    suggested_changes: list[str] = []
    for path in files_reviewed:
        if target.denies_path(path):
            findings.append(
                {
                    "severity": "high",
                    "file": path,
                    "message": f"External target {target.target_id} changed denied path {path}.",
                }
            )
            suggested_changes.append(f"Remove denied-path changes from {path}.")
            continue
        if not target.allows_path(path):
            findings.append(
                {
                    "severity": "medium",
                    "file": path,
                    "message": (
                        f"External target {target.target_id} changed {path}, "
                        "which is outside registered allowed paths."
                    ),
                }
            )
            suggested_changes.append(
                f"Keep changes inside {', '.join(target.allowed_paths)} for {target.target_id}."
            )

    evidence_by_type = {
        str(getattr(evidence, "command_type", "")): evidence
        for evidence in command_evidence
    }
    for command_type, command in [
        ("check", target.check_command),
        ("test", target.test_command),
        ("build", target.build_command),
    ]:
        if not command:
            continue
        evidence = evidence_by_type.get(command_type)
        if evidence is None:
            findings.append(
                {
                    "severity": "medium",
                    "file": None,
                    "message": (
                        f"External target {target.target_id} has configured "
                        f"{command_type} command `{command}` but no evidence was recorded."
                    ),
                }
            )
            suggested_changes.append(f"Record {command_type} evidence for `{command}`.")
            continue
        if getattr(evidence, "exit_code", 0) != 0:
            findings.append(
                {
                    "severity": "medium",
                    "file": None,
                    "message": (
                        f"External target {target.target_id} {command_type} command "
                        f"`{command}` failed with exit code {evidence.exit_code}."
                    ),
                }
            )
            suggested_changes.append(
                f"Fix failing {command_type} evidence before claiming validation success."
            )
    return findings, suggested_changes


def _contract_consistency_findings(
    files_reviewed: list[str],
    contract: dict[str, Any],
    patch_text: str,
    *,
    plan: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    findings: list[dict[str, Any]] = []
    suggested_changes: list[str] = []
    contract_id = str(contract.get("contractId") or "shared contract")
    frontend_target, backend_target = _contract_targets(contract)
    frontend_prefix = _primary_allowed_path(frontend_target)
    backend_prefix = _primary_allowed_path(backend_target)

    target_findings, target_suggestions = _target_policy_findings(
        files_reviewed,
        frontend_target,
        backend_target,
        contract_id,
    )
    findings.extend(target_findings)
    suggested_changes.extend(target_suggestions)

    task_target_findings, task_target_suggestions = _task_target_consistency_findings(
        plan,
        contract,
        frontend_target,
        backend_target,
        contract_id,
    )
    findings.extend(task_target_findings)
    suggested_changes.extend(task_target_suggestions)

    has_backend_change = any(path.startswith(f"{backend_prefix}/") for path in files_reviewed)
    has_frontend_change = any(path.startswith(f"{frontend_prefix}/") for path in files_reviewed)

    if not has_backend_change:
        findings.append(
            {
                "severity": "medium",
                "file": None,
                "message": f"Contract {contract_id} expected backend changes under {backend_prefix}.",
            }
        )
        suggested_changes.append(f"Add or verify backend implementation under {backend_prefix}.")

    if not has_frontend_change:
        findings.append(
            {
                "severity": "medium",
                "file": None,
                "message": f"Contract {contract_id} expected frontend changes under {frontend_prefix}.",
            }
        )
        suggested_changes.append(f"Add or verify frontend implementation under {frontend_prefix}.")

    api_findings, api_suggestions = _api_base_findings(
        files_reviewed,
        contract,
        frontend_prefix,
        backend_target,
        patch_text,
    )
    findings.extend(api_findings)
    suggested_changes.extend(api_suggestions)

    return findings, suggested_changes


def _api_base_findings(
    files_reviewed: list[str],
    contract: dict[str, Any],
    frontend_prefix: str,
    backend_target: TargetProject,
    patch_text: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    findings: list[dict[str, Any]] = []
    suggested_changes: list[str] = []
    frontend_files = [path for path in files_reviewed if path.startswith(f"{frontend_prefix}/")]
    if not frontend_files:
        return findings, suggested_changes

    expected_base = backend_target.base_url or str(contract.get("demoApiBaseUrl") or "")
    contract_id = str(contract.get("contractId") or "shared contract")
    local_bases = sorted(set(re.findall(r"http://(?:localhost|127\.0\.0\.1):\d+", patch_text)))
    for local_base in local_bases:
        if expected_base and local_base != expected_base:
            findings.append(
                {
                    "severity": "medium",
                    "file": _first_file(frontend_files),
                    "message": (
                        f"Contract {contract_id} expected demo API base {expected_base}, "
                        f"but frontend code references {local_base}."
                    ),
                }
            )
            suggested_changes.append(
                f"Use demo API base {expected_base} for generated app data calls."
            )
            break

    return findings, suggested_changes


def _contract_targets(contract: dict[str, Any]) -> tuple[TargetProject, TargetProject]:
    frontend_target_id = _string_value(contract.get("frontendTargetId")) or DEMO_FRONTEND_TARGET_ID
    backend_target_id = _string_value(contract.get("backendTargetId"))
    try:
        frontend_target = get_target(frontend_target_id)
    except TargetRegistryError:
        frontend_target = get_target(DEMO_FRONTEND_TARGET_ID)
    if backend_target_id:
        try:
            return frontend_target, get_target(backend_target_id)
        except TargetRegistryError:
            pass
    return frontend_target, get_related_backend_target(frontend_target.target_id)


def _target_policy_findings(
    files_reviewed: list[str],
    frontend_target: TargetProject,
    backend_target: TargetProject,
    contract_id: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    findings: list[dict[str, Any]] = []
    suggested_changes: list[str] = []
    expected_targets = [frontend_target, backend_target]
    for path in files_reviewed:
        permitted_by = [target for target in expected_targets if target.permits_path(path)]
        if permitted_by:
            continue
        denied_by = [target for target in expected_targets if target.denies_path(path)]
        if denied_by:
            severity = "high" if path.startswith("apps/api/") else "medium"
            findings.append(
                {
                    "severity": severity,
                    "file": path,
                    "message": (
                        f"Contract {contract_id} changed denied target path {path}. "
                        "Ordinary app work must stay inside demo frontend/backend targets."
                    ),
                }
            )
            suggested_changes.append(
                f"Move or remove changes outside target policy for {contract_id}: {path}."
            )
            continue
        findings.append(
            {
                "severity": "medium",
                "file": path,
                "message": (
                    f"Contract {contract_id} changed {path}, which is outside "
                    "the expected target allowed paths."
                ),
            }
        )
        suggested_changes.append(
            f"Keep contract {contract_id} changes inside "
            f"{', '.join(frontend_target.allowed_paths + backend_target.allowed_paths)}."
        )
    return findings, suggested_changes


def _task_target_consistency_findings(
    plan: dict[str, Any],
    contract: dict[str, Any],
    frontend_target: TargetProject,
    backend_target: TargetProject,
    contract_id: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    findings: list[dict[str, Any]] = []
    suggested_changes: list[str] = []
    assigned_role = _string_value(plan.get("assignedRole"))
    expected_target_id = None
    if assigned_role == "frontend":
        expected_target_id = frontend_target.target_id
    elif assigned_role == "backend":
        expected_target_id = backend_target.target_id
    elif assigned_role in {"qa", "review"}:
        expected_target_id = _string_value(contract.get("frontendTargetId")) or frontend_target.target_id

    actual_target_id = _string_value(plan.get("targetId"))
    if expected_target_id and actual_target_id and actual_target_id != expected_target_id:
        findings.append(
            {
                "severity": "high",
                "file": None,
                "message": (
                    f"Contract {contract_id} expected task target {expected_target_id}, "
                    f"but task plan targets {actual_target_id}."
                ),
            }
        )
        suggested_changes.append(
            f"Align task targetId with contract target IDs for {contract_id}."
        )

    for field, expected in [
        ("frontendTargetId", frontend_target.target_id),
        ("backendTargetId", backend_target.target_id),
    ]:
        actual = _string_value(plan.get(field))
        if actual and actual != expected:
            findings.append(
                {
                    "severity": "high",
                    "file": None,
                    "message": (
                        f"Contract {contract_id} expected {field}={expected}, "
                        f"but task plan has {actual}."
                    ),
                }
            )
            suggested_changes.append(f"Use registry-resolved {field}={expected}.")
    return findings, suggested_changes


def _status_and_risk_for(findings: list[dict[str, Any]]) -> tuple[str, str]:
    severities = {str(finding.get("severity") or "").lower() for finding in findings}
    if "high" in severities:
        return "failed", "high"
    if findings:
        return "warning", "medium"
    return "passed", "low"


def _summary_for(
    status: str,
    risk_level: str,
    files_reviewed: list[str],
    findings: list[dict[str, Any]],
    *,
    contract: Optional[dict[str, Any]] = None,
) -> str:
    file_count = len(files_reviewed)
    if contract is not None and status == "passed":
        contract_id = str(contract.get("contractId") or "shared contract")
        return (
            f"Scripted Review Agent passed {file_count} changed file"
            f"{'' if file_count == 1 else 's'} with low risk and verified "
            f"contract consistency for {contract_id}."
        )
    if status == "passed":
        return (
            f"Scripted Review Agent passed {file_count} changed file"
            f"{'' if file_count == 1 else 's'} with low risk."
        )
    return (
        f"Scripted Review Agent found {len(findings)} advisory finding"
        f"{'' if len(findings) == 1 else 's'} with {risk_level} risk."
    )


def _plan_for_diff_artifact(
    db: DbSession,
    diff_artifact: Artifact,
) -> dict[str, Any]:
    task_run = db.get(TaskRun, diff_artifact.task_run_id)
    if task_run is None:
        return {}
    task = db.get(Task, task_run.task_id)
    if task is None:
        return {}
    try:
        plan = json.loads(task.plan_json)
    except json.JSONDecodeError:
        return {}
    return plan if isinstance(plan, dict) else {}


def _external_target_for_plan(
    db: DbSession,
    diff_artifact: Artifact,
    plan: dict[str, Any],
) -> Optional[TargetProject]:
    target_id = _string_value(plan.get("targetId"))
    if target_id is None or not target_id.startswith("external-"):
        return None
    task_run = db.get(TaskRun, diff_artifact.task_run_id)
    if task_run is None:
        return None
    task = db.get(Task, task_run.task_id)
    if task is None:
        return None
    session = db.get(AgentHubSession, task.session_id)
    if session is None:
        return None
    try:
        return get_target_for_workspace(db, session.workspace_id, target_id)
    except TargetRegistryError:
        return None


def _first_file(files_reviewed: list[str]) -> Optional[str]:
    return files_reviewed[0] if files_reviewed else None


def _primary_allowed_path(target: TargetProject) -> str:
    return target.allowed_paths[0] if target.allowed_paths else target.root


def _string_value(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


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
