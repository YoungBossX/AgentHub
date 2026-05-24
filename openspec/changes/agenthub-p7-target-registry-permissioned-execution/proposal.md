## Why

P6 proved that AgentHub can coordinate a bounded full-stack mini CRM flow with
real `ClaudeCodeAdapter` execution, but it also exposed that target knowledge is
scattered across planner logic, instruction text, review checks, scripts, and
docs. P7 is needed so agents can execute against explicit target projects with
known allowed paths, denied paths, validation commands, preview settings, and
backend base URLs.

## What Changes

- Introduce a Target Project Registry as the source of truth for supported
  execution targets:
  - `demo-frontend` for `apps/demo`;
  - `demo-backend` for `apps/demo-api`;
  - `agenthub-platform` for AgentHub platform maintenance.
- Move target metadata into registry records, including:
  - target ID, display name, target type, root, allowed paths, denied paths,
    dev/test/preview commands, base URL, allowed agents, and platform-mode /
    approval requirements.
- Make the instruction builder target-aware so role instructions use registry
  metadata rather than scattered hardcoded paths and URLs.
- Make contract-first planning target-aware by referencing
  `frontendTargetId` and `backendTargetId`, then deriving raw paths and backend
  base URLs from the registry.
- Make review / QA target-aware by checking allowed-path violations,
  forbidden platform-code edits, frontend backend-base mismatches, and contract
  target consistency.
- Add an explicit Platform Maintenance Mode so ordinary application backend
  tasks remain isolated from `apps/api`, while platform maintenance can target
  `agenthub-platform` only when explicitly requested and approved.
- Rehearse P7 against the P6 mini CRM path to verify that target registry
  indirection preserves the full P6 diff / review / preview / mock deploy
  baseline.

## Capabilities

### New Capabilities

- `target-registry`: Target project registry, permissioned execution metadata,
  target-aware planning/instructions/review, and explicit platform maintenance
  mode.

### Modified Capabilities

None. P7 introduces a new capability while preserving the P4/P5/P6 baseline.

## Impact

OpenSpec artifacts:

- `openspec/changes/agenthub-p7-target-registry-permissioned-execution/proposal.md`
- `openspec/changes/agenthub-p7-target-registry-permissioned-execution/design.md`
- `openspec/changes/agenthub-p7-target-registry-permissioned-execution/tasks.md`
- `openspec/changes/agenthub-p7-target-registry-permissioned-execution/specs/target-registry/spec.md`

Expected implementation impact when P7 is later applied:

- Backend:
  - target registry module or service;
  - target metadata included in context packs and adapter run requests;
  - planner updates to use target IDs and registry-resolved metadata;
  - instruction builder updates to consume registry records;
  - review / QA checks for target policy, allowed paths, denied paths, and
    backend base URL consistency;
  - explicit platform maintenance routing and approval boundary.
- Frontend:
  - no required broad redesign;
  - optional display of target names / modes on task, context, and artifact
    surfaces if needed for clarity.
- Data model:
  - P7 can start with static in-code registry records;
  - persistence is optional and deferred unless implementation needs it.
- Runtime:
  - same-session write tasks remain serial;
  - ordinary application tasks stay inside `apps/demo` and `apps/demo-api`;
  - `apps/api` remains protected unless platform maintenance mode is explicit.

P7 does not add multi-user IM, external IM integration, production deployment,
Docker sandboxing, provider marketplace, PR creation, unrestricted repository
editing, distributed scheduling, or arbitrary SaaS generation.
