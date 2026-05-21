## 1. P5 Implementation Tasks

- [x] 1.1 P5-1 Agent Registry and IM Contact UI.
  - Objective: Make built-in agents visible as IM-style contacts and introduce
    direct-chat/group-workflow visual modes without adding real multi-user
    accounts.
  - Scope:
    - expose or enrich enabled agent metadata for contact display;
    - show agents with avatar, name, role, adapterType, capability tags, and
      status;
    - represent Manager Agent, Coding Agent, Review Agent, and system service
      contacts where applicable;
    - add direct-chat and group-workflow visual modes;
    - preserve current `@orchestrator`, `@frontend`, `@backend`, and `@qa`
      mention behavior.
  - Acceptance criteria:
    - contact list renders built-in agents from backend data or a documented
      backend-backed registry shape;
    - direct-chat and group-workflow modes are visual/local only and do not
      claim multi-user support;
    - `CodexAdapter`, `ClaudeCodeAdapter`, and `ScriptedMockAdapter` remain
      visible or preserved where relevant;
    - final demo baseline still works.
  - Validation:
    - targeted frontend/backend tests as changed;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`.

- [x] 1.2 P5-2 Shared Context and Execution Ledger.
  - Objective: Persist and display a compact execution ledger for the current
    session.
  - Scope:
    - persist current goal, active agents, latest plan, latest task, latest run,
      latest diff, latest review, latest preview, latest mock deploy, changed
      files, and review summary;
    - expose ledger read API;
    - update ledger after relevant message/task/run/artifact events;
    - keep ledger inspectable and session-scoped;
    - avoid full vector database memory.
  - Acceptance criteria:
    - ledger can be reconstructed or read after reload;
    - ledger references real messages, tasks, runs, and artifacts;
    - no cross-session context leakage;
    - fallback path remains intact.
  - Validation:
    - backend tests for ledger updates;
    - frontend tests if ledger UI is added in this task;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`.

- [ ] 1.3 P5-3 Review Agent Workflow.
  - Objective: Add a non-blocking Review Agent workflow after coding diffs.
  - Scope:
    - after a coding diff is produced, create or run a Review Agent task;
    - generate a review artifact with `passed`, `warning`, or `failed` status;
    - include summary and findings;
    - link review artifact to the reviewed diff artifact;
    - keep v1 non-blocking by default;
    - allow review to be read-only.
  - Acceptance criteria:
    - review artifact is persisted and visible;
    - review status is clearly advisory/non-blocking;
    - diff, preview, and mock deploy flow still works;
    - real Claude/Codex review execution is documented if used;
    - scripted/mock review behavior is labeled if used.
  - Validation:
    - backend review workflow tests;
    - frontend review card tests;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`.

- [ ] 1.4 P5-4 Multi-Agent Execution Trace UI.
  - Objective: Show Manager, Coding Agent, Review Agent, QA/Preview/Deploy
    services as a visible execution trace.
  - Scope:
    - derive trace from messages, tasks, task runs, events, and artifacts;
    - show Manager planning, coding execution, diff collection, review, preview,
      and mock deploy steps;
    - link trace nodes to artifact cards and task/run details;
    - show active, completed, warning, failed, and skipped states.
  - Acceptance criteria:
    - users can follow the whole workflow from requirement to mock deploy;
    - system service steps are labeled as services, not autonomous agents;
    - trace survives reload using persisted data;
    - existing task timeline remains usable.
  - Validation:
    - frontend component tests;
    - backend/API tests if trace endpoint is added;
    - browser smoke rehearsal;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`.

- [ ] 1.5 P5-5 Dynamic Manager Planner v1.
  - Objective: Add a bounded dynamic Manager planner for frontend change
    intents while preserving deterministic fallback planning.
  - Scope:
    - introduce Manager planner service boundary;
    - classify bounded frontend change intents;
    - output structured task graph;
    - validate task graph schema, role set, target files, dependency depth, and
      task count;
    - fall back to deterministic planner on unsupported intent or invalid model
      output;
    - persist planner rationale and graph metadata.
  - Acceptance criteria:
    - bounded dynamic planner can create a valid frontend-oriented task graph;
    - deterministic demo planner still handles the known login-page path;
    - unsupported broad requests fail safely or fall back without claiming
      arbitrary editing support;
    - same-session write tasks remain serial.
  - Validation:
    - planner unit tests;
    - backend integration tests for fallback behavior;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`.

- [ ] 1.6 P5-6 Artifact Message Cards v2.
  - Objective: Render Diff, Preview, Review, and Mock Deploy as inline message
    cards and support artifact selection/reference for follow-up interaction.
  - Scope:
    - add inline cards for Diff, Preview, Review, and Mock Deploy;
    - preserve the right-side artifact panel as detailed inspector;
    - support selecting or referencing artifacts in follow-up messages;
    - keep references session-scoped;
    - avoid implying mock deploy is production deploy.
  - Acceptance criteria:
    - artifact cards render in the chat stream;
    - selecting/referencing an artifact creates inspectable follow-up context;
    - referenced artifacts are validated against the current session;
    - follow-up interaction still produces real diff/preview evidence when
      execution is run.
  - Validation:
    - frontend card/reference tests;
    - backend reference validation tests if backend metadata is added;
    - browser smoke rehearsal;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`.

- [ ] 1.7 P5-7 P5 E2E rehearsal and freeze review.
  - Objective: Verify and freeze P5 as a local single-user IM-style
    multi-agent coding workspace v1.
  - Scope:
    - rehearse user requirement -> Manager planning -> coding agent execution
      -> review artifact -> artifact cards -> preview -> mock deploy ->
      follow-up interaction;
    - verify real or fallback coding execution with evidence;
    - verify review artifact behavior and non-blocking semantics;
    - verify reload/recovery behavior;
    - record caveats and validation results;
    - ensure no P5 non-goals were accidentally implemented.
  - Acceptance criteria:
    - P5 loop has evidence IDs for plan, tasks, runs, diff, review, preview,
      deployment, and follow-up artifacts where applicable;
    - mock deploy remains labeled as mock;
    - real Claude/Codex execution is documented only if actually run;
    - final demo baseline remains intact;
    - P5 is not described as full multi-user IM.
  - Validation:
    - browser E2E rehearsal notes;
    - `pnpm check`;
    - `pnpm test`;
    - `git diff --check`;
    - `openspec validate agenthub-p5-platform-evolution --strict`.

## 2. Explicit Non-Goals For P5

- Full multi-user IM platform.
- Real Feishu, WeChat, Slack, Matrix, or other external IM integration.
- Desktop or mobile apps.
- Provider marketplace.
- Production deploy.
- Docker sandbox.
- PR creation.
- Unrestricted arbitrary code editing.
- Full vector database memory.
- Distributed worker cluster.
- Enterprise approval workflow.
- Real-time multi-user sync and conflict resolution.
- User-created agents as an immediate P5 runtime feature.

## 3. P5 Definition Of Done

- AgentHub can be explained as a local single-user IM-style multi-agent coding
  workspace v1.
- Agent contacts and workflow modes are visible.
- Manager Agent planning is bounded and has deterministic fallback.
- Coding execution still uses preserved adapters and worktree isolation.
- Review Agent produces non-blocking review artifacts.
- Diff, Preview, Review, and Mock Deploy cards are visible and referenceable.
- Follow-up interaction can reference prior artifacts.
- Same-session write tasks remain serial.
- Final demo baseline still passes.
- Future long-term platform items remain deferred and plainly documented.
