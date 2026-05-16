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

---

## P1-4: Incremental Codex JSONL Streaming

**Date:** 2026-05-16

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/codex_adapter.py` | Replaced whole-process stdout collection with incremental stdout JSONL line streaming and concurrent stderr capture. |
| `apps/api/tests/test_codex_adapter.py` | Added streaming process fakes and tests for incremental event yield, pre-completion persistence, and event-loop responsiveness. |
| `docs/change-log.md` | Added this P1-4 entry. |

### Modified Functions / Areas

- `apps/api/app/codex_adapter.py`
  - `CodexProcess` — now exposes `stdout_lines()`, `wait()`, and `stderr_text()` instead of a whole-process `communicate()` contract.
  - `SubprocessCodexProcess.stdout_lines` — reads stdout one line at a time with `asyncio.to_thread(stdout.readline)`.
  - `SubprocessCodexProcess.stderr_text` — drains stderr concurrently while stdout is streamed.
  - `CodexAdapter.streamEvents` — parses each complete JSONL stdout line as soon as it is available, yields mapped `AgentEvent`s immediately, then handles stderr and exit status after the process completes.
  - `_finish_process` — waits for process completion and returns the normalized stderr excerpt.

- `apps/api/tests/test_codex_adapter.py`
  - `StepwiseFakeCodexProcess` — fake process that pauses after the first JSONL line so tests can prove events are yielded before process completion.
  - `test_codex_adapter_streams_jsonl_before_process_completion` — verifies the first mapped event is yielded before the fake process has waited/exited.
  - `test_codex_streamed_events_persist_before_process_completion` — verifies `run_adapter_event_stream` persists the first TaskRunEvent before process completion.
  - `test_codex_adapter_does_not_block_event_loop_while_waiting_for_jsonl` — verifies unrelated async tasks can run while Codex stdout is waiting.

### What Changed

Before P1-4, `CodexAdapter.streamEvents()` used:

```python
stdout, stderr = await asyncio.to_thread(state.process.communicate)
```

That kept the FastAPI event loop responsive, but it still collected all stdout
after Codex exited. TaskRunEvents were parsed and persisted in a batch at the
end of the subprocess run.

After P1-4, the adapter streams stdout incrementally:

1. Start stderr capture concurrently.
2. Await each stdout JSONL line as it becomes available.
3. Parse the line immediately.
4. Map it to an `AgentEvent`.
5. Yield the event immediately to `run_adapter_event_stream`.
6. Let `run_adapter_event_stream` persist the event before SSE delivery.
7. After stdout closes, wait for process completion and handle stderr/exit code.

### Why

P1-3 solved event-loop blocking, but not realtime visibility. The UI/SSE path
could remain responsive, but it could not observe Codex progress until the
process finished. P1-4 makes Codex JSONL stdout a true stream so persisted
TaskRunEvents can appear while Codex is still running.

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_codex_adapter.py` | Pass (14 tests) |
| `pnpm check` | Pass |
| `pnpm test` | Pass (84 tests: 21 web + 63 API) |
| `git diff --check` | Pass |

### Manual Verification Result

HTTP Direct Start with real Codex was attempted against a new planned frontend
task:

- Session: `62919139-e820-47d0-9557-ae7653740082`
- TaskRun: `360e7781-a3cf-4692-bf7f-67f5447c0f36`
- Initial state: `queued`
- Observed state during execution: `streaming`
- Health checks during execution: `ok` in 1-9ms
- Persisted event replay lines: 12
- Final state: `failed`
- Normalized error code: `CODEX_EXIT_ERROR`
- Normalized error message:
  `Reconnecting... 2/5 (timeout waiting for child process to exit)`
- Diff artifact: not produced

This verifies that HTTP Direct Start no longer remains stuck at `queued`, that
real Codex execution is attempted, that events/state become visible while Codex
is running, and that the API remains responsive. It does **not** verify HTTP
Direct Start -> real Codex file mutation -> diff artifact, because the real
Codex process failed before producing a successful file change.

### Known Limitations

- The adapter now streams Codex stdout incrementally, but real HTTP write-and-diff verification still depends on local Codex quota/auth/process stability.
- Stderr is captured concurrently and attached to final fallback/error handling, but mapped intermediate events may not include final stderr because they are emitted before process completion.
- Preview/deploy through a real Codex success path remains unverified unless the manual HTTP run reaches a successful file mutation and diff artifact.
- The existing fallback-based P0 demo path remains intact and must stay available.

---

## P1-5: Codex Reconnect Handling and HTTP Direct Start Diagnosis

**Date:** 2026-05-16

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/codex_adapter.py` | Treat Codex reconnect JSON events as informational progress, preserve specific Codex error codes when a later generic `turn.failed` arrives. |
| `apps/api/app/main.py` | Generate a bounded demo-file instruction for planned frontend login-page tasks instead of sending the broad task title to Codex. |
| `apps/api/tests/test_codex_adapter.py` | Added reconnect and specific-error preservation tests. |
| `apps/api/tests/test_task_runs.py` | Added a test for bounded frontend login-page run instructions. |
| `docs/change-log.md` | Added this P1-5 entry. |

### Modified Functions / Areas

- `apps/api/app/codex_adapter.py`
  - `_map_codex_json_event` — maps `Reconnecting... N/5 (timeout waiting for child process to exit)` JSON events to `message.delta` progress events instead of terminal errors.
  - `_is_reconnecting_error` (new) — detects reconnect progress messages from Codex JSON stdout.
  - `_is_generic_failure_event` (new) — detects generic `CODEX_EXIT_ERROR` / `Codex run failed.` events.
  - `CodexAdapter.streamEvents` — skips a later generic `turn.failed` error when a more specific Codex error was already emitted, so actionable errors such as `CODEX_USAGE_LIMIT` are not overwritten.

- `apps/api/app/main.py`
  - `instruction_for_task` (new) — converts the planned frontend login-page task into a small, explicit instruction targeting `apps/demo/src/App.tsx` and `data-agenthub-target="login-page-slot"`.
  - `agent_run_request_for` — now uses `instruction_for_task(task)` instead of the broad task title.

### What Changed

P1-4 showed HTTP Direct Start failed with:

```text
CODEX_EXIT_ERROR: Reconnecting... 2/5 (timeout waiting for child process to exit)
```

P1-5 found that this was an adapter mapping bug. Running the same Codex CLI
command manually showed that Codex can emit `Reconnecting... 5/5`, then log
`falling back to HTTP`, continue emitting normal item events, modify files, and
finish with `turn.completed`. The reconnect JSON event is therefore not
necessarily terminal.

The adapter now treats reconnect JSON events as progress messages. Real failure
comes from the process exit code, a non-reconnect Codex error, or a specific
Codex failure such as usage limit or authentication failure.

P1-5 also narrowed the HTTP Direct Start instruction. Previously the backend
sent only the task title, `Build the Vite React login page`, so Codex treated
the request like a broad OpenSpec implementation task and read large OpenSpec
files before touching the demo app. The backend now sends a bounded,
file-targeted instruction for the deterministic demo login-page task.

### Why

The direct Python write-and-diff smoke succeeded because it used a narrow file
edit instruction. HTTP Direct Start used a broad task title and also treated
Codex reconnect progress as terminal. Those differences made the HTTP path fail
before mutation/diff despite the CLI being capable of real file edits in the
same session worktree.

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_codex_adapter.py tests/test_task_runs.py` | Pass (29 tests) |
| `pnpm check` | Pass |
| `pnpm test` | Pass (89 tests: 21 web + 68 API) |
| `git diff --check` | Pass |

### Manual Verification Result

HTTP Direct Start with real Codex was attempted after the reconnect-mapping and
bounded-instruction fixes:

- Session: `1eac3075-ac06-4504-94f9-76dd4b17ad9d`
- TaskRun: `dac99e3d-2bb5-4f93-a31d-da9480c04ae6`
- Initial state: `queued`
- Observed state during execution: `streaming`
- Health checks during execution: `ok` in 1-5ms
- Persisted event replay lines: 27
- Final state: `failed`
- Final normalized error code: `CODEX_EXIT_ERROR`
- Final normalized error message: `Codex run failed.`
- Diff artifact: not produced

Inspecting persisted events showed the useful underlying error before the final
generic failure:

```text
CODEX_USAGE_LIMIT: You've hit your usage limit. To get more access now, send a request to your admin or try again at 10:02 PM.
```

After P1-5, tests ensure this specific `CODEX_USAGE_LIMIT` error is preserved
instead of being overwritten by a later generic `turn.failed` event.

The fallback path was also exercised in the same session after Codex failed:

- Retry with ScriptedMockAdapter: completed
- Diff artifact: produced
- Changed file: `apps/demo/src/App.tsx`
- Diff stats: 1 file changed, 11 additions, 4 deletions
- Preview: healthy at `http://127.0.0.1:64508`
- Deployment: mock provider, status `ready`

### Known Limitations

- HTTP Direct Start with real Codex file mutation and diff collection was not
  verified because the local Codex account hit a usage limit during the HTTP
  run.
- Manual CLI verification confirmed reconnect events can be followed by
  fallback-to-HTTP, file mutation, `git diff`, and `turn.completed`; the adapter
  now handles that event shape.
- Preview/deploy through a real Codex success path remains unverified until
  Codex quota permits a successful HTTP Direct Start mutation.
- The existing fallback-based P0 demo path remains intact and verified.

---

## P1-6: HTTP Direct Start Real Codex End-to-End Rehearsal

**Date:** 2026-05-16

### Modified Files

| File | Change |
|---|---|
| `docs/change-log.md` | Added this P1-6 rehearsal result. |

### What Changed

No product code was changed for P1-6. This was a focused rehearsal after the
P1-5 reconnect/error-handling fixes and after Codex usage limits reset.

### Manual Verification Result

HTTP Direct Start with real Codex was rehearsed through the backend API path
used by the UI:

- Session: `a0b51d27-0473-44f3-b079-bbb02fdf00bb`
- User request:
  `@orchestrator build a login page for the demo app`
- Codex-backed task: `f9e982c3-df76-4740-b38c-e14e8cb3497c`
- TaskRun: `fa23fb4a-6506-4b0e-a608-3197356d0628`
- Initial state: `queued`
- Observed state during execution: `streaming`
- Final state: `completed`
- Error code/message: none
- Persisted event replay lines: 84
- Health checks during execution: `ok` in 1-5ms
- Worktree:
  `.worktrees/98449267-914c-4f26-82b5-e1d176d64f91/a0b51d27-0473-44f3-b079-bbb02fdf00bb`

Real Codex changed:

```text
apps/demo/src/App.tsx
```

The collected diff artifact was persisted:

- Artifact ID: `782e16f4-36b5-46f3-86cf-42c3fb6119e9`
- Diff ID: `5df0273d-f9fc-46b3-bbfa-242d5d185667`
- Changed files: `["apps/demo/src/App.tsx"]`
- Stats: 1 file changed, 20 additions, 4 deletions

The file diff replaced the deterministic login-page slot copy with a compact
login form containing email and password fields. This verifies:

```text
HTTP Direct Start -> real Codex file mutation -> diff artifact
```

### Fallback Verification

The P1-6 direct Codex run completed, so fallback was not needed in this
rehearsal. P1-5 verified the fallback path immediately before this run:

- Retry with ScriptedMockAdapter completed.
- Diff artifact was produced for `apps/demo/src/App.tsx`.
- Preview became healthy.
- Mock deployment card was created.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (89 tests: 21 web + 68 API) |
| `git diff --check` | Pass |

### Known Limitations

- Preview and mock deploy were not triggered from the real Codex success run in
  this rehearsal. The verified P1-6 scope was real Codex mutation plus diff
  artifact.
- The Codex run took about 163 seconds and emitted reconnect progress before
  completion, so demos should still keep the ScriptedMockAdapter fallback
  available.

---

## P1-7: Real Codex Preview and Mock Deploy Rehearsal

**Date:** 2026-05-16

### Modified Files

| File | Change |
|---|---|
| `docs/change-log.md` | Added this P1-7 rehearsal result. |

### Modified Functions or Areas

No product code changed. This rehearsal used the existing preview and deploy
APIs after the successful real Codex Direct Start run from P1-6.

### What Changed

No backend, frontend, adapter, preview, or deploy implementation was changed.
The only change was documenting the focused verification result for continuing
from a real Codex diff artifact to preview and mock deployment.

### Why

P1-6 verified:

```text
HTTP Direct Start -> real Codex file mutation -> diff artifact
```

P1-7 verifies whether the existing artifact path can continue from that same
real Codex TaskRun to:

```text
healthy Vite preview -> mock deploy card
```

### Manual Verification Result

The rehearsal reused the successful real Codex Direct Start run from P1-6:

- Session: `a0b51d27-0473-44f3-b079-bbb02fdf00bb`
- Codex-backed task: `f9e982c3-df76-4740-b38c-e14e8cb3497c`
- TaskRun: `fa23fb4a-6506-4b0e-a608-3197356d0628`
- Changed file from real Codex: `apps/demo/src/App.tsx`
- Diff artifact ID: `782e16f4-36b5-46f3-86cf-42c3fb6119e9`
- Diff ID: `5df0273d-f9fc-46b3-bbfa-242d5d185667`

The existing preview API was called for that TaskRun:

```text
POST /task-runs/fa23fb4a-6506-4b0e-a608-3197356d0628/preview
```

Preview result:

- Preview ID: `877daf34-cabe-4ddf-8726-94677ba18831`
- Preview artifact ID: `a14d9194-b198-4d17-a152-79e71cc0590a`
- URL: `http://127.0.0.1:53089`
- Port: `53089`
- Command: `pnpm dev --host 127.0.0.1 --port 53089`
- Process ID: `32754`
- Health status: `healthy`
- Artifact status: `ready`

The preview URL served the Vite React HTML shell successfully.

The existing mock deploy API was called for the healthy preview:

```text
POST /previews/877daf34-cabe-4ddf-8726-94677ba18831/deploy
```

Deployment result:

- Deployment ID: `9ba427d9-1ea8-454a-8890-e243075fcec7`
- Deployment artifact ID: `a623f388-8891-4282-9f7d-6b0074a9152c`
- Provider: `mock`
- Environment: `preview`
- Status: `ready`
- Commit SHA/worktree ref:
  `9777b992c46ebb52150c19131410c3dfea54c268+worktree`
- URL:
  `https://mock.agenthub.local/deployments/9ba427d9-1ea8-454a-8890-e243075fcec7`
- Deploy log URI:
  `mock://deployments/9ba427d9-1ea8-454a-8890-e243075fcec7/logs`

This verifies:

```text
HTTP Direct Start -> real Codex file mutation -> diff artifact -> healthy Vite preview -> mock deploy
```

The preview and deployment records are backend-created and persisted. The
frontend already reads these persisted preview/deployment APIs, but this
P1-7 rehearsal used the backend API path directly rather than clicking through
the browser UI.

### Fallback Verification

The fallback path was not needed for this rehearsal because the real Codex run
from P1-6 had already completed and produced a diff. The fallback-based P0 demo
path remains covered by the existing tests and prior P1-5/P1-6 verification:

```text
forced Codex failure -> ScriptedMockAdapter fallback -> diff -> preview -> mock deploy
```

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (89 tests: 21 web + 68 API) |
| `git diff --check` | Pass |

### Known Limitations

- This P1-7 rehearsal triggered preview and deploy through the existing backend
  APIs, not by clicking the browser UI.
- Real Codex execution remains dependent on local Codex quota and CLI stability;
  keep the ScriptedMockAdapter fallback available for demos.
