## 1. Agent Runtime Configuration

- [x] 1.1 P16-1 Agent Runtime Config Model: add workspace/global runtime config persistence for planner, frontend, backend, and review defaults; include agentProfileId, providerId, adapterType, mode, enabled, fallbackPolicy where supported; preserve current default behavior when no config exists; add model/serialization tests.
- [x] 1.2 P16-2 Runtime Config API: add GET, PUT, and validate endpoints for runtime config; return effective config, selectable safe profiles/providers, config source, validation errors, and warnings; reject invalid provider/profile/role/target/mode combinations honestly; add API tests.
- [x] 1.3 P16-3 Agent Runtime Settings UI: add UI for Planner Agent, Frontend Agent, and Backend Agent settings; show provider badge, adapter type, capability tags, supported targets, supported modes, status/auth/unavailable state; allow selecting only existing safe ProviderConfig and AgentProfile options; do not add arbitrary shell command agent fields; add/update frontend tests.
- [ ] 1.4 P16-4 Runtime Config Resolution: connect runtime config to PlannerProvider selection, ProviderAssignmentMatrix, and AgentSelectionPolicy; planner uses configured planner provider, frontend uses configured frontend provider, backend uses configured backend provider, review remains review-capable and safe; preserve explicit/auditable fallback behavior; add resolution tests.
- [ ] 1.5 P16-5 Runtime Config Evidence: record resolved agentProfileId, providerId, adapterType, configSource, and fallbackReason in planner evidence, TaskRun metadata/API responses, and mission trace where appropriate; exclude secrets/protected host paths; add evidence tests.
- [ ] 1.6 P16-6 Safety And Policy Enforcement: ensure runtime config cannot bypass Target Registry, PlanValidator, scheduler locks/recovery, platform maintenance approval, or protected-path policy; ensure ordinary backend config cannot edit `apps/api`; ensure ScriptedMock remains labeled as fallback/mock; add negative policy tests.
- [ ] 1.7 P16-7 Rehearsal And Freeze Review: configure Planner = `claude_cli`, Frontend = `claude_code`, Backend = `codex`; run a bounded workflow or reuse a Breakout-style frontend workflow; verify runtime config affects actual planner/provider resolution; verify invalid config rejection; verify P6-P15b baselines; document evidence and caveats; update docs/project-state.md, docs/change-log.md, and a P16 freeze review doc.

## 2. Explicit Non-goals

- [ ] 2.1 Confirm P16 does not add a provider marketplace, arbitrary custom shell command agents, OpenCode integration, cloud token manager, production deploy, multi-user RBAC, desktop/IDE/CLI clients, full artifact editor, or new adapters.

## 3. Validation

- [ ] 3.1 Run targeted runtime config model/API/resolution/evidence/policy/UI tests added for P16.
- [ ] 3.2 Run `pnpm check`.
- [ ] 3.3 Run `pnpm test`.
- [ ] 3.4 Run `pnpm demo:api:test`.
- [ ] 3.5 Run `git diff --check`.
- [ ] 3.6 Run `openspec validate agenthub-p16-agent-runtime-configuration --strict`.
