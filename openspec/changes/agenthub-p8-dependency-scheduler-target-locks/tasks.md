## 1. P8 Dependency Scheduler And Target Locks

- [x] 1.1 P8-1 Dependency-aware Task Scheduler.
  - Objective: Make declared task graph dependencies operational.
  - Scope:
    - add a scheduler boundary that evaluates task readiness from
      `dependsOnTaskIds`;
    - ensure downstream tasks wait until dependencies complete;
    - ensure failed, interrupted, or blocked dependencies block downstream
      tasks;
    - expose dependency wait / block reason through task, run, event, or
      scheduler metadata;
    - preserve existing manual TaskRun creation behavior for tasks outside the
      scheduler path.
  - Acceptance criteria:
    - incomplete dependencies prevent automatic TaskRun creation;
    - completed dependencies allow runnable tasks to proceed when no other
      rule blocks them;
    - failed dependencies block downstream tasks and identify the dependency;
    - dependency state is visible through an API payload or event stream.
  - Validation:
    - scheduler unit tests;
    - dependency readiness API tests;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict`.

- [ ] 1.2 P8-2 Target Write Locks.
  - Objective: Prevent same-target write conflicts during scheduled execution.
  - Scope:
    - derive task target IDs and read/write mode from P7 registry-aware plans;
    - add lock acquisition / release for write tasks;
    - serialize `demo-frontend` write tasks;
    - serialize `demo-backend` write tasks;
    - keep `agenthub-platform` write tasks platform-mode and approval-gated;
    - allow read-oriented review / QA tasks to avoid write locks when safe.
  - Acceptance criteria:
    - two `demo-frontend` write tasks cannot run concurrently;
    - two `demo-backend` write tasks cannot run concurrently;
    - waiting tasks report `waiting_target_lock` with the target ID;
    - review / QA tasks do not acquire write locks unless explicitly configured
      as write tasks;
    - ordinary backend tasks cannot lock or write `agenthub-platform`.
  - Validation:
    - target lock unit tests;
    - scheduler concurrency tests;
    - platform target protection tests;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict`.

- [ ] 1.3 P8-3 Auto-run Pipeline.
  - Objective: Automatically progress bounded full-stack app pipelines through
    existing execution and artifact paths.
  - Scope:
    - add scheduler progression for:
      Contract -> Backend -> Frontend -> Review/QA -> Preview -> Mock Deploy;
    - use existing TaskRun creation, adapter execution, diff collection,
      review artifact, preview, and mock deploy code paths;
    - preserve P6/P7 mini CRM behavior and target IDs;
    - keep mock deploy clearly mock-labeled;
    - avoid repeated real Claude/Codex mutations unless a bounded smoke
      explicitly requires it.
  - Acceptance criteria:
    - mini CRM pipeline can progress automatically in dependency order;
    - backend execution targets `demo-backend`;
    - frontend execution targets `demo-frontend`;
    - review starts only after required diffs exist;
    - preview and mock deploy still use existing APIs and artifacts.
  - Validation:
    - pipeline progression tests;
    - mini CRM scheduler API smoke with mocked or scripted execution where
      sufficient;
    - `pnpm check`;
    - `pnpm test`;
    - `pnpm demo:api:test`;
    - `git diff --check`;
    - `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict`.

- [ ] 1.4 P8-4 Failure Recovery And Blocked States.
  - Objective: Make scheduler failure propagation, retry, and fallback states
    explicit.
  - Scope:
    - introduce or formalize scheduler-visible states:
      `waiting_dependency`, `waiting_target_lock`, `running`, `completed`,
      `failed`, `blocked`, `retryable`, and `fallback_available`;
    - prevent downstream tasks from silently continuing after upstream failure;
    - keep retry and fallback traceable through TaskRun history;
    - keep real Claude/Codex success claims evidence-based;
    - ensure scheduler re-evaluates downstream tasks after retry or fallback
      completion.
  - Acceptance criteria:
    - failed upstream tasks block downstream tasks;
    - retryable and fallback-available states are visible;
    - fallback creates traceable run history;
    - completed retry/fallback can unblock downstream tasks when dependency and
      lock rules are satisfied;
    - no downstream task claims success after upstream failure.
  - Validation:
    - blocked-state tests;
    - retry/fallback scheduler tests;
    - event/history regression tests;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict`.

- [ ] 1.5 P8-5 Scheduler UI Trace.
  - Objective: Make scheduler decisions visible in the current workspace UI.
  - Scope:
    - surface scheduler states in existing task cards, timeline, or execution
      trace;
    - show dependency wait, target lock wait, running, blocked, failed,
      retryable, fallback available, and completed states;
    - show target IDs and dependency IDs where useful;
    - preserve existing artifact panel and artifact message cards;
    - avoid broad UI redesign.
  - Acceptance criteria:
    - a user can tell why a task is not running;
    - blocked tasks identify upstream failure when available;
    - lock-waiting tasks identify the target lock;
    - existing Start, Retry, Fallback, Review, Preview, Deploy, artifact cards,
      and artifact panel behavior remain available.
  - Validation:
    - frontend component tests;
    - API fixture tests where needed;
    - browser/manual UI smoke if practical;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict`.

- [ ] 1.6 P8-6 P8 E2E Rehearsal And Freeze Review.
  - Objective: Verify that P8 adds scheduler behavior without regressing
    P6/P7.
  - Scope:
    - verify the mini CRM task graph executes in correct order;
    - verify target locks protect `demo-frontend` and `demo-backend`;
    - verify failed dependencies block downstream tasks;
    - verify review, preview, and mock deploy still work;
    - verify ordinary backend tasks remain isolated from `apps/api`;
    - verify platform tasks remain explicit and approval-gated;
    - document evidence IDs, adapter usage, fallback usage, caveats, and final
      freeze recommendation.
  - Acceptance criteria:
    - P8 mini CRM rehearsal produces contract, backend, frontend, review,
      preview, and mock deploy evidence;
    - scheduler order and lock evidence are recorded;
    - failure blocking evidence is recorded;
    - P6/P7 baselines remain intact;
    - no unverified real Claude/Codex success is claimed.
  - Validation:
    - targeted API/browser rehearsal as practical;
    - `pnpm check`;
    - `pnpm test`;
    - `pnpm demo:api:test`;
    - `git diff --check`;
    - `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict`.

## 2. Explicit Non-Goals For P8

- Distributed worker cluster.
- Multi-user IM.
- Matrix, Feishu, WeChat, Slack, or other external IM integration.
- Production deploy.
- Docker sandbox.
- Provider marketplace.
- PR creation.
- Arbitrary SaaS generation.
- Full external repo import.
- Desktop/mobile clients.
- Document/PPT artifact editor.

## 3. P8 Definition Of Done

- Task dependencies drive scheduler execution order.
- Same-target write tasks are serialized by target locks.
- The bounded mini CRM pipeline can progress automatically through existing
  TaskRun, diff, review, preview, and mock deploy paths.
- Failed dependencies block downstream tasks.
- Retry and fallback remain explicit and traceable.
- Scheduler state is visible in the UI.
- P7 Target Registry remains the source of truth for target IDs and target
  protections.
- Ordinary backend tasks cannot modify `apps/api`.
- Mock deploy remains mock-labeled.
- Real Claude/Codex success is documented only when actually run.
- P4/P5/P6/P7 baselines remain intact.
