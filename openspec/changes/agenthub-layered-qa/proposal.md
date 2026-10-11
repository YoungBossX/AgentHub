# Layered QA evidence

Rule reports and model verdicts currently share a generic passed badge. Add an
explicit, server-owned QA snapshot separating deterministic rules, native model
assessment, and recorded check/test/build results. Preserve existing execution
permissions, native review selection, and local preview/fallback behavior.

## Impact
Review metadata/API, task evidence, group summary inputs and review UI. No new
database entity, dependency, adapter, automatic provider call or command runner.
