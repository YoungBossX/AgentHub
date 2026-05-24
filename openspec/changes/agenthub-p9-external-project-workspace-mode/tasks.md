## 1. P9 External Project Workspace Mode

- [x] 1.1 P9-1 External Workspace Registration.
  - Objective: Let a local external project root become a first-class AgentHub
    workspace target.
  - Scope:
    - add persisted registration for external project targets;
    - store `targetId`, `name`, `rootPath`, `projectType`, `allowedPaths`,
      `deniedPaths`, `devCommand`, `testCommand`, `checkCommand`,
      `buildCommand`, `previewCommand`, `packageManager`, and
      `detectedFramework`;
    - reject unsafe roots such as home directory, filesystem root, system
      directories, and unbounded parent directories;
    - require explicit allowed paths or analyzer-inferred allowed paths before
      execution;
    - expose read/list APIs for registered external targets.
  - Acceptance criteria:
    - a local sample project can be registered as an external target;
    - denied paths include `.env`, `.env.*`, `secrets`, `.git`,
      `node_modules`, `.venv`, and generated dependency/build directories;
    - registration does not grant access to arbitrary filesystem paths;
    - built-in `demo-frontend`, `demo-backend`, and `agenthub-platform` targets
      remain available.
  - Validation:
    - registration service/API tests;
    - unsafe root rejection tests;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - `openspec validate agenthub-p9-external-project-workspace-mode --strict`.

- [ ] 1.2 P9-2 Project Analyzer.
  - Objective: Infer external project shape and safe defaults without running
    arbitrary commands.
  - Scope:
    - inspect `package.json`, `vite.config.*`, `next.config.*`,
      `pyproject.toml`, `requirements.txt`, lockfiles, and source/test layout;
    - infer project types: `vite-react`, `nextjs`, `fastapi`, `node-api`,
      `python-package`, or `unknown`;
    - infer package manager, framework, allowed paths, denied paths, and safe
      command candidates;
    - produce `needs_confirmation` when inference is uncertain;
    - never install dependencies during analysis.
  - Acceptance criteria:
    - analyzer detects representative Vite React, Next.js, FastAPI, Node API,
      and Python package fixtures;
    - unknown projects require confirmation/config before execution;
    - analyzer output includes warnings and confidence status;
    - analyzer never treats dependency/build output directories as allowed
      write paths.
  - Validation:
    - analyzer fixture tests;
    - uncertain inference tests;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - `openspec validate agenthub-p9-external-project-workspace-mode --strict`.

- [ ] 1.3 P9-3 External Target Registry Integration.
  - Objective: Make external targets available through the same Target Registry
    model as built-in targets.
  - Scope:
    - merge built-in and persisted external targets in registry reads;
    - map external metadata into Target Registry fields;
    - update planner, instruction builder, review, and scheduler lookups to
      accept external target IDs;
    - ensure P8 target locks apply to external target IDs;
    - keep `agenthub-platform` protections unchanged.
  - Acceptance criteria:
    - registered external targets can be resolved by target ID;
    - external target metadata is visible to context packs and instructions;
    - same external target write tasks are serialized by P8 locks;
    - built-in demo target behavior remains unchanged.
  - Validation:
    - registry integration tests;
    - scheduler external lock tests;
    - built-in target regression tests;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - `openspec validate agenthub-p9-external-project-workspace-mode --strict`.

- [ ] 1.4 P9-4 External Target Instruction Builder.
  - Objective: Generate meaningful role instructions for registered external
    targets without assuming demo paths.
  - Scope:
    - update frontend/backend/qa/review/manager instruction paths to consume
      external target metadata;
    - preserve original user request;
    - include allowed paths, denied paths, commands, project type, package
      manager, detected framework, selected artifact, latest diff, scheduler
      state, and validation expectations;
    - prepare backend instructions for external backend targets without
      allowing AgentHub platform backend edits;
    - keep built-in demo instructions working.
  - Acceptance criteria:
    - external frontend instructions reference external root/allowed paths and
      do not mention `apps/demo` unless that is the registered target;
    - external backend instructions reference external backend target metadata
      and do not permit `apps/api`;
    - review instructions include command evidence expectations;
    - unsupported external tasks ask for clarification or fail honestly.
  - Validation:
    - instruction builder tests;
    - context pack tests;
    - built-in instruction regression tests;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - `openspec validate agenthub-p9-external-project-workspace-mode --strict`.

- [ ] 1.5 P9-5 External Project Task Execution.
  - Objective: Allow registered external targets to receive executable
    coding/review tasks through existing adapters.
  - Scope:
    - route `@frontend` to the active external frontend target when selected;
    - route `@backend` to the active external backend target when selected;
    - route `@qa` / `@review` to read-oriented external review tasks;
    - let Orchestrator create external target tasks for selected workspaces;
    - preserve `CodexAdapter`, `ClaudeCodeAdapter`, and `ScriptedMockAdapter`
      behavior;
    - keep adapter execution scoped to registered external target worktrees or
      roots and explicit allowed paths.
  - Acceptance criteria:
    - direct mention tasks can target a registered external project;
    - Orchestrator can create at least one bounded external target task;
    - TaskRun instructions preserve the user's original request;
    - unsupported or ambiguous external requests do not silently execute.
  - Validation:
    - routing tests;
    - TaskRun request tests;
    - unsupported request tests;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - `openspec validate agenthub-p9-external-project-workspace-mode --strict`.

- [ ] 1.6 P9-6 External Evidence Pipeline.
  - Objective: Record external project evidence according to target
    capabilities.
  - Scope:
    - collect git diff for external target work;
    - add evidence artifacts for check, test, and build command output;
    - support preview URL / health only when preview is configured;
    - do not require every external project to support preview;
    - record failed commands honestly;
    - surface external evidence in existing artifact/message card patterns.
  - Acceptance criteria:
    - external diffs are collected and scoped to allowed paths;
    - check/test/build output can be stored as evidence;
    - failed command evidence is visible as failed/warning evidence;
    - targets without preview remain valid if diff and command evidence exist.
  - Validation:
    - evidence artifact tests;
    - failed command evidence tests;
    - no-preview target tests;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - `openspec validate agenthub-p9-external-project-workspace-mode --strict`.

- [ ] 1.7 P9-7 External Project Review.
  - Objective: Review external diffs and evidence against registered target
    policy.
  - Scope:
    - detect edits outside allowed paths;
    - detect edits to denied paths including `.env`, `.env.*`, `secrets`,
      `.git`, `node_modules`, `.venv`, generated dependency/build directories,
      and unsafe host paths;
    - include check/test/build evidence in review summaries;
    - report failed command evidence honestly;
    - do not fake Claude/Codex success.
  - Acceptance criteria:
    - allowed path violations fail or warn review;
    - denied path edits fail review;
    - failed tests/checks/builds are visible in review status and findings;
    - review remains compatible with built-in P6/P7/P8 demo targets.
  - Validation:
    - external review tests;
    - denied path tests;
    - failed command evidence review tests;
    - built-in review regression tests;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - `openspec validate agenthub-p9-external-project-workspace-mode --strict`.

- [ ] 1.8 P9-8 External Project E2E Rehearsal And Freeze Review.
  - Objective: Verify external workspace mode without regressing P6/P7/P8.
  - Scope:
    - create or use a local sample external project outside built-in demo
      targets;
    - register it as an external workspace target;
    - run one bounded real-agent task if practical;
    - if real Claude/Codex is blocked by auth/quota/runtime, record the exact
      error and use controlled fallback only for plumbing evidence;
    - verify diff, review, test/check/build evidence, and preview evidence
      when configured;
    - verify target locks apply to external targets;
    - verify built-in demo baseline remains intact.
  - Acceptance criteria:
    - external project registration and analysis evidence is recorded;
    - at least one external task/run/evidence path is rehearsed;
    - real Claude/Codex success is claimed only if actually run;
    - P6/P7/P8 built-in mini CRM / registry / scheduler baselines remain
      intact;
    - remaining caveats are documented.
  - Validation:
    - targeted API/browser rehearsal as practical;
    - `pnpm check`;
    - `pnpm test`;
    - `pnpm demo:api:test`;
    - `git diff --check`;
    - `openspec validate agenthub-p9-external-project-workspace-mode --strict`.

## 2. Explicit Non-Goals For P9

- Cloud repo import.
- Multi-user project sharing.
- Production deploy.
- Docker sandbox.
- Provider marketplace.
- PR creation.
- Arbitrary unrestricted filesystem access.
- Enterprise RBAC.
- Full multi-tenant workspace system.
- Matrix, Feishu, WeChat, Slack, or other external IM integrations.
- Payment/auth/multi-tenant app generation.

## 3. P9 Definition Of Done

- A local external project can be registered as a first-class AgentHub target.
- The project analyzer detects common project types and requires confirmation
  when uncertain.
- External targets are consumed through the existing Target Registry model.
- Planner, instruction builder, review, and scheduler can use external target
  metadata.
- `CodexAdapter` and `ClaudeCodeAdapter` can receive meaningful external target
  coding instructions bounded to allowed paths.
- External evidence includes diff plus check/test/build and preview when
  configured.
- External review enforces allowed/denied paths and command evidence honesty.
- Target locks apply to external targets.
- Built-in P6/P7/P8 demo targets continue working.
- No unverified Claude/Codex success is claimed.
