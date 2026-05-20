# AgentHub Project State

This document captures stable project state that future Codex prompts can
reference instead of repeating long context blocks.

## P4 Status

### P4-6 Final Freeze Review

P4-6 final freeze review completed on 2026-05-20.

Freeze result: ready to freeze the `agenthub-final-demo-hardening` baseline.

Verified documentation consistency:

- `AGENTS.md`, README, `docs/project-state.md`, `docs/change-log.md`,
  `docs/e2e-capability-audit.md`, `docs/final-demo-checklist.md`,
  `docs/project-summary-for-interview.md`, `docs/platform-roadmap.md`, and the
  `agenthub-final-demo-hardening` OpenSpec artifacts consistently describe
  AgentHub as a local single-user Agent Coding Workspace / strong demo MVP.
- Docs do not claim a full IM multi-user platform, production deploy, provider
  marketplace, Docker sandbox, PR creation, or broad arbitrary
  natural-language editing.
- P4 tasks 1.1 through 1.6 are complete after this review.

Remaining caveats are documented:

- deploy is mock-backed, not production deployment;
- browser click automation has local tooling/permission caveats recorded in
  `docs/e2e-capability-audit.md`;
- `pnpm demo:reset` does not delete `.worktrees`;
- `pnpm demo:reset` does not stop old preview or dev-server processes;
- mobile/responsive polish remains future work, not final-demo scope.

Validation passed:

- `openspec validate agenthub-im-coding-mvp --strict`
- `openspec validate agenthub-final-demo-hardening --strict`
- `pnpm check`
- `pnpm test`
- `git diff --check`

Recommended tag name after committing the final freeze review:
`agenthub-final-demo-hardening-freeze`.

### P4-5 Final Project Summary / Interview Explanation

P4-5 adds `docs/project-summary-for-interview.md`, a truthful final project
summary for demo, review, and interview use. It positions AgentHub as a local
single-user Agent Coding Workspace / strong demo MVP and explains:

- the problem AgentHub solves;
- frontend, backend, SQLite, session worktree, adapter, and artifact-pipeline
  architecture;
- the core requirement -> plan -> execution -> diff -> preview -> mock deploy
  workflow;
- `CodexAdapter`, `ClaudeCodeAdapter`, and `ScriptedMockAdapter`;
- forced-failure fallback recovery;
- same-session follow-up text-change flow;
- what is real, what is mock, and what is intentionally not implemented;
- design trade-offs and interview talking points.

The summary points readers to `docs/e2e-capability-audit.md` for evidence IDs
instead of inventing new evidence.

### P4-4 Final Demo Checklist

P4-4 adds `docs/final-demo-checklist.md` as the evidence-first rehearsal
checklist for the final AgentHub demo. It covers:

- clean reset with `pnpm demo:reset`;
- backend/frontend startup;
- optional Claude Code default adapter startup;
- fixed requirement message;
- task run, adapter, diff, preview, and mock deploy verification;
- fallback recovery through forced Codex failure and `ScriptedMockAdapter`;
- same-session follow-up request `把按钮文案改成 Sign in`;
- evidence ID capture;
- troubleshooting for occupied ports, missing API, auth/quota/runtime issues,
  stale preview, and reset refusal while SQLite is open.

The checklist is documentation-only and does not change app behavior.

### P4-3 Demo Reset / Clean Seed Helper

P4-3 adds a safe local reset workflow for repeatable final-demo rehearsals:

- Command: `pnpm demo:reset`
- Script: `scripts/demo-reset.sh`
- Active SQLite DB: `apps/api/data/agenthub.sqlite3`
- Backup location:
  `apps/api/data/backups/demo-reset-<timestamp>/`
- Reset behavior:
  - refuses to run while the SQLite DB is open by the API process;
  - backs up the active DB plus any SQLite WAL/SHM files;
  - recreates and seeds the database using the existing SQLModel init path;
  - does not delete `.worktrees`, source code, dependencies, or preview files;
  - does not stop running preview or dev-server processes;
  - prints restore commands for the created backup.

The helper seeds the existing baseline demo records: one demo user, one
`AgentHub Demo` workspace pointing at `apps/demo`, and enabled orchestrator,
frontend, backend, and QA agents. It does not pre-create a session; the demo
starts cleanly by creating a new session in the UI.

Reset rehearsal on 2026-05-20:

- First run while the API had SQLite open: refused reset and printed the owning
  process.
- Second run after stopping the API: backed up the previous DB to
  `apps/api/data/backups/demo-reset-20260520-124612/`.
- Seed check after reset: 1 user, 1 workspace, 4 agents, 0 sessions, 0 task
  runs, 0 previews.
- `.worktrees` remained present and was not deleted.

### P4-2 Browser E2E Click Rehearsal

P4-2 verified the final demo loop through browser UI clicks at
`http://127.0.0.1:3000` while the API ran with
`AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code pnpm dev:api`.

Real Claude Code path passed through UI clicks:

- Session: `59ad209a-1f8d-4134-97c4-e4ad275b6f67`
- UI label: `会话 55`
- Task: `eaac4f19-03c7-486f-b85a-1c4847cdcec8`
- TaskRun: `f1e78e9e-2f6b-4b9c-b4a7-5879d513c555`
- Adapter: `claude_code`
- Final state: `completed`
- Changed file: `apps/demo/src/App.tsx`
- Diff artifact: `b4c0fae4-bfeb-4105-a506-64de639472c6`
- Preview: `4eb1622b-fb10-49e7-9b3d-5c256fad4b29`
- Preview URL: `http://127.0.0.1:49373`
- Preview health/status: `healthy`, `ready`
- Deployment: `6c5a423c-ec7b-4070-9a05-87a8dddd91a1`
- Provider/status: `mock`, `ready`

Fallback path passed through UI clicks:

- Session: `c148a1d6-8cd1-4efb-a797-7d10bbe475aa`
- UI label: `会话 56`
- Task: `200e3d57-5856-41d1-9ec5-1ba203edc1f0`
- Failed Codex TaskRun: `e7cead6e-93cd-4195-9a53-e258da253a81`
- Failed error code: `CODEX_DEMO_FORCED_FAILURE`
- Fallback TaskRun: `36d68849-f644-4242-a64b-27c05b8cf2d8`
- Adapter: `scripted_mock`
- Final state: `completed`
- Changed file: `apps/demo/src/App.tsx`
- Diff artifact: `fbe67726-20e3-4ad5-9b08-d4514aa97cbe`
- Preview: `6c7f6f46-e287-4698-b6be-c99058f69b11`
- Preview URL: `http://127.0.0.1:49752`
- Preview health/status: `healthy`, `ready`
- Deployment: `a0b5d533-acee-4b2a-a384-103197d46481`
- Provider/status: `mock`, `ready`

Reload caveat: persisted runs, chips, and artifact tabs survived reload. The
right artifact panel defaults back to Diff after reload; click `预览1` to show
the persisted preview URL and iframe again.

Follow-up browser spot check on 2026-05-20 re-opened the persisted P4-2
sessions without running another real agent mutation:

- Real Claude Code session
  `59ad209a-1f8d-4134-97c4-e4ad275b6f67` still showed the completed
  `claude_code` run, `apps/demo/src/App.tsx` diff chip, `预览1` iframe at
  `http://127.0.0.1:49373`, and mock deployment
  `6c5a423c-ec7b-4070-9a05-87a8dddd91a1`.
- Fallback session `c148a1d6-8cd1-4efb-a797-7d10bbe475aa` still showed
  `CODEX_DEMO_FORCED_FAILURE`, `scripted_mock`, `兜底已恢复`, `Diff 就绪`,
  `预览健康`, and `模拟部署就绪`.

### P4-1 Baseline Governance Cleanup

P4-1 aligns repository governance around the current project identity:

- AgentHub is a local single-user Agent Coding Workspace / strong demo MVP, not
  a full multi-user IM collaboration platform.
- `CodexAdapter`, `ClaudeCodeAdapter`, and `ScriptedMockAdapter` are all current
  adapters and must not be removed or regressed.
- The fallback-based P0 path, P1/P2/P3 verified paths, and P4-0 real-agent
  evidence remain preserved.
- Production deploy, provider marketplace, WebSocket/multiplayer, Docker
  sandbox, external IM integrations, PR creation, broad arbitrary editing, and
  enterprise workflows remain deferred.

### P4-0 Full E2E Agent Execution Capability Audit

P4-0 verified that AgentHub can drive the full coding-agent execution pipeline
through the browser-facing API path:

```text
requirement -> orchestrator plan -> Direct Start -> agent execution -> file mutation -> diff -> preview -> mock deploy
```

Real-agent path with Claude Code default adapter passed:

- Session: `ebec86df-90bf-47ed-a5f1-b4f3b82a6c84`
- Task: `7c0fab95-e929-4252-9231-d92c2cc7e2e1`
- TaskRun: `ab038575-a4e4-406c-bfcf-e0ae3ca4a318`
- Adapter: `claude_code`
- Final state: `completed`
- Changed file: `apps/demo/src/App.tsx`
- Diff artifact: `1c53db5d-94ba-4667-af09-c8e5b8a2214f`
- Preview: `51e6c80f-006f-48e5-b1f7-2ecd629de442`
- Preview URL: `http://127.0.0.1:62044`
- Preview health/status: `healthy`, `ready`
- Deployment: `2b9e1c5e-c936-47c5-bd2a-4b29e243cca1`
- Provider/status: `mock`, `ready`

Fallback path passed:

- Session: `52836726-e895-43da-964a-3244a30d5948`
- Task: `773483a0-e026-4aa0-b816-0cb4decdfaf4`
- Failed Codex TaskRun: `608113c6-a5f8-4df1-9742-8db1db7934de`
- Failed error code: `CODEX_DEMO_FORCED_FAILURE`
- Fallback TaskRun: `9662bb80-70dc-4d47-b82d-4ea1c9effb89`
- Adapter: `scripted_mock`
- Final state: `completed`
- Diff artifact: `8007fd66-6f6b-4e9d-b61f-abf946cc9a08`
- Preview: `38b3e7c9-2ec6-4fb0-ad7f-f4fc142f6b64`
- Preview URL: `http://127.0.0.1:62136`
- Preview health: `healthy`
- Deployment: `fd5ca6bb-ae1c-4ce3-b0f2-dfd50e04eb3f`
- Provider/status: `mock`, `ready`

Follow-up path passed in the same real-agent session:

- Request: `把按钮文案改成 Sign in`
- Follow-up task: `81aeff37-608c-4708-a8c1-284e73b6ba2d`
- Follow-up TaskRun: `62c9ff50-7772-4000-9fe5-77a6596d7f92`
- Adapter: `claude_code`
- Final state: `completed`
- Diff artifact: `a76d098b-f16c-4823-ac40-22062515edf0`
- Preview: `b850d9c8-5e3f-4862-96aa-6cd0cb5942fa`
- Preview URL: `http://127.0.0.1:62341`
- Preview health: `healthy`

Browser automation caveat: this audit opened the audited session URL, but full
automated browser-button clicking was blocked because Playwright is not
installed and Chrome AppleScript control hit a macOS Apple Events permission
prompt. The audit therefore verifies the browser-facing API execution path and
records the browser-click automation gap honestly.

## P0 Baseline

P0 is complete and the judge-demoable path remains fallback-based:

```text
forced Codex failure -> ScriptedMockAdapter fallback -> real diff -> healthy Vite preview -> mock deploy card
```

Preserve this path when making P1 changes.

## P1 Status

### P1-10 Frozen Demo Baseline

P1 is frozen as a stable local demo baseline.

Frozen path:

```text
real Codex Direct Start -> diff card -> Start preview -> preview iframe -> Create deploy card
```

The acceptance checklist lives in `docs/p1-acceptance-checklist.md`.

Frozen baseline evidence is the P1-9 clean-start rehearsal:

- Session: `666fa20b-6f54-4342-b844-39594b903da3`
- TaskRun: `b1882cda-47f6-4035-b12d-ba3d72d67939`
- Diff artifact: `c832b249-c2c3-444c-ac97-6b3e811e5c70`
- Preview: `b363eb09-7251-4b8e-a5b4-3c59775b58b7`
- Deployment: `d97e447a-c8d0-41b7-95f8-e40008d83eb0`
- Provider/status: `mock`, `ready`

Fallback path remains available:

```text
forced Codex failure -> ScriptedMockAdapter fallback -> real diff -> healthy Vite preview -> mock deploy card
```

### P1-6 Verified

P1-6 verified:

- HTTP Direct Start
- Real Codex file mutation
- Diff artifact generation

Verified path:

```text
HTTP Direct Start -> real Codex file mutation -> diff artifact
```

### P1-7 Verified Through Backend APIs

P1-7 verified through backend APIs:

- Real Codex Direct Start
- Real diff artifact
- Healthy Vite preview
- Mock deploy

Verified path:

```text
real Codex Direct Start -> real diff artifact -> healthy Vite preview -> mock deploy
```

P1-7 evidence:

- TaskRun: `fa23fb4a-6506-4b0e-a608-3197356d0628`
- Diff artifact: `782e16f4-36b5-46f3-86cf-42c3fb6119e9`
- Preview: `877daf34-cabe-4ddf-8726-94677ba18831`
- Preview URL: `http://127.0.0.1:53089`
- Deployment: `9ba427d9-1ea8-454a-8890-e243075fcec7`
- Provider/status: `mock`, `ready`

### P1-8 Verified Through Browser UI

P1-8 verified the post-diff artifact path through browser UI interaction:

- Real Codex Direct Start run remained visible in the UI.
- Persisted real diff artifact rendered as a diff card.
- Preview was started from the UI.
- Healthy Vite preview opened in the right-side iframe panel.
- Mock deploy card was created from the UI.
- Diff, preview, and deploy cards remained visible after reload.

Verified path:

```text
real Codex Direct Start -> diff card -> Start preview -> preview iframe -> Create deploy card
```

P1-8 evidence:

- TaskRun: `fa23fb4a-6506-4b0e-a608-3197356d0628`
- Diff artifact: `782e16f4-36b5-46f3-86cf-42c3fb6119e9`
- UI-created preview: `810324d7-2ba9-47e6-b676-7391e87cb131`
- UI-created preview URL: `http://127.0.0.1:64067`
- UI-created deployment: `58c7812c-31f8-49ee-8b08-28d38264cd87`
- Provider/status: `mock`, `ready`

### P1-9 Clean-Start Demo Rehearsal

P1-9 verified the browser UI demo path from a clean server start:

- Backend started with `pnpm dev:api`.
- Frontend started with `pnpm dev:web`.
- A new session was created from the UI.
- The fixed demo request was sent from the UI.
- Direct UI Start invoked a real Codex TaskRun.
- Real Codex completed and produced a real diff artifact.
- Preview was started from the UI and opened in the right-side iframe panel.
- Mock deploy card was created from the UI.
- Diff, preview, and deploy cards remained visible after reload.

Verified path:

```text
clean start -> real Codex Direct Start -> diff card -> Start preview -> preview iframe -> Create deploy card
```

P1-9 evidence:

- Session: `666fa20b-6f54-4342-b844-39594b903da3`
- Task: `c90396af-1b9f-42f4-a6dd-9daa4f3913f6`
- TaskRun: `b1882cda-47f6-4035-b12d-ba3d72d67939`
- Base ref: `ad9136f91fe9776c33e839359a2203d64fbbf322`
- Head ref: `ad9136f91fe9776c33e839359a2203d64fbbf322+worktree`
- Diff: `8a0155a6-b865-4cee-987e-82d773b9f20e`
- Diff artifact: `c832b249-c2c3-444c-ac97-6b3e811e5c70`
- Changed file: `apps/demo/src/App.tsx`
- Diff stats: 1 file changed, 14 additions, 4 deletions
- Preview: `b363eb09-7251-4b8e-a5b4-3c59775b58b7`
- Preview artifact: `f93ebc25-b8c7-47e9-ac11-aeee777c604e`
- Preview URL: `http://127.0.0.1:51763`
- Deployment: `d97e447a-c8d0-41b7-95f8-e40008d83eb0`
- Deployment artifact: `d85e9bcf-9b92-4c3c-958a-352f855e59a9`
- Provider/status: `mock`, `ready`

### P1-11 Clean-State and Fallback Rehearsal

P1-11 closed the main P1 demo-readiness gaps from a non-destructive clean
state rehearsal.

Backup/reset method:

- Moved the active SQLite database to
  `/tmp/agenthub-p1-11-backup-20260517-095901/agenthub.sqlite3.before-p1-11`.
- Recorded the pre-rehearsal Git worktree registry and directory inventory at:
  - `/tmp/agenthub-p1-11-backup-20260517-095901/worktree-list-before.txt`
  - `/tmp/agenthub-p1-11-backup-20260517-095901/worktree-dirs-before.txt`
- Left existing `.worktrees` checkouts in place to avoid disturbing Git's
  registered worktree metadata.
- Reinitialized a clean SQLite database with `pnpm db:init`.
- Created fresh session-level worktrees from the clean DB during the rehearsal.

Restore note: stop the dev servers first, back up the current
`apps/api/data/agenthub.sqlite3` if it needs to be preserved, then move
`/tmp/agenthub-p1-11-backup-20260517-095901/agenthub.sqlite3.before-p1-11`
back to `apps/api/data/agenthub.sqlite3`.

Clean-state direct Codex rehearsal passed:

```text
clean SQLite -> fresh session worktree -> real Codex Direct Start -> real diff -> healthy Vite preview -> mock deploy card
```

Clean-state evidence:

- Session: `72668a90-74a0-45c6-a0c4-98e8cfa54c27`
- Session worktree:
  `/Users/luotianhang/Desktop/agenthub/.worktrees/0474f8b8-499e-4117-afab-c780bd562446/72668a90-74a0-45c6-a0c4-98e8cfa54c27`
- Task: `7e0a4e97-1b80-404d-bcab-4616418627e3`
- TaskRun: `4c92132f-3c89-47cc-b8a4-3f1395825c39`
- Adapter: `codex`
- Final TaskRun state: `completed`
- Error code/message: none
- Base ref: `abdcd88e200ce8c39f50ed38f244d40cb52295bb`
- Head ref: `abdcd88e200ce8c39f50ed38f244d40cb52295bb+worktree`
- Diff: `bb45131e-42f8-47d7-88eb-c8126d694b0a`
- Diff artifact: `243ce682-748b-42ad-9354-dd8eed1f3e67`
- Changed file: `apps/demo/src/App.tsx`
- Diff stats: 1 file changed, 15 additions, 4 deletions
- Preview: `a30d07e2-470c-4614-a864-c21ac0b52363`
- Preview artifact: `4b3475ad-0d1f-4980-ab80-18abb50492fd`
- Preview URL: `http://127.0.0.1:58634`
- Preview health/status: `healthy`, `ready`
- Deployment: `448b7d91-5064-43c2-a849-3e89634e14bd`
- Deployment artifact: `717d28cc-eb3e-47cb-9950-cee1985ea798`
- Provider/environment/status: `mock`, `preview`, `ready`

Manual forced-failure fallback rehearsal passed:

```text
forced Codex failure -> ScriptedMockAdapter fallback -> real diff -> healthy Vite preview -> mock deploy card
```

Fallback evidence:

- Session: `695287ed-2967-4360-8520-a5fdc1be46e3`
- Session worktree:
  `/Users/luotianhang/Desktop/agenthub/.worktrees/0474f8b8-499e-4117-afab-c780bd562446/695287ed-2967-4360-8520-a5fdc1be46e3`
- Task: `1a790664-c817-42eb-a953-d7c0f11cccb0`
- Failed Codex TaskRun: `1b50d047-0c08-4ff2-a4d7-12412b36f786`
- Failed run error code: `CODEX_DEMO_FORCED_FAILURE`
- Fallback TaskRun: `c35d52f5-bf27-4656-aee1-b0321eb2bd96`
- Fallback adapter: `scripted_mock`
- Final fallback TaskRun state: `completed`
- Diff: `8a8f05bf-6559-44f4-bafc-fb87881c4750`
- Diff artifact: `91b6c898-bf2b-4c0c-b44b-f6a236a72ef0`
- Changed file: `apps/demo/src/App.tsx`
- Diff stats: 1 file changed, 11 additions, 4 deletions
- Preview: `e1be7c11-1cc7-42f9-8441-62c7eb0a1b92`
- Preview artifact: `4ed1465f-f887-4680-b9a1-6893e593468d`
- Preview URL: `http://127.0.0.1:59152`
- Preview health/status: `healthy`, `ready`
- Deployment: `cb8c7f95-42f7-4213-8273-4201500bf8b3`
- Deployment artifact: `43e15df7-5fb4-4711-85b6-94c485b0b4cb`
- Provider/environment/status: `mock`, `preview`, `ready`

After reload, the failed Codex run, fallback run, diff, preview, and deploy
card all remained visible in the browser UI.

### P1 Final Freeze Review

The final freeze review confirmed:

- P1-11 is committed at `faca556`.
- No tag currently points at P1-11 HEAD.
- README, demo script, project state, change log, and P1 checklist align on the
  P1 direct Codex path and the fallback-based P0 path.
- Natural-language second-change orchestration remains a caveat.
- Approval card UI is outside the frozen P1 judge path.
- Production deploy remains out of scope.
- A locale-specific development hydration warning around session date formatting
  was observed during P1-11, but did not block the clean-state or fallback
  rehearsal.

## P2 Status

### P2-1 Locale Hydration Warning Fixed

P2-1 replaced runtime-locale timestamp rendering in the workspace shell and
preview card with deterministic compact formatting. Manual reload verification
confirmed the previous locale-specific hydration overlay did not appear.

### P2-2 Approval Card UI/Rehearsal Verified

P2-2 exposed the existing P0 approval request payload on waiting TaskRuns,
added approve/deny endpoints, and rendered a compact approval card in the task
card run controls.

Verified approval rehearsal state:

- Session: `67421999-3b16-44c4-ade3-98cb31331549`
- Approved TaskRun: `5653e8f9-0057-478f-913c-ac25b4484216`
- Denial rehearsal TaskRun: `54bde1de-b9f7-4f2b-9357-98d51b3675c7`
- Approval types rendered: `product_confirmation`, `security_approval`

Manual browser verification confirmed the `product_confirmation` approval card
rendered and the Approve action moved the run from `waiting_approval` to
`queued`. The `security_approval` card rendered as well; denial behavior is
covered by backend/API tests and frontend button wiring tests.

### P2-3 Natural-Language Second-Change Orchestration Verified

P2-3 added deterministic follow-up planning for simple UI text-change requests
inside an existing session. Supported demo-safe examples include:

- `change the primary button text to Sign in`
- `把按钮文案改成 Sign in`
- `把标题改成 Welcome back`

Verified path:

```text
initial plan -> fallback run -> first diff/preview -> natural-language follow-up -> follow-up frontend task -> fallback run -> second diff/preview
```

P2-3 rehearsal evidence:

- Session: `d65fc331-39f2-432b-9828-89723b9f3c32`
- Session worktree:
  `/Users/luotianhang/Desktop/agenthub/.worktrees/0474f8b8-499e-4117-afab-c780bd562446/d65fc331-39f2-432b-9828-89723b9f3c32`
- Initial frontend task: `3f7f6f65-9f72-4add-ab0a-c9a944dc3b23`
- Initial fallback TaskRun: `607ad185-8eb2-4158-8219-e124880e68a7`
- Initial diff artifact: `c83c21d5-dad8-4d56-b0b8-cf1bc9de2bc3`
- Initial preview: `511ee0ca-e0dc-4054-8775-e487e81f7303`
- Initial preview health: `healthy`
- Follow-up request: `把按钮文案改成 Sign in`
- Follow-up task: `3ce6aa3d-97bf-4e16-b85a-33676e62bef2`
- Follow-up task title: `Change primary button text to Sign in`
- Follow-up task target: `primary_action_button_text`
- Follow-up task target text: `Sign in`
- Follow-up fallback TaskRun: `7a4f5763-ebbe-4d51-a207-b36b1fff7091`
- Follow-up diff artifact: `f1ca4318-0b41-48a8-9b27-acb957448734`
- Follow-up preview: `551aa58f-ab73-49f3-96c2-e6db8994bdd6`
- Follow-up preview health: `healthy`
- Total tasks after follow-up: 4

The follow-up run reused the same session worktree and produced a second diff
artifact for `apps/demo/src/App.tsx`. The preview refresh after the second
change was verified through the backend preview API returning a healthy preview.

Known P2-3 limits:

- Execution rehearsal used the `ScriptedMockAdapter` fallback path, not real
  Codex, to avoid quota dependency during this task.
- Browser iframe refresh after the second change was not separately rehearsed.
- Broad arbitrary natural-language code editing remains out of scope; P2-3 is
  intentionally limited to deterministic button/title text changes.

### P2-4 Browser Preview Iframe Refresh Verified

P2-4 verified the remaining second-change preview gap through browser UI
interaction. No product code changes were required.

Verified path:

```text
browser UI initial task -> ScriptedMockAdapter fallback -> first diff -> Start preview -> iframe at first preview URL -> natural-language follow-up -> ScriptedMockAdapter fallback -> second diff -> Start preview -> iframe refreshed to second preview URL
```

P2-4 browser rehearsal evidence:

- Session: `cb653482-c31a-48da-a8ee-31ed8cd367e3`
- Session worktree:
  `/Users/luotianhang/Desktop/agenthub/.worktrees/0474f8b8-499e-4117-afab-c780bd562446/cb653482-c31a-48da-a8ee-31ed8cd367e3`
- Initial frontend task: `5f2c26c2-6511-4b8f-b359-b9de5c9e5a50`
- Initial fallback TaskRun: `cfeff131-8cbf-4bcc-95b9-1aa84dbf5130`
- Initial diff artifact: `737085ee-7b73-4715-8303-df64b3a14132`
- Initial preview: `c077ba2d-7bd4-4c49-8e0c-313e2ecd641c`
- Initial preview URL: `http://127.0.0.1:61087`
- Initial preview health: `healthy`
- Follow-up request: `把按钮文案改成 Sign in`
- Follow-up task: `0f9ff26c-8216-4489-b71a-3628c1a7ab7a`
- Follow-up fallback TaskRun: `f8d78651-5347-43de-8553-12b29c8c3647`
- Follow-up diff artifact: `b48b3b33-feb2-4313-805d-89811a5cb51c`
- Follow-up preview: `44ea9495-04b5-419a-ba64-0701eaa83ec8`
- Follow-up preview URL: `http://127.0.0.1:61292`
- Follow-up preview health: `healthy`

The right-side preview panel changed from the initial iframe URL
`http://127.0.0.1:61087` to the follow-up iframe URL
`http://127.0.0.1:61292`. The in-app browser cannot inspect cross-origin iframe
DOM directly, so the visible panel refresh was verified by screenshot and the
follow-up preview content was verified by opening `http://127.0.0.1:61292` as a
top-level page, where the DOM and screenshot showed the `Sign in` button.

Known P2-4 limits:

- Real Codex was not used for the P2-4 execution portion; the rehearsal used
  the reliable forced-failure plus `ScriptedMockAdapter` fallback path.
- Browser verification confirmed the iframe URL and visible panel refresh, but
  direct DOM inspection inside the cross-origin iframe is not supported by the
  current in-app browser runtime.

### P2-5 GitHub Actions CI Added

P2-5 added a minimal GitHub Actions workflow for pull requests and pushes. The
workflow mirrors the repeated local validation path:

```text
pnpm install --frozen-lockfile -> Python .venv API dependency install -> pnpm check -> pnpm test -> git diff --check
```

CI uses:

- Node.js 22
- pnpm 10.33.4, matching `package.json`
- Python 3.11
- the existing repo scripts, including the `.venv/bin/python`-based API check
  and test wrappers

No app code, test behavior, deployment, Docker, or production release workflow
was added.

### Minimal Claude Code Adapter Added

The backend now includes a minimal `ClaudeCodeAdapter` runtime option behind the
existing adapter contract. It is a sibling of `CodexAdapter`, uses subprocess
`cwd` for session worktree isolation, and maps Claude Code `stream-json` stdout
into normalized AgentHub events.

Current verified state:

- Fake-runner tests cover command construction, incremental stream-json event
  parsing, persisted `TaskRunEvent` sequence ordering, missing CLI, auth
  required, usage limit, parse error, startup timeout, and interruption
  normalization. P2-7 added coverage for real Claude `stream_event` text-delta
  mapping and thinking-delta filtering.
- `adapterType: claude_code` is supported by backend adapter dispatch.
- Guardrails allow the bounded `claude --print --output-format stream-json`
  command family so it can be evaluated through the same command policy path as
  the Codex CLI.

Current limitations:

- P2-7 has run one explicitly approved real Claude Code mutation smoke. Broader
  prompts, browser UI wiring, auth failure text, and usage-limit text remain
  unverified.
- `ScriptedMockAdapter` remains the reliability fallback, and the P1 real Codex
  path remains unchanged.

### P2-7 Real Claude Code Smoke Verified

P2-7 ran a bounded real Claude Code adapter smoke in a detached disposable
session worktree:

```text
ClaudeCodeAdapter -> real Claude CLI -> stream-json events -> file mutation -> completed TaskRun -> diff artifact
```

Disposable worktree:

```text
/Users/luotianhang/Desktop/agenthub/.worktrees/claude-smoke-96d46af7-dc74-4d71-a062-c9be42cd1332
```

The first attempt found a local adapter bug before mutation:

- Failed TaskRun: `c66f1f86-2407-487a-b18f-cf01abd3a7f3`
- Error code: `CLAUDE_CODE_EXIT_ERROR`
- Error message:
  `Error: When using --print, --output-format=stream-json requires --verbose`

The adapter command was updated to include `--verbose`, and the second bounded
smoke succeeded:

- Session: `4cf32311-1a9b-4eda-9ec3-ab0d010691fc`
- Task: `a5557a9a-99de-4962-9d25-86ed548ea7ca`
- TaskRun: `095ae634-c188-4ffc-a502-53a500d20e14`
- AdapterRun: `claude-code-94cc6074-f15d-4290-b050-c2383363f44d`
- Final state: `completed`
- Base ref: `0066dea6c7f6a235cb2c2e0361624a1116d66dad`
- Head ref: `0066dea6c7f6a235cb2c2e0361624a1116d66dad+worktree`
- Diff artifact: `95bb1d0b-12a3-4a0e-be3e-c07cf1bf79d4`
- Diff: `9f69bc39-6b32-42ca-8a86-cf9fbfa62343`
- Changed file: `apps/demo/src/App.tsx`
- Diff stats: 1 file changed, 1 addition, 1 deletion

The direct git diff in the disposable worktree shows only the primary button
text changed from `Continue` to `Claude smoke`.

Known P2-7 limits:

- This was a direct backend smoke, not a full browser UI flow.
- Only one tiny mutation instruction was verified.
- Claude `stream-json` includes verbose low-level `stream_event` records; the
  adapter now maps text deltas and filters thinking deltas, but broader stream
  event shapes remain unverified.
- Auth failure and usage-limit real outputs are still unverified.

### P2-8 Claude Code Direct-Start Selection Added

P2-8 added a minimal environment-based adapter selection path for normal demo
execution. Direct Start still uses the assigned agent's configured adapter by
default, but setting:

```bash
AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code
```

causes frontend/backend coding tasks whose seeded adapter is `codex` to create
new TaskRuns with `adapterType: claude_code`. Explicit adapter selections still
win, so forced Codex failure, retry history, and retry-with-ScriptedMockAdapter
fallback keep their existing behavior. Non-code agents, including the
`scripted_mock` QA path, are not changed by the env var.

Verified state:

- Service tests cover default Claude selection for frontend tasks.
- Service tests cover explicit Codex preserving its requested adapter.
- Service tests cover ScriptedMockAdapter preserving non-code fallback behavior.
- Service tests cover invalid env values failing loudly.

Known P2-8 limits:

- No new real Claude mutation was run for P2-8; P2-7 remains the real Claude
  smoke evidence.
- This is an env/config switch, not a provider marketplace or UI selector.

### P2-9 Claude Default Adapter Mode Documented

P2-9 documented how to start the API with Claude Code as the default coding
adapter:

```bash
AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code pnpm dev:api
```

Minimal Direct Start verification used an in-memory API rehearsal, not a real
Claude execution. With the env var set, `POST /tasks/{task_id}/runs` created a
queued TaskRun with `adapterType: claude_code`.

Evidence:

- Session: `1c662ede-d0be-4349-8c86-20f49be6fb53`
- Task: `c28cda5b-67c7-44a8-bd2b-e43ebbc64217`
- TaskRun: `a1c191ea-1414-4746-95ca-d6c51b36b4f8`
- Adapter type: `claude_code`
- State: `queued`
- Queued event payload: `{"adapterType":"claude_code","state":"queued"}`

Known P2-9 limits:

- No real Claude mutation was run for P2-9.
- Full browser UI Claude-default execution through diff/preview/deploy remains
  unrehearsed.
- P2-7 remains the real Claude mutation and diff artifact evidence.

### P2 Final Freeze Review

P2 final freeze review confirmed the documentation is aligned on the current
P2 baseline:

- P2 stabilization work is complete through P2-9.
- P2 validation remains green with `pnpm check`, `pnpm test`, and
  `git diff --check`.
- The P1 real Codex demo path and fallback-based P0 demo path remain preserved.
- Claude Code default mode is documented with
  `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code`.
- P2 caveats remain visible:
  - full browser UI Claude-default execution through diff/preview/deploy is
    unrehearsed
  - real Claude auth-failure and usage-limit outputs remain partially
    unverified
  - broad arbitrary natural-language editing remains out of scope
  - production deploy remains out of scope

No app code, adapter code, backend API behavior, frontend behavior, or tests
changed during the P2 final freeze review.
