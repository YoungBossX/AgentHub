# Same-version native QA evaluation

2026-10-16. Local implementation only; no commit/push or product runtime restart.
This is item 1 of [the ordered three-item objective](ordered-local-improvements.md).
Business contracts and execution-engine/task-card extraction were completed later
in separate focused tasks; see the ordered objective. This frozen cohort predates
those source/policy changes and is not a current-version performance claim.

## Implementation

The v2 CLI defaults live QA to the existing Claude read-only contract. Fresh
evaluation workspaces get explicit custom coding/review profiles and mentions;
changing an Agent label alone cannot establish the selected native provider.
Product settings, database and worktrees are untouched. Scripted QA is allowed
only with the explicit test-double API path, never the live CLI.

Each QA attempt records server-persisted assessment/artifact identifiers, actual
full-file Read hashes, bound source manifest, input/output identity, adapter and
current layered validation. The evaluator revalidates the native assessment and
current input, requires every writer-changed file to be read, matches source to
the independent acceptance version and rejects missing/scripted/expired/wrong
owner/prose-only evidence. Warning/failed assessments do not count as passed.
This verifies review provenance, not that every model judgement is correct.

Cohort identity includes uncommitted API implementation, trusted Python/Node
scripts and helpers, patch/dependency declarations, demo fixture inputs, selected
profiles, scenario prompts/repetitions/retry policy and Python version. Before/
after-case drift or unreadable policy invalidates whole-cohort rates, preserves
observed outcomes and stops remaining cases. Running/interrupted reports have no
final native success rate. HEAD alone is not the version identifier; this does
not guarantee an unchanged remote model or CLI-internal context.

Explicit failed/interrupted retries are bounded to 0–2 per task (default 1),
using the existing retry API without resets/permission bypass. Completed model
warnings do not trigger an automatic coding repair. Every failure/retry lineage
remains; first-attempt success includes coding, native QA and independent checks.
Per-attempt server start/end wall time is separated into coding and QA totals;
missing/invalid timing remains unknown. Preparation/total scenario time is
separate from execution wall time, not model inference duration or token cost.

## Verification so far

- Final focused tests: **35 passed**. Real production read-only parser, scoped
  profiles, full-file evidence and persisted QA artifact were exercised with an
  explicitly labeled native transport double; natural QA failure/retry preserved
  first-attempt failure, retry count and role duration. Native gates, drift,
  unreadable sources, partial-rate suppression and policy coverage passed.
- Earlier workflow integration/scoring batch: **48 passed**; adjacent native
  review/layered QA: **55 passed**. Batches overlap, not a unique total.
- Root checks passed before the final policy-coverage addition; its final import/
  syntax and the above 35 tests passed afterward. No Web changes in this task.
- An intermediate policy-list parenthesis typo failed test collection and was
  fixed before this final run. No live result was produced by that failed run.

## Live evidence

A real backend pilot **passed on its first attempt, no retries**: actual native
Planner, Codex write, one verified Claude read-only QA artifact, current automatic
checks and independent ASGI acceptance; immutable inputs held. Execution wall
91.891 s, coding run 52.697 s, QA run 18.247 s, total including preparation
93.063 s. This one case is not a general success-rate estimate.

The frozen ten-sample batch completed with process exit **1** (four samples did
not pass). All 195 fingerprinted policy/input files still matched at terminal
inspection; the cohort was not invalidated:
`dd27e0051a7b422a84af09a11da212b3eee6bc024b3145c6da93a87d62419565`.
Five categories each have two fresh repetitions. Its platform policy map matches
the pilot; the pilot is excluded from this ten-sample denominator.

| Population | First attempt | Final | Explicit retries |
| --- | --- | --- | --- |
| All ten samples | 4/10 (40%) | 6/10 (60%) | 2 |
| Natural scenarios | 4/8 (50%) | 4/8 (50%) | 0 |
| Deliberate failure injection | 0/2 | 2/2 | 2 |

There were 12 coding attempts (two injected failures, ten completed), 10 completed
native QA attempts, and **10 verified native QA receipts**. Coding wall totals:
461.598 s, median 40.163 s, maximum 88.641 s; QA totals: 245.096 s, median 22.1155 s,
maximum 41.478 s. Scenario execution median 90.6795 s, maximum 267.234 s. Total
scenario time including preparation: 1,160.468 s, median 100.617 s, maximum
294.984 s. Per-role sums are not end-to-end duration, and neither measures model
inference alone. No token-cost or general model-success claim follows.

### Retained failures

- Coordination repetition 1: independent backend/frontend/integration checks
  passed; actual frontend native QA warned about `Contact.id: number` while the
  backend creates string identifiers. Both native QA receipts verified. The
  advisory type mismatch did not break the tested create/list/persist flow;
  warning still does not count as passed.
- Coordination repetition 2: actual Planner failed with `PLANNER_TIMEOUT` at its
  60-second deadline, before any coding or QA. Missing-evidence gates describe
  the resulting absent work, not independent coding-provider failures.
- Follow-up repetitions 1 and 2: first phases passed, second phases never reached
  coding. Actual Planner evidence records `CONTEXT_BUDGET_EXCEEDED`: 240,662 and
  244,894 text characters against 200,000. The Planner currently embeds the full
  mission trace (including historical event payloads and artifact metadata).
  In repetition 1, persisted event payloads alone include 41,627 characters of
  message deltas. This identifies an expansion path but is not an exact additive
  attribution of every serialized character. Required rules must not be silently
  truncated; raising the budget is not a repair. Context compaction is follow-up
  work, not claimed fixed by this evaluation task.

No source edits occurred during the live batch. The original report SHA-256 is
`c6470fb5652197edb3a2140bb81e49e5c648d12d9d273aae72dc3926b55ef618`.
[The bounded export](evidence/native-qa-evaluation/batch.json) preserves case and
phase outcomes, Planner error/budget counters, all failed/retried attempt lineage,
full-file read/source/assessment identities and independent validation. Every
selected sample and both coordinated targets were inspected; failed samples are
not replaced by rechecks. This is an isolated CLI workflow, not product UI/SSE,
live HTTP preview, deployment, broader business coverage or a distinct-task study.

### Post-batch reporting correction

The frozen raw/exported cohort remains unchanged. After terminal inspection,
initial pending rows gained `faultInjection` metadata so interim natural/injected
selection counts are correct before execution. `attempted` now counts a started
scenario independently of timing, with separate `finalized` and `timed` counts;
harness errors without duration no longer disappear. Running rates remain null.
This source revision is later than the live cohort and is tested separately;
the ten-sample final denominators/rates were independently recomputed unchanged.

Final post-batch focused verification: **37 passed / 41.40 s** in `agenthub-native-qa-postbatch-20261016.log`; source changes are limited to report counters after the live run.
