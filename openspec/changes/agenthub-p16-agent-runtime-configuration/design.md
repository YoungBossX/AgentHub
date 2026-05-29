## Context

P6-P15b moved AgentHub from a narrow local demo into a target-aware coding
workspace with real planner/coding provider evidence. The backend already has
AgentProfile, ProviderConfig, ProviderAssignmentMatrix, AgentSelectionPolicy,
Target Registry, scheduler/recovery, CanonicalSharedContext, planner evidence,
TaskRun evidence, mission trace, and staging deploy artifacts.

The remaining usability gap is configuration. A user can see providers and
agent profiles, but cannot safely choose which existing profile/provider should
serve as Planner, Frontend, or Backend at runtime. Today those choices are
mostly environment variables or internal defaults. P16 adds a controlled
runtime settings layer without opening arbitrary custom agents, shell command
agents, marketplace installs, or secret management.

## Goals / Non-Goals

**Goals:**

- Define a workspace-level or global-level Agent Runtime Config model.
- Configure planner, frontend, backend, and review role defaults using existing
  safe AgentProfile and ProviderConfig records.
- Expose read, update, and validation APIs.
- Add UI controls for Planner Agent, Frontend Agent, and Backend Agent.
- Resolve runtime config into PlannerProvider selection, ProviderAssignmentMatrix
  behavior, AgentSelectionPolicy, TaskRun metadata, planner evidence, and
  mission trace.
- Preserve defaults when no config exists.
- Reject invalid profile/provider/role/target combinations before execution.

**Non-Goals:**

- Full provider marketplace.
- Arbitrary custom shell command agents.
- OpenCode integration.
- Cloud token manager or plaintext secret storage.
- Production deploy.
- Multi-user RBAC.
- Desktop, IDE, or CLI clients.
- Full artifact editor.
- Replacing AgentAdapter, PlannerProvider, scheduler, or Target Registry.

## Decisions

### Decision: Runtime Config Is A Validated Selection Layer

P16 should add a small runtime configuration model rather than replacing
ProviderAssignmentMatrix or AgentSelectionPolicy. Runtime config chooses among
existing profiles/providers; the existing policy stack remains authoritative
for target, capability, mode, and safety checks.

Alternatives considered:

- Store only environment variables. This is simpler but keeps configuration
  invisible and hard to validate through UI/API.
- Let users enter arbitrary commands. This would bypass P14 safety boundaries
  and is out of scope.

### Decision: Scope Starts With Workspace-Level Config

The first implementation should prefer workspace-level config, with a global
default fallback if the existing model makes that simpler. Session-specific
overrides are deferred. Workspace scope matches the current local single-user
product and avoids multi-user preference semantics.

Each role config should include:

- `agentProfileId`;
- `providerId`;
- `adapterType`;
- `mode`;
- `enabled`;
- `fallbackPolicy` when supported.

### Decision: Planner Config Maps To PlannerProvider, Not AgentAdapter

Planner runtime config must resolve to the planner provider abstraction
introduced in P15b. For example, Planner = `claude_cli` selects the real LLM
planner provider path. Coding roles still resolve through AgentProfile,
ProviderConfig, ProviderAssignmentMatrix, and AgentSelectionPolicy.

This keeps planning and coding execution semantics separate.

### Decision: UI Selects Only Valid Existing Options

The settings UI should render selectable rows/cards from existing
AgentProfile/ProviderConfig data. It should show provider badge, adapter type,
capability tags, supported targets, supported modes, status, and auth/available
state. The UI should not expose arbitrary command inputs, secret fields, or
custom tool permission editing.

### Decision: Runtime Config Evidence Is Auditable

Resolution should record `agentProfileId`, `providerId`, `adapterType`,
`configSource`, and `fallbackReason` when applicable. Evidence should appear in
the most natural existing surfaces:

- planner evidence for Planner role;
- TaskRun metrics/provider assignment for Frontend/Backend/Review roles;
- mission trace task/run entries;
- API responses where task/run metadata is already returned.

Fallback must be explicit. The system must not silently substitute ScriptedMock
or another provider and present it as real Claude/Codex success.

### Decision: Invalid Config Fails Before Use

PUT/validate should reject mismatches such as:

- frontend role configured with a backend-only profile;
- backend role configured for a provider/profile that cannot write to backend
  targets;
- planner role configured with a coding-only adapter instead of a planner
  provider;
- disabled or unavailable provider selected as enabled without an explicit
  fallback policy;
- platform maintenance mode implied by ordinary backend config.

Runtime use should also revalidate, because provider/profile availability may
change between configuration and execution.

## Risks / Trade-offs

- **Risk: Config duplicates ProviderAssignmentMatrix behavior.** Mitigation:
  runtime config resolves into the existing assignment/policy path and does not
  become an independent dispatch engine.
- **Risk: User-selected provider bypasses target safety.** Mitigation:
  AgentSelectionPolicy, Target Registry, PlanValidator, scheduler locks, and
  platform maintenance approval remain mandatory.
- **Risk: Provider auth status is uncertain.** Mitigation: represent auth or
  availability as metadata/evidence; fail honestly at execution time if the
  provider is not usable.
- **Risk: Fallback hides real provider failure.** Mitigation: fallback policy
  must be explicit and evidence must record fallback reason/source.
- **Risk: UI implies marketplace/custom agents.** Mitigation: settings choose
  only from existing safe built-in profiles/providers and draft-safe metadata.

## Migration Plan

1. Add runtime config persistence and default resolution with no behavior
   change when no config exists.
2. Add API endpoints and validation errors.
3. Add UI settings using existing profile/provider metadata.
4. Connect config resolution to planner and coding provider paths.
5. Add evidence in planner/task/run/mission trace responses.
6. Rehearse Planner = `claude_cli`, Frontend = `claude_code`, Backend =
   `codex`; verify invalid config rejection and baseline preservation.

Rollback strategy: delete or disable runtime config rows and fall back to the
current environment/default provider behavior.

## Open Questions

- Should the first persistence model be workspace-scoped only, or include a
  nullable global config row for future multi-workspace support?
- Should Review Agent configuration be in the first UI or API-only for P16?
- Should unavailable provider auth state block saving config or only block
  execution?
