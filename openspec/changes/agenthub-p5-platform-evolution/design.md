## Context

AgentHub final demo hardening is frozen. The current system is a local
single-user Agent Coding Workspace / strong demo MVP with this verified loop:

```text
requirement -> plan -> agent execution -> diff -> preview -> mock deploy
```

Current baseline:

- local single-user workspace;
- SQLite persistence;
- multiple sessions;
- IM-style chat shell;
- mention routing for `@orchestrator`, `@frontend`, `@backend`, and `@qa`;
- simple deterministic orchestrator planner;
- one git worktree per Session;
- same-session worktree reuse across TaskRuns;
- `CodexAdapter`, `ClaudeCodeAdapter`, and `ScriptedMockAdapter`;
- real file mutation, Git diff artifacts, Vite React preview, and mock deploy;
- forced-failure fallback path through `ScriptedMockAdapter`;
- same-session follow-up text-change path.

P5 should evolve this baseline into a local single-user IM-style multi-agent
coding workspace v1. It should feel less like a one-off demo and more like a
workspace where a user talks to agents, sees agent contacts, follows a
Manager-led workflow, reviews artifacts inline, and continues from prior
evidence.

P5 must not become the long-term platform all at once. Multi-end, multi-user,
external IM integration, user-created agents, provider marketplace, real deploy,
Docker sandbox, and enterprise approval are future roadmap items, not immediate
P5 implementation.

## Product Shape

P5 target path:

```text
user requirement
-> Manager Agent planning
-> coding agent execution
-> review agent
-> artifact cards
-> preview
-> mock deploy
-> follow-up interaction
```

Product concepts:

- **Agent contacts:** visible built-in agents with avatar, name, role,
  adapterType, capability tags, and status.
- **Direct chat mode:** user can focus on one agent or service role visually.
- **Group workflow mode:** user can watch Manager, Coding Agent, Review Agent,
  QA/Preview/Deploy services participate in one workflow.
- **Manager Agent:** PM/PMO-style coordinator that plans, assigns, tracks, and
  summarizes the workflow.
- **Coding Agent:** current code adapters such as Codex and Claude Code execute
  bounded write tasks.
- **Review Agent:** read-only/non-blocking v1 reviewer that produces review
  artifacts after coding diffs.
- **Artifact cards:** inline cards for Diff, Preview, Review, and Mock Deploy,
  each selectable for follow-up interaction.

## Design Constraints

- Preserve the final demo baseline.
- Preserve `CodexAdapter`, `ClaudeCodeAdapter`, and `ScriptedMockAdapter`.
- Do not break diff, preview, or mock deploy flow.
- Do not fake real agent success.
- Document any real Claude/Codex execution.
- Same-session write tasks must remain serial to avoid worktree conflicts.
- Review tasks may be read-only and non-blocking in v1.
- Dynamic planning must be bounded and must preserve deterministic fallback
  planning.
- P5 remains local and single-user.

## P5-1 Agent Registry And IM Contact UI

### Objective

Make agents visible as IM-style contacts so AgentHub feels like a multi-agent
workspace instead of a hidden task runner.

### Required Backend Changes

- Expose an agent registry endpoint or enrich existing workspace/session
  responses with enabled agents.
- Include display metadata: avatar key, name, role, adapterType, capability
  tags, status, and short description.
- Map existing seeded roles to product roles:
  - Orchestrator or Manager Agent;
  - Frontend/Backend Coding Agent;
  - QA or Review Agent;
  - Preview/Deploy service roles if represented as system contacts.
- Keep current adapter types unchanged.

### Required Frontend Changes

- Add an agent contact list in the workspace shell.
- Show avatar, name, role, adapterType, capability tags, and status.
- Add visual direct-chat and group-workflow modes.
- Direct-chat mode may be visual/contextual only in P5; it does not need real
  separate one-to-one persistence semantics.
- Group-workflow mode should make Manager, Coding Agent, Review Agent, and
  artifact services visually present.

### Data Model Impact

- Prefer extending existing `Agent` metadata first.
- If needed, add display fields such as `avatar_key`, `capability_tags_json`,
  `status`, and `description`.
- Do not add multi-user account or external contact tables in P5.

### Security Risks

- Contact UI can imply capabilities that are not actually available.
- Agent status can mislead users if not derived from real availability.
- Exposing adapter details may reveal local environment assumptions.

### Why Deferred From Final-Demo-Hardening

Final-demo-hardening freezes evidence and docs. Agent contact UI changes product
surface and backend API shape, so it belongs in P5, not the frozen demo.

## P5-2 Shared Context And Execution Ledger

### Objective

Persist a compact, inspectable session ledger that captures the current goal,
active agents, latest plan/task/run/diff/review/preview/deploy, changed files,
and review summary.

### Required Backend Changes

- Add a ledger service that updates after message creation, planning, task run
  completion, diff collection, review creation, preview creation, and mock
  deployment creation.
- Provide a read endpoint for the current session execution ledger.
- Include artifact IDs and changed files so follow-up interactions can refer to
  concrete evidence.
- Keep ledger writes deterministic and derivable from existing records where
  possible.

### Required Frontend Changes

- Show the current goal and active agents.
- Show latest plan, active task, latest run state, changed files, review status,
  preview status, and deploy status.
- Let users inspect the ledger without hiding the existing task timeline.
- Use ledger state to power follow-up context chips.

### Data Model Impact

- Add a `SessionExecutionLedger` record or a normalized set of ledger snapshots.
- Store references to latest message, plan, task, task run, diff, review,
  preview, and deployment artifacts.
- Store changed files and review summary in structured JSON.
- Avoid full vector memory or hidden cross-session memory in P5.

### Security Risks

- Ledger may preserve sensitive file names or summaries.
- Stale ledger fields can cause follow-up tasks to target the wrong artifact.
- Cross-session ledger leakage would be severe if multi-user later arrives.

### Why Deferred From Final-Demo-Hardening

The final demo can already recover messages, tasks, and artifacts. A ledger is a
new product abstraction for P5 follow-up and traceability, not a freeze task.

## P5-3 Review Agent Workflow

### Objective

After a coding diff is produced, run a Review Agent task and generate a review
artifact with `passed`, `warning`, or `failed` status. The first version is
non-blocking by default.

### Required Backend Changes

- Add a review task type and review artifact type.
- Trigger a review task after a coding TaskRun has a diff artifact.
- Package diff metadata, changed files, and patch text for read-only review.
- Use `ClaudeCodeAdapter`, `CodexAdapter`, or `ScriptedMockAdapter` according to
  configured review-agent policy, while preserving current coding adapters.
- Store review summary, findings, severity, and status.
- Keep v1 non-blocking unless later policy explicitly enables blocking gates.

### Required Frontend Changes

- Show review task/run in the workflow.
- Render review artifact cards with passed/warning/failed status.
- Show review summary and findings.
- Link review cards to the diff they reviewed.
- Make clear that v1 review is advisory/non-blocking.

### Data Model Impact

- Add `Review` or generalized artifact subtype support.
- Add fields for reviewed diff artifact ID, status, summary, findings JSON,
  reviewer agent ID, and adapter metadata.
- Add run/event links so review is part of the execution trace.

### Security Risks

- Review agent output is not a security boundary.
- False negatives can create misplaced confidence.
- False positives can create unnecessary warnings.
- Review prompts may expose patch content; packaging must stay within session
  worktree and protected-path rules.

### Why Deferred From Final-Demo-Hardening

Final-demo-hardening does not add runtime workflow steps. Review Agent execution
changes the task pipeline and artifact model, so it belongs in P5.

## P5-4 Multi-Agent Execution Trace UI

### Objective

Show Manager, Coding Agent, Review Agent, QA/Preview/Deploy services as a
visible execution trace so users can understand who did what and which evidence
was produced.

### Required Backend Changes

- Ensure task run events include enough role/agent/artifact metadata for trace
  rendering.
- Expose trace-friendly data shape for a session or task graph.
- Include system service steps for diff collection, preview, and mock deploy.
- Preserve existing TaskRunEvent-backed SSE behavior.

### Required Frontend Changes

- Add a multi-agent trace component.
- Display Manager planning, coding execution, diff collection, review, preview,
  and mock deploy in order.
- Show active, completed, warning, failed, and skipped states.
- Link trace nodes to messages, tasks, runs, and artifact cards.
- Keep the existing timeline usable for small demos.

### Data Model Impact

- Prefer deriving trace from existing `Message`, `Task`, `TaskRun`,
  `TaskRunEvent`, and `Artifact` rows.
- Add explicit trace event metadata only if derivation is insufficient.
- Include review artifacts once P5-3 lands.

### Security Risks

- Trace can overstate agent autonomy if service-generated steps are not labeled.
- Missing events can make a workflow appear cleaner than it was.
- Revealing local paths or internal process details can leak environment data.

### Why Deferred From Final-Demo-Hardening

The final demo already proves the loop. P5 trace UI improves product clarity but
is not needed to freeze the baseline.

## P5-5 Dynamic Manager Planner v1

### Objective

Add a bounded dynamic Manager planner for frontend change intents. It should
output structured task graphs while preserving the deterministic fallback
planner.

### Required Backend Changes

- Introduce a Manager planner service boundary.
- Support structured planner output with schema validation.
- Limit v1 to frontend change intents and same-session follow-up interaction.
- Bound task count, role set, target files, and dependency depth.
- Fall back to the deterministic planner on model failure, invalid output, or
  unsupported intent.
- Persist planner rationale and task graph metadata.

### Required Frontend Changes

- Show Manager-generated plan and task graph.
- Show planner rationale and fallback use when applicable.
- Let user inspect task assignments before starting execution.
- Keep the current fixed demo path visibly stable.

### Data Model Impact

- Add plan graph metadata or a `Plan`/`PlanVersion` structure.
- Store validated structured task graph output.
- Link tasks back to the Manager plan version that created them.
- Preserve current `Task` and `TaskRun` behavior.

### Security Risks

- Prompt injection can expand scope or target protected paths.
- Model output can assign writes to the wrong agent.
- Dynamic planning can create too many tasks.
- Unsupported requests may look accepted unless rejected clearly.

### Why Deferred From Final-Demo-Hardening

Dynamic planning changes core runtime behavior. P5 can introduce it only as a
bounded v1 with deterministic fallback, not as a final-demo-hardening patch.

## P5-6 Artifact Message Cards v2

### Objective

Render Diff, Preview, Review, and Mock Deploy as inline message cards and allow
users to select or reference artifacts for follow-up interaction.

### Required Backend Changes

- Add artifact reference support in messages or follow-up requests.
- Provide artifact summary payloads suitable for inline cards.
- Track selected/referenced artifact IDs for follow-up tasks.
- Ensure artifact references are session-scoped.

### Required Frontend Changes

- Add inline artifact cards in the chat stream.
- Support card types:
  - Diff;
  - Preview;
  - Review;
  - Mock Deploy.
- Let users select cards or insert references into follow-up messages.
- Keep the right-side artifact panel as a detailed inspector.

### Data Model Impact

- Add message-to-artifact reference records or structured message metadata.
- Store selected artifact IDs for follow-up context.
- Reuse existing Artifact IDs and artifact subtype records.

### Security Risks

- Artifact references could cross sessions if not scoped.
- Follow-up tasks might act on stale or wrong artifacts.
- Inline deploy cards must not imply production deployment.

### Why Deferred From Final-Demo-Hardening

Final-demo-hardening documents and freezes the existing artifact panel. Inline
artifact cards and follow-up references are a product evolution for P5.

## P5-7 E2E Rehearsal And Freeze Review

### Objective

Verify and freeze the P5 local single-user IM-style multi-agent coding workspace
v1.

### Required Backend Changes

- No new backend feature work in this task; only evidence collection and final
  fixes discovered during P5 implementation.

### Required Frontend Changes

- No new frontend feature work in this task; only evidence collection and final
  fixes discovered during P5 implementation.

### Data Model Impact

- No new model scope in this task.

### Security Risks

- Overclaiming platform features remains the main risk. Evidence must label
  what is verified, mock-backed, local-only, and deferred.

### Why Deferred From Final-Demo-Hardening

P5 freeze comes after P5 runtime tasks. It should not replace the already frozen
final demo baseline.

## Long-Term Roadmap Items Not In P5

These remain long-term roadmap items:

- full multi-user IM platform;
- external Feishu, WeChat, Slack, or Matrix integration;
- desktop/mobile apps;
- user-created agents;
- provider marketplace;
- production deploy;
- Docker sandbox;
- PR creation;
- unrestricted arbitrary code editing;
- full vector database memory;
- distributed worker cluster;
- enterprise approval workflow;
- real-time multi-user sync and conflict resolution.

## Validation

P5 proposal validation:

```bash
git diff --check
openspec validate agenthub-p5-platform-evolution --strict
```
