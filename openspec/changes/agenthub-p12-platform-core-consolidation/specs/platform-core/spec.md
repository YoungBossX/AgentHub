## ADDED Requirements

### Requirement: Planner Orchestrator Boundary

The system MUST separate planner and orchestrator responsibilities into
clear service boundaries while preserving existing demo fallback behavior.

#### Scenario: PlanDraft is produced

- **WHEN** a user message is routed to the planner service
- **THEN** the system MUST produce a PlanDraft with plan ID, version, task
  graph, dependency edges, agent role, target ID, planned files, and rationale.

#### Scenario: Demo fallback is preserved

- **WHEN** an existing login page, dashboard, mini CRM, follow-up, or
  unsupported fallback request is planned
- **THEN** the system MUST preserve the current deterministic demo behavior
- **AND** it MUST NOT claim unsupported execution success.

#### Scenario: Plan validation fails

- **WHEN** a plan draft references invalid targets, unsafe planned files, or
  impossible dependency edges
- **THEN** the plan validator MUST reject or downgrade the plan before task
  creation
- **AND** the rejection reason MUST be visible to the caller.

### Requirement: Canonical Shared Context

The system MUST formalize CanonicalSharedContext as the shared context contract
for planner, provider instruction adapters, review, scheduler, and UI-facing
mission trace behavior.

#### Scenario: Canonical context is built

- **WHEN** a TaskRun instruction request is prepared
- **THEN** the context MUST include session, user goal, current task, task
  graph, target context, safe paths, recent messages, relevant artifacts,
  latest diff, latest review, latest preview, latest deployment, handoff notes,
  and guardrails.

#### Scenario: Context fields carry provenance

- **WHEN** a canonical context field is included
- **THEN** the field MUST carry source, visibility, created_at, and trust_level
  metadata.

#### Scenario: Provider-visible context is filtered

- **WHEN** canonical context is rendered for a provider
- **THEN** protected host paths, secrets, `.env`, `.git`, dependency
  directories, and unassigned host paths MUST NOT enter provider-visible
  context.

#### Scenario: Context snapshot is persisted

- **WHEN** a TaskRun is created or started with canonical context
- **THEN** the system MUST persist a context snapshot in TaskRun metadata or
  artifact metadata for audit and replay.

### Requirement: Provider Instruction Adapter

The system MUST render provider-specific instructions from canonical shared
context through provider instruction adapters.

#### Scenario: Codex instruction is rendered

- **WHEN** CodexAdapter receives an instruction request
- **THEN** the Codex instruction adapter MUST render provider-specific
  instructions from the same canonical context used by other providers.

#### Scenario: Claude Code instruction is rendered

- **WHEN** ClaudeCodeAdapter receives an instruction request
- **THEN** the Claude Code instruction adapter MUST render provider-specific
  instructions from the same canonical context used by other providers.

#### Scenario: ScriptedMock instruction is rendered

- **WHEN** ScriptedMockAdapter receives an instruction request
- **THEN** the scripted mock adapter MUST preserve deterministic fallback paths
  while consuming the same target and safety context.

#### Scenario: Target-aware behavior is preserved

- **WHEN** instructions are generated for demo, demo-api, platform, or
  external targets
- **THEN** target boundaries, safe paths, adapter behavior, and existing
  P6-P11 execution semantics MUST remain intact.

### Requirement: Handoff Artifact

The system MUST support a first-class handoff artifact type for passing
upstream task output to downstream tasks.

#### Scenario: Handoff artifact is created

- **WHEN** a dependency task completes and downstream tasks can use its output
- **THEN** the system MUST be able to create a handoff artifact with
  from_task_id, from_task_run_id, from_agent_role, to_task_id, to_agent_role,
  summary, changed_files, artifact_refs, open_questions, verification_status,
  risk_notes, and created_at.

#### Scenario: Downstream task receives handoff

- **WHEN** a downstream task depends on an upstream task with a handoff artifact
- **THEN** canonical context for the downstream task MUST include the relevant
  upstream handoff.

### Requirement: Artifact Reference Follow-up Context

The system MUST support artifact references for diff, review, preview, and
deployment artifacts in follow-up context.

#### Scenario: Artifact reference is attached to a message

- **WHEN** the user selects or references an artifact in a follow-up message
- **THEN** the message-to-task flow MUST preserve the artifact reference.

#### Scenario: Artifact reference reaches provider instruction

- **WHEN** a task is created from a message with selected artifact context
- **THEN** the artifact reference MUST flow into canonical context
- **AND** the provider instruction MUST include only safe, relevant artifact
  context.

#### Scenario: Unsupported artifact reference is requested

- **WHEN** a request requires document, PPT, paragraph, or unsupported artifact
  references
- **THEN** P12 MUST reject or defer the request honestly.

### Requirement: Mission Trace Foundation

The system MUST define a SessionMissionTraceResponse read model for mission
state and navigation.

#### Scenario: Mission trace is requested

- **WHEN** a client requests the mission trace for a session
- **THEN** the response MUST include current goal, tasks, task runs, events,
  artifacts, blockers, and next actions.

#### Scenario: Scheduler blockers are explicit

- **WHEN** a task or run is blocked, waiting_dependency, or
  waiting_target_lock
- **THEN** the mission trace MUST expose the reason and navigation references
  to the relevant task, run, target, or dependency.

### Requirement: Web Component Decomposition And Message Actions

The system MUST decompose large workspace UI components into focused
components while preserving current behavior.

#### Scenario: Workspace components are decomposed

- **WHEN** the web workspace shell is refactored
- **THEN** behavior MUST be preserved while responsibilities are split into
  session-sidebar, agent-contact-list, chat-thread, message-composer,
  mission-panel, artifact-panel, task-card, run-history, run-controls, and
  artifact-chips components.

#### Scenario: Message actions are available

- **WHEN** a user interacts with messages, runs, or artifacts
- **THEN** first-stage actions MUST support copy, quote as context, use
  artifact as context, retry failed run, and open artifact when backed by
  existing APIs.

### Requirement: Artifact Version History Skeleton

The system MUST add or standardize an ArtifactVersion skeleton for follow-up
artifact chains.

#### Scenario: Artifact version is recorded

- **WHEN** an artifact is created or superseded by a follow-up change
- **THEN** the version record MUST include artifact_id, version,
  source_task_run_id, parent_artifact_id, git_base_ref, git_head_ref,
  changed_files, and summary.

#### Scenario: Version chain is read

- **WHEN** a user or provider references v1/v2 artifact history
- **THEN** the system MUST expose enough version metadata to identify parent
  and current artifacts.

#### Scenario: Online editing is requested

- **WHEN** a request requires online artifact editing or git revert UI
- **THEN** P12 MUST defer it honestly.

### Requirement: Agent Profile Minimal Foundation

The system MUST stabilize a minimal AgentProfile schema for built-in agents.

#### Scenario: Agent profile is exposed

- **WHEN** a client or planner reads agent metadata
- **THEN** the profile MUST include id, display_name, avatar_initials, role,
  adapter_type, provider_id, capability_tags, supported_targets,
  supported_modes, safe_for_write, safe_for_review, and description.

#### Scenario: User-created custom agent is requested

- **WHEN** a request requires full user-created custom agents or a custom
  agents UI
- **THEN** P12 MUST defer the request honestly.

### Requirement: P12 Rehearsal And Freeze Review

The system MUST rehearse the consolidated platform core and preserve P6-P11
baselines before freeze.

#### Scenario: Complete rehearsal succeeds

- **WHEN** P12 freeze review is performed
- **THEN** the rehearsal MUST cover new session, orchestrator login-page
  request, plan/task graph, frontend run, diff, handoff, QA review, preview,
  local staging deploy, follow-up modification, artifact v2, and updated
  preview/deploy evidence.

#### Scenario: Existing baselines remain intact

- **WHEN** validation is run
- **THEN** P6 mini CRM/full-stack execution, P7 target registry, P8 scheduler,
  P9 external workspace mode, P10 robustness, P11 staging deploy, and
  ScriptedMock fallback MUST remain operational.

#### Scenario: Validation is completed

- **WHEN** P12 is marked ready to freeze
- **THEN** `pnpm check`, `pnpm test`, `git diff --check`, and
  `openspec validate agenthub-p12-platform-core-consolidation --strict` MUST
  pass.
