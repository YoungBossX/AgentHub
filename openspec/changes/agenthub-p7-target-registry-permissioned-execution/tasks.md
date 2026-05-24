## 1. P7 Target Registry And Permissioned Execution

- [x] 1.1 P7-1 Target Project Registry.
  - Objective: Define a single source of truth for supported target projects.
  - Scope:
    - create registry records for `demo-frontend`, `demo-backend`, and
      `agenthub-platform`;
    - include `targetId`, `name`, `type`, `root`, `allowedPaths`,
      `deniedPaths`, `devCommand`, `testCommand`, `previewCommand` when
      applicable, `baseUrl` when applicable, `allowedAgents`,
      `requiresPlatformMode`, and `requiresApproval`;
    - provide lookup helpers by target ID and relationship helpers between
      frontend and backend targets;
    - keep registry static/in-code for P7 unless implementation discovers a
      need for persistence;
    - add tests for registry contents and denied-path defaults.
  - Acceptance criteria:
    - target metadata for demo frontend, demo backend, and AgentHub platform is
      available from one registry boundary;
    - demo backend base URL is available only through target metadata;
    - `apps/api` is denied for ordinary app backend targets;
    - platform target requires explicit platform mode and approval.
  - Validation:
    - registry unit tests;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - `openspec validate agenthub-p7-target-registry-permissioned-execution --strict`.

- [ ] 1.2 P7-2 Target-aware Instruction Builder.
  - Objective: Generate role instructions from target registry metadata.
  - Scope:
    - update frontend, backend, QA, and review instructions to resolve target
      metadata from `targetId`;
    - remove scattered hardcoded target paths and base URLs where practical;
    - ensure frontend instructions use the backend target `baseUrl` from the
      registry for app data calls;
    - keep guardrails for `.env*`, `node_modules`, `.git`, `secrets`, and
      unassigned host paths;
    - preserve P6 instruction behavior for the mini CRM path.
  - Acceptance criteria:
    - frontend contract instructions reference `demo-frontend` and the
      registry-resolved `demo-backend` base URL;
    - backend instructions target `demo-backend` and forbid `apps/api`;
    - platform instructions are produced only for explicit platform mode;
    - existing P6 role-instruction tests continue to pass after registry
      migration.
  - Validation:
    - instruction builder tests;
    - adapter request construction tests;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - `openspec validate agenthub-p7-target-registry-permissioned-execution --strict`.

- [ ] 1.3 P7-3 Target-aware Contract Planner.
  - Objective: Make app contracts and generated tasks target-ID based.
  - Scope:
    - add `frontendTargetId` and `backendTargetId` to app contracts;
    - derive `frontendTarget`, `backendTarget`, and backend base URL from the
      registry;
    - generate frontend/backend/review task plans with `targetId` and resolved
      target metadata;
    - keep deterministic unsupported-request behavior;
    - preserve todo, notes, and mini CRM contacts bounded app planning.
  - Acceptance criteria:
    - mini CRM contracts reference `demo-frontend` and `demo-backend`;
    - generated frontend/backend tasks reference target IDs, not only raw
      paths;
    - frontend tasks receive the registry-resolved demo backend base URL;
    - unsupported platform or arbitrary SaaS requests fail honestly or request
      clarification.
  - Validation:
    - planning tests;
    - contract schema tests;
    - unsupported request tests;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - `openspec validate agenthub-p7-target-registry-permissioned-execution --strict`.

- [ ] 1.4 P7-4 Target-aware Review / QA.
  - Objective: Review diffs and contracts against target registry policy.
  - Scope:
    - check changed files against target `allowedPaths`;
    - warn or fail on target `deniedPaths`;
    - detect accidental `apps/api` modification for ordinary app backend tasks;
    - detect frontend calls to a backend base URL that does not match the
      registry-resolved backend target;
    - verify contract target IDs match task target IDs and changed-file
      prefixes;
    - keep review advisory in P7 unless a later change introduces hard gates.
  - Acceptance criteria:
    - ordinary app backend diffs that touch `apps/api` are reported as target
      policy violations;
    - frontend diffs that call `http://localhost:8000` for app data are
      reported as backend-base mismatches;
    - full-stack diffs that touch only `demo-frontend` and `demo-backend`
      allowed paths pass target consistency checks;
    - intermediate backend-only serial diffs may warn until the accumulated
      frontend diff exists.
  - Validation:
    - review unit tests;
    - regression tests for P6 mini CRM review behavior;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - `openspec validate agenthub-p7-target-registry-permissioned-execution --strict`.

- [ ] 1.5 P7-5 Platform Maintenance Mode.
  - Objective: Explicitly separate app development tasks from AgentHub platform
    maintenance tasks.
  - Scope:
    - ordinary `@backend` and Orchestrator-created app backend tasks must
      target `demo-backend`, not `agenthub-platform`;
    - add explicit platform maintenance routing or task metadata;
    - platform maintenance tasks target `agenthub-platform`;
    - platform tasks require platform mode and approval;
    - platform tasks use stricter validation, such as `pnpm check` and
      `pnpm test`;
    - unsupported ambiguous requests must not silently execute against
      `apps/api`.
  - Acceptance criteria:
    - `@backend add endpoint` creates a demo backend task by default;
    - requests to modify AgentHub platform backend require explicit platform
      mode;
    - platform-mode tasks are labeled as platform maintenance and include
      stricter validation expectations;
    - no ordinary app task can modify `apps/api` without review warning or
      failure.
  - Validation:
    - routing tests;
    - target-policy tests;
    - approval/platform-mode tests as needed;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - `openspec validate agenthub-p7-target-registry-permissioned-execution --strict`.

- [ ] 1.6 P7-6 P7 E2E Rehearsal And Freeze Review.
  - Objective: Verify that P7 target registry preserves P6 while adding
    permissioned execution boundaries.
  - Scope:
    - verify the P6 mini CRM vertical slice still works through target registry
      metadata;
    - verify frontend connects to `demo-backend.baseUrl` from the registry;
    - verify backend target remains `apps/demo-api`;
    - verify ordinary app tasks cannot modify `apps/api`;
    - verify platform code remains protected unless platform mode is explicit;
    - document evidence IDs, real adapter usage, fallback usage, caveats, and
      final freeze recommendation.
  - Acceptance criteria:
    - mini CRM flow still produces contract, backend task, frontend task, diff,
      review, preview, and mock deploy evidence;
    - target IDs and target metadata are visible in plans or evidence;
    - demo frontend loads data from registry-resolved demo backend base URL;
    - platform-code mutation is blocked or reported unless platform mode is
      explicit;
    - P4/P5/P6 baselines remain intact.
  - Validation:
    - targeted API/browser rehearsal as practical;
    - `pnpm check`;
    - `pnpm test`;
    - `pnpm demo:api:test`;
    - `git diff --check`;
    - `openspec validate agenthub-p7-target-registry-permissioned-execution --strict`.

## 2. Explicit Non-Goals For P7

- Multi-user IM.
- Matrix, Feishu, WeChat, Slack, or other external IM integration.
- Production deploy.
- Docker sandbox.
- Provider marketplace.
- PR creation.
- Unrestricted repository editing.
- Distributed Manager/Worker scheduler.
- Arbitrary SaaS generation.

## 3. P7 Definition Of Done

- Target registry is the source of truth for demo frontend, demo backend, and
  AgentHub platform target metadata.
- Planner, instruction builder, context pack, and review logic consume target
  metadata rather than duplicating path and URL constants.
- App contracts reference target IDs and backend base URLs through registry
  resolution.
- Ordinary app backend tasks cannot modify `apps/api`.
- Platform maintenance requires explicit platform mode and approval.
- P6 mini CRM vertical slice still works through the target registry.
- Unsupported target operations fail honestly.
- Real Claude/Codex success is documented only when actually run.
- P4/P5/P6 baselines remain intact.
