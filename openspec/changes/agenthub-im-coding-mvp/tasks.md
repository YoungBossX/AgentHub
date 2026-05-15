## 1. Week 1 - Foundation, Demo Repo, and Feasibility

- [x] 1.1 Scaffold fixed-stack frontend and backend applications.
  - Objective: Establish the Next.js App Router product UI and FastAPI backend baseline.
  - Scope: TypeScript, Tailwind CSS, shadcn/ui setup, Python FastAPI app, Pydantic schemas, SQLModel setup, SQLite local database configuration.
  - Affected modules: frontend app shell, backend app, database config, developer scripts.
  - Acceptance criteria: Frontend and backend start locally; frontend can call a backend health endpoint; SQLite is initialized through SQLModel.
  - Test or validation method: Run local dev commands and health check; verify database file and initial schema creation.
  - Explicit non-goals: No production deployment, no auth provider integration, no Postgres requirement, no Alembic requirement unless already available.

- [x] 1.2 Add AGENTS.md with P0 implementation guardrails.
  - Objective: Give future coding agents a local instruction file that preserves the MVP scope and safety rules.
  - Scope: Fixed stack, Vite React demo app boundary, session-level worktree rule, local Codex CLI rule, no P0 Docker/WebSocket/marketplaces/multi-user/external IM, protected paths, command allowlist, demo success criteria.
  - Affected modules: repo root documentation, future agent workflow.
  - Acceptance criteria: AGENTS.md exists and clearly states the P0/P1/P2 boundaries and implementation constraints.
  - Test or validation method: Manual review against this OpenSpec design and non-goals.
  - Explicit non-goals: No implementation code, no broad process handbook, no enterprise policy document.

- [x] 1.3 Implement P0 SQLModel schema and seed records.
  - Objective: Persist only the required P0 entities plus TaskRunEvent as the sole support entity.
  - Scope: User, Workspace, Session, Message, Agent, Task, TaskRun, TaskRunEvent, Artifact, Diff, Preview, Deployment models; TaskRun `baseRef`/`headRef`; Preview command/process/status fields; seed one demo user, workspace, and enabled orchestrator/frontend/backend/qa agents.
  - Affected modules: backend models, schema init, seed script, repository layer.
  - Acceptance criteria: All required fields from the specs exist; TaskRunEvent is present; no unrelated P0 domain entities are introduced; seeded agents and workspace are queryable.
  - Test or validation method: Run schema init and a model/repository smoke test that creates a session, message, task, task run, task run event, and artifact.
  - Explicit non-goals: No enterprise RBAC, multi-tenant admin, audit backend, billing, provider marketplace schema, or Alembic migration workflow unless already available.

- [x] 1.4 Add Vite React demo repo and setup-time dependency install path.
  - Objective: Provide the fixed agent-modified demo app for the 5-minute demo.
  - Scope: Vite React app, deterministic demo files for login page and button text changes, setup script that installs dependencies, workspace seed pointing at the demo root.
  - Affected modules: demo repo assets, setup scripts, seed config, README draft.
  - Acceptance criteria: Demo app starts locally after setup; `node_modules` exists only from setup-time install; scripted fallback has known files to mutate.
  - Test or validation method: Run setup command, run `pnpm dev --host 127.0.0.1 --port <port>` manually, verify baseline page loads.
  - Explicit non-goals: No Next.js demo app, no generic multi-framework preview runner, no dependency installation during agent execution.

- [x] 1.5 Run Codex CLI feasibility spike inside a session worktree.
  - Objective: Confirm P0 CodexAdapter can use local CLI invocation inside a git worktree.
  - Scope: Manual or scripted spike for creating a session-level worktree, invoking Codex CLI with a small instruction, observing process behavior, authentication assumptions, stdout/stderr, exit codes, interruption feasibility, output shape, and failure modes.
  - Affected modules: adapter design notes, worktree service assumptions, AGENTS.md or docs/adapter-notes.md.
  - Acceptance criteria: The discovered Codex CLI invocation shape is documented before task 2.4 starts; documentation includes exact command shape, working directory assumptions, required authentication or login state, stdout/stderr behavior, exit code behavior, interrupt behavior, known failure modes, and fallback trigger conditions; documentation is stored in AGENTS.md or docs/adapter-notes.md.
  - Test or validation method: Run a disposable worktree experiment and record command, cwd, expected output/events, and error mapping notes.
  - Explicit non-goals: No Codex API/cloud wrapper, no production adapter hardening, no second real adapter.

- [x] 1.6 Build workspace/session UI/API with session-level worktree creation.
  - Objective: Let the user create and switch between at least three sessions, each with a distinct worktree.
  - Scope: Workspace read endpoint, session CRUD endpoints, deterministic session worktree creation, session list UI, selected session state, `lastMessageAt` updates.
  - Affected modules: frontend session sidebar, backend workspace/session APIs, worktree service, persistence layer.
  - Acceptance criteria: User can create three sessions and switch between them; each session has a unique worktree path; TaskRuns in a session can reuse that path.
  - Test or validation method: API tests for session creation and unique worktree paths; manual UI validation with three sessions.
  - Explicit non-goals: No task-run-level worktree strategy in P0, no multi-user presence, no sharing, no external IM import.

- [x] 1.7 Build IM-style chat stream, persisted messages, and SSE replay foundation.
  - Objective: Render session chat and create the backend event path for recoverable state updates.
  - Scope: Message create/list APIs, markdown display, sender rendering, SSE endpoint, TaskRunEvent append/query APIs, sequence handling.
  - Affected modules: frontend chat view, backend message APIs, TaskRunEvent repository, SSE event service.
  - Acceptance criteria: Messages persist across reload; TaskRunEvents can be appended and queried by sequence; frontend can subscribe to SSE.
  - Test or validation method: Backend tests for message and TaskRunEvent persistence; manual UI validation by sending a message and reloading.
  - Explicit non-goals: No WebSocket, typing indicators, multiplayer presence, external chat integration, or event bus infrastructure.

- [x] 1.8 Implement @mention parsing and simple orchestrator planning.
  - Objective: Route P0 mentions and create 2-4 visible tasks for the demo request.
  - Scope: Mention parser for `@orchestrator`, `@frontend`, `@backend`, `@qa`; deterministic planning template; role-agent assignment; task cards; simple serial dependencies and at most one parallel group.
  - Affected modules: backend chat command parser, orchestrator service, Agent/Task repositories, frontend task cards.
  - Acceptance criteria: `@orchestrator build a login page for the demo app` creates 2-4 tasks with assigned role agents and visible states.
  - Test or validation method: Unit tests for mention parsing and orchestrator planning; manual chat validation.
  - Explicit non-goals: No arbitrary DAG builder, LangGraph/CrewAI dependency, recursive agent tree, autonomous team, provider marketplace discovery.

## 2. Week 2 - Execution, Events, Diff, Controls, and Preview Skeleton

- [x] 2.1 Implement adapter interface, AdapterCapabilities, and event persistence.
  - Objective: Provide the shared adapter contract and guarantee events are persisted before SSE delivery.
  - Scope: `getCapabilities`, `createRun`, `streamEvents`, `interrupt`, `approve`, `collectArtifacts`, `cleanup`; AdapterCapabilities model; normalized event mapper; TaskRunEvent persistence before emit.
  - Affected modules: backend adapter layer, TaskRunEvent service, SSE event service, orchestrator service.
  - Acceptance criteria: Both P0 adapters expose capabilities; normalized events create TaskRunEvent records; SSE can deliver persisted events.
  - Test or validation method: Unit tests with fake adapter events and sequence assertions.
  - Explicit non-goals: No ClaudeCodeAdapter, HumanAgentAdapter, WebSocket, provider marketplace, or external event bus.

- [x] 2.2 Implement permission guardrails and ApprovalRequestPayload.
  - Objective: Enforce P0 command, path, network, and approval rules.
  - Scope: Command allowlist, protected paths including `node_modules`, network-off default, `ApprovalRequestPayload`, approval card event, Task/TaskRun `waiting_approval` state, approve/deny endpoints.
  - Affected modules: backend guardrail service, adapter service, approval UI, TaskRun state handling.
  - Acceptance criteria: Risky actions emit approval payloads; pending approvals put TaskRun in `waiting_approval`; non-allowlisted commands and protected paths are blocked or require approval.
  - Test or validation method: Unit tests for command/path policy and approval payloads; manual approval continuation validation.
  - Explicit non-goals: No enterprise RBAC, policy admin console, arbitrary shell, full host access, unbounded background processes, or unreviewed deploy.

- [x] 2.3 Implement ScriptedMockAdapter real mutation fallback.
  - Objective: Provide a stable fallback adapter that modifies the Vite React demo repo for real.
  - Scope: Controlled scripts for login page and button text changes, realistic progress events, success/failure/interruption/approval simulation, worktree-scoped file mutations, guardrail compliance.
  - Affected modules: backend adapter layer, demo scripts, SSE event service, guardrail service.
  - Acceptance criteria: ScriptedMockAdapter can complete the login page demo and create real file changes; it does not access external network or bypass allowlists.
  - Test or validation method: Integration test running scripted fallback and verifying changed files through Git CLI; manual failure recovery demo.
  - Explicit non-goals: No fake-only message responses, no arbitrary shell, no external provider calls.

- [x] 2.4 Implement CodexAdapter local CLI happy path and normalized errors.
  - Objective: Add the P0 real coding adapter using local CLI invocation.
  - Scope: Read the Codex CLI feasibility note from AGENTS.md or docs/adapter-notes.md, then implement Codex CLI process start inside Session worktree, instruction passing, event adaptation, interruption attempt, artifact collection hook, error mapping to TaskRun fields.
  - Affected modules: backend adapter layer, TaskRun service, TaskRunEvent service, guardrail integration.
  - Acceptance criteria: At least one task can execute through CodexAdapter local CLI and produce real file modifications; failures create normalized error code/message and allow retry.
  - Test or validation method: Local integration test or manual run against the Vite React demo repo; forced failure validates fallback path.
  - Explicit non-goals: No Codex API/cloud wrapper, no ClaudeCodeAdapter, no HumanAgentAdapter, no complex provider configuration.

- [x] 2.5 Implement TaskRun lifecycle, interrupt, retry, and retry-with-fallback.
  - Objective: Make execution controllable from chat while preserving run history.
  - Scope: Updated TaskRun states, run creation, state transitions, interrupt endpoint/UI, retry endpoint/UI, retry-with-ScriptedMockAdapter path, prior run visibility.
  - Affected modules: backend task run service, orchestrator service, frontend task controls, SSE event stream.
  - Acceptance criteria: User can interrupt a running task; user can retry failed or interrupted tasks; retry creates a new TaskRun without overwriting previous history; fallback can be selected after Codex failure.
  - Test or validation method: Backend state transition tests; manual interrupt/retry/fallback validation in UI.
  - Explicit non-goals: No deep recursive team control, arbitrary DAG re-planning UI, long-running background agent scheduler.

- [x] 2.6 Implement real git diff collection and storage.
  - Objective: Turn real session worktree changes into Diff artifacts.
  - Scope: TaskRun `baseRef`/`headRef`, `git diff -p`, changed files, stats, optional `git apply --check`, `node_modules` exclusion, Artifact and Diff persistence, `artifact.diff.ready` events.
  - Affected modules: backend diff service, Artifact/Diff repositories, adapter artifact collection, worktree service.
  - Acceptance criteria: The system stores patch text, changed files JSON, stats JSON, and refs after Codex or scripted changes; `node_modules` is not diffed.
  - Test or validation method: Integration test modifies demo repo file and verifies stored diff matches Git CLI output.
  - Explicit non-goals: No PR creation, no patch export in P0, no full code review system.

- [x] 2.7 Build diff card with file summary and expandable Monaco inspection.
  - Objective: Let the user inspect real file changes from chat.
  - Scope: Diff card, changed files list, patch summary, expand/collapse behavior, Monaco Diff Editor detail view.
  - Affected modules: frontend artifact card components, backend artifact read APIs.
  - Acceptance criteria: User can see changed files and patch summary; expanding the card shows file-level changes through Monaco.
  - Test or validation method: Component test with sample diff fixture; manual validation after ScriptedMockAdapter run.
  - Explicit non-goals: No full IDE editing, arbitrary file explorer, inline code editing workflow.

- [x] 2.8 Implement preview runner backend skeleton.
  - Objective: Add the backend process and persistence foundation for Vite React preview.
  - Scope: Port allocation, fixed command construction, process start/stop skeleton, health check endpoint, Preview record fields, `artifact.preview.ready` event shape, no dependency install during execution.
  - Affected modules: backend preview service, Preview model/repository, guardrail service, TaskRunEvent service.
  - Acceptance criteria: Backend can start `pnpm dev --host 127.0.0.1 --port <port>` in a session worktree with setup-time dependencies and persist preview status.
  - Test or validation method: Backend integration test or manual invocation against the Vite React demo repo.
  - Explicit non-goals: No preview UI polish in Week 2, no Dockerized preview, no multiple framework runners, no external preview sharing.

## 3. Week 3 - Preview Polish, Deploy Card, Recovery, and Demo QA

- [ ] 3.1 Polish preview card and right-side panel.
  - Objective: Make preview usable and demo-ready in the product UI.
  - Scope: Preview card status, URL, open action, refresh action, last checked time, right-side panel or iframe, second-change refresh behavior.
  - Affected modules: frontend preview card/panel, backend preview read/refresh APIs.
  - Acceptance criteria: User can open the Vite React preview in a right-side panel or iframe; preview reflects a second small change in the same session.
  - Test or validation method: Manual run through login page change and button text change; verify preview health and iframe display.
  - Explicit non-goals: No new preview framework support, no dependency install during agent execution, no external preview sharing.

- [ ] 3.2 Implement basic deploy card with mock fallback.
  - Objective: Complete the demo loop after preview succeeds.
  - Scope: Deployment record creation, deploy card UI, mock deploy mode, optional single Vercel demo deploy if stable, approval gate before real deploy.
  - Affected modules: backend deploy service, frontend deploy card, approval controls.
  - Acceptance criteria: Deploy card appears after preview succeeds; mock Deployment record keeps demo path working when real deploy is unavailable.
  - Test or validation method: Manual preview-to-deploy-card validation; forced real-deploy-unavailable validation.
  - Explicit non-goals: No provider matrix, production deploy platform, full deploy matrix, unreviewed deploy, git push requirement.

- [ ] 3.3 Implement and rehearse failure recovery demo flow.
  - Objective: Prove the demo survives CodexAdapter failure or interruption.
  - Scope: Forced CodexAdapter failure mode, retry UI, retry with ScriptedMockAdapter, real file changes, diff collection, preview, deploy card.
  - Affected modules: adapter layer, retry controls, TaskRun error handling, ScriptedMockAdapter, diff/preview/deploy services.
  - Acceptance criteria: User can click retry after failure or interruption; ScriptedMockAdapter completes with real changed files, diff, preview, and deploy card.
  - Test or validation method: Manual failure recovery rehearsal and integration test for fallback run.
  - Explicit non-goals: No generic provider failover marketplace, no complex autonomous recovery planner.

- [ ] 3.4 Add README and demo script.
  - Objective: Make the MVP runnable and judge-demoable.
  - Scope: Local setup, setup-time dependency install, frontend/backend start commands, database seed, Vite React demo repo setup, success path script, failure recovery script, known P0/P1/P2 boundaries.
  - Affected modules: README, demo script docs, developer scripts.
  - Acceptance criteria: README explains how to run the app and trigger the demo; demo script includes one success path and one failure recovery path.
  - Test or validation method: Fresh local run-through following only the README and demo script.
  - Explicit non-goals: No full production deployment guide, enterprise operations manual, marketplace documentation.

- [ ] 3.5 Final P0 acceptance checklist and scope guard.
  - Objective: Verify all P0 acceptance criteria and prevent late scope expansion.
  - Scope: P0 Acceptance Checklist, demo definition of done, P1/P2 deferrals, visual sanity check for chat/diff/preview/deploy surfaces, event replay sanity check.
  - Affected modules: all P0 modules, README, demo script.
  - Acceptance criteria: Final demo shows requirement -> plan -> agent execution -> diff -> preview -> deploy card; all P0 acceptance criteria are marked pass or documented with a demo-safe fallback.
  - Test or validation method: Run the 5-minute judge script twice: once success path, once failure recovery path.
  - Explicit non-goals: No ClaudeCodeAdapter, HumanAgentAdapter, Docker sandbox, WebSocket, provider marketplace, MCP marketplace, multi-user collaboration, external Feishu/Slack integration, full deploy matrix, arbitrary DAG builder.
