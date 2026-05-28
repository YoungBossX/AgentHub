## 1. Real LLM Planner Engine

- [x] 1.1 P15b-1 Planner Provider Abstraction: define PlannerProvider interface and provider result/error types; add disabled and fake/test providers; add explicit provider selection config; record selected provider in planner metadata; preserve deterministic fallback when planner is disabled.
- [x] 1.2 P15b-2 Planner Request / Response Contract: add PlannerRequest and PlannerResponse models; include original request, CanonicalSharedContext summary, Target Registry summary, Project Analyzer summary, recent messages, artifact references, supported roles/modes/capabilities, and guardrails; exclude secrets/protected host paths; define required PlanDraft fields.
- [x] 1.3 P15b-3 Real Planner Provider Implementation: implement one real provider path, either Claude CLI planner, Claude API planner, or OpenAI API planner; handle timeout, stderr, non-zero exit, auth/quota failure, runtime failure, invalid output, and unavailable provider; do not store secrets in plain text and do not fake success.
- [x] 1.4 P15b-4 Structured Output Parsing And Validation: safely extract JSON from provider output; validate schema; normalize only safe fields; reject ambiguous, malformed, unsafe, or incomplete output; never create tasks directly from unvalidated LLM output.
- [ ] 1.5 P15b-5 PlanValidator Hardening For Real LLM Output: validate targets, roles, capabilities, supported modes, allowed paths, denied paths, dependency graph, platform maintenance mode, approval requirements, and command policy; unsafe plans must enter honest failed/fallback/clarification state and must not auto-start.
- [ ] 1.6 P15b-6 Planner Evidence And Mission Trace: record planner provider, planner source, duration, validation result, fallback reason, error summary, plan rationale, created task IDs, and safe evidence metadata; expose planner source as `real_llm`, `fake_test`, `disabled`, `deterministic`, or `fallback` without leaking secrets.
- [ ] 1.7 P15b-7 Real LLM Planner Breakout Rehearsal And Freeze Review: run the Breakout request with a real LLM planner provider producing the task plan; verify the plan is not hardcoded and not fake; execute through existing passthrough and ClaudeCodeAdapter or CodexAdapter if auth/quota permits; verify diff, review, build/check evidence, preview, staging deploy; document exact planner/coding provider errors if blocked; update freeze review docs.

## 2. Explicit Non-goals

- [ ] 2.1 Confirm P15b does not replace ClaudeCodeAdapter or CodexAdapter, replace the scheduler, add provider marketplace, add user-created arbitrary command agents, add production deploy, add cloud token manager, add multi-user IM, add desktop/IDE/CLI clients, or add a hardcoded Breakout planner template.

## 3. Validation

- [ ] 3.1 Run targeted planner provider, request/response, parsing, validation, evidence, and fallback tests added for P15b.
- [ ] 3.2 Run `pnpm check`.
- [ ] 3.3 Run `pnpm test`.
- [ ] 3.4 Run `pnpm demo:api:test`.
- [ ] 3.5 Run `git diff --check`.
- [ ] 3.6 Run `openspec validate agenthub-p15b-real-llm-planner-engine --strict`.
