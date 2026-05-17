# AgentHub Frontend Design Brief For Gemini

**Date:** 2026-05-17

This brief documents the current AgentHub frontend so Gemini can design a better
UI without inventing unsupported backend behavior. It is a design handoff, not a
redesign spec or implementation plan.

## Product Positioning

AgentHub is an IM-style coding-agent collaboration product. It should feel like
a coding-focused group chat where human requirements become visible agent work,
not like a generic chatbot and not like a full IDE clone.

The core demo loop is:

```text
requirement -> orchestrator plan -> agent execution -> real diff -> preview -> mock deploy
```

The product should make that loop legible. The most important user feeling is:
"I sent a request into a coding-agent room, watched the team plan and execute,
then inspected the resulting app change."

## Current Verified P1 Capabilities

These capabilities are documented as verified in `README.md`,
`docs/demo-script.md`, `docs/project-state.md`, and
`docs/p1-acceptance-checklist.md`:

- Real Codex Direct Start can produce a file mutation and a real git diff.
- Real Codex Direct Start can continue to a healthy Vite preview and a mock
  deploy card.
- The forced-failure fallback path works through `ScriptedMockAdapter`.
- The clean-state rehearsal passed from clean SQLite through fresh session
  worktree, real diff, healthy preview, and mock deploy.
- After reload, persisted messages, tasks, failed runs, fallback runs, diff
  cards, preview cards, and deploy cards remain visible.

The verified direct path is:

```text
real Codex Direct Start -> diff card -> Start preview -> preview iframe -> Create deploy card
```

The reliability fallback path remains:

```text
forced Codex failure -> ScriptedMockAdapter fallback -> real diff -> healthy Vite preview -> mock deploy card
```

## Current UI Surfaces

The current frontend is in `apps/web` and is intentionally small.

- **Top page shell:** `apps/web/src/app/page.tsx` fetches backend health, the demo
  workspace, and sessions, then renders `WorkspaceShell` plus `HealthCard`.
- **Session sidebar:** `WorkspaceShell` shows workspace metadata, `New session`,
  the session list, session status, last message time, and worktree path.
- **Chat stream:** `WorkspaceShell` shows user, system, orchestrator, and agent
  messages as chat-style bubbles.
- **Message composer:** `WorkspaceShell` has a single text input and `Send`
  button. The placeholder is `@orchestrator build a login page`.
- **Orchestrator plan:** The backend writes an orchestrator plan message and
  tasks after a supported mention request. The UI displays the plan as chat
  content plus task cards.
- **Task cards:** `TaskCardList` renders each task with step number, assigned
  role, title, status, dependencies, run history, and run controls.
- **TaskRun history:** `TaskCardList` shows compact rows like
  `Run 1 · codex · completed`, with error code when present.
- **Run controls:** Task cards expose `Start run`, `Force Codex failure`,
  `Interrupt`, `Retry`, `Retry with ScriptedMockAdapter`, and `Start preview`
  depending on the latest run state.
- **Diff card:** `DiffCard` shows changed files, additions/deletions, base/head
  refs, and an expandable Monaco diff view parsed from stored unified diff text.
- **Preview card:** `PreviewCard` shows preview title, URL, health, status, port,
  last checked time, optional status reason, and actions for open, refresh, mock
  deploy creation, and stop.
- **Right-side preview panel:** `PreviewPanel` renders a right-side or stacked
  iframe panel for the selected Vite React preview.
- **Deploy card:** `DeployCard` shows persisted mock deployment provider,
  environment, status, commit/ref, URL, and deploy log URI.
- **Backend health card:** `HealthCard` shows FastAPI, SQLite, and backend URL
  status.
- **Approval UI:** No dedicated approval card UI is present in the current P1
  judge path. The task card state list knows about `waiting_approval`, and the
  backend adapter model has approval event concepts, but visual approval
  handling was not exercised in the frozen P1 demo.

## Main User Flows

### Success Path

1. Create or select a session.
2. Send:

   ```text
   @orchestrator build a login page for the demo app
   ```

3. See the user message, orchestrator plan, and 3 planned tasks.
4. Click `Start run` on the frontend implementation task.
5. Watch the run move through visible states and eventually complete.
6. Inspect the diff card and expand the Monaco diff when useful.
7. Click `Start preview`.
8. Open the preview in the right-side iframe panel.
9. Click `Create deploy card`.
10. See the persisted mock deploy card.

### Fallback Path

1. Start from a selected session with planned tasks.
2. Click `Force Codex failure`.
3. Confirm the failed Codex run remains visible in run history with
   `CODEX_DEMO_FORCED_FAILURE`.
4. Click `Retry with ScriptedMockAdapter`.
5. Confirm a separate fallback run completes.
6. Continue through diff, preview, right-side iframe, and mock deploy.

### Reload And Recovery Path

The frontend refetches persisted messages and tasks for the selected session.
Task cards also refetch diffs, previews, and deployments for each TaskRun.
After reload, the verified P1 state shows the chat, tasks, runs, diff, preview,
and deploy artifacts remain visible.

## Current Frontend Architecture

### Routes And Pages

- `apps/web/src/app/layout.tsx` defines the root layout and metadata.
- `apps/web/src/app/page.tsx` is the only product route. It is a server
  component that fetches:
  - `GET /health`
  - `GET /workspaces/demo`
  - `GET /workspaces/{workspace_id}/sessions`

### Main Components

- `WorkspaceShell`: stateful client shell for sessions, chat, task loading, SSE
  refresh, run actions, artifact actions, and selected preview state.
- `TaskCardList`: task cards, run summaries, run controls, and per-run artifact
  fetching.
- `DiffCard`: persisted diff summary and expandable Monaco diff inspection.
- `PreviewCard`: preview artifact summary and preview/deploy/stop controls.
- `PreviewPanel`: iframe panel for the selected preview URL.
- `DeployCard`: persisted mock deployment artifact.
- `HealthCard`: backend and SQLite health.
- `Button` and `cn`: local shadcn-style UI/util helpers.

### API Client Functions

`apps/web/src/lib/api.ts` defines the frontend data types and fetch helpers:

- health/workspace/session:
  - `getBackendHealth`
  - `getDemoWorkspace`
  - `listWorkspaceSessions`
  - `createWorkspaceSession`
- messages/tasks/events:
  - `listSessionMessages`
  - `createSessionMessage`
  - `sessionEventsUrl`
  - `listSessionTasks`
- runs:
  - `createTaskRun`
  - `forceCodexFailure`
  - `interruptTaskRun`
  - `retryTaskRun`
  - `retryTaskRunWithFallback`
- artifacts:
  - `listTaskRunDiffs`
  - `startTaskRunPreview`
  - `listTaskRunPreviews`
  - `stopPreview`
  - `createPreviewDeployment`
  - `listTaskRunDeployments`

### Key UI Data Types

The UI currently depends on these TypeScript data surfaces:

- `BackendHealth`
- `Workspace`
- `WorkspaceSession`
- `ChatMessage`
- `SessionTask`
- `TaskRun`
- `DiffArtifact`
- `PreviewArtifact`
- `DeploymentArtifact`

Important displayed fields include session title/status/worktree path, message
sender/content, task title/status/role/dependencies, run adapter/state/error,
diff patch/stats/changed files, preview health/status/port/URL, and deployment
provider/environment/status/URL/log URI.

### Fetching And State Ownership

- `page.tsx` owns initial backend, workspace, and session fetches.
- `WorkspaceShell` owns selected session, messages, tasks, composer text, SSE
  sequence, selected preview, and artifact refresh version.
- `TaskCardList` fetches diff, preview, and deployment artifacts for every
  visible TaskRun when task IDs or refresh keys change.
- `PreviewPanel` does not fetch directly. It receives the selected preview from
  `WorkspaceShell`.

### SSE / EventSource

`WorkspaceShell` opens an `EventSource` using:

```text
GET /sessions/{session_id}/events?after=<lastEventSequence>&stream=true
```

On each event, it updates `lastEventSequence` and refetches session tasks. SSE is
used for persisted `TaskRunEvent` recovery/replay and live task refresh. There
is no WebSocket path.

## Backend And API Constraints Gemini Must Respect

Gemini should design only against existing backend behavior unless a feature is
explicitly labeled future.

Current relevant backend routes in `apps/api/app/main.py`:

- `GET /health`
- `GET /workspaces/demo`
- `GET /workspaces/{workspace_id}/sessions`
- `POST /workspaces/{workspace_id}/sessions`
- `GET /sessions/{session_id}`
- `PATCH /sessions/{session_id}`
- `GET /sessions/{session_id}/messages`
- `POST /sessions/{session_id}/messages`
- `GET /sessions/{session_id}/tasks`
- `POST /tasks/{task_id}/runs`
- `POST /tasks/{task_id}/runs/force-codex-failure`
- `POST /task-runs/{task_run_id}/interrupt`
- `POST /task-runs/{task_run_id}/retry`
- `POST /task-runs/{task_run_id}/retry-with-fallback`
- `POST /task-runs/{task_run_id}/diff`
- `GET /task-runs/{task_run_id}/diffs`
- `POST /task-runs/{task_run_id}/preview`
- `GET /task-runs/{task_run_id}/previews`
- `POST /previews/{preview_id}/stop`
- `POST /previews/{preview_id}/deploy`
- `GET /task-runs/{task_run_id}/deployments`
- `GET /sessions/{session_id}/events`

Respect these constraints:

- Do not invent new backend features.
- Use existing APIs only unless a proposed element is explicitly marked future.
- Preview and deploy are user-triggered actions today.
- Mock deploy is acceptable and expected.
- Do not imply production deploy exists.
- Do not add or design around a provider marketplace.
- Do not add multi-user collaboration.
- Do not design WebSocket behavior.
- Do not design a full IDE editor. Diff inspection is allowed; full file editing
  is not part of the current product.
- Do not assume arbitrary repository previews. P1 preview is Vite React only.
- Do not assume Docker sandboxing, PR creation, patch export, external IM
  integrations, or human/Claude adapters.
- The second natural-language change path is documented as a caveat, not a
  polished verified flow.

## Design Problems In The Current UI

These are observed weaknesses in the current implementation, not new feature
requests:

- **Visual hierarchy:** The page has many same-weight bordered cards. It is hard
  to tell what the primary demo action is at a glance.
- **Crowded task cards:** Task status, role, dependencies, run controls, run
  history, and artifacts are close together, so the execution story can feel
  compressed.
- **Unclear run history:** Run rows are very compact and do not clearly explain
  which run is current, failed, fallback, interrupted, or completed.
- **Weak diff/preview/deploy relationship:** Diff, preview, and deploy cards
  appear as separate stacked artifacts, but the UI does not strongly show them
  as one pipeline produced by a TaskRun.
- **Insufficient status clarity:** Raw backend states such as `streaming`,
  `collecting_diff`, `healthy`, `ready`, and adapter names are visible but not
  grouped into a clear user-facing status model.
- **Weak right-side panel design:** The preview panel works, but the empty state
  and selected-preview state feel utilitarian. The relation between preview card
  actions and the iframe could be clearer.
- **Unclear primary demo action:** After the plan appears, `Start run`, `Force
  Codex failure`, and later `Start preview` compete visually. The ideal demo
  next step is not strongly guided.
- **Session sidebar density:** Worktree paths are useful for verification but
  dominate the sidebar visually.
- **Artifact loading visibility:** Artifact fetches happen in `TaskCardList`,
  but loading and empty states are minimal.
- **Hydration warning caveat:** A non-blocking locale-specific development
  hydration warning around session date formatting was observed during P1-11.
  It did not block clean-state rehearsal, fallback rehearsal, preview iframe, or
  mock deploy card.

## Design Requirements For Gemini

Gemini should produce a UI design package that includes:

- Information architecture for an IM-style coding-agent workspace.
- Page layout that keeps group chat primary while making agent work and
  artifacts easy to scan.
- Component hierarchy for session sidebar, chat, plan, task execution, artifact
  timeline, and preview panel.
- Visual style direction that feels coding-focused, calm, and operational.
- Task card design with clearer role, status, dependencies, current action, and
  progress.
- Run history design that distinguishes direct Codex runs, forced failures,
  fallback retries, current run, failed run, completed run, and retry actions.
- Diff artifact design that summarizes files/stats and supports expandable code
  inspection without becoming a full editor.
- Preview artifact design that clearly connects preview health, iframe opening,
  refresh, stop, and deploy-card creation.
- Deploy artifact design that is honest about `mock` provider and `preview`
  environment.
- Right-side panel design for selected preview, empty state, refresh, close, and
  responsive behavior.
- Empty, loading, disabled, failed, interrupted, completed, and recovered states.
- Responsive behavior for desktop three-column layout, tablet stacked layout,
  and mobile constrained chat/task/artifact views.
- Implementation notes suitable for Tailwind CSS and local shadcn-style
  components.
- A list of what should remain unchanged.

What should remain unchanged:

- The existing backend API contract unless Codex explicitly implements a tiny
  missing wiring later.
- The demo request: `@orchestrator build a login page for the demo app`.
- The P1 direct Codex path.
- The forced-failure `ScriptedMockAdapter` fallback path.
- The Vite React-only preview boundary.
- The mock deploy truthfulness.
- SSE as the realtime/recovery mechanism.
- The absence of production deploy, provider marketplace, WebSocket, full IDE,
  external IM integrations, and multi-user collaboration.

## Implementation Constraints For Codex

If Codex later implements Gemini's design:

- Prefer frontend-only changes.
- Avoid backend changes unless a tiny missing API wiring is found and explicitly
  justified.
- Preserve the P1 demo paths:
  - real Codex Direct Start -> diff -> preview -> mock deploy
  - forced Codex failure -> ScriptedMockAdapter fallback -> diff -> preview ->
    mock deploy
- Preserve existing tests.
- Add or update frontend tests if behavior changes.
- Keep changes scoped to `apps/web` unless the task explicitly says otherwise.
- Keep docs honest about unverified behavior.
- Do not commit or push unless explicitly instructed.
