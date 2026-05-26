## Context

P12 froze AgentHub's platform core: planner boundaries, CanonicalSharedContext,
provider instruction adapters, handoff artifacts, artifact references, mission
trace, artifact versions, and agent profiles. P6-P11 also established target
registry, scheduler dependencies, target locks, recovery, external workspace
mode, and local staging deployment.

The next gap is mixed-provider cooperation. AgentHub has `CodexAdapter`,
`ClaudeCodeAdapter`, and `ScriptedMockAdapter`, but the system has not yet
made provider assignment explicit enough to prove that a backend task can run
with Codex, a frontend task can run with Claude Code, and review can preserve
provider identity and evidence in one task graph.

P13 is therefore a coordination phase, not a provider marketplace or custom
agent phase. It should make provider choice explicit, auditable, and visible
while preserving the P6-P12 baselines.

## Goals / Non-Goals

**Goals:**

- Add an explicit provider assignment matrix for orchestrator, frontend,
  backend, QA, and review roles.
- Support mixed-provider workflows such as `backend=codex` and
  `frontend=claude_code` in the same session task graph.
- Extend AgentProfile metadata with provider assignment, supported roles,
  supported targets, supported modes, and safety capabilities.
- Enforce CanonicalSharedContext as the single context source for
  provider-backed instruction rendering.
- Define Handoff Protocol v1 for backend-to-frontend, frontend-to-review, and
  review-to-fix transitions.
- Normalize provider evidence without hiding real provider identity, errors,
  logs, changed files, diffs, reviews, previews, or staging deploys.
- Integrate provider assignment with scheduler dependencies, target locks,
  recovery, mission trace, and artifact navigation.
- Rehearse one bounded mixed-provider workflow and record exact provider
  success or failure.

**Non-Goals:**

- New provider marketplace.
- OpenCode integration.
- Full user-created custom agents UI.
- Multi-user IM.
- Desktop or mobile clients.
- Production deploy.
- Distributed worker cluster.
- Full autonomous free-form agent negotiation.
- Replacing the current scheduler with LangGraph, CrewAI, or another
  orchestration framework.

## Decisions

### Decision: Provider Assignment Matrix Is Explicit Runtime Policy

P13 should introduce a small provider assignment matrix that maps role, target,
and mode to adapter/provider choices.

Example conceptual shape:

```text
role: backend
targetId: demo-backend
adapterType: codex
providerId: local-codex-cli
mode: write
fallbackPolicy: explicit_only
```

Rationale: provider choice must be auditable. Environment defaults such as
`AGENTHUB_DEFAULT_CODE_ADAPTER` are useful, but P13 needs per-role and
target-aware overrides so the task graph can intentionally mix Codex and
Claude Code.

Alternative considered: continue relying only on Agent.adapter_type and
environment defaults. Rejected because it makes mixed-provider intent implicit
and hard to verify in mission trace or evidence.

### Decision: AgentProfile Exposes Provider Coordination Metadata

The existing AgentProfile foundation should grow to expose provider ID,
adapter type, supported roles, supported targets, supported modes,
safe-for-write, and safe-for-review.

Rationale: users and planner code both need a stable view of which agents can
run where and with which provider. This enables mixed provider assignment
without implementing a custom-agent UI.

Alternative considered: create a separate custom agent registry now. Rejected
because P13 is about coordination of current built-in agents, not user-created
agent lifecycle.

### Decision: Canonical Context Remains The Provider Contract

All provider-backed runs should derive instructions from
CanonicalSharedContext. Provider-specific prompt adapters may format text
differently, but they must preserve shared mission data: session goal, recent
messages, task graph, appContract, target metadata, safe paths, upstream
handoffs, artifact references, validation expectations, and guardrails.

Rationale: mixed-provider coordination fails if Codex and Claude Code receive
different facts about the same contract or target boundary.

Alternative considered: add provider-specific context builders. Rejected
because it would duplicate safety filtering and risk context drift.

### Decision: Handoff Protocol v1 Extends Existing Handoff Artifacts

P13 should keep using the P12 handoff artifact layer and standardize metadata
for cross-provider transitions:

```text
fromProviderId
fromAdapterType
fromTaskRunId
toProviderId
toAdapterType
changedFiles
implementedRoutes
implementedComponents
artifactRefs
openQuestions
warnings
verificationStatus
```

Rationale: handoffs are the bridge between provider outputs. They must be
persisted, visible, and available to downstream canonical context.

Alternative considered: pass handoff text only through prompts. Rejected
because mission trace and review need navigable artifact evidence.

### Decision: Evidence Normalization Keeps Raw Provider Identity

TaskRun metrics, events, artifacts, mission trace, and UI surfaces should
normalize common evidence fields while preserving provider-specific identity
and errors.

Rationale: fallback and recovery are only trustworthy if a failed Codex run is
not silently presented as a Claude Code success, and vice versa.

Alternative considered: map all provider results into generic "agent success"
messages. Rejected because it hides the core risk P13 is meant to solve.

### Decision: Scheduler Integration Builds On Existing Locks And Recovery

P13 should not replace scheduler behavior. It should ensure mixed-provider
tasks still obey dependencies, same-target write locks, failure propagation,
retry/fallback explicitness, and staging deploy prerequisites.

Rationale: provider diversity increases risk, so P8-P10 safety rules become
more important, not less.

Alternative considered: a separate cross-provider orchestration runner.
Rejected because it would split task state and conflict handling.

## Risks / Trade-offs

- **Risk: provider assignment conflicts with existing adapter defaults.**
  Mitigation: preserve current defaults and apply the matrix only when it is
  explicitly configured or selected for a task.
- **Risk: CanonicalSharedContext leaks protected data to multiple providers.**
  Mitigation: keep P12 provider-visible filtering and add regression tests for
  mixed-provider instruction rendering.
- **Risk: provider-specific prompt formatting loses shared contract fields.**
  Mitigation: test Codex and Claude Code instruction output against the same
  canonical context fixture.
- **Risk: fallback masks provider failure.**
  Mitigation: require fallback runs to reference the failed provider run and
  expose both provider identities in mission trace and artifacts.
- **Risk: real provider rehearsal is blocked by auth, quota, or CLI runtime.**
  Mitigation: record the exact normalized error and use deterministic plumbing
  evidence only for non-provider-success assertions.
- **Risk: P13 expands into marketplace/custom agents.**
  Mitigation: keep provider assignment scoped to built-in roles and defer
  custom-agent UI to a later change.

## Migration Plan

1. Add provider assignment matrix data structures, defaults, and read APIs.
2. Extend AgentProfile responses with provider coordination metadata.
3. Route TaskRun adapter selection through explicit assignment resolution while
   preserving current defaults.
4. Add canonical-context enforcement tests for Codex and Claude Code
   instruction adapters.
5. Extend handoff artifacts with provider-aware metadata and include handoffs
   in downstream context.
6. Normalize provider evidence in TaskRun events, artifacts, and mission trace.
7. Verify scheduler behavior with mixed-provider task graphs.
8. Run the mixed-provider rehearsal and freeze review.

Rollback strategy: if provider matrix resolution causes regressions, fall back
to current Agent.adapter_type and environment default behavior while preserving
new read-only metadata for diagnosis.

## Open Questions

- Should provider assignment be stored in SQLite immediately, or start as a
  versioned static policy with API exposure?
- Should review default to Claude Code, ScriptedReview, or provider-specific
  review by target?
- How much provider log detail should be exposed in mission trace versus
  artifact metadata?
- Should mixed-provider rehearsal use built-in demo targets, an external
  sample workspace, or both?
