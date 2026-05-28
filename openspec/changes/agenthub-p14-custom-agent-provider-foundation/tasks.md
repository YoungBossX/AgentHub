## 1. Custom Agent / Provider / Plugin Foundation

- [x] 1.1 P14-1 Agent Profile Registry: promote AgentProfile into a stable registry service/schema with id, displayName, avatarInitials, role, adapterType, providerId, capabilityTags, supportedTargets, supportedModes, safeForWrite, safeForReview, description, and status; preserve built-in orchestrator, frontend, backend, QA, review, and fallback profiles.
- [ ] 1.2 P14-2 Provider Config Registry: define non-secret provider config metadata for claude_code, codex, and scripted_mock; include providerId, displayName, adapterType, authStatus, available, defaultForRoles, and supportedModes; do not store secrets or implement cloud token management.
- [ ] 1.3 P14-3 Capability And Mode Schema: define controlled modes frontend, backend, qa, review, platform_maintenance, read_only, and debug; define capability tags code_write, code_review, test_run, diff_analysis, preview, deploy_staging, and platform_change; add validation helpers and regression tests.
- [ ] 1.4 P14-4 Agent Selection Policy: resolve agent/provider by explicit mention, ProviderAssignmentMatrix, role, target, capability, and safeForWrite/safeForReview; reject unsupported target/capability assignments honestly; preserve explicit fallback auditability.
- [ ] 1.5 P14-5 Agent Contact UI Upgrade: show provider badge, adapter type, capability tags, supported targets, status/auth issue/unavailable states in the existing contact UI; preserve Direct chat / Group workflow visual modes and current task controls.
- [ ] 1.6 P14-6 Safe Custom Agent Draft: allow draft AgentProfile metadata while keeping draft agents disabled or review-only until validated; reject arbitrary user-supplied shell commands, unsafe tool permissions, unrestricted filesystem access, and marketplace behavior.
- [ ] 1.7 P14-7 P14 Rehearsal And Freeze Review: verify built-in agents still work, provider-aware selection still works, backend=Codex/frontend=Claude Code metadata remains intact, invalid capability/target assignment is rejected, UI metadata is visible, and P6-P13 baselines remain intact.

## 2. Explicit Non-goals

- [ ] 2.1 Confirm P14 does not implement full provider marketplace, arbitrary custom shell command agents, OpenCode integration, cloud token manager, enterprise RBAC, multi-user agent sharing, production deploy, desktop/IDE/CLI clients, or adapter replacement.

## 3. Validation

- [ ] 3.1 Run targeted backend and frontend tests added for each P14 task.
- [ ] 3.2 Run `pnpm check`.
- [ ] 3.3 Run `pnpm test`.
- [ ] 3.4 Run `pnpm demo:api:test`.
- [ ] 3.5 Run `git diff --check`.
- [ ] 3.6 Run `openspec validate agenthub-p14-custom-agent-provider-foundation --strict`.
