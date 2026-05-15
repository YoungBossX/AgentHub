# Adapter Notes

These notes belong to the OpenSpec change at
`openspec/changes/agenthub-im-coding-mvp`. Task 2.4 must read this file before
implementing `CodexAdapter`.

## Codex CLI Feasibility Spike

Date: 2026-05-14

Local CLI:

```bash
/Applications/Codex.app/Contents/Resources/codex
codex-cli 0.130.0-alpha.5
```

Login state observed:

```bash
codex login status
```

Output: logged in using ChatGPT. A logged-in CLI can still fail because of
usage limits.

## P0 Invocation Shape

Use `codex exec` in JSON event mode from the backend process, with the run
scoped to the assigned session worktree:

```bash
codex --ask-for-approval never exec --json --cd <session_worktree_path> --sandbox workspace-write "<instruction>"
```

Important flag placement:

- `--ask-for-approval` is a top-level `codex` option and must appear before
  `exec`.
- `--cd` is accepted by `codex exec` and should point at the session worktree.
- `--sandbox workspace-write` keeps writes scoped to the worktree sandbox.

The spike first tried placing `--ask-for-approval never` after `exec`; the CLI
rejected that command with exit code `2` and:

```text
error: unexpected argument '--ask-for-approval' found
```

## Working Directory Assumptions

`CodexAdapter` can launch the CLI from the backend process directory or repo
root as long as `--cd <session_worktree_path>` is supplied. The session
worktree should be a git worktree rooted at the AgentHub repo. Demo app edits
for P0 should target files under `apps/demo`.

For the spike, the current repo scaffold contained uncommitted files, so a
detached disposable git worktree alone did not contain `apps/demo`. The spike
copied the current working tree into the disposable worktree to exercise the CLI
against the demo app. Future session worktree creation should ensure the demo
app exists in the source ref before invoking Codex.

## Stdout Behavior

With `--json`, stdout is newline-delimited JSON events. The failed spike emitted
events like:

```jsonl
{"type":"thread.started","thread_id":"019e24b2-877a-7fb0-b1eb-390fd9612782"}
{"type":"turn.started"}
{"type":"error","message":"Reconnecting... 2/5 (timeout waiting for child process to exit)"}
{"type":"error","message":"You've hit your usage limit. To get more access now, send a request to your admin or try again at 2:42 PM."}
{"type":"turn.failed","error":{"message":"You've hit your usage limit. To get more access now, send a request to your admin or try again at 2:42 PM."}}
```

`CodexAdapter` should parse stdout as JSONL, persist useful lifecycle events,
and treat `turn.failed` as the canonical task failure signal when present.

## Stderr Behavior

Stderr is operational noise and diagnostics, not the primary event stream. The
spike saw:

- `Reading additional input from stdin...`
- plugin sync and connector warnings
- Cloudflare 403 HTML from plugin listing requests
- GitHub plugin sync timeout warnings
- stream disconnect retry messages
- `falling back to HTTP`
- shutdown MCP warnings

The adapter should capture stderr separately with a size limit and include a
short excerpt in normalized errors. It should not rely on stderr alone for
normal task state.

## Exit Code Behavior

Observed exit codes:

- `2`: CLI argument parsing failure.
- `1`: model/runtime failure after JSONL `turn.failed`, including usage limit.
- `1`: process interrupted with SIGINT during the probe.

A successful run was not observed because the account hit a usage limit during
the spike. P0 should treat exit code `0` plus expected file changes as success,
and any non-zero exit as failed or interrupted depending on the local run state.

## Interrupt Behavior

The interrupt probe started `codex exec --json`, waited briefly, then sent
SIGINT to the CLI process. Stdout contained only:

```jsonl
{"type":"thread.started","thread_id":"019e24b5-902b-7e93-b3ad-a52aeb9c0ac2"}
{"type":"turn.started"}
```

The process exited with code `1`. No explicit interrupted JSON event was
observed before exit. P0 should mark a run interrupted from AgentHub's own
interrupt request state after terminating the process or process group, rather
than waiting for a specific Codex JSON event.

## Known Failure Modes

- Missing `codex` binary.
- CLI is not logged in.
- Logged-in CLI hits a usage limit.
- `--ask-for-approval` is placed after `exec`.
- Network/plugin sync warnings create large stderr output.
- Stream disconnects and retry loops occur before failure.
- Disposable worktree is created from a ref that lacks current demo files.
- CLI exits non-zero without producing the expected file diff.
- JSONL stdout contains malformed or incomplete events after abrupt
  interruption.

## Fallback Trigger Conditions

P0 should offer or automatically select `ScriptedMockAdapter` fallback when any
of these conditions occur:

- `codex` is not found.
- `codex login status` fails or reports no usable login.
- `codex exec` exits non-zero.
- stdout includes `turn.failed` or an error matching usage limit/auth failure.
- the run times out or is interrupted.
- the run completes without expected changes in the session worktree.
- stdout cannot be parsed as JSONL.
- the requested action would touch protected paths or commands outside the P0
  allowlist.

Do not implement `CodexAdapter` or `ScriptedMockAdapter` in task 1.5. These
notes only define the local process assumptions for later implementation.

## Task 2.4 Manual CodexAdapter Smoke

On 2026-05-14, a task 2.4 manual smoke used the same command shape against a
disposable git worktree:

```bash
codex --ask-for-approval never exec --json --cd /Users/luotianhang/Desktop/agenthub/.worktrees/codex-smoke-2-4 --sandbox workspace-write "Inspect apps/demo/src/App.tsx and do not edit files. Reply with a short status line."
```

Observed behavior:

- Running from the default sandbox failed before model execution because the
  Codex app could not write its local state database and could not initialize
  its in-process app-server client.
- Running with normal local app permissions succeeded.
- stdout emitted JSONL lifecycle events including `thread.started`,
  `turn.started`, `item.started`, `item.completed`, an `agent_message`, and
  `turn.completed`.
- stderr remained noisy, including plugin sync warnings, Cloudflare/GitHub
  network diagnostics, stream disconnected retry notices, telemetry warnings,
  and shutdown MCP warnings.
- The process exited with code `0`.
- The disposable worktree had no file changes after the read-only smoke.

This confirms the task 2.4 adapter command shape can execute locally when the
Codex CLI is available and the process has access to the user's Codex app state.
