# V2.6 Transactional Delivery Freeze Review

**Date:** 2026-06-09

## Scope

V2.6 adds a transactional delivery evidence layer over existing TaskRun
checkpoint, diff, review, command evidence, recovery, and diagnostics paths.

Implemented:

- Delivery states and retry modes.
- Checkpoint evidence projection from existing TaskRun `preRunCheckpoint`
  metrics.
- Pending validation and rollback preflight decisions.
- Validation gate helper that turns failed command evidence, denied policy
  evidence, and high-risk review evidence into `review_required`.
- Delivery artifact state and accept decision evidence.
- Rollback decision evidence that records checkpoint restore intent and refuses
  missing checkpoints.
- Explicit retry mode evidence for current state vs checkpoint retry.
- TaskRunEvent recording helper for delivery decisions.
- Run Diagnostics mapping for `delivery.*` events.

## Safety

- V2.6 does not replace Durable Run Engine, Provider Gateway, Session Queue,
  Target Lock, Policy Engine, or Run Diagnostics.
- V2.6 does not add new adapters, WebSocket, Docker sandbox, PR/export,
  production deployment, or planner core rewrites.
- Rollback helpers currently record safe evidence and preflight decisions; they
  do not perform destructive worktree restoration yet.
- Validation failure is represented as `review_required` evidence and must not
  be claimed as successful delivery.

## Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_transactional_delivery.py tests/test_recovery.py -q` | Pass |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_transactional_delivery.py tests/test_run_diagnostics.py -q` | Pass |
| `pnpm check` | Pass |
| `pnpm test` | Pass, web 90 / API 582 / demo-api 5 |
| `pnpm demo:api:test` | Pass, 5 tests |
| `openspec validate agenthub-v2-6-transactional-delivery --strict` | Pass |
| `git diff --check` | Pass |

## Limitations

- V2.6 intentionally keeps actual rollback execution out of scope. The current
  implementation records rollback readiness/refusal and restore intent.
- Run Engine finalizer behavior is not changed to block preview/deploy jobs on
  delivery validation yet; V2.6 provides the evidence hooks and diagnostics
  mapping for that next integration.
- Accept records artifact-state evidence but does not merge changes to another
  branch or create PR/export artifacts.

## Follow-up

Recommended follow-up: wire transactional delivery gates into Run Engine
finalization so validation failure pauses downstream preview/deploy until the
user accepts, rolls back, or retries.
