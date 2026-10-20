"""Descriptive workflow measurements; no billing or model-quality inference."""
from contextlib import contextmanager
from datetime import datetime, timezone
import math
import time


ATTEMPT_STAGES = ('queueWaitMs', 'preAdapterMs', 'adapterLaunchMs', 'firstSemanticTextMs',
                  'adapterWallMs', 'finalizationMs', 'attemptEndToEndMs')
PHASE_STAGES = ('planningDispatchMs', 'workflowExecutionMs', 'independentAcceptanceMs')
USAGE_FIELDS = ('inputTokens', 'outputTokens', 'cacheReadInputTokens', 'cacheCreationInputTokens',
                'tokenTotal', 'estimatedCostUsd')


def _valid(value):
    return type(value) in (int, float) and 0 <= value <= 2**53 - 1 and math.isfinite(value)


def _date(value):
    try:
        result = datetime.fromisoformat(value) if isinstance(value, str) else value
        if not isinstance(result, datetime):
            return None
        return result.astimezone(timezone.utc).replace(tzinfo=None) if result.tzinfo is not None else result
    except ValueError:
        return None


def _duration(start, end):
    start, end = _date(start), _date(end)
    return round((end - start).total_seconds() * 1000, 3) if start is not None and end is not None and end >= start else None


def attempt_timings(run, queue, timing):
    timing = timing if isinstance(timing, dict) else {}
    return {'queueWaitMs': _duration(queue.created_at, queue.started_at) if queue is not None else None,
            'preAdapterMs': _duration(queue.started_at, timing.get('launchStartedAt')) if queue is not None else None,
            **{key: timing.get(key) if _valid(timing.get(key)) else None
               for key in ('adapterLaunchMs', 'firstSemanticTextMs', 'adapterWallMs')},
            'finalizationMs': _duration(timing.get('adapterTerminalAt'), run.ended_at),
            'attemptEndToEndMs': _duration(run.created_at, run.ended_at)}


@contextmanager
def stage_timer(stages, name):
    started = time.monotonic()
    try:
        yield
    except BaseException:
        stages[name] = None
        raise
    else:
        stages[name] = round(max(0, time.monotonic() - started) * 1000, 3)


def _distribution(values):
    known = sorted(value for value in values if _valid(value))
    return {'observed': len(known), 'unknown': len(values) - len(known),
            'p50Ms': known[math.ceil(.5 * len(known)) - 1] if known else None,
            'p95Ms': known[math.ceil(.95 * len(known)) - 1] if known else None,
            'maxMs': max(known) if known else None, 'quantileMethod': 'nearest_rank',
            'descriptiveOnly': True}


def measurement_summary(cases):
    attempts, calls, phases = [], [], []
    seen_runs, seen_calls = set(), set()
    for case_index, case in enumerate(cases):
        for phase_index, phase in enumerate(case.get('phases', [])):
            phases.append(phase)
            for call_index, call in enumerate(phase.get('plannerCalls', [])):
                key = call.get('callId') or (case_index, phase_index, call_index)
                if key not in seen_calls:
                    seen_calls.add(key)
                    calls.append(call.get('providerUsage') or {})
            for index, attempt in enumerate(phase.get('attempts', [])):
                key = attempt.get('taskRunId') or (case_index, phase_index, index)
                if key not in seen_runs:
                    seen_runs.add(key)
                    attempts.append(attempt)
                    calls.append(attempt.get('providerUsage') or {})
    fields = {}
    for key in USAGE_FIELDS:
        known = [call[key] for call in calls if _valid(call.get(key))]
        fields[key] = {'known': len(known), 'unknown': len(calls) - len(known),
                       'knownSum': round(sum(known), 9) if known else None,
                       'total': round(sum(known), 9) if calls and len(known) == len(calls) else None}
    stages = {key: _distribution([(attempt.get('stageTimings') or {}).get(key) for attempt in attempts]) for key in ATTEMPT_STAGES}
    stages.update({key: _distribution([(phase.get('stageTimings') or {}).get(key) for phase in phases]) for key in PHASE_STAGES})
    for field, key in (('elapsedSeconds', 'episodePipelineMs'), ('totalElapsedSeconds', 'episodeIncludingPreparationMs')):
        stages[key] = _distribution([case[field] * 1000 if _valid(case.get(field)) else None for case in cases])
    return {'providerUsage': {'callRecords': len(calls), 'plannerCallRecords': len(seen_calls),
                             'adapterAttemptRecords': len(attempts), 'fields': fields, 'verifiedBilling': False,
                             'scope': 'Deduplicated recorded Planner calls and all TaskRun attempts, including failures/retries. Missing values stay unknown; estimates are not bills.'},
            'stageTimings': stages,
            'limits': 'Application boundaries, not isolated model inference. Small fixed or mixed scenarios support descriptive quantiles only; no concurrency/production inference.'}
