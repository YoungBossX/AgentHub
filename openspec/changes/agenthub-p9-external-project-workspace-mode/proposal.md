## Why

P6 proved AgentHub can coordinate a bounded full-stack mini CRM against the
built-in demo frontend and demo backend. P7 made those targets explicit through
the Target Project Registry, and P8 added dependency-aware scheduling, target
write locks, failure blocking, and scheduler UI trace. However, AgentHub still
mainly operates on built-in demo targets:

- `demo-frontend`: `apps/demo`;
- `demo-backend`: `apps/demo-api`;
- `agenthub-platform`: AgentHub maintenance.

P9 is needed so a user-selected local project can become a first-class
AgentHub workspace. This is a practical execution capability upgrade: Claude
Code and Codex should be able to work on registered external project targets
with explicit path boundaries, detected commands, scheduler locks, review
checks, and evidence artifacts.

## What Changes

- Add external workspace registration for local project roots.
- Add a project analyzer that detects framework/type, safe commands, package
  manager, default allowed paths, and uncertainty.
- Integrate external targets with the existing Target Project Registry model so
  planner, instruction builder, review, and scheduler consume one target shape.
- Build target-aware instructions for external frontend, backend, QA, and
  review tasks without assuming `apps/demo` or `apps/demo-api`.
- Allow Orchestrator and explicit `@frontend`, `@backend`, `@qa`, and
  `@review` assignments to create executable tasks against registered external
  targets.
- Extend the evidence pipeline for external targets with git diff, check/test
  output, build output, and preview URL when configured.
- Extend review to enforce external allowed/denied paths and report failed
  checks honestly.
- Rehearse P9 against a local sample external project while preserving P6/P7/P8
  built-in demo behavior.

P9 must be more than a conservative metadata-only binding. The goal is for
registered external local projects to be runnable AgentHub targets that can
receive real coding tasks through `ClaudeCodeAdapter` / `CodexAdapter` when the
user chooses to run them.

## Capabilities

### New Capabilities

- `external-workspace`: registration, analysis, target-registry integration,
  role instructions, task execution, evidence, review, and rehearsal for
  external local project workspaces.

### Modified Capabilities

- Target Registry consumers must support external target metadata while
  preserving built-in `demo-frontend`, `demo-backend`, and `agenthub-platform`.
- Planner / Orchestrator should route registered external workspace requests to
  external targets when explicitly selected.
- Scheduler target locks must apply to external targets.
- Review must enforce external path policy and command evidence.

## Impact

OpenSpec artifacts:

- `openspec/changes/agenthub-p9-external-project-workspace-mode/proposal.md`
- `openspec/changes/agenthub-p9-external-project-workspace-mode/design.md`
- `openspec/changes/agenthub-p9-external-project-workspace-mode/tasks.md`
- `openspec/changes/agenthub-p9-external-project-workspace-mode/specs/external-workspace/spec.md`

Expected implementation impact when P9 is later applied:

- Backend:
  - persisted external workspace / target registration;
  - project analyzer service;
  - dynamic external target registry entries;
  - external target-aware planning and direct mention assignment;
  - external evidence artifacts for command output;
  - external review checks for path policy and command result honesty.
- Frontend:
  - external project registration UI;
  - project analysis/confirmation UI;
  - selected workspace/target indicator in chat and task surfaces;
  - external evidence cards for diff/check/test/build/preview where
    available.
- Runtime:
  - adapters execute only inside explicitly registered external target roots or
    their assigned worktrees;
  - denied paths include `.env`, `.env.*`, `secrets`, `.git`, `node_modules`,
    `.venv`, generated dependency directories, and unsafe system paths;
  - external target locks prevent same-target write conflicts;
  - failed commands are recorded honestly and must not be converted into
    success claims.
