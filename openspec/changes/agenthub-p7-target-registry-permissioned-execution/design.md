## Context

P6 is complete and tagged at `p6-agent-execution-upgrade-freeze`. It verified
that AgentHub can route a normal user request to Orchestrator, generate a
shared mini CRM contract, run Backend Agent and Frontend Agent with
`ClaudeCodeAdapter`, produce backend/frontend diffs, generate scripted review
artifacts, preview the app, and create a mock deploy card.

The P6 freeze also showed the next structural problem: target knowledge is
spread across implementation details. Today, AgentHub knows by convention that:

- demo frontend code lives in `apps/demo`;
- demo backend code lives in `apps/demo-api`;
- the AgentHub platform backend lives in `apps/api`;
- the demo backend base URL is `http://127.0.0.1:5174`;
- frontend tasks should use `apps/demo/src`;
- backend app tasks must not mutate `apps/api`;
- preview, test, and dev commands vary by target.

P7 turns those scattered conventions into a Target Project Registry so planning,
instructions, review, and execution boundaries share the same source of truth.

## Goals / Non-Goals

**Goals:**

- Define target registry records for `demo-frontend`, `demo-backend`, and
  `agenthub-platform`.
- Store or expose target metadata with allowed paths, denied paths, commands,
  base URLs, allowed agents, and platform-mode / approval requirements.
- Make role instructions read target metadata from the registry.
- Make contract-first planning reference `frontendTargetId` and
  `backendTargetId`.
- Make frontend instructions use the backend target `baseUrl` from the
  registry.
- Make review detect:
  - allowed-path violations;
  - denied-path edits;
  - accidental platform-code mutation;
  - frontend backend-base mismatches;
  - contract target inconsistency.
- Add explicit Platform Maintenance Mode for AgentHub platform code changes.
- Preserve the P6 mini CRM vertical slice.

**Non-Goals:**

- Multi-user IM.
- Matrix, Feishu, WeChat, Slack, or other external IM integration.
- Production deploy or real deploy providers.
- Docker sandbox.
- Provider marketplace.
- PR creation.
- Unrestricted repository editing.
- Distributed Manager/Worker scheduler.
- Arbitrary SaaS generation.

## Target Registry Shape

P7 should introduce a structured target record. The first implementation can be
static in code and does not need database persistence.

Suggested fields:

```text
targetId
name
type: frontend | backend | platform
root
allowedPaths
deniedPaths
devCommand
testCommand
previewCommand
baseUrl
allowedAgents
requiresPlatformMode
requiresApproval
relatedTargetIds
```

Initial targets:

```text
demo-frontend
  type: frontend
  root: apps/demo
  allowedPaths: apps/demo/src
  deniedPaths: apps/api, apps/demo-api, .env*, node_modules, .git, secrets
  devCommand: pnpm demo:dev
  previewCommand: pnpm dev --host 127.0.0.1 --port <port>
  allowedAgents: frontend, qa, review
  relatedTargetIds: demo-backend

demo-backend
  type: backend
  root: apps/demo-api
  allowedPaths: apps/demo-api
  deniedPaths: apps/api, apps/demo, .env*, node_modules, .git, secrets
  devCommand: pnpm demo:api:dev
  testCommand: pnpm demo:api:test
  baseUrl: http://127.0.0.1:5174
  allowedAgents: backend, qa, review

agenthub-platform
  type: platform
  root: .
  allowedPaths: apps/api, apps/web, scripts, docs, openspec, package metadata
  deniedPaths: .env*, node_modules, .git, secrets, unassigned host paths
  testCommand: pnpm check && pnpm test
  allowedAgents: orchestrator, backend, frontend, qa, review
  requiresPlatformMode: true
  requiresApproval: true
```

Exact allowed paths can be narrowed during implementation, but the registry
must remain the source of truth.

## Decisions

### Decision 1: Static Registry First

P7 should start with a static registry module rather than a dynamic database
model. The target set is small, known, and directly tied to the local demo
workspace. This keeps P7 focused on execution correctness instead of admin UI or
tenant configuration.

Alternative considered: persist targets in SQLite immediately. That may be
useful later, but it increases migration and UI scope before the registry
contract is proven.

### Decision 2: Target IDs In Plans And Contracts

Contracts and tasks should reference target IDs such as `demo-frontend` and
`demo-backend`. Raw paths can remain as resolved metadata for compatibility,
but the target ID is the stable planning boundary.

Alternative considered: continue storing only raw paths. That caused the P6
API-base mismatch and makes review / instruction logic drift over time.

### Decision 3: Registry-Resolved Backend Base URL

Frontend instructions should derive app data base URLs from the backend target
record. For the P6 mini CRM path, the frontend target references the
`demo-backend` target and uses its `baseUrl`.

Alternative considered: keep `demoApiBaseUrl` as a planner constant. That fixed
P6-7a, but it still leaves the value scattered outside a target relationship.

### Decision 4: Review Checks Target Policy

Review should inspect changed files and patch content against target policy:

- any file outside allowed paths should be a warning or failure;
- any denied path should be at least a warning, and platform-code edits should
  fail ordinary app tasks;
- frontend code should not call the AgentHub platform API for app data;
- contract target IDs should match the task target IDs.

P7 review remains advisory unless a later change introduces blocking gates.

### Decision 5: Platform Maintenance Requires Explicit Mode

Ordinary `@backend` or Orchestrator-created app backend tasks must target
`demo-backend`, not `apps/api`. Work on AgentHub itself requires an explicit
platform maintenance mode, targets `agenthub-platform`, and uses stricter
validation and approval.

Alternative considered: infer platform maintenance from phrases like "backend"
or "API". That is too easy to misroute and risks control-plane mutation.

## Risks / Trade-offs

- **Risk: Registry indirection breaks existing P6 behavior.** Mitigation: keep
  raw resolved paths in plan context during transition and rehearse the P6 mini
  CRM flow.
- **Risk: Platform mode becomes an escape hatch.** Mitigation: require explicit
  mode, approval, and stricter validation for `agenthub-platform`.
- **Risk: Review becomes too strict for partial serial tasks.** Mitigation:
  allow backend-only intermediate warnings while requiring the accumulated final
  full-stack diff to pass target consistency.
- **Risk: Static registry becomes stale.** Mitigation: centralize all target
  metadata and add tests that fail when planner, instruction, and review drift.

## Migration Plan

1. Add static target registry records and tests.
2. Thread target IDs and resolved target metadata into plans, contracts, context
   packs, and adapter run requests.
3. Update role instructions to use registry values.
4. Update contract-first planner to resolve frontend/backend relationships
   through the registry.
5. Update review checks to enforce target policy.
6. Add explicit platform maintenance mode.
7. Rehearse P6 mini CRM through the registry and freeze P7 only after the
   diff/review/preview/mock deploy loop remains intact.

Rollback is straightforward: planner and instruction builder can fall back to
the P6 constants while keeping the P6 freeze tag as the stable baseline.

## Open Questions

- Should `agenthub-platform` initially allow both `apps/api` and `apps/web`, or
  should it be split into `agenthub-api` and `agenthub-web` later?
- Should platform maintenance mode be triggered by a command, a UI toggle, or
  an explicit mention such as `@orchestrator platform mode ...`?
- Should target registry records be exposed in the UI during P7, or remain a
  backend capability until a later UX task?
