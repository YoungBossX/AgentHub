## 1. Durable live SSE polling and heartbeat

- [x] 1.1 Add focused failing backend tests proving a persisted event is emitted
  without an in-process publish notification and an idle stream emits a comment
  heartbeat.
- [x] 1.2 Implement the queue-or-timeout replay loop and idle heartbeat without
  changing the durable cursor or frontend payload contract.
- [x] 1.3 Run focused backend tests, available project checks, and strict OpenSpec
  validation.
- [x] 1.4 Update current architecture, project state, and change log, then mark
  this task complete only after verification.

Verification record (2026-08-31): the focused SSE backend suite passed 22 tests,
the web suite passed 102 tests, the demo API passed 5 tests, `pnpm check` and
strict OpenSpec validation passed. The complete API suite passed 1,139 tests,
skipped 1, and retained 9 TaskRun-scope failures; all 9 failures reproduced at
unchanged baseline commit `d2b8f1b`, outside this SSE change.
