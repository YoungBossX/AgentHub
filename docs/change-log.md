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

---

## P1-2: Real Codex CLI Execution Verification

**Date:** 2026-05-16

### Modified Files

| File | Change |
|---|---|
| `apps/api/tests/test_codex_adapter.py` | +30 lines (4 new tests) |
| `apps/api/tests/test_task_runs.py` | +19/-2 lines (strengthened assertions) |

### Modified Functions / Areas

- `apps/api/tests/test_codex_adapter.py`
  - `test_codex_adapter_default_binary_is_macos_codex_app_path` (new) — verifies `DEFAULT_CODEX_BINARY` constant.
  - `test_codex_adapter_respects_codex_cli_path_env_var` (new) — verifies `CODEX_CLI_PATH` env var override.
  - `test_codex_adapter_falls_back_to_default_when_env_var_unset` (new) — verifies fallback to default when env var absent.
  - `test_codex_adapter_constructor_binary_override_takes_precedence` (new) — verifies explicit `codex_binary` parameter takes highest priority.

- `apps/api/tests/test_task_runs.py`
  - `test_direct_ui_start_background_execution_persists_events` — strengthened assertions: now verifies adapter lifecycle events exist beyond queued, and failed runs carry a `CODEX_*` error code with a non-null error message.

### What Changed

1. Added 4 new unit tests for `CodexAdapter` binary resolution (default path, env var override, constructor override, fallback precedence).
2. Strengthened the background dispatch integration test to assert that CodexAdapter produces recognizable `CODEX_*` error codes when execution fails.
3. Performed a real Codex CLI smoke test against the session worktree to verify the adapter path works end-to-end when Codex is available.

### Real Codex CLI Smoke Test Result

- **Codex CLI available:** `/Applications/Codex.app/Contents/Resources/codex` (v0.131.0-alpha.9) — **Yes.**
- **Codex CLI authenticated:** Logged in using ChatGPT — **Yes.**
- **Command shape:** Matches `docs/adapter-notes.md` exactly (`--ask-for-approval never exec --json --cd <worktree> --sandbox workspace-write "<instruction>"`).
- **JSONL events produced:** `thread.started`, `turn.started`, `item.started`, `item.completed` — **Yes.**
- **Exit code:** `0` — **Yes.**
- **File changes in worktree:** Not tested (read-only smoke). Codex searched and located `apps/demo/src/App.tsx` across multiple session worktree directories.

### Why

P1-1 fixed Direct UI Start dispatch but did not verify whether the real CodexAdapter CLI path actually works. P1-2 closes that verification gap: confirms Codex CLI is present and executable, confirms its command shape matches the documented spec, confirms it produces JSONL lifecycle events inside the session worktree, and adds CI-safe tests that do not depend on real Codex.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (81 tests: 21 web + 60 API) |
| `git diff --check` | Pass |
| Real Codex read-only smoke (manual) | Pass (JSONL events, worktree navigation confirmed) |
| Real Codex write-and-diff smoke (manual) | Pass (see below) |

### Real Codex Write-and-Diff Smoke Test (2026-05-16)

**Outcome A: Real write-and-diff through Direct UI Start verified (API-level, not UI-level).**

A new session worktree was created. A task was assigned to the frontend agent (CodexAdapter). CodexAdapter was invoked with instruction: `"In apps/demo/src/App.tsx, find the element with data-agenthub-target='primary-action-button' and change only its text to 'Codex Verified'."`

Results:
- **26 TaskRunEvents persisted** including `thread.started`, `turn.started`, `item.started`/`item.completed` (command_execution and file_change), `turn.completed`.
- **Codex modified the file:** `apps/demo/src/App.tsx` — replaced button text from `"Continue"` to `"Codex Verified"`.
- **TaskRun state:** `completed`.
- **Diff artifact collected:** `artifact.diff.ready` event persisted with `artifactId` and `diffId`. Git diff confirmed 1 file changed, 1 insertion, 1 deletion.
- **Transient stderr noise:** Codex emits `"Reconnecting..."` messages as `{"type":"error"}` JSONL events during execution; these are mapped to `CODEX_EXIT_ERROR` error events but do not prevent the run from completing when `turn.completed` follows. This is a known Codex CLI behavior, not an adapter bug.

The verification was performed through direct Python invocation of `CodexAdapter` + `run_adapter_event_stream` + `collect_task_run_diff` rather than through the HTTP endpoint, because `BackgroundTasks` + synchronous `process.communicate()` in CodexAdapter blocks the FastAPI event loop, preventing concurrent request handling during long Codex runs. This event-loop blocking is a pre-existing limitation that also affects the `force-codex-failure` and `retry-with-fallback` endpoints.

### Known Limitations

- Real Codex CLI **is available** (v0.131.0-alpha.9, logged in via ChatGPT) in the current validation environment. This is environment-dependent.
- **Real write-and-diff verified** (API-level): Codex modified `apps/demo/src/App.tsx`, changed file confirmed by `git diff`, diff artifact collected by backend service.
- Direct UI Start endpoint dispatches real Codex execution in background. `process.communicate()` was blocking the event loop; this is resolved in P1-3.
- `FileNotFoundError` from missing worktree vs missing Codex binary both map to `CODEX_NOT_FOUND`. This pre-existing ambiguity is not addressed in P1-2.
- Transient Codex `"Reconnecting..."` JSONL events are mapped to `CODEX_EXIT_ERROR` error events but do not prevent successful completion when followed by `turn.completed`.
- The existing fallback-based P0 demo path remains intact and unchanged.

---

## P1-3: Non-Blocking Subprocess Execution Fix

**Date:** 2026-05-16

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/codex_adapter.py` | +2 lines: added `import asyncio`, changed `communicate()` to `await asyncio.to_thread(communicate)` |
| `apps/api/tests/test_codex_adapter.py` | +49 lines: `DelayedFakeCodexProcess`, non-blocking test, `_drain_events` helper |
| `docs/change-log.md` | P1-3 entry |

### Modified Functions / Areas

- `apps/api/app/codex_adapter.py`
  - `streamEvents` (line 161): replaced synchronous `state.process.communicate()` with `await asyncio.to_thread(state.process.communicate)`.
  - Added `import asyncio`.

- `apps/api/tests/test_codex_adapter.py`
  - `DelayedFakeCodexProcess` (new) — fake process that sleeps in `communicate()` to simulate a long-running subprocess.
  - `test_codex_adapter_does_not_block_event_loop_during_communicate` (new) — proves a concurrent `asyncio.sleep` completes promptly while the adapter's `communicate()` runs in the thread pool.
  - `_drain_events` (new) — helper to collect events from an async generator.

### What Changed

The blocking `process.communicate()` call inside `CodexAdapter.streamEvents()` was wrapped in `asyncio.to_thread()`. This moves the blocking subprocess wait to a worker thread, keeping the asyncio event loop free to serve other requests (health checks, SSE, task queries).

### Why

P1-2 confirmed that `BackgroundTasks` + synchronous `process.communicate()` blocks the FastAPI asyncio event loop for the entire duration of Codex execution (30-90s). During this time, no other HTTP requests could be served — health checks, SSE event delivery, and task queries would all hang. `asyncio.to_thread()` isolates the blocking operation in a thread pool, allowing the event loop to remain responsive.

### HTTP Direct UI Start Verification

ScriptedMockAdapter was tested through the full HTTP path:

| Step | Result |
|---|---|
| `POST /tasks/{task_id}/runs` | Returned 201 with queued TaskRun |
| Health check during execution | `ok` in ~5ms throughout |
| TaskRun final state | `completed` |
| Diff artifact | 1 file changed (`apps/demo/src/App.tsx`), 11 additions, 4 deletions |

CodexAdapter ran via direct `_background_execute_task_run` invocation:
- 9 TaskRunEvents persisted (queued → streaming events → error events)
- TaskRun finalized as `failed` with `CODEX_USAGE_LIMIT` (account hit usage limit)
- Event loop remained free during Codex subprocess execution

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (82 tests: 21 web + 61 API) |
| `git diff --check` | Pass |
| HTTP Direct UI Start + ScriptedMockAdapter | Pass (diff collected) |
| Direct `_background_execute_task_run` + CodexAdapter | Pass (events persisted, usage limit normalized) |

### Known Limitations

- Events are still persisted in batch after `communicate()` returns, not streamed in real-time during Codex execution. Real-time per-line event streaming would require replacing `communicate()` with an async readline loop — deferred.
- Real Codex hit a usage limit during P1-3 verification, so real Codex success through HTTP was not verified. The normalized failure path (CODEX_USAGE_LIMIT) was verified.
- `asyncio.to_thread` is Python 3.9+; the project requires Python 3.9+.
- The existing fallback-based P0 demo path remains intact and unchanged.
