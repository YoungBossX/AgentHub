## Why

P6-P11 proved AgentHub can execute real local coding workflows, but the core is
now spread across tightly coupled planning, API orchestration, instruction,
context, artifact, and UI modules. P12 consolidates those foundations before
P13 custom agents, P14 artifact editing, P15 mission control, and P16 multi-end
support add more surface area.

## What Changes

- Split planner/orchestrator responsibilities into clearer service boundaries:
  planner service, task graph builder, plan validator, and demo fallback
  planner.
- Formalize a canonical shared context contract with provenance, visibility,
  trust level, protected-path filtering, and persisted context snapshots.
- Refactor provider instruction generation into provider-specific instruction
  adapters that consume the same canonical context.
- Add first-class handoff artifacts so upstream task output can be referenced
  by downstream tasks.
- Add an artifact reference concept for diff, review, preview, and deployment
  follow-up context.
- Add a mission trace foundation that exposes current goal, tasks, runs,
  events, artifacts, blockers, and next actions.
- Decompose large web workspace components into smaller mission/chat/artifact/
  run components while preserving existing behavior.
- Add an artifact version history skeleton for v1/v2 follow-up chains.
- Stabilize a minimal AgentProfile schema for built-in agents without adding
  full user-created custom agents.
- Rehearse the complete baseline loop through diff, handoff, review, preview,
  local staging deploy, follow-up, and artifact v2 evidence.

## Capabilities

### New Capabilities

- `platform-core`: Consolidated planner boundaries, canonical shared context,
  provider instruction adapters, handoff artifacts, artifact references,
  mission trace foundation, web component decomposition, artifact version
  skeleton, and minimal agent profile foundation.

### Modified Capabilities

None. P12 introduces an architecture consolidation capability and preserves
existing P6-P11 behavior.

## Impact

- Backend:
  - `planning.py`, `instruction_builder.py`, `context_pack.py`, `main.py`,
    task graph, artifact, review, scheduler, and deploy integration points;
  - new or standardized service modules for planner, task graph, validation,
    demo fallback, canonical context, instruction adapters, handoff artifacts,
    artifact references, mission traces, artifact versions, and agent profiles;
  - persistence and response schema additions where needed.
- Frontend:
  - decomposition of `workspace-shell.tsx` and `task-card-list.tsx` into
    focused session, chat, mission, artifact, task, run, and action
    components;
  - first-stage message actions for copy, quote as context, use artifact as
    context, retry failed run, and open artifact.
- Runtime:
  - behavior-preserving refactor with no Claude/Codex execution during
    implementation unless a later rehearsal explicitly requests it;
  - P6 mini CRM, P7 target registry, P8 scheduler, P9 external workspace, P10
    recovery, and P11 staging deploy baselines must remain intact.
