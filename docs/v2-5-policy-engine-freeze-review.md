# V2.5 Policy Engine Freeze Review

**Date:** 2026-06-09

## Scope

V2.5 adds a standalone Policy Engine contract and side-effect-free policy
evaluation helpers. The goal is to unify policy decisions without widening
AgentHub execution permissions.

Implemented:

- Policy categories: command, path, network, cost, destructive change, deploy,
  and platform maintenance.
- Policy outcomes: allow, deny, require approval, require elevated approval.
- Risk levels, approval types, decision evidence, and safe metadata redaction.
- Command policy helper backed by existing Project Command Policy.
- Path policy helper backed by existing Target Registry / Guardrails semantics.
- Network policy helper that defaults to approval required.
- Deploy policy helper that allows local/mock staging, requires approval for
  external staging, and denies production deploy by default.
- Platform maintenance helper that requires elevated approval for AgentHub
  platform targets.
- Approval timeout helper that defaults to deny.
- Stable `policy.decision` evidence payload helper.

## Safety

- V2.5 does not replace Target Registry, PlanValidator, Guardrails, Provider
  Gateway, Scheduler, or adapters.
- V2.5 does not add arbitrary shell-command agents, marketplace behavior,
  production deployment, Docker sandbox, WebSocket, cloud secret manager, or
  PR creation.
- Generic repo and project profile metadata do not allow unconfigured commands.
- External network and third-party deploy remain approval-gated.
- Platform maintenance requires elevated approval.
- Policy evidence is redacted before serialization.

## Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_policy_engine.py -q` | Pass |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_policy_engine.py tests/test_guardrails.py tests/test_project_command_policy.py -q` | Pass |
| `pnpm check` | Pass |
| `pnpm test` | Pass, web 90 / API 568 / demo-api 5 |
| `pnpm demo:api:test` | Pass, 5 tests |
| `openspec validate agenthub-v2-5-policy-engine --strict` | Pass |
| `git diff --check` | Pass |

## Limitations

- V2.5 intentionally adds a contract/helper layer first. Existing Run Engine,
  Approval, Deploy, and Transactional Delivery paths are not fully rewired to
  require Policy Engine decisions yet.
- Policy evidence can be consumed by Run Diagnostics / MissionTrace in later
  phases, but V2.5 does not add a new UI.
- Cost and destructive-change policies are represented in the contract and can
  be expanded when V2.6 transactional delivery introduces richer change gates.

## Follow-up

Recommended next implementation task: start V2.6 Transactional Delivery so
preflight, validation, accept, rollback, and retry can call Policy Engine
decisions at the right execution points.
