# AgentHub Project State

This document captures stable project state that future Codex prompts can
reference instead of repeating long context blocks.

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
