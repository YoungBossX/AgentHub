## 1. Final Demo Hardening Tasks

- [x] 1.1 P4-1 Baseline governance cleanup.
  - Objective: Make the repository's written baseline match the current
    implementation reality while preserving safety boundaries.
  - Scope:
    - update `AGENTS.md` to reflect current adapter reality, including Codex,
      `ScriptedMockAdapter`, and the existing `ClaudeCodeAdapter` option;
    - align README, `docs/project-state.md`, and `docs/change-log.md`;
    - fix the known OpenSpec strict validation issue in
      `openspec/changes/agenthub-im-coding-mvp/specs/worktree-diff/spec.md`;
    - clean unrelated dirty files only when they are clearly disposable or
      explicitly documented.
  - Acceptance criteria:
    - docs no longer contradict current adapter behavior;
    - the local single-user Agent Coding Workspace positioning is explicit;
    - fallback-based P0 demo path remains documented;
    - `openspec validate agenthub-im-coding-mvp --strict` passes or any
      remaining issue is documented with a concrete reason;
    - no app code is changed.
  - Validation:
    - `git diff --check`;
    - OpenSpec strict validation for the fixed change.

- [x] 1.2 P4-2 Browser E2E click rehearsal.
  - Objective: Verify the final demo through the browser UI as far as local
    permissions allow.
  - Scope:
    - start the API and web app using documented commands;
    - create or select a clean session;
    - send `@orchestrator build a login page for the demo app`;
    - trigger UI-driven agent execution;
    - inspect diff, start preview, open iframe, and create mock deploy card;
    - reload and confirm persisted messages, runs, and artifacts remain visible;
    - record evidence IDs, URLs, screenshots if available, and caveats.
  - Acceptance criteria:
    - real agent path is verified from UI interaction, or any blocked portion is
      documented precisely;
    - diff, preview, and mock deploy surfaces are verified;
    - no unverified behavior is claimed;
    - no app code is changed.
  - Validation:
    - browser rehearsal notes;
    - `git diff --check`.

- [x] 1.3 P4-3 Demo reset / clean seed helper.
  - Objective: Make the final demo reset safe and repeatable.
  - Scope:
    - define or add a helper workflow that backs up SQLite before reset;
    - reset the DB using the existing initialization path;
    - seed clean demo state or document the exact manual clean-session setup;
    - document restore method;
    - avoid deleting git worktrees by default unless explicitly proven safe.
  - Acceptance criteria:
    - reset workflow has backup and restore instructions;
    - clean demo setup can be repeated from docs;
    - dependency installation is not run during agent execution;
    - no app feature behavior is changed.
  - Validation:
    - reset rehearsal or documented dry run;
    - `git diff --check`.

- [ ] 1.4 P4-4 Final demo checklist.
  - Objective: Produce the final evidence checklist for the judge/demo path.
  - Scope:
    - real agent path;
    - fallback path;
    - follow-up path;
    - diff, preview, and mock deploy evidence;
    - reload/SSE recovery evidence or caveats;
    - validation commands and results.
  - Acceptance criteria:
    - checklist distinguishes verified, partial, fallback, and not-verified
      items;
    - evidence IDs are recorded where available;
    - mock deploy is labeled as mock;
    - remaining limitations are plain.
  - Validation:
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`.

- [ ] 1.5 P4-5 Final project summary / interview explanation.
  - Objective: Create a concise explanation of what AgentHub is, how it works,
    and where it stops.
  - Scope:
    - architecture summary;
    - adapter model summary;
    - artifact pipeline summary;
    - session worktree isolation summary;
    - limitations and deferred platform scope.
  - Acceptance criteria:
    - summary positions AgentHub as a local single-user Agent Coding Workspace /
      strong demo MVP;
    - it explains why the full IM platform remains only partially complete;
    - it names non-goals and limitations without apologizing or overclaiming;
    - it is suitable for interview or judge narration.
  - Validation:
    - doc review against current README, project state, and P4 evidence;
    - `git diff --check`.

- [ ] 1.6 P4-6 Final freeze review.
  - Objective: Freeze the final demo baseline after hardening.
  - Scope:
    - verify P4-1 through P4-5 are complete;
    - ensure docs agree with each other;
    - confirm no app-code feature expansion was introduced;
    - confirm fallback-based P0 path remains intact;
    - record validation commands;
    - leave commit/tag/push decisions to the user.
  - Acceptance criteria:
    - all tasks above are checked only after verification;
    - final docs and checklists are internally consistent;
    - dirty files are either expected artifacts or explicitly documented;
    - no commit or push is performed unless the user asks.
  - Validation:
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - relevant OpenSpec validation.

## 2. Explicit Non-Goals

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

## 3. Definition Of Done

- The final demo can be explained as a local single-user Agent Coding Workspace
  with a verified coding-agent loop.
- Real agent, fallback, and follow-up paths have current evidence or clearly
  documented caveats.
- Baseline docs no longer contradict current adapter reality.
- Demo reset and restore instructions are safe enough for repeated rehearsals.
- Validation command results are recorded.
- No app code changes, commits, or pushes are made without explicit user
  request.
