# P15 Freeze Review: Real Coding Assistant Upgrade

**Date:** 2026-05-28

## Decision

P15 is ready to freeze.

AgentHub now behaves less like a narrow demo-template runner and more like a
real target-scoped coding assistant for registered frontend projects. The
final acceptance target, a Breakout / brick breaker game, was implemented by a
real `ClaudeCodeAdapter` run through AgentHub orchestration.

## Verified Scope

- `llm_v1` planner foundation exists and validates structured PlanDraft JSON
  before task creation.
- Deterministic planner fallback remains available and records fallback reason
  instead of claiming LLM planner success.
- `passthrough_v1` provider instructions preserve the original user request
  and avoid old login-page/button/demo-slot rewrites.
- Target guardrails allow meaningful changes inside registered target
  `allowedPaths` while preserving protected path denial.
- Target-scoped command policy records honest command evidence.
- Task cards expose read-only planner rationale and task review metadata.
- Breakout smoke verified real `claude_code` execution, diff, review, build,
  preview, and local staging deploy evidence.

## Breakout Evidence

Detailed evidence is recorded in `docs/p15-breakout-smoke.md`.

Key IDs:

| Item | Value |
|---|---|
| Session ID | `901ae011-a095-489e-b0f4-72c6c1a27187` |
| Message ID | `93972c24-3cb4-40cb-a7bc-eba9789596cb` |
| Task ID | `e6b6d537-5787-413a-944c-b456025bf905` |
| TaskRun ID | `8d719899-8042-49b0-8e26-79d065841a3c` |
| Adapter | `claude_code` |
| Planner / instruction mode | `passthrough_v1` |
| Diff artifact ID | `96b576ec-d673-49b7-a461-78e937f219b8` |
| Review artifact ID | `706265e5-91dc-4d90-a309-b0ca7c4700ad` |
| Build evidence artifact ID | `7dddb098-3e84-48c5-9855-4f2479a865f0` |
| Preview | `68d04a67-99d1-4fdb-8bfb-5ba584ae6f6c`, healthy at `http://127.0.0.1:50086` |
| Local staging deploy | `1747ed90-9999-4919-bfac-8b4cdfea13a4`, ready at `http://127.0.0.1:50424` |

Changed files:

- `apps/demo/src/App.tsx`
- `apps/demo/src/styles.css`
- `apps/demo/src/BreakoutGame.tsx`

## Non-goals Confirmed

P15 did not implement:

- hardcoded Breakout planner template;
- provider marketplace;
- user-created arbitrary command agents;
- production deploy;
- cloud provider integration;
- multi-user IM;
- desktop, IDE, or CLI clients;
- full artifact editor;
- scheduler replacement;
- removal of deterministic demo fallback.

## Remaining Caveats

- `llm_v1` planner execution remains a foundation and is disabled by default;
  P15 acceptance used `passthrough_v1`.
- Browser-click playability was not automated because browser automation was
  not available and Playwright is not installed in the workspace.
- Review evidence remains deterministic scripted review, not real Claude
  review.
- The Breakout smoke used the built-in `demo-frontend` target, not an external
  project target.

## Recommended Tag

`p15-real-coding-assistant-upgrade-freeze`
