## Why

P6 proved a bounded full-stack mini CRM vertical slice, and P7 made execution
target-aware, but AgentHub still does not have a mature scheduler for
dependency order, target write locks, automatic pipeline progression, or
downstream blocked states. P8 is needed so the Manager / PMO Agent can safely
coordinate multi-agent execution instead of merely creating a task graph.

## What Changes

- Add a dependency-aware scheduler that evaluates `dependsOn` before starting
  task runs.
- Add target write locks so same-target write tasks do not run concurrently.
- Add automatic pipeline progression for bounded full-stack app flows:
  Contract -> Backend -> Frontend -> Review/QA -> Preview -> Mock Deploy.
- Add blocked and waiting states for dependency waits, target lock waits,
  upstream failures, retry availability, and fallback availability.
- Surface scheduler state in the existing task timeline / execution trace UI.
- Rehearse P8 against the P6/P7 mini CRM path and verify target locks,
  blocked downstream behavior, preview, and mock deploy.

P8 preserves the P6 full-stack mini CRM capability and the P7 Target Registry.
It does not add distributed workers, multi-user IM, external IM integration,
production deploy, Docker sandboxing, provider marketplace, PR creation, or
arbitrary SaaS generation.

## Capabilities

### New Capabilities

- `scheduler`: Dependency-aware task scheduling, target write locks,
  automatic bounded pipeline progression, blocked/fallback state handling, and
  scheduler UI trace.

### Modified Capabilities

None. P8 introduces a scheduler capability while preserving the P4/P5/P6/P7
baseline.

## Impact

OpenSpec artifacts:

- `openspec/changes/agenthub-p8-dependency-scheduler-target-locks/proposal.md`
- `openspec/changes/agenthub-p8-dependency-scheduler-target-locks/design.md`
- `openspec/changes/agenthub-p8-dependency-scheduler-target-locks/tasks.md`
- `openspec/changes/agenthub-p8-dependency-scheduler-target-locks/specs/scheduler/spec.md`

Expected implementation impact when P8 is later applied:

- Backend:
  - scheduler service or module;
  - dependency readiness evaluation for task graphs;
  - target lock acquisition / release using P7 target IDs;
  - scheduler events in existing `TaskRunEvent` / task state surfaces;
  - automatic progression to review, preview, and mock deploy using existing
    APIs;
  - blocked/failure propagation for downstream tasks.
- Frontend:
  - scheduler state in task cards, timeline, and execution trace;
  - clear labels for dependency wait, target lock wait, blocked, retryable,
    fallback available, running, and completed states.
- Data model:
  - P8 can start with existing `Task`, `TaskRun`, and `TaskRunEvent` fields
    plus plan/context metadata if enough;
  - persistence additions are allowed only when needed for durable scheduler
    state or locks.
- Runtime:
  - same-session write tasks remain serial per target lock;
  - ordinary backend tasks remain bounded to `demo-backend`;
  - `agenthub-platform` execution remains approval-gated;
  - mock deploy remains clearly mock-labeled.
