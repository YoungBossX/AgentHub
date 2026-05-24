## ADDED Requirements

### Requirement: TaskRun Heartbeat And Lease

The system MUST record TaskRun liveness metadata so local execution can be
classified as active, stale, timed out, or terminal.

#### Scenario: TaskRun heartbeat is recorded

- **WHEN** a TaskRun is created or begins execution
- **THEN** the system MUST record a `runnerId`, `lastHeartbeatAt`, and
  `leaseExpiresAt` value for that TaskRun
- **AND** subsequent heartbeat updates MUST refresh `lastHeartbeatAt` and
  `leaseExpiresAt`.

#### Scenario: Running TaskRun becomes stale

- **WHEN** a TaskRun is in an active running state
- **AND** its lease has expired without a newer heartbeat
- **THEN** the system MUST identify the TaskRun as stale
- **AND** the system MUST NOT claim the adapter completed successfully.

#### Scenario: Stale TaskRun is marked honestly

- **WHEN** stale detection marks a TaskRun timed out or abandoned
- **THEN** the TaskRun MUST move to a failed, interrupted, timed-out, or
  equivalent terminal state
- **AND** an audit event MUST record the stale reason, runner ID, and lease
  timestamp.

### Requirement: Stale Target Lock Cleanup

The system MUST bind target write locks to TaskRun owners and clean up only
locks whose owners are stale.

#### Scenario: Target lock records its owner

- **WHEN** a write TaskRun acquires a target lock
- **THEN** the lock metadata MUST identify the `targetId`, owning `taskRunId`,
  session, lock mode, acquisition time, and lease expiration.

#### Scenario: Active lock is not released

- **WHEN** a target lock owner has a valid heartbeat and unexpired lease
- **THEN** stale lock cleanup MUST NOT release that lock
- **AND** downstream same-target write tasks MUST remain blocked by the lock.

#### Scenario: Stale owner lock is released

- **WHEN** a target lock owner is stale or timed out
- **THEN** cleanup MAY release the target lock
- **AND** cleanup MUST write an audit event identifying the lock, target ID,
  owner TaskRun, and cleanup reason.

### Requirement: Pre-run Snapshot And Checkpoint

The system MUST record a pre-run checkpoint before write tasks execute against
built-in or external targets.

#### Scenario: Write task checkpoint is created

- **WHEN** a write TaskRun is about to start
- **THEN** the system MUST record target ID, target root, allowed paths, denied
  paths, base commit, git status, dirty files, planned files, and checkpoint
  creation time.

#### Scenario: External target checkpoint is created

- **WHEN** a write TaskRun targets a registered external project
- **THEN** the checkpoint MUST use the external target root and path policy
  from the Target Registry
- **AND** the checkpoint MUST NOT expose denied path contents.

#### Scenario: Checkpoint metadata is visible for recovery

- **WHEN** a TaskRun has a pre-run checkpoint
- **THEN** retry and recovery APIs MUST be able to read checkpoint metadata
- **AND** the UI or API MUST expose enough metadata to explain retry safety.

### Requirement: Retry Idempotency

The system MUST make retry decisions based on previous run state, checkpoint
metadata, and current target cleanliness.

#### Scenario: Retry records previous run

- **WHEN** a user retries a failed or interrupted TaskRun
- **THEN** the retry TaskRun MUST record the previous run ID, failure summary,
  retry mode, and checkpoint reference when available.

#### Scenario: Unsafe retry is blocked

- **WHEN** the target worktree has dirty files outside the checkpoint or planned
  safe paths
- **THEN** automatic retry MUST be blocked
- **AND** the system MUST explain that an explicit recovery decision is
  required.

#### Scenario: Safe retry proceeds

- **WHEN** the target worktree matches the checkpoint safety conditions
- **AND** dependency and target lock rules allow execution
- **THEN** retry MAY create a new TaskRun through the existing TaskRun path
- **AND** retry history MUST remain traceable.

### Requirement: Failure Propagation Hardening

The system MUST prevent downstream execution, preview, and mock deploy after
failed prerequisites.

#### Scenario: Failed dependency blocks downstream

- **WHEN** an upstream dependency fails, is interrupted, times out, or is marked
  stale
- **THEN** downstream tasks MUST remain blocked
- **AND** their scheduler state MUST identify the failed prerequisite.

#### Scenario: Retry unblocks downstream after success

- **WHEN** a failed dependency is retried or recovered successfully
- **THEN** the scheduler MUST re-evaluate downstream tasks
- **AND** downstream tasks MAY become runnable only if dependencies, locks,
  approvals, and conflict checks pass.

#### Scenario: Preview and deploy are gated

- **WHEN** a coding prerequisite failed or is blocked
- **THEN** preview creation MUST NOT run automatically
- **AND** mock deploy MUST NOT run automatically.

### Requirement: Conflict Detection

The system MUST detect common write conflicts and stop rather than auto-merging
complex changes.

#### Scenario: File overlap conflict is detected

- **WHEN** two write tasks in the same session target overlapping planned files
- **AND** they could run concurrently or in unsafe order
- **THEN** the scheduler MUST identify a file overlap conflict
- **AND** at least one task MUST wait, block, or require explicit recovery.

#### Scenario: Dirty worktree conflict is detected

- **WHEN** a target worktree contains dirty files not covered by checkpoint,
  selected artifact, or planned safe paths
- **THEN** the scheduler MUST identify a dirty worktree conflict
- **AND** the system MUST NOT start an unsafe write TaskRun automatically.

#### Scenario: Contract drift conflict is detected

- **WHEN** a downstream task references an app contract version, hash, or ID
  that no longer matches the active contract
- **THEN** the scheduler MUST identify a contract drift conflict
- **AND** downstream implementation MUST NOT silently proceed against stale
  contract context.

#### Scenario: Complex conflict is not auto-merged

- **WHEN** conflict detection finds overlapping file changes, dirty worktree
  state, or contract drift
- **THEN** the system MUST NOT auto-merge the conflict in P10
- **AND** recovery options MUST be explicit and auditable.

### Requirement: Recovery Actions

The system MUST provide explicit auditable recovery actions for stale runs,
stale locks, retry decisions, and downstream pipeline control.

#### Scenario: Mark stale task failed

- **WHEN** a user or scheduler recovery action marks a stale TaskRun failed
- **THEN** the TaskRun MUST become terminal
- **AND** an audit event MUST record actor, reason, previous state, and new
  state.

#### Scenario: Release stale lock

- **WHEN** a recovery action releases a stale target lock
- **THEN** the lock MUST be released only if its owning TaskRun is stale or
  terminal
- **AND** an audit event MUST record the released lock and owner.

#### Scenario: Retry from current state

- **WHEN** a user chooses retry from current state
- **THEN** the system MUST check dirty worktree and conflict conditions
- **AND** the retry MUST be blocked or executed with a traceable recovery event.

#### Scenario: Retry from checkpoint

- **WHEN** a user chooses retry from checkpoint
- **THEN** the system MUST verify that checkpoint recovery is safe
- **AND** the system MUST NOT destructively reset files outside allowed target
  paths.

#### Scenario: Stop or resume downstream pipeline

- **WHEN** a user stops or resumes downstream pipeline progression
- **THEN** the scheduler MUST update downstream eligibility explicitly
- **AND** the action MUST produce an audit event.

### Requirement: P10 Baseline Preservation

The system MUST preserve P6/P7/P8/P9 behavior while adding scheduler
robustness and conflict recovery.

#### Scenario: P10 freeze review is performed

- **WHEN** P10 is reviewed for freeze
- **THEN** stale task, stale lock, failed dependency, retry, and conflict
  scenarios MUST be rehearsed
- **AND** P9 external project workspace mode MUST remain operational
- **AND** P8 dependency and target lock semantics MUST remain intact
- **AND** no unverified Claude/Codex success MUST be claimed.

#### Scenario: Out-of-scope capability is requested

- **WHEN** a request requires distributed workers, Docker sandbox, production
  deploy, provider marketplace, PR creation, automatic Git conflict merge,
  multi-user IM, or enterprise RBAC
- **THEN** P10 MUST reject or defer the request honestly
- **AND** it MUST NOT silently execute outside registered target boundaries.
