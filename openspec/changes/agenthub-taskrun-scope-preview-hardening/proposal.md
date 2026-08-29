## Why Change

The current Diff collector can apply a target path filter. That makes the shown
Diff useful, but it can also hide a write outside the TaskRun's approved scope
while the run still proceeds through Review, Preview, and Deploy. Because a
Session reuses one worktree across TaskRuns, comparing the worktree to a Git
base alone cannot distinguish a prior run's valid changes from the current
run's writes.

This change makes scope verification a fail-closed completion gate for writing
TaskRuns. It records a complete, unfiltered pre-run worktree footprint for
each run, compares it with the post-run footprint, and only permits final
completion and downstream artifacts after the delta passes the run's scope.

## What Changes

- Add a TaskRun scope guard that compares complete per-run pre- and post-run
  snapshots before a writing run can transition to `completed`.
- Persist scope-pass, violation, or unverifiable evidence in `TaskRun.metrics_json`.
- Fail a scope violation with `TASK_RUN_SCOPE_VIOLATION` and an unavailable or
  incomplete verification with `TASK_RUN_SCOPE_UNVERIFIABLE`.
- Require the persisted scope-pass marker before manual Diff, Review, Preview,
  or Deploy creation; historical runs without the marker fail closed.
- Keep protected-path exclusions as a separately recorded, safely redacted
  footprint rather than silently filtering them out of the evidence model.

## Impact

- Expected implementation touchpoints are the existing TaskRun lifecycle,
  snapshot/diff evidence, and artifact guard services and their focused tests.
- No new adapter, entity, migration, WebSocket, Docker sandbox, provider, or
  SSE contract is introduced.
- Existing `CodexAdapter`, `ClaudeCodeAdapter`, and `ScriptedMockAdapter`
  remain on the same execution path; only their final completion is gated.
