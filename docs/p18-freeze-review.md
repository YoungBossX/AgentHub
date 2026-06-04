# P18 Memory and Instruction Control Plane Freeze Review

**Date:** 2026-06-04

## Result

P18 is ready to freeze after adding a canonical memory and instruction control
plane for Planner, Claude Code, Codex, Review, and future coding agents.

P18 keeps memory as guidance and leaves enforcement in Target Registry,
PlanValidator, Guardrails, runtime config, and scheduler policy.

## Rehearsal Evidence

- Managed instruction bridge compiles deterministic `AGENTS.md` content and a
  short `CLAUDE.md` bridge while preserving a user custom block.
- New sessions receive a `memorySnapshotId`.
- Planner evidence, TaskRun metrics, canonical context, and mission trace record
  the same memory snapshot for a session/task chain.
- Explicit user memory writes such as `记住这个` create active canonical memory.
- Ordinary chat creates no long-term memory.
- Tool output, provider output, retrieved content, Claude/Codex suggestions, and
  scanned external files cannot create active memory without review.
- Active memory is retrievable by keyword with metadata filters and injected into
  Planner and coding-agent context.
- External `AGENTS.md` / `CLAUDE.md` scans create pending suggestions and detect
  conflicts without overriding canonical memory.
- `/settings/memory` shows memory status, source, scope, target, role, trust
  level, compiled outlet state, and current session `memorySnapshotId`.

## Metrics

| Metric | Current Evaluation |
|---|---|
| Preference Recall Rate | Covered by `tests/test_memory_evals.py`; saved preference appears in Planner and coding context. |
| Cross-Agent Consistency Rate | Covered by snapshot consistency checks across Planner, TaskRun, and context. |
| Memory Precision@5 | Covered by retrieval tests using relevant and non-relevant memory items. |
| Stale Memory Injection Count | Covered by stale/archived exclusion tests and eval helper. |
| Prompt Injection Write Block Rate | Covered by untrusted-source active-write rejection tests. |
| Snapshot Consistency Rate | Covered by session refresh, TaskRun, planner, context, and mission trace tests. |

## Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `pnpm demo:api:test` | Pass through `pnpm test` |
| `git diff --check` | Pass |
| `openspec validate agenthub-p18-memory-instruction-control-plane --strict` | Pass |

## Remaining Limitations

- P18 uses keyword/BM25-style retrieval, not embeddings, RRF, or knowledge graph
  retrieval.
- Supersede is implemented in the service layer; the first UI exposes status
  review actions and defers rich edit/supersede workflows.
- External Claude Code and Codex private memory scans are policy-planned but not
  automatically imported.
- Memory effectiveness metrics are deterministic tests and rehearsal checks, not
  a production telemetry dashboard.
- Memory does not grant permissions and cannot bypass Target Registry,
  PlanValidator, or Guardrails.
