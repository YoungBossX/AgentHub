# V2.4 Project Profile Boundary Freeze Review

**Date:** 2026-06-09

## Scope

V2.4 adds a ProjectProfile boundary for registered projects. It turns existing
project analysis and target metadata into an auditable profile summary without
changing the hard execution boundary.

Implemented:

- ProjectProfile contract with profile id, display name, project type,
  framework, package manager, allowed/denied paths, commands, preview strategy,
  confidence, status, and warnings.
- Project analyzer output now includes `projectProfile`.
- External target and workspace target responses expose derived
  `projectProfile` summaries.
- TargetProject can carry a derived project profile for external targets.
- Project command policy has direct coverage for configured commands, missing
  commands, mismatched commands, unknown command types, and conservative generic
  repo behavior.
- Coding-agent target instructions include project profile id, status, preview
  strategy, and configured profile commands.

## Safety

- ProjectProfile is descriptive context, not an authorization boundary.
- Target Registry, PlanValidator, Guardrails, Provider Gateway, and command
  policy remain the hard execution controls.
- Generic Repo does not open arbitrary shell commands; only explicitly
  configured validation commands are allowed.
- Protected paths remain denied: `.git`, `.env*`, `secrets`, `node_modules`,
  virtualenv/cache/build outputs, and target-outside paths.
- Platform maintenance still requires explicit platform mode and approval.
- No new adapter, provider marketplace, WebSocket, Docker sandbox, PR creation,
  production deployment, or arbitrary shell-command agent was added.

## Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_project_profiles.py tests/test_project_analyzer.py -q` | Pass |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_external_workspaces.py tests/test_target_registry.py tests/test_project_profiles.py tests/test_project_analyzer.py -q` | Pass |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_project_command_policy.py tests/test_external_evidence.py -q` | Pass |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_task_runs.py::test_external_target_context_reaches_instruction_builder tests/test_task_runs.py::test_external_backend_instruction_uses_external_target_metadata -q` | Pass |
| `pnpm check` | Pass |
| `pnpm test` | Pass, web 90 / API 556 / demo-api 5 |
| `pnpm demo:api:test` | Pass, 5 tests |
| `openspec validate agenthub-v2-4-project-profile-boundary --strict` | Pass |
| `git diff --check` | Pass |

## Limitations

- ProjectProfile metadata is derived from existing target fields; V2.4 does not
  add a database column or migration for profile snapshots.
- Next.js and FastAPI preview strategies are recorded as metadata, but V2.4
  does not productize full preview hosting for every framework.
- Planner target summaries still rely on the existing context paths. V2.4 adds
  profile context to coding-agent instructions and target APIs without changing
  planner routing semantics.
- Policy Engine, transactional delivery, checkpoint rollback, and production
  deploy approval remain later Reliability V2 phases.

## Follow-up

Recommended next implementation task: start V2.5 Policy Engine with a small
backend-only policy contract that consumes Target Registry, ProjectProfile, and
existing guardrail signals, returning `allow`, `deny`, `require_approval`, or
`require_elevated_approval`.
