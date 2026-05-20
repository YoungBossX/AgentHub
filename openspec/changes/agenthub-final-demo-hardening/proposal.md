## Why

AgentHub has crossed the original P0 demo bar, but the project baseline now
mixes P0 guardrails, P1/P2/P4 evidence, current adapter reality, and a few
stale validation caveats. This change hardens the final local demo so it can be
shown, explained, reset, and frozen without overstating it as a full IM
multi-agent collaboration platform.

## What Changes

- Reconcile baseline governance documents so `AGENTS.md`, README,
  `docs/project-state.md`, and `docs/change-log.md` describe the current local
  single-user Agent Coding Workspace reality.
- Fix the known OpenSpec strict-validation issue in the previous
  `agenthub-im-coding-mvp` change.
- Clean unrelated dirty files only when they are confirmed to be disposable or
  intentionally moved into documentation.
- Run and document a browser-driven E2E click rehearsal for the real agent path:
  requirement -> plan -> agent execution -> diff -> preview -> mock deploy.
- Preserve and reverify the forced-failure `ScriptedMockAdapter` fallback path.
- Preserve and reverify the same-session follow-up path for a narrow UI text
  change.
- Add or document a demo reset / clean seed helper workflow that safely backs up
  SQLite state, resets and seeds the local demo, and explains restore steps.
- Produce a final demo checklist and final project summary suitable for an
  interview or judge walkthrough.
- Freeze the final demo baseline after validation.

No runtime feature expansion is intended. This is a hardening, evidence, and
documentation change.

## Capabilities

### New Capabilities

- `demo-baseline-hardening`: Governance and evidence requirements for final
  AgentHub demo hardening. This is a documentation and verification capability,
  not a runtime feature expansion.

### Modified Capabilities

None. Existing runtime capability contracts remain unchanged. The work is
limited to baseline governance, demo verification, reset documentation, and
final explanatory documentation.

## Impact

- Documentation and OpenSpec artifacts:
  - `AGENTS.md`
  - `README.md`
  - `docs/project-state.md`
  - `docs/change-log.md`
  - final demo checklist / summary documents as needed
  - existing OpenSpec strict-validation wording in
    `openspec/changes/agenthub-im-coding-mvp`
- Optional scripts or docs for reset helpers if required by the implementation
  task.
- No app code changes are expected.
- No new dependencies are expected.
- Validation target for this proposal creation: `git diff --check`.

## Explicit Non-Goals

- Full IM platform.
- Multi-user collaboration.
- External Feishu, WeChat, Slack, or other IM integration.
- Provider marketplace.
- Production deploy.
- Docker sandbox.
- WebSocket or multiplayer transport.
- PR creation or patch export.
- Broad arbitrary natural-language editing.
- Enterprise approval workflow.
- Mobile-first redesign.
