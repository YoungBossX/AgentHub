# AgentHub Final Demo Checklist

Use this checklist before a rehearsal, recording, or review of the final
AgentHub local demo. It is evidence-first: record what actually happened and do
not claim real agent success if the local CLI failed or was not run.

## Demo Boundary

AgentHub is a local single-user Agent Coding Workspace / strong demo MVP. The
final demo target is:

```text
requirement -> plan -> agent execution -> diff -> preview -> mock deploy
```

Out of scope for this demo: multi-user IM collaboration, external Feishu/Slack
or WeChat integration, production deploy, provider marketplace, Docker sandbox,
WebSocket/multiplayer, PR creation, and broad arbitrary natural-language
editing.

## Preflight

| Step | Expected Result | Evidence / Notes |
|---|---|---|
| Stop the API before reset. | No process is holding `apps/api/data/agenthub.sqlite3`. | |
| Run `pnpm demo:reset`. | Existing SQLite DB is backed up, a clean seeded DB is created, `.worktrees` is not deleted. | Backup path: |
| Optional: run `pnpm demo:setup` if demo dependencies may be missing. | Vite React demo dependencies are available before agent execution. | |
| Start backend: `pnpm dev:api`. | API listens at `http://127.0.0.1:8000`. | |
| Optional Claude default: `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code pnpm dev:api`. | Frontend/backend coding TaskRuns default to `claude_code`. | |
| Start frontend: `pnpm dev:web`. | UI listens at `http://127.0.0.1:3000`. | |
| Open `http://127.0.0.1:3000`. | Health card shows API ok and SQLite ready. | |

## Main Real-Agent Path

| Step | Expected Result | Evidence / Notes |
|---|---|---|
| Create or select a fresh session. | Sidebar shows the selected session. | Session ID: |
| Send `@orchestrator build a login page for the demo app`. | Chat shows the user request and an orchestrator plan. | |
| Verify task plan. | 2-4 visible tasks appear; current seeded path normally shows 3 tasks. | Task IDs: |
| Start the frontend implementation task. | Run history shows a new TaskRun and active state. | TaskRun ID: |
| Verify adapter type. | Run shows `claude_code` when Claude default is enabled, or `codex` otherwise. | Adapter: |
| Wait for completion or normalized failure. | Successful run reaches `completed`; failed run remains visible with error code/message. | Final state / error: |
| Verify real file mutation. | Changed file is normally `apps/demo/src/App.tsx`. | Changed file: |
| Verify diff artifact. | Diff chip/card appears with changed files and patch summary. | Diff artifact ID: |
| Expand diff details. | File-level diff inspection is visible. | |
| Start preview. | Preview card appears and eventually reports healthy. | Preview ID: |
| Open preview. | Right-side iframe or panel shows the preview URL. | Preview URL / health: |
| Create mock deploy. | Deploy card appears and is labeled mock-backed. | Deployment ID / provider / status: |
| Refresh page. | Message, plan, run history, diff, preview, and deploy cards remain visible. | |

## Reliable Fallback Path

Use this path when local Codex/Claude is unavailable, unauthenticated,
usage-limited, or too slow.

| Step | Expected Result | Evidence / Notes |
|---|---|---|
| Create or select a session with the fixed plan. | Frontend task card is visible. | Session ID / task ID: |
| Click `Force Codex failure`. | Failed Codex run appears and remains visible. | Failed TaskRun ID: |
| Verify error. | Error code is `CODEX_DEMO_FORCED_FAILURE`. | |
| Click `Retry with ScriptedMockAdapter`. | New fallback TaskRun appears; previous failed run remains visible. | Fallback TaskRun ID: |
| Wait for fallback completion. | Fallback run reaches `completed` and shows `scripted_mock`. | |
| Verify diff artifact. | Diff appears for a real `apps/demo/src/App.tsx` mutation. | Diff artifact ID: |
| Start/open preview. | Preview becomes healthy and opens in iframe/panel. | Preview ID / URL / health: |
| Create mock deploy. | Mock deploy card appears and is persisted. | Deployment ID / provider / status: |

## Follow-Up Change Path

Run this after the first successful real or fallback task in the same session.

| Step | Expected Result | Evidence / Notes |
|---|---|---|
| Send `把按钮文案改成 Sign in`. | A focused follow-up frontend task appears. | Follow-up task ID: |
| Start the follow-up task. | New TaskRun appears without overwriting prior history. | Follow-up TaskRun ID: |
| Verify same-session continuity. | Prior task/run history remains visible. | |
| Verify second diff. | A new diff artifact appears for the follow-up change. | Second diff artifact ID: |
| Refresh preview. | Preview health returns healthy and iframe shows the updated button text. | Preview ID / URL: |

## Evidence Record

Fill this table during rehearsal.

| Field | Value |
|---|---|
| Date/time | |
| Branch / commit | |
| Backend command | |
| Frontend command | |
| Adapter used | |
| Session ID | |
| Task ID | |
| TaskRun ID | |
| Final run state | |
| Error code/message, if any | |
| Changed file | |
| Diff artifact ID | |
| Preview ID | |
| Preview URL / health | |
| Deployment ID | |
| Deployment provider / status | |
| Fallback failed TaskRun ID | |
| Fallback TaskRun ID | |
| Follow-up TaskRun ID | |
| Follow-up diff artifact ID | |

## Troubleshooting

### Port Occupied

- API default: `127.0.0.1:8000`.
- Web default: `127.0.0.1:3000`.
- Preview ports are allocated by the backend.
- Stop stale local processes before retrying. Do not delete DB/worktrees as a
  first response.

### API Not Running

- The health card should show API ok and SQLite ready.
- Start the backend with `pnpm dev:api`.
- If the browser uses `localhost:3000`, the backend CORS config should allow
  both `http://127.0.0.1:3000` and `http://localhost:3000`.

### Reset Refuses While API Is Open

`pnpm demo:reset` intentionally refuses to run while SQLite is open. Stop the
API/dev server and rerun the command. The refusal is a safety feature, not a
failure.

### Claude Auth / Quota / Runtime

- Start backend with
  `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code pnpm dev:api` when using Claude
  as the default coding adapter.
- If Claude fails, record the normalized error and switch to the reliable
  fallback path.
- Do not claim real Claude success unless the run actually completed and
  produced the expected artifact.

### Codex Auth / Quota / Runtime

- Codex runs are local CLI runs inside the session worktree.
- If Codex is unavailable, unauthenticated, usage-limited, or slow, use
  `Force Codex failure` and `Retry with ScriptedMockAdapter`.

### Stale Preview

- `pnpm demo:reset` does not stop running preview or dev-server processes.
- If a preview port is stale or unhealthy, stop stale preview processes and
  create a fresh preview from the current run.
- If preview dependencies are missing, run setup-time install with
  `pnpm demo:setup`; do not install dependencies during agent execution.

### Deploy Card Missing

- Create or refresh a healthy preview first.
- Then click `Create deploy card`.
- The deploy card is mock-backed for the final local demo.

## Final Pass Criteria

- A real-agent path or clearly labeled fallback path reaches diff, healthy
  preview, and mock deploy.
- Failed runs remain visible when demonstrating recovery.
- Follow-up text-change path creates a second task and second diff when used.
- Evidence IDs are recorded.
- Mock deploy is described as mock, not production.
- Remaining caveats are stated plainly.
