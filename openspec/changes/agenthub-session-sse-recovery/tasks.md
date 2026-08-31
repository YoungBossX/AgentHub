## 1. Session SSE recovery repair

- [x] 1.1 Add focused failing backend tests for standard SSE messages,
  cross-TaskRun Session resume, and backlog/subscriber de-duplication.
- [x] 1.2 Implement the durable Session cursor and race-free persisted SSE
  delivery without changing TaskRunEvent's per-run sequence semantics.
- [x] 1.3 Add focused failing frontend tests for per-Session cursors and
  non-closing EventSource error handling.
- [x] 1.4 Implement the minimal API client and workspace-shell subscriber
  changes required by those tests.
- [x] 1.5 Run focused backend/frontend tests, available project checks, and
  `openspec validate agenthub-session-sse-recovery --strict`.
- [x] 1.6 Update `docs/change-log.md` after code changes and mark this task
  complete only after verification.

> 2026-08-30 clean-baseline evidence: SSE-focused backend tests pass 22/22,
> focused web tests pass 46/46, full web tests pass 102/102, full API tests pass
> 1146 with 1 skipped, demo-api tests pass 5/5, `pnpm check` and strict OpenSpec
> validation pass. The independent review's cursor-order, cross-thread wake-up,
> and transient-refresh findings were fixed and covered by regressions.
