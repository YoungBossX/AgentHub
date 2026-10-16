# Execution ownership and task-card modularity

2026-10-16. Item 3 of the ordered objective. Local source only; no dependencies,
product restart, commit/push or deployment.

## Actual boundaries

`execution_ownership.py` owns immutable execution/finalizer/launch/failure records,
exact run/session/queue/lock comparisons, ownership token capture and transactional
lease renewal. It depends on lower-level models/scope/scheduler/queue/task-run
modules, never on run_engine. The engine retains orchestration, lease controller,
launch/finalizer commit fences and its existing names. Two small forwarding
wrappers preserve the engine's clock and historic injection seams; authority
checks are not duplicated. BEGIN IMMEDIATE, conditional generation/owner writes,
rollback and lock identity remain unchanged.

`task-card-data.ts` centralizes pure plan/scheduler interpretation.
`task-plan-summary.tsx` renders plan evidence and PMO controls.
`artifact-message-cards.tsx` owns artifact presentation, action/disable rules,
metadata and ordering. TaskCardList retains fetching, state, selection and run
orchestration. ArtifactContextIntent is type-re-exported from its historic path.
All children inherit the original client boundary; no server callback boundary
was introduced. The installed Next use-client guide was read before edits.

| File | Before | After |
| --- | ---: | ---: |
| run_engine.py | 4,103 | 3,743 |
| execution_ownership.py | absent | 419 |
| task-card-list.tsx | 1,532 | 767 |
| task-card-data.ts | absent | 156 |
| task-plan-summary.tsx | absent | 213 |
| artifact-message-cards.tsx | absent | 408 |

Line counts identify changed boundaries, not runtime speed or quality metrics.
Total source includes extra explicit imports/wrappers; no function body is copied
into both entrypoint and extracted module.

## Source equivalence

The pre-edit engine and task-card source were saved externally in
`agenthub-modularity-baseline-0_ruht63`. AST comparison verified eleven backend
definitions moved unchanged except two internal export renames and an explicit
optional clock for token capture; the engine forwards its existing clock.
Seventy-four remaining engine definitions are unchanged. Frontend comparison
verified all 28 moved declarations and twelve remaining entry declarations after
normalizing only export modifiers and newlines, including JSX labels/classes,
callbacks and disable conditions. These checks are static evidence and do not
replace the runtime regressions below.

## Verification

- Final lifecycle/lease/generation/scope/artifact/dispatcher/responsiveness batch:
  **548 passed, 1 skipped / 147.48 s**. The skip is exact-case POSIX filesystem
  semantics on Windows, not a silently omitted ownership check.
- The first identical batch had **542 passed, 6 failed, 1 skipped** because its
  fresh global SQLite had no tables; route tests schedule work against that
  global database even with overridden request fixtures. All six errors were
  missing `targetlock`. Initializing a new isolated global schema (26 tables)
  made the same six pass, then the full batch above passed. Product DB and code
  were not changed to suppress these failures.
- Web full **326 passed / 43 files / 35.16 s**, exercising extracted children
  through TaskCardList. Initial unused-import warnings were removed; final
  ESLint/TypeScript check passed without warnings. A temporary extraction helper
  initially used CommonJS's reserved `exports` binding and failed before writing
  source; it was renamed and rerun.
- Adjacent native-review/backend-validation/isolated-worktree/DAG/provider-contract
  batch: **139 passed / 336.97 s**. This includes actual isolated source and
  integration state tests; it does not claim real provider execution.
- Root `pnpm check` passed with the installed Git Bash in this process PATH.
  Final strict OpenSpec and whitespace verification passed. No new whole-API,
  product UI/browser or remote CI acceptance is claimed. The two API batches and
  Web tests have different scopes and are not a universal success count.

External logs/XML under local Temp: `agenthub-modularity-api-final-20261016`,
`agenthub-modularity-adjacent-20261016`, `agenthub-modularity-webtests-20261016.log`,
`agenthub-modularity-webcheck-final-20261016.log`, and
`agenthub-modularity-rootcheck-20261016.log`. The initial uninitialized-DB batch
remains in `agenthub-modularity-api-20261016.log`/`.xml`; six-case environment
recheck is in `agenthub-modularity-envfix-20261016.log`.

The [bounded evidence](evidence/execution-card-modularity/README.md) retains source
hashes/equivalence, test-report hashes and the explicit skipped-test reason.
Item 3 is complete locally. Overall completion is limited to the original three
scoped improvements; current source/policy differs from the earlier native-QA
cohort, whose results and failures remain immutable and historical.

Current local web port 3000 was not listening when inspected. No product server
was started or restarted. Browser-based business acceptance belongs to item 2;
this refactor's UI evidence is full component regression and source equivalence,
not a new full-page Next/browser or real Provider acceptance run.

This is a focused first extraction, not complete decomposition of the engine,
scope/persistence modules or every task-card helper. Remaining large modules and
the native-QA cohort's context growth/Planner-timeout findings remain explicit
future work; the three scoped improvements do not establish arbitrary-task or
production readiness.

Final requirement-by-requirement audit passed: all three checklists closed, ten-sample cohort/raw SHA and denominators verified, final business input/current-policy receipts matched, current modularity source/test hashes matched, and 144 local document links resolved. [Audit](evidence/execution-card-modularity/completion-audit.json) explicitly identifies seven changed historical native-cohort policy paths; no final-revision native performance is inferred.

Delivery preparation, 2026-10-16: staged whitespace checking found one extra EOF separator in the new ownership file. Removing it changes 420 to 419 lines; Python AST is identical, and source/audit hashes record both revisions. Runtime tests above predate this EOF-only normalization; no behavior or frozen cohort was rewritten.
