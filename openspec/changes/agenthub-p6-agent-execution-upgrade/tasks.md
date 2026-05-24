## 1. P6 Agent Execution Capability Upgrade

- [x] 1.1 P6-1 Message Routing, Direct Agent Assignment, and Orchestrator Auto-Run v1.
  - Objective: Route normal unmentioned messages to Orchestrator / Manager by
    default while making `@frontend`, `@backend`, `@qa`, and `@review`
    explicit assignment shortcuts and auto-starting Orchestrator-created safe
    demo-target tasks.
  - Scope:
    - implement routing priority: explicit mentions first, otherwise
      Orchestrator / Manager;
    - route `@orchestrator` and unmentioned messages to Orchestrator / Manager;
    - extend explicit role mentions to create direct role tasks for supported
      bounded requests;
    - auto-start Orchestrator-created safe demo-target coding tasks through the
      existing TaskRun path;
    - pass selected artifact context to Orchestrator by default when no explicit
      role mention is present;
    - preserve the user's original request on the task;
    - assign tasks to the correct existing role or review role representation;
    - keep tasks startable through the existing TaskRun path;
    - reject or clarify unsupported broad requests honestly;
    - preserve existing `@orchestrator` login-page and P5 planner behavior.
  - Acceptance criteria:
    - messages without explicit role mention route to Orchestrator / Manager;
    - Orchestrator can answer, create tasks, generate a contract/task graph, ask
      clarification, or reject unsupported requests honestly;
    - Orchestrator-created safe demo-target frontend tasks auto-start;
    - direct `@frontend` requests can create executable frontend tasks;
    - direct `@backend` requests can create executable backend tasks targeting
      only safe demo backend scope once available or clearly staged for it;
    - direct `@qa` and `@review` requests create read-only review/QA tasks;
    - original user request is stored and visible;
    - no adapter receives unrestricted workspace access.
  - Validation:
    - backend mention-routing tests;
    - frontend task rendering tests if UI copy changes;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - `openspec validate agenthub-p6-agent-execution-upgrade --strict`.

- [x] 1.2 P6-2 Session Context Pack.
  - Objective: Give agent runs structured session context for multi-turn
    iteration.
  - Scope:
    - build a context pack service from current-session records only;
    - include recent messages, execution ledger, selected artifact, latest diff
      metadata, changed files, preview/deploy status, current goal, and app
      contract when present;
    - pass selected artifact context to Orchestrator for default-routed
      messages;
    - include context pack metadata in adapter run requests;
    - validate selected artifact references against the current session;
    - protect against cross-session context leakage.
  - Acceptance criteria:
    - follow-up tasks receive relevant prior context;
    - selected artifact context is represented when available;
    - context pack excludes other sessions;
    - existing P4/P5 task execution still works.
  - Validation:
    - backend context-pack unit tests;
    - task-run request tests;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - `openspec validate agenthub-p6-agent-execution-upgrade --strict`.

- [x] 1.3 P6-3 Role-based Agent Instruction Builder.
  - Objective: Generate meaningful, role-specific instructions for frontend,
    backend, QA/review, and manager tasks.
  - Scope:
    - introduce an instruction builder boundary;
    - generate frontend instructions scoped to `apps/demo`;
    - generate backend instructions scoped to the demo backend target;
    - generate QA/review instructions from diff, contract, risk, and evidence;
    - generate manager instructions for contract/task graph planning;
    - keep protected-path and no-install guardrails;
    - stop reducing every coding request to login-page-only instructions.
  - Acceptance criteria:
    - frontend/backend/review/manager instruction tests cover role differences;
    - original user request and context pack are present in generated
      instructions;
    - backend instructions do not target AgentHub platform backend by default;
    - unsupported requests remain honest.
  - Validation:
    - instruction builder unit tests;
    - adapter request construction tests;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - `openspec validate agenthub-p6-agent-execution-upgrade --strict`.

- [x] 1.4 P6-4 Demo Backend Target Scaffold.
  - Objective: Add or finalize a safe backend target such as `apps/demo-api`
    for Backend Agent execution.
  - Scope:
    - add a minimal local demo backend target with setup/check/test commands
      consistent with repo tooling;
    - update workspace/guardrail metadata so backend tasks target the demo
      backend, not `apps/api`;
    - include simple local endpoints suitable for todo, notes, or contacts;
    - ensure diff collection includes demo backend files and excludes protected
      paths;
    - document how preview/frontend can call the demo backend in local mode.
  - Acceptance criteria:
    - `@backend` tasks have a safe target directory;
    - demo backend checks/tests are available;
    - AgentHub platform backend remains protected by default;
    - fallback-based P4/P5 demo remains intact.
  - Validation:
    - demo backend tests/checks as added;
    - backend guardrail tests;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - `openspec validate agenthub-p6-agent-execution-upgrade --strict`.

- [x] 1.5 P6-5 Contract-first Orchestrator.
  - Objective: Create a structured app contract before bounded full-stack
    implementation tasks.
  - Scope:
    - define app contract schema for bounded mini apps;
    - support one or more mini app families such as todo, notes, or mini CRM
      contacts;
    - generate backend and frontend tasks that reference the same contract;
    - include acceptance criteria and target directories in the contract;
    - keep deterministic fallback or clarification behavior for unsupported
      requests;
    - keep same-session write tasks serial.
  - Acceptance criteria:
    - orchestrator can create a valid contract and task graph for a supported
      mini app request;
    - backend and frontend tasks reference the same contract ID/data;
    - unsupported arbitrary app requests do not claim support;
    - existing P5 planner paths still work.
  - Validation:
    - contract schema tests;
    - planner/task graph tests;
    - unsupported request tests;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - `openspec validate agenthub-p6-agent-execution-upgrade --strict`.

- [x] 1.6 P6-6 Mini App Generation Vertical Slice.
  - Objective: Verify a bounded full-stack mini app path using the upgraded
    execution capability.
  - Scope:
    - choose a bounded app such as todo, notes, or mini CRM contacts;
    - run user requirement -> contract -> backend task -> frontend task ->
      QA/review -> diff -> preview -> mock deploy;
    - prefer one documented real Claude/Codex execution only when practical;
    - use fallback or scripted behavior only when honestly labeled;
    - capture evidence IDs and caveats.
  - Acceptance criteria:
    - mini app path produces a contract, backend task, frontend task, review,
      diff, preview, and mock deploy artifact;
    - adapter types and fallback behavior are documented truthfully;
    - mock deploy remains mock;
    - P4/P5 baseline remains intact.
  - Validation:
    - targeted E2E/API/browser rehearsal as practical;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - `openspec validate agenthub-p6-agent-execution-upgrade --strict`.

- [x] 1.7 P6-7 P6 E2E rehearsal and freeze review.
  - Objective: Verify and freeze P6 as an agent execution capability upgrade.
  - Scope:
    - verify default Orchestrator routing for unmentioned messages;
    - verify direct role assignment for explicit mentions;
    - verify context pack and role-based instruction behavior;
    - verify demo backend target boundaries;
    - verify contract-first mini app flow;
    - verify direct and orchestrated paths preserve diff/review/preview/mock
      deploy;
    - document evidence IDs, real adapter usage, fallback usage, limitations,
      and remaining non-goals.
  - Acceptance criteria:
    - P6 can be described as practical agent execution upgrade, not generic SaaS
      generation;
    - unsupported requests fail honestly or request clarification;
    - same-session write tasks remain serial;
    - P4/P5 baseline and adapters remain intact;
    - final caveats and recommended freeze tag are documented.
  - Validation:
    - P6 rehearsal notes;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - `openspec validate agenthub-p6-agent-execution-upgrade --strict`.

## 2. Explicit Non-Goals For P6

- Arbitrary SaaS generation.
- Unrestricted editing of AgentHub platform code.
- Production deploy.
- Multi-user IM.
- Matrix, Feishu, WeChat, Slack, or other external IM integration.
- Provider marketplace.
- Docker sandbox.
- PR creation.
- Enterprise approval workflow.
- Payment, auth, or multi-tenant production systems.

## 3. P6 Definition Of Done

- Direct mentions create executable tasks for supported role requests.
- Messages without explicit role mentions route to Orchestrator / Manager by
  default.
- Explicit role mentions have highest priority and act as advanced assignment
  shortcuts.
- Orchestrator-created safe demo-target tasks can auto-start through the
  existing TaskRun path.
- Direct tasks preserve original user requests.
- Agent instructions include session context and selected artifact context when
  available.
- Frontend, backend, QA/review, and manager instructions are role-specific.
- Backend execution targets a safe demo backend, not the AgentHub platform API.
- Orchestrator can generate a shared contract for one bounded full-stack mini
  app family.
- The mini app vertical slice has diff, review, preview, and mock deploy
  evidence.
- Real Claude/Codex success is documented only when actually run.
- Unsupported requests fail honestly or create clarification tasks.
- P4/P5 baseline and existing adapters remain intact.
