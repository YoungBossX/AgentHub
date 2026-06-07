## Why

P18 made memory auditable and P18b proved deterministic memory effectiveness,
but AgentHub still needs bounded live-agent evidence that long-term memory
actually affects ClaudeCodeAdapter or CodexAdapter execution. P18c creates a
single non-trivial library-management app smoke that tests whether real coding
agents follow active memory without the user repeating those rules.

## What Changes

- Add a live memory compliance smoke centered on a new Library Management App
  task.
- Require active long-term memory rules to exist before the session starts.
- Verify that Planner, coding agent, review/eval, TaskRun evidence, and mission
  trace use the same `memorySnapshotId`.
- Run a real ClaudeCodeAdapter or CodexAdapter task when auth/quota/runtime
  permits; record the exact blocker when unavailable.
- Evaluate whether the generated app follows memory rules for project location,
  Vite + React + TypeScript, localStorage persistence, change-log update,
  target boundary, and provider evidence.
- Produce `docs/p18c-freeze-review.md` with session, run, memory, diff, review,
  build, preview/staging, and compliance evidence.
- Preserve P18/P18b boundaries: memory guides agents, while Target Registry,
  PlanValidator, Guardrails, runtime config, and scheduler policy enforce
  safety.

## Capabilities

### New Capabilities

- `live-memory-compliance`: live-agent smoke and compliance evaluation for
  long-term memory effects on a bounded coding task.

### Modified Capabilities

- None.

## Impact

- May add evaluation helpers, smoke scripts, tests, and freeze documentation.
- May create or register an external frontend target under
  `~/Desktop/agenthub-rehearsals/` during implementation.
- May run real ClaudeCodeAdapter or CodexAdapter only during implementation
  smoke, never during this planning task.
- Does not add backend/database hosting, production deploy, new memory
  retrieval algorithms, vector search, knowledge graph, provider marketplace,
  or any guardrail bypass.
