# AgentHub E2E Capability Audit

## P4-2 Browser E2E Click Rehearsal

**Date:** 2026-05-20

### Summary

P4-2 verified the final-demo loop through browser UI clicks at
`http://127.0.0.1:3000` with the API started as:

```bash
AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code pnpm dev:api
```

The real path was clicked through the UI:

```text
new session -> send requirement -> generated plan -> Start run -> claude_code
-> diff -> Start preview -> preview iframe -> Create mock deploy
```

The fallback path was also clicked through the UI:

```text
new session -> send requirement -> Force Codex failure -> fallback retry
-> scripted_mock -> diff -> Start preview -> preview iframe -> Create mock deploy
```

This rehearsal does not claim full IM multi-user collaboration, production
deployment, provider marketplace, Docker sandboxing, WebSocket/multiplayer, PR
creation, or external Feishu/WeChat/Slack integration.

### Real Claude Code Path

Evidence:

| Field | Value |
|---|---|
| Session ID | `59ad209a-1f8d-4134-97c4-e4ad275b6f67` |
| UI session label | `会话 55` |
| Task ID | `eaac4f19-03c7-486f-b85a-1c4847cdcec8` |
| Task title | `Build the Vite React login page` |
| TaskRun ID | `f1e78e9e-2f6b-4b9c-b4a7-5879d513c555` |
| Adapter type | `claude_code` |
| Adapter run ID | `claude-code-fdd16bb8-6ab3-49be-bde0-ee77e80bdf7e` |
| Final run state | `completed` |
| Error | none |
| Worktree | `.worktrees/0474f8b8-499e-4117-afab-c780bd562446/59ad209a-1f8d-4134-97c4-e4ad275b6f67` |
| Base ref | `3363a05af86cbcaa010ed573c142b7fdb7c86181` |
| Head ref | `3363a05af86cbcaa010ed573c142b7fdb7c86181+worktree` |
| Changed file | `apps/demo/src/App.tsx` |
| Diff ID | `6650d975-6100-49b5-9cd5-cffee2a72754` |
| Diff artifact ID | `b4c0fae4-bfeb-4105-a506-64de639472c6` |
| Diff stats | 1 file changed, 7 additions, 4 deletions |
| Preview ID | `4eb1622b-fb10-49e7-9b3d-5c256fad4b29` |
| Preview artifact ID | `82042679-683c-439b-aaef-307ae83e17c4` |
| Preview URL | `http://127.0.0.1:49373` |
| Preview health/status | `healthy`, `ready` |
| Deployment ID | `6c5a423c-ec7b-4070-9a05-87a8dddd91a1` |
| Deployment artifact ID | `08d24039-6122-4f03-9470-ccc0b9262c8a` |
| Deployment provider/status | `mock`, `ready` |

Observed UI evidence:

- A new session was created from the sidebar.
- The fixed request was sent through the chat composer.
- The browser displayed a three-task plan.
- The frontend task was started from the `开始运行` button.
- The UI displayed `claude_code`, completed state, a diff chip for
  `apps/demo/src/App.tsx`, a healthy preview chip, and a mock deployment chip.
- The preview was started by clicking `启动预览`, then selected through the
  `预览1` tab; the right panel displayed the preview URL and iframe.
- The mock deployment was created by clicking `创建部署卡片`; the `部署1` tab and
  mock deployment-ready chip became visible.

### Fallback Path

Evidence:

| Field | Value |
|---|---|
| Session ID | `c148a1d6-8cd1-4efb-a797-7d10bbe475aa` |
| UI session label | `会话 56` |
| Task ID | `200e3d57-5856-41d1-9ec5-1ba203edc1f0` |
| Task title | `Build the Vite React login page` |
| Failed Codex TaskRun ID | `e7cead6e-93cd-4195-9a53-e258da253a81` |
| Failed adapter type | `codex` |
| Failed adapter run ID | `codex-733b3a70-84d5-4c71-baa7-b64560faceec` |
| Failed error code | `CODEX_DEMO_FORCED_FAILURE` |
| Fallback TaskRun ID | `36d68849-f644-4242-a64b-27c05b8cf2d8` |
| Fallback adapter type | `scripted_mock` |
| Fallback adapter run ID | `scripted-mock-dc38475a-432e-450c-a6d6-7e82ac6f6962` |
| Final fallback state | `completed` |
| Worktree | `.worktrees/0474f8b8-499e-4117-afab-c780bd562446/c148a1d6-8cd1-4efb-a797-7d10bbe475aa` |
| Base ref | `3363a05af86cbcaa010ed573c142b7fdb7c86181` |
| Head ref | `3363a05af86cbcaa010ed573c142b7fdb7c86181+worktree` |
| Changed file | `apps/demo/src/App.tsx` |
| Diff ID | `0a64bb85-deed-4307-a52c-815ffb5d8b9d` |
| Diff artifact ID | `fbe67726-20e3-4ad5-9b08-d4514aa97cbe` |
| Diff stats | 1 file changed, 11 additions, 4 deletions |
| Preview ID | `6c7f6f46-e287-4698-b6be-c99058f69b11` |
| Preview artifact ID | `5d5c3ae3-87d6-43fd-937e-57b371944637` |
| Preview URL | `http://127.0.0.1:49752` |
| Preview health/status | `healthy`, `ready` |
| Deployment ID | `a0b5d533-acee-4b2a-a384-103197d46481` |
| Deployment artifact ID | `ab42a147-dff9-4957-88be-d158676d9255` |
| Deployment provider/status | `mock`, `ready` |

Observed UI evidence:

- A separate new session was created from the sidebar.
- The same fixed request was sent through the chat composer.
- The frontend task was forced to fail by clicking `模拟 Codex 失败`.
- The UI displayed the failed `codex` run and
  `CODEX_DEMO_FORCED_FAILURE`.
- The fallback was started by clicking `使用兜底重试`.
- The UI displayed `scripted_mock`, `已恢复`, completed state, a diff chip, a
  healthy preview chip, and a mock deployment chip.
- The preview and mock deployment were created through the same UI controls as
  the real path.

### Reload And UI Caveats

Reload check:

- Reloading `http://127.0.0.1:3000/?session=c148a1d6-8cd1-4efb-a797-7d10bbe475aa`
  preserved the selected session, user message, generated plan, failed Codex
  run, fallback run, diff chip, preview chip, deployment chip, and artifact
  tabs.
- After reload, the artifact panel defaults back to the Diff tab. The preview
  URL and iframe are still available after clicking `预览1`, but they are not
  shown by default on the reloaded panel.

Browser automation caveats:

- The initial attempt to target the real-path Start button with a broad
  `article` locator matched all three task cards. The rehearsal recovered by
  clicking the second `开始运行` button, which corresponded to the frontend task.
  This was a test-locator issue, not a product runtime failure.
- The browser plugin emitted an unrelated Statsig network timeout while the
  local rehearsal continued. The AgentHub UI, API, preview, and deployment
  evidence were unaffected.

### P4-2 Validation Status

Validation was run after documenting the rehearsal:

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `git diff --check` | Pass |

### P4-2 Follow-Up Browser Spot Check

On 2026-05-20, the persisted P4-2 evidence was re-opened in the Codex in-app
browser without starting another real Claude or Codex mutation.

Checked real Claude Code session:

- URL:
  `http://127.0.0.1:3000/?session=59ad209a-1f8d-4134-97c4-e4ad275b6f67`
- The UI still showed `claude_code`, completed run state, the
  `apps/demo/src/App.tsx` diff chip, preview controls, and deployment controls.
- Clicking `预览1` showed one iframe with
  `src="http://127.0.0.1:49373"`.
- Clicking `部署1` showed the persisted mock deployment URL:
  `https://mock.agenthub.local/deployments/6c5a423c-ec7b-4070-9a05-87a8dddd91a1`.

Checked fallback session:

- URL:
  `http://127.0.0.1:3000/?session=c148a1d6-8cd1-4efb-a797-7d10bbe475aa`
- The UI still showed `CODEX_DEMO_FORCED_FAILURE`, `scripted_mock`,
  `兜底已恢复`, `Diff 就绪`, `预览健康`, `模拟部署就绪`, and
  `apps/demo/src/App.tsx`.

This spot check verifies persisted browser UI visibility for the already
recorded P4-2 run. It intentionally did not repeat a real agent execution.

## P4-0 Full E2E Agent Execution Capability Audit

**Date:** 2026-05-19

## Summary

AgentHub can drive the documented coding-agent loop through the browser-facing
API path:

```text
requirement -> orchestrator plan -> Direct Start -> agent execution -> file mutation -> diff -> preview -> mock deploy
```

The real-agent audit used `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code` to avoid
Codex quota. Claude Code completed a real demo-app mutation, generated a diff
artifact, started a healthy Vite preview, and created a mock deployment record.

The fallback audit also completed:

```text
Force Codex failure -> ScriptedMockAdapter fallback -> diff -> preview -> mock deploy
```

The follow-up audit completed in the same session:

```text
把按钮文案改成 Sign in -> follow-up frontend task -> Claude Code run -> second diff -> healthy preview
```

## Browser UI Coverage

The audit used the same backend endpoints called by the browser UI. The web app
was reachable at `http://127.0.0.1:3000`, and the audited session URL was opened:

```text
http://127.0.0.1:3000/?session=ebec86df-90bf-47ed-a5f1-b4f3b82a6c84
```

Full automated browser clicking was not completed because this checkout does
not have Playwright installed and the fallback Chrome AppleScript route was
blocked by a macOS Apple Events permission prompt asking whether Codex may
control Google Chrome. Because of that, this audit does **not** claim a verified
automated browser-button click. It verifies the UI-facing Direct Start,
fallback, preview, and deploy endpoints and records the browser automation
blocker explicitly.

## Environment

- Branch: `p3-ui-redesign`
- API: `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code pnpm dev:api`
- Web: existing `pnpm dev:web` process at `http://127.0.0.1:3000`
- Backend health: `{"status":"ok","service":"agenthub-api","database":"ready"}`
- CORS check: `http://localhost:3000` and `http://127.0.0.1:3000` are allowed
  local frontend origins.

## Real Agent Path

Path verified:

```text
UI-facing API -> Direct Start -> ClaudeCodeAdapter -> file mutation -> diff -> preview -> mock deploy
```

Evidence:

| Field | Value |
|---|---|
| Session ID | `ebec86df-90bf-47ed-a5f1-b4f3b82a6c84` |
| Task ID | `7c0fab95-e929-4252-9231-d92c2cc7e2e1` |
| Task title | `Build the Vite React login page` |
| TaskRun ID | `ab038575-a4e4-406c-bfcf-e0ae3ca4a318` |
| Adapter type | `claude_code` |
| Final run state | `completed` |
| Error | none |
| Changed file | `apps/demo/src/App.tsx` |
| Diff ID | `f255c967-dc21-4902-b842-96a86f52092f` |
| Diff artifact ID | `1c53db5d-94ba-4667-af09-c8e5b8a2214f` |
| Diff stats | 1 file changed, 7 additions, 4 deletions |
| Preview ID | `51e6c80f-006f-48e5-b1f7-2ecd629de442` |
| Preview artifact ID | `2a9f0d46-3c0c-4294-82b3-a673daa5e9c6` |
| Preview URL | `http://127.0.0.1:62044` |
| Preview health/status | `healthy`, `ready` |
| Deployment ID | `2b9e1c5e-c936-47c5-bd2a-4b29e243cca1` |
| Deployment artifact ID | `cba3a924-320c-44d6-bf0f-1302df5cb93e` |
| Deployment provider/status | `mock`, `ready` |

Observed state:

- Direct Start created a `claude_code` TaskRun, proving the default adapter
  environment selection was active.
- TaskRun moved through `queued` and `streaming` before reaching `completed`.
- Diff collection persisted a real diff for `apps/demo/src/App.tsx`.
- Preview service started a Vite React preview and reported `healthy`.
- Mock deploy service persisted a deployment record.

## Fallback Path

Path verified:

```text
Force Codex failure -> ScriptedMockAdapter fallback -> diff -> preview -> mock deploy
```

Evidence:

| Field | Value |
|---|---|
| Session ID | `52836726-e895-43da-964a-3244a30d5948` |
| Task ID | `773483a0-e026-4aa0-b816-0cb4decdfaf4` |
| Failed Codex TaskRun ID | `608113c6-a5f8-4df1-9742-8db1db7934de` |
| Failed error code | `CODEX_DEMO_FORCED_FAILURE` |
| Fallback TaskRun ID | `9662bb80-70dc-4d47-b82d-4ea1c9effb89` |
| Adapter type | `scripted_mock` |
| Final run state | `completed` |
| Changed file | `apps/demo/src/App.tsx` |
| Diff ID | `8ea04b9e-7d42-45cd-aeca-ca09d93e573f` |
| Diff artifact ID | `8007fd66-6f6b-4e9d-b61f-abf946cc9a08` |
| Preview ID | `38b3e7c9-2ec6-4fb0-ad7f-f4fc142f6b64` |
| Preview URL | `http://127.0.0.1:62136` |
| Preview health | `healthy` |
| Deployment ID | `fd5ca6bb-ae1c-4ce3-b0f2-dfd50e04eb3f` |
| Deployment provider/status | `mock`, `ready` |

Observed state:

- The failed Codex run remained separate from the successful fallback run.
- ScriptedMockAdapter created real demo-app file changes.
- Diff, preview, and mock deploy artifacts were generated through the same
  backend artifact pipeline.

## Follow-Up Path

Path verified:

```text
same session -> 把按钮文案改成 Sign in -> follow-up frontend task -> Claude Code run -> second diff -> healthy preview
```

Evidence:

| Field | Value |
|---|---|
| Session ID | `ebec86df-90bf-47ed-a5f1-b4f3b82a6c84` |
| Follow-up request | `把按钮文案改成 Sign in` |
| Follow-up Task ID | `81aeff37-608c-4708-a8c1-284e73b6ba2d` |
| Follow-up task title | `Change primary button text to Sign in` |
| TaskRun ID | `62c9ff50-7772-4000-9fe5-77a6596d7f92` |
| Adapter type | `claude_code` |
| Final run state | `completed` |
| Changed file | `apps/demo/src/App.tsx` |
| Diff ID | `267bd2d0-94a1-4935-b16d-4634458f96b5` |
| Diff artifact ID | `a76d098b-f16c-4823-ac40-22062515edf0` |
| Diff stats | 1 file changed, 8 additions, 5 deletions |
| Preview ID | `b850d9c8-5e3f-4862-96aa-6cd0cb5942fa` |
| Preview URL | `http://127.0.0.1:62341` |
| Preview health | `healthy` |

Direct worktree diff confirmed the deterministic button target changed from
`Continue` to `Sign in` in `apps/demo/src/App.tsx`.

## Broken Layers / Blockers

| Layer | Result | Notes |
|---|---|---|
| Frontend UI wiring | Partially verified | UI-facing endpoints completed. Automated browser button clicking was blocked by local browser automation permissions. |
| API client / backend endpoints | Pass | Session, message, task, run, diff, preview, and deployment endpoints completed. |
| Adapter execution | Pass | `ClaudeCodeAdapter` completed two real runs; `ScriptedMockAdapter` completed fallback. |
| Worktree | Pass | Mutations happened inside session worktrees. |
| Diff collection | Pass | Diff artifacts persisted for real and fallback runs. |
| Preview service | Pass | Preview records became `healthy`. |
| Deploy service | Pass | Mock deployment records persisted with provider `mock`. |
| SSE / refresh | Partial | TaskRun events were persisted and readable; live browser SSE refresh was not directly clicked/observed due browser automation blocker. |
| Auth / quota / env | Pass for this run | Claude Code was available and completed the audited runs. |

## Minimal Fixes Made

No new product features were added for the audit.

The working tree already contained a local CORS/sync hardening fix before this
audit was documented:

- backend CORS now allows both `localhost:3000` and `127.0.0.1:3000`
- browser-side session sync failures are caught and shown as a UI warning

That fix supports reliable local browser use but does not change the agent
execution model.

## Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (139 tests: 26 web + 113 API) |
| `git diff --check` | Pass |

## Conclusion

AgentHub can call a real local coding agent through the Direct Start path and
complete a coding goal with real file mutation, diff, healthy preview, and mock
deploy artifacts. The fallback path also remains intact. The remaining gap from
this audit is not the backend execution pipeline; it is automated browser-click
verification in this local environment.
