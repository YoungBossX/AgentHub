# AgentHub Project Summary For Interview

## One-Sentence Positioning

AgentHub is a local single-user Agent Coding Workspace / strong demo MVP that
turns an IM-style requirement into visible tasks, real local agent execution,
real Git diffs, a live Vite preview, and a mock deploy card.

It is not a complete multi-user IM collaboration platform.

## Problem It Solves

Coding-agent demos often hide the important parts: what task was planned, which
agent ran, what files changed, whether the result can be previewed, and how a
failure is recovered. AgentHub makes that loop visible and inspectable in one
workspace:

```text
requirement -> plan -> execution -> diff -> preview -> deploy card
```

The goal is to show a judge or reviewer a concrete agent workflow rather than a
chatbot response. The user can see the request, plan, task cards, run history,
adapter type, diff evidence, preview state, and deploy artifact in the same
session.

## Architecture

### Frontend

- Next.js App Router product UI in `apps/web`.
- TypeScript and Tailwind CSS.
- IM-style workspace shell with:
  - session sidebar;
  - chat stream;
  - task cards;
  - run history;
  - artifact area for diff, preview, and deploy cards.

The UI calls the FastAPI backend and uses persisted state rather than pretending
that agent output is only ephemeral frontend state.

### Backend

- FastAPI app in `apps/api`.
- Pydantic and SQLModel.
- SQLite local database.
- SSE backed by persisted `TaskRunEvent` records.
- APIs for workspaces, sessions, messages, tasks, task runs, diffs, previews,
  deployments, and approvals.

### Persistence

The demo database is SQLite at:

```text
apps/api/data/agenthub.sqlite3
```

The P4 reset helper can safely back up and rebuild the seeded demo database:

```bash
pnpm demo:reset
```

It does not delete `.worktrees` or source code.

### Session Worktree Isolation

Each AgentHub Session gets a persisted session-level git worktree under
`.worktrees/`. TaskRuns in the same Session reuse that worktree, which lets the
demo show continuity:

- first request creates the login page;
- follow-up request modifies the same demo app state;
- diffs are collected from the session worktree boundary.

### Adapter Model

AgentHub has three current execution paths:

- `CodexAdapter`: invokes the local Codex CLI inside the session worktree.
- `ClaudeCodeAdapter`: invokes the local Claude Code CLI inside the session
  worktree and can be selected with
  `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code`.
- `ScriptedMockAdapter`: deterministic reliability fallback that still makes
  real file changes in the Vite React demo app.

The adapter contract normalizes events so task runs can persist lifecycle
events, output, failures, and artifact readiness without the UI needing to know
each CLI's native output shape.

### Artifact Pipeline

The artifact pipeline is intentionally concrete:

1. Agent execution mutates files in the session worktree.
2. The backend collects a real Git diff.
3. The diff is stored as an Artifact and Diff record.
4. The preview runner starts Vite React from the session worktree.
5. Preview status and URL are persisted.
6. A backend-created mock Deployment record can be shown as the deploy card.

Mock deploy is clearly labeled as mock-backed. It is not production deployment.

## Core Workflow

The primary demo request is:

```text
@orchestrator build a login page for the demo app
```

The expected flow:

```text
requirement
-> orchestrator plan
-> frontend task run
-> agent execution
-> apps/demo/src/App.tsx mutation
-> real Git diff
-> healthy Vite preview
-> mock deploy card
```

P4 evidence is recorded in `docs/e2e-capability-audit.md`; this summary refers
to that audit rather than duplicating or inventing new IDs.

## Failure Recovery

AgentHub has an explicit resilience path:

```text
forced Codex failure -> ScriptedMockAdapter fallback -> diff -> preview -> mock deploy
```

The failed Codex run remains visible in run history with
`CODEX_DEMO_FORCED_FAILURE`. The fallback run is a new TaskRun and does not
overwrite prior history. Because `ScriptedMockAdapter` modifies real files, the
same diff and preview pipeline still proves the artifact path.

## Follow-Up Change Flow

The follow-up path demonstrates same-session continuity. After the first run,
the user can send:

```text
把按钮文案改成 Sign in
```

AgentHub creates a focused follow-up frontend task. The follow-up run reuses the
same session worktree, produces a second diff, and the preview can be refreshed
to show the updated button text. This is intentionally narrow: deterministic
button and heading text edits are supported for the demo; broad arbitrary
natural-language editing remains out of scope.

## What Is Real

- Real local CLI agent execution has been verified.
- `ClaudeCodeAdapter` can mutate `apps/demo/src/App.tsx`.
- `CodexAdapter` has also been verified in prior P1 rehearsals.
- Git diff collection is real and uses the session worktree.
- Vite React preview is real and runs from the mutated session worktree.
- TaskRun history, TaskRunEvents, diffs, previews, and deployments are
  persisted in SQLite.
- The fallback adapter makes real file changes rather than only returning fake
  UI state.

## What Is Mock

- Deployment is mock-backed for the final local demo.
- The deploy card is backend-created and persisted, but it does not publish to
  a production hosting provider.

## What Is Not Implemented

The following are intentionally outside the current final-demo scope:

- full multi-user IM platform;
- external Feishu, WeChat, Slack, or other chat integrations;
- provider marketplace;
- production deployment;
- Docker sandbox;
- WebSocket/multiplayer transport;
- PR creation or patch export;
- broad arbitrary natural-language editing;
- enterprise approval workflow;
- mobile-first product redesign.

## Design Decisions And Trade-Offs

### Local First

The project optimizes for a repeatable local demo. SQLite, local CLIs, and local
worktrees keep the system inspectable and avoid a fragile cloud dependency
matrix.

### Session-Level Worktrees

One worktree per Session keeps follow-up edits coherent. It is simpler than
task-run-level isolation and is enough to demonstrate continuity, diffs, and
preview refresh.

### Persist Events Before UI Delivery

TaskRunEvents are stored before SSE delivery. That gives the UI a recovery path
after refresh and lets the demo show run history instead of losing the story if
the page reloads.

### Scripted Fallback Is A Product Feature

The fallback path is not a fake screenshot path. It modifies real files and uses
the same artifact pipeline. This makes the demo reliable while preserving the
integrity of the diff and preview proof.

### Mock Deploy Is Honest Scope Control

Production deploy providers would add auth, provider-specific APIs, and
environment risk. The current demo uses a mock deployment card to prove the
artifact and workflow surface without claiming production deployment.

## Interview Talking Points

- "I built AgentHub as a local agent-coding workspace, not just a chat UI."
- "The core value is observability: the user sees requirement, plan, execution,
  diff, preview, and deploy artifact."
- "Adapters normalize different CLI runtimes into one TaskRunEvent stream."
- "The fallback adapter is deterministic but still changes real files, so the
  diff and preview evidence stays meaningful."
- "SQLite and session worktrees were chosen to keep the demo local,
  inspectable, and resettable."
- "The project deliberately defers multi-user IM, provider marketplace,
  production deploy, Docker sandboxing, and broad autonomous editing."
- "The next phase would turn the demo into a platform by adding stronger
  planning, shared memory, manager/worker scheduling, security review, IM
  integrations, plugin ecosystem, and real deploy providers."

## Future Roadmap

The long-term platform roadmap lives in `docs/platform-roadmap.md`. Those
phases are not current three-week tasks. They should become focused OpenSpec
changes before implementation.
