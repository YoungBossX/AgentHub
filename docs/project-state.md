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
