# P7 Target Registry Freeze Review

**Date:** 2026-05-24

## Result

P7 is ready to freeze as Target Project Registry + Permissioned Execution for
the local single-user AgentHub workspace.

P7 did not run a new real Claude/Codex mutation. The freeze review reuses the
P6 final real `ClaudeCodeAdapter` mini CRM evidence for diff, review, preview,
and mock deploy, then verifies the new P7 target-registry layer through API
rehearsal and full regression validation.

## P7 API Rehearsal Evidence

Mini CRM request:

```text
帮我做一个 mini CRM，包含联系人和备注
```

Evidence:

- session ID: `d0500f2c-a480-4903-aea5-5d2d72b2bf31`;
- message status: `201`;
- contract ID: `contract-mini_crm_contacts`;
- frontend target ID: `demo-frontend`;
- backend target ID: `demo-backend`;
- demo API base URL: `http://127.0.0.1:5174`;
- task IDs:
  - `952bcfd1-12b9-41ca-b81d-694a66b4dcea`;
  - `d382a368-0cd2-4d46-86c6-790b691d4b58`;
  - `5966d060-0df4-463d-94e1-d7bebdddf729`;
  - `634bb541-3b0e-47ad-a408-13392b6dea11`;
- task roles: `orchestrator`, `backend`, `frontend`, `qa`;
- target IDs by task: planning task has no concrete write target,
  then `demo-backend`, `demo-frontend`, and `demo-frontend`.

Platform maintenance request:

```text
@backend platform mode update AgentHub API health metadata
```

Evidence:

- session ID: `57d92dde-710f-484e-b86a-f7c0e06e22e6`;
- message status: `201`;
- task ID: `fc86452a-a92b-4894-844d-372b5df799e1`;
- target ID: `agenthub-platform`;
- `platformMode`: `true`;
- `requiresApproval`: `true`;
- task run ID: `7ef6efcb-979c-4984-a1a2-2f29f893bc79`;
- task run state: `waiting_approval`;
- approval type / risk: `security_approval`, `high`.

## Reused P6 Real Execution Evidence

P6 final rehearsal remains the real execution evidence for the bounded mini CRM
vertical slice:

- session ID: `d39ed32a-8426-4c75-86a1-9fd10a57f44c`;
- contract ID: `contract-mini_crm_contacts`;
- backend task / run: `efe6482b-b2e3-43a7-bae9-2aa0b44dde41`,
  `908a5708-3334-474c-8af6-b18e6ceaa319`;
- frontend task / run: `f1d141d1-7fcb-4629-9ed1-20fd957d6ef4`,
  `7a01e9ea-8d5d-4690-ae4c-35fbca0b6309`;
- adapter type for both coding runs: `claude_code`;
- final diff artifact ID: `a89dba5d-cc92-490c-aca1-6c00cd20cc5c`;
- final review artifact ID: `076f01c5-1949-4fa6-9715-623e41642edb`;
- preview ID / URL / health:
  `d515ffaf-bf9d-481d-9b51-77aa57eb2cef`,
  `http://127.0.0.1:62947`, healthy;
- mock deployment ID / provider / status:
  `ff54062e-35ca-462d-a5f7-e9a4786517ec`, `mock`, `ready`.

The P6 preview loaded contacts from the safe demo backend at
`http://127.0.0.1:5174`. P7 now makes that backend base URL registry-resolved
through `demo-backend`.

## What P7 Verified

- `demo-frontend`, `demo-backend`, and `agenthub-platform` are registry
  targets.
- Contract-first mini CRM planning emits `frontendTargetId` and
  `backendTargetId`.
- Frontend instructions receive the registry-resolved `demo-backend` base URL.
- Backend instructions target `demo-backend`, not `apps/api`.
- Target-aware review reports `apps/api` mutation as a high-risk failure for
  ordinary app tasks.
- Explicit platform maintenance creates `agenthub-platform` tasks and requires
  approval before adapter execution.
- P4/P5/P6 tests continue to pass.

## Remaining Caveats

- P7 did not run a fresh real Claude/Codex mutation after the registry
  migration; it reused the P6 real execution evidence and validated P7 through
  targeted API/unit regression.
- Review remains deterministic `scripted_mock`, not real Claude review.
- Platform maintenance approval is a local guardrail, not enterprise RBAC.
- Deployment remains mock-labeled and is not production deployment.
- P7 does not add Docker sandboxing, PR creation, external IM integration,
  multi-user sync, or arbitrary SaaS generation.

Recommended freeze tag: `p7-target-registry-permissioned-execution-freeze`.
