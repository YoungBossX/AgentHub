## Why

AgentHub now has real planner/coding providers, provider assignment, agent
profiles, target registry, scheduler, evidence, and staging deploy, but the
core role-to-provider choices are still mostly internal configuration. Users
need a safe runtime settings layer for Planner, Frontend, Backend, and Review
roles so they can choose existing providers/profiles without opening arbitrary
custom agents or unsafe shell execution.

## What Changes

- Add a validated Agent Runtime Config model for core roles: planner,
  frontend, backend, and review.
- Expose runtime config APIs to read, update, and validate workspace/global
  runtime defaults.
- Add an Agent Runtime Settings UI for Planner Agent, Frontend Agent, and
  Backend Agent, with provider/profile metadata and safe selectable options.
- Connect runtime config resolution to the existing ProviderAssignmentMatrix,
  AgentSelectionPolicy, planner provider selection, and provider evidence.
- Record resolved runtime config evidence in planner evidence, TaskRun
  metadata, mission trace, or API responses where appropriate.
- Enforce policy so runtime config cannot bypass Target Registry,
  PlanValidator, platform maintenance approval, or protected-path guardrails.
- Rehearse a configuration where Planner uses `claude_cli`, Frontend uses
  `claude_code`, and Backend uses `codex`.

## Capabilities

### New Capabilities

- `agent-runtime-config`: Workspace/global runtime configuration for selecting
  safe existing agent profiles and providers for planner, frontend, backend,
  and review roles, including API, UI, resolution, evidence, and policy
  enforcement.

### Modified Capabilities

- None.

## Impact

- Backend:
  - adds runtime config persistence and validation;
  - adds read/update/validate API endpoints;
  - resolves runtime config into planner provider and coding provider
    selection;
  - records runtime config evidence in planner/task/run/mission trace metadata.
- Frontend:
  - adds runtime settings UI using existing AgentProfile and ProviderConfig
    metadata;
  - shows provider badge, adapter type, capability tags, supported targets, and
    status/auth availability.
- Runtime and security:
  - preserves existing defaults when no runtime config exists;
  - refuses invalid provider/profile/role/target combinations honestly;
  - keeps ScriptedMock clearly marked as fallback/mock;
  - does not store secrets in plaintext or allow arbitrary shell command
    agents.
