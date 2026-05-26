## Why

P12 gave AgentHub stable platform-core contracts, but mixed-provider
cooperation is still not a verified product capability. AgentHub has
ClaudeCodeAdapter and CodexAdapter, yet it must prove that different
provider-backed role agents can work together in the same task graph without
losing context, target policy, handoff evidence, scheduler state, or provider
identity.

## What Changes

- Add an explicit provider assignment matrix for role and target combinations.
- Extend the AgentProfile foundation so role agents expose auditable provider,
  adapter, target, mode, write, and review capabilities.
- Enforce CanonicalSharedContext as the shared source for provider-backed
  instructions.
- Define Handoff Protocol v1 for backend-to-frontend, frontend-to-review, and
  review-to-fix collaboration.
- Ensure Claude Code and Codex instruction adapters receive semantically
  consistent contract, target, handoff, validation, and guardrail context.
- Normalize provider evidence across run status, errors, logs, changed files,
  diff metadata, review metadata, preview evidence, and staging deploy
  evidence.
- Integrate mixed-provider task graphs with the existing scheduler,
  dependencies, target locks, recovery states, mission trace, and staging
  deploy prerequisites.
- Rehearse a bounded workflow where backend uses Codex and frontend uses
  Claude Code, recording exact provider success or failure without masking it.

## Capabilities

### New Capabilities

- `cross-provider-coordination`: Provider assignment, provider-aware agent
  profiles, canonical-context enforcement, handoff protocol, provider-specific
  instruction consistency, normalized evidence, scheduler integration, and
  mixed-provider rehearsal for AgentHub role agents.

### Modified Capabilities

None. P13 introduces cross-provider coordination as a new capability while
preserving P6-P12 behavior.

## Impact

- Backend:
  - provider assignment configuration and read APIs;
  - AgentProfile, instruction adapter, canonical context, handoff, task-run,
    scheduler, mission trace, and artifact evidence integration points;
  - tests for mixed Codex/Claude Code role assignment and fallback honesty.
- Frontend:
  - provider identity and provider assignment visibility in existing agent,
    task, mission trace, run, and artifact surfaces where already present;
  - no broad UI redesign or user-created custom-agent UI.
- Runtime:
  - preserve CodexAdapter, ClaudeCodeAdapter, and ScriptedMockAdapter;
  - do not fake real provider success;
  - preserve P6 mini CRM, P7 target registry, P8 scheduler, P9 external
    workspace, P10 recovery, P11 staging deploy, and P12 platform-core
    baselines.
