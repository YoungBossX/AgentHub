import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine

from app.memory_rehearsal import (
    MemoryRehearsalScenario,
    MemoryRehearsalSeed,
    MemoryRehearsalProviderAvailability,
    built_in_memory_rehearsal_scenarios,
    evaluate_memory_rehearsal_scenario,
    generate_memory_rehearsal_report,
    scenario_by_id,
    scenario_contains_private_data,
    validate_built_in_memory_rehearsal_scenarios,
    validate_memory_rehearsal_scenario,
)
from app.models import Workspace


def test_built_in_memory_rehearsal_scenarios_are_valid() -> None:
    validate_built_in_memory_rehearsal_scenarios()

    scenarios = built_in_memory_rehearsal_scenarios()

    assert {scenario.id for scenario in scenarios} == {
        "zh-preference-recall",
        "project-rule-change-log",
        "stale-pattern-exclusion",
        "prompt-injection-blocking",
    }
    assert all(not scenario_contains_private_data(scenario) for scenario in scenarios)


def test_memory_rehearsal_scenario_payload_is_stable_and_parseable() -> None:
    scenario = scenario_by_id("zh-preference-recall")

    first_payload = scenario.stable_json()
    second_payload = scenario.stable_json()

    assert first_payload == second_payload
    assert '"expectedMemoryKeys":["prefer-chinese-summary"]' in first_payload
    assert scenario.to_payload()["memorySeeds"][0]["key"] == "prefer-chinese-summary"


def test_memory_rehearsal_scenario_rejects_private_data() -> None:
    scenario = MemoryRehearsalScenario(
        id="private-data",
        title="Private data sample",
        persona="Synthetic user",
        request="请联系 test@example.com 并记住这个信息。",
        memory_seeds=(
            MemoryRehearsalSeed(
                key="private-email",
                scope="user",
                memory_type="user_preference",
                title="Private email",
                content_md="联系邮箱 test@example.com。",
            ),
        ),
        expected_memory_keys=("private-email",),
        excluded_memory_keys=(),
        roles=("orchestrator",),
        target_ids=(),
        expected_metrics=("preference_recall_rate",),
        scoring_notes="Should be rejected because fixtures must avoid private data.",
    )

    assert scenario_contains_private_data(scenario)
    with pytest.raises(ValueError, match="contains private data"):
        validate_memory_rehearsal_scenario(scenario)


def test_memory_rehearsal_scenario_rejects_missing_expected_key() -> None:
    scenario = MemoryRehearsalScenario(
        id="missing-key",
        title="Missing key",
        persona="Synthetic user",
        request="请用中文总结。",
        memory_seeds=(),
        expected_memory_keys=("missing",),
        excluded_memory_keys=(),
        roles=("orchestrator",),
        target_ids=(),
        expected_metrics=("preference_recall_rate",),
        scoring_notes="Expected memory key must exist in seeds.",
    )

    with pytest.raises(ValueError, match="missing expected memory keys"):
        validate_memory_rehearsal_scenario(scenario)


def test_memory_rehearsal_evaluator_compares_control_and_treatment() -> None:
    with _db() as db:
        workspace = _workspace(db)
        evaluation = evaluate_memory_rehearsal_scenario(
            db,
            scenario=scenario_by_id("zh-preference-recall"),
            workspace_id=workspace.id,
        )

    assert evaluation.scenario_id == "zh-preference-recall"
    assert evaluation.control.metrics.preference_recall_rate == 0.0
    assert evaluation.control.metrics.memory_precision_at_5 == 0.0
    assert evaluation.treatment.metrics.preference_recall_rate == 1.0
    assert evaluation.treatment.metrics.memory_precision_at_5 > 0
    assert evaluation.treatment.retrieved_memory_keys == ("prefer-chinese-summary",)
    assert evaluation.treatment.task_success_delta is None
    assert "unknown" in evaluation.treatment.task_success_delta_reason
    assert evaluation.improvement_summary.startswith("improved:")


def test_memory_rehearsal_evaluator_excludes_stale_and_untrusted_memory() -> None:
    with _db() as db:
        workspace = _workspace(db)
        stale_evaluation = evaluate_memory_rehearsal_scenario(
            db,
            scenario=scenario_by_id("stale-pattern-exclusion"),
            workspace_id=workspace.id,
        )
        injection_evaluation = evaluate_memory_rehearsal_scenario(
            db,
            scenario=scenario_by_id("prompt-injection-blocking"),
            workspace_id=workspace.id,
        )

    assert stale_evaluation.treatment.excluded_memory_keys_seen == ()
    assert stale_evaluation.treatment.metrics.stale_memory_injection_count == 0
    assert (
        injection_evaluation.treatment.metrics.prompt_injection_write_block_rate
        == 1.0
    )
    assert injection_evaluation.treatment.excluded_memory_keys_seen == ()
    assert injection_evaluation.treatment.metrics.snapshot_consistency_rate == 1.0


def test_memory_rehearsal_evaluator_marks_change_log_delta_unknown() -> None:
    with _db() as db:
        workspace = _workspace(db)
        evaluation = evaluate_memory_rehearsal_scenario(
            db,
            scenario=scenario_by_id("project-rule-change-log"),
            workspace_id=workspace.id,
        )

    assert evaluation.treatment.change_log_missing_rate is None
    assert "unknown" in evaluation.treatment.change_log_missing_rate_reason
    assert evaluation.treatment.task_success_delta is None


def test_memory_rehearsal_report_serializes_deterministic_evidence() -> None:
    with _db() as db:
        workspace = _workspace(db)
        report = generate_memory_rehearsal_report(
            db,
            workspace_id=workspace.id,
            scenarios=(scenario_by_id("zh-preference-recall"),),
        )

    payload = report.to_payload()

    assert payload["reportId"].startswith("p18b-")
    assert payload["evidenceSource"] == "deterministic"
    assert payload["providerAvailability"] == {
        "evidenceSource": "deterministic",
        "status": "not_requested",
        "providerId": None,
        "reason": "P18b deterministic rehearsal did not request live provider execution.",
    }
    assert payload["scenarioResults"][0]["scenarioId"] == "zh-preference-recall"
    assert payload["aggregateMetrics"]["averageTreatmentPreferenceRecallRate"] == 1.0


def test_memory_rehearsal_report_records_provider_unavailable() -> None:
    with _db() as db:
        workspace = _workspace(db)
        report = generate_memory_rehearsal_report(
            db,
            workspace_id=workspace.id,
            scenarios=(scenario_by_id("zh-preference-recall"),),
            provider_availability=MemoryRehearsalProviderAvailability(
                evidence_source="real_provider",
                status="unavailable",
                provider_id="deepseek-api-planner",
                reason="missing API key env DEEPSEEK_API_KEY",
            ),
        )

    payload = report.to_payload()

    assert payload["providerAvailability"]["status"] == "unavailable"
    assert payload["providerAvailability"]["providerId"] == "deepseek-api-planner"
    assert "DEEPSEEK_API_KEY" in payload["providerAvailability"]["reason"]


def test_memory_rehearsal_report_marks_metric_limitations() -> None:
    with _db() as db:
        workspace = _workspace(db)
        report = generate_memory_rehearsal_report(
            db,
            workspace_id=workspace.id,
            scenarios=(scenario_by_id("project-rule-change-log"),),
        )

    assert report.aggregate_metrics["knownTaskSuccessDeltaCount"] == 0
    assert report.aggregate_metrics["knownChangeLogMissingRateCount"] == 0
    assert any("Task Success Delta is unknown" in item for item in report.limitations)
    assert any("Change-log Missing Rate is unknown" in item for item in report.limitations)


def _db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return DbSession(engine)


def _workspace(db: DbSession) -> Workspace:
    workspace = Workspace(
        name="P18b Memory Eval",
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace
