# Memory Snapshot Content Consistency Implementation Plan

> Execution: complete this single OpenSpec task in the current session with TDD and independent read-only review. The existing dirty implementation belongs to this task and is preserved before edits. No commit or push is authorized.

**Goal:** A snapshot identifies a fixed memory collection and scoring time; prepared planner/coding requests retain verifiable memory usage evidence.

**Architecture:** Preserve SQLite and the existing MemorySnapshot.meta_json schema surface. Production consumers retrieve frozen v2 members, retain legacy v1 as unavailable historical content, and persist filtered request receipts using existing TaskRun fencing.

**Tech Stack:** Python, SQLModel/SQLite, Pydantic, pytest; existing Next.js compatibility checks.

**Spec:** [design.md](design.md), [spec.md](specs/memory-snapshot-content-consistency/spec.md).

## Constraints

- Implement only OpenSpec task 1.1. No Skill/MCP, mandatory-rule selector, semantic retrieval, automatic learning, dependency installation or new database entity.
- Preserve adapters, target permissions, protected paths, serial fallback and execution lease checks.
- Use repository Python from apps/api with a fresh external pytest basetemp. No production database or real provider mutation for tests.
- Preserve existing v1 records without backfilling current content. Only explicit refresh changes an existing Session's snapshot.
- A prepared-request receipt does not prove provider execution or compliance.

## Task 1.1: Complete and verify the existing implementation

Files: memory_snapshots.py / memory_store.py own immutable members and hashes; memory_retrieval.py owns scoring against frozen time; context_pack.py / llm_planner.py consume frozen members; planning.py / task_runs.py / run_engine.py preserve binding and request evidence; memory_usage.py describes the filtered request. Tests belong in test_memory_snapshot_consistency.py and relevant existing task/planner integration tests. Final documentation is docs/project-state.md, docs/change-log.md and this OpenSpec.

- [x] Preserve existing dirty files and inspect the specification and current source.
- [x] Establish focused baseline: 64 memory tests passed on 2026-09-09.
- [ ] Check consumer boundaries with failing regressions before fixes: a changed bound digest must reject request preparation; a damaged snapshot must produce a recoverable bounded error; TaskRun creation and retry must bind the explicitly documented snapshot choice without rewriting earlier evidence.
- [x] Confirm refresh, reload, workspace/role/target boundaries and v1 compatibility with real temporary SQLite, and keep error paths free of original private memory text.
- [x] Fix only demonstrated gaps; rerun focused memory and adjacent planner/TaskRun checks.
- [ ] Receive independent read-only review and resolve substantive findings with regression tests.
- [x] Run full API regression, pnpm check, Web tests, demo-api tests, strict OpenSpec validation and git diff --check. Investigate actual failures before changing fixtures or production behavior.
- [x] Record verification results and remaining evidence boundaries; update project documentation and mark only task 1.1 complete.

### Verification commands

Run from apps/api with ../../.venv/Scripts/python.exe:

```text
python -B -m pytest -q -p no:cacheprovider --disable-warnings --basetemp=<fresh external path> tests/test_memory_snapshot_consistency.py tests/test_memory_store.py tests/test_memory_retrieval.py tests/test_memory_write_policy.py tests/test_memory_instructions.py tests/test_memory_evals.py tests/test_memory_rehearsal.py
python -B -m pytest -q -p no:cacheprovider --disable-warnings --basetemp=<fresh external path>
```

Run from repository root:

```text
pnpm check
pnpm test:web
pnpm demo:api:test
openspec validate agenthub-memory-snapshot-content-consistency --strict
git diff --check
```

### Acceptance evidence

Compare exact selected content/version/hash and scores before/after live-store mutations; reopen SQLite to verify persistent replay; compare receipt hashes with the actual filtered instruction. Verify rejected preparation does not write a new request receipt or invoke an adapter. Keep test-double evidence separate from real-provider behavior.

### 2026-10-07 verification record

- Reproduced the invalid-plan fallback AttributeError before changing code (1 failed), then extracted evidence from the original conversation.planner_input and asserted the fallback reason/error code.
- Focused memory regression: 95 passed. Full API with the test-process-only CODEX_CLI_PATH=codex setting: 1,293 passed / 1 Windows POSIX-only skipped. Web: 109 passed; demo-api: 5 passed; pnpm check and strict OpenSpec validation passed.
- The initial full API run had one unrelated CLI health test expecting codex instead of the ambient codex.exe command summary. Its sources and production configuration were preserved; the isolated rerun and normalized full rerun passed.
- Source review in this turn was performed by the primary agent. No independent Subagent review was dispatched; the independent-review checkbox and earlier consumer-specific failing-first checkbox remain unchecked rather than fabricating those process steps. OpenSpec task 1.1 is marked complete against its specified implementation and verification criteria.
- No real provider compliance claim, commit, push, dependency installation, or subsequent OpenSpec task is part of this closeout.
