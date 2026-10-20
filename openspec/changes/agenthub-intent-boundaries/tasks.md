## 1. Intent recognition boundaries

- [x] 1.4 Fix the live feedback route rejecting ordinary email addresses as unknown Agent mentions. Use one shared lexical boundary for built-in/custom recipient selection and mention stripping, preserve explicit unknown/disabled rejection and Chinese adjacent mentions, verify literal copy values and real routing, then repeat the previously rejected real repair instruction. Preserve the measured source-A cohort instead of relabeling it as a post-fix run.

1.4 verified2026-10-20: initial14-case RED9; Unicode4-case RED4; final18-case
and adjacent regressions338passed, authored corpus85/85. Final B2 root check/full
pnpm test exit0: API2782passed/19skipped/2warnings, Web333/tools24/demoAPI5;
source216 plus3additional files match the frozen snapshot, independent review no
remainingP1/P2. Same rejected real prompt passed earlier frozenB1 with4observed
coding/review turns,2nativeQA and24/24business checks; A's10-case8/10 result
unchanged. No B2 model cohort or new Docker/remote-CI claim. User confirmed
retaining2policy-denied pytest caches. See docs/real-api-validation-20261019.md.

- [x] 1.3 Fix neutral comma introductions without treating their first imperative
  as a second action; retain negative/informational/multi-action/quoted/slot
  boundaries, add parser/corpus/production planning regressions, and verify a
  fresh real execution/Diff/preview flow using the original comma wording.

1.3 verified locally: 227 parser/planning tests, 85/85 authored corpus cases with
0 unsafe rule executions among 56 negatives, and real Codex run
`12f2b4d5-a42d-4307-b28e-9b7ef7cfe605` using the original failed sentence.
Version-bound check/build/3 smoke tests and 4 heading checks passed; browser
rendered the expected heading. Adjacent batch: 123/124 passed, one temporary
PermissionError retained and its isolated rerun passed. Model QA was not run.
See [comma-verification.md](comma-verification.md).

- [x] 1.1 Implement shared decision/evidence, conservative rule boundaries and routing enforcement; verify negation, questions, quoted/code input, multi-action and missing/oversized slots through parsers and production planning, preserve supported demo/direct/group/LLM paths, run the frozen offline corpus and relevant regressions, and document results and limitations.

Verified locally: authored corpus 73/73; same 49 negative parser cases 23 baseline
matches versus 0 current; final API regression 448 and adjacent context/selection/
provider contract 45 passed; root check, final API syntax, strict specification and
whitespace checks. No real-provider/browser/remote-CI claim. See
docs/intent-boundaries-review.md and docs/evidence/intent-boundaries/.

- [x] 1.2 Fix the exact-commit CI regression for native multi-file/coordinated group planning: allow planner-required groups only after a validated native plan, keep unavailable/failed/non-task plans from persisting detached tasks, reproduce both workflow failures and verify negative controls before delivery.

Verified locally: routing/group/recognition 260 passed; workflow evaluation/native
QA/scoring 53 passed, including both failed complete workflows; API syntax and
strict specification passed. First remote failure retained in ci-followup.json;
follow-up remote result must be checked against the pushed fix commit.
