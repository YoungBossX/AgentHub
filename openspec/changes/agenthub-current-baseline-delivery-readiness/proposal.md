## Why

The current `dev` worktree contains the delivered SSE recovery, source
modularization, and Windows TaskRun scope compatibility changes, but those
changes are not yet staged or published. Unit and project checks are green,
while the historical P18c run cannot be reused as proof of a successful current
TaskRun because its persisted run ended in post-provider failure.

## What changes

- Run one fresh, bounded real-Codex TaskRun against an isolated registered
  external Vite target through the public session, target, message, planner,
  scheduler, scope, adapter, Diff, Review, and Preview paths.
- Correct the Windows command guard so the health-probed `codex.exe` entrypoint
  is accepted exactly like the existing extensionless `codex` entrypoint,
  without admitting executable lookalikes.
- Resolve the canonical `pnpm dev` Preview command to the exact `pnpm.cmd`
  launcher on Windows while retaining the portable evidence command.
- Persist exact instruction and memory hashes, database entity IDs, provider
  events, scope decision, and changed-file evidence without rewriting the
  historical P18c record.
- Run the complete available project and documentation gates, audit the exact
  intended commit set, and clean reproducible temporary artifacts.

## Impact

- Adds one Windows runtime compatibility correction, delivery-readiness
  evidence, focused regression coverage, and synchronized project records.
- Does not change database schema, provider selection, dependency set, or
  deployment scope.
- Does not stage, commit, merge, or push; those remain explicit follow-up
  delivery actions after the evidence gates pass.
