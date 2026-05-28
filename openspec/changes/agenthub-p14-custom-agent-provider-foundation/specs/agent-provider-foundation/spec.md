## ADDED Requirements

### Requirement: Agent Profile Registry
The system MUST expose a stable Agent Profile Registry for built-in agents and
validated draft agents.

#### Scenario: Built-in profile fields are exposed
- **WHEN** a client reads an AgentProfile from the registry
- **THEN** the profile MUST include id, displayName, avatarInitials, role,
  adapterType, providerId, capabilityTags, supportedTargets, supportedModes,
  safeForWrite, safeForReview, description, and status.

#### Scenario: Built-in agents are preserved
- **WHEN** P14 registry behavior is enabled
- **THEN** existing orchestrator, frontend, backend, QA, review, and fallback
  agent profiles MUST remain available
- **AND** existing CodexAdapter, ClaudeCodeAdapter, and ScriptedMockAdapter
  behavior MUST NOT be removed or regressed.

#### Scenario: Profile status is visible
- **WHEN** a profile is disabled, unavailable, auth-blocked, or draft-only
- **THEN** the registry response MUST expose that status without claiming the
  agent can execute write work.

### Requirement: Provider Config Registry
The system MUST expose non-secret provider configuration metadata for current
AgentHub providers.

#### Scenario: Built-in provider configs are exposed
- **WHEN** a client reads provider config metadata
- **THEN** the system MUST include provider metadata for claude_code, codex,
  and scripted_mock.

#### Scenario: Provider config fields are exposed
- **WHEN** provider config metadata is returned
- **THEN** each provider config MUST include providerId, displayName,
  adapterType, authStatus, available, defaultForRoles, and supportedModes.

#### Scenario: Provider secrets are protected
- **WHEN** provider config metadata is returned or persisted
- **THEN** secrets, tokens, API keys, and raw credential values MUST NOT be
  exposed or stored in plain text.

#### Scenario: Cloud token management is requested
- **WHEN** a task requires cloud token management or provider credential setup
- **THEN** P14 MUST defer it honestly.

### Requirement: Capability And Mode Schema
The system MUST define controlled supported modes and capability tags for
AgentHub agent assignment.

#### Scenario: Controlled modes are recognized
- **WHEN** an AgentProfile or assignment policy declares supported modes
- **THEN** the mode MUST be one of frontend, backend, qa, review,
  platform_maintenance, read_only, or debug.

#### Scenario: Controlled capability tags are recognized
- **WHEN** an AgentProfile or assignment policy declares capability tags
- **THEN** each capability tag MUST be one of code_write, code_review,
  test_run, diff_analysis, preview, deploy_staging, or platform_change.

#### Scenario: Unsupported capability is rejected
- **WHEN** a task requires a capability that no eligible profile supports
- **THEN** the system MUST reject or block the assignment honestly
- **AND** it MUST NOT silently assign a provider without the capability.

### Requirement: Agent Selection Policy
The system MUST resolve agent and provider assignment using explicit policy
that respects mentions, provider assignment, role, target, capability, and
safety flags.

#### Scenario: Explicit mention has priority
- **WHEN** a user explicitly mentions a role agent such as @frontend,
  @backend, @qa, or @review
- **THEN** selection MUST start from the mentioned role
- **AND** the selected profile MUST still satisfy target, capability, and
  safety requirements.

#### Scenario: Provider assignment matrix is honored
- **WHEN** ProviderAssignmentMatrix defines a role or target provider
  assignment
- **THEN** agent selection MUST honor that assignment if the selected provider
  and profile satisfy the required target, capability, and safety constraints.

#### Scenario: Target support is required
- **WHEN** a task targets a built-in or external target
- **THEN** the selected AgentProfile MUST support that target or an allowed
  target pattern.

#### Scenario: Write and review safety are enforced
- **WHEN** a task requires write execution
- **THEN** the selected AgentProfile MUST have safeForWrite enabled.
- **WHEN** a task requires review execution
- **THEN** the selected AgentProfile MUST have safeForReview enabled.

#### Scenario: Invalid assignment fails honestly
- **WHEN** no AgentProfile can satisfy role, provider, target, capability, and
  safety requirements
- **THEN** the system MUST fail, block, or ask for clarification honestly
- **AND** it MUST NOT fake provider success.

#### Scenario: Fallback is explicit
- **WHEN** ScriptedMock or another fallback is used after a provider failure
- **THEN** fallback MUST remain explicit, auditable, and distinguishable from
  the original provider attempt.

### Requirement: Agent Contact UI Upgrade
The system MUST display provider, capability, target, and availability metadata
for AgentHub contacts without changing current execution semantics.

#### Scenario: Contact displays provider metadata
- **WHEN** the Agent Contact UI renders a profile
- **THEN** it MUST show provider identity or provider badge and adapter type.

#### Scenario: Contact displays capability and target metadata
- **WHEN** the Agent Contact UI renders a profile
- **THEN** it MUST show capability tags and supported targets in a compact,
  scan-friendly form.

#### Scenario: Contact displays unavailable state
- **WHEN** a profile or provider is unavailable, auth-blocked, disabled, or
  draft-only
- **THEN** the Agent Contact UI MUST show that state without implying the
  agent can execute unavailable work.

#### Scenario: Current contact behavior is preserved
- **WHEN** the UI metadata upgrade is applied
- **THEN** Direct chat and Group workflow visual modes MUST remain local visual
  modes only
- **AND** current Start, Retry, Fallback, Review, Preview, and Deploy behavior
  MUST remain unchanged.

### Requirement: Safe Custom Agent Draft
The system MUST allow safe draft AgentProfile metadata without allowing unsafe
execution.

#### Scenario: Draft profile can be defined
- **WHEN** a user or system defines a draft AgentProfile
- **THEN** the draft MUST be represented as metadata with role, provider,
  capability, target, mode, description, and status fields.

#### Scenario: Draft profile is not write-enabled by default
- **WHEN** a draft AgentProfile is created
- **THEN** it MUST be disabled or review-only until validation succeeds
- **AND** it MUST NOT be eligible for write execution by default.

#### Scenario: Arbitrary shell commands are rejected
- **WHEN** a draft AgentProfile includes arbitrary user-supplied shell
  commands, unsafe tool permissions, or unrestricted filesystem access
- **THEN** the system MUST reject or disable that draft.

#### Scenario: Marketplace behavior is deferred
- **WHEN** a request requires publishing, sharing, searching, installing, or
  monetizing custom agents
- **THEN** P14 MUST defer it honestly.

### Requirement: P14 Rehearsal And Freeze Review
The system MUST rehearse and validate the Agent Provider Foundation before P14
freeze.

#### Scenario: Built-in agents still work
- **WHEN** P14 rehearsal runs
- **THEN** built-in orchestrator, frontend, backend, QA, review, and fallback
  profiles MUST remain available and compatible with existing flows.

#### Scenario: Provider-aware selection still works
- **WHEN** backend is assigned to Codex and frontend is assigned to Claude Code
- **THEN** assignment metadata MUST remain intact in TaskRun, scheduler,
  artifact evidence, handoff, and mission trace surfaces.

#### Scenario: Invalid capability or target assignment is rejected
- **WHEN** a task requests a target or capability unsupported by the selected
  profile
- **THEN** the system MUST reject or block it honestly.

#### Scenario: UI metadata is visible
- **WHEN** the Agent Contact UI renders P14 profile metadata
- **THEN** provider, capability, target, and unavailable/auth state metadata
  MUST be visible.

#### Scenario: Baselines remain intact
- **WHEN** P14 validation is run
- **THEN** P6-P13 baselines MUST remain operational, including ScriptedMock
  fallback, target registry, scheduler locks, external workspace mode,
  recovery, staging deploy, platform-core contracts, and cross-provider
  coordination.
