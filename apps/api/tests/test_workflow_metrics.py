"""Metric definitions, retry accounting and honest partial coverage."""
import copy

import pytest

from app.workflow_evaluation import aggregate


def receipt(count, cost):
    return {'schemaVersion': 'agenthub.provider_usage.v1', 'status': 'reported',
            'inputTokens': count, 'outputTokens': 2, 'cacheReadInputTokens': 0,
            'cacheCreationInputTokens': 0, 'tokenTotal': count + 2, 'estimatedCostUsd': cost,
            'billingVerified': False}


def example():
    return {'caseId': 'sample', 'faultInjection': False, 'verdict': 'passed', 'elapsedSeconds': 1,
            'phases': [{'plannerCalls': [{'callId': 'planner', 'providerUsage': receipt(5, .01)}],
                        'stageTimings': {'planningDispatchMs': 30, 'independentAcceptanceMs': 20},
                        'attempts': [
                            {'taskRunId': 'failed', 'role': 'frontend', 'state': 'failed', 'providerUsage': receipt(10, .02),
                             'stageTimings': {'adapterWallMs': 100, 'firstSemanticTextMs': None}},
                            {'taskRunId': 'retry', 'role': 'frontend', 'state': 'completed', 'retryOfRunId': 'failed',
                             'providerUsage': receipt(20, .03), 'stageTimings': {'adapterWallMs': 200, 'firstSemanticTextMs': 80}},
                            {'taskRunId': 'qa', 'role': 'review', 'state': 'completed', 'providerUsage': receipt(3, .01),
                             'stageTimings': {'adapterWallMs': 150, 'firstSemanticTextMs': 60}}]}]}


def test_usage_aggregate_counts_planning_failure_retry_and_qa_once():
    case = example()
    case['phases'][0]['attempts'].append(copy.deepcopy(case['phases'][0]['attempts'][1]))
    result = aggregate([case], mode='live').get('measurements')
    assert result, 'Per-call usage aggregation is missing'
    usage = result['providerUsage']
    assert usage['callRecords'] == 4
    assert usage['fields']['inputTokens']['total'] == 38
    assert usage['fields']['tokenTotal']['total'] == 46
    assert usage['fields']['estimatedCostUsd']['total'] == pytest.approx(.07)
    assert usage['verifiedBilling'] is False


def test_missing_usage_does_not_claim_complete_token_total_or_free_call():
    case = example()
    case['phases'][0]['attempts'][0]['providerUsage'] = None
    result = aggregate([case], mode='live').get('measurements')
    assert result, 'Unknown usage coverage is missing'
    fields = result['providerUsage']['fields']
    assert fields['inputTokens'] == {'known': 3, 'unknown': 1, 'knownSum': 28, 'total': None}
    assert fields['estimatedCostUsd']['total'] is None
    assert fields['estimatedCostUsd']['knownSum'] == pytest.approx(.05)


def test_repair_usage_is_included_without_overwriting_natural_success_rate():
    case = example()
    case.update(verdict='failed', firstAttemptPassed=False, repairOutcome={'status': 'recovered'})
    repair = copy.deepcopy(case['phases'][0])
    for attempt in repair['attempts']:
        attempt['taskRunId'] += '-repair'
    repair['plannerCalls'][0]['callId'] += '-repair'
    case['repairPhases'] = [repair]
    result = aggregate([case], mode='live')
    assert result['passed'] == 0 and result['finalSuccessRate'] == 0
    assert result['repairs'] == {'attempted': 1, 'recovered': 1, 'failed': 0}
    assert result['measurements']['providerUsage']['callRecords'] == 8
    assert result['measurements']['providerUsage']['fields']['inputTokens']['total'] == 76
    assert result['measurements']['stageTimings']['planningDispatchMs']['observed'] == 2
    assert result['roles']['coding']['attempts'] == 4


def test_empty_report_has_unknown_totals_not_zero_and_no_latency():
    result = aggregate([], mode='live').get('measurements')
    assert result
    assert result['providerUsage']['fields']['tokenTotal']['total'] is None
    assert result['stageTimings']['adapterWallMs']['p95Ms'] is None


def test_quantiles_use_only_observed_values_and_expose_missing_semantic_text():
    result = aggregate([example()], mode='live').get('measurements')
    assert result
    wall = result['stageTimings']['adapterWallMs']
    assert wall['observed'] == 3 and wall['p50Ms'] == 150 and wall['p95Ms'] == 200
    first = result['stageTimings']['firstSemanticTextMs']
    assert first['observed'] == 2 and first['unknown'] == 1 and first['p50Ms'] == 60
    assert first['quantileMethod'] == 'nearest_rank'
    assert result['stageTimings']['planningDispatchMs']['observed'] == 1


def test_fault_measurements_keep_their_own_denominator():
    natural, fault = example(), example()
    fault['caseId'] = 'recovery'; fault['faultInjection'] = True
    for attempt in fault['phases'][0]['attempts']:
        attempt['taskRunId'] += '-fault'
    fault['phases'][0]['plannerCalls'][0]['callId'] += '-fault'
    result = aggregate([natural, fault], mode='live')
    assert result['naturalScenarios'].get('measurements')
    assert result['naturalScenarios']['measurements']['providerUsage']['callRecords'] == 4
    assert result['faultInjectionScenarios']['measurements']['providerUsage']['callRecords'] == 4


def test_queue_launch_and_finalization_boundaries_are_distinct():
    from app import workflow_metrics
    from datetime import datetime, timedelta
    from types import SimpleNamespace
    base = datetime(2026, 1, 1)
    iso = lambda ms: (base + timedelta(milliseconds=ms)).isoformat()
    run = SimpleNamespace(created_at=base, ended_at=base + timedelta(milliseconds=1000))
    queue = SimpleNamespace(created_at=base, started_at=base + timedelta(milliseconds=100))
    timing = {'launchStartedAt': iso(150), 'adapterTerminalAt': iso(800),
              'adapterLaunchMs': 20, 'firstSemanticTextMs': 200, 'adapterWallMs': 650}
    result = workflow_metrics.attempt_timings(run, queue, timing)
    assert result == {'queueWaitMs': 100, 'preAdapterMs': 50, 'adapterLaunchMs': 20,
                      'firstSemanticTextMs': 200, 'adapterWallMs': 650, 'finalizationMs': 200,
                      'attemptEndToEndMs': 1000}
    run.ended_at = None
    assert workflow_metrics.attempt_timings(run, queue, timing)['finalizationMs'] is None


@pytest.mark.parametrize('error', [RuntimeError, __import__('asyncio').CancelledError])
def test_incomplete_stage_is_unknown_and_excluded_from_quantiles(error):
    from app.workflow_metrics import stage_timer
    case = example()
    stages = case['phases'][0]['stageTimings']
    with pytest.raises(error):
        with stage_timer(stages, 'independentAcceptanceMs'):
            raise error()
    assert stages['independentAcceptanceMs'] is None
    result = aggregate([case], mode='live')['measurements']['stageTimings']['independentAcceptanceMs']
    assert result['observed'] == 0 and result['unknown'] == 1 and result['p95Ms'] is None
