## 1. Cross-provider Agent Coordination

- [x] 1.1 P13-1 Provider Assignment Matrix: add explicit provider assignment configuration for orchestrator, frontend, backend, QA, and review roles; support target-specific assignment where needed; preserve existing default adapter behavior when no assignment is configured; expose assignment evidence through TaskRun metadata, API responses, and tests.
- [x] 1.2 P13-2 Provider-aware Agent Profile: extend the P12 AgentProfile foundation with provider_id, adapter_type, supported_roles, supported_targets, supported_modes, safe_for_write, and safe_for_review; map existing built-in agents to profile/provider assignments; update API/frontend profile tests without adding user-created custom agents UI.
- [x] 1.3 P13-3 Canonical Context Usage Enforcement: ensure CodexAdapter and ClaudeCodeAdapter instructions are rendered from CanonicalSharedContext; include session goal, recent messages, task graph, appContract, target metadata, upstream artifacts, handoff artifacts, validation commands, and guardrails where available; verify protected paths/secrets are filtered.
- [ ] 1.4 P13-4 Handoff Protocol v1: extend handoff artifact metadata for backend-to-frontend, frontend-to-review, and review-to-fix transitions with provider, adapter_type, taskRunId, changedFiles, implemented routes/components, artifact refs, open questions, warnings, and verification status; include provider-aware handoffs in downstream canonical context and mission trace.
- [ ] 1.5 P13-5 Provider-specific Instruction Mapping: add regression coverage proving Codex and Claude Code instructions derived from the same canonical context preserve the same contract, target, handoff, validation, and guardrail facts while allowing provider-specific formatting differences.
- [ ] 1.6 P13-6 Cross-provider Evidence Normalization: normalize provider identity, run status, errors, logs/event summaries, changed files, diff metadata, review metadata, preview evidence, and staging deploy evidence; preserve real provider identity; ensure failed provider runs are not masked unless fallback is explicitly recorded.
- [ ] 1.7 P13-7 Mixed-provider Scheduler Integration: verify scheduler dependencies, target locks, recovery states, retry/fallback metadata, and staging deploy prerequisites work when backend and frontend tasks use different providers; add tests for backend=Codex and frontend=Claude Code task graphs.
- [ ] 1.8 P13-8 Mixed-provider Rehearsal and Freeze Review: run or simulate one bounded workflow with backend=codex and frontend=claude_code; verify shared contract, provider assignments, handoffs, diff/review/preview/staging deploy evidence, and P6-P12 baseline preservation; if a real provider is blocked by auth/quota/runtime, record the exact normalized error and do not claim success.

## 2. Explicit Non-goals

- [ ] 2.1 Confirm P13 does not implement provider marketplace, OpenCode integration, user-created custom agents UI, multi-user IM, desktop/mobile clients, production deploy, distributed worker cluster, full autonomous free-form agent negotiation, or scheduler replacement with LangGraph/CrewAI.

## 3. Validation

- [ ] 3.1 Run `pnpm check`.
- [ ] 3.2 Run `pnpm test`.
- [ ] 3.3 Run targeted backend/frontend tests added for each P13 task.
- [ ] 3.4 Run `git diff --check`.
- [ ] 3.5 Run `openspec validate agenthub-p13-cross-provider-agent-coordination --strict`.
