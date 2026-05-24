## ADDED Requirements

### Requirement: Dependency-aware Task Scheduling

The system MUST schedule task execution according to declared task
dependencies.

#### Scenario: Task waits for incomplete dependencies

- **WHEN** a task has one or more `dependsOnTaskIds`
- **AND** at least one dependency is not completed
- **THEN** the scheduler MUST NOT start a TaskRun for that task
- **AND** the task MUST expose a scheduler state equivalent to
  `waiting_dependency`.

#### Scenario: Task becomes runnable after dependencies complete

- **WHEN** all dependencies for a task are completed
- **AND** no target lock or approval rule blocks the task
- **THEN** the scheduler MAY create a TaskRun through the existing TaskRun
  path
- **AND** the task MUST expose a scheduler state equivalent to `running` once
  execution starts.

#### Scenario: Failed dependency blocks downstream task

- **WHEN** a dependency task fails, is interrupted, or is blocked
- **THEN** downstream tasks that depend on it MUST NOT start automatically
- **AND** downstream tasks MUST expose a scheduler state equivalent to
  `blocked`
- **AND** the block reason MUST identify the failed dependency.

### Requirement: Target Write Locks

The system MUST prevent concurrent same-target write tasks by using target
metadata from the P7 Target Project Registry.

#### Scenario: Same frontend target write is already running

- **WHEN** a write task targeting `demo-frontend` is active
- **AND** another write task targeting `demo-frontend` becomes otherwise
  runnable
- **THEN** the scheduler MUST NOT start the second write task
- **AND** the second task MUST expose a scheduler state equivalent to
  `waiting_target_lock`
- **AND** the lock reason MUST identify `demo-frontend`.

#### Scenario: Same backend target write is already running

- **WHEN** a write task targeting `demo-backend` is active
- **AND** another write task targeting `demo-backend` becomes otherwise
  runnable
- **THEN** the scheduler MUST NOT start the second write task
- **AND** the second task MUST expose a scheduler state equivalent to
  `waiting_target_lock`
- **AND** the lock reason MUST identify `demo-backend`.

#### Scenario: Platform target write is requested

- **WHEN** a write task targets `agenthub-platform`
- **THEN** the task MUST require explicit platform mode
- **AND** the task MUST require approval before adapter execution
- **AND** ordinary app backend tasks MUST NOT acquire an `agenthub-platform`
  write lock.

#### Scenario: Read-only review is evaluated

- **WHEN** a review or QA task is read-oriented
- **AND** its dependencies are completed
- **THEN** the scheduler MUST NOT require a write lock for that task
- **AND** the scheduler MUST still respect dependency and approval rules.

### Requirement: Automatic Bounded Pipeline Progression

The system MUST automatically progress bounded full-stack app pipelines when
dependencies, target locks, and approvals allow it.

#### Scenario: Mini CRM pipeline progresses

- **WHEN** Orchestrator creates a supported mini CRM app contract task graph
- **THEN** the scheduler MUST progress the pipeline in dependency order:
  Contract, Backend, Frontend, Review/QA, Preview, Mock Deploy
- **AND** Backend Agent execution MUST target `demo-backend`
- **AND** Frontend Agent execution MUST target `demo-frontend`
- **AND** Review / QA MUST run after the required coding diffs exist
- **AND** Preview MUST use the existing preview path
- **AND** deployment MUST remain mock-labeled.

#### Scenario: Pipeline step is not runnable

- **WHEN** a pipeline step has an incomplete dependency, blocked dependency,
  unavailable approval, or target lock conflict
- **THEN** the scheduler MUST stop progression at that step
- **AND** downstream steps MUST NOT silently continue.

### Requirement: Failure Recovery And Blocked States

The system MUST make scheduler failure, retry, and fallback status explicit and
traceable.

#### Scenario: Adapter run fails

- **WHEN** a TaskRun fails during adapter execution
- **THEN** the owning task MUST expose a scheduler state equivalent to `failed`
  or `retryable`
- **AND** downstream dependent tasks MUST expose `blocked`
- **AND** the scheduler MUST NOT claim Claude/Codex success.

#### Scenario: Fallback is available

- **WHEN** a failed coding TaskRun can use `ScriptedMockAdapter` fallback under
  the existing fallback policy
- **THEN** the task MUST expose a scheduler state equivalent to
  `fallback_available`
- **AND** fallback execution MUST remain traceable through a new TaskRun or
  equivalent run history.

#### Scenario: User retries a failed dependency

- **WHEN** the user retries or falls back a failed dependency
- **AND** the retried or fallback run completes
- **THEN** the scheduler MUST re-evaluate downstream blocked tasks
- **AND** downstream tasks MAY become runnable if dependency and lock rules are
  satisfied.

### Requirement: Scheduler UI Trace

The system MUST surface scheduler state in existing task timeline or execution
trace UI surfaces.

#### Scenario: Task is waiting on dependency

- **WHEN** a task is waiting for dependencies
- **THEN** the UI MUST show a waiting dependency state
- **AND** the UI MUST identify the dependency when available.

#### Scenario: Task is waiting on target lock

- **WHEN** a task is waiting for a target write lock
- **THEN** the UI MUST show a waiting target lock state
- **AND** the UI MUST identify the locked target ID.

#### Scenario: Downstream task is blocked

- **WHEN** a downstream task is blocked by upstream failure
- **THEN** the UI MUST show a blocked state
- **AND** the UI MUST preserve retry and fallback actions where existing APIs
  support them.

#### Scenario: Scheduler trace coexists with artifacts

- **WHEN** scheduler states are shown in the UI
- **THEN** existing artifact panel behavior MUST remain available
- **AND** Diff, Review, Preview, and Mock Deploy artifact cards MUST remain
  usable.

### Requirement: P8 Baseline Preservation

The system MUST preserve P6/P7 local workspace behavior while adding
dependency-aware scheduling and target locks.

#### Scenario: P8 freeze review is performed

- **WHEN** P8 is reviewed for freeze
- **THEN** the mini CRM path MUST still produce contract, backend task,
  frontend task, review, preview, and mock deploy evidence
- **AND** target locks MUST protect `demo-frontend` and `demo-backend`
- **AND** failed dependencies MUST block downstream tasks
- **AND** ordinary backend tasks MUST NOT modify `apps/api`
- **AND** `agenthub-platform` execution MUST remain explicit platform mode and
  approval-gated
- **AND** P8 MUST NOT claim distributed workers, multi-user IM, production
  deployment, Docker sandboxing, PR creation, provider marketplace, or
  arbitrary SaaS generation.
