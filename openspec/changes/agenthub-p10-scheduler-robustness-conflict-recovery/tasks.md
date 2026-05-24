## 1. P10 Scheduler Robustness And Conflict Recovery

- [ ] 1.1 P10-1 TaskRun Heartbeat And Lease.
  - Objective: make TaskRun liveness explicit so running work can be
    classified as healthy, stale, timed out, or terminal.
  - Scope:
    - Add durable `runnerId`, `lastHeartbeatAt`, `leaseExpiresAt`, and stale
      reason metadata on `TaskRun` or an equivalent TaskRun-owned metadata
      surface.
    - Refresh heartbeat metadata while local TaskRun execution is active.
    - Detect expired leases without newer heartbeats.
    - Mark stale/timed-out runs honestly without claiming adapter success.
    - Record a `TaskRunEvent` audit entry when stale detection changes state.
  - Acceptance criteria:
    - Active TaskRuns have runner and lease metadata.
    - Unexpired TaskRuns are not marked stale.
    - Expired running TaskRuns become stale/timed-out or equivalent terminal
      failures.
    - Stale transition records runner ID, lease timestamp, and reason.
  - Validation:
    - Add or update focused heartbeat/lease tests.
    - Run `pnpm check`.
    - Run `pnpm test`.
    - Run `git diff --check`.
    - Run `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict`.

- [ ] 1.2 P10-2 Stale Target Lock Cleanup.
  - Objective: ensure target write locks are owned, auditable, and safely
    releasable only when their owning TaskRun is stale or terminal.
  - Scope:
    - Bind scheduler target locks to owning `taskRunId`, `sessionId`,
      `targetId`, lock mode, acquisition time, and lease expiration.
    - Keep active locks held when the owner heartbeat and lease are valid.
    - Release locks only when the owner TaskRun is stale, timed out, or already
      terminal.
    - Record cleanup audit events with lock, target, owner, actor, and reason.
  - Acceptance criteria:
    - Same-target write tasks remain blocked by active locks.
    - Stale owner locks can be released without releasing active locks.
    - Cleanup is traceable through TaskRunEvent or equivalent audit metadata.
    - External targets use the same lock cleanup rules as built-in targets.
  - Validation:
    - Add or update target lock cleanup tests.
    - Run `pnpm check`.
    - Run `pnpm test`.
    - Run `git diff --check`.
    - Run `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict`.

- [ ] 1.3 P10-3 Pre-run Snapshot / Checkpoint.
  - Objective: capture the target state before write execution so retry and
    recovery can reason from a known baseline.
  - Scope:
    - Record a pre-run checkpoint before built-in and external write TaskRuns.
    - Include target ID, target root, allowed paths, denied paths, base commit,
      git status, dirty files, planned files, contract ID/hash when available,
      and creation time.
    - Redact or omit denied path contents and secrets.
    - Expose checkpoint metadata through API/UI surfaces needed to explain
      retry safety.
  - Acceptance criteria:
    - Write TaskRuns have checkpoint metadata before adapter execution starts.
    - External target checkpoints use Target Registry path policy.
    - Checkpoints never expose denied path contents.
    - Retry/recovery code can read checkpoint metadata.
  - Validation:
    - Add or update checkpoint tests for demo and external targets.
    - Run `pnpm check`.
    - Run `pnpm test`.
    - Run `git diff --check`.
    - Run `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict`.

- [ ] 1.4 P10-4 Retry Idempotency.
  - Objective: make retries traceable and prevent automatic retries into unsafe
    dirty or conflicting worktrees.
  - Scope:
    - Record `previousRunId`, failure summary, retry mode, checkpoint reference,
      and dirty worktree decision on retry runs.
    - Detect dirty files outside checkpoint, selected artifact, or planned safe
      paths before retry.
    - Block unsafe automatic retry and surface that explicit recovery is
      required.
    - Allow safe retry through the existing TaskRun path when dependencies and
      locks permit.
  - Acceptance criteria:
    - Retry history links back to the failed/interrupted TaskRun.
    - Unsafe retry is blocked with an explainable reason.
    - Safe retry creates a new TaskRun without erasing prior evidence.
    - Retry does not fake adapter success or bypass target policy.
  - Validation:
    - Add or update retry idempotency tests.
    - Run `pnpm check`.
    - Run `pnpm test`.
    - Run `git diff --check`.
    - Run `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict`.

- [ ] 1.5 P10-5 Failure Propagation Hardening.
  - Objective: prevent downstream execution, preview, and mock deploy from
    proceeding after failed prerequisites.
  - Scope:
    - Ensure failed, interrupted, stale, timed-out, or blocked dependencies keep
      downstream tasks in blocked/waiting states.
    - Re-evaluate downstream eligibility only after retry/fallback/recovery
      succeeds and dependency, lock, approval, and conflict checks pass.
    - Gate preview and mock deploy creation behind successful coding
      prerequisites.
    - Surface failed prerequisite information in scheduler state.
  - Acceptance criteria:
    - Failed dependencies block downstream tasks.
    - Successful retry/fallback can unblock downstream tasks after re-check.
    - Preview and mock deploy do not auto-run after failed prerequisites.
    - Existing P8 dependency semantics remain intact.
  - Validation:
    - Add or update failure propagation and preview/deploy gating tests.
    - Run `pnpm check`.
    - Run `pnpm test`.
    - Run `pnpm demo:api:test`.
    - Run `git diff --check`.
    - Run `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict`.

- [ ] 1.6 P10-6 Conflict Detection.
  - Objective: identify common conflicts early and stop rather than attempting
    automatic merge or unsafe execution.
  - Scope:
    - Detect file overlap conflicts between runnable write tasks in the same
      session or target pipeline.
    - Detect dirty worktree conflicts outside checkpoint, selected artifact, or
      planned safe paths.
    - Detect app contract drift when downstream tasks reference a stale
      contract ID/hash/version.
    - Surface conflict details and recovery options without auto-merging.
  - Acceptance criteria:
    - Overlapping planned or touched files block unsafe concurrent writes.
    - Dirty worktree conflicts prevent automatic write execution.
    - Stale contract references block downstream implementation.
    - No complex conflict is auto-merged in P10.
  - Validation:
    - Add or update conflict detection tests.
    - Run `pnpm check`.
    - Run `pnpm test`.
    - Run `git diff --check`.
    - Run `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict`.

- [ ] 1.7 P10-7 Recovery Actions.
  - Objective: provide explicit, auditable recovery actions for stale runs,
    stale locks, retry decisions, and downstream pipeline control.
  - Scope:
    - Add recovery actions to mark stale TaskRun failed, release stale lock,
      retry from current state, retry from checkpoint when safe, stop downstream
      progression, and resume downstream progression.
    - Validate each recovery action against lease, lock, checkpoint, conflict,
      dependency, and target policy state.
    - Record actor, reason, previous state, new state, and affected IDs in audit
      events.
    - Expose UI or API affordances only for actions that are implemented and
      safe.
  - Acceptance criteria:
    - Recovery actions are explicit and auditable.
    - Stale lock release cannot release an active owned lock.
    - Retry from checkpoint does not destructively reset files outside allowed
      target paths.
    - Stop/resume downstream pipeline updates scheduler eligibility visibly.
  - Validation:
    - Add or update recovery action tests.
    - Run `pnpm check`.
    - Run `pnpm test`.
    - Run `git diff --check`.
    - Run `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict`.

- [ ] 1.8 P10-8 Robustness Rehearsal And Freeze Review.
  - Objective: verify P10 robustness behavior end to end and decide whether the
    change is ready to freeze.
  - Scope:
    - Rehearse stale TaskRun detection.
    - Rehearse stale target lock cleanup.
    - Rehearse failed dependency blocking and downstream re-evaluation.
    - Rehearse retry safety and unsafe retry blocking.
    - Rehearse file overlap, dirty worktree, and contract drift conflicts.
    - Verify P6/P7/P8/P9 baselines remain intact, including P9 external project
      workspace mode.
    - Update `docs/project-state.md`, `docs/change-log.md`, and this task list
      with final evidence and caveats.
  - Acceptance criteria:
    - P10 scenarios are documented with evidence IDs or test names.
    - P9 external project execution remains target-policy aware.
    - P8 scheduler dependency and target lock semantics remain intact.
    - No unverified Claude/Codex success is claimed.
    - P10 caveats and deferred work are documented.
  - Validation:
    - Run `pnpm check`.
    - Run `pnpm test`.
    - Run `pnpm demo:api:test`.
    - Run `git diff --check`.
    - Run `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict`.

## Explicit Non-goals

- Distributed worker cluster.
- Docker sandbox.
- Production deploy.
- Provider marketplace.
- PR creation.
- Full automatic Git conflict merge.
- Multi-user IM.
- Enterprise RBAC.
- Unrestricted repository editing or bypassing P7 Target Registry policy.
- Changing `CodexAdapter`, `ClaudeCodeAdapter`, or `ScriptedMockAdapter`
  execution semantics.

## Definition Of Done

P10 is done only when heartbeat/lease, stale lock cleanup, checkpoints, retry
idempotency, failure propagation hardening, conflict detection, recovery
actions, and freeze rehearsal are implemented and verified without regressing
P6/P7/P8/P9 baselines. Unsafe retries and conflicts must stop honestly, recovery
actions must be auditable, external target allowed/denied paths must remain
enforced, and no real Claude/Codex success may be claimed without real evidence.
