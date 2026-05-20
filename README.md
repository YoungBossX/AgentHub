# AgentHub

AgentHub is a local, single-user Agent Coding Workspace / strong demo MVP. It
uses an IM-style command-center interface, but it is not a full multi-user
Feishu/WeChat-style collaboration platform. The verified demo loop is:

```text
requirement -> orchestrator plan -> agent execution -> real git diff -> real preview -> deploy card
```

The original MVP source is the completed OpenSpec change at
`openspec/changes/agenthub-im-coding-mvp`. Final demo hardening is tracked in
`openspec/changes/agenthub-final-demo-hardening`, with current state recorded in
`AGENTS.md`, `docs/project-state.md`, and `docs/change-log.md`.

## Current Stack

- Product UI: Next.js App Router, TypeScript, Tailwind CSS, and local
  shadcn/ui-style components in `apps/web`.
- Backend: FastAPI, Pydantic, SQLModel, and SQLite in `apps/api`.
- Demo app modified by agents: Vite React only in `apps/demo`.
- Realtime: SSE backed by persisted `TaskRunEvent` records.
- Isolation: one git worktree per AgentHub Session.
- Execution adapters: local-CLI `CodexAdapter`, local-CLI
  `ClaudeCodeAdapter`, and `ScriptedMockAdapter`.
- Artifacts: Git diff cards, Vite React preview cards, and mock deploy cards.

## Prerequisites

- Node.js and pnpm. This repo declares `pnpm@10.33.4` in `package.json`.
- Python 3.9 or newer.
- Git.
- Optional for the Codex real adapter path: the local Codex CLI, logged in and
  available at either `CODEX_CLI_PATH` or the default macOS app path used by
  `apps/api/app/codex_adapter.py`.
- Optional for the Claude Code real adapter path: the local Claude Code CLI,
  logged in and available as `claude` or via `CLAUDE_CODE_CLI_PATH`.

## Setup

Run these commands from the repo root.

Install JavaScript workspace dependencies:

```bash
pnpm install
```

Create and populate the Python virtual environment used by the backend scripts:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r apps/api/requirements.txt
```

Install the Vite React demo app dependencies during setup:

```bash
pnpm demo:setup
```

Agent execution and preview startup must not run dependency installation. The
setup step above is the intended time for creating `node_modules`.

Initialize and seed the local SQLite database:

```bash
pnpm db:init
```

`pnpm db:init` creates the SQLModel tables and seeds:

- one demo user
- one `AgentHub Demo` workspace pointing at `apps/demo`
- enabled orchestrator, frontend, backend, and QA agents

To reseed an existing database without recreating tables:

```bash
pnpm db:seed
```

The default database URL is `sqlite:///data/agenthub.sqlite3`, relative to
`apps/api`.

## Run Locally

Start the backend:

```bash
pnpm dev:api
```

The backend listens on `http://127.0.0.1:8000` by default. Override the port
with `AGENTHUB_API_PORT`.

Start the product UI in a second terminal:

```bash
pnpm dev:web
```

The frontend listens on `http://127.0.0.1:3000` and calls the backend at
`http://127.0.0.1:8000` by default. Override the backend URL for the Next.js app
with `BACKEND_URL`.

Start the demo app manually when you only want to inspect the baseline Vite
React app:

```bash
pnpm demo:dev
```

The repo-level demo command uses port `5173` by default. The fixed preview
command shape is:

```bash
pnpm dev --host 127.0.0.1 --port <port>
```

The backend preview runner executes that command inside the session worktree and
does not install dependencies.

## Verification Commands

Run these from the repo root:

```bash
pnpm check
pnpm test
git diff --check
```

Useful narrower commands:

```bash
pnpm check:web
pnpm check:api
pnpm check:demo
pnpm test:web
pnpm test:api
```

## Product Surfaces

The local UI currently includes:

- session list and `New session` control
- selected-session chat stream
- orchestrator plan message
- task cards with assigned role agents and dependencies
- run history per task
- run controls: `Start run`, `Interrupt`, `Retry`, `Force Codex failure`, and
  `Retry with ScriptedMockAdapter`
- diff card with changed files, patch summary, and expandable Monaco diff
  inspection
- preview card with status, URL, port, refresh/open actions, and a right-side
  iframe panel
- deploy card backed by a persisted mock Deployment record

## Demo Request

Use this fixed request in a selected session:

```text
@orchestrator build a login page for the demo app
```

The current planner creates a 3-step plan:

1. Plan the login page change.
2. Build the Vite React login page.
3. Review the login page demo path.

The deterministic demo mutation targets are in `apps/demo/src/App.tsx`:

- `data-agenthub-target="login-page-slot"`
- `data-agenthub-target="primary-action-button"`

## Demo Script

Use `docs/demo-script.md` for the narrated demo. It includes:

- a main demo path through session creation, planning, task cards, real local
  agent Direct Start execution, diff, preview, and mock deploy
- a failure recovery path showing a failed Codex run preserved in history and a
  successful `ScriptedMockAdapter` retry

Current P4 status: the `Start run` UI dispatches real local agent Direct Start
execution. P1-11 verified a clean SQLite rehearsal through real Codex file
mutation, diff, healthy Vite preview, and mock deploy card. P4-0 verified a
Claude Code default-adapter path, plus fallback and follow-up paths, through the
browser-facing API path. The forced-failure `ScriptedMockAdapter` path remains
the reliability fallback if real local agent execution is unavailable,
unauthenticated, usage-limited, or too slow for the demo window.

To use Claude Code as the default coding adapter for frontend/backend coding
tasks:

```bash
AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code pnpm dev:api
```

## Current Demo Boundaries

The current local demo includes:

- single-user local workspace and sessions
- SSE, not WebSocket
- session-level git worktrees, not Docker sandbox
- Vite React preview only
- SQLite, not Postgres
- local Codex CLI and local Claude Code CLI as real adapter paths
- `ScriptedMockAdapter` as the reliability fallback, with real file changes
- Git CLI diff collection and persisted diff artifacts
- mock-backed deploy card when real deployment is unavailable

Deferred platform items include:

- `HumanAgentAdapter`
- Docker sandbox
- WebSocket
- provider marketplace or MCP marketplace
- PR creation or patch export
- external Feishu, Slack, WeChat, or other IM integrations
- multiplayer collaboration
- enterprise RBAC, billing, or admin policy console
- production deployment matrix or one-click production deploy guide

## P1 Reset Notes

- `pnpm db:init` initializes and seeds the SQLite database.
- Runtime worktrees live under `.worktrees/`.
- Runtime API database files live under `apps/api/data/`.
- Do not delete `.git/`, `.env*`, `node_modules/`, or unrelated user files
  during a demo reset.
- For the P1-11 clean-state rehearsal, the previous SQLite database was moved
  to `/tmp/agenthub-p1-11-backup-20260517-095901/agenthub.sqlite3.before-p1-11`
  before running `pnpm db:init`. Existing `.worktrees` checkouts were left in
  place to avoid disturbing Git's registered worktree metadata.
- To restore that pre-P1-11 database, stop the dev servers first, back up the
  current `apps/api/data/agenthub.sqlite3` if you need to keep it, then move the
  P1-11 backup file back to `apps/api/data/agenthub.sqlite3`.

## Troubleshooting

### Frontend Does Not Start

Run `pnpm install` from the repo root, then `pnpm dev:web`. The web app expects
the backend at `http://127.0.0.1:8000` unless `BACKEND_URL` is set.

### Backend Does Not Start

Create the Python virtual environment and install backend requirements:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r apps/api/requirements.txt
```

Then run `pnpm dev:api`.

### Database Is Missing Or Not Seeded

Run:

```bash
pnpm db:init
```

Refresh the web app. The health card should show the backend as reachable, and
the workspace should be `AgentHub Demo`.

### Real Agent CLI Is Unavailable, Unauthenticated, Or Usage-Limited

Read `docs/adapter-notes.md` for Codex notes and
`docs/claude-code-adapter-notes.md` for Claude Code notes. Use the visible
recovery path: `Force Codex failure`, then `Retry with ScriptedMockAdapter`.

### Preview Port Is Unavailable

The preview runner allocates a port for backend-started previews. For manual
demo-app startup, set a different port:

```bash
AGENTHUB_DEMO_PORT=5174 pnpm demo:dev
```

### Vite Demo Dependencies Are Missing

Run setup-time installation:

```bash
pnpm demo:setup
```

Do not add dependency installation to adapter execution or preview startup.

### Fallback Does Not Produce A Diff

Check that the selected session has a git worktree and that the fallback run
completed. `ScriptedMockAdapter` expects `apps/demo/src/App.tsx` inside the
session worktree and uses the deterministic targets listed above.

### Mock Deploy Card Does Not Appear

Create or refresh a healthy preview first. The mock deploy card is created from
the preview card with `Create deploy card`; it is persisted by the backend and
is not a frontend-only placeholder.

### Locale-Specific Hydration Warning In Dev Console

During P1-11, a non-blocking development hydration warning was observed around
locale-specific session date formatting. It did not block the clean-state
rehearsal, fallback rehearsal, diff cards, preview iframe, or mock deploy card.
