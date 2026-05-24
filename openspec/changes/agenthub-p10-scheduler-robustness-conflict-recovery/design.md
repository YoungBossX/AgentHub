## Context

P8 introduced dependency-aware scheduling, target write locks, automatic
bounded pipeline progression, failure blocking, retry/fallback state, and
scheduler UI trace. P9 then expanded execution from built-in demo targets to
registered external local projects with target registry metadata, external
TaskRuns, diff, command evidence, and review policy.

That combination makes scheduler correctness more important. A stale TaskRun
or stale target lock that was annoying for `apps/demo` can become risky for a
user-selected external project. P10 adds the robustness layer needed before
AgentHub should encourage broader external project usage.

Current constraints:

- AgentHub remains a local single-user Agent Coding Workspace.
- SQLite remains the local demo persistence layer.
- Existing adapters stay: `CodexAdapter`, `ClaudeCodeAdapter`,
  `ScriptedMockAdapter`.
- P8 scheduler semantics and P9 external workspace behavior must be preserved.
- External target allowed/denied paths remain enforced.
- Recovery actions must be auditable and must not fake success.

## Goals / Non-Goals

**Goals:**

- Track TaskRun liveness with heartbeat, lease, and runner identity.
- Detect stale running TaskRuns and mark timeouts honestly.
- Bind target locks to TaskRun owners and clean up only stale owned locks.
- Record pre-run checkpoints for write tasks across built-in and external
  targets.
- Make retries idempotent enough to avoid re-running blindly into dirty or
  conflicting worktrees.
- Harden downstream failure propagation, especially preview/mock deploy gating.
- Detect file overlap, dirty worktree, and contract drift conflicts.
- Provide auditable recovery actions for stale runs, stale locks, retry, and
  downstream pipeline control.
- Rehearse stale task, stale lock, failed dependency, retry, and conflict cases.

**Non-Goals:**

- Distributed worker cluster.
- Docker sandbox.
- Production deploy.
- Provider marketplace.
- PR creation.
- Full automatic Git conflict merge.
- Multi-user IM.
- Enterprise RBAC.
- Changing adapter execution semantics beyond scheduler/recovery metadata.

## Decisions

### Decision: Heartbeat And Lease Live On TaskRun Metadata First

P10 should add durable heartbeat fields on `TaskRun` or an equivalent
TaskRun-owned metadata surface:

```text
lastHeartbeatAt
leaseExpiresAt
runnerId
staleDetectedAt
staleReason
```

Rationale: P8 already treats TaskRun as the execution owner for scheduler
state and target locks. Keeping liveness anchored to TaskRun avoids adding a
separate worker cluster model.

Alternative considered: create a separate worker/runner table. Deferred
because P10 is not a distributed worker system.

### Decision: Target Locks Are Owner-bound And Recomputed

Target locks should remain compatible with the P8 lock behavior but become
owner-bound:

```text
targetId
taskRunId
sessionId
lockMode: write | read
acquiredAt
leaseExpiresAt
releasedAt
releaseReason
```

The implementation may persist explicit lock records or derive them from
active TaskRuns plus scheduler metadata, as long as stale cleanup can identify
the owning TaskRun and write an audit event.

Alternative considered: global target lock rows only. Deferred because they
make stale ownership and cleanup less traceable.

### Decision: Pre-run Checkpoint Is Required For Write Tasks

Before creating or starting a write TaskRun, AgentHub should record:

```text
targetId
targetRoot
allowedPaths
deniedPaths
baseCommit
gitStatus
dirtyFiles
plannedFiles
contractId
contractHash
createdAt
```

Rationale: retries and recovery need a known starting point. This is especially
important for external targets that may already have local uncommitted work.

Alternative considered: rely on `base_ref` only. Rejected because it misses
dirty files, path policy, contract drift, and target metadata.

### Decision: Unsafe Retry Blocks Instead Of Guessing

Retries should record:

```text
previousRunId
failureSummary
retryMode
checkpointId
dirtyWorktreeDecision
```

If the target has dirty files outside the checkpoint or planned safe paths, the
retry must be blocked or require an explicit recovery decision. P10 must not
auto-reset or auto-merge.

Alternative considered: always retry from current state. Deferred because it
can compound partial adapter changes on external projects.

### Decision: Conflict Detection Is Conservative

P10 should detect conflicts and stop, not merge:

- file overlap conflict: two runnable write tasks plan or touch overlapping
  files;
- dirty worktree conflict: target has uncommitted files not expected by the
  checkpoint;
- contract drift conflict: downstream task references a contract hash/version
  that no longer matches the active contract.

Rationale: conservative conflict detection protects the workspace while keeping
P10 implementation bounded.

Alternative considered: automatic Git conflict resolution. Explicit non-goal.

### Decision: Recovery Actions Are Explicit And Audited

Every recovery action must append a `TaskRunEvent` or equivalent audit record:

- mark stale task failed;
- release stale lock;
- retry from current state;
- retry from checkpoint if safe;
- stop downstream pipeline;
- resume downstream pipeline after dependencies and locks are valid.

Rationale: AgentHub must remain inspectable. Recovery without audit would make
external project changes hard to trust.

## Risks / Trade-offs

- **Risk: False stale detection marks an active run failed.** Mitigation:
  leases need grace periods, runner IDs, and heartbeat freshness checks before
  cleanup.
- **Risk: Stale lock cleanup releases an active lock.** Mitigation: cleanup
  only if owner TaskRun is stale/timed out and record an audit event naming the
  owner.
- **Risk: Checkpoint records sensitive paths.** Mitigation: checkpoint metadata
  must respect protected path redaction and must not include secrets content.
- **Risk: Retry logic becomes too strict.** Mitigation: allow explicit recovery
  decisions while keeping unsafe automatic retry blocked.
- **Risk: Conflict detection blocks legitimate local edits.** Mitigation:
  surface file names, reason, and recovery options instead of silently failing.
- **Risk: P10 adds too much schema churn.** Mitigation: start with TaskRun,
  Artifact, and TaskRunEvent metadata where practical, adding tables only when
  durable queryability requires them.

## Migration Plan

1. Add heartbeat/lease and checkpoint metadata in a backward-compatible way.
2. Ensure existing TaskRuns without heartbeat fields are treated as legacy and
   not automatically stale unless they are active and clearly expired under new
   rules.
3. Add stale detection and cleanup APIs/services behind explicit scheduler
   calls.
4. Add retry and conflict checks before changing default UI behavior.
5. Rehearse P10 with controlled local scenarios before claiming freeze.

Rollback strategy: P10 should be removable by ignoring the new robustness
metadata and keeping the P8 scheduler path active. No recovery action should
destructively mutate worktrees without explicit user decision.

## Open Questions

- Should checkpoints be first-class database rows or `Artifact` /
  `TaskRunEvent` metadata in the first implementation?
- What default heartbeat interval and lease timeout should local runner tasks
  use?
- Which recovery actions need UI buttons in P10 versus API-only rehearsal?
- Should external command evidence execution remain manual/API-fed, or should a
  later P11 add controlled command execution?
