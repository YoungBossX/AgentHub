## 1. Real Coding Assistant Upgrade

- [x] 1.1 P15-1 LLM Planner v1: add planner mode `llm_v1`; build planner input from original user request, CanonicalSharedContext, Target Registry, Project Analyzer metadata, recent messages, artifact references, and guardrails; parse structured PlanDraft JSON; validate through PlanValidator before creating tasks; record planner mode/fallback reason; do not fake LLM planner success.
- [x] 1.2 P15-2 Passthrough Instruction Mode: add `passthrough_v1` provider instruction behavior for `llm_v1` plans; preserve original user request and task description; avoid demo-slot rewrite unless deterministic fallback is selected; include target context, allowed paths, validation commands, artifact/handoff context, acceptance criteria, and guardrails for Claude Code and Codex wrappers.
- [ ] 1.3 P15-3 Permissive Target Guardrails: allow meaningful read/write work inside registered target `allowedPaths`; keep `.git`, `.env`, secrets, `node_modules`, `.venv`, paths outside selected target/worktree, production deploy, unapproved network access, and ordinary platform-code modification denied; preserve platform maintenance approval flow.
- [ ] 1.4 P15-4 Project Command Policy: derive allowed validation commands from Target Registry, Project Analyzer, and explicit target config; support configured pnpm/npm/pytest-style test/build/lint/dev/check commands; record stdout, stderr, exit code, target ID, command, and status as honest command evidence.
- [ ] 1.5 P15-5 Planner Rationale And Task Review Metadata: expose planner mode, rationale, task breakdown, assigned role, target, dependencies, planned files, acceptance criteria, and validation expectations through API/UI surfaces; keep plan review read-only unless existing safe adjustment actions already support changes.
- [ ] 1.6 P15-6 Breakout Game Real Coding Smoke: run the final acceptance request in a registered frontend target; require `llm_v1` or `passthrough_v1` frontend task; preserve the original Breakout request in provider instruction; use real ClaudeCodeAdapter or CodexAdapter if auth/quota permits; verify diff, review, build/check, preview, staging deploy, and browser playability; record exact provider error if blocked; do not use ScriptedMock to claim Breakout success.
- [ ] 1.7 P15-7 P15 Freeze Review: verify P15 real coding assistant behavior, Breakout evidence or honest provider blockage, deterministic demo fallback preservation, ScriptedMock fallback labeling, Target Registry policy, scheduler locks/recovery, provider assignment, Agent Selection Policy, review/preview/staging deploy evidence, and P6-P14 baseline preservation.

## 2. Explicit Non-goals

- [ ] 2.1 Confirm P15 does not implement a hardcoded Breakout planner template, provider marketplace, user-created arbitrary command agents, production deploy, cloud provider integration, multi-user IM, desktop/IDE/CLI clients, full artifact editor, scheduler replacement, or removal of deterministic demo fallback.

## 3. Validation

- [ ] 3.1 Run targeted planner, instruction, guardrail, command policy, metadata, and Breakout smoke tests added for P15.
- [ ] 3.2 Run `pnpm check`.
- [ ] 3.3 Run `pnpm test`.
- [ ] 3.4 Run `pnpm demo:api:test`.
- [ ] 3.5 Run `git diff --check`.
- [ ] 3.6 Run `openspec validate agenthub-p15-real-coding-assistant-upgrade --strict`.
