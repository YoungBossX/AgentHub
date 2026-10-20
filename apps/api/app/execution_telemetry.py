"""Bounded provider-reported usage and application-observed adapter timings."""
from datetime import datetime, timezone
import math
import re
import time


def _number(value, *, integer=False):
    if type(value) not in ((int,) if integer else (int, float)):
        return None
    return value if 0 <= value <= 2**53 - 1 and math.isfinite(value) else None


def provider_usage(raw, protocol='claude_cli'):
    raw = raw if isinstance(raw, dict) else {}
    usage = raw.get('usage') if isinstance(raw.get('usage'), dict) else {}
    claude = protocol == 'claude_cli'
    tokens = {'inputTokens': _number(usage.get('input_tokens'), integer=True),
              'outputTokens': _number(usage.get('output_tokens'), integer=True),
              'cacheReadInputTokens': _number(usage.get('cache_read_input_tokens' if claude else 'cached_input_tokens'), integer=True),
              'cacheCreationInputTokens': _number(usage.get('cache_creation_input_tokens'), integer=True) if claude else None}
    required = list(tokens.values()) if claude else [tokens['inputTokens'], tokens['outputTokens']]
    complete = all(value is not None for value in required)
    models = raw.get('modelUsage')
    names = sorted(name for name in models if isinstance(name, str)
                   and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,99}', name))[:16] if isinstance(models, dict) else []
    return {'schemaVersion': 'agenthub.provider_usage.v1', 'source': protocol + '_result',
            'status': 'reported' if complete else 'partial' if any(v is not None for v in tokens.values()) else 'unavailable',
            **tokens, 'tokenTotal': sum(required) if complete else None,
            'tokenConvention': 'uncached_input_plus_cache_plus_output' if claude else 'input_includes_cache_plus_output',
            'estimatedCostUsd': _number(raw.get('total_cost_usd')) if claude else None,
            'billingVerified': False, 'reportedModels': names,
            'providerDurationMs': _number(raw.get('duration_ms')),
            'providerApiDurationMs': _number(raw.get('duration_api_ms')),
            'providerTurns': _number(raw.get('num_turns'), integer=True),
            'scope': 'One independent CLI call final result, not streamed snapshots; provider-reported values and CLI estimates, not verified upstream billing.'}


def is_semantic_text(event):
    payload = event.payload
    if event.type != 'message.delta' or not isinstance(payload.get('text'), str) or not payload['text'].strip():
        return False
    if payload.get('adapter') == 'claude_code':
        return payload.get('claudeEventType') in {'assistant', 'message', 'message.delta', 'content_block_delta'} or (
            payload.get('claudeEventType') == 'stream_event'
            and payload.get('claudeStreamEventType') in {'content_block_start', 'content_block_delta'})
    return payload.get('adapter') == 'codex' and (
        payload.get('codexEventType') in {'message.delta', 'agent_message_delta'} or (
            payload.get('codexEventType') == 'item.completed' and payload.get('codexItemType') == 'agent_message'))


class AdapterTiming:
    def __init__(self):
        self.started = time.monotonic()
        self.values = {'schemaVersion': 'agenthub.execution_timing.v1',
                       'launchStartedAt': datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
                       'adapterLaunchMs': None, 'firstSemanticTextMs': None,
                       'adapterWallMs': None, 'adapterTerminalAt': None,
                       'firstTextScope': 'Application-observed redacted semantic text after adapter launch began; not model first-token latency.'}

    def launched(self):
        self.values['adapterLaunchMs'] = self.elapsed()

    def elapsed(self):
        return round(max(0, time.monotonic() - self.started) * 1000, 3)

    def observe(self, event):
        changed = False
        if self.values['firstSemanticTextMs'] is None and is_semantic_text(event):
            self.values['firstSemanticTextMs'] = self.elapsed()
            changed = True
        if event.type in {'completed', 'error'}:
            self.values['adapterWallMs'] = self.elapsed()
            self.values['adapterTerminalAt'] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
            changed = True
        if changed:
            event.payload['executionTiming'] = dict(self.values)
