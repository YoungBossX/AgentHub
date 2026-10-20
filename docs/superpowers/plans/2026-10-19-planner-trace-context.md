# Planner historical trace repair

> **For agentic workers:** Execute inline with systematic debugging, TDD and verification; the user requested completion and only the dev branch. Do not create branches, commit or push in this task.

**Goal:** Fix the actual live follow-up failure, then collect new real-provider evidence for resume wording.

**Architecture:** Separate the full UI trace from a bounded Planner history projection. Never replay streamed event payloads; expose counts and known task/run/artifact identities, states, errors and blockers. Keep the existing 200,000-character final gate and mandatory input intact.

**Tech Stack:** Existing FastAPI, SQLModel, SQLite and Claude Code CLI; no dependencies.

**Spec:** `openspec/changes/agenthub-final-context-budget/specs/final-context-budget/spec.md`, task 1.2.

## Constraints and review focus

- Work in the clean primary dev checkout to honor the user's branch consolidation; use only E:/Docker for new evidence and temporary data.
- No product database migration, deletion, Provider setting rewrite or historical receipt rewrite.
- Many events must not expand Planner text; full UI trace must retain them.
- Large nested task/artifact telemetry must not leak into the summary.
- Active/failed work takes selection priority over completed history; omitted rows and shortened summary text must be counted.
- Keep current user request, frozen rules, explicit references and pins unchanged.
- A frozen real-provider batch may use a dirty source fingerprint; do not edit runtime sources during the batch, mix old/new results, hide failures, or claim token/cost/model identity not observed.

## Task 1: Historical trace projection and live evidence

Files: `apps/api/app/mission_trace.py`, new `apps/api/app/planner_trace_context.py`, `apps/api/app/llm_planner.py`, `apps/api/app/context_budget.py`, existing API tests, and verification docs.

- [ ] Add production-input regression tests using real SQLite rows and many events, large nested metadata, selection overflow and failed work; watch them fail before implementation.
- [ ] Add `build_planner_mission_trace(db, session_id)` and switch only Planner history to it. Full trace defaults remain unchanged; omit raw event loads in the projection. Add missionTrace source accounting.
- [ ] Run the focused tests and reconstruct the original failed SQLite copy offline; record before/after character counts and source immutability.
- [ ] Run relevant regressions, root checks and the full project test command. Preserve any environmental failures separately.
- [ ] Run one fresh live follow-up first; only then run a fresh frozen full cohort with bounded retries and independent acceptance. Retain every attempt and fault injection labels.
- [ ] Inventory prior project junk, remove only validated generated caches without touching backups, original failure evidence, worktrees or product data; write a cleanup receipt.
- [ ] Record verified metrics and four copy-ready resume bullets with denominators and limits. Update change-log, project-state and task checkbox only after verification.

## Diagnostic evidence

E:/Docker/AgentHub/live-fixes-20261019/diagnostic-before.json: copied original failing database; input540,911 characters on rebuilt current source, missionTrace496,381, events462,832. Prior recorded failure540,541 differs because the rebuilt trace includes subsequent failure metadata. The source SQLite hash stayed unchanged.
