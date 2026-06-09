# V2.7 Run Diagnostics Freeze Review

**Date:** 2026-06-09

## Scope

V2.7 added a safe diagnostics projection over TaskRun, TaskRunEvent, provider
gateway, queue, lock, preview, deploy, and artifact evidence.

Implemented:

- RunDiagnostics response model.
- failure category classifier and primary/contributing factor selection.
- run timeline builder.
- provider/queue/lock/preview/deploy health summaries.
- next-step suggestion model.
- `GET /task-runs/{task_run_id}/diagnostics`.
- `GET /sessions/{session_id}/run-diagnostics-summary`.
- Mission panel diagnostic summary using TaskRun provider/queue/lock/job
  evidence.

## Safety

- Diagnostics do not change execution semantics.
- No new adapter, WebSocket, Docker sandbox, external IM, PR, or deployment
  behavior was added.
- Metadata and evidence are redacted before being exposed.
- Missing evidence is shown as unknown/limited, not inferred success.
- ScriptedMock remains visibly mock/fallback evidence.

## Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_run_diagnostics.py -q` | Pass |
| `pnpm --filter @agenthub/web test -- mission-panel.test.tsx` | Pass |
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `pnpm demo:api:test` | Pass |
| `openspec validate agenthub-v2-7-run-diagnostics --strict` | Pass |
| `git diff --check` | Pass |

## Limitations

- The first UI pass intentionally stays compact and surfaces diagnostics in the
  mission panel rather than adding a full detail drawer.
- Suggestion action buttons remain tied to existing retry/settings/artifact
  flows; new automatic remediation is deferred.
- Timeline display is available through API and summarized in UI, with richer
  visual timeline reserved for a later pass.

## Follow-up

Recommended follow-up: add a dedicated run diagnostics drawer after V2.4/V2.5
stabilize ProjectProfile and Policy Engine signals.
