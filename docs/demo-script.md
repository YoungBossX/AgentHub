# AgentHub Demo Script

This script is for the OpenSpec change
`openspec/changes/agenthub-im-coding-mvp`. It describes the local AgentHub demo
as implemented through the completed P0 scope and the P1 direct-Codex
rehearsals.

## Setup Before The Demo

From the repo root:

```bash
pnpm install
python3 -m venv .venv
.venv/bin/python -m pip install -r apps/api/requirements.txt
pnpm demo:setup
pnpm db:init
```

Start the backend:

```bash
pnpm dev:api
```

Start the product UI in another terminal:

```bash
pnpm dev:web
```

Open:

```text
http://127.0.0.1:3000
```

Keep `docs/adapter-notes.md` handy if you plan to demonstrate real local
Codex CLI behavior.

## What To Say Up Front

AgentHub is an IM coding workspace. The point of the demo is not a chatbot
answer. The point is that a chat request becomes visible tasks, task runs,
real file changes, diff artifacts, a live Vite React preview, and a deploy
card.

P0 constraints:

- realtime is SSE, not WebSocket
- isolation is one session-level git worktree, not Docker
- preview supports Vite React only
- deploy can be mock-backed
- `ScriptedMockAdapter` is the reliability fallback and still creates real file
  changes
- dependency installation happens during setup, not during agent execution

## Main Demo Path With Local Codex

Use this path when the local Codex CLI is available, authenticated, and not
usage-limited.

1. Confirm the health card shows the backend URL and a reachable API.
2. In the workspace sidebar, click `New session`.
3. Optionally create two more sessions and switch between them to show that
   each session has its own persisted worktree path.
4. Select the session you want to demo.
5. Send this exact chat message:

   ```text
   @orchestrator build a login page for the demo app
   ```

6. Point out the IM surfaces:
   - the user message remains in the chat stream
   - the orchestrator posts a plan message
   - task cards appear in the selected session
   - each task shows status, assigned role, dependencies, and run history
7. The visible plan should contain three tasks:
   - `Plan the login page change`
   - `Build the Vite React login page`
   - `Review the login page demo path`
8. On the frontend implementation task, click `Start run`.
9. Point out that run history shows a Codex TaskRun and that the task moves
   through active states.
10. Wait for the Codex run to reach `completed`.
11. Verify the diff card appears.
12. Expand the diff card and show:
    - changed file list
    - additions/deletions summary
    - file-level diff inspection through Monaco
13. Click `Start preview`.
14. When the preview card appears, show:
    - status
    - URL
    - port
    - last checked time
15. Click `Open preview`.
16. Point out that the right-side panel or iframe opens the Vite React demo
    from the session worktree.
17. Click `Create deploy card`.
18. Point out the persisted mock deploy card:
    - provider
    - environment
    - status
    - worktree ref or commit field
    - mock URL
    - mock deploy log URI
19. Refresh the page and confirm the diff, preview, and deploy cards remain
    visible.

Expected result: the demo reaches real file changes, Git diff, preview, and a
backend-created mock deploy card.

## Reliable Fallback Demo Path

Use this path if local Codex is unavailable, unauthenticated, usage-limited, or
too slow for the demo window.

1. Follow steps 1-7 from the main demo path.
2. On the frontend implementation task, click `Force Codex failure`.
3. Point out that a failed Codex run remains visible in run history with
   `CODEX_DEMO_FORCED_FAILURE`.
4. Click `Retry with ScriptedMockAdapter`.
5. Wait for the new fallback run to complete.
6. Point out that the successful fallback run is a separate TaskRun and did not
   overwrite the failed Codex run.
7. Continue with the same artifact loop:
   - expand the diff card
   - click `Start preview`
   - click `Open preview`
   - click `Create deploy card`

Expected result: the fallback run still creates real demo-app file changes and
the same diff, preview, and mock deploy cards.

## Success Path With Local Codex

`CodexAdapter` exists and uses the command shape documented in
`docs/adapter-notes.md`:

```bash
codex --ask-for-approval never exec --json --cd <session_worktree_path> --sandbox workspace-write "<instruction>"
```

The adapter has tests for command construction, JSONL stdout parsing, noisy
stderr capture, error mapping, and interruption behavior. P1 rehearsals verified
the browser UI path:

```text
Start run -> real Codex file mutation -> diff card -> preview iframe -> mock deploy card
```

If a real Codex run fails, do not claim success. Show the normalized failure in
run history and switch to the reliable fallback path.

## Failure Recovery Demo Path

Use this path when you want to focus on resilience.

1. Start from a selected session with planned tasks.
2. On the frontend implementation task, click `Force Codex failure`.
3. Confirm the failed run remains visible in run history.
4. Confirm the failed run shows `CODEX_DEMO_FORCED_FAILURE`.
5. Click `Retry with ScriptedMockAdapter`.
6. Confirm a new run appears below the failed run.
7. Confirm the new run reaches `completed`.
8. Confirm a diff card appears.
9. Expand the diff card and show the Vite React file mutation.
10. Click `Start preview`.
11. Open the preview in the right-side panel.
12. Click `Create deploy card`.
13. Confirm the deploy card appears and is mock-backed.

Expected result: the failed Codex run remains visible, the fallback run creates
real changes in the demo app, and the existing artifact actions still produce
diff, preview, and deploy cards.

## Second Small Change Rehearsal

The demo app has a deterministic button target:

```text
data-agenthub-target="primary-action-button"
```

The intended follow-up request is:

```text
make the button text more friendly
```

Current caveat: a polished natural-language follow-up orchestration path is not
documented as complete in this checkout. If a later task wires this into the UI,
use the same session so the TaskRun records a new `baseRef`, the session
worktree keeps prior changes, and the preview can be refreshed from the preview
card.

## Manual API References

These are useful for debugging or rehearsing with browser dev tools. The UI
calls these backend APIs:

- `GET /workspaces/demo`
- `POST /workspaces/{workspace_id}/sessions`
- `GET /workspaces/{workspace_id}/sessions`
- `POST /sessions/{session_id}/messages`
- `GET /sessions/{session_id}/tasks`
- `POST /tasks/{task_id}/runs`
- `POST /tasks/{task_id}/runs/force-codex-failure`
- `POST /task-runs/{task_run_id}/interrupt`
- `POST /task-runs/{task_run_id}/retry`
- `POST /task-runs/{task_run_id}/retry-with-fallback`
- `GET /task-runs/{task_run_id}/diffs`
- `POST /task-runs/{task_run_id}/preview`
- `GET /task-runs/{task_run_id}/previews`
- `POST /previews/{preview_id}/stop`
- `POST /previews/{preview_id}/deploy`
- `GET /task-runs/{task_run_id}/deployments`
- `GET /sessions/{session_id}/events`

## Demo Reset Notes

- `pnpm db:init` initializes and seeds the SQLite database.
- Runtime worktrees live under `.worktrees/`.
- Runtime API database files live under `apps/api/data/`.
- Do not delete `.git/`, `.env*`, `node_modules/`, or unrelated user files
  during a demo reset.

## Troubleshooting During The Demo

- Backend unavailable: confirm `pnpm dev:api` is running and the health card
  points at `http://127.0.0.1:8000`.
- Workspace unavailable: run `pnpm db:init` and refresh.
- No tasks after sending the request: use the exact request
  `@orchestrator build a login page for the demo app` in a selected session.
- Codex unavailable or usage-limited: use `Force Codex failure`, then
  `Retry with ScriptedMockAdapter`.
- No diff after fallback: confirm the fallback run completed and that the
  session worktree contains `apps/demo/src/App.tsx`.
- Preview does not become healthy: confirm demo dependencies were installed
  with `pnpm demo:setup` and that the allocated port is available.
- Deploy card missing: create or refresh a healthy preview first, then click
  `Create deploy card`.
