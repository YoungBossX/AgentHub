## Why

P8 added dependency-aware scheduling and target locks, but it is still
scheduler v1. P9 now lets AgentHub operate on registered external local
projects, which raises the cost of stale runs, stale locks, unsafe retries, and
file conflicts.

P10 is needed to make external project execution safer and more recoverable
without changing AgentHub into a distributed worker platform.

## What Changes

- Add TaskRun heartbeat and lease metadata so running work can be detected as
  healthy, stale, timed out, or abandoned.
- Add stale target lock cleanup that releases only locks owned by stale runs
  and writes audit events.
- Add pre-run snapshots / checkpoints for write tasks, including git status,
  base commit, dirty files, target paths, and external target metadata.
- Harden retry idempotency by recording previous run context, detecting dirty
  worktrees, and blocking unsafe retries unless an explicit recovery decision
  is made.
- Harden failure propagation so failed dependencies block downstream work and
  preview/mock deploy never run after failed prerequisites.
- Add conflict detection for overlapping files, dirty worktrees, and contract
  drift.
- Add recovery actions for marking stale tasks failed, releasing stale locks,
  retrying from current state, retrying from checkpoint when safe, and stopping
  or resuming downstream progression.
- Rehearse P10 against stale task, stale lock, failed dependency, retry, and
  conflict scenarios while preserving P6/P7/P8/P9 baselines.

P10 preserves existing `CodexAdapter`, `ClaudeCodeAdapter`, and
`ScriptedMockAdapter` behavior. It must not claim real Claude/Codex success
unless a real run is executed and documented.

## Capabilities

### New Capabilities

- `scheduler-robustness`: TaskRun heartbeat/lease, stale lock cleanup,
  pre-run checkpoints, retry idempotency, failure propagation hardening,
  conflict detection, auditable recovery actions, and freeze rehearsal.

### Modified Capabilities

None. P10 adds a scheduler robustness layer while preserving P8 scheduler
semantics and P9 external project workspace mode.

## Impact

OpenSpec artifacts:

- `openspec/changes/agenthub-p10-scheduler-robustness-conflict-recovery/proposal.md`
- `openspec/changes/agenthub-p10-scheduler-robustness-conflict-recovery/design.md`
- `openspec/changes/agenthub-p10-scheduler-robustness-conflict-recovery/tasks.md`
- `openspec/changes/agenthub-p10-scheduler-robustness-conflict-recovery/specs/scheduler-robustness/spec.md`

Expected implementation impact when P10 is later applied:

- Backend:
  - TaskRun heartbeat / lease fields or equivalent durable metadata;
  - stale run and stale lock detection services;
  - pre-run checkpoint records and recovery metadata;
  - retry idempotency checks;
  - conflict detection for file overlap, dirty worktree, and contract drift;
  - auditable recovery actions through `TaskRunEvent` or a dedicated audit
    surface.
- Frontend:
  - scheduler robustness state in existing task timeline / execution trace;
  - visible stale, timed-out, conflict, unsafe retry, checkpoint, and recovery
    states;
  - recovery action affordances only where backed by explicit APIs.
- Runtime:
  - stale lock cleanup must not release active locks;
  - external target allowed/denied paths remain enforced;
  - unsafe retries are blocked or require explicit recovery decision;
  - preview and mock deploy stay gated by successful prerequisites;
  - no distributed worker cluster, Docker sandbox, production deploy,
    provider marketplace, PR creation, automatic Git conflict merge, multi-user
    IM, or enterprise RBAC is introduced.
