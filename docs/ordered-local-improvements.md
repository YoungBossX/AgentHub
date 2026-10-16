# Ordered local improvements

User objective, 2026-10-16: complete all three items below, in order. Existing
uncommitted local work is the baseline; no commit/push, production deployment,
dependency installation or interruption of existing product runs is included.

| Order | Required end state and authoritative evidence | State |
| --- | --- | --- |
| 1. Real task evaluation | At least ten fresh same-source/policy samples over all five existing workflow categories (repeat counts explicitly reported); actual native Planner/coding/QA with bound full-file review evidence, no scripted fallback counted as native; first-attempt/final outcomes, all retries and per-role/workflow elapsed time. Freeze cohort identity, invalidate mixed-source aggregates, retain failed/unattempted cases and distinguish test doubles. Native QA must actually be observed, not merely configured. | Complete locally: ten frozen samples, first 4/10, final 6/10; natural 4/8, injected 2/2 with two retries, ten verified native QA attempts. Four failures retained; 37 final focused tests after separately documented reporting correction. See `native-qa-evaluation-review.md` |
| 2. Business acceptance | Add explicit independent backend and frontend/integration business contracts beyond the existing fixed happy paths; prove positive and realistic negative controls using source-bound receipts and trusted harnesses. Preserve existing P0 paths, scope and no arbitrary target test execution. Describe exact covered/uncovered behavior. | Complete locally: 70 final business/backend tests, 53 workflow and 55 adjacent QA regressions (overlap); actual 13 syntax/API groups plus legacy ten/resilience eighteen browser checks with dual-source/policy receipts. Exact covered/uncovered behavior in `business-contract-coverage-review.md` |
| 3. Maintainability | Extract cohesive execution-engine and task-card responsibilities into focused modules/components; reduce the large entrypoints without duplicating logic or changing runtime behavior. Preserve ownership/lease/state transitions, scope/approval/fallback, artifact provenance and UI controls; verify meaningful existing safety/state and UI regressions, then reconcile current docs. | Complete locally: independent ownership core and task-card data/plan/artifact modules; source equivalence, 548 lifecycle/safety tests plus one POSIX-only skip, 139 adjacent, Web 326 and lint/types/root/strict checks. See `execution-card-modularity-review.md`; no product runtime/remote delivery claim |

Do not mark the overall goal complete after item 1, a prepared report, a green
fixture run or a plan for later items. Every item needs current source and actual
verification. A same-version cohort is identified by loaded implementation/input/
harness fingerprints, not HEAD alone; repeated fixed scenarios are not distinct
business tasks or a general model-success estimate.

All three scoped items are complete locally on 2026-10-16. Frozen native-QA evidence remains historical after subsequent policy/refactor changes; no failed sample was replaced. Other product debt, real Provider uncertainty, context compaction and production delivery are not claimed resolved.

Subsequent delivery authorization, 2026-10-16: the user requested committing and pushing the accumulated completed work to the current `codex/local-workspace-improvements` branch. This is separate from the original local-only validation scope. Actual commit/remote/CI state must be read from Git/GitHub.
