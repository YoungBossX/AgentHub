## ADDED Requirements

### Requirement: Provider Assignment Matrix
The system MUST support explicit provider assignment for built-in AgentHub
roles and target-aware workflows while preserving existing default adapter
behavior.

#### Scenario: Role provider assignment is resolved
- **WHEN** a task is created for orchestrator, frontend, backend, QA, or review
- **THEN** the system MUST resolve an auditable provider assignment containing
  role, adapter_type, provider_id, supported target scope, supported mode, and
  fallback policy.

#### Scenario: Mixed providers are assigned in one workflow
- **WHEN** a bounded workflow assigns backend work to Codex and frontend work
  to Claude Code
- **THEN** the backend TaskRun MUST record Codex provider identity
- **AND** the frontend TaskRun MUST record Claude Code provider identity
- **AND** both tasks MUST remain in the same dependency graph.

#### Scenario: Existing defaults are preserved
- **WHEN** no explicit provider assignment exists for a task
- **THEN** the system MUST preserve the existing adapter selection behavior
  from Agent metadata and supported environment defaults.

#### Scenario: Target-specific assignment is resolved
- **WHEN** a target-specific provider assignment exists for a role and target
- **THEN** the system MUST use the target-specific assignment ahead of the
  role default
- **AND** the assignment MUST be visible in TaskRun metadata or mission trace.

### Requirement: Provider-aware Agent Profile
The system MUST expose provider-aware AgentProfile metadata for built-in agents
without implementing full user-created custom agents.

#### Scenario: Agent profile exposes provider metadata
- **WHEN** a client or planner reads an AgentProfile
- **THEN** the profile MUST include provider_id, adapter_type,
  supported_roles, supported_targets, supported_modes, safe_for_write, and
  safe_for_review.

#### Scenario: Profile matches provider assignment
- **WHEN** a provider assignment is available for a built-in role
- **THEN** the corresponding AgentProfile MUST expose compatible provider and
  adapter metadata.

#### Scenario: Custom agent UI is requested
- **WHEN** a request requires user-created custom agents or a custom agent UI
- **THEN** P13 MUST defer the request honestly.

### Requirement: Canonical Context Usage Enforcement
The system MUST render all provider-backed instructions from
CanonicalSharedContext.

#### Scenario: Provider instruction uses canonical context
- **WHEN** a CodexAdapter or ClaudeCodeAdapter TaskRun instruction is prepared
- **THEN** the instruction MUST be derived from CanonicalSharedContext.

#### Scenario: Shared context fields are present
- **WHEN** a provider-backed instruction is rendered
- **THEN** the provider-visible context MUST include safe representations of
  session goal, recent messages, task graph, appContract, target metadata,
  upstream artifacts, handoff artifacts, validation commands, and guardrails
  when those fields are available.

#### Scenario: Protected context is filtered
- **WHEN** CanonicalSharedContext is rendered for any provider
- **THEN** protected paths, secrets, `.env`, `.git`, dependency directories,
  and unassigned host paths MUST NOT enter provider-visible context.

#### Scenario: Context snapshot is auditable
- **WHEN** a mixed-provider TaskRun starts
- **THEN** the TaskRun MUST preserve a context snapshot or context reference
  sufficient to audit what was provided to that provider.

### Requirement: Handoff Protocol v1
The system MUST support provider-aware handoff artifacts for cross-provider
task transitions.

#### Scenario: Backend-to-frontend handoff is created
- **WHEN** a backend task completes before a dependent frontend task
- **THEN** the system MUST create or expose a handoff containing provider,
  adapter_type, taskRunId, changedFiles, implemented routes, artifact refs,
  open questions, warnings, and verification status.

#### Scenario: Frontend-to-review handoff is created
- **WHEN** a frontend task completes before a dependent review or QA task
- **THEN** the system MUST create or expose a handoff containing provider,
  adapter_type, taskRunId, changedFiles, implemented components, artifact
  refs, open questions, warnings, and verification status.

#### Scenario: Review-to-fix handoff is created
- **WHEN** a review task produces warnings or failures for a downstream fix
  task
- **THEN** the system MUST create or expose a handoff containing review
  provider identity, findings, affected files, artifact refs, warnings, and
  suggested follow-up scope.

#### Scenario: Handoff reaches downstream context
- **WHEN** a downstream provider-backed task depends on an upstream task with
  a handoff artifact
- **THEN** the downstream CanonicalSharedContext MUST include the relevant
  handoff.

### Requirement: Provider-specific Instruction Mapping
The system MUST map the same canonical mission facts into provider-specific
Codex and Claude Code instructions without semantic drift.

#### Scenario: Codex instruction preserves shared facts
- **WHEN** a Codex instruction is rendered from CanonicalSharedContext
- **THEN** the instruction MUST preserve appContract, target ID, safe paths,
  handoff references, validation expectations, and guardrails.

#### Scenario: Claude Code instruction preserves shared facts
- **WHEN** a Claude Code instruction is rendered from CanonicalSharedContext
- **THEN** the instruction MUST preserve appContract, target ID, safe paths,
  handoff references, validation expectations, and guardrails.

#### Scenario: Provider formatting differs safely
- **WHEN** Codex and Claude Code instructions are rendered for the same
  canonical context
- **THEN** formatting MAY differ
- **AND** contract, target, handoff, validation, and guardrail data MUST NOT be
  lost.

### Requirement: Cross-provider Evidence Normalization
The system MUST normalize cross-provider execution evidence while preserving
real provider identity and failures.

#### Scenario: Provider evidence is recorded
- **WHEN** a provider-backed TaskRun is created, started, completed, failed,
  retried, or replaced by fallback
- **THEN** the system MUST record provider_id, adapter_type, run status,
  errors, logs or event summaries, changed files, and artifact references when
  available.

#### Scenario: Diff and review evidence include provider identity
- **WHEN** diff or review artifacts are produced from a provider-backed run
- **THEN** artifact metadata or related run evidence MUST identify the
  originating provider and adapter.

#### Scenario: Preview and deploy evidence remains linked
- **WHEN** preview or staging deploy evidence is created from a mixed-provider
  workflow
- **THEN** the evidence MUST remain linked to the source TaskRun, provider
  identity, diff, review, and target metadata.

#### Scenario: Provider failure is not hidden
- **WHEN** Codex or Claude Code fails due to auth, quota, runtime, guardrail,
  or adapter error
- **THEN** the system MUST record the exact normalized failure
- **AND** it MUST NOT claim provider success.

#### Scenario: Fallback is explicit
- **WHEN** ScriptedMock or another fallback path is used after provider failure
- **THEN** the fallback TaskRun MUST reference the failed provider TaskRun
- **AND** mission trace MUST distinguish failed provider evidence from fallback
  evidence.

### Requirement: Mixed-provider Scheduler Integration
The system MUST preserve scheduler dependencies, target locks, recovery, and
deploy prerequisites for mixed-provider task graphs.

#### Scenario: Mixed-provider dependencies are enforced
- **WHEN** a frontend Claude Code task depends on a backend Codex task
- **THEN** the frontend task MUST wait until the backend dependency is
  completed or explicitly recovered.

#### Scenario: Target locks are provider independent
- **WHEN** two provider-backed write tasks target the same target
- **THEN** the scheduler MUST enforce the same target write lock regardless of
  provider identity.

#### Scenario: Different targets can progress safely
- **WHEN** backend and frontend write tasks use different targets and have no
  unmet dependency conflict
- **THEN** scheduler readiness MUST be based on dependency, lock, and conflict
  policy rather than provider sameness.

#### Scenario: Recovery preserves provider evidence
- **WHEN** a mixed-provider task is retried, marked stale, or recovered
- **THEN** recovery events MUST preserve the original provider identity and
  resulting provider or fallback identity.

#### Scenario: Staging deploy prerequisites are enforced
- **WHEN** staging deploy is requested after a mixed-provider workflow
- **THEN** deploy gates MUST still require healthy preview, acceptable review,
  target policy compliance, and non-production environment.

### Requirement: Mixed-provider Rehearsal and Freeze Review
The system MUST rehearse cross-provider coordination before P13 freeze.

#### Scenario: Mixed-provider workflow is rehearsed
- **WHEN** P13 freeze review is performed
- **THEN** the rehearsal MUST cover a bounded workflow with backend assigned to
  Codex and frontend assigned to Claude Code, or record exact provider
  blockers if real execution is unavailable.

#### Scenario: Shared contract is verified
- **WHEN** the mixed-provider rehearsal creates backend and frontend tasks
- **THEN** both tasks MUST reference the same appContract or shared task graph
  contract.

#### Scenario: Handoff and artifacts are verified
- **WHEN** the mixed-provider rehearsal completes or reaches a provider
  blocker
- **THEN** the review MUST document handoff artifacts, diff evidence, review
  evidence, preview evidence, staging deploy evidence where available, and any
  provider-specific caveats.

#### Scenario: Baselines remain intact
- **WHEN** P13 validation is run
- **THEN** P6-P12 baselines, including ScriptedMock fallback, target registry,
  scheduler locks, external workspace mode, recovery, staging deploy, and
  platform-core contracts MUST remain operational.
