# P17 Conversational Orchestrator Routing Freeze Review

**Date:** 2026-05-29

## Decision

P17 is ready to freeze.

AgentHub now routes no-mention and `@orchestrator` messages through a
ConversationOutcome-first Orchestrator boundary. Normal chat can produce an
`orchestrator` reply without creating tasks, while programming requests can
produce a validated `task_plan` that flows into PlanValidator and the existing
scheduler/execution path.

## Evidence

- `你好` can produce an `orchestrator` assistant reply with no Task or TaskRun.
- `你能做什么` uses the same non-task reply path through
  `assistant_reply` outcomes.
- `ConversationOutcome(task_plan)` creates validated task graph entries through
  the LLM planner path.
- LLM `task_plan` outcomes bypass legacy signal gates such as
  `_is_safe_demo_frontend_request`, `_is_safe_external_frontend_request`,
  `_is_passthrough_frontend_request`, and `_is_unsupported_broad_request`.
- Clarification, refusal, and approval-required outcomes create
  `orchestrator` messages and no executable tasks.
- Follow-up messages are no longer limited to empty sessions and include
  CanonicalSharedContext plus mission trace context.
- Disabled/unavailable LLM routing returns friendly chat fallback for pure chat
  and audited `plannerSource: fallback` metadata for safe frontend fallback
  tasks.

## Runtime Boundary

P17 keeps the Conversation/Planner LLM separate from coding agents:

- Planner runtime handles intent classification, assistant replies,
  clarification, refusal, approval-required outcomes, and PlanDraft generation.
- Frontend, Backend, QA, and Review coding agents only run after a validated
  task plan reaches the scheduler.
- Normal chat does not invoke Claude Code, Codex, ScriptedMock, or another
  coding runtime.

## Validation

| Command | Result |
|---|---|
| P17 targeted conversational router/schema/reply/plan/fallback/follow-up tests | Pass: 44 tests. |
| `pnpm check` | Pass. |
| `pnpm test` | Pass: web 44 tests, API 319 tests, demo-api 5 tests. |
| `pnpm demo:api:test` | Pass: 5 tests. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p17-conversational-orchestrator-routing --strict` | Pass. |

## Caveats

- P17 does not add the full model settings UI; it uses existing P16 runtime
  configuration where available.
- P17 does not run a new real Claude/Codex coding smoke; it preserves the
  existing P15b/P16 execution baseline and verifies routing through tests.
- Deterministic/demo routing remains as fallback, not as the primary
  no-mention Orchestrator gate.

## Recommended Tag

`p17-conversational-orchestrator-routing-freeze`
