## 1. P18-1 Managed AGENTS.md / CLAUDE.md Bridge

- [x] 1.1 Define deterministic managed block markers for `AGENTS.md` and preserve a user custom block.
- [x] 1.2 Compile the `AGENTS.md` managed block from AgentHub canonical memory, target summaries, runtime boundaries, and guardrail references.
- [x] 1.3 Generate a short `CLAUDE.md` bridge that references or imports `AGENTS.md` where practical.
- [x] 1.4 Ensure `CLAUDE.md` does not duplicate large project rules.
- [x] 1.5 Add tests for deterministic export, custom block preservation, and idempotent re-export.

## 2. P18-2 Memory Snapshot Model

- [x] 2.1 Add or plan a persisted memory snapshot model with `memorySnapshotId`.
- [x] 2.2 Associate sessions with a memory snapshot by default.
- [x] 2.3 Record snapshot IDs and relevant hashes/versions on Planner evidence, TaskRun metadata, mission trace, or artifact metadata where appropriate.
- [x] 2.4 Ensure Planner, Claude Code, Codex, and Review Agent use the same snapshot for one session/task chain.
- [x] 2.5 Prevent running TaskRuns from silently switching snapshots.
- [x] 2.6 Add tests for snapshot consistency and explicit session refresh behavior.

## 3. P18-3 Canonical Memory Model

- [x] 3.1 Add memory item schema with scope, type, source, status, trustLevel, targetIds, agentRoles, lastUsedAt, supersededBy, and timestamps.
- [x] 3.2 Support statuses: active, pending_review, warm, archived, rejected, deleted.
- [x] 3.3 Define memory types for project rules, user preferences, decisions, patterns, feedback, session summaries, and external suggestions.
- [x] 3.4 Add version/hash metadata for project memory and user preference memory.
- [x] 3.5 Add tests for schema validation, status transitions, supersession, and scope filters.

## 4. P18-4 Memory Write Policy and Prompt-injection Guard

- [x] 4.1 Detect explicit user memory write intents such as "记住这个", "以后都这样", and "写入项目规则".
- [x] 4.2 Create active memory only after user-confirmed writes where policy allows it.
- [x] 4.3 Create `pending_review` candidates for system discoveries such as repeated build failures, review findings, deploy failures, and repeated fixes.
- [x] 4.4 Ensure ordinary chat does not become long-term memory automatically.
- [x] 4.5 Block file contents, tool output, provider output, retrieved content, and Claude/Codex suggestions from becoming active memory without review.
- [x] 4.6 Add prompt-injection guard tests and user-confirmation tests.

## 5. P18-5 Memory Retrieval v1

- [x] 5.1 Implement or plan SQLite FTS5 / BM25-style keyword retrieval.
- [x] 5.2 Add metadata filters for scope, target, role, status, and time window.
- [x] 5.3 Apply importance/trust scoring, time decay, stale penalty, conflict penalty, and token-cost penalty.
- [x] 5.4 Retrieve relevant memory for Planner and follow-up task context.
- [x] 5.5 Keep embedding, RRF, and graph retrieval out of mandatory P18 scope.
- [x] 5.6 Add tests for Memory Precision@5, status filtering, target filtering, role filtering, and stale-memory exclusion.

## 6. P18-6 External Agent Memory Scan

- [ ] 6.1 Scan repo `AGENTS.md` and `CLAUDE.md` into external memory suggestions.
- [ ] 6.2 Plan safe scanning for Claude Code local auto memory and Codex global/repo instructions.
- [ ] 6.3 Detect conflicts between external suggestions and AgentHub canonical memory.
- [ ] 6.4 Ensure external suggestions never auto-import as active memory.
- [ ] 6.5 Add tests for suggestion creation, conflict detection, and no automatic override.

## 7. P18-7 Memory Management UI

- [ ] 7.1 Add `/settings/memory` or equivalent settings surface.
- [ ] 7.2 Show active, pending, warm, archived, rejected, and deleted memory.
- [ ] 7.3 Allow confirm, reject, archive, delete, and supersede actions where policy allows.
- [ ] 7.4 Show source, scope, target, agent role, trust level, status, and compiled-to outlet state.
- [ ] 7.5 Show current `memorySnapshotId` for a session where useful.
- [ ] 7.6 Add UI tests for review actions, filters, and snapshot display.

## 8. P18-8 Memory Eval and Freeze Review

- [ ] 8.1 Add targeted evals for Preference Recall Rate.
- [ ] 8.2 Add targeted evals for Cross-Agent Consistency Rate.
- [ ] 8.3 Add targeted evals for Memory Precision@5.
- [ ] 8.4 Add targeted evals for Stale Memory Injection Count.
- [ ] 8.5 Add targeted evals for Prompt Injection Write Block Rate.
- [ ] 8.6 Add targeted evals for Snapshot Consistency Rate.
- [ ] 8.7 Rehearse a saved preference or project rule flowing to Planner and coding agents through the same snapshot.
- [ ] 8.8 Run freeze validation and document limitations honestly in `docs/project-state.md`, `docs/change-log.md`, and a P18 freeze review doc.

## 9. Explicit Non-goals Confirmation

- [ ] 9.1 Confirm P18 does not implement mandatory vector database, full knowledge graph, RRF fusion, automatic long-term learning without review, multi-user shared memory, provider marketplace, cloud secret manager, production deploy, or guardrail replacement.
- [ ] 9.2 Confirm Claude Code / Codex private memory cannot override AgentHub canonical memory.
