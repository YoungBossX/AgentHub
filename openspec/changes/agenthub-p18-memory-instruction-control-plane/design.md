## Context

AgentHub now has a clear runtime split:

```text
user message
-> Conversation Router / Planner LLM
-> ConversationOutcome
-> PlanValidator
-> Scheduler
-> Frontend / Backend / Review coding agents
```

P17b added API Planner providers, and P17c moved Planner/Frontend/Backend/Review runtime configuration into settings. P9 through P17 also added Target Registry, external workspace mode, scheduler, recovery, canonical context, mission trace, diff/review/preview/staging evidence, and target-aware execution.

The remaining gap is instruction consistency. The Planner may receive one system prompt, Claude Code may read `CLAUDE.md` or auto memory, Codex may read `AGENTS.md`, Review may receive another instruction block, and Target Registry/PlanValidator may enforce a separate reality. P18 should make AgentHub the memory and instruction source of truth while preserving hard guardrails outside the memory system.

## Goals / Non-Goals

**Goals:**
- Make AgentHub Canonical Memory the source of truth for project instructions and cross-agent memory.
- Compile/export deterministic instruction artifacts for `AGENTS.md`, `CLAUDE.md`, Planner, Claude Code, Codex, and Review Agent.
- Add session-level memory snapshots so every agent in a session/task chain can be audited against the same memory version.
- Add scope-aware memory lifecycle, scoring, retrieval, write policy, prompt-injection guard, and external memory suggestion handling.
- Add memory management UI and measurable eval criteria.
- Preserve P6-P17c baselines and existing runtime provider settings.

**Non-Goals:**
- Do not build full graph memory, mandatory vector retrieval, or RRF fusion in P18.
- Do not allow automatic long-term learning without user review.
- Do not add multi-user shared memory, provider marketplace, cloud secret manager, production deploy, or new coding adapters.
- Do not let memory bypass Target Registry, PlanValidator, Guardrails, runtime provider config, or platform maintenance approval.

## Core Decisions

### AgentHub Canonical Memory Is Source Of Truth

AgentHub should maintain canonical memory items and compile instruction outlets from them. `AGENTS.md` and `CLAUDE.md` become generated/managed artifacts with preserved user custom areas.

External agent memory, including Claude Code auto memory or Codex global/repo instructions, should be treated as suggestion input only. It may create `pending_review` memory candidates and conflicts, but it must not automatically become active memory or override AgentHub canonical memory.

### Memory Is Not Guardrails

Memory may say "prefer Chinese responses" or "run `pnpm check` after frontend changes." It must not enforce security. Forbidden paths, secret protection, platform maintenance mode, production deploy prohibition, target write permissions, and command policy remain in Target Registry, PlanValidator, Guardrails, Scheduler, and runtime execution policy.

### Snapshot Before Execution

Each session should receive a `memorySnapshotId`. Planner evidence, TaskRun metadata, mission trace, and review evidence should reference that snapshot where useful. A running TaskRun must not silently switch snapshots. Memory changes should affect new sessions by default. Existing sessions should refresh only through an explicit refresh action that records the old and new snapshot.

### Managed Markdown File Responsibilities

P18 should support or plan these files:

| File | Responsibility |
|---|---|
| `AGENTS.md` | Cross-coding-agent project instruction outlet. Contains an AgentHub managed block plus preserved user custom block. Used by Codex and other coding agents. |
| `CLAUDE.md` | Short Claude Code bridge. References/imports `AGENTS.md` where possible and avoids duplicating large rules. |
| `.agenthub/memory/project.md` | Project structure, stack, commands, workflow rules. |
| `.agenthub/memory/user-preferences.md` | User language, style, validation, and documentation preferences. |
| `.agenthub/memory/decisions.md` | Architecture decisions, phase conclusions, and supersession notes. |
| `.agenthub/memory/patterns.md` | Failure patterns, common fixes, and known regression traps. |
| `.agenthub/memory/feedback.md` | User feedback about agent behavior. |
| `.agenthub/memory/sessions/YYYY-MM-DD.md` | Session summaries and daily task logs. |

### Hot Memory Budget

P18 should define initial practical limits and enforce summarization/archive behavior instead of append-only growth:

| File / Region | Initial Budget |
|---|---:|
| `AGENTS.md` managed block | 8k-12k characters |
| `CLAUDE.md` | 1k-3k characters |
| `project.md` | 6k-10k characters |
| `user-preferences.md` | 1.5k-3k characters |
| `decisions.md` | 8k-12k characters |
| `patterns.md` | 8k-15k characters |
| `feedback.md` | 5k-8k characters |
| `sessions/YYYY-MM-DD.md` | 20k-50k characters |

If a file exceeds budget, AgentHub should summarize, archive, or downgrade low-value memory. It should not delete-first.

### Lifecycle And Eviction

Memory item statuses:

- `active`
- `pending_review`
- `warm`
- `archived`
- `rejected`
- `deleted`

Eviction is downgrade-based. Project rules and user preferences should not be evicted by time alone. Pattern memories may be downgraded by low usage, age, low helpfulness, conflict, or high token cost. Session summaries may be compressed and archived. Superseded memories should be archived with `supersededBy` metadata.

### Scoring Model

Memory retrieval and hot/default inclusion should use a score based on:

- importance
- trust level
- usage frequency
- recency
- recent success
- specificity
- token cost
- conflict penalty
- stale penalty

The score should drive whether memory is hot/default, retrieval-only, warm, or archive-only.

### Memory Write Policy

Explicit user memory writes may create memory candidates:

- "记住这个"
- "以后都这样"
- "写入项目规则"
- "写进 user-preferences.md"

Automatic system discoveries from build failures, review findings, deploy failures, and repeated fixes may create `pending_review` candidates only. Ordinary chat must not become long-term memory automatically. File contents or code comments saying "remember this" must not create memory automatically.

### Prompt-injection Guard

Memory writes from files, tool output, provider output, Claude/Codex suggestions, or retrieved content must go to `pending_review` or `rejected`, not `active`. User confirmation is required before long-term project rules, user preferences, and cross-agent instructions become active.

### Retrieval v1

P18 retrieval should be intentionally modest:

- SQLite FTS5 or BM25-style keyword retrieval;
- scope filter;
- target filter;
- role filter;
- status filter;
- time decay;
- importance/trust score.

Embedding retrieval, RRF fusion, and knowledge graph retrieval are future enhancements.

### Context Injection Policy

Planner LLM receives:

- user preferences;
- project summary;
- current session / mission summary;
- relevant retrieved memories;
- relevant artifact evidence.

Claude Code receives:

- `AGENTS.md` / `CLAUDE.md` instructions;
- task instruction;
- target boundary;
- selected relevant memory snippets;
- validation expectations.

Codex receives:

- `AGENTS.md` instructions;
- task instruction;
- target boundary;
- selected relevant memory snippets;
- validation expectations.

Review Agent receives:

- diff;
- review checks;
- project rules;
- relevant pattern memory.

Normal chat must not invoke coding agents.

### External Agent Memory Management

AgentHub may scan:

- repo `AGENTS.md`;
- repo `CLAUDE.md`;
- Claude Code local auto memory;
- Codex global or repo instructions.

Scanned memory becomes external suggestions. It must not automatically overwrite canonical memory. Conflicts should be detected and shown to the user.

### Consistency Evidence

P18 should record these identifiers/hashes/versions where appropriate:

- `memorySnapshotId`;
- `agentsMdHash`;
- `claudeMdHash`;
- `projectMemoryVersion`;
- `userPreferenceVersion`;
- `targetRegistryVersion`;
- `runtimeConfigVersion`;
- `contextPackHash`.

These should appear in TaskRun evidence, planner evidence, mission trace, or artifact metadata where useful.

## Risks / Trade-offs

- Memory system scope can explode -> Mitigation: implement P18 as small, evaluable tasks and keep retrieval v1 keyword-based.
- Generated `AGENTS.md` may overwrite user edits -> Mitigation: use managed block markers and preserved user custom block.
- Claude/Codex private memory may conflict with AgentHub rules -> Mitigation: scan as suggestions and require confirmation.
- Prompt injection through files or provider output could create persistent rules -> Mitigation: pending/rejected default and user confirmation for active long-term memory.
- Snapshot metadata can add noise -> Mitigation: expose summary in mission trace and detailed hashes in evidence metadata.

## Evaluation Metrics

P18 should define targeted evals:

- Preference Recall Rate.
- Cross-Agent Consistency Rate.
- Memory Precision@5.
- Stale Memory Injection Count.
- Prompt Injection Write Block Rate.
- Snapshot Consistency Rate.
- Task Success Delta.
- Change-log Missing Rate when change-log preference is active.
