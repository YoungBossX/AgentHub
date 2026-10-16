"""Evaluation-only verification of persisted native QA; never model-only proof."""
import json
from datetime import timezone

from sqlmodel import select

from app.models import Artifact, Review
from app.native_reviews import NativeReviewError, require_native_review_input_current, validate_native_assessment
from app.task_runs import internal_metrics_for_run


def attempt_seconds(run):
    if run.started_at is None or run.ended_at is None:
        return None
    start = run.started_at.replace(tzinfo=timezone.utc) if run.started_at.tzinfo is None else run.started_at
    end = run.ended_at.replace(tzinfo=timezone.utc) if run.ended_at.tzinfo is None else run.ended_at
    seconds = (end - start).total_seconds()
    return round(seconds, 3) if seconds >= 0 else None


def collect_reviews(db, run, payloads):
    binding = internal_metrics_for_run(run).get("_nativeReviewBinding")
    native = next((payload.get("nativeReview") for payload in reversed(payloads) if isinstance(payload.get("nativeReview"), dict)), None)
    result = []
    for review, artifact in db.exec(select(Review, Artifact).join(Artifact, Artifact.id == Review.artifact_id)
            .where(Artifact.task_run_id == run.id)).all():
        metadata = json.loads(artifact.meta_json)
        receipt = metadata.get("nativeReceipt") or {}
        qa = metadata.get("qaAssessment") or {}
        evidence = metadata.get("providerEvidence") or {}
        failures = []
        try:
            if not isinstance(binding, dict) or not isinstance(native, dict):
                raise ValueError("native_binding_or_completion_missing")
            assessment = validate_native_assessment(json.dumps(native["assessment"], ensure_ascii=False), binding, native["readEvidence"])
            require_native_review_input_current(db, run, binding)
            if (run.state != "completed" or review.adapter_type != "claude_code"
                    or metadata.get("adapterType") != "claude_code" or evidence.get("adapterType") != "claude_code"
                    or evidence.get("taskRunId") != run.id or native.get("adapterRunId") != run.adapter_run_id
                    or receipt.get("taskRunId") != run.id or receipt.get("adapterRunId") != run.adapter_run_id
                    or receipt.get("targetId") != binding["targetId"]
                    or receipt.get("outputSha256") != native.get("outputSha256")
                    or receipt.get("inputFingerprint") != binding["inputFingerprint"]
                    or qa.get("inputFingerprint") != binding["inputFingerprint"]
                    or qa.get("model", {}).get("source") != "native"
                    or review.status != assessment["status"] or qa.get("model", {}).get("status") != assessment["status"]
                    or json.loads(review.files_reviewed_json) != assessment["filesReviewed"]
                    or receipt.get("files") != {path: binding["files"][path] for path in assessment["filesReviewed"]}):
                raise ValueError("native_review_binding_mismatch")
        except (NativeReviewError, ValueError, KeyError, TypeError, OSError) as exc:
            failures.append(getattr(exc, "error_code", type(exc).__name__))
        result.append({"artifactId": artifact.id, "reviewId": review.id, "taskRunId": run.id,
            "adapterType": review.adapter_type, "status": review.status, "riskLevel": review.risk_level,
            "qaStatus": qa.get("status"), "model": qa.get("model"),
            "inputFingerprint": receipt.get("inputFingerprint"), "outputSha256": receipt.get("outputSha256"),
            "verifiedNativeReceipt": not failures, "verificationFailures": failures,
            "filesReviewed": json.loads(review.files_reviewed_json),
            "readEvidence": native.get("readEvidence", {}) if isinstance(native, dict) else {},
            "boundFiles": {path: item["sha256"] for path, item in (binding or {}).get("files", {}).items()},
            "findingCount": len(json.loads(review.findings_json)), "validation": qa.get("validation"),
            "currentness": qa.get("currentness")})
    return result


def review_gates(target, writer, reviewers, phase):
    prefix = f"{target}:qa_"
    if not reviewers:
        return [prefix + "missing"]
    last = reviewers[-1]
    gates = []
    if last.get("state") != "completed":
        gates.append(prefix + "execution_incomplete")
    if not last.get("providerTurnObserved"):
        gates.append(prefix + "provider_turn_unobserved")
    reviews = last.get("reviews") or []
    if not reviews or not all(review.get("verifiedNativeReceipt") for review in reviews):
        gates.append(prefix + "native_receipt_unverified")
        return gates
    expected = {path for diff in writer.get("diffs", []) for path in diff.get("files", [])}
    covered = set()
    current = phase.get("sourceHashes", {})
    for review in reviews:
        if review.get("taskRunId") != last.get("taskRunId") or review.get("adapterType") != "claude_code":
            gates.append(prefix + "owner_mismatch")
        if review.get("status") != "passed" or review.get("model") != {"source": "native", "status": "passed"} or review.get("qaStatus") != "passed":
            gates.append(prefix + "assessment_not_passed")
        if review.get("currentness") != "current":
            gates.append(prefix + "validation_not_current")
        if (review.get("validation") or {}).get("sourceFingerprint") != (writer.get("validation") or {}).get("sourceFingerprint"):
            gates.append(prefix + "validation_source_mismatch")
        if not review.get("boundFiles") or any(current.get(path) != fingerprint for path, fingerprint in review.get("boundFiles", {}).items()):
            gates.append(prefix + "source_mismatch")
        covered.update(review.get("filesReviewed", []))
    if not expected or not expected.issubset(covered):
        gates.append(prefix + "changed_files_unread")
    return sorted(set(gates))
