## Context

The latest reassessment and P4-0 audit show that AgentHub is best described as a
local single-user Agent Coding Workspace / strong demo MVP. The verified core
loop is:

```text
requirement -> plan -> agent execution -> diff -> preview -> mock deploy
```

Evidence exists for:

- real local agent execution through `claude_code`;
- the forced Codex failure plus `ScriptedMockAdapter` fallback path;
- a same-session follow-up text-change path;
- persisted diff, preview, and mock deployment artifacts.

The remaining risk is not missing product surface for the demo. The risk is
baseline drift: old P0 guardrails say one thing, current code and docs say
another, and the final walkthrough still needs a browser-click rehearsal,
repeatable reset story, and crisp explanation of what AgentHub is and is not.

## Goals

- Make the repository's governance documents match the current implementation
  without hiding the original P0 fallback path.
- Keep the final project identity honest: local single-user Agent Coding
  Workspace, not a full Feishu/WeChat-style collaboration platform.
- Verify the final demo from the browser UI where possible, not only through
  backend API calls.
- Make demo reset and restore safe, explicit, and repeatable.
- Capture a concise final checklist with real-agent, fallback, follow-up, and
  validation evidence.
- Prepare a final architecture and interview explanation that names limitations
  plainly.

## Non-Goals

- Do not modify app code as part of this hardening proposal unless a later task
  explicitly discovers a blocker that cannot be solved by docs, reset workflow,
  or verification.
- Do not implement full IM collaboration, multi-user presence, external chat
  integrations, production deployment, provider marketplace, Docker sandbox,
  WebSocket/multiplayer transport, PR creation, broad arbitrary editing, or
  enterprise approval flows.
- Do not claim browser automation success unless a real browser click rehearsal
  is actually performed.
- Do not claim real deployment success when the deploy card is mock-backed.

## Design Approach

### 1. Baseline Governance Cleanup

Treat current implementation reality as the baseline:

- P0 fallback path remains preserved and demo-safe.
- P1/P2/P4 additions such as `ClaudeCodeAdapter` and
  `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code` are current reality, not future
  speculation.
- The project should be described as a local single-user demo MVP with strong
  evidence, not a complete IM collaboration product.

The cleanup should update stale guardrail language without loosening important
safety boundaries:

- keep no WebSocket, no Docker sandbox, no provider marketplace, no production
  deploy, no external IM integrations, and no broad platform expansion;
- keep the fallback-based P0 path explicit;
- keep command/path/network guardrails explicit.

The known strict OpenSpec issue should be fixed by changing the invalid
`SHOULD` requirement wording in the old change to a strict-compatible form or
otherwise restructuring that requirement so `openspec validate` can pass.

### 2. Browser E2E Click Rehearsal

The rehearsal should prefer a real browser UI path:

1. Start API and web app using documented commands.
2. Open AgentHub in the browser.
3. Create or select a clean session.
4. Send `@orchestrator build a login page for the demo app`.
5. Start a real agent run from the UI.
6. Verify visible task state progression.
7. Inspect the diff card from the UI.
8. Start preview from the UI and confirm the iframe displays the updated Vite
   app.
9. Create the mock deploy card from the UI.
10. Reload and confirm persisted messages, tasks, runs, and artifacts remain
    visible.

If automated browser control is blocked by local permissions, the task must
state that clearly and document exactly which parts were verified manually,
through UI-facing endpoints, or not verified.

### 3. Demo Reset / Clean Seed Helper

The reset workflow must be non-destructive by default:

- back up `apps/api/data/agenthub.sqlite3` before resetting;
- record enough metadata to restore the prior state;
- run the existing DB initialization/seed path;
- create or document a clean demo session seed if that can be done without
  app-code changes;
- avoid deleting registered git worktrees unless the implementation task
  explicitly proves the cleanup is safe;
- document restore instructions.

If a helper script is added later, it should use existing project conventions
and should not silently install dependencies.

### 4. Final Checklist And Summary

The checklist should be evidence-first:

- real agent path;
- fallback path;
- follow-up path;
- browser/UI verification level;
- SSE/reload recovery level;
- diff, preview, and mock deploy evidence;
- validation commands;
- remaining caveats.

The final project summary should explain:

- frontend, backend, persistence, and execution architecture;
- adapter model and why fallback exists;
- artifact pipeline from TaskRun events to diff/preview/deploy cards;
- isolation model with session worktrees;
- what is intentionally deferred.

### 5. Final Freeze Review

The freeze review should verify that:

- hardening tasks are complete and checked off;
- final docs agree with each other;
- fallback-based P0 demo remains intact;
- validation commands were run and recorded;
- no accidental app-code feature expansion landed;
- any remaining dirty files are explained;
- the baseline is ready to tag or archive if the user asks later.

## Risks And Mitigations

- **Browser automation may be blocked locally.** Mitigate with an honest manual
  browser rehearsal record and UI-facing API evidence, without claiming
  automated clicks.
- **Real agent execution depends on local CLI auth, quota, and availability.**
  Mitigate by preserving the ScriptedMockAdapter fallback path and documenting
  when the real path was or was not used.
- **Reset helpers can destroy useful local evidence.** Mitigate with backups,
  restore instructions, and no destructive worktree cleanup by default.
- **Documentation drift can continue.** Mitigate by making P4-1 update all
  baseline docs in one pass and using final freeze review as a consistency
  check.

## Validation

For this proposal creation:

```bash
git diff --check
```

Implementation tasks may additionally run:

```bash
pnpm check
pnpm test
openspec validate agenthub-im-coding-mvp --strict
openspec validate agenthub-final-demo-hardening --strict
```

Browser rehearsal validation must be documented with evidence IDs, screenshots,
or explicit caveats.
