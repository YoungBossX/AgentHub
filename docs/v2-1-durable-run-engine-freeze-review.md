# V2.1 Durable Run Engine Freeze Review

**Date:** 2026-06-09

## Scope

V2.1 rebuilt the TaskRun execution boundary without replacing the existing
ClaudeCodeAdapter, CodexAdapter, Scheduler, Target Registry, PlanValidator,
diff/review/preview/deploy evidence, or ScriptedMock fallback.

Implemented:

- `run_engine.py` execution boundary.
- `run_supervisor.py` active run registry.
- shared run scheduling helper.
- worker claim / lease / heartbeat.
- durable worker `run_once` over queued TaskRuns.
- active run supervisor registration.
- adapter run id callback from `run_adapter_event_stream`.
- interrupt path that attempts supervisor adapter interrupt before DB state
  transition.
- max runtime timeout failure path.
- startup/stale recovery helper using existing stale TaskRun recovery.
- completed run finalizer boundary for diff/review/ledger/preview/deploy and
  downstream auto-start.
- mission trace durable run evidence.

## Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_task_runs.py -q` | Pass |
| `pnpm check` | Pass |
| `pnpm demo:api:test` | Pass |
| `openspec validate agenthub-v2-1-durable-run-engine --strict` | Pass |
| `git diff --check` | Pass |

## Evidence

TaskRun and mission trace now expose:

- `runnerId`
- `adapterRunId`
- `startedAt`
- `endedAt`
- `lastHeartbeatAt`
- `leaseExpiresAt`
- `staleDetectedAt`
- `staleReason`
- provider assignment and runtime config evidence already present in metrics

## Limitations

- V2.1 still uses an in-process FastAPI background task as a worker wake-up
  mechanism. The work itself is now routed through `RunWorker`, but a separate
  long-lived worker process is deferred.
- SQLite claim is still minimal and will be strengthened by V2.3 explicit
  queue/target lock work.
- Provider rate limits, circuit breaker, fallback policy, and provider health
  alignment are deferred to V2.2.
- Fine-grained idle stdout timeout is deferred to the provider/process gateway
  layer because current adapters stream stdout internally.
- Transactional rollback/accept flows are deferred to V2.6.

## Follow-up

Recommended next implementation phase: V2.2 Provider Gateway, followed by V2.3
Session Queue and Target Lock.

