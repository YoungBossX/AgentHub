# AgentHub Project State

This document captures stable project state that future Codex prompts can
reference instead of repeating long context blocks.

## P11 Status

### P11-4 Deploy Logs And Status Artifact

P11-4 completed on 2026-05-25.

Deployment artifacts now expose provider evidence more directly. Deployment
metadata records provider type, target ID, source preview/diff/review
references, provider logs, and status history. The deploy API response includes
these fields so UI clients do not need to parse raw artifact metadata.

The existing deploy card now renders target/source references, status history,
and logs while preserving mock deploy behavior. Local staging failures such as
build failure, missing output directory, or failed health check are persisted as
failed deployment artifacts with logs instead of being silently lost.

Current limitation: P11-4 records status history as provider-produced metadata
and deploy events. It does not yet enforce review/preview/policy deploy gates;
that remains P11-5.

### P11-3 Local Staging Deploy Provider

P11-3 completed on 2026-05-25.

AgentHub now includes a `local_staging` deploy provider alongside the existing
mock provider. The local staging provider resolves target deploy configuration
from Target Registry, runs the configured build command in the target root,
verifies the configured output directory, starts a local static file server,
health-checks the generated URL, and persists a ready staging deployment
artifact when the provider succeeds.

The deploy API remains backward-compatible: `POST /previews/{previewId}/deploy`
defaults to `providerId: mock`, while callers can request
`providerId: local_staging`. Failed build, missing output directory, and failed
health check states are reported honestly and do not create a ready deployment.

Current limitation: P11-3 stores provider logs inside artifact metadata and
ready events, but does not yet persist full deploy status transition history or
UI log expansion. That is P11-4. Deploy gates beyond preview/task prerequisites
remain P11-5.

### P11-2 Target-aware Deploy Configuration

P11-2 completed on 2026-05-25.

Target Registry now exposes staging deploy metadata for deployable frontend
targets. The built-in `demo-frontend` target includes a build command, staging
output directory, staging serve command template, and allowed deploy provider
IDs. External project registration and workspace target responses can also
carry `stagingOutputDir`, `stagingServeCommand`, and `deployProviderIds`.

`resolve_deploy_config()` centralizes deploy configuration lookup and fails
honestly when a target is not a deployable frontend target or lacks the required
build/output/provider metadata. `demo-backend` and `agenthub-platform` remain
non-deployable through this staging config path.

Current limitation: P11-2 only provides target-aware deploy configuration. It
does not yet run a build, serve static output, record expanded deploy logs, or
enforce deploy gates.

### P11-1 Deploy Provider Abstraction

P11-1 completed on 2026-05-25.

AgentHub now has a narrow deploy provider abstraction for the existing deploy
path. `DeployService.create_deployment()` selects a provider by ID, rejects
unknown providers honestly, rejects failed provider results without creating a
successful deployment artifact, and keeps `create_mock_deployment()` as a
backward-compatible wrapper around the provider-compatible mock path.

The mock provider still produces the existing mock deployment URL and artifact
shape, while deployment artifact metadata now includes a standard
`providerResult` payload with provider ID, provider type, target ID, build
command, deploy command, output URL, status, logs, and environment.

Current limitation: P11-1 only introduces the provider abstraction and mock
compatibility. Target-aware staging config, local static serving, deploy logs
UI/status expansion, deploy gates, and real staging rehearsal remain later P11
tasks.

## P10 Status

### P10-8 Robustness Rehearsal And Freeze Review

P10-8 completed on 2026-05-24.

Result: P10 is ready to freeze as Scheduler Robustness and Conflict Recovery.

The freeze review used deterministic local tests and did not run a fresh real
Claude/Codex mutation. Covered rehearsal scenarios include:

- TaskRun heartbeat and lease;
- stale TaskRun detection;
- active-lock preservation;
- stale target lock cleanup;
- pre-run checkpoint;
- retry idempotency and unsafe retry blocking;
- failed dependency propagation;
- preview/mock deploy prerequisite gating;
- file overlap, dirty worktree, and contract drift conflicts;
- auditable recovery actions.

See `docs/p10-freeze-review.md` for the evidence table, caveats, and validation
record.

Recommended freeze tag:
`p10-scheduler-robustness-conflict-recovery-freeze`.

### P10-7 Recovery Actions

P10-7 completed on 2026-05-24.

AgentHub now has a focused recovery service for scheduler robustness scenarios:

- mark a stale TaskRun failed with a recovery audit event;
- release a stale target lock and re-evaluate waiting tasks;
- retry from current state with retry metadata and audit event;
- retry from checkpoint after the same safety checks used by retry;
- stop downstream pipeline progression with explicit blocked scheduler state;
- resume downstream progression by re-evaluating dependency and scheduler
  readiness.

Each recovery action writes a `recovery.action` `TaskRunEvent` with actor,
reason, action, and affected IDs. Stale lock release also preserves the
`target_lock.released` audit event from P10-2.

Current limitation: P10-7 exposes service-level recovery actions for API/test
rehearsal. It does not add new UI buttons or automatic Git reset/merge
behavior.

### P10-6 Conflict Detection

P10-6 completed on 2026-05-24.

Scheduler readiness now performs conservative conflict detection before
starting write TaskRuns:

- unsequenced write tasks with overlapping planned files are blocked as
  `file_overlap`;
- external or registered target dirty worktrees with dirty files outside the
  planned safe files are blocked as `dirty_worktree`;
- tasks whose `contractId` or `contractHash` no longer matches the embedded
  `appContract` are blocked as `contract_drift`;
- conflict details are written into the task scheduler metadata, including
  conflict type, conflicting tasks, and conflicting files where available.

P10-6 does not auto-merge conflicts. It stops before unsafe execution and
leaves recovery decisions to explicit P10-7 actions.

Current limitation: file-overlap detection is intentionally bounded to
unsequenced write tasks so existing dependency-ordered P8/P9 pipelines keep
working.

### P10-5 Failure Propagation Hardening

P10-5 completed on 2026-05-24.

Preview and mock deploy creation are now gated by successful prerequisites:

- preview requires the source TaskRun to be completed;
- preview rejects failed, interrupted, stale, timed-out, or still-running
  TaskRuns;
- preview rejects tasks whose dependencies are missing or not completed;
- mock deploy requires a healthy preview backed by a completed TaskRun;
- mock deploy rejects failed or incomplete upstream dependencies.

Existing scheduler dependency blocking, retry/fallback downstream
re-evaluation, and the fallback diff -> preview -> mock deploy path remain
intact.

Current limitation: P10-5 hardens downstream gating but does not yet perform
file-overlap, dirty-worktree, or contract-drift conflict detection. Those
remain P10-6.

### P10-4 Retry Idempotency

P10-4 completed on 2026-05-24.

Retry TaskRuns now carry idempotency metadata:

- `previousRunId` links the retry to the prior failed/interrupted run;
- `failureSummary` records prior state, error code/message, and end time;
- `retryMode` records whether retry is from current state or scripted fallback;
- `checkpointId` points to the prior TaskRun when a pre-run checkpoint exists;
- `dirtyWorktreeDecision` records whether the current target state is safe.

Automatic retry checks the current git dirty files against the previous
checkpoint dirty files and planned files. If dirty files exist outside the
checkpoint/planned safe paths, retry is blocked with an explicit unsafe retry
error and no new TaskRun is created.

Current limitation: P10-4 blocks unsafe retry but does not yet provide a
separate recovery decision API. Retry-from-checkpoint and explicit recovery
actions remain P10-7.

### P10-3 Pre-run Snapshot / Checkpoint

P10-3 completed on 2026-05-24.

Write TaskRuns now record a pre-run checkpoint in
`metrics_json.preRunCheckpoint` and emit a `task.checkpoint.created` event.
The checkpoint records:

- target ID and target root;
- Target Registry allowed and denied paths;
- base commit when available;
- git status availability and scoped dirty files;
- planned files from the task plan;
- app contract ID and deterministic contract hash when present;
- checkpoint creation timestamp.

External target checkpoints use the registered external target root and path
policy. Checkpoint metadata records file paths and git status only; it does not
store file contents or denied-path contents.

Current limitation: P10-3 records checkpoint metadata only. Retry idempotency,
dirty worktree retry blocking, conflict detection, and recovery actions consume
this metadata in P10-4 through P10-7.

### P10-2 Stale Target Lock Cleanup

P10-2 completed on 2026-05-24.

Target write locks remain derived from active TaskRuns, but cleanup is now
owner-aware and auditable:

- active write-lock owners with valid heartbeat leases are not released;
- expired write-lock owners can be marked stale through the cleanup path;
- stale owner cleanup writes `target_lock.released` audit events that identify
  target ID, owning TaskRun, task, session, lock mode, lease expiry, release
  timestamp, and release reason;
- waiting same-target write tasks are re-evaluated after stale owner cleanup.

Current limitation: P10-2 still uses derived lock ownership instead of a
dedicated lock table. Pre-run checkpoints, retry idempotency, conflict
detection, and recovery action APIs remain P10-3 through P10-7.

### P10-1 TaskRun Heartbeat And Lease

P10-1 completed on 2026-05-24.

TaskRun execution now records local runner liveness metadata:

- `runner_id` identifies the local runner owner for a TaskRun;
- `last_heartbeat_at` records the most recent active-run heartbeat;
- `lease_expires_at` records when the current heartbeat lease expires;
- `stale_detected_at` and `stale_reason` record honest stale detection.

New TaskRuns receive heartbeat and lease metadata when created. Active
TaskRuns can refresh their heartbeat through the TaskRun lifecycle service, and
expired active leases can be marked failed with `TASK_RUN_STALE` without
claiming adapter success. Stale transitions write `task.state` and
`task.stale` audit events and refresh downstream scheduler state.

Current limitation: P10-1 introduces liveness metadata and stale marking, but
does not yet clean stale target locks, create checkpoints, harden retry
idempotency, detect conflicts, or expose recovery actions. Those remain P10-2
through P10-7.

## P9 Status

### P9-8 External Project E2E Rehearsal And Freeze Review

P9-8 completed on 2026-05-24.

Result: P9 is ready to freeze as External Project Workspace Mode.

The freeze rehearsal used a temporary local Vite-style external project and
controlled local service calls, not a fresh real Claude/Codex mutation.

P9 rehearsal evidence:

- sample root: `/tmp/agenthub-p9-external-sample`;
- workspace ID: `deecb61e-8255-4f97-af36-668f8fefc66d`;
- session ID: `09977dc0-1eac-49f6-ae78-cb7ae7aa9ccc`;
- target ID: `external-p9-sample`;
- analysis status / type: `ready`, `vite-react`;
- task / run:
  `ce8fe3de-6969-4273-84e9-274ab440f39b`,
  `1d6d2916-b179-4bb7-ad7a-642733dfd175`;
- changed file: `src/App.tsx`;
- diff artifact: `7bf6efa3-289b-4cb8-9644-6ca6e283b230`;
- command evidence:
  `c6d581bf-e80a-4fb9-bb21-f0db1cb9ff4d`,
  `b01ccc78-b3d4-44fc-b758-4c9558d2f594`,
  `9a256f14-fe1f-4e4b-9dc7-78c4402edd01`;
- review artifact/status/risk:
  `383e7822-0145-4950-9bd1-b3dffb170b36`, `passed`, `low`.

See `docs/p9-freeze-review.md` for the full evidence record and caveats.

Recommended freeze tag:
`p9-external-project-workspace-mode-freeze`.

### P9-7 External Project Review

P9-7 completed on 2026-05-24.

Scripted review now checks registered external target policy and command
evidence:

- external diffs are reviewed against target allowed paths and denied paths;
- denied path edits such as `.env` fail review with high risk;
- edits outside registered allowed paths produce warning findings;
- configured check/test/build commands are expected to have command evidence;
- failed command evidence is reported honestly and keeps review at warning or
  failed status as appropriate;
- clean external diffs with passing configured evidence can pass review.

Current limitation: P9-7 is deterministic scripted review policy. It does not
run a real Claude/Codex review; that remains optional evidence for P9-8.

### P9-6 External Evidence Pipeline

P9-6 completed on 2026-05-24.

External project TaskRuns now have a capability-based evidence path:

- external git diffs use target registry allowed paths and denied paths when
  collecting changed files and patch text;
- command evidence artifacts can record configured check, test, and build
  command output;
- command evidence preserves exit code and records failed commands as
  `failed` instead of converting them into success;
- command evidence is emitted as `command_evidence` artifacts with TaskRun
  events and list/read API support;
- session context packs include latest command evidence metadata for later
  review and instruction use;
- targets without preview command can still carry diff and command evidence.

Current limitation: P9-6 records command evidence supplied by the controlled
pipeline/API; it does not yet execute arbitrary external commands. Review
policy over command evidence is P9-7.

### P9-5 External Project Task Execution

P9-5 completed on 2026-05-24.

Registered external targets can now receive executable tasks through existing
routing and TaskRun paths:

- sessions can select active external frontend/backend target IDs;
- target selection validates that the target exists in the workspace registry
  and matches the requested frontend/backend type;
- direct `@frontend` and `@backend` assignments route to the selected external
  target when present;
- direct `@qa` / `@review` assignments become read-oriented external review
  tasks when an external target is active;
- Orchestrator can create and auto-start a bounded external frontend task when
  an active external frontend target is selected and the request is a safe UI
  change;
- external TaskRuns use the external target root as their execution worktree
  path instead of the built-in session demo worktree;
- SQLite initialization now backfills the session active-target columns for
  existing local demo databases.

Current limitation: external diff/command evidence is still basic and
capability-specific evidence artifacts are P9-6. Real Claude/Codex external
execution is reserved for P9-8 rehearsal.

### P9-4 External Target Instruction Builder

P9-4 completed on 2026-05-24.

Role instructions now use registered external target metadata instead of
assuming built-in demo paths:

- external frontend instructions include target root, allowed paths, denied
  paths, project type, detected framework, package manager, and configured
  validation/evidence commands;
- external backend instructions use external backend metadata and explicitly
  preserve the `apps/api` AgentHub platform boundary;
- external QA/review instructions are read-oriented and require honest handling
  of diff and check/test/build evidence;
- built-in demo frontend/backend/review instructions remain compatible with
  P4/P5/P6/P7/P8 paths.

Current limitation: instructions are external-target aware, but routing and
TaskRun execution against selected external targets are still P9-5.

### P9-3 External Target Registry Integration

P9-3 completed on 2026-05-24.

External project targets are now adapted into the same Target Registry shape as
built-in targets:

- workspace-aware registry reads merge `demo-frontend`, `demo-backend`,
  `agenthub-platform`, and persisted external targets;
- external registrations map into `TargetProject` metadata, including root,
  allowed paths, denied paths, commands, package manager, detected framework,
  project type, and analysis status;
- backend APIs expose merged workspace targets through
  `/workspaces/{workspace_id}/targets`;
- session context packs can resolve external `targetId` values and pass target
  metadata into agent instructions;
- instruction building can render external target metadata without falling back
  to demo target IDs;
- P8 target write locks now recognize registered external targets, so
  same-session same-external-target write tasks are serialized.

Current limitation: Orchestrator does not yet select external targets for user
requests, and adapters do not yet execute inside external roots. Those remain
P9-4 and P9-5.

### P9-2 Project Analyzer

P9-2 completed on 2026-05-24.

AgentHub now has a read-only external project analyzer for local registered
workspace candidates:

- detects representative Vite React, Next.js, FastAPI, Node API, and Python
  package projects from project files without installing dependencies or
  running commands;
- infers package manager from lockfiles and project markers;
- infers safe source/test allowed paths from existing directories;
- infers candidate dev, test, check, build, and preview commands from package
  scripts or Python/FastAPI conventions;
- always returns the external denied-path baseline used by registration;
- marks unknown or incomplete projects as `needs_confirmation` with warnings;
- exposes workspace-scoped analysis API for future registration and selection
  flows.

Current limitation: analyzer output is not yet merged into the Target Registry
or execution path. P9-3 and later tasks will consume analyzer/registration
metadata for planning, instructions, locks, evidence, and review.

### P9-1 External Workspace Registration

P9-1 completed on 2026-05-24 as the first implementation step of
`agenthub-p9-external-project-workspace-mode`.

AgentHub now has a persisted registration boundary for external local project
targets:

- external targets are stored per workspace with target ID, name, resolved root
  path, project type, allowed paths, denied paths, commands, package manager,
  detected framework, and analysis status;
- registration requires explicit bounded allowed paths and rejects whole-root,
  parent traversal, absolute allowed paths, missing roots, filesystem root, home
  directory, and common system directories;
- default denied paths include `.env`, `.env.*`, `secrets`, `.git`,
  `node_modules`, `.venv`, dependency directories, cache directories, and build
  output directories;
- backend APIs can create, list, and read registered external targets under a
  workspace;
- built-in `demo-frontend`, `demo-backend`, and `agenthub-platform` registry
  targets remain unchanged.

Current limitation: P9-1 only registers external targets. Planner,
instruction-builder, scheduler, adapter execution, evidence, and review
integration remain P9-3 through P9-7.

## P8 Status

### P8-6 P8 E2E Rehearsal And Freeze Review

P8-6 completed on 2026-05-24.

Result: P8 is ready to freeze as Dependency-aware Scheduler and Target Locks
for the local single-user AgentHub workspace.

The freeze rehearsal used a temporary git worktree and controlled local fake
adapter, not a fresh real Claude/Codex mutation. P6 remains the latest real
`ClaudeCodeAdapter` mini CRM execution evidence.

P8 rehearsal evidence:

- session ID: `3fad4108-f0ea-4134-8b31-fb2ab911fadd`;
- contract ID: `contract-mini_crm_contacts`;
- backend task / run:
  `e7f85f87-fa8a-4203-a33f-682e568a6d50`,
  `72cf0f92-1c65-460e-b697-4e37cbcefed0`;
- frontend task / run:
  `e37a46b0-834b-4396-b703-8ecdfd1bf27b`,
  `bb28106d-d1f8-4431-8245-d40db304edfa`;
- review task: `336a0c82-6caf-4d84-b421-4ccfcdd17ad7`;
- diff artifacts:
  `104f1a7b-fa6f-4842-9152-a8e2acc0bbce`,
  `e92f2e27-c463-4a41-8dad-c7fce2eb87ce`;
- preview: `56d01fc3-affb-4f6a-bf46-973469a81e1d`, `healthy`;
- mock deploy: `d94dade3-8b3e-4ea0-a0a9-61b2b085ce9e`, provider `mock`;
- target lock evidence: waiting task
  `7e507b15-3cd6-4be3-89d1-893e3777045a`, holder run
  `3c241653-2a4e-4782-b58c-729cdc98d1bf`;
- failed dependency evidence: failed task
  `39d5151f-888a-4790-bd66-9044f6328053`, blocked downstream task
  `84e11005-0148-4926-993c-6c002555507b`;
- platform protection evidence: platform task / run
  `4ed028eb-998c-4ca4-8aa0-e0c2dd9dd2f8`,
  `ca3f70d9-d4aa-49ed-9e47-c757c432bde5`, state `waiting_approval`.

See `docs/p8-freeze-review.md` for the full evidence record and caveats.

Recommended freeze tag:
`p8-dependency-scheduler-target-locks-freeze`.

### P8-5 Scheduler UI Trace

P8-5 completed on 2026-05-24.

The workspace UI now surfaces scheduler state from `planJson.scheduler` in the
existing task timeline and execution trace:

- task status labels include `waiting_dependency`, `waiting_target_lock`,
  `blocked`, `retryable`, and `fallback_available`;
- each task card can show scheduler reason, target ID, blocking dependency IDs,
  lock-holder TaskRun IDs, write-lock indicator, retryable state, and fallback
  availability;
- the execution trace header highlights dependency waits, target-lock waits,
  and blocked states;
- existing artifact chips, artifact message cards, right Artifact Panel, Start,
  Retry, Fallback, Review, Preview, and Deploy actions remain available.

Current limitation: P8-5 is a UI visibility pass only. It does not add new
scheduler backend semantics beyond P8-1 through P8-4.

### P8-4 Failure Recovery And Blocked States

P8-4 completed on 2026-05-24.

Scheduler-visible failure recovery states are now recorded in task
`planJson.scheduler`:

- completed TaskRuns record `state: completed`;
- failed or interrupted coding TaskRuns record `retryable: true`;
- failed/interrupted Codex coding runs record `state: fallback_available` and
  `fallbackAvailable: true`;
- failed non-Codex or non-fallback tasks record `state: retryable`;
- downstream dependencies still move to `blocked` on upstream failure;
- completed retry/fallback runs re-evaluate downstream tasks and can unblock
  them when dependencies and target locks are satisfied;
- terminal task scheduler metadata is preserved during session-level lock
  refresh.

Current limitation: P8-4 exposes retry/fallback state in backend payloads but
does not yet add dedicated UI treatment. That remains P8-5.

### P8-3 Auto-run Pipeline

P8-3 completed on 2026-05-24.

Contract-first full-stack plans now participate in automatic pipeline
progression:

- mini CRM / todo / notes contract-first backend and frontend tasks include
  `autoStart: true`;
- the initial backend task auto-starts through the existing TaskRun path once
  the synthetic contract task is completed;
- when a coding TaskRun completes, AgentHub collects diff, creates the scripted
  review artifact, refreshes ledger state, and starts the next runnable
  contract-first coding task;
- ready contract review / QA tasks are marked completed from the generated
  review artifact instead of running a mutating QA adapter;
- completed contract-first frontend runs attempt the existing Vite preview path
  and create a mock deployment only when the preview is healthy and the demo
  app root exists.

Current limitation: P8-3 still uses the existing local adapter execution path;
if Claude/Codex fails, downstream pipeline steps remain governed by P8-1/P8-2
dependency and lock states. Rich retry/fallback scheduler states remain P8-4.

### P8-2 Target Write Locks

P8-2 completed on 2026-05-24.

The scheduler now derives target write-lock requirements from P7 target-aware
task plans:

- `frontend_change`, `backend_change`, and `platform_maintenance` tasks require
  a write lock for their resolved `targetId`;
- same-session write tasks targeting `demo-frontend` or `demo-backend` do not
  start concurrently;
- lock-waiting tasks are marked `waiting_target_lock` with
  `planJson.scheduler.targetId` and `lockHolderTaskRunIds`;
- terminal TaskRun transitions refresh scheduler state so waiting tasks can
  return to `pending` / `ready` after the lock holder completes;
- Review / QA tasks remain read-oriented by default and do not acquire write
  locks unless explicitly marked as write tasks;
- ordinary backend tasks that try to target `agenthub-platform` without
  platform mode and approval are blocked before TaskRun creation.

Current limitation: P8-2 does not yet auto-progress the full Contract ->
Backend -> Frontend -> Review -> Preview -> Mock Deploy pipeline. That remains
P8-3.

### P8-1 Dependency-aware Task Scheduler

P8-1 completed on 2026-05-24 as the first implementation step of
`agenthub-p8-dependency-scheduler-target-locks`.

AgentHub now has a narrow scheduler boundary for task graph dependencies:

- tasks with incomplete upstream dependencies are marked
  `waiting_dependency` and do not auto-start;
- tasks with failed, interrupted, or blocked upstream dependencies are marked
  `blocked`;
- dependency wait/block metadata is visible in `planJson.scheduler`, including
  scheduler state, runnable flag, reason, dependency IDs, and blocking
  dependency IDs;
- synthetic Manager planning tasks that only represent an already-created plan
  are marked `completed` when the task graph is created, so dependent safe
  frontend tasks can still auto-start through the P6 path;
- when an upstream TaskRun reaches a terminal state, downstream tasks are
  re-evaluated;
- manual TaskRun creation keeps its existing behavior outside the scheduler
  auto-start path.

Current limitation: P8-1 does not add target write locks, automatic full
pipeline progression, failure recovery affordances, or scheduler UI trace.
Those remain P8-2 through P8-5.

## P7 Status

### P7-6 E2E Rehearsal And Freeze Review

P7-6 completed on 2026-05-24.

Result: P7 is ready to freeze as Target Project Registry + Permissioned
Execution for the local single-user AgentHub workspace.

P7 did not run a fresh real Claude/Codex mutation. The freeze review reused the
P6 final real `ClaudeCodeAdapter` mini CRM evidence for the diff, review,
preview, and mock deploy loop, then verified the new P7 registry and permission
boundaries through API rehearsal and full regression validation.

P7 API rehearsal evidence:

- mini CRM rehearsal session ID:
  `d0500f2c-a480-4903-aea5-5d2d72b2bf31`;
- contract ID: `contract-mini_crm_contacts`;
- frontend target ID / backend target ID: `demo-frontend`, `demo-backend`;
- registry-resolved demo API base URL: `http://127.0.0.1:5174`;
- mini CRM task IDs:
  `952bcfd1-12b9-41ca-b81d-694a66b4dcea`,
  `d382a368-0cd2-4d46-86c6-790b691d4b58`,
  `5966d060-0df4-463d-94e1-d7bebdddf729`,
  `634bb541-3b0e-47ad-a408-13392b6dea11`;
- platform rehearsal session ID:
  `57d92dde-710f-484e-b86a-f7c0e06e22e6`;
- platform task / run:
  `fc86452a-a92b-4894-844d-372b5df799e1`,
  `7ef6efcb-979c-4984-a1a2-2f29f893bc79`;
- platform target / state / approval:
  `agenthub-platform`, `waiting_approval`, `security_approval`, `high`.

See `docs/p7-freeze-review.md` for the full evidence record and caveats.

Recommended freeze tag:
`p7-target-registry-permissioned-execution-freeze`.

### P7-5 Platform Maintenance Mode

P7-5 completed on 2026-05-24.

AgentHub now separates ordinary app backend work from platform maintenance:

- ordinary `@backend` requests continue to create `demo-backend` tasks that
  target `apps/demo-api`;
- explicit platform maintenance requests such as `platform mode ...` create
  `platform_maintenance` tasks targeting `agenthub-platform`;
- platform maintenance plans include `platformMode: true`,
  `requiresApproval: true`, stricter validation expectations, and
  `safeTarget: apps/api`;
- creating a TaskRun for a platform maintenance task starts it in
  `waiting_approval` with a `security_approval` request instead of queueing
  adapter execution immediately.

This keeps AgentHub platform backend code protected from ordinary app backend
tasks while preserving an explicit path for approved platform maintenance.

### P7-4 Target-aware Review / QA

P7-4 completed on 2026-05-24.

Scripted review now evaluates contract diffs against Target Project Registry
policy:

- changed files must be permitted by either the contract frontend target or
  backend target;
- denied paths such as `apps/api`, `.env*`, `.git`, `node_modules`, and
  `secrets` are reported as target policy violations;
- ordinary app diffs that mutate `apps/api` are reported as `failed` /
  `high` risk;
- frontend local API base URLs are compared with the registry-resolved
  `demo-backend` base URL;
- task target IDs are checked against contract frontend/backend target IDs.

Review remains advisory in the product flow: warnings or failures are recorded
as review artifacts and do not introduce a new blocking approval gate in P7-4.

### P7-3 Target-aware Contract Planner

P7-3 completed on 2026-05-24.

Contract-first planning for bounded app requests now resolves targets through
the Target Project Registry:

- app contracts include `frontendTargetId: demo-frontend` and
  `backendTargetId: demo-backend`;
- app contracts keep compatibility fields such as `frontendTarget`,
  `backendTarget`, and `demoApiBaseUrl`, but those values are derived from
  registry metadata;
- generated backend, frontend, and review task plans include target IDs and
  registry-derived safe paths;
- task graph metadata includes target IDs where a task maps to a concrete
  target.

The P6 mini CRM path still creates the same four-task contract-first graph:
Manager contract, Backend Agent, Frontend Agent, and Review/QA. Unsupported
broad requests still avoid silent execution.

### P7-2 Target-aware Instruction Builder

P7-2 completed on 2026-05-24.

Agent instructions are now generated through the Target Project Registry
boundary:

- frontend instructions resolve `demo-frontend`, its allowed path
  `apps/demo/src`, and the related `demo-backend` base URL;
- backend instructions resolve `demo-backend`, its allowed path
  `apps/demo-api`, its validation command `pnpm demo:api:test`, and the
  `apps/api` denial;
- platform-maintenance instructions can be built only when a task explicitly
  targets `agenthub-platform`, and those instructions state that platform mode
  and approval are required;
- session context packs now include resolved target metadata when task plans
  include target IDs, while preserving the P6 legacy plan shape.

The old unused `instruction_for_task` helper in `apps/api/app/main.py` was
removed so `apps/api/app/instruction_builder.py` remains the single instruction
builder boundary.

Current limitation: planner-generated app contracts and tasks still need to be
migrated to emit target IDs by default in P7-3. Review policy enforcement still
needs the P7-4 target-aware checks.

### P7-1 Target Project Registry

P7-1 completed on 2026-05-24 as the first step of
`agenthub-p7-target-registry-permissioned-execution`.

AgentHub now has a static backend Target Project Registry boundary with three
initial targets:

- `demo-frontend`: `apps/demo`, frontend app target, allowed writes under
  `apps/demo/src`, related to `demo-backend`;
- `demo-backend`: `apps/demo-api`, backend app target, base URL
  `http://127.0.0.1:5174`, validation command `pnpm demo:api:test`;
- `agenthub-platform`: AgentHub maintenance target, requires explicit platform
  mode and approval, with stricter validation through `pnpm check && pnpm test`.

The registry also centralizes default denied paths such as `.env*`,
`node_modules`, `.git`, and `secrets`, and ordinary demo app targets deny
cross-target mutations such as `apps/api`.

Current limitation: P7-1 only introduces and tests the registry boundary.
Planner, instruction builder, context pack, review, and platform-maintenance
routing still use their existing P6 behavior until P7-2 through P7-5 migrate
them to consume registry metadata.

## P6 Status

### P6-7 Final Full-stack Rehearsal And Freeze Review

P6-7 final rehearsal passed on 2026-05-23 after the P6-7a API-base alignment
fix and a small demo-api CORS hardening fix.

Result: P6 is ready to freeze as a practical agent execution capability
upgrade for a local single-user Agent Coding Workspace. It is still not a
generic SaaS generator or production deployment platform.

Fresh rehearsal request:

```text
帮我做一个 mini CRM，包含联系人和备注
```

Fresh evidence:

- session ID: `d39ed32a-8426-4c75-86a1-9fd10a57f44c`;
- contract ID: `contract-mini_crm_contacts`;
- contract demo API base URL: `http://127.0.0.1:5174`;
- backend task / run: `efe6482b-b2e3-43a7-bae9-2aa0b44dde41`,
  `908a5708-3334-474c-8af6-b18e6ceaa319`;
- frontend task / run: `f1d141d1-7fcb-4629-9ed1-20fd957d6ef4`,
  `7a01e9ea-8d5d-4690-ae4c-35fbca0b6309`;
- adapter type for both coding runs: `claude_code`;
- final diff artifact ID: `a89dba5d-cc92-490c-aca1-6c00cd20cc5c`;
- final review artifact ID: `076f01c5-1949-4fa6-9715-623e41642edb`;
- final review status / risk: `passed`, `low`;
- preview ID / URL / health:
  `d515ffaf-bf9d-481d-9b51-77aa57eb2cef`,
  `http://127.0.0.1:62947`, healthy;
- mock deployment ID / provider / status:
  `ff54062e-35ca-462d-a5f7-e9a4786517ec`, `mock`, `ready`.

The final frontend diff included `http://127.0.0.1:5174` and did not include
`http://localhost:8000` or `http://127.0.0.1:8000`. Browser inspection of the
preview showed the contacts list with `Ada Lovelace` and `Grace Hopper`, which
verified that the browser-visible mini CRM loaded data from the demo API rather
than staying stuck at `Loading contacts...`.

The demo API now allows local preview origins through CORS so Vite previews on
dynamic local ports can call `apps/demo-api` during full-stack rehearsals.

Remaining caveats:

- the planned QA/Review task in the contract graph remains pending; the
  automatic post-diff review artifact supplies the contract consistency
  evidence;
- Review remains deterministic `scripted_mock`, not a real Claude review;
- deploy remains mock-labeled and is not production deployment;
- P6 remains bounded to todo, notes, and mini CRM contacts style vertical
  slices, not arbitrary SaaS generation;
- same-session write tasks remain serial.

Recommended freeze tag: `p6-agent-execution-upgrade-freeze`.

### P6-7a Demo API Base Alignment Fix

P6-7a completed on 2026-05-23 as a targeted fix for the P6-7 freeze blocker.

What changed:

- contract-first app contracts now include
  `demoApiBaseUrl: "http://127.0.0.1:5174"`;
- contract validation expectations now state that frontend app data calls must
  use the demo API base URL;
- contract-aware Frontend Agent instructions now explicitly require using the
  demo backend base URL from the contract;
- contract-aware Frontend Agent instructions explicitly forbid using the
  AgentHub platform API at `http://localhost:8000` or
  `http://127.0.0.1:8000` for generated app data;
- scripted review now warns when a frontend contract diff references the
  AgentHub platform API base instead of the demo API base.
- `apps/demo-api` now allows local preview origins through CORS so Vite
  previews on dynamic local ports can call the demo backend.

Tests added or updated:

- planning coverage verifies `demoApiBaseUrl` is present in the mini CRM
  `appContract`;
- instruction coverage verifies Frontend Agent prompts include
  `http://127.0.0.1:5174` and forbid `http://localhost:8000`;
- review coverage verifies a frontend diff with
  `const API_BASE = "http://localhost:8000"` produces a warning and suggests
  `http://127.0.0.1:5174`.
- demo-api coverage verifies local preview CORS preflight for `/contacts`.

P6-7a initially did not run a new real Claude/Codex mutation. A later fresh
P6-7 rehearsal verified that generated frontend code uses the demo API base and
the browser-visible mini CRM loads contacts from `apps/demo-api`.

### P6-7 Full-stack Vertical Slice Rehearsal And Freeze Review

P6-7 freeze review ran on 2026-05-23.

Result: P6 is not ready to freeze yet. The P6-6 evidence remains valid for
contract-first orchestration, target-aware backend/frontend task creation, real
`ClaudeCodeAdapter` execution, diff/review artifact creation, persistent
preview startup, and mock deploy creation. However, the browser-visible mini
CRM app is not fully integrated with the safe demo backend by default.

Reused P6-6 evidence:

- session ID: `ad122cf7-afe7-4921-bbd9-b7e815539427`;
- contract ID: `contract-mini_crm_contacts`;
- backend task / run: `590cb06b-4a47-422e-b68f-79a873d4c84a`,
  `d6779d0f-afa3-4124-9117-c40b651dd79a`;
- frontend task / run: `12ffc19d-f483-4f8d-a541-4c5b935a49b4`,
  `ade5c49c-097d-448e-831c-d10c6bdc3a71`;
- adapter type for both coding runs: `claude_code`;
- final diff artifact ID: `db403329-7f0c-4b2c-9134-d2d7ee652564`;
- final review artifact ID: `1782b85d-c7f9-4d93-b699-27bd27a05ef7`.

Persistent preview evidence:

- persistent AgentHub API was started on `http://127.0.0.1:8010` because the
  old `127.0.0.1:8000` process accepted TCP connections but did not respond to
  `/health`;
- preview was started through the persistent API for frontend task run
  `ade5c49c-097d-448e-831c-d10c6bdc3a71`;
- new preview ID: `3e500940-4d46-423b-af66-b36f1e6ba604`;
- new preview URL / health: `http://127.0.0.1:65046`, healthy;
- `curl -I http://127.0.0.1:65046` returned `200 OK` immediately after preview
  creation and again after a 20 second delay;
- new mock deploy ID / provider / status:
  `6b14e81b-c1d6-40ed-b6c4-88a3f846db60`, `mock`, `ready`.

The temporary preview process and the temporary `8010` / `5174` dev services
were stopped after verification.

Demo backend evidence:

- `pnpm demo:api:dev` served the safe demo backend on
  `http://127.0.0.1:5174`;
- `GET /health` returned `{"status":"ok","service":"agenthub-demo-api"}`;
- `GET /contacts` returned the seed contacts.

Freeze blocker:

- the generated frontend code in the P6-6 session worktree uses
  `const API_BASE = "http://localhost:8000"`;
- `apps/demo-api` defaults to `http://127.0.0.1:5174`;
- browser inspection of the preview showed the app stuck at
  `Loading contacts...`;
- `curl http://127.0.0.1:8000/contacts` timed out against the stale AgentHub API
  process;
- therefore the final mini CRM preview shell is reachable, but the generated
  frontend does not reliably call the safe demo backend target.

P6-7 is intentionally left unchecked in the OpenSpec task list until this
integration blocker is re-verified with a fresh rehearsal. P6-7a fixed the
planning, instruction, and review path so future full-stack frontend tasks are
directed to the demo API base URL and API-base mismatches are caught by review.

### P6-6 Mini CRM Full-stack Vertical Slice

P6-6 completed on 2026-05-22 as an API-driven full-stack vertical slice smoke.

Smoke request:

```text
帮我做一个 mini CRM，包含联系人和备注
```

Result: a normal no-mention request routed through Orchestrator, generated the
shared `contract-mini_crm_contacts` app contract, created target-aware Backend
Agent and Frontend Agent tasks, ran both coding tasks with
`ClaudeCodeAdapter`, produced a final accumulated diff covering both demo
backend and demo frontend targets, generated review artifacts, created a
preview artifact, and created a mock deployment artifact.

Evidence:

- session ID: `ad122cf7-afe7-4921-bbd9-b7e815539427`;
- contract ID: `contract-mini_crm_contacts`;
- backend task / run: `590cb06b-4a47-422e-b68f-79a873d4c84a`,
  `d6779d0f-afa3-4124-9117-c40b651dd79a`;
- frontend task / run: `12ffc19d-f483-4f8d-a541-4c5b935a49b4`,
  `ade5c49c-097d-448e-831c-d10c6bdc3a71`;
- adapter type for both coding runs: `claude_code`;
- final diff artifact ID: `db403329-7f0c-4b2c-9134-d2d7ee652564`;
- final review artifact ID: `1782b85d-c7f9-4d93-b699-27bd27a05ef7`;
- preview ID / URL / health: `79bfff4f-4991-470b-8862-eb43e7dac852`,
  `http://127.0.0.1:55592`, healthy at creation;
- mock deployment ID / provider / status:
  `e7b676d6-1505-43f8-be78-7120bfaef831`, `mock`, `ready`.

Changed files in the session worktree:

- `apps/demo-api/app/main.py`;
- `apps/demo-api/tests/test_contacts.py`;
- `apps/demo/src/App.tsx`;
- `apps/demo/src/styles.css`.

The final review artifact passed with low risk and verified contract
consistency for `contract-mini_crm_contacts`: the accumulated diff included
both backend target changes under `apps/demo-api` and frontend target changes
under `apps/demo/src`.

The demo backend tests in the smoke worktree passed from the correct
`apps/demo-api` working directory: `6 passed`.

Caveats:

- this was API-driven rehearsal, not browser click rehearsal;
- the review artifact used deterministic `scripted_mock` review behavior;
- the planned QA/Review task remained pending because the automatic post-diff
  review artifact supplied the contract consistency evidence;
- the preview artifact was healthy at creation, but a later `curl` to the
  recorded preview URL failed after the one-shot TestClient smoke process
  exited. Long-lived preview availability should be checked under persistent
  `pnpm dev:api` during P6-7.

Detailed evidence is recorded in `docs/p6-mini-crm-vertical-slice.md`.

### P6-5 Target-Aware Contract-First Orchestrator

P6-5 completed on 2026-05-22.

AgentHub now has contract-first Orchestrator planning for bounded full-stack
mini app requests. This is a planning upgrade only; it does not run real
Claude/Codex full-stack generation yet.

Supported app types:

- todo app;
- notes app;
- mini CRM contacts app.

When a normal no-mention or `@orchestrator` message asks for one of those app
types, Orchestrator creates a shared `appContract` plan payload with:

- `appName`;
- `appType`;
- `userGoal`;
- `entities` and `fields`;
- `apiRoutes`;
- `frontendPages`;
- `backendTarget: apps/demo-api`;
- `frontendTarget: apps/demo`;
- `validationExpectations`;
- `taskGraph`.

The generated task graph is serial and target-aware:

```text
Manager / Contract task -> Backend Agent task -> Frontend Agent task -> QA / Review task
```

Each task stores the same `contractId` and `appContract` in `planJson`.
Backend tasks target `apps/demo-api`, frontend tasks target `apps/demo/src`
inside the `apps/demo` frontend, and review tasks validate that backend and
frontend work reference the same contract. The tasks are pending by default and
do not auto-start in P6-5.

Role instructions now surface the shared app contract explicitly:

- Backend Agent instructions reference the contract and target `apps/demo-api`;
- Frontend Agent instructions reference the same contract and target
  `apps/demo/src`;
- QA / Review instructions review backend and frontend work against the shared
  contract.

Existing login-page, bounded frontend planner, no-mention dashboard auto-run,
direct `@frontend`, and direct `@backend` paths remain intact.

Unsupported broad SaaS requests, such as production SaaS with payments,
authentication, or multi-tenancy, still create no unrestricted task and receive
an honest boundary response.

P6-5 does not implement actual full-stack app generation, production deploy,
auth, payments, multi-tenancy, Docker, cloud database, provider marketplace, PR
creation, or any permission to modify `apps/api` as app backend code.

### P6-4 Safe Demo Backend Target Scaffold

P6-4 completed on 2026-05-22.

AgentHub now has an isolated demo backend target under `apps/demo-api` so
Backend Agent work can target application backend code without modifying the
AgentHub platform backend in `apps/api`.

Demo backend scaffold:

- framework: minimal FastAPI app;
- persistence: in-memory contacts for the first scaffold;
- endpoints:
  - `GET /health`;
  - `GET /contacts`;
  - `POST /contacts`;
- local dev command: `pnpm demo:api:dev`;
- test command: `pnpm demo:api:test`;
- check command: `pnpm check:demo-api`.

`@backend` direct mentions now create a pending `backend_change` task assigned
to the Backend Agent when `apps/demo-api` exists. The task is bounded to
`apps/demo-api` and includes `apps/demo-api/app/main.py` and
`apps/demo-api/tests/test_contacts.py` as the first scaffold files. It does not
auto-start in P6-4.

Backend role instructions now state that `apps/demo-api` exists, mention the
contacts API scaffold, and continue to forbid editing `apps/api`, which remains
the AgentHub control-plane backend.

P6-4 does not implement contract-first orchestration, full-stack app
generation, production deploy, Docker, auth, payment, cloud database,
multi-tenant behavior, or automatic frontend integration with the demo API.

### P6-2 / P6-3 Context Pack And Role-Based Instructions

P6-2 and P6-3 completed on 2026-05-22.

AgentHub now builds a reusable session context pack for agent execution and
uses a role-based instruction builder for TaskRun adapter requests.

Context pack fields include:

- original user request;
- current task ID, title, intent type, description, and plan;
- recent messages from the same session only, bounded to eight messages;
- session execution ledger summary and latest ledger IDs;
- latest changed files;
- latest diff metadata, including artifact ID, refs, changed files, and stats;
- latest review summary, status, risk, files reviewed, findings, and
  suggestions;
- latest preview ID, URL, health, and port;
- latest mock deployment ID, provider, environment, status, and URL;
- selected artifact context when a valid current-session artifact ID is passed;
- safe target paths;
- validation expectations for the task role and artifact flow.

The context pack is attached to adapter `planContext` as `sessionContext` and
is also embedded in the generated instruction as a JSON block. This gives
Claude Code / Codex enough session state for follow-up work without allowing
cross-session leakage.

Role instruction behavior:

- Manager / Orchestrator instructions focus on routing, bounded task creation,
  clarification, and honest rejection for unsupported work.
- Frontend instructions preserve the original request, include session context,
  keep legacy login-page/button/title templates intact, and allow meaningful
  changes only inside `apps/demo/src` for generic demo frontend requests.
- Backend instructions prepare for `apps/demo-api`, but clearly state that the
  safe demo backend target is not available yet and that `apps/api` must not be
  modified.
- QA / Review instructions are read-oriented by default and focus on diff,
  changed files, ledger, preview/deploy status, and advisory findings.

P6-2/P6-3 do not add `apps/demo-api`, full-stack app generation,
Manager/Worker scheduling, production deploy, new adapters, or broader
guardrail permissions.

Validation passed:

- targeted `pytest tests/test_planning.py tests/test_task_runs.py -q`
  (37 tests);
- full validation results are recorded in the change log for this task.

### P6-1b Orchestrator Autonomy Real Smoke

P6-1b completed on 2026-05-22 as an API-driven real execution smoke.

Smoke request:

```text
帮我把当前 demo app 改成一个 dashboard，有三张统计卡片和一个最近活动列表
```

Result: a normal user message without an explicit `@mention` routed to
Orchestrator / Manager, created a safe demo frontend task, auto-started a
TaskRun, invoked `ClaudeCodeAdapter`, produced a real diff, generated a
non-blocking scripted review artifact, started a healthy preview during the
smoke, and created a mock deploy artifact.

Evidence:

- session ID: `cca9af54-1338-4cdd-b239-7f8b6e1dcc76`;
- message ID: `48bad4c0-8ddf-4514-bf35-d2561082c22e`;
- task ID: `63a8aded-b311-40f3-a54c-a40d232102c5`;
- task run ID: `210f3f89-df0f-4e72-8c20-d505faed5ea2`;
- adapter type: `claude_code`;
- final state: `completed`;
- changed files: `apps/demo/src/App.tsx`,
  `apps/demo/src/styles.css`;
- diff artifact ID: `7114d52a-925a-4c4d-a00b-4d6c8775a20c`;
- review artifact ID: `ce989818-5d85-4f88-9f70-8b9b5e69d606`;
- preview ID / URL / health: `841f7fd6-bb75-4e80-b19c-9b228f5040fb`,
  `http://127.0.0.1:58487`, healthy during the smoke;
- deployment ID / provider / status:
  `7c9fab78-2b5f-44b3-a9fc-2af0d912a757`, `mock`, `ready`.

The session ledger recorded the original goal, `frontend` as active agent, the
latest diff/review/preview/deploy evidence, and `claude_code` as the last
successful adapter.

Caveats:

- this was an API-driven smoke using FastAPI `TestClient`, not a browser click
  rehearsal;
- a follow-up `curl` after the one-shot TestClient process exited could not
  reach the preview URL, so long-lived preview availability should be verified
  under `pnpm dev:api` in a later browser rehearsal;
- the Review artifact used deterministic `scripted_mock` review behavior;
- ScriptedMock fallback execution was not needed because the real Claude Code
  run succeeded.

Detailed evidence is recorded in `docs/p6-orchestrator-autonomy-smoke.md`.

### P6-1 Orchestrator Autonomy Spike

P6-1 completed on 2026-05-22.

AgentHub now has the first P6 message routing and execution autonomy slice:

- normal user messages without explicit role mentions route to Orchestrator /
  Manager by default;
- `@orchestrator` also routes to Orchestrator / Manager;
- `@frontend`, `@backend`, `@qa`, and `@review` are explicit assignment modes
  for advanced users;
- Orchestrator-created safe demo frontend tasks can auto-start through the
  existing TaskRun path;
- generic demo frontend instructions preserve the original user request and
  allow broader changes inside `apps/demo/src` instead of reducing every task
  to login-page/button/title templates.

The first auto-run path is intentionally narrow. P6-1 auto-starts only safe
demo frontend tasks marked with `autoStart` and `safeTarget=apps/demo/src`.
Backend execution does not auto-start because the safe demo backend target is
not available yet; direct `@backend` requests now receive a clear missing-target
response instead of creating an unrestricted task against the AgentHub platform
backend.

Routing behavior:

- no explicit mention: Orchestrator decides whether to create a task, ask for a
  bounded demo target, or reject unsupported requests honestly;
- `@frontend`: creates a pending frontend task when the request is bounded to
  the demo app UI;
- `@backend`: reports that a safe demo backend target is required first;
- `@qa`: creates a QA review-style task assigned to the QA agent;
- `@review`: creates a read-only review task assigned to the QA-backed review
  path.

P6-1 keeps the existing `CodexAdapter`, `ClaudeCodeAdapter`, and
`ScriptedMockAdapter` execution path. It does not add a full approval/risk
engine, Manager/Worker scheduler, full-stack app generation, multi-user IM,
provider marketplace, production deploy, or PR creation.

Validation passed:

- `pnpm check`
- `pnpm test` (36 web tests, 121 API tests)
- `git diff --check`
- `openspec validate agenthub-p6-agent-execution-upgrade --strict`

Manual browser smoke was not run in P6-1. The auto-run behavior was verified
through API tests that confirm a no-mention demo dashboard request creates a
frontend task and queued TaskRun with the configured adapter. Real Claude/Codex
success was not claimed or re-run in this task.

## P5 Status

### P5-7 E2E Rehearsal And Freeze Review

P5-7 completed on 2026-05-22.

Freeze result: P5 is ready to freeze as a local single-user IM-style
multi-agent coding workspace v1. It preserves the P4 final demo baseline and
does not claim to be a full multi-user IM platform.

Review basis:

- initial worktree was clean at `d3b479d feat: add review workflow, execution
  trace, and artifact cards`;
- reviewed `AGENTS.md`, the project README, project state, change log, P4 audit
  and final demo docs, platform roadmap, and the P5 OpenSpec proposal, design,
  tasks, and spec;
- no new Claude/Codex mutation was run during P5-7, to avoid repeated real
  adapter work after the P4 browser rehearsal already verified the real and
  fallback execution paths;
- P5-specific behavior was verified through committed backend/frontend tests and
  code review of the implemented task slices.

P5 freeze evidence:

- Agent contacts render Manager / Orchestrator, Frontend, Backend, QA, Review,
  and Fallback entries with role, adapter type, tags, and status. Direct chat
  and Group workflow remain local visual modes only.
- Workspace Context / Execution Ledger is persisted and exposed through
  `GET /sessions/{session_id}/ledger`, with tests covering updates after
  planning, diff, preview, and mock deployment.
- Dynamic Manager Planner v1 supports bounded frontend intents for heading/title
  text, primary button text, accent color, simple input field, status/help text,
  and small layout copy changes. Unsupported broad requests create no tasks and
  do not claim support.
- Review artifacts are created after diff collection, use deterministic
  `scripted_mock` review behavior in v1, and remain non-blocking for preview and
  mock deploy.
- Multi-Agent Execution Trace shows Manager planned, Coding Agent ran, Diff
  produced, Review Agent reviewed, Preview healthy, and Mock deploy ready.
- Artifact Message Cards render Diff, Review, Preview, and Mock Deploy cards,
  select the right Artifact Panel item, and only expose actions backed by
  existing APIs.
- Preview and Mock Deploy continue to use the existing preview/deployment APIs.
- P4 browser evidence remains the real end-to-end proof for
  requirement -> plan -> agent execution -> diff -> preview -> mock deploy:
  real Claude Code run `f1e78e9e-2f6b-4b9c-b4a7-5879d513c555`, diff artifact
  `b4c0fae4-bfeb-4105-a506-64de639472c6`, preview
  `4eb1622b-fb10-49e7-9b3d-5c256fad4b29`, deployment
  `6c5a423c-ec7b-4070-9a05-87a8dddd91a1`; fallback run
  `36d68849-f644-4242-a64b-27c05b8cf2d8`, diff artifact
  `fbe67726-20e3-4ad5-9b08-d4514aa97cbe`, preview
  `6c7f6f46-e287-4698-b6be-c99058f69b11`, deployment
  `a0b5d533-acee-4b2a-a384-103197d46481`.

Remaining caveats:

- P5 is still local single-user software, not a full multi-user IM product.
- Direct chat and Group workflow are visual modes only; no accounts,
  multiplayer sync, or external IM integration was added.
- The Review Agent is deterministic and non-blocking in v1, not an enterprise
  security gate or real Claude/Codex review path.
- The dynamic planner is bounded and rule-based, not unrestricted natural
  language editing or a general LLM planner.
- Artifact context selection is a frontend session affordance only; artifact
  references are not persisted into backend message records.
- Mock Deploy remains mock evidence, not production deployment.

Recommended tag name after committing the P5 freeze review:
`agenthub-p5-platform-evolution-freeze`.

Validation passed:

- `openspec validate agenthub-p5-platform-evolution --strict`
- `pnpm check`
- `pnpm test` (36 web tests, 116 API tests)
- `git diff --check`

### P5-6 Artifact Message Cards v2

P5-6 completed on 2026-05-21.

AgentHub now renders Diff, Review, Preview, and Mock Deploy artifacts as
message-style cards inside the task timeline. The cards reuse existing loaded
artifacts and do not add a new backend artifact-reference table.

Artifact card behavior:

- Diff cards show changed files, additions/deletions, source task/run, and
  actions to inspect the Diff, use the Diff as local follow-up context, or
  trigger the existing Review API when a review is not already loaded.
- Review cards show review status, risk, files reviewed, adapter type, source
  task/run, and actions to inspect or use the review as local follow-up
  context.
- Preview cards show URL, health, status, port, source task/run, and actions to
  inspect, open the preview, or create the existing mock deploy card when the
  preview is healthy.
- Mock Deploy cards show provider, environment, status, URL, source task/run,
  and remain explicitly labeled as mock deploy evidence.

The right Artifact Panel remains the detailed inspector. Selecting a card opens
the matching panel item. The composer now shows a local, session-scoped
follow-up context chip when the user chooses an artifact as context. This is a
frontend affordance only; P5-6 does not persist message-to-artifact references
or change backend planning semantics.

P5-6 does not add production deploy, provider marketplace, document/PPT
rendering, full code editor editing, unrestricted arbitrary editing, or adapter
execution changes.

Validation passed:

- `pnpm check`
- `pnpm test` (36 web tests, 116 API tests)
- `git diff --check`
- `openspec validate agenthub-p5-platform-evolution --strict`

### P5-5 Dynamic Manager Planner v1

P5-5 completed on 2026-05-21.

AgentHub now has a bounded local Manager planner v1 for a small set of
frontend change intents. The implementation is deterministic and rule-based;
it does not call an LLM planner and does not claim unrestricted natural
language editing.

Supported dynamic frontend intents:

- title or heading text change;
- primary button text change;
- theme/accent color change;
- simple input field addition;
- simple status/help text addition;
- small layout copy adjustment.

Dynamic Manager plans persist structured task graph metadata in task
`planJson`. The graph includes the goal, planner version, intent, task nodes,
assigned agent role, priority, dependencies, and expected artifact types. For
new orchestrator-led bounded frontend requests, the graph creates Manager,
Frontend Coding, and Review tasks. For same-session follow-up requests, it
creates a serial Frontend Coding task followed by a Review task that depends on
the coding task.

The existing deterministic login-page planner remains intact as
`deterministic_login_v1`, and the known button/title follow-up path still
works. Unsupported broad requests, such as whole-app refactors, fall back to
the existing deterministic behavior and do not create tasks or claim support.

P5-5 adds bounded instructions for real coding adapters for the new targets,
but it does not change adapter dispatch, adapter runtime semantics,
Manager/Worker scheduling, production deploy, multi-user IM, or the P4 final
demo baseline. `ScriptedMockAdapter` remains optimized for the original login
page and copy-change demo path.

Validation passed:

- `pnpm check`
- `pnpm test` (34 web tests, 116 API tests)
- `git diff --check`
- `openspec validate agenthub-p5-platform-evolution --strict`

### P5-4 Multi-Agent Execution Trace UI

P5-4 completed on 2026-05-21.

AgentHub now shows a multi-agent execution trace inside each task card. The
trace is derived from existing tasks, task runs, loaded artifacts, reviews,
previews, and deployments; it does not add a new backend trace endpoint or
change adapter execution semantics.

Trace stages:

- Manager planned;
- Coding Agent ran;
- Diff produced;
- Review Agent reviewed;
- Preview healthy;
- Mock deploy ready.

Each stage shows the responsible agent or service identity, adapter/service
type, state, and available artifact link. Diff, Review, Preview, and Mock
Deploy trace nodes reuse the existing artifact selection behavior so the
right-side artifact panel remains the detailed inspector. System steps such as
Diff Service, Preview Service, and Mock Deploy Service are labeled as services,
not autonomous agents.

The trace highlights fallback recovery when a `scripted_mock` run recovered
from a prior run and highlights review warning states. The P5-3 review remains
advisory and non-blocking.

P5-4 does not add Manager/Worker scheduling, dynamic planning, real multi-user
IM, production deploy, new adapters, or real Claude/Codex review execution.

Validation passed:

- `pnpm check`
- `pnpm test` (34 web tests, 113 API tests)
- `git diff --check`
- `openspec validate agenthub-p5-platform-evolution --strict`

### P5-3 Review Agent Workflow

P5-3 completed on 2026-05-21.

AgentHub now creates a non-blocking Review Agent artifact after a coding diff is
generated. The first implementation is deterministic and labeled as
`scripted_mock`; it does not claim real Claude or Codex review execution.

Review behavior:

- diff collection still stores the Git diff first;
- a scripted Review artifact is created for the latest diff on the TaskRun;
- repeated review creation for the same diff is idempotent;
- review status is advisory and can be `passed`, `warning`, or `failed`;
- v1 review does not block preview creation or mock deployment;
- `GET /task-runs/{task_run_id}/reviews` lists persisted review artifacts;
- `POST /task-runs/{task_run_id}/review` can create or return the current
  scripted review for a TaskRun.

Review artifact schema includes status, risk level, summary, reviewed files,
findings, suggested changes, reviewed diff artifact ID, and adapter type.

The session ledger summary now includes the latest review summary when present.
The right artifact panel and task timeline can show Review artifacts alongside
Diff, Preview, and Mock Deploy artifacts.

P5-3 does not add enterprise approval gates, security enforcement, real
Claude/Codex review execution, Manager/Worker scheduling, or any blocking
policy for preview/deploy.

Validation passed:

- `pnpm check`
- `pnpm test` (33 web tests, 113 API tests)
- `git diff --check`
- `openspec validate agenthub-p5-platform-evolution --strict`

### P5-2 Shared Context and Execution Ledger

P5-2 completed on 2026-05-21.

AgentHub now persists a lightweight session-scoped execution ledger in SQLite
and exposes it through `GET /sessions/{session_id}/ledger`. The ledger is a
deterministic snapshot of existing session records, not long-term memory. It
tracks:

- current goal;
- active agent roles;
- latest task and task run;
- latest diff artifact and changed files;
- latest preview ID, URL, and health;
- latest mock deployment ID, provider, and status;
- last successful adapter;
- a compact Markdown summary and update timestamp.

Ledger refresh points:

- after user message creation and planning;
- after successful diff collection;
- after healthy preview creation or preview health refresh;
- after mock deployment creation;
- on ledger read, so older sessions can be reconstructed from persisted
  messages, tasks, runs, and artifacts.

The workspace shell now shows a small `Workspace Context` card for the selected
session. It summarizes the current goal, active agents, latest evidence,
adapter, and changed files without replacing the task timeline.

P5-2 does not add vector memory, embeddings, cross-session memory, Review Agent
execution, Manager/Worker scheduling, or adapter dispatch changes.

Validation passed:

- `pnpm check`
- `pnpm test` (30 web tests, 113 API tests)
- `git diff --check`
- `openspec validate agenthub-p5-platform-evolution --strict`

### P5-1 Agent Registry and IM Contact UI

P5-1 completed on 2026-05-21 as the first implementation slice of
`agenthub-p5-platform-evolution`.

AgentHub now exposes enabled built-in agents as IM-style contacts through a
workspace-scoped read API and renders them in the workspace shell. The contact
registry is display/metadata only and does not change adapter dispatch,
planning, task execution, diff collection, preview, or mock deploy behavior.

Visible contacts:

- Manager / Orchestrator (`@orchestrator`, `scripted_mock`);
- Frontend Agent (`@frontend`, `codex`);
- Backend Agent (`@backend`, `codex`);
- QA Agent (`@qa`, `scripted_mock`);
- Review Agent placeholder (`@review`, planned `claude_code`);
- Fallback Agent / ScriptedMock (`@fallback`, `scripted_mock` service).

The UI adds local visual modes for Direct chat and Group workflow. These are
single-user product modes only; they do not add multi-user accounts, external
IM integration, Manager/Worker scheduling, dynamic planning, or Review Agent
execution.

Validation passed:

- `pnpm check`
- `pnpm test` (28 web tests, 114 API tests)
- `git diff --check`
- `openspec validate agenthub-p5-platform-evolution --strict`

## P4 Status

### P4-6 Final Freeze Review

P4-6 final freeze review completed on 2026-05-20.

Freeze result: ready to freeze the `agenthub-final-demo-hardening` baseline.

Verified documentation consistency:

- `AGENTS.md`, README, `docs/project-state.md`, `docs/change-log.md`,
  `docs/e2e-capability-audit.md`, `docs/final-demo-checklist.md`,
  `docs/project-summary-for-interview.md`, `docs/platform-roadmap.md`, and the
  `agenthub-final-demo-hardening` OpenSpec artifacts consistently describe
  AgentHub as a local single-user Agent Coding Workspace / strong demo MVP.
- Docs do not claim a full IM multi-user platform, production deploy, provider
  marketplace, Docker sandbox, PR creation, or broad arbitrary
  natural-language editing.
- P4 tasks 1.1 through 1.6 are complete after this review.

Remaining caveats are documented:

- deploy is mock-backed, not production deployment;
- browser click automation has local tooling/permission caveats recorded in
  `docs/e2e-capability-audit.md`;
- `pnpm demo:reset` does not delete `.worktrees`;
- `pnpm demo:reset` does not stop old preview or dev-server processes;
- mobile/responsive polish remains future work, not final-demo scope.

Validation passed:

- `openspec validate agenthub-im-coding-mvp --strict`
- `openspec validate agenthub-final-demo-hardening --strict`
- `pnpm check`
- `pnpm test`
- `git diff --check`

Recommended tag name after committing the final freeze review:
`agenthub-final-demo-hardening-freeze`.

### P4-5 Final Project Summary / Interview Explanation

P4-5 adds `docs/project-summary-for-interview.md`, a truthful final project
summary for demo, review, and interview use. It positions AgentHub as a local
single-user Agent Coding Workspace / strong demo MVP and explains:

- the problem AgentHub solves;
- frontend, backend, SQLite, session worktree, adapter, and artifact-pipeline
  architecture;
- the core requirement -> plan -> execution -> diff -> preview -> mock deploy
  workflow;
- `CodexAdapter`, `ClaudeCodeAdapter`, and `ScriptedMockAdapter`;
- forced-failure fallback recovery;
- same-session follow-up text-change flow;
- what is real, what is mock, and what is intentionally not implemented;
- design trade-offs and interview talking points.

The summary points readers to `docs/e2e-capability-audit.md` for evidence IDs
instead of inventing new evidence.

### P4-4 Final Demo Checklist

P4-4 adds `docs/final-demo-checklist.md` as the evidence-first rehearsal
checklist for the final AgentHub demo. It covers:

- clean reset with `pnpm demo:reset`;
- backend/frontend startup;
- optional Claude Code default adapter startup;
- fixed requirement message;
- task run, adapter, diff, preview, and mock deploy verification;
- fallback recovery through forced Codex failure and `ScriptedMockAdapter`;
- same-session follow-up request `把按钮文案改成 Sign in`;
- evidence ID capture;
- troubleshooting for occupied ports, missing API, auth/quota/runtime issues,
  stale preview, and reset refusal while SQLite is open.

The checklist is documentation-only and does not change app behavior.

### P4-3 Demo Reset / Clean Seed Helper

P4-3 adds a safe local reset workflow for repeatable final-demo rehearsals:

- Command: `pnpm demo:reset`
- Script: `scripts/demo-reset.sh`
- Active SQLite DB: `apps/api/data/agenthub.sqlite3`
- Backup location:
  `apps/api/data/backups/demo-reset-<timestamp>/`
- Reset behavior:
  - refuses to run while the SQLite DB is open by the API process;
  - backs up the active DB plus any SQLite WAL/SHM files;
  - recreates and seeds the database using the existing SQLModel init path;
  - does not delete `.worktrees`, source code, dependencies, or preview files;
  - does not stop running preview or dev-server processes;
  - prints restore commands for the created backup.

The helper seeds the existing baseline demo records: one demo user, one
`AgentHub Demo` workspace pointing at `apps/demo`, and enabled orchestrator,
frontend, backend, and QA agents. It does not pre-create a session; the demo
starts cleanly by creating a new session in the UI.

Reset rehearsal on 2026-05-20:

- First run while the API had SQLite open: refused reset and printed the owning
  process.
- Second run after stopping the API: backed up the previous DB to
  `apps/api/data/backups/demo-reset-20260520-124612/`.
- Seed check after reset: 1 user, 1 workspace, 4 agents, 0 sessions, 0 task
  runs, 0 previews.
- `.worktrees` remained present and was not deleted.

### P4-2 Browser E2E Click Rehearsal

P4-2 verified the final demo loop through browser UI clicks at
`http://127.0.0.1:3000` while the API ran with
`AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code pnpm dev:api`.

Real Claude Code path passed through UI clicks:

- Session: `59ad209a-1f8d-4134-97c4-e4ad275b6f67`
- UI label: `会话 55`
- Task: `eaac4f19-03c7-486f-b85a-1c4847cdcec8`
- TaskRun: `f1e78e9e-2f6b-4b9c-b4a7-5879d513c555`
- Adapter: `claude_code`
- Final state: `completed`
- Changed file: `apps/demo/src/App.tsx`
- Diff artifact: `b4c0fae4-bfeb-4105-a506-64de639472c6`
- Preview: `4eb1622b-fb10-49e7-9b3d-5c256fad4b29`
- Preview URL: `http://127.0.0.1:49373`
- Preview health/status: `healthy`, `ready`
- Deployment: `6c5a423c-ec7b-4070-9a05-87a8dddd91a1`
- Provider/status: `mock`, `ready`

Fallback path passed through UI clicks:

- Session: `c148a1d6-8cd1-4efb-a797-7d10bbe475aa`
- UI label: `会话 56`
- Task: `200e3d57-5856-41d1-9ec5-1ba203edc1f0`
- Failed Codex TaskRun: `e7cead6e-93cd-4195-9a53-e258da253a81`
- Failed error code: `CODEX_DEMO_FORCED_FAILURE`
- Fallback TaskRun: `36d68849-f644-4242-a64b-27c05b8cf2d8`
- Adapter: `scripted_mock`
- Final state: `completed`
- Changed file: `apps/demo/src/App.tsx`
- Diff artifact: `fbe67726-20e3-4ad5-9b08-d4514aa97cbe`
- Preview: `6c7f6f46-e287-4698-b6be-c99058f69b11`
- Preview URL: `http://127.0.0.1:49752`
- Preview health/status: `healthy`, `ready`
- Deployment: `a0b5d533-acee-4b2a-a384-103197d46481`
- Provider/status: `mock`, `ready`

Reload caveat: persisted runs, chips, and artifact tabs survived reload. The
right artifact panel defaults back to Diff after reload; click `预览1` to show
the persisted preview URL and iframe again.

Follow-up browser spot check on 2026-05-20 re-opened the persisted P4-2
sessions without running another real agent mutation:

- Real Claude Code session
  `59ad209a-1f8d-4134-97c4-e4ad275b6f67` still showed the completed
  `claude_code` run, `apps/demo/src/App.tsx` diff chip, `预览1` iframe at
  `http://127.0.0.1:49373`, and mock deployment
  `6c5a423c-ec7b-4070-9a05-87a8dddd91a1`.
- Fallback session `c148a1d6-8cd1-4efb-a797-7d10bbe475aa` still showed
  `CODEX_DEMO_FORCED_FAILURE`, `scripted_mock`, `兜底已恢复`, `Diff 就绪`,
  `预览健康`, and `模拟部署就绪`.

### P4-1 Baseline Governance Cleanup

P4-1 aligns repository governance around the current project identity:

- AgentHub is a local single-user Agent Coding Workspace / strong demo MVP, not
  a full multi-user IM collaboration platform.
- `CodexAdapter`, `ClaudeCodeAdapter`, and `ScriptedMockAdapter` are all current
  adapters and must not be removed or regressed.
- The fallback-based P0 path, P1/P2/P3 verified paths, and P4-0 real-agent
  evidence remain preserved.
- Production deploy, provider marketplace, WebSocket/multiplayer, Docker
  sandbox, external IM integrations, PR creation, broad arbitrary editing, and
  enterprise workflows remain deferred.

### P4-0 Full E2E Agent Execution Capability Audit

P4-0 verified that AgentHub can drive the full coding-agent execution pipeline
through the browser-facing API path:

```text
requirement -> orchestrator plan -> Direct Start -> agent execution -> file mutation -> diff -> preview -> mock deploy
```

Real-agent path with Claude Code default adapter passed:

- Session: `ebec86df-90bf-47ed-a5f1-b4f3b82a6c84`
- Task: `7c0fab95-e929-4252-9231-d92c2cc7e2e1`
- TaskRun: `ab038575-a4e4-406c-bfcf-e0ae3ca4a318`
- Adapter: `claude_code`
- Final state: `completed`
- Changed file: `apps/demo/src/App.tsx`
- Diff artifact: `1c53db5d-94ba-4667-af09-c8e5b8a2214f`
- Preview: `51e6c80f-006f-48e5-b1f7-2ecd629de442`
- Preview URL: `http://127.0.0.1:62044`
- Preview health/status: `healthy`, `ready`
- Deployment: `2b9e1c5e-c936-47c5-bd2a-4b29e243cca1`
- Provider/status: `mock`, `ready`

Fallback path passed:

- Session: `52836726-e895-43da-964a-3244a30d5948`
- Task: `773483a0-e026-4aa0-b816-0cb4decdfaf4`
- Failed Codex TaskRun: `608113c6-a5f8-4df1-9742-8db1db7934de`
- Failed error code: `CODEX_DEMO_FORCED_FAILURE`
- Fallback TaskRun: `9662bb80-70dc-4d47-b82d-4ea1c9effb89`
- Adapter: `scripted_mock`
- Final state: `completed`
- Diff artifact: `8007fd66-6f6b-4e9d-b61f-abf946cc9a08`
- Preview: `38b3e7c9-2ec6-4fb0-ad7f-f4fc142f6b64`
- Preview URL: `http://127.0.0.1:62136`
- Preview health: `healthy`
- Deployment: `fd5ca6bb-ae1c-4ce3-b0f2-dfd50e04eb3f`
- Provider/status: `mock`, `ready`

Follow-up path passed in the same real-agent session:

- Request: `把按钮文案改成 Sign in`
- Follow-up task: `81aeff37-608c-4708-a8c1-284e73b6ba2d`
- Follow-up TaskRun: `62c9ff50-7772-4000-9fe5-77a6596d7f92`
- Adapter: `claude_code`
- Final state: `completed`
- Diff artifact: `a76d098b-f16c-4823-ac40-22062515edf0`
- Preview: `b850d9c8-5e3f-4862-96aa-6cd0cb5942fa`
- Preview URL: `http://127.0.0.1:62341`
- Preview health: `healthy`

Browser automation caveat: this audit opened the audited session URL, but full
automated browser-button clicking was blocked because Playwright is not
installed and Chrome AppleScript control hit a macOS Apple Events permission
prompt. The audit therefore verifies the browser-facing API execution path and
records the browser-click automation gap honestly.

## P0 Baseline

P0 is complete and the judge-demoable path remains fallback-based:

```text
forced Codex failure -> ScriptedMockAdapter fallback -> real diff -> healthy Vite preview -> mock deploy card
```

Preserve this path when making P1 changes.

## P1 Status

### P1-10 Frozen Demo Baseline

P1 is frozen as a stable local demo baseline.

Frozen path:

```text
real Codex Direct Start -> diff card -> Start preview -> preview iframe -> Create deploy card
```

The acceptance checklist lives in `docs/p1-acceptance-checklist.md`.

Frozen baseline evidence is the P1-9 clean-start rehearsal:

- Session: `666fa20b-6f54-4342-b844-39594b903da3`
- TaskRun: `b1882cda-47f6-4035-b12d-ba3d72d67939`
- Diff artifact: `c832b249-c2c3-444c-ac97-6b3e811e5c70`
- Preview: `b363eb09-7251-4b8e-a5b4-3c59775b58b7`
- Deployment: `d97e447a-c8d0-41b7-95f8-e40008d83eb0`
- Provider/status: `mock`, `ready`

Fallback path remains available:

```text
forced Codex failure -> ScriptedMockAdapter fallback -> real diff -> healthy Vite preview -> mock deploy card
```

### P1-6 Verified

P1-6 verified:

- HTTP Direct Start
- Real Codex file mutation
- Diff artifact generation

Verified path:

```text
HTTP Direct Start -> real Codex file mutation -> diff artifact
```

### P1-7 Verified Through Backend APIs

P1-7 verified through backend APIs:

- Real Codex Direct Start
- Real diff artifact
- Healthy Vite preview
- Mock deploy

Verified path:

```text
real Codex Direct Start -> real diff artifact -> healthy Vite preview -> mock deploy
```

P1-7 evidence:

- TaskRun: `fa23fb4a-6506-4b0e-a608-3197356d0628`
- Diff artifact: `782e16f4-36b5-46f3-86cf-42c3fb6119e9`
- Preview: `877daf34-cabe-4ddf-8726-94677ba18831`
- Preview URL: `http://127.0.0.1:53089`
- Deployment: `9ba427d9-1ea8-454a-8890-e243075fcec7`
- Provider/status: `mock`, `ready`

### P1-8 Verified Through Browser UI

P1-8 verified the post-diff artifact path through browser UI interaction:

- Real Codex Direct Start run remained visible in the UI.
- Persisted real diff artifact rendered as a diff card.
- Preview was started from the UI.
- Healthy Vite preview opened in the right-side iframe panel.
- Mock deploy card was created from the UI.
- Diff, preview, and deploy cards remained visible after reload.

Verified path:

```text
real Codex Direct Start -> diff card -> Start preview -> preview iframe -> Create deploy card
```

P1-8 evidence:

- TaskRun: `fa23fb4a-6506-4b0e-a608-3197356d0628`
- Diff artifact: `782e16f4-36b5-46f3-86cf-42c3fb6119e9`
- UI-created preview: `810324d7-2ba9-47e6-b676-7391e87cb131`
- UI-created preview URL: `http://127.0.0.1:64067`
- UI-created deployment: `58c7812c-31f8-49ee-8b08-28d38264cd87`
- Provider/status: `mock`, `ready`

### P1-9 Clean-Start Demo Rehearsal

P1-9 verified the browser UI demo path from a clean server start:

- Backend started with `pnpm dev:api`.
- Frontend started with `pnpm dev:web`.
- A new session was created from the UI.
- The fixed demo request was sent from the UI.
- Direct UI Start invoked a real Codex TaskRun.
- Real Codex completed and produced a real diff artifact.
- Preview was started from the UI and opened in the right-side iframe panel.
- Mock deploy card was created from the UI.
- Diff, preview, and deploy cards remained visible after reload.

Verified path:

```text
clean start -> real Codex Direct Start -> diff card -> Start preview -> preview iframe -> Create deploy card
```

P1-9 evidence:

- Session: `666fa20b-6f54-4342-b844-39594b903da3`
- Task: `c90396af-1b9f-42f4-a6dd-9daa4f3913f6`
- TaskRun: `b1882cda-47f6-4035-b12d-ba3d72d67939`
- Base ref: `ad9136f91fe9776c33e839359a2203d64fbbf322`
- Head ref: `ad9136f91fe9776c33e839359a2203d64fbbf322+worktree`
- Diff: `8a0155a6-b865-4cee-987e-82d773b9f20e`
- Diff artifact: `c832b249-c2c3-444c-ac97-6b3e811e5c70`
- Changed file: `apps/demo/src/App.tsx`
- Diff stats: 1 file changed, 14 additions, 4 deletions
- Preview: `b363eb09-7251-4b8e-a5b4-3c59775b58b7`
- Preview artifact: `f93ebc25-b8c7-47e9-ac11-aeee777c604e`
- Preview URL: `http://127.0.0.1:51763`
- Deployment: `d97e447a-c8d0-41b7-95f8-e40008d83eb0`
- Deployment artifact: `d85e9bcf-9b92-4c3c-958a-352f855e59a9`
- Provider/status: `mock`, `ready`

### P1-11 Clean-State and Fallback Rehearsal

P1-11 closed the main P1 demo-readiness gaps from a non-destructive clean
state rehearsal.

Backup/reset method:

- Moved the active SQLite database to
  `/tmp/agenthub-p1-11-backup-20260517-095901/agenthub.sqlite3.before-p1-11`.
- Recorded the pre-rehearsal Git worktree registry and directory inventory at:
  - `/tmp/agenthub-p1-11-backup-20260517-095901/worktree-list-before.txt`
  - `/tmp/agenthub-p1-11-backup-20260517-095901/worktree-dirs-before.txt`
- Left existing `.worktrees` checkouts in place to avoid disturbing Git's
  registered worktree metadata.
- Reinitialized a clean SQLite database with `pnpm db:init`.
- Created fresh session-level worktrees from the clean DB during the rehearsal.

Restore note: stop the dev servers first, back up the current
`apps/api/data/agenthub.sqlite3` if it needs to be preserved, then move
`/tmp/agenthub-p1-11-backup-20260517-095901/agenthub.sqlite3.before-p1-11`
back to `apps/api/data/agenthub.sqlite3`.

Clean-state direct Codex rehearsal passed:

```text
clean SQLite -> fresh session worktree -> real Codex Direct Start -> real diff -> healthy Vite preview -> mock deploy card
```

Clean-state evidence:

- Session: `72668a90-74a0-45c6-a0c4-98e8cfa54c27`
- Session worktree:
  `/Users/luotianhang/Desktop/agenthub/.worktrees/0474f8b8-499e-4117-afab-c780bd562446/72668a90-74a0-45c6-a0c4-98e8cfa54c27`
- Task: `7e0a4e97-1b80-404d-bcab-4616418627e3`
- TaskRun: `4c92132f-3c89-47cc-b8a4-3f1395825c39`
- Adapter: `codex`
- Final TaskRun state: `completed`
- Error code/message: none
- Base ref: `abdcd88e200ce8c39f50ed38f244d40cb52295bb`
- Head ref: `abdcd88e200ce8c39f50ed38f244d40cb52295bb+worktree`
- Diff: `bb45131e-42f8-47d7-88eb-c8126d694b0a`
- Diff artifact: `243ce682-748b-42ad-9354-dd8eed1f3e67`
- Changed file: `apps/demo/src/App.tsx`
- Diff stats: 1 file changed, 15 additions, 4 deletions
- Preview: `a30d07e2-470c-4614-a864-c21ac0b52363`
- Preview artifact: `4b3475ad-0d1f-4980-ab80-18abb50492fd`
- Preview URL: `http://127.0.0.1:58634`
- Preview health/status: `healthy`, `ready`
- Deployment: `448b7d91-5064-43c2-a849-3e89634e14bd`
- Deployment artifact: `717d28cc-eb3e-47cb-9950-cee1985ea798`
- Provider/environment/status: `mock`, `preview`, `ready`

Manual forced-failure fallback rehearsal passed:

```text
forced Codex failure -> ScriptedMockAdapter fallback -> real diff -> healthy Vite preview -> mock deploy card
```

Fallback evidence:

- Session: `695287ed-2967-4360-8520-a5fdc1be46e3`
- Session worktree:
  `/Users/luotianhang/Desktop/agenthub/.worktrees/0474f8b8-499e-4117-afab-c780bd562446/695287ed-2967-4360-8520-a5fdc1be46e3`
- Task: `1a790664-c817-42eb-a953-d7c0f11cccb0`
- Failed Codex TaskRun: `1b50d047-0c08-4ff2-a4d7-12412b36f786`
- Failed run error code: `CODEX_DEMO_FORCED_FAILURE`
- Fallback TaskRun: `c35d52f5-bf27-4656-aee1-b0321eb2bd96`
- Fallback adapter: `scripted_mock`
- Final fallback TaskRun state: `completed`
- Diff: `8a8f05bf-6559-44f4-bafc-fb87881c4750`
- Diff artifact: `91b6c898-bf2b-4c0c-b44b-f6a236a72ef0`
- Changed file: `apps/demo/src/App.tsx`
- Diff stats: 1 file changed, 11 additions, 4 deletions
- Preview: `e1be7c11-1cc7-42f9-8441-62c7eb0a1b92`
- Preview artifact: `4ed1465f-f887-4680-b9a1-6893e593468d`
- Preview URL: `http://127.0.0.1:59152`
- Preview health/status: `healthy`, `ready`
- Deployment: `cb8c7f95-42f7-4213-8273-4201500bf8b3`
- Deployment artifact: `43e15df7-5fb4-4711-85b6-94c485b0b4cb`
- Provider/environment/status: `mock`, `preview`, `ready`

After reload, the failed Codex run, fallback run, diff, preview, and deploy
card all remained visible in the browser UI.

### P1 Final Freeze Review

The final freeze review confirmed:

- P1-11 is committed at `faca556`.
- No tag currently points at P1-11 HEAD.
- README, demo script, project state, change log, and P1 checklist align on the
  P1 direct Codex path and the fallback-based P0 path.
- Natural-language second-change orchestration remains a caveat.
- Approval card UI is outside the frozen P1 judge path.
- Production deploy remains out of scope.
- A locale-specific development hydration warning around session date formatting
  was observed during P1-11, but did not block the clean-state or fallback
  rehearsal.

## P2 Status

### P2-1 Locale Hydration Warning Fixed

P2-1 replaced runtime-locale timestamp rendering in the workspace shell and
preview card with deterministic compact formatting. Manual reload verification
confirmed the previous locale-specific hydration overlay did not appear.

### P2-2 Approval Card UI/Rehearsal Verified

P2-2 exposed the existing P0 approval request payload on waiting TaskRuns,
added approve/deny endpoints, and rendered a compact approval card in the task
card run controls.

Verified approval rehearsal state:

- Session: `67421999-3b16-44c4-ade3-98cb31331549`
- Approved TaskRun: `5653e8f9-0057-478f-913c-ac25b4484216`
- Denial rehearsal TaskRun: `54bde1de-b9f7-4f2b-9357-98d51b3675c7`
- Approval types rendered: `product_confirmation`, `security_approval`

Manual browser verification confirmed the `product_confirmation` approval card
rendered and the Approve action moved the run from `waiting_approval` to
`queued`. The `security_approval` card rendered as well; denial behavior is
covered by backend/API tests and frontend button wiring tests.

### P2-3 Natural-Language Second-Change Orchestration Verified

P2-3 added deterministic follow-up planning for simple UI text-change requests
inside an existing session. Supported demo-safe examples include:

- `change the primary button text to Sign in`
- `把按钮文案改成 Sign in`
- `把标题改成 Welcome back`

Verified path:

```text
initial plan -> fallback run -> first diff/preview -> natural-language follow-up -> follow-up frontend task -> fallback run -> second diff/preview
```

P2-3 rehearsal evidence:

- Session: `d65fc331-39f2-432b-9828-89723b9f3c32`
- Session worktree:
  `/Users/luotianhang/Desktop/agenthub/.worktrees/0474f8b8-499e-4117-afab-c780bd562446/d65fc331-39f2-432b-9828-89723b9f3c32`
- Initial frontend task: `3f7f6f65-9f72-4add-ab0a-c9a944dc3b23`
- Initial fallback TaskRun: `607ad185-8eb2-4158-8219-e124880e68a7`
- Initial diff artifact: `c83c21d5-dad8-4d56-b0b8-cf1bc9de2bc3`
- Initial preview: `511ee0ca-e0dc-4054-8775-e487e81f7303`
- Initial preview health: `healthy`
- Follow-up request: `把按钮文案改成 Sign in`
- Follow-up task: `3ce6aa3d-97bf-4e16-b85a-33676e62bef2`
- Follow-up task title: `Change primary button text to Sign in`
- Follow-up task target: `primary_action_button_text`
- Follow-up task target text: `Sign in`
- Follow-up fallback TaskRun: `7a4f5763-ebbe-4d51-a207-b36b1fff7091`
- Follow-up diff artifact: `f1ca4318-0b41-48a8-9b27-acb957448734`
- Follow-up preview: `551aa58f-ab73-49f3-96c2-e6db8994bdd6`
- Follow-up preview health: `healthy`
- Total tasks after follow-up: 4

The follow-up run reused the same session worktree and produced a second diff
artifact for `apps/demo/src/App.tsx`. The preview refresh after the second
change was verified through the backend preview API returning a healthy preview.

Known P2-3 limits:

- Execution rehearsal used the `ScriptedMockAdapter` fallback path, not real
  Codex, to avoid quota dependency during this task.
- Browser iframe refresh after the second change was not separately rehearsed.
- Broad arbitrary natural-language code editing remains out of scope; P2-3 is
  intentionally limited to deterministic button/title text changes.

### P2-4 Browser Preview Iframe Refresh Verified

P2-4 verified the remaining second-change preview gap through browser UI
interaction. No product code changes were required.

Verified path:

```text
browser UI initial task -> ScriptedMockAdapter fallback -> first diff -> Start preview -> iframe at first preview URL -> natural-language follow-up -> ScriptedMockAdapter fallback -> second diff -> Start preview -> iframe refreshed to second preview URL
```

P2-4 browser rehearsal evidence:

- Session: `cb653482-c31a-48da-a8ee-31ed8cd367e3`
- Session worktree:
  `/Users/luotianhang/Desktop/agenthub/.worktrees/0474f8b8-499e-4117-afab-c780bd562446/cb653482-c31a-48da-a8ee-31ed8cd367e3`
- Initial frontend task: `5f2c26c2-6511-4b8f-b359-b9de5c9e5a50`
- Initial fallback TaskRun: `cfeff131-8cbf-4bcc-95b9-1aa84dbf5130`
- Initial diff artifact: `737085ee-7b73-4715-8303-df64b3a14132`
- Initial preview: `c077ba2d-7bd4-4c49-8e0c-313e2ecd641c`
- Initial preview URL: `http://127.0.0.1:61087`
- Initial preview health: `healthy`
- Follow-up request: `把按钮文案改成 Sign in`
- Follow-up task: `0f9ff26c-8216-4489-b71a-3628c1a7ab7a`
- Follow-up fallback TaskRun: `f8d78651-5347-43de-8553-12b29c8c3647`
- Follow-up diff artifact: `b48b3b33-feb2-4313-805d-89811a5cb51c`
- Follow-up preview: `44ea9495-04b5-419a-ba64-0701eaa83ec8`
- Follow-up preview URL: `http://127.0.0.1:61292`
- Follow-up preview health: `healthy`

The right-side preview panel changed from the initial iframe URL
`http://127.0.0.1:61087` to the follow-up iframe URL
`http://127.0.0.1:61292`. The in-app browser cannot inspect cross-origin iframe
DOM directly, so the visible panel refresh was verified by screenshot and the
follow-up preview content was verified by opening `http://127.0.0.1:61292` as a
top-level page, where the DOM and screenshot showed the `Sign in` button.

Known P2-4 limits:

- Real Codex was not used for the P2-4 execution portion; the rehearsal used
  the reliable forced-failure plus `ScriptedMockAdapter` fallback path.
- Browser verification confirmed the iframe URL and visible panel refresh, but
  direct DOM inspection inside the cross-origin iframe is not supported by the
  current in-app browser runtime.

### P2-5 GitHub Actions CI Added

P2-5 added a minimal GitHub Actions workflow for pull requests and pushes. The
workflow mirrors the repeated local validation path:

```text
pnpm install --frozen-lockfile -> Python .venv API dependency install -> pnpm check -> pnpm test -> git diff --check
```

CI uses:

- Node.js 22
- pnpm 10.33.4, matching `package.json`
- Python 3.11
- the existing repo scripts, including the `.venv/bin/python`-based API check
  and test wrappers

No app code, test behavior, deployment, Docker, or production release workflow
was added.

### Minimal Claude Code Adapter Added

The backend now includes a minimal `ClaudeCodeAdapter` runtime option behind the
existing adapter contract. It is a sibling of `CodexAdapter`, uses subprocess
`cwd` for session worktree isolation, and maps Claude Code `stream-json` stdout
into normalized AgentHub events.

Current verified state:

- Fake-runner tests cover command construction, incremental stream-json event
  parsing, persisted `TaskRunEvent` sequence ordering, missing CLI, auth
  required, usage limit, parse error, startup timeout, and interruption
  normalization. P2-7 added coverage for real Claude `stream_event` text-delta
  mapping and thinking-delta filtering.
- `adapterType: claude_code` is supported by backend adapter dispatch.
- Guardrails allow the bounded `claude --print --output-format stream-json`
  command family so it can be evaluated through the same command policy path as
  the Codex CLI.

Current limitations:

- P2-7 has run one explicitly approved real Claude Code mutation smoke. Broader
  prompts, browser UI wiring, auth failure text, and usage-limit text remain
  unverified.
- `ScriptedMockAdapter` remains the reliability fallback, and the P1 real Codex
  path remains unchanged.

### P2-7 Real Claude Code Smoke Verified

P2-7 ran a bounded real Claude Code adapter smoke in a detached disposable
session worktree:

```text
ClaudeCodeAdapter -> real Claude CLI -> stream-json events -> file mutation -> completed TaskRun -> diff artifact
```

Disposable worktree:

```text
/Users/luotianhang/Desktop/agenthub/.worktrees/claude-smoke-96d46af7-dc74-4d71-a062-c9be42cd1332
```

The first attempt found a local adapter bug before mutation:

- Failed TaskRun: `c66f1f86-2407-487a-b18f-cf01abd3a7f3`
- Error code: `CLAUDE_CODE_EXIT_ERROR`
- Error message:
  `Error: When using --print, --output-format=stream-json requires --verbose`

The adapter command was updated to include `--verbose`, and the second bounded
smoke succeeded:

- Session: `4cf32311-1a9b-4eda-9ec3-ab0d010691fc`
- Task: `a5557a9a-99de-4962-9d25-86ed548ea7ca`
- TaskRun: `095ae634-c188-4ffc-a502-53a500d20e14`
- AdapterRun: `claude-code-94cc6074-f15d-4290-b050-c2383363f44d`
- Final state: `completed`
- Base ref: `0066dea6c7f6a235cb2c2e0361624a1116d66dad`
- Head ref: `0066dea6c7f6a235cb2c2e0361624a1116d66dad+worktree`
- Diff artifact: `95bb1d0b-12a3-4a0e-be3e-c07cf1bf79d4`
- Diff: `9f69bc39-6b32-42ca-8a86-cf9fbfa62343`
- Changed file: `apps/demo/src/App.tsx`
- Diff stats: 1 file changed, 1 addition, 1 deletion

The direct git diff in the disposable worktree shows only the primary button
text changed from `Continue` to `Claude smoke`.

Known P2-7 limits:

- This was a direct backend smoke, not a full browser UI flow.
- Only one tiny mutation instruction was verified.
- Claude `stream-json` includes verbose low-level `stream_event` records; the
  adapter now maps text deltas and filters thinking deltas, but broader stream
  event shapes remain unverified.
- Auth failure and usage-limit real outputs are still unverified.

### P2-8 Claude Code Direct-Start Selection Added

P2-8 added a minimal environment-based adapter selection path for normal demo
execution. Direct Start still uses the assigned agent's configured adapter by
default, but setting:

```bash
AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code
```

causes frontend/backend coding tasks whose seeded adapter is `codex` to create
new TaskRuns with `adapterType: claude_code`. Explicit adapter selections still
win, so forced Codex failure, retry history, and retry-with-ScriptedMockAdapter
fallback keep their existing behavior. Non-code agents, including the
`scripted_mock` QA path, are not changed by the env var.

Verified state:

- Service tests cover default Claude selection for frontend tasks.
- Service tests cover explicit Codex preserving its requested adapter.
- Service tests cover ScriptedMockAdapter preserving non-code fallback behavior.
- Service tests cover invalid env values failing loudly.

Known P2-8 limits:

- No new real Claude mutation was run for P2-8; P2-7 remains the real Claude
  smoke evidence.
- This is an env/config switch, not a provider marketplace or UI selector.

### P2-9 Claude Default Adapter Mode Documented

P2-9 documented how to start the API with Claude Code as the default coding
adapter:

```bash
AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code pnpm dev:api
```

Minimal Direct Start verification used an in-memory API rehearsal, not a real
Claude execution. With the env var set, `POST /tasks/{task_id}/runs` created a
queued TaskRun with `adapterType: claude_code`.

Evidence:

- Session: `1c662ede-d0be-4349-8c86-20f49be6fb53`
- Task: `c28cda5b-67c7-44a8-bd2b-e43ebbc64217`
- TaskRun: `a1c191ea-1414-4746-95ca-d6c51b36b4f8`
- Adapter type: `claude_code`
- State: `queued`
- Queued event payload: `{"adapterType":"claude_code","state":"queued"}`

Known P2-9 limits:

- No real Claude mutation was run for P2-9.
- Full browser UI Claude-default execution through diff/preview/deploy remains
  unrehearsed.
- P2-7 remains the real Claude mutation and diff artifact evidence.

### P2 Final Freeze Review

P2 final freeze review confirmed the documentation is aligned on the current
P2 baseline:

- P2 stabilization work is complete through P2-9.
- P2 validation remains green with `pnpm check`, `pnpm test`, and
  `git diff --check`.
- The P1 real Codex demo path and fallback-based P0 demo path remain preserved.
- Claude Code default mode is documented with
  `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code`.
- P2 caveats remain visible:
  - full browser UI Claude-default execution through diff/preview/deploy is
    unrehearsed
  - real Claude auth-failure and usage-limit outputs remain partially
    unverified
  - broad arbitrary natural-language editing remains out of scope
  - production deploy remains out of scope

No app code, adapter code, backend API behavior, frontend behavior, or tests
changed during the P2 final freeze review.
