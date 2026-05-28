## Why

P15 proved AgentHub can execute real coding work through `passthrough_v1` and
ClaudeCodeAdapter, but `llm_v1` planning is still only an interface,
test-double, and deterministic fallback foundation. AgentHub needs a real LLM
planner engine so Orchestrator can analyze the original request and project
context, then produce a validated PlanDraft instead of relying on
passthrough/deterministic routing.

## What Changes

- Add a PlannerProvider abstraction with disabled, fake/test, and at least one
  real planner provider implementation.
- Define an auditable PlannerRequest / PlannerResponse contract around the
  original user request, CanonicalSharedContext, Target Registry, Project
  Analyzer summaries, recent messages, artifact references, supported
  roles/modes/capabilities, and guardrails.
- Wire `llm_v1` to a real provider path while preserving explicit provider
  selection, timeout handling, auth/quota/runtime error reporting, invalid
  output rejection, and deterministic fallback.
- Add structured output parsing and schema validation before PlanValidator and
  task creation.
- Harden PlanValidator for real LLM output across targets, roles,
  capabilities, allowed/denied paths, dependency graph, platform mode, and
  command policy.
- Record planner evidence in mission trace and task metadata, including
  provider identity, duration, validation result, fallback reason, error
  summary, plan source, and rationale.
- Rehearse the Breakout request with a real LLM planner provider producing the
  task, then execute through existing passthrough/coding-provider flow and
  verify diff, review, build, preview, and staging deploy evidence.

## Capabilities

### New Capabilities

- `llm-planner-engine`: Real `llm_v1` planner provider abstraction, request and
  response contract, provider execution, structured parsing, validation,
  evidence, fallback, and Breakout planner rehearsal.

### Modified Capabilities

- None.

## Impact

- Backend:
  - adds planner provider interfaces and provider selection;
  - connects `llm_v1` to a real provider path;
  - expands planner evidence and mission trace metadata;
  - hardens parsing, validation, fallback, and error normalization.
- Frontend:
  - may surface planner provider/source/evidence metadata through existing
    plan review or mission trace surfaces;
  - no broad UI redesign is required for P15b.
- Runtime and security:
  - real planner provider execution must not expose secrets or protected host
    paths;
  - all LLM planner output must pass PlanValidator before task creation;
  - deterministic fallback remains available and auditable;
  - P6-P15 baselines, Target Registry, scheduler, Agent Selection Policy,
    CanonicalSharedContext, provider instruction adapters, review, preview,
    staging deploy, and ScriptedMock fallback labeling must remain intact.
