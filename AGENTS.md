# AgentHub P0 Implementation Guardrails

This repo is implementing the OpenSpec change at
`openspec/changes/agenthub-im-coding-mvp`. Treat that change's `proposal.md`,
`design.md`, `tasks.md`, and capability specs as the source of truth. If this
file conflicts with those artifacts, stop and resolve the conflict before
coding.

## Current P0 Stack

- Product UI: Next.js App Router, TypeScript, Tailwind CSS, and shadcn/ui-style
  components in `apps/web`.
- Backend: FastAPI, Pydantic, SQLModel, and SQLite in `apps/api`.
- Realtime: SSE for P0. Do not add WebSocket for P0.
- Demo app boundary: the agent-modified demo app is Vite React only.
- Diff and isolation: Git CLI diffs from one session-level git worktree per
  Session.
- Real adapter path: `CodexAdapter` uses the local Codex CLI inside the assigned
  session worktree.
- Codex CLI feasibility notes live in `docs/adapter-notes.md`; read them before
  implementing `CodexAdapter`.
- Reliability path: `ScriptedMockAdapter` must make real file changes in the
  Vite React demo repo and feed the same diff/preview path.

## P0 Scope

Build only the capabilities needed for the local single-user demo loop:

```text
requirement -> orchestrator plan -> agent execution -> real git diff -> real preview -> deploy card
```

P0 includes single-user workspaces, multiple sessions, IM-style chat, mention
routing for `@orchestrator`, `@frontend`, `@backend`, and `@qa`, simple
orchestrator planning, TaskRunEvent-backed SSE recovery, session-level
worktrees, real git diffs, Vite React preview, basic approvals, retry,
interrupt, `CodexAdapter`, `ScriptedMockAdapter`, and a deploy card that may be
mock-backed.

## Defer P1/P2

Do not add P1 or P2 features while implementing P0 tasks.

P1 examples to defer:
- `ClaudeCodeAdapter`
- `HumanAgentAdapter`
- Docker sandbox
- WebSocket
- PR creation or patch export
- Codex API/cloud task wrapper
- Alembic adoption unless a later task explicitly adds it
- richer provider configuration

P2 or mock-only examples to defer:
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

- SQLite is the P0 database. Do not require Postgres for P0.
- The P0 schema is limited to User, Workspace, Session, Message, Agent, Task,
  TaskRun, TaskRunEvent, Artifact, Diff, Preview, and Deployment.
- `TaskRunEvent` is the only P0 support entity beyond the core model.
- Each Session gets exactly one persisted worktree path.
- Multiple TaskRuns in the same Session reuse that Session worktree.
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

P0 execution must use explicit commands only. Keep commands scoped to the repo,
the backend app, the frontend app, or the assigned session worktree.

Currently allowed project commands:

```bash
pnpm check
pnpm test
pnpm db:init
pnpm dev:api
pnpm dev:web
pnpm demo:setup
pnpm demo:dev
```

Expected P0 runtime command families:

- Git read/worktree/diff commands needed for session worktrees and artifacts,
  such as `git rev-parse`, `git worktree`, `git diff`, `git status`, and
  optional `git apply --check`.
- Vite React preview command:
  `pnpm dev --host 127.0.0.1 --port <port>`.
- Local Codex CLI invocation for `CodexAdapter`, only inside
  `Session.worktreePath`.
- Controlled `ScriptedMockAdapter` scripts, only inside the assigned session
  worktree and demo app boundary.

Anything outside the allowlist must be blocked or routed through the approval
flow required by the OpenSpec design. Network access is off by default for agent
execution unless a later P0 approval rule explicitly allows it.

## Future Codex Task Rules

- Implement exactly one OpenSpec task at a time.
- Do not proceed to the next task unless the user asks.
- Read the relevant OpenSpec artifacts before changing files.
- Keep changes minimal and tied to the current task's acceptance criteria.
- Do not add P1/P2 features while completing P0 work.
- Do not add auth provider integration, Postgres requirement, Alembic workflow,
  Docker sandbox, WebSocket, provider marketplace, multiplayer collaboration,
  external IM integrations, or full deploy matrix unless a future task explicitly
  changes scope.
- Run relevant verification commands after each task.
- Mark the task checkbox complete only after verification.

## Current Project Commands

Use these commands from the repo root:

```bash
pnpm check
pnpm test
pnpm db:init
pnpm dev:api
pnpm dev:web
pnpm demo:setup
pnpm demo:dev
```

The current scaffold has:

- `apps/web`: Next.js App Router UI that calls the backend health endpoint.
- `apps/api`: FastAPI app with `/health` and SQLModel-backed SQLite
  initialization.
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

## Definition of Done for P0 Tasks

A P0 task is done only when:

- its implementation matches the specific task in
  `openspec/changes/agenthub-im-coding-mvp/tasks.md`
- it stays within the P0/P1/P2 boundaries above
- relevant tests, checks, or manual smoke commands have been run
- any database initialization or generated runtime artifacts are verified when
  the task touches persistence
- the task's OpenSpec checkbox is updated
- no next task has been started without a user request
