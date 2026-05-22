## Context

AgentHub has a frozen P4 final demo baseline and a frozen P5 local single-user
IM-style multi-agent coding workspace v1 baseline. The verified loop remains:

```text
requirement -> plan -> agent execution -> diff -> preview -> mock deploy
```

P5 improved the workspace surface with agent contacts, execution ledger,
review artifacts, execution trace, bounded dynamic frontend planning, and
artifact message cards. The remaining gap is execution capability: Claude Code
and Codex are available as strong coding adapters, but AgentHub still requires
too much explicit `@orchestrator` phrasing for normal requests and routes most
useful work through narrow planner templates that reduce tasks to the original
demo app path.

P6 focuses on making AgentHub a practical agent execution router and coordinator
before adding more UI packaging. The intended upgrade is incremental: message
routing, direct assignment, and Orchestrator auto-run first, context and
instruction quality second, and only then a bounded full-stack vertical slice.

## Goals / Non-Goals

**Goals:**

- Route messages without explicit role mentions to Orchestrator / Manager by
  default.
- Let `@frontend`, `@backend`, `@qa`, and `@review` act as explicit advanced
  assignment shortcuts that create executable tasks directly.
- Auto-start Orchestrator-created safe demo-target coding tasks through the
  existing TaskRun path.
- Preserve the user's original request on direct assignment tasks.
- Build a session context pack that gives adapters the current workspace state.
- Generate role-specific instructions for frontend, backend, QA/review, and
  manager tasks.
- Add or plan a safe demo backend target so backend execution does not mutate
  the AgentHub platform backend by default.
- Add contract-first orchestration for bounded full-stack app generation.
- Verify one mini app vertical slice with real or honestly labeled fallback
  evidence.
- Preserve the P4/P5 diff, preview, review, artifact card, and mock deploy
  baseline.

**Non-Goals:**

- Arbitrary SaaS generation.
- Unrestricted editing of the AgentHub platform codebase.
- Production deploy or real deploy providers.
- Multi-user IM or external IM integrations.
- Provider marketplace, Docker sandbox, PR creation, or enterprise approval.
- Payment, auth, multi-tenant, or compliance-heavy production systems.
- Same-session parallel write execution before conflict handling exists.

## Decisions

### Decision 1: Make Orchestrator The Default Route

Messages without explicit role mentions will route to Orchestrator / Manager by
default. The Orchestrator decides whether to answer conversationally, create
frontend/backend/QA/review tasks, generate a contract/task graph, ask a
clarifying question, or reject unsupported requests honestly.

Selected artifact context follows the same rule: it is passed to the
Orchestrator as context by default rather than bypassing the Orchestrator and
implicitly assigning work to a role.

Alternative considered: require users to always type `@orchestrator`. That
keeps routing explicit but makes normal product use feel unnatural and
reinforces the current demo-specific prompt style.

### Decision 2: Treat Role Mentions As Explicit Assignment Shortcuts

Explicit mentions have highest priority. `@orchestrator` routes to the Manager,
while `@frontend`, `@backend`, `@qa`, and `@review` create role-assigned tasks
directly when the request can be bounded to a supported target. These mentions
are advanced assignment modes for users who know which agent should own the
work.

Alternative considered: send every message through Orchestrator even when the
user explicitly mentions a role. That would simplify routing but would make
role mentions mostly cosmetic and slow down power-user workflows.

### Decision 3: Auto-Start Orchestrator-Created Safe Demo Tasks

When Orchestrator creates a safe demo-target coding task, AgentHub will
auto-start that task through the existing TaskRun lifecycle. This is an
autonomy spike, not a full approval/risk system. The auto-start boundary is
kept narrow: safe demo frontend tasks only in this slice, with backend
auto-start deferred until a demo backend target exists.

Alternative considered: always require the user to click Start. That preserves
manual control but makes it hard to evaluate whether Orchestrator can actually
drive agent execution as a product experience.

### Decision 4: Preserve Original User Requests On Direct Tasks

Direct tasks will store the original message/request alongside derived role,
target, and safety metadata. The instruction builder can add constraints and
context, but it must not collapse every request into the old login-page-only
phrasing.

Alternative considered: continue converting requests into fixed templates. That
keeps demos stable but prevents meaningful agent execution capability testing.

### Decision 5: Introduce A Session Context Pack Boundary

Adapters will receive a structured context pack containing recent messages,
execution ledger, selected artifact, latest diff metadata, changed files,
preview/deploy status, current goal, and relevant contract data. The context
pack becomes the boundary between chat state and adapter prompts.

Alternative considered: have each adapter fetch context ad hoc. That risks
inconsistent prompts, cross-session leakage, and hard-to-test behavior.

### Decision 6: Use Role-Based Instruction Builder

Frontend, backend, QA/review, and manager roles need different instructions:

- frontend instructions focus on `apps/demo` UI files and previewability;
- backend instructions focus on the demo backend target, not AgentHub's own
  FastAPI app;
- QA/review instructions focus on diff, contract, risk, and non-blocking
  findings;
- manager instructions focus on contracts, task graph, dependencies, and
  clarification when unsupported.

Alternative considered: pass a generic instruction to every adapter. That would
make role assignment mostly cosmetic and would not improve backend/review
quality.

### Decision 7: Add A Safe Demo Backend Target

P6 backend execution should target a demo backend such as `apps/demo-api`.
Backend Agent tasks must not freely mutate `apps/api`, because that is the
AgentHub platform backend and part of the control plane.

Alternative considered: allow backend tasks inside `apps/api`. That is tempting
for speed but blurs product-under-test and platform code, increasing risk to
the control plane.

### Decision 8: Use Contract-First Full-Stack Orchestration

For bounded mini app generation, Orchestrator will first create a structured
contract that backend and frontend tasks reference. This can be triggered by an
explicit `@orchestrator` mention or by a normal unmentioned request routed to
Orchestrator by default. The contract defines app goal, entities, API
endpoints, UI screens, acceptance criteria, and target directories.

Alternative considered: let frontend and backend tasks independently interpret
the same user prompt. That is fast but causes drift between API behavior and UI
expectations.

### Decision 9: Keep Same-Session Write Tasks Serial

P6 may plan frontend and backend tasks as separate steps, but write tasks in the
same session remain serial until conflict detection, locks, merge strategy, and
recovery UX exist.

Alternative considered: allow immediate parallel execution. That would create a
more impressive demo but risks corrupting shared worktrees and producing
conflicting diffs.

## Risks / Trade-offs

- **Risk: Direct mention execution enables broad, unsafe requests.** Mitigation:
  bound each direct task to supported roles, safe target directories, protected
  paths, and honest unsupported/clarification states.
- **Risk: Auto-run starts unsafe work.** Mitigation: limit P6-1 auto-run to
  Orchestrator-created safe demo-target coding tasks and preserve protected
  paths, command allowlist, and adapter guardrails.
- **Risk: Default Orchestrator routing hides user intent.** Mitigation:
  explicit role mentions have highest priority and selected artifact context is
  included in the Orchestrator context pack.
- **Risk: Less restrictive instructions reduce demo determinism.** Mitigation:
  keep P4/P5 paths intact, preserve fallback execution, and add targeted tests
  for instruction construction and routing.
- **Risk: Backend target scaffold increases project complexity.** Mitigation:
  keep `apps/demo-api` intentionally small, local, and separate from
  AgentHub's platform API.
- **Risk: Contract-first planning becomes overbuilt.** Mitigation: support one
  bounded mini app family first, with a small schema and explicit non-goals.
- **Risk: Review output appears authoritative.** Mitigation: keep P6 review
  advisory unless a later change implements gates.
- **Risk: Context packs leak data between sessions.** Mitigation: construct
  packs from current-session records only and test session isolation.

## Migration Plan

1. Add message routing policy: explicit mentions first, otherwise route to
   Orchestrator / Manager by default.
2. Add narrow Orchestrator auto-run for safe demo-target tasks through the
   existing TaskRun path.
3. Add context pack generation and use it in instructions while preserving the
   existing TaskRun lifecycle.
4. Add role-based instruction builder and tests for each role.
5. Add the demo backend target and update safe target metadata.
6. Add contract-first orchestrator output for one bounded full-stack mini app.
7. Rehearse the full P6 vertical slice and freeze only after validation.

Rollback is straightforward while P6 is task-scoped: disable direct mention task
creation and fall back to the existing P5 planner/task path.

## Open Questions

- Should `@review` be backed by a real seeded `Agent` row or remain a virtual
  contact with review-specific execution metadata in P6-1?
- Should `apps/demo-api` be Node, FastAPI, or a minimal local JSON API? The
  safest choice should match the repo's current tooling and keep setup simple.
- Should the mini app vertical slice be todo, notes, or mini CRM contacts? Mini
  CRM contacts best demonstrates frontend/backend contract value, while todo is
  simpler for first rehearsal.
