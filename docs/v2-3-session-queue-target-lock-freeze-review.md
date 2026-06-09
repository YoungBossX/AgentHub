# V2.3 Session Queue And Target Lock Freeze Review

**Date:** 2026-06-09

## Scope

V2.3 upgraded scheduling from inferred active-run soft locks to persisted queue
and lock evidence.

Implemented:

- `SessionQueueEntry` model and queue helpers.
- `TargetLock` model and SQLite-compatible acquire/release helpers.
- `PreviewDeployJob` model and preview/deploy job evidence helpers.
- TaskRun creation and terminal transitions now maintain queue/lock state.
- Durable Run Engine checks queue and target lock before launching adapters.
- Scheduler readiness reads persisted queue/lock state.
- Stale queue and lock recovery records evidence and never claims provider
  success when provider result cannot be confirmed.
- MissionTrace and TaskRun responses include queue, lock, and preview/deploy job
  diagnostics.

## Safety

- Same-session write runs are serialized.
- Cross-session writes to the same target compete for the same DB target lock.
- Waiting approval, blocked dependencies, unsafe paths, and terminal runs do not
  bypass queue/lock gates.
- Preview/deploy jobs record evidence separately and do not overwrite coding run
  terminal state.

## Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_session_queue.py tests/test_target_locks.py tests/test_scheduler.py tests/test_task_runs.py -q` | Pass |
| `pnpm test` | Pass |
| `pnpm check` | Pass |
| `pnpm demo:api:test` | Pass |
| `openspec validate agenthub-v2-3-session-queue-target-lock --strict` | Pass |
| `git diff --check` | Pass |

## Limitations

- Queue and lock state are still SQLite/local-demo scoped.
- Preview/deploy job execution is still synchronous inside finalization for this
  phase, but evidence is now represented as separate job records.
- Fine-grained path-range locks are deferred.
- Broader policy approval, rollback, and ProjectProfile behavior remain later
  Reliability V2 phases.

## Follow-up

Recommended follow-up: finish V2.7 UI so queue/lock/provider diagnostics are
visible in the task cards and mission panel.
