## 1. Conversational Orchestrator Routing

- [x] 1.1 P17-1 ConversationOutcome Schema: define and test a structured routing outcome with `assistant_reply`, `task_plan`, `clarification`, `refusal`, `approval_required`, and `unsupported`; include reply text, plan draft, risk level, reason, planner provider, validation result, and fallback/error metadata; keep planner provider/config evidence separate from coding agent provider/config evidence.
- [x] 1.2 P17-2a Retire Legacy Signal Gates from Primary Routing: ensure `_is_safe_demo_frontend_request`, `_is_safe_external_frontend_request`, `_is_passthrough_frontend_request`, and `_is_unsupported_broad_request` do not remain primary gates after an LLM Router returns `task_plan`; route `task_plan` directly into ConversationOutcome schema validation, PlanDraft schema validation, and PlanValidator; keep legacy deterministic/demo routing only as fallback.
- [x] 1.3 P17-2b Implement LLM-first Orchestrator Entry: route no-mention and `@orchestrator` messages to one LLM Orchestrator provider call that returns a single `ConversationOutcome`; resolve the Conversation Router through the configured Planner runtime; do not invoke Claude Code, Codex, or other coding agents for normal chat; keep `@frontend`, `@backend`, `@qa`, and `@review` as explicit assignment shortcuts.
- [x] 1.4 P17-3 Conversational Reply Path: persist `orchestrator` sender reply messages for pure chat such as `你好` and `你能做什么`; ensure no task or TaskRun is created for pure chat; ensure pure chat does not invoke coding agent runtimes; preserve chat stream and SSE behavior where applicable; do not introduce a new sender type.
- [ ] 1.5 P17-4 Task Plan Path: convert programming requests into validated PlanDraft/task graph outcomes from the same ConversationOutcome call; require PlanValidator before task creation; keep Target Registry, roles, dependencies, approval, and command policy authoritative; after validation/scheduling, resolve frontend/backend/review tasks through configured P16 runtime agent providers; avoid hardcoded Breakout/login regex as primary behavior.
- [ ] 1.6 P17-5 Clarification, Refusal, And Approval Outcomes: ambiguous requests create `orchestrator` clarification replies; unsafe target-outside requests create `orchestrator` refusal replies; platform maintenance or high-risk requests produce approval-required outcomes without bypassing guardrails.
- [ ] 1.7 P17-6 Follow-up Routing Context: route follow-up messages through the same LLM router with recent messages, CanonicalSharedContext, mission trace, selected artifact, latest diff/review/build/preview/deploy evidence, active tasks, and current goal; do not limit LLM routing to empty sessions.
- [ ] 1.8 P17-7 Friendly Fallback: when LLM routing is disabled, unavailable, invalid, or blocked by auth/quota/runtime, pure chat returns a friendly `orchestrator` reply; clear safe frontend coding intent may create one audited passthrough frontend task with `plannerSource: fallback`; backend/platform/high-risk/ambiguous requests ask clarification, require approval, or refuse; never return a demo-boundary rejection for normal chat.
- [ ] 1.9 P17-8 Rehearsal And Freeze Review: verify `你好` -> `orchestrator` assistant reply/no task/no coding agent invocation, `你能做什么` -> `orchestrator` assistant reply/no task/no coding agent invocation, `帮我做打砖块` -> LLM `task_plan` with no demo signal gate rejection, LLM `task_plan` enters PlanValidator directly, legacy signal gates do not block LLM `task_plan`, Planner provider evidence is recorded separately from coding agent provider evidence, LLM disabled + clear safe frontend coding request may create audited fallback passthrough task, LLM disabled + pure chat returns friendly reply, unsafe request returns refusal or approval_required, and follow-up goes through LLM Router with session/artifact context; verify P6-P16 baselines; document evidence and caveats.

## 2. Explicit Non-goals

- [ ] 2.1 Confirm P17 does not remove Target Registry, remove PlanValidator, remove scheduler/recovery, replace ClaudeCodeAdapter or CodexAdapter, make Claude Code/Codex handle normal chat directly, add arbitrary shell-command agents, add full multi-user IM, add artifact editor, add provider marketplace, or add production deploy.

## 3. Validation

- [ ] 3.1 Run targeted conversational router/schema/reply/plan/fallback/follow-up tests added for P17.
- [ ] 3.2 Run `pnpm check`.
- [ ] 3.3 Run `pnpm test`.
- [ ] 3.4 Run `pnpm demo:api:test`.
- [ ] 3.5 Run `git diff --check`.
- [ ] 3.6 Run `openspec validate agenthub-p17-conversational-orchestrator-routing --strict`.
