## Intent

Build the AgentHub IM coding MVP: a single-user, chat-style multi-agent development platform where users can @ an orchestrator or role agents, watch task state changes, review real git diffs, open a real preview, and see a deploy card inside one demoable workflow.

## Problem

AgentHub must not look like a generic chatbot or a broad enterprise agent platform. The 3-week demo needs to prove the core product claim: coding agents become visible IM collaborators whose work produces verifiable artifacts, not just text.

The Research Brief identifies the same industry pattern: modern coding-agent products are converging on plans, worktree isolation, approval controls, diffs, previews, and deployable artifacts. For this change, the brief is background only; the MVP guardrails, acceptance criteria, and demo script are the controlling constraints.

## Goals

- Deliver a 5-minute demo path from user requirement to plan, agent execution, real file change, git diff, preview, and deploy card.
- Use the fixed stack: Next.js App Router product UI, TypeScript, Tailwind CSS, shadcn/ui, Monaco Diff Editor, FastAPI, Pydantic, SQLModel, SQLite for P0, SSE for realtime, Git CLI for diffs, and Vite React as the agent-modified demo app.
- Support single-user workspace operation with multiple sessions and one isolated git worktree per Session.
- Provide IM-style chat with user, orchestrator, and role-agent messages, including `@orchestrator`, `@frontend`, `@backend`, and `@qa` mention parsing.
- Implement one real coding adapter, `CodexAdapter`, plus a reliable `ScriptedMockAdapter` that modifies the demo repo for real so fallback demos still produce real diffs and previews.
- Keep orchestration simple: 2-4 visible tasks, simple serial dependencies, at most one simple parallel group, visible state changes, retry, interrupt, and result summary.
- Provide basic approval controls for risky actions and a deploy card that can be mock-backed if real deployment is unstable.

## Non-Goals

- No enterprise RBAC, billing, multi-tenant admin, external IM integration, full IDE editor, arbitrary DAG builder, provider marketplace, full deploy matrix, multiplayer presence, complex autonomous agent teams, model reasoning visualization, long-term memory, or complete MCP marketplace.
- No P0 WebSocket implementation; P0 realtime uses SSE only.
- No P0 Docker sandbox requirement; P0 isolation uses git worktrees, command allowlists, and protected paths.
- No generic preview runner; P0 supports one demo stack only.
- No generic deployment platform; P0 shows a basic deploy card and may use a mock deploy card if real deploy is unreliable.

## Scope

P0 includes:
- Single-user workspace, multiple sessions, and session switching.
- IM-style chat stream with user, orchestrator, and role-agent messages.
- Mention parsing for orchestrator and role agents.
- Simple orchestrator state machine and task state display.
- Core data models only: User, Workspace, Session, Message, Agent, Task, TaskRun, TaskRunEvent, Artifact, Diff, Preview, Deployment. `TaskRunEvent` is the only P0 support entity allowed beyond the original core model.
- Adapter lifecycle with `AdapterCapabilities`, local-CLI `CodexAdapter`, and `ScriptedMockAdapter`.
- Worktree isolation, command allowlist, protected paths, and approval gates.
- Real git diff collection using `git diff -p`, changed files, and stats.
- Diff card with changed files, patch summary, and expandable file-level inspection.
- Preview runner and preview card for the Vite React demo app only.
- Interrupt, retry, basic approval UI, deploy card, demo repo, README, and demo script.

P1 may include ClaudeCodeAdapter, HumanAgentAdapter, artifact tabs, simplified approval policy configuration, Docker sandbox, patch export, PR creation, simple cost/duration metrics, WebSocket, Codex API/cloud wrapper, Alembic adoption, and fuller provider configuration. P1 must not block P0.

P2/mock-only includes multi-user collaboration, Slack/Feishu/WeChat integrations, provider marketplace, complete MCP marketplace, background agents, auto-inspection, enterprise permission admin, multi-tenant management, full audit backend, and full-stack one-click deployment.

## MVP Definition

The MVP is complete when a judge can open AgentHub, create or select a workspace, create a session, send `@orchestrator build a login page for the demo app`, see a 2-4 step plan, watch at least one role agent execute, inspect real git diff output from the demo repo, open a preview in the right-side panel or iframe, request a second small change, see updated diff and refreshed preview, and reach a deploy card. If the real adapter fails, retry must be able to complete the demo through `ScriptedMockAdapter` while still creating real file changes.

## Success Criteria

- User can create and switch between at least 3 sessions.
- User can type `@orchestrator build a login page`.
- Orchestrator creates 2-4 visible tasks.
- Task states change visibly in the chat stream.
- At least one task can execute through `CodexAdapter`.
- If `CodexAdapter` fails, `ScriptedMockAdapter` can run a stable fallback flow.
- The fallback flow creates real file changes in the demo repo.
- The system generates a real `git diff` from workspace changes.
- The UI renders changed files and patch summary.
- The user can expand a diff card and inspect file-level changes.
- The system starts a preview URL for the supported demo app.
- The user can open preview inside a right-side panel or iframe.
- The user can interrupt a running task.
- The user can retry a failed or interrupted task.
- Multiple sessions can exist without sharing the same worktree, and multiple TaskRuns in the same session reuse that session worktree.
- A deploy card is shown after preview succeeds.
- The demo path still works when real deploy is unavailable.
- README explains how to run the app and trigger the demo.
- Demo script includes one success path and one failure recovery path.
- The final demo shows requirement -> plan -> agent execution -> diff -> preview -> deploy card.

## What Changes

- Add an IM-first AgentHub product shell and backend contract for P0 coding-agent collaboration.
- Add workspace/session management for a single-user local demo.
- Add chat message flow with orchestrator and role-agent mention parsing.
- Add a minimal orchestrator that creates visible tasks and tracks simple state transitions.
- Add an adapter layer with `CodexAdapter` and `ScriptedMockAdapter`.
- Add session-level worktree isolation, command/path guardrails, and approval controls.
- Add TaskRunEvent persistence for SSE replay, debugging, and adapter traceability.
- Add real git diff collection and diff artifact rendering.
- Add one-stack preview runner, preview card, and basic deploy card.
- Add demo repo, README, and demo script for the 5-minute success and recovery paths.

## Capabilities

### New Capabilities
- `workspace-session`: Single-user workspace setup, session creation/switching, and session-level worktree binding.
- `chat-collaboration`: IM chat stream, message roles, and @mention routing for orchestrator and role agents.
- `agent-adapter`: Minimal adapter lifecycle, AdapterCapabilities, local-CLI `CodexAdapter`, `ScriptedMockAdapter`, unified events, fallback behavior, and permission guardrails.
- `orchestrator`: P0 planning, task assignment, simple dependency handling, state display, retry, interrupt, and result summary.
- `task-run-artifact`: Core task/run/artifact lifecycle, TaskRunEvent persistence, and P0 entity boundaries.
- `worktree-diff`: Git worktree isolation and real diff collection/rendering.
- `preview-deploy`: Vite React preview runner, preview card, and basic deploy card.
- `approval-control`: ApprovalRequestPayload, basic approval UI, and enforcement for deploy, push, protected paths, non-allowlisted commands, destructive edits, and network access.

### Modified Capabilities

## Impact

- Frontend: Next.js App Router UI, chat stream, session navigation, task cards, diff card with Monaco, preview panel/iframe, deploy card, approval controls.
- Backend: FastAPI APIs, SSE event streaming and replay, Pydantic schemas, SQLModel persistence, orchestrator service, adapter service, worktree/diff/preview/deploy services.
- Database: SQLite P0 schema designed to remain Postgres-compatible later.
- Execution: Git CLI session worktree management, command allowlist, protected path checks, Codex local CLI integration, scripted demo mutation runner.
- Demo assets: Vite React demo repo, README, AGENTS.md, and demo script.
