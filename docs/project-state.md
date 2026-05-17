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
