# AgentHub Demo Baseline Guardrails

This repo has completed the original P0 OpenSpec change at
`openspec/changes/agenthub-im-coding-mvp`, hardened the final local demo through
`openspec/changes/agenthub-final-demo-hardening`, and is evolving the local
workspace through `openspec/changes/agenthub-p5-platform-evolution`. Treat those
OpenSpec artifacts, `docs/project-state.md`, and `docs/change-log.md` as the
current baseline. If this file conflicts with those artifacts, stop and resolve
the conflict before coding.

## Project-Wide Mandatory Rules

- Keep changes minimal and task-scoped.
- Do not implement unrelated features.
- Do not fake real Codex success.
- Do not claim unverified behavior.
- Preserve the fallback-based P0 demo path.
- Do not remove or regress the current adapters: `CodexAdapter`,
  `ClaudeCodeAdapter`, or `ScriptedMockAdapter`.
- Do not add new adapters, `HumanAgentAdapter`, Docker sandbox, WebSocket,
  provider marketplace, PR creation, or production deployment unless explicitly
  asked through a focused OpenSpec task.
- Do not silently install dependencies.
- If code or engineering files change, update `docs/change-log.md`.
- Do not commit or push unless explicitly instructed.
- Runtime exception for `agenthub-parallel-dag-execution` phase 4: the server
  may commit validated demo patches in its newly allocated integration worktree
  and fast-forward the assigned clean canonical Session worktree. This does not
  authorize committing/pushing the AgentHub development checkout or letting an
  adapter modify Git control files.
- Focused user-edit exception under `agenthub-bounded-code-editing`: explicit
  workbench apply may write bounded, version-checked text changes in the assigned
  canonical Session target with execution exclusion and durable user provenance.
  It does not authorize adapters to bypass their controls, write protected paths,
  create a HumanAgentAdapter, commit/push, or treat user edits as Agent success.
  Existing P23 document artifact editing remains database-only.

## Current Demo Stack

- Product UI: Next.js App Router, TypeScript, Tailwind CSS, and shadcn/ui-style
  components in `apps/web`.
- Backend: FastAPI, Pydantic, SQLModel, and SQLite in `apps/api`.
- Realtime: SSE. Do not add WebSocket for the final demo baseline.
- Demo app boundary: the agent-modified demo app is Vite React only.
- Diff and isolation: one canonical session-level git worktree per Session;
  explicitly isolated demo writes may use server-owned TaskRun execution worktrees
  under `agenthub-parallel-dag-execution` phase 3.
- Real adapter paths:
  - `CodexAdapter` uses the local Codex CLI inside the assigned session
    worktree.
  - `ClaudeCodeAdapter` is a current runtime option, selected for coding agents
    with `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code`.
- Reliability path: `ScriptedMockAdapter` must make real file changes in the
  Vite React demo repo and feed the same diff/preview path.

## Current Baseline Scope

AgentHub is currently a local single-user Agent Coding Workspace / strong demo
MVP, not a full Feishu/WeChat-style multi-user IM collaboration platform. The
verified local demo loop is:

```text
requirement -> orchestrator plan -> agent execution -> real git diff -> real preview -> deploy card
```

The baseline includes single-user workspaces, multiple sessions, IM-style chat,
mention routing for `@orchestrator`, `@frontend`, `@backend`, and `@qa`, simple
orchestrator planning, Agent contact UI, local Direct chat / Group workflow
visual modes, session execution ledger, non-blocking review artifacts,
multi-agent execution trace UI, artifact message cards, TaskRunEvent-backed SSE
recovery, session-level worktrees, real git diffs, Vite React preview, basic
approvals, retry, interrupt, `CodexAdapter`, `ClaudeCodeAdapter`,
`ScriptedMockAdapter`, and a mock-backed deploy card.

## Defer Platform Scope

Do not add broad platform features while implementing demo-hardening tasks.

Deferred examples:
- `HumanAgentAdapter`
- Docker sandbox
- WebSocket
- PR creation or patch export
- Codex API/cloud task wrapper
- Alembic adoption unless a later task explicitly adds it
- richer provider configuration
- multi-user collaboration
- Slack, Feishu, WeChat, or other external IM integrations
- provider marketplace
- complete MCP marketplace
- background agents
- auto-inspection
- enterprise permission admin, RBAC, billing, audit backend, or multi-tenant
  management
- full deploy matrix or one-click production deployment
- arbitrary DAG builder or broad agent-team platform features

## Data and Runtime Boundaries

- Focused exception under `agenthub-alembic-migrations`: fixed Alembic revisions
  own SQLite schema transitions. Developer-only `pnpm db:status` and
  `pnpm db:migrate --backup-dir <new-external-directory>` do not expand Agent
  commands. Existing databases require offline exclusive ownership, verified
  WAL-aware backup and isolated rehearsal; API startup only initializes empty
  databases or validates current schemas. Never drop records, blindly stamp,
  rewrite existing seed settings or automatically overwrite a database restore.

- Focused exception under `agenthub-local-data-maintenance`: the offline operator
  CLI may read the primary checkout's SQLite/Git metadata and registered managed
  worktrees to create a new external local snapshot. Restore never overwrites an
  existing checkout; rehearsal repairs only copied Git pointers. Explicit cleanup
  may quarantine only revalidated fixed developer caches. It may not delete
  Sessions, modify user project paths, run saved hooks/code, install dependencies
  or expand adapter permissions. The API holds a shared database lifetime lease;
  maintenance requires exclusive ownership and a stopped runtime.

- Focused exception under `agenthub-controlled-mcp`: `WorkspaceMcpConnection`
  stores the built-in read-only document connection and Agent defaults in SQLite.
  Compatible Codex runs may reach only the server-owned loopback MCP gateway with
  execution-bound ephemeral credentials and a fixed tool allowlist. The gateway
  reads bounded README/docs in the assigned target and explicitly related
  built-in backend documentation in that same worktree; no arbitrary remote URLs,
  processes, host paths, write tools or general adapter network scope are added.

- Focused exception under `agenthub-skills`: `WorkspaceSkill` stores bounded
  workspace instruction packages and default Agent bindings in SQLite. Frozen
  content lives in existing message/run evidence; Skills grant no new tools,
  filesystem scope, network access or script execution permissions.

- SQLite remains the local database; do not require Postgres. The original P0
  core is extended only by focused OpenSpec changes already recorded in
  `docs/project-state.md` (queue/locks/jobs, targets, memory, profiles/runtime,
  Skills/MCP, attachments and artifact versions). Current table authority is
  `apps/api/app/models.py`; this is not permission to add unrelated entities.
- Focused exception under `agenthub-message-attachments`: `MessageAttachment`
  stores bounded Session-owned upload bytes, extraction metadata and immutable
  Message bindings in SQLite. Attachment input does not grant new tool/write
  scope. Codex may receive only server-created, per-call temporary image files
  through validated `--image` inputs; never add their directory to sandbox access.
- Each Session gets exactly one persisted canonical worktree path.
- By default, TaskRuns reuse that Session worktree and writes remain serial.
- Focused exception: `executionMode=isolated_write` for built-in demo writes may
  allocate a validated, per-TaskRun worktree/branch, persisted in TaskRun metrics.
  Keep the canonical Session path unchanged; do not preview/deploy unmerged outputs.
- Different Sessions must not share a worktree.
- Preview supports only Vite React and runs:

```bash
pnpm dev --host 127.0.0.1 --port <port>
```

- Demo app dependencies are installed during setup only. Do not run dependency
  installation during agent execution.

## Protected Paths

Adapters, scripts, diff collection, and preview/deploy flows must protect these
paths unless a later explicit approval task defines narrower behavior:

- `.git/`
- `.env`
- `.env.*`
- `secrets/`
- `node_modules/`
- system paths outside the repo or assigned worktree
- host paths not explicitly assigned to the current Session

Do not expose protected host paths to adapters. Do not allow edits to
`node_modules`, and exclude `node_modules` from diff artifacts.

## Command Allowlist

Demo execution must use explicit commands only. Keep commands scoped to the
repo, the backend app, the frontend app, or the assigned session worktree.

Currently allowed project commands:

```bash
pnpm check
pnpm check:demo-api
pnpm test
pnpm db:init
pnpm dev:api
pnpm dev:web
pnpm demo:reset
pnpm demo:setup
pnpm demo:api:dev
pnpm demo:api:test
pnpm demo:dev
```

Expected P0 runtime command families:

- Focused exception under `agenthub-container-validation`: server-owned fixed
  check/test profiles may use the explicitly selected local Docker backend with
  operator-prepared immutable images, bounded snapshots, no network, fixed
  resource budgets and verified ownership cleanup. Native remains the default;
  unavailable Docker never silently falls back. Developer `sandbox:doctor`,
  `sandbox:prepare` and `sandbox:verify` are not Agent commands. This exception
  grants no Docker access to adapters and makes no database or preview changes.

- Focused exception under `agenthub-backend-versioned-validation`: the server may
  invoke its fixed Python syntax/ASGI contract harness with the installed isolated
  interpreter in a disposable copy of built-in `demo-backend`. Never run edited
  target tests/configuration, install dependencies, start a target listener or
  expand adapter permissions. Bind actual check/test evidence to source, policy
  and execution generation. Python audit guards are not an OS security sandbox.

- Focused exception under `agenthub-requirement-validation`: after fixed demo
  build validation the server may run its trusted Playwright harness against
  temporary output for a frozen login/heading/button contract. Use a fresh
  sandboxed browser context, deny external requests/downloads/service workers,
  and use installed browsers only. No arbitrary selectors/scripts from plans,
  authentication, runtime installation, or adapter browser permissions are added.

- Focused exception under `agenthub-versioned-validation`: the server may run
  its fixed TypeScript check, trusted Vite build harness and Node build-output
  smoke tests in a temporary copy of `demo-frontend`, using already installed
  platform dependencies. It must bind receipts to source/policy fingerprints,
  honor execution cancellation/ownership and never execute edited configuration
  or install dependencies. This does not expand adapter command permissions.

- Git read/worktree/diff commands needed for session worktrees and artifacts,
  such as `git rev-parse`, `git worktree`, `git diff`, `git status`, and
  optional `git apply --check`.
- The phase-4 server-only join coordinator may apply target-validated patches
  in a fresh integration worktree, create a local integration commit with hooks
  disabled, and perform a verified `git merge --ff-only` into the clean assigned
  Session worktree. Conflicts must not mutate canonical files; no push or reset.
- Vite React preview command:
  `pnpm dev --host 127.0.0.1 --port <port>`.
- Local Codex CLI invocation for `CodexAdapter`, only inside the validated
  TaskRun worktree (canonical Session path by default).
- Local Claude Code CLI invocation for `ClaudeCodeAdapter`, only inside the validated
  TaskRun worktree (canonical Session path by default).
- Controlled `ScriptedMockAdapter` scripts, only inside the assigned session
  worktree and demo app boundary.

Anything outside the allowlist must be blocked or routed through the approval
flow required by the OpenSpec design. Network access is off by default for
agent execution unless a later focused approval rule explicitly allows it.

## Future Codex Task Rules

- Implement exactly one OpenSpec task at a time.
- Do not proceed to the next task unless the user asks.
- Read the relevant OpenSpec artifacts before changing files.
- Keep changes minimal and tied to the current task's acceptance criteria.
- Do not add broad platform features while completing focused OpenSpec tasks.
- Do not add auth provider integration, Postgres requirement, Alembic workflow,
  Docker sandbox, WebSocket, provider marketplace, multiplayer collaboration,
  external IM integrations, or full deploy matrix unless a future task explicitly
  changes scope.
- Run relevant verification commands after each task.
- Mark the task checkbox complete only after verification.

## Current Project Commands

Use these commands from the repo root:

Local developer startup commands added by `agenthub-local-startup-entrypoint`:
`pnpm doctor:local`, `pnpm dev:local`, and `pnpm test:local`. These commands
do not expand adapter command permissions or install dependencies. Existing
runtime command allowlists above remain unchanged.

```bash
pnpm check
pnpm check:demo-api
pnpm test
pnpm db:init
pnpm dev:api
pnpm dev:web
pnpm demo:reset
pnpm demo:setup
pnpm demo:api:dev
pnpm demo:api:test
pnpm demo:dev
```

The current scaffold has:

- `apps/web`: Next.js App Router UI that calls the backend health endpoint.
- `apps/api`: FastAPI app with `/health` and SQLModel-backed SQLite
  initialization.
- `apps/demo-api`: isolated FastAPI demo backend target for Backend Agent work.
- `apps/demo`: Vite React demo app used for later adapter mutations.
- `scripts`: developer wrappers for API dev, API checks, API tests, and DB init.

## Demo Success Criteria

The completed P0 demo must let a judge:

- open AgentHub locally
- create or select a workspace
- create and switch among at least three sessions
- send `@orchestrator build a login page for the demo app`
- see a 2-4 step plan and visible task states
- watch at least one role agent execute
- inspect real git diff output from the demo repo
- open a Vite React preview in a right-side panel or iframe
- request a second small change in the same Session
- see updated diff and refreshed preview
- interrupt and retry failed or interrupted work
- fall back to `ScriptedMockAdapter` if local Codex CLI execution fails
- reach a backend-created deploy card, mock-backed if necessary

## Definition of Done for Final Demo Tasks

A final demo hardening task is done only when:

- its implementation matches the specific task in the active OpenSpec change
- it stays within the local single-user demo boundaries above
- relevant tests, checks, or manual smoke commands have been run
- any database initialization or generated runtime artifacts are verified when
  the task touches persistence
- the task's OpenSpec checkbox is updated
- no next task has been started without a user request
