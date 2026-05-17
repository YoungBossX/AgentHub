# P1 Acceptance Checklist

P1 freezes the current AgentHub demo baseline around the verified browser UI
path:

```text
real Codex Direct Start -> diff card -> Start preview -> preview iframe -> Create deploy card
```

The fallback-based P0 demo remains available:

```text
forced Codex failure -> ScriptedMockAdapter fallback -> real diff -> healthy Vite preview -> mock deploy card
```

## Completed Capabilities

| ID | Capability | Result | Evidence |
|---|---|---|---|
| P1-A1 | Direct UI Start dispatches backend execution instead of stopping at queued | Pass | P1-1; `POST /tasks/{task_id}/runs` dispatches background adapter execution. |
| P1-A2 | Codex CLI path is available and command shape is verified | Pass | P1-2; local Codex app path and documented command shape verified. |
| P1-A3 | Codex subprocess execution does not block the API event loop | Pass | P1-3; health remained responsive during execution. |
| P1-A4 | Codex JSONL events stream incrementally | Pass | P1-4; event persistence occurs while Codex is running. |
| P1-A5 | Codex reconnect/error handling supports successful completion after reconnect progress | Pass | P1-5; reconnect progress no longer forces premature failure. |
| P1-A6 | HTTP Direct Start can produce real Codex file mutation and diff artifact | Pass | P1-6 TaskRun `fa23fb4a-6506-4b0e-a608-3197356d0628`; diff artifact `782e16f4-36b5-46f3-86cf-42c3fb6119e9`. |
| P1-A7 | Backend APIs can continue from real Codex diff to healthy preview and mock deploy | Pass | P1-7 preview `877daf34-cabe-4ddf-8726-94677ba18831`; deployment `9ba427d9-1ea8-454a-8890-e243075fcec7`. |
| P1-A8 | Browser UI can show real diff, open preview iframe, and create mock deploy card | Pass | P1-8 preview `810324d7-2ba9-47e6-b676-7391e87cb131`; deployment `58c7812c-31f8-49ee-8b08-28d38264cd87`. |
| P1-A9 | Clean-start browser demo can reproduce the full P1 path | Pass | P1-9 session `666fa20b-6f54-4342-b844-39594b903da3`; TaskRun `b1882cda-47f6-4035-b12d-ba3d72d67939`. |

## Frozen P1 Evidence

Clean-start P1-9 rehearsal evidence:

- Session: `666fa20b-6f54-4342-b844-39594b903da3`
- Task: `c90396af-1b9f-42f4-a6dd-9daa4f3913f6`
- TaskRun: `b1882cda-47f6-4035-b12d-ba3d72d67939`
- Adapter: `codex`
- Final TaskRun state: `completed`
- Error code/message: none
- Base ref: `ad9136f91fe9776c33e839359a2203d64fbbf322`
- Head ref: `ad9136f91fe9776c33e839359a2203d64fbbf322+worktree`
- Diff: `8a0155a6-b865-4cee-987e-82d773b9f20e`
- Diff artifact: `c832b249-c2c3-444c-ac97-6b3e811e5c70`
- Changed file: `apps/demo/src/App.tsx`
- Diff stats: 1 file changed, 14 additions, 4 deletions
- Preview: `b363eb09-7251-4b8e-a5b4-3c59775b58b7`
- Preview artifact: `f93ebc25-b8c7-47e9-ac11-aeee777c604e`
- Preview URL: `http://127.0.0.1:51763`
- Preview health/status: `healthy`, `ready`
- Deployment: `d97e447a-c8d0-41b7-95f8-e40008d83eb0`
- Deployment artifact: `d85e9bcf-9b92-4c3c-958a-352f855e59a9`
- Provider/environment/status: `mock`, `preview`, `ready`
- Deployment URL:
  `https://mock.agenthub.local/deployments/d97e447a-c8d0-41b7-95f8-e40008d83eb0`

## Validation Commands

Latest P1-10 validation:

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (90 tests: 22 web + 68 API) |
| `git diff --check` | Pass |

Prior P1-9 validation:

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (90 tests: 22 web + 68 API) |
| `git diff --check` | Pass |

## Known Unverified Items

- P1-9 did not reset the SQLite database or delete existing worktrees; it
  restarted backend/frontend processes and created a fresh session from the UI.
- The fallback-based P0 path was not manually re-run during P1-9 because real
  Codex completed. It remains covered by existing tests and prior manual
  verification.
- Natural-language second-change orchestration remains a documented caveat.
- Approval card UI was not part of the frozen P1 judge path.
- Production deploy was not implemented or verified.

## Known Risks

- Real Codex execution depends on local Codex CLI availability, authentication,
  quota, and CLI stability.
- Codex run duration can vary; keep the ScriptedMockAdapter fallback ready for
  time-boxed demos.
- Preview health depends on setup-time demo dependencies already being
  installed.
- Runtime evidence IDs are local SQLite records and are useful for this
  checkout, not portable production identifiers.

## Fallback-Based P0 Status

The fallback-based P0 demo remains intact and should be used if real Codex is
unavailable, usage-limited, unauthenticated, or too slow:

1. Send `@orchestrator build a login page for the demo app`.
2. Click `Force Codex failure`.
3. Verify the failed Codex run remains visible.
4. Click `Retry with ScriptedMockAdapter`.
5. Verify real file changes, diff card, preview iframe, and mock deploy card.

## Explicitly Out Of Scope For P1

- `ClaudeCodeAdapter`
- `HumanAgentAdapter`
- Docker sandbox
- WebSocket
- Provider marketplace
- MCP marketplace
- PR creation or patch export
- Production deployment
- Full deployment provider matrix
- External IM integrations
- Multi-user collaboration
- Enterprise RBAC, billing, audit backend, or multi-tenant admin

## Recommended Next Phase

Archive or tag the frozen P1 demo baseline, then move to a focused P2 planning
step. Recommended P2 candidates:

- improve judge-facing demo reset tooling
- make second-change orchestration explicit and tested
- add clearer run progress details in the UI
- design approval UI rehearsal coverage
- evaluate production-ready preview/deploy options without expanding the P1
  frozen demo scope
