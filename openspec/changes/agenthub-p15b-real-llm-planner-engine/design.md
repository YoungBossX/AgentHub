## Context

P15 froze the real coding assistant execution path: bounded frontend requests
can route to `passthrough_v1`, preserve the original request, execute through
ClaudeCodeAdapter, collect diffs including untracked files, record build
evidence, pass review, preview, and local staging deploy. The remaining gap is
the planner itself. `llm_v1` currently builds planner input and validates test
outputs, but no real provider call is wired into Orchestrator as the planning
engine.

P15b focuses on planning, not another execution or UI expansion. It connects
the existing `llm_v1` planner contract to a real provider while keeping the
validated PlanDraft boundary as the safety line between LLM reasoning and task
creation.

## Goals / Non-Goals

**Goals:**

- Add PlannerProvider abstraction and explicit provider selection.
- Support disabled planner, fake/test planner, and at least one real planner
  provider.
- Build PlannerRequest from original request, CanonicalSharedContext, Target
  Registry, Project Analyzer summaries, recent messages, artifact references,
  supported roles/modes/capabilities, and guardrails.
- Parse real provider output into a structured PlannerResponse / PlanDraft.
- Validate schema and PlanValidator constraints before task creation.
- Record planner evidence, provider identity, validation result, fallback
  reason, and error summary.
- Verify the Breakout request is planned by a real LLM provider, not a
  hardcoded template or fake planner.

**Non-Goals:**

- Replacing ClaudeCodeAdapter or CodexAdapter.
- Replacing the scheduler.
- Provider marketplace.
- User-created arbitrary command agents.
- Production deploy.
- Cloud token manager.
- Multi-user IM.
- Desktop, IDE, or CLI clients.
- Hardcoded Breakout planner template.

## Decisions

### Decision: PlannerProvider Is Separate From Coding AgentAdapter

P15b should introduce a planner-specific provider interface instead of reusing
AgentAdapter directly. A planner provider returns structured planning data, not
code edits, diffs, previews, or deployment artifacts.

The interface should support:

- provider ID and provider type;
- availability/auth status checks where practical;
- timeout and cancellation boundaries;
- structured PlannerRequest input;
- raw output and normalized PlannerResponse output;
- error classification for auth, quota, runtime, timeout, invalid JSON, and
  unsafe plan results.

Alternatives considered:

- Reuse ClaudeCodeAdapter/CodexAdapter directly for planning. This would blur
  planning and coding execution semantics and make planner evidence harder to
  audit.
- Keep `llm_v1` as test-only. This leaves Orchestrator without the product
  capability P15b is meant to unlock.

### Decision: Real Provider Is Explicit And Auditable

Provider selection should be explicit through configuration, for example a
planner provider setting such as `disabled`, `fake_test`, `claude_cli`,
`claude_api`, or `openai_api`. P15b only needs one real provider path, but the
abstraction should make the selected provider visible in task metadata,
planner evidence, and mission trace.

Real provider execution must not store secrets in plain text. If an API-based
provider is selected, credentials must come from environment/runtime config and
must not be echoed into planner evidence. If a CLI provider is selected,
command shape and stderr handling must be constrained and normalized.

### Decision: PlannerRequest Is A Sanitized Context Contract

PlannerRequest should include enough context to plan well while excluding
protected data:

- original user request;
- CanonicalSharedContext summary;
- target registry summaries;
- project analyzer summary;
- recent messages;
- selected artifact and artifact references;
- supported roles, modes, capabilities, and available agents;
- guardrails, allowed paths, denied paths, validation expectations, and
  command policy;
- existing task graph or ledger state when relevant.

Protected host paths, secrets, tokens, `.env` values, dependency directories,
and raw provider credentials must not enter provider-visible planner context.

### Decision: Structured Output Is Required Before Task Creation

The real planner provider must return JSON or JSON-extractable content. P15b
should parse it safely, validate the schema, normalize only safe fields, then
pass the candidate plan through PlanValidator before any Task rows are
created.

Required PlanDraft content includes:

```text
planId
planner: llm_v1
rationale
tasks
role
targetId
intentType
plannedFiles
dependsOn
acceptanceCriteria
riskLevel
requiresApproval
```

Invalid, unsafe, incomplete, or unsupported plans must become an honest
failure, fallback, or clarification response. They must not silently execute.

### Decision: PlanValidator Becomes The Safety Gate For Real LLM Output

PlanValidator should validate real LLM output against:

- known targets;
- allowed roles;
- AgentProfile capabilities and supported modes;
- target allowed paths and denied paths;
- dependency graph consistency;
- platform maintenance mode and approval requirements;
- command policy and validation expectations;
- same-session scheduling constraints.

This preserves flexibility from the planner while keeping the Target Registry,
Agent Selection Policy, and scheduler as authoritative execution boundaries.

### Decision: Breakout Rehearsal Proves Planning, Not Just Execution

P15b should rerun the Breakout acceptance request, but with a stronger
requirement: the frontend task must be produced by a real LLM planner provider.
The provider may choose a frontend task and passthrough coding instruction, but
the plan cannot come from a Breakout regex/template or fake test planner.

The coding execution can reuse P15's working path: ClaudeCodeAdapter or
CodexAdapter, target-scoped guardrails, diff, review, build evidence, preview,
and local staging deploy.

## Risks / Trade-offs

- **Risk: Provider returns invalid or unsafe JSON.** Mitigation: strict schema
  parsing, safe normalization, PlanValidator, and honest fallback/failure.
- **Risk: Planner context leaks secrets or host paths.** Mitigation: build
  PlannerRequest from CanonicalSharedContext sanitization and explicit
  provider-visible fields only.
- **Risk: Real provider auth/quota blocks rehearsal.** Mitigation: record the
  exact normalized error and do not claim planner success.
- **Risk: Planner over-plans unsupported work.** Mitigation: validate target,
  capabilities, command policy, platform mode, and dependency graph before
  persistence.
- **Risk: Fallback hides real planner failure.** Mitigation: planner evidence
  must expose `real_llm`, `fake_test`, `disabled`, `deterministic`, and
  `fallback` source states.

## Migration Plan

1. Add planner provider interfaces, disabled/fake providers, config, and
   provider selection metadata.
2. Add PlannerRequest / PlannerResponse schema and sanitized context builder.
3. Implement one real provider path with timeout and error normalization.
4. Add structured output extraction, parsing, validation, and safe
   normalization.
5. Harden PlanValidator for real LLM plans.
6. Record planner evidence in task metadata and mission trace.
7. Run the real LLM planner Breakout rehearsal and freeze review.

Rollback strategy: set planner provider to `disabled` and keep deterministic
fallback / P15 passthrough execution behavior active.

## Open Questions

- Which real provider should be implemented first in this environment:
  Claude CLI planner, Claude API planner, or OpenAI API planner?
- Should real planner execution default to disabled until explicitly enabled
  by environment config?
- Should planner provider prompts be versioned separately from coding provider
  instructions?
