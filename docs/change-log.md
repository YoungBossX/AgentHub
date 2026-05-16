# AgentHub Change Log

## P1-1: Direct UI Start TaskRun Dispatch Fix

**Date:** 2026-05-16

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/main.py` | +86/-3 lines |
| `apps/api/tests/test_task_runs.py` | +107 lines (3 new tests) |

### Modified Functions / Areas

- `apps/api/app/main.py`
  - `create_task_run_for_task` — changed from `def` to `async def`, added `BackgroundTasks` parameter, now dispatches `_background_execute_task_run` after creating the TaskRun.
  - `adapter_for_type` (new) — resolves `AgentAdapter` instance from adapter type string.
  - `execute_task_run` (new) — reusable helper that builds an `AgentRunRequest`, dispatches adapter execution via `run_adapter_event_stream`, and collects diff on completion.
  - `_background_execute_task_run` (new) — async background task that creates an independent DB session, resolves the adapter, calls `execute_task_run`, and normalizes unexpected failures to `failed` state with `ADAPTER_EXECUTION_ERROR`.

- `apps/api/tests/test_task_runs.py`
  - `test_direct_ui_start_dispatch_creates_queued_run_with_adapter_type` (new)
  - `test_direct_ui_start_background_execution_persists_events` (new)
  - `test_direct_ui_start_scripted_mock_background_execution_persists_events` (new)

### What Changed

`POST /tasks/{task_id}/runs` previously only created a `queued` TaskRun database row and returned immediately. No adapter execution was dispatched. The TaskRun remained stuck in `queued` state forever.

After this fix, the endpoint:
1. Creates the TaskRun in `queued` state (unchanged).
2. Dispatches `_background_execute_task_run` via FastAPI `BackgroundTasks`.
3. Returns the TaskRun response promptly.
4. The background task creates an independent DB session, resolves the appropriate adapter (`CodexAdapter` or `ScriptedMockAdapter`), and invokes the existing `execute_task_run` path.
5. TaskRunEvents are persisted, state transitions are applied, and diffs are collected on completion.
6. Unexpected adapter failures are normalized to `failed` state.

### Why

Direct UI Start was the only execution path that did not dispatch adapter execution. The working paths (`force-codex-failure` and `retry-with-fallback`) already called `run_adapter_event_stream` after creating the run. This fix unifies Direct UI Start with the existing dispatch pattern while using `BackgroundTasks` to avoid blocking the HTTP response on long-running adapter execution.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (77 tests: 21 web + 56 API) |
| `git diff --check` | Pass |

### Known Limitations

- Real Codex success was not tested because Codex CLI is not installed on this machine.
- This fix verifies Direct UI Start at the dispatch level (background execution is scheduled, adapter invocation is attempted, TaskRunEvents are persisted, failures are normalized).
- Full artifact generation (diff, preview, deploy) still depends on successful adapter execution against a real session worktree.
- The existing fallback-based P0 demo path (`Force Codex failure` → `Retry with ScriptedMockAdapter` → diff → preview → deploy) remains intact and unchanged.
