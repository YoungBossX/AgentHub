# P0 Acceptance Checklist

Date: 2026-05-16

Change: `openspec/changes/agenthub-im-coding-mvp`

Overall result: judge-demoable through the documented failure-recovery path.
The direct UI `Start run` path is still a caveat: it creates a queued Codex
TaskRun in this checkout but does not execute Codex through artifact collection.
The demo-safe path is `Force Codex failure` -> `Retry with ScriptedMockAdapter`
-> diff -> preview -> mock deploy.

## Result Summary

| Result | Count |
| --- | ---: |
| Pass | 26 |
| Fallback | 4 |
| Fail | 0 |
| Not Tested | 1 |

## Command Results

| Command or step | Result | Evidence |
| --- | --- | --- |
| `pnpm demo:setup` | Pass | Completed with lockfile up to date; no agent execution dependency install was run. |
| `pnpm db:init` | Pass | Printed `Initialized and seeded database at sqlite:///data/agenthub.sqlite3`. |
| `pnpm dev:api` | Pass | Uvicorn started at `http://127.0.0.1:8000`. |
| `pnpm dev:web` | Pass | Next.js started at `http://127.0.0.1:3000`. |
| Manual API/UI rehearsal | Pass | Evidence run `20260516015440` reached three sessions, plan, forced Codex failure, ScriptedMockAdapter fallback, diff, healthy preview, and mock deploy. |
| `POST /task-runs/c5cef51a-2191-40e3-8aac-ed43760fa6a6/interrupt` | Pass | Returned `state: interrupted` and `errorCode: TASK_RUN_INTERRUPTED`. |
| `POST /task-runs/c5cef51a-2191-40e3-8aac-ed43760fa6a6/retry` | Pass | Returned a new queued Codex TaskRun with `retryOfRunId`. |
| Scope search in `apps` | Pass | `rg` found no ClaudeCodeAdapter, HumanAgentAdapter, WebSocket, Docker, provider marketplace, MCP marketplace, external IM, PR creation, or full deploy matrix implementation. |

## Acceptance Table

| ID | Acceptance criterion | Source area | Result | Evidence | Command or manual step used | Notes / follow-up |
| --- | --- | --- | --- | --- | --- | --- |
| P0-01 | User can open AgentHub UI locally. | README, frontend app | Pass | Frontend returned page content containing `AgentHub` and `IM Coding Workspace`. | `pnpm dev:web`; manual fetch of `http://127.0.0.1:3000` | Visual component coverage also exists in web tests. |
| P0-02 | User can create and switch between at least three sessions. | Workspace/session API and UI | Pass | Manual run created sessions `38932d68-...`, `f8e83460-...`, and `d723098a-...`; UI session list renders selectable sessions. | `POST /workspaces/{workspace_id}/sessions` x3; component/API tests | Switching is covered by persisted selected-session routing and API state. |
| P0-03 | Each session has a distinct worktree. | Worktree service | Pass | The three manual session worktree paths were distinct under `.worktrees/98449267-.../`. | Manual API rehearsal; `test_create_three_sessions_persists_unique_worktree_paths` | Added setup dependency symlink support for new session worktrees. |
| P0-04 | User can send `@orchestrator build a login page for the demo app`. | Chat/message API, planner | Pass | Manual message `f36c1c21-...` persisted with the exact content. | `POST /sessions/{session_id}/messages` | Message remained readable after reload through `GET /sessions/{session_id}/messages`. |
| P0-05 | Orchestrator creates 2-4 visible tasks. | Planner, task cards | Pass | Manual run created exactly 3 tasks: plan, build, review. | `GET /sessions/{session_id}/tasks` | Matches P0 deterministic planning template. |
| P0-06 | Task cards show assigned role agents. | Task API and task card UI | Pass | Manual task roles were `orchestrator`, `frontend`, and `qa`; component tests render role labels. | Manual task fetch; `pnpm test:web` | Backend returns `assignedAgentRole`. |
| P0-07 | Task states update visibly in the chat/session surface. | TaskRun lifecycle, task cards, SSE | Pass | Run history showed queued Codex, failed Codex, completed ScriptedMockAdapter, then interrupted/retry states. | Manual rehearsal; interrupt/retry API calls | State visibility is in task cards/run history rather than separate natural-language chat bubbles. |
| P0-08 | TaskRunEvents persist and support SSE recovery/replay. | Events service | Pass | Replay response for the manual session had 33 SSE text lines and included diff, preview, and deploy event types. | `GET /sessions/{session_id}/events?after=0&stream=false` | Events are persisted before SSE delivery by adapter/artifact services. |
| P0-09 | At least one task can execute through CodexAdapter local CLI, if Codex is available and authenticated. | CodexAdapter | Fallback | Adapter command shape and fake-runner tests pass, but current UI `Start run` only created queued Codex run `c5cef51a-...`; no real Codex execution was claimed in this rehearsal. | `POST /tasks/{task_id}/runs`; `pnpm test:api`; `docs/adapter-notes.md` | Demo uses ScriptedMockAdapter fallback. A future small task should wire direct Start to adapter execution before claiming Pass. |
| P0-10 | If CodexAdapter fails or is unavailable, ScriptedMockAdapter can complete the flow. | Failure recovery | Pass | Forced failure run `1d2a71d6-...` failed with `CODEX_DEMO_FORCED_FAILURE`; fallback run `70b2b306-...` completed. | `POST /tasks/{task_id}/runs/force-codex-failure`; `POST /task-runs/{run_id}/retry-with-fallback` | Failed run remained visible in history. |
| P0-11 | Fallback flow modifies real files in the Vite React demo repo. | ScriptedMockAdapter, worktree | Pass | Diff patch included `Welcome back`; changed file was `apps/demo/src/App.tsx`. | Manual fallback run; `GET /task-runs/{run_id}/diffs` | The mutation happened inside the session worktree. |
| P0-12 | Backend collects real git diff output. | Diff service | Pass | Diff artifact stored patch text, changed files, and stats from Git CLI. | `GET /task-runs/{run_id}/diffs`; `tests/test_diffs.py` | Stats: 1 changed file, 11 additions, 4 deletions. |
| P0-13 | UI renders changed files and patch summary. | Diff card UI | Pass | Diff card component tests render `Git diff`, changed file, and summary data. | `pnpm test:web` | Manual API confirmed artifact data is present for the UI to render. |
| P0-14 | User can expand diff details. | Diff card UI | Pass | Frontend tests cover expandable diff details with Monaco Diff Editor fixture. | `pnpm test:web` | Monaco is used only for diff inspection. |
| P0-15 | Preview starts for the Vite React demo app with `pnpm dev --host 127.0.0.1 --port <port>`. | Preview service | Pass | Manual preview `9e4b6c8e-...` stored command `pnpm dev --host 127.0.0.1 --port 53096` and became healthy. | `POST /task-runs/{run_id}/preview` | Fixed session worktree setup dependency links and local preview health probing during this task. |
| P0-16 | Preview runner does not run dependency installation during agent execution. | Preview service, setup docs | Pass | Stored preview command contains only `pnpm dev --host 127.0.0.1 --port <port>`; tests assert `install` is not in preview command. | `pnpm demo:setup`; `pnpm test:api` | Worktrees link already-installed setup dependency dirs; no install command is executed by preview. |
| P0-17 | User can open preview in side panel or iframe. | Preview card/panel UI | Pass | Preview panel component test renders iframe titled `Vite React preview`; manual preview URL was healthy. | `pnpm test:web`; manual preview rehearsal | Live UI page loaded; right-side panel behavior is covered in component tests. |
| P0-18 | User can request or simulate a second small change in the same session. | ScriptedMockAdapter, demo target | Fallback | ScriptedMockAdapter has deterministic button mutation support in tests, but natural-language follow-up orchestration is not wired as a polished UI path. | `tests/test_scripted_mock_adapter.py`; README/demo caveat | Demo can explain the deterministic target; full follow-up UX remains a documented caveat. |
| P0-19 | User can refresh preview state after the second change. | Preview card/service | Fallback | Preview refresh now rechecks backend health and updates stored preview state; second-change UI flow itself remains a caveat. | `GET /task-runs/{run_id}/previews`; `test_listing_preview_refreshes_health_and_emits_ready_event` | Preview refresh is usable for the main fallback flow. |
| P0-20 | User can interrupt a running task, if current flow exposes a running state long enough. | TaskRun lifecycle | Pass | Manual interrupt changed queued run `c5cef51a-...` to `interrupted` with `TASK_RUN_INTERRUPTED`. | `POST /task-runs/{run_id}/interrupt` | Queued is an active P0 state and can be interrupted. |
| P0-21 | User can retry a failed or interrupted task. | TaskRun lifecycle | Pass | Manual retry of interrupted run created new run `cdeb2dc5-...`; fallback retry of failed Codex run created `70b2b306-...`. | `POST /task-runs/{run_id}/retry`; `POST /task-runs/{run_id}/retry-with-fallback` | Retried runs create new rows. |
| P0-22 | Failed or interrupted TaskRuns remain visible and retried runs do not overwrite previous run history. | Task cards, TaskRun persistence | Pass | Reload read showed history containing queued/interrupted Codex, failed Codex, completed scripted fallback, and retry rows as separate records. | `GET /sessions/{session_id}/tasks` after refresh-style reload | Run history is persisted per task. |
| P0-23 | Approval card appears for risky or deploy actions where applicable. | Approval guardrails | Not Tested | Current judge flow uses mock deploy and does not trigger a risky approval card; backend approval payload/state tests pass. | `pnpm test:api`; source review | No approval card UI was exercised in this flow. Do not claim visual approval-card pass. |
| P0-24 | Deploy card appears after preview succeeds. | Deploy service, deploy card UI | Pass | Manual deploy `62cf65a2-...` returned provider `mock`, status `ready`, and persisted URL/log URI. | `POST /previews/{preview_id}/deploy`; `GET /task-runs/{run_id}/deployments` | Deploy card UI has component coverage. |
| P0-25 | Mock deploy keeps the demo working when real deploy is unavailable. | Deploy service | Pass | Mock deploy card used provider `mock` and did not claim a real provider deployment. | Manual deploy rehearsal; `pnpm test:api` | Real deploy providers remain deferred. |
| P0-26 | README explains local setup. | README | Pass | README includes prerequisites, `pnpm install`, Python venv, `pnpm demo:setup`, `pnpm db:init`, and dev commands. | Manual doc review | README also states direct Start caveat. |
| P0-27 | Demo script includes one success path and one failure recovery path. | `docs/demo-script.md` | Pass | Demo script contains main demo path, local Codex caveat, and failure recovery path. | Manual doc review | The success path is reliable through fallback. |
| P0-28 | Final demo can show requirement -> plan -> agent execution -> diff -> preview -> deploy card. | End-to-end demo | Pass | Manual evidence run reached requirement, 3-task plan, forced failure plus fallback execution, diff, healthy preview, and mock deploy. | Manual API/UI rehearsal `20260516015440` | Judge-demoable through documented fallback path. |
| P0-29 | P1/P2 items remain deferred and unimplemented. | Scope guard | Pass | Search in `apps` found no ClaudeCodeAdapter, HumanAgentAdapter, WebSocket, Docker, provider marketplace, MCP marketplace, external IM, PR creation, or full deploy matrix. | `rg` scope search | Docs mention these only as deferred boundaries. |
| P0-30 | Existing checks/tests still pass. | Repo verification | Pass | `pnpm check` passed; `pnpm test` passed with web 21 tests and API 53 tests; `git diff --check` passed. | `pnpm check`; `pnpm test`; `git diff --check` | Verification was run before marking task 3.5 complete. |
| P0-31 | Direct UI `Start run` executes through artifacts. | Known caveat | Fallback | Direct run `c5cef51a-...` was created as queued Codex and did not execute through artifacts. | `POST /tasks/{task_id}/runs` | Do not hide this. The judge demo should use the documented fallback path. |

## Remaining Caveats

- Direct UI `Start run` does not currently execute CodexAdapter through diff,
  preview, and deploy. It creates a queued Codex TaskRun. This is documented as
  a fallback, not a pass.
- Real Codex CLI execution was not claimed during this checklist run. Adapter
  behavior is covered by fake-runner tests and prior CLI notes in
  `docs/adapter-notes.md`.
- Natural-language second-change orchestration is not fully wired. The
  deterministic button mutation target and adapter behavior exist, but the
  polished follow-up UI path remains a fallback caveat.
- Approval card UI was not exercised because the current judge flow uses mock
  deploy and does not require a risky action approval.

## Scope Guard

Confirmed P0 scope remains:

- single-user local demo
- session-level git worktree isolation
- SSE, not WebSocket
- Vite React preview only
- mock deploy allowed
- ScriptedMockAdapter fallback creates real file changes

Confirmed deferred / not implemented in `apps`:

- ClaudeCodeAdapter
- HumanAgentAdapter
- Docker sandbox
- WebSocket
- provider marketplace
- MCP marketplace
- PR creation
- external Feishu, Slack, or WeChat integration
- full deployment matrix
