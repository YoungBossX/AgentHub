# Verification

## Scope and source
Base dev commit: `1c0e54ed4fe85e3051a764cfbb643a2b47240830`, preserving earlier
uncommitted readiness work and unrelated teaching/interview files. This task
changes only the opt-in trusted contacts contract/harness, its tests and docs.
Actual generated-case repairs are external native runs, not platform UI edits.

## Regression evidence
- `contract-red.log`: two expected failures before v4 support.
- `contract-first.log`: 14 passed, including unchanged v3 and malformed-save mutant.
- `contract-controls.log`: four v4 positive/negative controls passed.
- `neutral-red.log`: expected failure proving an error-styled notice was accepted
  before adding the existing neutral-class guard to the new checks.
- `contract-final.log`: 52 passed / 1 failed; the failed old preparation test
  recorded integration `stale` because the harness changed while running. This
  overlapping run is retained and is not the final source verification.
- `contract-stable.log`: 63 passed at that intermediate policy.
- `contract-race-controls.log`: 18 passed after adding delayed initial responses.
- `abort-red.log`: expected failure for a valid AbortController-based control.
- `contract-race-final.log`: seven controls passed after cancellation handling.
- `regression-frozen.log`: final five-suite frozen-source run **102 passed** in
  523.10s. JUnit: `E:/Docker/cq26/agenthub-pytest-api.GVAf36/results.xml`.

## Real native corrections, separately retained
1. `E:/Docker/cqfix26-01`: fresh copy of preserved failed case and read-only SQLite
   backup, new Session/database and fixture repository. Native Planner/coding/QA;
   original three findings repaired. Native QA warning identified a real initial
   GET versus post-save refresh race. Draft v4 also falsely required an additional
   status on successful reconciliation. Failed result and its 34-check frozen
   policy remain unchanged. Product/configuration/original-evidence checks passed.
2. Final policy keeps historical v1-v3 behavior and extends unreleased v4 to 38
   checks. Fixes the harness false rejection and accepts observed cancellation of
   only the exact held initial GET; canceled delivery status is null, original
   backend status is separate. Independent controls cover blocking, cancellation,
   eager acknowledgement, hidden empty text, misleading/error-styled notices and
   stale initial success/failure. No new adapter or permission, retries remain 0.
3. `E:/Docker/cqfix26-02`: fresh copy/new Session and native Planner/coding/QA;
   only App.tsx changed from prior repair, adding disabled initial-loading controls,
   submit guard and request-generation fences. Native QA passed with zero findings;
   final v4 38/38, original v3 28/28. Phase elapsed 142.203s; operator elapsed
   including preparation/baselines/final legacy recheck 163.453s, not model latency.
   Three recorded calls total 275699 Token including 216704 cache-read tokens;
   estimated cost is not verified billing. Unknown stage fields remain unknown.

## Independent check
`E:/Docker/cqverify26-01/verification.json` verifies final source/archive hashes,
fresh current native read/assessment receipt, zero findings, two stored nonempty
Diff hashes/exports, 610 continuous unique TaskRunEvent sequence entries and
SQLite quick/FK checks. Database hash unchanged across read-only verification.
Original ten natural cases remain 8/10, original and intermediate source/SQLite
and report hashes unchanged. Primary product login classes and data/configuration
preserved. No HTTP/UI preview/deployment/remote CI claim; no commit or push.

All operator scripts, logs, snapshots, fixture Git history, databases and temp
data are under E:/Docker. API compile passed with bytecode redirected to
E:/Docker/cq26/compile-cache; Node script syntax, strict OpenSpec validation and
git whitespace checks passed. No generated build/cache/database output staged.
