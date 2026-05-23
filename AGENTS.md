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

## Current Demo Stack

- Product UI: Next.js App Router, TypeScript, Tailwind CSS, and shadcn/ui-style
  components in `apps/web`.
- Backend: FastAPI, Pydantic, SQLModel, and SQLite in `apps/api`.
- Realtime: SSE. Do not add WebSocket for the final demo baseline.
- Demo app boundary: the agent-modified demo app is Vite React only.
- Diff and isolation: Git CLI diffs from one session-level git worktree per
  Session.
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

- SQLite is the demo database. Do not require Postgres for the final demo.
- The demo schema is limited to User, Workspace, Session, Message, Agent, Task,
  TaskRun, TaskRunEvent, Artifact, Diff, Preview, Deployment,
  SessionExecutionLedger, and Review.
- `TaskRunEvent`, `SessionExecutionLedger`, and `Review` are the only support
  entities beyond the core model.
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

- Git read/worktree/diff commands needed for session worktrees and artifacts,
  such as `git rev-parse`, `git worktree`, `git diff`, `git status`, and
  optional `git apply --check`.
- Vite React preview command:
  `pnpm dev --host 127.0.0.1 --port <port>`.
- Local Codex CLI invocation for `CodexAdapter`, only inside
  `Session.worktreePath`.
- Local Claude Code CLI invocation for `ClaudeCodeAdapter`, only inside
  `Session.worktreePath`.
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
