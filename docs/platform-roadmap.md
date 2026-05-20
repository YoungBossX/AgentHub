# AgentHub Long-Term Platform Roadmap

## 1. Current Baseline

AgentHub is currently a local single-user Agent Coding Workspace / strong demo
MVP. It uses an IM-style command-center interface, but it is not yet a full
multi-user Feishu, WeChat, or Slack-style collaboration platform.

The verified final-demo loop is:

```text
requirement -> orchestrator plan -> agent execution -> real git diff -> real preview -> mock deploy card
```

Current verified capabilities:

- single local user and local demo workspace;
- multiple sessions;
- chat-style message entry;
- mention routing for `@orchestrator`, `@frontend`, `@backend`, and `@qa`;
- simple orchestrator planning for the fixed demo request;
- task cards, task dependencies, run history, retry, interrupt, and fallback
  controls;
- `CodexAdapter`, `ClaudeCodeAdapter`, and `ScriptedMockAdapter`;
- one git worktree per Session;
- real file mutation inside the assigned worktree;
- persisted `TaskRunEvent` records and SSE recovery;
- Git diff artifact collection;
- Vite React preview for `apps/demo`;
- mock deployment cards.

The current evidence supports calling AgentHub a strong coding-agent demo MVP.
It does not support claiming full IM collaboration, multi-user presence, a
provider marketplace, real production deploy, Docker sandboxing, broad
arbitrary natural-language editing, or enterprise workflow automation.

## 2. Long-Term Target

The long-term target is an IM-style multi-agent collaboration platform for
software work.

In that target state, a user should be able to describe a product or engineering
goal in a familiar chat environment, involve humans and agents through
mentions, let an orchestrator decompose the work, let specialized agents execute
or review subtasks, inspect durable engineering evidence, preview results, and
ship through approved deployment providers.

Target product shape:

- IM-style conversation as the primary interaction model;
- multi-user workspaces and shared sessions;
- dynamic orchestrator planning instead of fixed demo-specific planning;
- manager/worker scheduling for parallel and dependent tasks;
- shared project context and memory;
- multiple specialist agents, including coding, QA, security, design, docs, and
  release roles;
- plugin and skill ecosystem for agent capabilities;
- real deploy providers behind explicit approval and audit controls;
- strong isolation, permissions, and traceability for all agent actions.

This roadmap is strategic. These phases are not current three-week tasks and
are not part of `agenthub-final-demo-hardening`. Each phase should become its
own focused OpenSpec change before implementation.

## 3. Roadmap Principles

- Preserve the current demo loop while evolving the platform.
- Avoid replacing the final-demo-hardening scope with broad platform work.
- Add runtime capability only behind explicit specs, tests, and safety gates.
- Treat real agent execution as high-risk infrastructure, not ordinary UI
  plumbing.
- Keep mock and fallback paths available until real providers are reliable.
- Separate platform identity from demo evidence: do not claim a capability until
  it has been verified.

## 4. Phase 1: Dynamic Orchestrator Planning

### Objective

Replace the current fixed login-page planner with a general orchestrator that
can classify a user request, choose relevant agents, generate a task graph, and
revise the plan after new evidence arrives.

### Required Backend Changes

- Introduce a planner service boundary separate from request parsing.
- Support structured planning outputs with task graph validation.
- Add plan versioning so revised plans do not erase prior plans.
- Add planner evaluation and deterministic fallback behavior.
- Extend task creation so the planner can create frontend, backend, QA, docs,
  security, and release tasks when those roles exist.
- Add server-side constraints for maximum task count, maximum dependency depth,
  and allowed target paths.

### Required Frontend Changes

- Show generated plan versions and plan diffs.
- Let the user approve, reject, or ask for revision before execution.
- Visualize dependencies beyond the current simple three-task list.
- Show why each task was assigned to a role.
- Add clear empty, invalid-plan, and plan-revision states.

### Data Model Impact

- Add `Plan` or `TaskGraph` records instead of storing only task rows.
- Add `PlanVersion` metadata.
- Add task graph edges as first-class records or normalized JSON.
- Add planner confidence, rationale, and validation status.
- Preserve links from `Message` to generated plan and generated tasks.

### Security Risks

- Prompt injection could cause unsafe tasks or path expansion.
- A dynamic planner could create too many tasks or bypass demo boundaries.
- Planner output could assign a task to an agent with broader privileges than
  intended.
- Plan revisions could obscure the original user request or approval history.

### Why Deferred From Final Demo Hardening

Final demo hardening is about preserving and explaining a verified local loop.
Dynamic planning would change core runtime behavior, broaden the task surface,
and require a separate safety model. It is not a current three-week task.

## 5. Phase 2: Shared Context And Memory

### Objective

Give agents durable context about the workspace, sessions, decisions, artifacts,
prior task outcomes, and project conventions so later tasks can build on earlier
work without relying only on the current chat message.

### Required Backend Changes

- Add context indexing for messages, tasks, diffs, previews, and deployments.
- Add retrieval APIs for relevant session and workspace context.
- Add memory write policies that separate durable facts from transient notes.
- Add memory compaction and retention rules.
- Add context packaging per adapter so each agent receives only the context it
  is allowed to see.
- Add invalidation when code, docs, or project state changes.

### Required Frontend Changes

- Show what context was used by a run.
- Let users pin, unpin, or correct important memory.
- Add workspace memory and session memory panels.
- Show when a task is using stale context.
- Provide a way to inspect or delete memory entries.

### Data Model Impact

- Add `MemoryEntry`, `ContextSource`, or `KnowledgeItem` records.
- Add embeddings or search index metadata if semantic retrieval is adopted.
- Add source links back to messages, artifacts, files, and task runs.
- Add retention, visibility, and trust-level fields.
- Add audit records for memory creation, update, and deletion.

### Security Risks

- Sensitive data could be retained longer than intended.
- Agents could retrieve context from unrelated sessions or users.
- Poisoned memory could bias future plans or code edits.
- Semantic retrieval may surface confidential or irrelevant information.

### Why Deferred From Final Demo Hardening

The current demo works with explicit session state and artifacts. Shared memory
requires new storage, retrieval, privacy, retention, and audit design. It is not
needed to freeze the final local demo and is not a current three-week task.

## 6. Phase 3: Manager/Worker Scheduling

### Objective

Introduce a manager/worker execution model that can run independent tasks in
parallel, sequence dependent tasks, pause for approvals, retry failures, and
allocate work across available agents.

### Required Backend Changes

- Add a scheduler service that owns task queueing and dispatch.
- Model runnable, blocked, waiting approval, running, failed, and completed
  states consistently across task graphs.
- Add worker leases and heartbeat handling.
- Add cancellation propagation across dependent tasks.
- Add retry budgets and backoff policies.
- Add concurrency limits per workspace, session, agent, adapter, and provider.
- Add scheduling logs for auditability.

### Required Frontend Changes

- Show task graph execution status, not only a linear timeline.
- Surface blocked tasks and dependency reasons.
- Show active workers, queued work, retries, and cancellation state.
- Add controls for pause, resume, cancel graph, and rerun subset.
- Keep the simple demo path readable even when scheduling becomes richer.

### Data Model Impact

- Add `Worker`, `WorkerLease`, `TaskQueue`, or scheduler metadata records.
- Add task graph execution state separate from individual `TaskRun` rows.
- Add retry policy and concurrency policy entities.
- Add cancellation and dependency-resolution audit events.

### Security Risks

- Parallel agents can conflict in the same worktree or modify overlapping files.
- A stalled worker could leave locks or leases behind.
- Retry loops can burn quota or repeatedly apply unsafe changes.
- A scheduler bug could run unapproved tasks.

### Why Deferred From Final Demo Hardening

The final demo only needs one focused coding task at a time. Manager/worker
scheduling changes execution semantics, concurrency, locking, and approvals. It
must not be folded into demo hardening and is not a current three-week task.

## 7. Phase 4: ClaudeCode Security Review Agent

### Objective

Add a dedicated security review role, likely powered by `ClaudeCodeAdapter`, to
inspect diffs, identify risky changes, enforce path and secret rules, and
produce review artifacts before preview or deployment.

### Required Backend Changes

- Add a security-review task type and agent role.
- Package diffs, changed files, dependency metadata, and policy context for the
  review agent.
- Add a review verdict schema with severity, finding location, recommendation,
  and blocking/non-blocking status.
- Gate preview or deploy on configured review policy.
- Add policy configuration for protected paths, secret scanning, dependency
  changes, and command risk.

### Required Frontend Changes

- Show security review cards beside diff artifacts.
- Highlight blocking findings and required user decisions.
- Add approve-with-risk, request-fix, and dismiss-with-reason flows.
- Link findings to diff hunks or files.
- Show review status in task cards and artifact chips.

### Data Model Impact

- Add `Review`, `ReviewFinding`, or `PolicyCheck` records.
- Add severity, category, blocking status, source artifact, and resolution
  fields.
- Add approval decisions tied to findings.
- Add policy version metadata to make old reviews reproducible.

### Security Risks

- A review agent is not a security boundary by itself.
- False negatives could create misplaced confidence.
- False positives could block harmless work and slow the demo.
- Review prompts may expose sensitive code or secrets if context packaging is
  too broad.
- Auto-fix loops could create unreviewed changes unless gated.

### Why Deferred From Final Demo Hardening

The current hardening scope is documentation, verification, reset, and freeze.
A security review agent adds new runtime behavior, new approvals, and new
claims. It deserves a separate spec and is not a current three-week task.

## 8. Phase 5: Multi-User IM Integration

### Objective

Move from local single-user sessions to real multi-user collaboration with
presence, identity, permissions, threaded conversations, mentions, and optional
external IM integrations.

### Required Backend Changes

- Add authentication and user identity management.
- Add workspace membership and role-based permissions.
- Add multi-user session access control.
- Replace or augment SSE with WebSocket or another bidirectional realtime
  channel when presence and concurrent edits require it.
- Add message delivery state, read state, reactions, and mention notifications.
- Add integration adapters for Feishu, WeChat, Slack, or other IM systems only
  after core identity and permissions exist.

### Required Frontend Changes

- Add user identity, avatars, presence, and membership UI.
- Add shared session controls and permission-aware actions.
- Add mention autocomplete and notification surfaces.
- Add read receipts or delivery indicators if product scope requires them.
- Add conflict and concurrent-action feedback.
- Add external IM connection settings only after backend support is real.

### Data Model Impact

- Expand `User`, `Workspace`, and `Session` relationships.
- Add `WorkspaceMember`, `SessionParticipant`, `Presence`, `Mention`, and
  `Notification` records.
- Add external account and integration mapping tables.
- Add audit trails for user and agent actions.
- Consider migration from SQLite to Postgres when concurrent multi-user writes
  become a real requirement.

### Security Risks

- Cross-user data leakage becomes the main platform risk.
- External IM webhooks can be spoofed or replayed without strong verification.
- Mentions can trigger agent actions without proper authorization.
- Presence and notifications may reveal sensitive workspace activity.
- Multi-tenant isolation failures become severe.

### Why Deferred From Final Demo Hardening

Final demo hardening is explicitly local and single-user. Multi-user IM changes
identity, permissions, realtime transport, storage, and product surface. It is
not a current three-week task.

## 9. Phase 6: Plugin / Skill Ecosystem

### Objective

Allow AgentHub to grow beyond built-in adapters and fixed capabilities by
supporting plugins, skills, tools, and provider-specific integrations under a
governed capability model.

### Required Backend Changes

- Define plugin manifests and lifecycle states.
- Add capability registration, validation, and permission grants.
- Add tool invocation broker with audit logging.
- Add version compatibility checks.
- Add plugin sandboxing or isolation strategy.
- Add install, enable, disable, upgrade, and rollback flows.
- Add provider credential storage and secret handling only after a secure secret
  strategy exists.

### Required Frontend Changes

- Add plugin catalog and installed-plugin management UI.
- Show required permissions before enabling a plugin.
- Show which plugins or skills were used by a task run.
- Add configuration screens for provider credentials and capability toggles.
- Add warnings for untrusted or experimental plugins.

### Data Model Impact

- Add `Plugin`, `PluginVersion`, `Skill`, `Capability`, `ToolInvocation`, and
  `CredentialReference` records.
- Add permission grants scoped by workspace, user, session, and agent role.
- Add plugin audit events and failure records.
- Add dependency and compatibility metadata.

### Security Risks

- Plugins expand the trusted computing base.
- Tool calls can exfiltrate code, secrets, or user data.
- Bad manifests can overclaim safe behavior.
- Credential handling becomes a high-value attack surface.
- Version upgrades can silently change behavior unless pinned and audited.

### Why Deferred From Final Demo Hardening

The final demo should preserve a small, known adapter set. A plugin ecosystem is
a platform multiplier and security problem, not a demo hardening task. It is not
a current three-week task.

## 10. Phase 7: Real Deploy Providers

### Objective

Replace the current mock deployment card with real deployment integrations that
can publish preview or production environments through approved providers while
retaining artifact evidence and auditability.

### Required Backend Changes

- Add provider-specific deploy adapters such as Vercel, Netlify, Fly.io,
  Render, Kubernetes, or internal CI/CD.
- Add deployment target configuration per workspace.
- Add pre-deploy checks, approval gates, and environment policies.
- Add deploy job tracking, logs, cancellation, and rollback metadata.
- Add secret and environment-variable management.
- Add provider webhook handling for status updates.
- Add clear separation between preview deploy and production deploy.

### Required Frontend Changes

- Add deployment provider setup and environment selection UI.
- Show pre-deploy check results and approval requirements.
- Show real deploy logs, status progression, URLs, and rollback controls.
- Distinguish mock, preview, staging, and production deploys visually.
- Add warnings when deploying unreviewed or unapproved diffs.

### Data Model Impact

- Expand `Deployment` with provider, environment, project, region, build ID,
  commit SHA, log URL, status reason, rollback target, and approval metadata.
- Add `DeployProvider`, `DeployEnvironment`, `DeployCredential`, and
  `DeployPolicy` records.
- Add webhook event records for provider callbacks.
- Add environment variables and secret references without storing raw secrets in
  ordinary tables.

### Security Risks

- Production deploy can ship broken or malicious changes.
- Provider tokens and environment secrets are sensitive.
- A compromised agent could attempt to deploy unauthorized code.
- Rollback and cancellation failures can leave users in partial states.
- Webhook spoofing can forge deploy status.

### Why Deferred From Final Demo Hardening

The current deploy card is intentionally mock-backed. Real deploy providers
require credentials, approvals, provider APIs, logs, rollback, and production
risk controls. They are explicitly outside final-demo-hardening and are not
current three-week tasks.

## 11. Suggested Sequencing

Recommended order after final-demo-hardening:

1. Freeze the current local demo baseline.
2. Add a safe reset and seed workflow.
3. Introduce dynamic orchestrator planning behind a narrow spec.
4. Add shared context and memory after planning output is stable.
5. Add manager/worker scheduling once task graphs exist.
6. Add security review before expanding deploy or plugin capability.
7. Add real deploy providers with approval gates.
8. Add plugin/skill ecosystem only after permissioning and audit foundations are
   strong.
9. Add multi-user IM integration once identity, permissions, and realtime
   architecture are ready.

The order can change, but security review, permissions, and auditability should
arrive before broad plugin or production deployment capability.

## 12. Current Recommended Focus

The current focus should remain `agenthub-final-demo-hardening`:

- baseline consistency;
- browser E2E evidence;
- safe demo reset and restore;
- final demo checklist;
- final project summary and interview explanation;
- final freeze review.

The platform phases above are useful for strategy and future OpenSpec planning,
but they should not replace the current hardening work.
