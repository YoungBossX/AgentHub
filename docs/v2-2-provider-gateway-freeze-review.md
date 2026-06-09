# V2.2 Provider Gateway Freeze Review

**Date:** 2026-06-09

## Scope

V2.2 added a coding Provider Gateway between the Durable Run Engine and the
existing ClaudeCodeAdapter, CodexAdapter, and ScriptedMockAdapter.

Implemented:

- coding provider contract and safe evidence model
- ProviderRegistry / ProviderResolver for coding adapters only
- provider health probes for Claude Code, Codex, and ScriptedMock
- provider capacity limiter with idempotent release
- rate-limit evidence placeholder
- provider circuit breaker with closed/open/half_open states
- ProviderErrorClassifier and FallbackPolicy
- provider resolution, health, capacity, circuit, error, and fallback events
- Durable Run Engine integration for provider resolution before adapter launch

## Safety

- Planner providers remain separate from coding providers.
- No new adapter, marketplace, cloud Codex wrapper, Docker sandbox, WebSocket,
  or production deploy was added.
- ScriptedMock evidence stays marked as fallback/mock.
- Provider evidence is redacted for secrets, tokens, protected paths, and host
  paths.
- Provider failures are not converted into real provider success.

## Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_provider_gateway_contract.py tests/test_task_runs.py -q` | Pass |
| `pnpm check` | Pass |
| `pnpm demo:api:test` | Pass |
| `openspec validate agenthub-v2-2-provider-gateway --strict` | Pass |
| `git diff --check` | Pass |

## Limitations

- Circuit and capacity state are in-process for the local SQLite demo path.
- Full distributed provider quota/budget accounting is deferred.
- Fallback policy records evidence and selection, but deeper automatic
  provider retry chains should be hardened in later phases.
- Provider health probes are startup-path checks, not full interactive
  authentication smokes.

## Follow-up

Recommended follow-up: finish V2.3 freeze review, then complete V2.7 UI so
users can see provider gateway failures and next-step suggestions directly.
