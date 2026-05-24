# P8 Freeze Review

**Date:** 2026-05-24

## Result

P8 is ready to freeze as Dependency-aware Scheduler and Target Locks for the
local single-user AgentHub workspace.

P8 did not run a fresh real Claude/Codex mutation. The freeze rehearsal used a
temporary git worktree and a controlled local fake adapter to verify scheduler
plumbing without spending quota or claiming unverified real-agent success. P6
remains the latest real `ClaudeCodeAdapter` mini CRM execution evidence.

## Rehearsal Evidence

The P8 rehearsal verified a bounded mini CRM scheduler path:

```text
no-mention request -> Orchestrator contract -> Backend task -> Frontend task
-> diff/review artifacts -> healthy preview -> mock deploy
```

Evidence IDs:

| Field | Value |
|---|---|
| Session ID | `3fad4108-f0ea-4134-8b31-fb2ab911fadd` |
| Contract ID | `contract-mini_crm_contacts` |
| Backend task / run | `e7f85f87-fa8a-4203-a33f-682e568a6d50`, `72cf0f92-1c65-460e-b697-4e37cbcefed0` |
| Frontend task / run | `e37a46b0-834b-4396-b703-8ecdfd1bf27b`, `bb28106d-d1f8-4431-8245-d40db304edfa` |
| Review task | `336a0c82-6caf-4d84-b421-4ccfcdd17ad7` |
| Final task states | backend `completed`, frontend `completed`, review `completed` |
| Diff artifacts | `104f1a7b-fa6f-4842-9152-a8e2acc0bbce`, `e92f2e27-c463-4a41-8dad-c7fce2eb87ce` |
| Changed files | `apps/demo-api/app/main.py`, `apps/demo/src/App.tsx` |
| Preview | `56d01fc3-affb-4f6a-bf46-973469a81e1d`, `healthy` |
| Mock deploy | `d94dade3-8b3e-4ea0-a0a9-61b2b085ce9e`, provider `mock` |

## Scheduler Evidence

Target lock evidence:

- waiting task: `7e507b15-3cd6-4be3-89d1-893e3777045a`;
- lock holder run: `3c241653-2a4e-4782-b58c-729cdc98d1bf`;
- lock error: `Waiting for target write lock: demo-frontend.`;
- after the holder completed, scheduler re-evaluated the waiting task to
  `ready`.

Failed dependency evidence:

- failed dependency task: `39d5151f-888a-4790-bd66-9044f6328053`;
- blocked downstream task: `84e11005-0148-4926-993c-6c002555507b`;
- downstream status: `blocked`;
- scheduler state: `blocked`;
- blocking dependency ID:
  `39d5151f-888a-4790-bd66-9044f6328053`.

Platform protection evidence:

- platform task: `4ed028eb-998c-4ca4-8aa0-e0c2dd9dd2f8`;
- platform run: `ca3f70d9-d4aa-49ed-9e47-c757c432bde5`;
- state: `waiting_approval`.

## Validation

| Command | Result |
|---|---|
| P8 temporary API rehearsal | Pass |
| `pnpm check` | Pass |
| `pnpm test` | Pass: 37 web tests, 155 API tests, 5 demo-api tests. |
| `pnpm demo:api:test` | Pass: 5 tests. |
| `git diff --check` | Pass |
| `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict` | Pass |

## Caveats

- The P8 freeze rehearsal used a controlled fake adapter, not real Claude Code
  or Codex. P6 remains the real ClaudeCodeAdapter full-stack evidence.
- The rehearsal used a fake healthy preview service in a temporary worktree to
  verify scheduler-to-preview/deploy plumbing without starting long-lived
  local servers.
- P8 is not a distributed worker cluster, full multi-user IM system, production
  deploy platform, Docker sandbox, provider marketplace, PR system, or
  arbitrary SaaS generator.

Recommended freeze tag:
`p8-dependency-scheduler-target-locks-freeze`.
