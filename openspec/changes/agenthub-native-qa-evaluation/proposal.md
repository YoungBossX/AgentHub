# Same-version workflows with native QA

The current five-category runner defaults QA to ScriptedMock and only guards
individual cases after policy changes. Extend the existing isolated workflow
runner to evaluate native QA with immutable source/read/assessment provenance,
freeze a cohort identity and retain honest first-attempt/retry/elapsed statistics.
Run at least two fresh repetitions of all five categories on one frozen version.
Do not change product defaults, grant tools, install dependencies, use product
SQLite/worktrees, substitute mock results or require every model sample to pass.
