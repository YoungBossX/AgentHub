## Context

P7 is frozen at the local single-user AgentHub workspace baseline. AgentHub now
has a Target Project Registry with `demo-frontend`, `demo-backend`, and
`agenthub-platform`, and it can generate target-aware mini CRM contracts and
task plans. However, task execution is still mostly run-start driven: a task can
be created and a TaskRun can be started, but AgentHub does not yet consistently
own dependency order, target write locks, automatic progression, or downstream
blocked states.

P8 turns the Manager / Orchestrator from a planner that creates a graph into a
PMO-style coordinator that can safely run the graph.

## Goals / Non-Goals

**Goals:**

- Execute task graphs according to declared dependencies.
- Block downstream tasks when upstream dependencies fail.
- Serialize write tasks per target ID using P7 Target Registry metadata.
- Allow read-oriented review / QA tasks to run only when dependency and safety
  rules allow.
- Automatically progress bounded full-stack app pipelines using existing
  TaskRun, diff, review, preview, and mock deploy paths.
- Make scheduler state visible in the UI.
- Preserve P6/P7 mini CRM and platform protection behavior.

**Non-Goals:**

- Distributed worker cluster.
- Multi-user IM or real-time multi-user conflict resolution.
- Matrix, Feishu, WeChat, Slack, or other external IM integration.
- Production deployment or real deploy providers.
- Docker sandboxing.
- Provider marketplace.
- PR creation.
- Arbitrary SaaS generation.
- Full external repo import.
- Desktop/mobile clients.
- Document/PPT artifact editor.

## Scheduler Model

P8 should introduce a scheduler boundary that can be invoked after task graph
creation, after TaskRun state changes, and after user retry/fallback actions.
The first implementation can run inside the existing FastAPI process and use
existing background task behavior; it does not need a distributed queue.

Suggested scheduler inputs:

```text
sessionId
task graph / tasks
task dependencies
task targetId
task write/read mode
task status and latest TaskRun status
target lock state
approval state
fallback eligibility
```

Suggested scheduler outputs:

```text
task scheduler state
TaskRun creation when runnable
blocked state when dependencies fail
waiting_dependency state
waiting_target_lock state
scheduler events
pipeline continuation actions
```

The scheduler should remain conservative: if it cannot prove a task is runnable,
it must leave the task waiting or blocked rather than silently starting it.

## Dependency Semantics

Tasks already store `dependsOnTaskIds`. P8 should make that dependency list
operational:

- a task with incomplete dependencies enters `waiting_dependency`;
- a task with failed/interrupted/blocked dependencies enters `blocked`;
- a task becomes runnable only when all dependencies are completed and all
  approvals/locks are satisfied;
- downstream tasks must not start after upstream failure unless a user retries
  or creates an explicit fallback path.

For P6/P7 mini CRM, the graph remains:

```text
Contract -> Backend -> Frontend -> Review/QA -> Preview -> Mock Deploy
```

P8 may keep Backend -> Frontend serial for the first scheduler version even
though different targets could theoretically run in parallel. The important
behavior is that declared dependencies are respected and same-target writes are
not concurrent.

## Target Write Locks

P8 should use P7 target IDs as lock keys. Initial lock keys:

- `demo-frontend`;
- `demo-backend`;
- `agenthub-platform`.

Write tasks:

- frontend coding tasks for `demo-frontend`;
- backend coding tasks for `demo-backend`;
- platform maintenance tasks for `agenthub-platform`.

Read-oriented tasks:

- review / QA tasks;
- artifact inspection;
- preview and mock deploy actions when they do not mutate the target source.

Lock rules:

- only one same-target write task may run at a time;
- `demo-frontend` writes are serial;
- `demo-backend` writes are serial;
- `agenthub-platform` writes require explicit platform mode and approval;
- different-target writes may run concurrently only when dependency rules allow
  and the implementation can keep worktree conflict risk bounded;
- review / QA tasks may run without a write lock if dependencies are complete
  and review is read-oriented.

The first implementation can store locks in the database or derive active locks
from active TaskRuns. Durable DB locks are safer if scheduler decisions can span
requests, retries, or process restarts.

## Auto-run Pipeline

P8 should add a scheduler-driven auto-run path for bounded full-stack app
contracts. It should reuse existing artifact paths instead of introducing new
execution engines:

1. Contract task completes or is treated as a planning artifact.
2. Backend task starts when dependencies and `demo-backend` lock allow it.
3. Backend diff is collected through the existing diff path.
4. Frontend task starts when backend dependency completes and
   `demo-frontend` lock allows it.
5. Frontend diff is collected through the existing diff path.
6. Review / QA runs through the existing review artifact path.
7. Preview starts through the existing preview path.
8. Mock deploy is created through the existing mock deploy path and remains
   mock-labeled.

The scheduler must not claim real Claude/Codex success unless adapter evidence
exists. If a real adapter fails, fallback availability should be visible but
fallback execution remains explicit unless the active policy already allows it.

## Scheduler States

P8 should formalize scheduler-visible states without erasing existing
`Task.status` and `TaskRun.state` behavior.

Suggested states:

- `waiting_dependency`;
- `waiting_target_lock`;
- `running`;
- `completed`;
- `failed`;
- `blocked`;
- `retryable`;
- `fallback_available`;

These may be represented as task status values, scheduler metadata in
`plan_json`, `TaskRunEvent` payloads, or a small scheduler state table. The
implementation should choose the smallest durable option that gives API and UI
enough information.

## UI Trace

P8 is not a broad redesign. It should extend existing task cards, execution
trace, and artifact message card surfaces with scheduler state:

- dependency waiting;
- target lock waiting;
- running;
- blocked;
- failed;
- retryable;
- fallback available;
- completed.

The UI should help a user understand why work is not running yet, which target
is locked, which dependency failed, and what action is available next.

## Failure Recovery

Downstream failure behavior must be explicit:

- failed dependency blocks downstream tasks;
- interrupted dependency blocks downstream tasks until retry/fallback resolves
  it;
- retry creates traceable new TaskRun history;
- fallback availability is visible and traceable;
- no downstream task silently continues after upstream failure;
- no UI state claims success when the adapter did not succeed.

## Risks / Trade-offs

- **Risk: Scheduler becomes a hidden distributed systems project.** Mitigation:
  keep P8 local-process and SQLite-compatible, using existing TaskRun and event
  flows.
- **Risk: Locks over-constrain useful parallelism.** Mitigation: start
  conservative. Different-target concurrency can be enabled only when dependency
  rules and worktree conflict rules are clear.
- **Risk: UI becomes noisy.** Mitigation: show scheduler state in existing
  task/trace surfaces instead of creating a new dashboard.
- **Risk: Auto-run repeats costly real adapter calls.** Mitigation: P8 rehearsal
  can use existing evidence or ScriptedMock for scheduler plumbing unless a
  bounded real smoke is explicitly needed.
- **Risk: Platform maintenance bypasses P7 protections.** Mitigation:
  `agenthub-platform` remains platform-mode and approval-gated.

## Migration Plan

1. Add scheduler readiness evaluation for dependencies.
2. Add target lock calculation and lock-aware runnable decisions.
3. Add scheduler-driven auto-run progression for bounded app pipelines.
4. Add failure propagation and blocked/retry/fallback states.
5. Add UI scheduler trace state.
6. Rehearse mini CRM and target-lock/failure cases before freezing P8.

Rollback strategy: scheduler auto-run can be disabled while preserving the P7
manual TaskRun path, target registry, and review behavior.
