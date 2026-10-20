"""Reported usage must stay bounded, nullable and separate from billing."""
import json
import subprocess

import pytest

from app.claude_code_adapter import _map_claude_json_event
from app.planner_providers import ClaudeCliPlannerProvider


@pytest.mark.parametrize('failed', [False, True])
def test_claude_result_usage_survives_success_and_failure(failed):
    raw = {'type': 'result', 'is_error': failed, 'result': 'failed' if failed else '完成',
           'usage': {'input_tokens': 12, 'output_tokens': 8, 'cache_read_input_tokens': 40,
                     'cache_creation_input_tokens': 5, 'secret': 'must-not-persist'},
           'total_cost_usd': 0.25, 'duration_ms': 2300, 'duration_api_ms': 1800, 'num_turns': 3,
           'modelUsage': {'reported-model': {'inputTokens': 12, 'outputTokens': 8}},
           'api_key': 'must-not-persist'}
    event = _map_claude_json_event(raw, 'run', '', [])
    assert event.type == ('error' if failed else 'completed')
    receipt = event.payload.get('providerUsage')
    assert isinstance(receipt, dict), 'Result usage is currently discarded'
    assert receipt['inputTokens'] == 12 and receipt['outputTokens'] == 8
    assert receipt['cacheReadInputTokens'] == 40 and receipt['cacheCreationInputTokens'] == 5
    assert receipt['tokenTotal'] == 65
    assert receipt['estimatedCostUsd'] == 0.25 and receipt['billingVerified'] is False
    assert receipt['providerDurationMs'] == 2300 and receipt['providerApiDurationMs'] == 1800
    assert receipt['reportedModels'] == ['reported-model']
    assert 'must-not-persist' not in json.dumps(receipt)


@pytest.mark.parametrize('bad', [None, True, -1, '12', float('inf'), float('nan'), 2.5])
def test_invalid_or_missing_token_values_remain_unknown(bad):
    event = _map_claude_json_event({'type': 'result', 'usage': {'input_tokens': bad, 'output_tokens': 0}}, 'run', '', [])
    receipt = event.payload.get('providerUsage')
    assert isinstance(receipt, dict), 'Missing usage must be explicit, not a zero-filled success'
    assert receipt['inputTokens'] is None and receipt['outputTokens'] == 0
    assert receipt['cacheReadInputTokens'] is None and receipt['tokenTotal'] is None
    assert receipt['estimatedCostUsd'] is None and receipt['status'] == 'partial'


def test_legitimate_zero_usage_is_distinct_from_no_receipt():
    zero = _map_claude_json_event({'type': 'result', 'usage': {'input_tokens': 0, 'output_tokens': 0,
        'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0}, 'total_cost_usd': 0}, 'run', '', []).payload.get('providerUsage')
    absent = _map_claude_json_event({'type': 'result'}, 'run', '', []).payload.get('providerUsage')
    assert zero and absent, 'Explicit usage metadata is missing'
    assert zero['tokenTotal'] == 0 and zero['estimatedCostUsd'] == 0
    assert absent['tokenTotal'] is None and absent['status'] == 'unavailable'


@pytest.mark.parametrize('stream', [False, True])
def test_planner_unwraps_json_and_preserves_one_final_usage_receipt(stream):
    raw = {'type': 'result', 'result': '{"tasks": []}',
           'usage': {'input_tokens': 9, 'output_tokens': 3, 'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0},
           'total_cost_usd': 0.01}
    observed = {}
    class Runner:
        def run(self, command, *, timeout, input_text=None):
            observed['command'] = command
            stdout = json.dumps(raw)
            if stream:
                stdout = json.dumps({'type': 'assistant', 'message': {'usage': {'input_tokens': 9}}}) + '\n' + stdout
            return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr='')
    result = ClaudeCliPlannerProvider(command_runner=Runner(), claude_binary='claude').create_plan({
        'originalUserRequest': '需求' * (15000 if stream else 1), 'agentToolPolicy': 'planner_no_tools'})
    assert result.status == 'succeeded' and result.raw_output == '{"tasks": []}'
    receipt = result.to_metadata().get('providerUsage')
    assert receipt and receipt['tokenTotal'] == 12
    assert receipt['source'] == 'claude_cli_result'
    assert observed['command'][observed['command'].index('--output-format') + 1] == ('stream-json' if stream else 'json')


@pytest.mark.parametrize('stream', [False, True])
def test_planner_error_result_preserves_reported_usage(stream):
    class Runner:
        def run(self, command, **kwargs):
            return subprocess.CompletedProcess(command, 1, stdout=json.dumps({'type': 'result', 'is_error': True,
                'result': 'only support text input', 'usage': {'input_tokens': 5, 'output_tokens': 2}}), stderr='')
    result = ClaudeCliPlannerProvider(command_runner=Runner(), claude_binary='claude').create_plan({'originalUserRequest': '需求' * (15000 if stream else 1)})
    assert result.status == 'failed'
    assert result.to_metadata().get('providerUsage', {}).get('inputTokens') == 5


def test_codex_total_does_not_add_cached_input_twice():
    from app.codex_adapter import _map_codex_json_event
    event = _map_codex_json_event({'type': 'turn.completed', 'usage': {
        'input_tokens': 100, 'cached_input_tokens': 80, 'output_tokens': 7}}, 'run', '', [])
    receipt = event.payload.get('providerUsage')
    assert receipt and receipt['tokenTotal'] == 107
    assert receipt['cacheReadInputTokens'] == 80
    assert receipt['estimatedCostUsd'] is None


def test_codex_agent_message_is_semantic_but_tool_json_is_not():
    from app.codex_adapter import _map_codex_json_event
    from app.execution_telemetry import is_semantic_text
    message = _map_codex_json_event({'type': 'item.completed', 'item': {
        'type': 'agent_message', 'text': '实际回复'}}, 'run', '', [])
    tool = _map_codex_json_event({'type': 'item.completed', 'item': {
        'type': 'command_execution', 'text': '工具输出'}}, 'run', '', [])
    assert message.payload['text'] == '实际回复' and is_semantic_text(message)
    assert not is_semantic_text(tool)
