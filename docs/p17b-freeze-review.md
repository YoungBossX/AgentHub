# P17b Freeze Review: Multi-provider Planner API

Date: 2026-06-01

## Summary

P17b added AgentHub-native Planner API provider support while preserving the
P17 boundary between conversation/planning and coding-agent execution.

Supported Planner protocols and presets:

- `openai_responses`: `openai_api`
- `openai_compatible_chat`: `deepseek_api`, `mimo_api`,
  `custom_openai_compatible`
- `anthropic_messages`: `anthropic_api`
- existing `claude_cli`, `fake_test`, and `disabled`

API planner providers only return `ConversationOutcome` and optional PlanDraft
payloads. They do not edit files, run commands, deploy, or replace
ClaudeCodeAdapter/CodexAdapter.

## Secret Handling

Runtime config stores only provider metadata:

- provider preset id
- protocol
- model
- base URL
- timeout
- `apiKeyEnv`

Raw API keys are read only from environment variables. They are not returned in
runtime config responses, planner evidence, mission trace, errors, or logs.

The user provided DeepSeek and MiMo raw keys in chat, but those values were not
written into files, commands, logs, or commits. The current process environment
did not contain `DEEPSEEK_API_KEY` or `MIMO_API_KEY`, so no real DeepSeek/MiMo
API success is claimed.

## Rehearsal Evidence

Real API smoke:

- `DEEPSEEK_API_KEY`: missing in process environment
- `MIMO_API_KEY`: missing in process environment
- Result: real provider smoke skipped honestly; missing-key path verified

Fake-client / policy evidence:

- OpenAI Responses fake-client success passed
- OpenAI-compatible fake-client success passed
- Anthropic Messages fake-client success passed
- missing-key metadata for OpenAI, DeepSeek, MiMo, Anthropic, and custom envs
  passed
- `你好` produced an Orchestrator assistant reply with no TaskRun
- `帮我做打砖块` produced a validated task plan when a planner returned a plan
- unsafe requests remained non-executing refusal/approval outcomes

## Validation

Commands run during P17b rehearsal:

| Command | Result |
|---|---|
| `pnpm test` | Pass: web 45 tests, API 376 tests, demo-api 5 tests. |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_providers.py tests/test_agent_runtime_config.py tests/test_llm_planner.py tests/test_planning.py::test_api_planner_assistant_reply_creates_orchestrator_message_without_task -q` | Pass: 83 tests. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | Pass. |

## Caveats

- No real DeepSeek or MiMo API call was run because keys were not available via
  environment variables.
- API planner providers are Planner-only; coding agents remain separate.
- Full provider marketplace, cloud token manager, production deploy, and API
  LLM coding agents remain out of scope.

Recommended tag: `p17b-multi-provider-planner-api-freeze`.
