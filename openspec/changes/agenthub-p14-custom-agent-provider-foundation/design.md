## Context

P12 froze the platform core: CanonicalSharedContext, ProviderInstructionAdapter
foundation, Handoff Artifact, Artifact Reference, Mission Trace, Artifact
Version skeleton, and Agent Profile foundation. P13 froze cross-provider
coordination: provider assignment matrix, provider-aware agent profiles,
canonical provider context, provider-aware handoff metadata, provider-specific
instruction wrappers, normalized provider evidence, mixed-provider scheduler
state, and freeze rehearsal evidence.

P14 builds on that foundation by making Agent profiles and provider metadata
first-class, controlled, and inspectable. The goal is to prepare AgentHub for
future custom agents and plugin-like skills without opening unsafe arbitrary
execution or a marketplace.

## Goals / Non-Goals

**Goals:**

- Stabilize AgentProfile as a registry concept with explicit provider,
  adapter, capability, target, mode, write/review safety, status, and
  description fields.
- Add a Provider Config Registry for `claude_code`, `codex`, and
  `scripted_mock`.
- Define controlled supported modes and capability tags.
- Require agent assignment to respect target registry, provider assignment,
  capabilities, supported modes, and safety flags.
- Upgrade the Agent Contact UI to expose provider and capability metadata.
- Allow safe custom AgentProfile drafts that remain disabled or review-only
  until validated.
- Preserve built-in agents, current adapters, P6-P13 baselines, and fallback
  honesty.

**Non-Goals:**

- Full provider marketplace.
- Arbitrary custom shell command agents.
- OpenCode integration.
- Cloud token manager.
- Enterprise RBAC.
- Multi-user agent sharing.
- Production deploy.
- Desktop, IDE, or CLI clients.
- Replacing current adapters.

## Decisions

### Decision: AgentProfile Registry Is Metadata-First

P14 should promote current built-in AgentProfile output into a registry-backed
contract without changing adapter execution semantics in the first task.

Required profile fields:

```text
id
displayName
avatarInitials
role
adapterType
providerId
capabilityTags
supportedTargets
supportedModes
safeForWrite
safeForReview
description
status
```

Rationale: P13 made provider assignment auditable at runtime, but agent
metadata still needs a stable registry contract that UI, planner, scheduler,
and tests can share.

### Decision: Provider Config Registry Is Non-Secret Metadata

P14 should add provider metadata for the current providers only:

```text
claude_code
codex
scripted_mock
```

Provider config should include provider ID, display name, adapter type, auth
status, availability, default roles, and supported modes. It must not store
secrets in plain text and must not implement token management.

Rationale: users need to understand why an agent is available, unavailable, or
auth-blocked without AgentHub becoming a cloud credential manager.

### Decision: Capability And Mode Schema Is Controlled

P14 should define allowed modes:

```text
frontend
backend
qa
review
platform_maintenance
read_only
debug
```

P14 should define capability tags:

```text
code_write
code_review
test_run
diff_analysis
preview
deploy_staging
platform_change
```

Rationale: controlled vocabularies keep selection, UI, policy, and tests
consistent. Unsupported capabilities must fail honestly instead of becoming
free-form permission strings.

### Decision: Agent Selection Policy Builds On P13

Agent selection should resolve in this order:

1. explicit mention;
2. ProviderAssignmentMatrix;
3. role;
4. target;
5. capability;
6. `safeForWrite` / `safeForReview`.

The policy must not silently substitute another provider unless fallback is
explicit and auditable.

Rationale: P13 already made provider assignment explicit; P14 adds capability
and target validation so profile metadata cannot bypass Target Registry,
Scheduler, or provider evidence.

### Decision: Safe Custom Agent Drafts Are Disabled Or Review-Only

P14 should permit draft AgentProfile metadata for future custom agents, but
draft agents must not run arbitrary shell commands, request unsafe tool
permissions, or mutate targets until validated. Initial draft status should be
disabled or review-only.

Rationale: this gives the product a path toward custom agents without
introducing unsafe execution, marketplace complexity, or permission bypasses.

### Decision: Contact UI Upgrade Stays Informational

The Agent Contact UI should display provider badge, capability tags, supported
targets, and status/auth issue/unavailable state. It should preserve current
Direct chat / Group workflow behavior and must not introduce multi-user
accounts or marketplace browsing.

Rationale: P14 needs a visible product surface for the registry, but the
execution behavior remains governed by the backend policy.

## Risks / Trade-offs

- **Risk: registry duplicates Agent table data.**
  Mitigation: start with a service/API contract that maps current built-in
  agents, then introduce persistence only where needed for safe drafts.
- **Risk: provider auth status appears to imply credential management.**
  Mitigation: expose status only; do not store or manage tokens in P14.
- **Risk: custom agent drafts become unsafe execution.**
  Mitigation: disable write execution until validation and forbid arbitrary
  shell commands/tool permissions.
- **Risk: assignment policy rejects valid current flows.**
  Mitigation: preserve built-in agent mappings and add regression tests for
  P6-P13 demo, full-stack, scheduler, staging deploy, and mixed-provider
  baselines.
- **Risk: UI expands into marketplace.**
  Mitigation: keep contact UI metadata-only and defer marketplace/search/share.

## Migration Plan

1. Add Agent Profile Registry service/schema and preserve built-in agent
   mappings.
2. Add Provider Config Registry metadata and provider availability/auth status
   API.
3. Add controlled capability/mode schema and validation helpers.
4. Route selection policy through profile, provider, target, capability, and
   safety validation while preserving current default behavior.
5. Upgrade Agent Contact UI metadata display.
6. Add safe custom agent draft metadata and validation.
7. Run P14 rehearsal and freeze review.

Rollback strategy: if registry validation causes regressions, fall back to the
P13 built-in AgentProfile and ProviderAssignmentMatrix behavior while keeping
new metadata read-only for diagnosis.

## Open Questions

- Should safe draft AgentProfiles be stored in SQLite immediately or start as
  a versioned file/static registry plus API response?
- Should provider auth status be inferred from CLI availability checks, config
  flags, or explicit health probes?
- Which UI surface should own safe draft creation: contact list, settings
  panel, or a later dedicated agent management screen?
