## Context

AgentHub has moved beyond a simple demo. P6-P11 added real coding adapters,
target-aware execution, dependency scheduling, external workspaces, robustness
recovery, and local staging deployment. Those capabilities work, but the core
implementation has grown by layering behavior into a few large modules:

- `planning.py` owns mention routing, demo fallbacks, orchestrator planning,
  full-stack contract planning, target selection, and task graph assembly.
- `main.py` owns API routes, response mapping, execution orchestration,
  auto-preview/deploy behavior, and service wiring.
- `instruction_builder.py` mixes role logic, provider conventions, target
  rules, and session context prompt formatting.
- `context_pack.py` is useful, but not yet a formal context contract that can
  be shared by planner, scheduler, adapters, review, and UI.
- `workspace-shell.tsx` and `task-card-list.tsx` carry too much UI state and
  behavior for upcoming mission/artifact/custom-agent work.
- Artifacts exist, but handoff, references, selected context, and version
  history are not first-class enough for P13-P16.

P12 is therefore a consolidation phase. It is not meant to add flashy product
features. It creates stable platform core boundaries so later phases can add
custom agents, artifact editing, mission control, and multi-end surfaces
without piling more behavior into already large modules.

## Goals / Non-Goals

**Goals:**

- Preserve P6-P11 baselines while refactoring the core into clearer service
  boundaries.
- Split planner/orchestrator logic into planner service, task graph builder,
  plan validator, and demo fallback planner.
- Formalize `CanonicalSharedContext` with provenance, visibility, trust level,
  guardrails, safe path filtering, and persisted snapshots.
- Refactor provider instruction generation into provider-specific adapters that
  consume canonical context.
- Add first-class handoff artifacts and artifact references for downstream
  tasks and follow-up messages.
- Add a mission trace response foundation for P15 mission control.
- Decompose large web workspace components without changing user-facing
  behavior.
- Add an artifact version skeleton and minimal agent profile foundation.
- Rehearse the complete baseline through login page, diff, handoff, review,
  preview, local staging deploy, follow-up, artifact v2, and updated preview/
  deploy evidence.

**Non-Goals:**

- New provider marketplace.
- User-created custom agents UI.
- Full artifact editor.
- Document/PPT rendering or paragraph-level references.
- Multi-user mission control.
- Desktop, IDE, or CLI clients.
- Cloud deployment provider.
- LLM dynamic planner.
- Replacing the scheduler with LangGraph, CrewAI, or another orchestration
  framework.

## Decisions

### Decision: Consolidate Around Stable Internal Contracts

P12 will introduce explicit internal contracts before adding more product
surface:

```text
PlanDraft
CanonicalSharedContext
ProviderInstructionRequest
HandoffArtifact
ArtifactReference
SessionMissionTraceResponse
ArtifactVersion
AgentProfile
```

Rationale: P13-P16 all need the same concepts. If those concepts stay implicit
inside planner, prompt strings, artifact metadata, and UI component state,
later phases will duplicate logic and increase coupling.

Alternative considered: continue adding features directly to current modules.
Rejected because `planning.py`, `main.py`, `instruction_builder.py`, and the
main workspace components are already carrying too many unrelated
responsibilities.

### Decision: Refactor Planner Without Changing Current Routing Semantics

The planner layer should become:

```text
planner_service.py
task_graph_builder.py
plan_validator.py
demo_planner.py
```

`planner_service.py` owns message-to-plan flow and delegates. `task_graph_builder.py`
builds normalized task graphs. `plan_validator.py` validates dependencies,
targets, planned files, and fallback safety. `demo_planner.py` preserves login
page, dashboard, mini CRM, and deterministic fallback behavior.

Rationale: P12 must preserve the working demo/full-stack paths while making
planner output easier to validate and consume.

Alternative considered: replace the planner with an LLM planner. Rejected for
P12 because the goal is consolidation, not new planning intelligence.

### Decision: Canonical Context Is Data First, Prompt Second

`CanonicalSharedContext` should be a structured object used by planner,
instruction adapters, review, scheduler, and UI. Provider prompts are rendered
from that object, not assembled directly from scattered services.

Every context field should carry:

```text
source
visibility
created_at
trust_level
```

Protected host paths, secrets, `.env`, dependency directories, and unassigned
host paths must be filtered before provider-visible context is generated.

Rationale: provider instructions become safer and more consistent when all
providers consume the same vetted context snapshot.

Alternative considered: keep extending `context_pack.py` as an ad hoc dict.
Rejected because upcoming artifact references and custom agents need a stable
contract.

### Decision: Provider Instruction Adapters Are Thin Renderers

Provider-specific modules should live under:

```text
instruction_adapters/base.py
instruction_adapters/codex.py
instruction_adapters/claude_code.py
instruction_adapters/scripted_mock.py
instruction_adapters/shared_sections.py
```

The adapters render provider-specific instructions from the same canonical
context. They do not own target policy, artifact lookup, or session context
collection.

Rationale: Codex, Claude Code, and ScriptedMock need different wording and
capability flags, but they must not drift on safety boundaries or task context.

Alternative considered: one giant instruction builder with provider branches.
Rejected because it has already become difficult to change safely.

### Decision: Handoff And References Become Artifact-layer Concepts

P12 should treat handoff and artifact references as first-class platform
concepts:

- handoff artifacts summarize upstream output for downstream tasks;
- artifact references connect messages/tasks/context to diff, review, preview,
  and deployment artifacts;
- selected artifact context flows into canonical context and provider
  instructions.

Rationale: P14 artifact editing and P15 mission control need navigable,
versioned references instead of hidden context strings.

Alternative considered: continue storing handoff text in task plan JSON.
Rejected because that would make downstream context and UI navigation brittle.

### Decision: Mission Trace Is A Read Model

`SessionMissionTraceResponse` should aggregate existing tasks, TaskRuns,
events, artifacts, blockers, and next actions. It should not replace the
scheduler or become a second write path.

Rationale: P15 mission control needs a stable read model before adding complex
interactive controls.

Alternative considered: build mission control UI directly from many existing
endpoints. Rejected because UI clients would recreate backend graph logic.

### Decision: Web Decomposition Must Be Behavior-preserving

Large workspace components should be split into focused components:

```text
session-sidebar
agent-contact-list
chat-thread
message-composer
mission-panel
artifact-panel
task-card
run-history
run-controls
artifact-chips
```

Message actions should be limited to existing or safe first-stage behavior:
copy, quote as context, use artifact as context, retry failed run, and open
artifact.

Rationale: P13-P16 will add more UI surface. The current large components make
that risky.

Alternative considered: redesign the UI. Rejected because P12 is an
architecture consolidation phase, not a visual redesign.

## Risks / Trade-offs

- **Risk: behavior-preserving refactor accidentally changes routing or demo
  fallback.** Mitigation: implement one task at a time, add regression tests,
  and rehearse the baseline loop before freeze.
- **Risk: canonical context leaks protected host paths or secrets.**
  Mitigation: enforce protected-path filtering before provider-visible context
  is built, and test `.env`, `node_modules`, `.git`, and unassigned host path
  exclusion.
- **Risk: schema additions make the demo database harder to reset.**
  Mitigation: keep additions minimal and compatible with existing SQLite demo
  setup.
- **Risk: provider instruction adapters drift.** Mitigation: shared sections
  own common safety/target/context text; provider adapters render only
  provider-specific framing.
- **Risk: UI decomposition becomes a redesign.** Mitigation: preserve visible
  layout and existing tests, moving behavior into smaller components
  incrementally.
- **Risk: P12 becomes a feature grab bag.** Mitigation: keep custom agents,
  full artifact editing, mission control commands, and multi-end support as
  later phases.

## Migration Plan

1. Add planner service boundaries and PlanDraft while keeping public planner
   behavior stable.
2. Formalize canonical context and persist snapshots without changing adapter
   execution semantics.
3. Add provider instruction adapters behind the existing adapter dispatch.
4. Add handoff artifacts and artifact references, then feed them into context.
5. Add mission trace read model.
6. Decompose web components with existing behavior and tests preserved.
7. Add artifact version and agent profile foundations.
8. Run the P12 rehearsal and freeze review.

Rollback strategy: keep legacy planner/instruction paths callable until the new
services pass regression coverage. If a new boundary fails, route back to the
existing behavior and keep the phase paused rather than weakening safety.

## Open Questions

- Should handoff artifacts be generated for every dependency edge or only for
  write-to-read/write handoffs?
- Should context snapshots be stored in TaskRun metrics JSON initially or as a
  separate artifact/metadata table?
- Should artifact references become a table in P12 or begin as a normalized
  metadata concept with a migration path?
- Should mission trace include full event payloads or summarized event
  projections in v1?
