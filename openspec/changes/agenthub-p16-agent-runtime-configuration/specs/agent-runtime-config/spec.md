## ADDED Requirements

### Requirement: Agent Runtime Config Model
The system MUST define a validated runtime configuration model for core
AgentHub roles.

#### Scenario: Runtime config stores core role defaults
- **WHEN** runtime config is persisted
- **THEN** it MUST support planner, frontend, backend, and review role defaults
- **AND** each enabled role config MUST include agent profile ID, provider ID,
  adapter type, mode, enabled state, and fallback policy when supported.

#### Scenario: Missing config preserves defaults
- **WHEN** no runtime config exists for a workspace
- **THEN** the system MUST preserve the existing default planner/provider
  behavior.

#### Scenario: Config scope is explicit
- **WHEN** runtime config is stored
- **THEN** the system MUST record whether the config source is workspace-level
  or global/default-level.

### Requirement: Runtime Config API
The system MUST expose API endpoints to read, update, and validate Agent
Runtime Config.

#### Scenario: Read runtime config
- **WHEN** a client requests runtime config for a workspace
- **THEN** the API MUST return the effective role config, available selectable
  profiles/providers, validation state, and config source.

#### Scenario: Update runtime config
- **WHEN** a client updates runtime config
- **THEN** the API MUST validate all role entries before saving
- **AND** it MUST reject the entire update if any enabled role entry is invalid.

#### Scenario: Validate runtime config without saving
- **WHEN** a client requests config validation
- **THEN** the API MUST return validation errors and warnings without changing
  the persisted runtime config.

#### Scenario: Invalid combinations fail honestly
- **WHEN** a role config references an unknown provider, unknown profile,
  unsupported adapter type, unsupported mode, unavailable provider, or unsafe
  target/capability combination
- **THEN** the API MUST reject it with a clear validation error.

### Requirement: Agent Runtime Settings UI
The system MUST provide a user-facing settings UI for safe core role
configuration.

#### Scenario: Show configurable core roles
- **WHEN** the user opens runtime settings
- **THEN** the UI MUST show Planner Agent, Frontend Agent, and Backend Agent
  configuration sections.

#### Scenario: Show safe provider and profile metadata
- **WHEN** the UI lists selectable options
- **THEN** it MUST show provider badge, adapter type, capability tags,
  supported targets, supported modes, and status or auth/unavailable state.

#### Scenario: Restrict selectable options
- **WHEN** the user selects a provider/profile for a role
- **THEN** the UI MUST allow selection only from existing safe
  ProviderConfig and AgentProfile options returned by the runtime config API.

#### Scenario: No arbitrary shell command agents
- **WHEN** the runtime settings UI is displayed
- **THEN** it MUST NOT provide arbitrary shell command fields, unsafe tool
  permission editing, or marketplace-style provider installation.

### Requirement: Runtime Config Resolution
The system MUST resolve runtime config into existing planner and coding
provider selection paths.

#### Scenario: Planner role resolves to configured planner provider
- **WHEN** planner runtime config is enabled and valid
- **THEN** Orchestrator planning MUST use the configured planner provider
  before falling back to environment/default planner behavior.

#### Scenario: Frontend role resolves to configured coding provider
- **WHEN** a frontend task is started
- **THEN** the ProviderAssignmentMatrix and AgentSelectionPolicy MUST consider
  the configured frontend agent profile and provider.

#### Scenario: Backend role resolves to configured coding provider
- **WHEN** a backend task is started
- **THEN** the ProviderAssignmentMatrix and AgentSelectionPolicy MUST consider
  the configured backend agent profile and provider.

#### Scenario: Review role resolves safely
- **WHEN** review runtime config is enabled
- **THEN** review task resolution MUST require a review-capable profile and
  MUST preserve non-blocking/scripted review semantics unless explicitly
  changed by a later OpenSpec task.

#### Scenario: Fallback is explicit
- **WHEN** runtime config resolution falls back from the configured provider
- **THEN** the fallback source and reason MUST be recorded
- **AND** the system MUST NOT silently report fallback as configured provider
  success.

### Requirement: Runtime Config Evidence
The system MUST record auditable runtime config resolution evidence.

#### Scenario: TaskRun records runtime config evidence
- **WHEN** a TaskRun is created using runtime config
- **THEN** TaskRun metadata MUST include resolved agent profile ID, provider
  ID, adapter type, config source, and fallback reason when applicable.

#### Scenario: Planner evidence records runtime config source
- **WHEN** a planner provider is selected through runtime config
- **THEN** planner evidence MUST include config source, provider ID, provider
  type, planner source, and fallback reason when applicable.

#### Scenario: Mission trace exposes runtime config evidence
- **WHEN** mission trace is requested
- **THEN** planner/task/run entries MUST expose the runtime config source and
  resolved provider/profile metadata where available.

#### Scenario: Evidence hides secrets
- **WHEN** runtime config evidence is stored or returned
- **THEN** it MUST NOT include plaintext secrets, credentials, tokens, or
  protected host paths.

### Requirement: Runtime Config Safety Enforcement
The system MUST enforce existing safety policies when runtime config is used.

#### Scenario: Target Registry remains authoritative
- **WHEN** a runtime-configured role executes a task
- **THEN** Target Registry allowed paths, denied paths, target type, and
  command policy MUST remain authoritative.

#### Scenario: PlanValidator remains authoritative
- **WHEN** runtime config affects planner or task assignment
- **THEN** PlanValidator MUST still reject unsafe targets, unsafe paths,
  unsupported roles, unsupported capabilities, invalid dependencies, and
  unsupported commands before task execution.

#### Scenario: Backend config cannot modify platform code
- **WHEN** backend runtime config is used for ordinary backend tasks
- **THEN** those tasks MUST NOT modify AgentHub platform backend code under
  `apps/api` unless explicit platform maintenance mode and approval are
  present.

#### Scenario: ScriptedMock remains labeled as fallback
- **WHEN** runtime config selects or falls back to ScriptedMock
- **THEN** evidence and UI MUST label it as scripted/mock/fallback
- **AND** it MUST NOT be reported as real Claude/Codex provider success.

### Requirement: P16 Rehearsal And Freeze Review
The system MUST verify Agent Runtime Configuration without regressing existing
AgentHub baselines.

#### Scenario: Configured provider workflow
- **WHEN** P16 rehearsal configures Planner as `claude_cli`, Frontend as
  `claude_code`, and Backend as `codex`
- **THEN** runtime config MUST affect actual planner/provider resolution
- **AND** evidence MUST record those resolved choices.

#### Scenario: Invalid config rejection
- **WHEN** rehearsal submits invalid role/provider/profile combinations
- **THEN** the system MUST reject them with clear validation errors.

#### Scenario: Baselines remain intact
- **WHEN** P16 freeze review runs validation
- **THEN** P6-P15b baselines for planning, target registry, scheduler,
  recovery, external workspace mode, diff, review, build, preview, and staging
  deploy MUST remain intact.

#### Scenario: No real-provider success is faked
- **WHEN** real Claude/Codex/planner execution is blocked by auth, quota,
  runtime, or environment failure
- **THEN** the exact normalized error MUST be recorded
- **AND** P16 MUST NOT claim real provider success for that run.
