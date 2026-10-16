from copy import deepcopy

import pytest

from app.workflow_evaluation import phase_gates, aggregate
from app.workflow_suite import select_scenarios


def valid_phase():
    memory = {"memorySnapshotId": "snapshot", "snapshotContentStatus": "frozen", "items": [
        {"id": "rule", "contentHash": "rule-hash", "layer": "rule", "contentVisible": True, "visibleContentHash": "rule-hash"}]}
    return {"nativePlanning": True, "requiredSnapshotId": "snapshot", "requiredRuleId": "rule", "requiredRuleHash": "rule-hash",
            "plannerReceipts": [deepcopy(memory)], "allTasksCompleted": True, "immutableInputs": True,
            "acceptance": {"status": "passed", "results": {"backend": {"sourceFingerprint": "current-source"}}},
            "attempts": [{"role": "backend", "targetId": "demo-backend", "state": "completed", "providerTurnObserved": True,
                "scope": {"status": "passed"}, "diffs": [{"nonempty": True}], "memoryUsage": memory,
                "validation": {"status": "passed", "sourceFingerprint": "current-source"}}]}


@pytest.mark.parametrize("failure,expected", [
    ("provider", "demo-backend:provider_turn_unobserved"),
    ("scope", "demo-backend:scope_not_passed"), ("diff", "demo-backend:diff_missing"),
    ("version", "demo-backend:validation_source_mismatch"), ("checks", "demo-backend:automatic_checks_not_passed"),
    ("memory", "demo-backend:memory_binding_invalid"), ("planner_memory", "planner_memory_binding_invalid"),
    ("native", "native_planning_unobserved"), ("acceptance", "independent_acceptance_failed"),
    ("immutable", "immutable_inputs_changed"), ("unfinished", "planned_tasks_incomplete"),
])
def test_green_functional_output_does_not_override_missing_execution_evidence(failure, expected):
    scenario = select_scenarios("backend-repair")[0]
    phase = valid_phase()
    assert phase_gates(scenario, phase) == []
    attempt = phase["attempts"][0]
    if failure == "provider": attempt["providerTurnObserved"] = False
    if failure == "scope": attempt["scope"]["status"] = "failed"
    if failure == "diff": attempt["diffs"] = []
    if failure == "version": attempt["validation"]["sourceFingerprint"] = "other-source"
    if failure == "checks": attempt["validation"]["status"] = "failed"
    if failure == "memory": attempt["memoryUsage"]["memorySnapshotId"] = "other-snapshot"
    if failure == "planner_memory": phase["plannerReceipts"][0]["items"] = []
    if failure == "native": phase.update(nativePlanning=False, planningSource="fake_test")
    if failure == "acceptance": phase["acceptance"]["status"] = "failed"
    if failure == "immutable": phase["immutableInputs"] = False
    if failure == "unfinished": phase["allTasksCompleted"] = False
    assert phase_gates(scenario, phase) == [expected]


def test_explicit_test_source_can_never_be_mistaken_for_native_planning():
    scenario = select_scenarios("backend-repair")[0]
    phase = valid_phase()
    phase.update(nativePlanning=False, planningSource="fake_test", testExecution=True)
    assert phase_gates(scenario, phase) == []
    phase["testExecution"] = False
    assert phase_gates(scenario, phase) == ["native_planning_unobserved"]


def test_not_attempted_selected_cases_stay_in_both_first_and_final_denominators():
    cases = [{"caseId": "one", "verdict": "passed", "firstAttemptPassed": True}, {"caseId": "two", "verdict": "not_attempted"}]
    value = aggregate(cases, mode="live")
    assert value["firstAttemptSuccessRate"] == .5 and value["finalSuccessRate"] == .5
    assert aggregate(cases, mode="prepare_only")["finalSuccessRate"] is None


def test_missing_independent_source_evidence_is_not_reported_as_a_proven_mismatch():
    phase = valid_phase()
    phase["acceptance"] = {"status": "not_run", "results": {}}
    gates = phase_gates(select_scenarios("backend-repair")[0], phase)
    assert "demo-backend:validation_source_unverified" in gates
    assert "demo-backend:validation_source_mismatch" not in gates
