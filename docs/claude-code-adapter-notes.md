# Claude Code Adapter Feasibility Notes

**Date:** 2026-05-17

These notes investigate whether a future `ClaudeCodeAdapter` could fit the
existing AgentHub adapter contract. This is documentation only. No adapter code,
backend behavior, frontend behavior, or file mutation was implemented.

## Current Adapter Architecture

AgentHub adapters implement `AgentAdapter` in `apps/api/app/adapters.py`:

- `getCapabilities`
- `createRun`
- `streamEvents`
- `interrupt`
- `approve`
- `collectArtifacts`
- `cleanup`

Adapter events are normalized to `AgentEvent` and persisted through
`run_adapter_event_stream` before SSE delivery. A future Claude adapter should
follow the same pattern as `CodexAdapter`:

1. Build a deterministic command from `AgentRunRequest`.
2. Start the subprocess inside `Session.worktreePath`.
3. Stream stdout incrementally where possible.
4. Map CLI events or text lines into normalized `AgentEvent` records.
5. Capture stderr separately.
6. Map startup failures, auth failures, usage limits, nonzero exits, and
   interruption to stable `TaskRun.errorCode` / `TaskRun.errorMessage` values.
7. Let the existing TaskRun lifecycle collect real git diffs after completion.

`ScriptedMockAdapter` remains the reliability fallback and should not be
replaced by a future Claude path.

## Local CLI Availability

Safe commands run:

```bash
which claude
claude --version
claude --help
claude -p --help
claude auth --help
claude auth status
```

Results:

- Binary: `/Users/luotianhang/.npm-global/bin/claude`
- Version: `2.1.143 (Claude Code)`
- Auth status command returned JSON:

```json
{
  "loggedIn": true,
  "authMethod": "api_key_helper",
  "apiProvider": "firstParty",
  "apiKeySource": "apiKeyHelper"
}
```

No real prompt execution, file mutation, or quota-consuming adapter rehearsal
was run.

## CLI Behavior Observed From Help

Claude Code starts an interactive session by default. Help text says to use
`-p` / `--print` for non-interactive output.

Relevant options:

- `-p, --print`: print response and exit.
- `prompt`: positional instruction argument.
- `--output-format text|json|stream-json`: machine-readable modes are available
  only with `--print`.
- `--include-partial-messages`: include partial chunks as they arrive, only with
  `--print --output-format=stream-json`.
- `--input-format text|stream-json`: text input is default; stream-json input is
  available only with `--print`.
- `--permission-mode default|acceptEdits|auto|dontAsk|plan|bypassPermissions`.
- `--allowedTools` / `--disallowedTools`: restrict built-in tools.
- `--tools`: specify available built-in tools, or `""` to disable all tools.
- `--add-dir`: allow access to additional directories.
- `--model`: select a model or alias.
- `--max-budget-usd`: cap API spend, only with `--print`.
- `--no-session-persistence`: disable session persistence, only with `--print`.
- `--session-id`: supply a session UUID.
- `--bare`: minimal mode that skips hooks, plugin sync, auto-memory, keychain
  reads, and `CLAUDE.md` auto-discovery. Its auth behavior is stricter.

The help output does not expose a direct `--cd` option like Codex. A future
adapter should set the subprocess `cwd` to `AgentRunRequest.worktree_path`.
`--add-dir <worktree>` can be considered if Claude needs explicit directory
allowance, but the primary cwd should be the session worktree.

## Tentative Command Shape

For a future write-capable AgentHub run, the most plausible command shape is:

```bash
claude \
  --print \
  --output-format stream-json \
  --include-partial-messages \
  --permission-mode dontAsk \
  --allowedTools "Read,Edit,MultiEdit" \
  --no-session-persistence \
  --max-budget-usd <small-budget> \
  "<instruction>"
```

Run this with subprocess `cwd=<session_worktree_path>`.

For a read-only or smoke preflight, a safer shape may be:

```bash
claude \
  --print \
  --output-format json \
  --tools "" \
  --no-session-persistence \
  "<read-only instruction>"
```

The read-only shape was not executed during this investigation to avoid
unnecessary Claude usage.

Open questions before implementation:

- Whether `--permission-mode dontAsk` allows edits automatically or requires
  pairing with specific allowed tools.
- Whether `--allowedTools "Read,Edit,MultiEdit"` is sufficient for the demo
  edits, or whether the CLI expects separate shell arguments instead of a comma
  string.
- Whether `--bare` is desirable. It reduces ambient project behavior but may
  require explicit auth settings because it skips keychain/OAuth access.

## Feasibility Matrix

| Capability | Feasibility | Evidence / Notes |
|---|---|---|
| Non-interactive execution | Appears feasible | Help explicitly says use `-p` / `--print` for non-interactive output. |
| Passing an instruction | Appears feasible | Help shows positional `[prompt]` / `prompt` argument. |
| Setting cwd/worktree | Feasible via subprocess cwd | No `--cd` option observed; adapter should run the process with `cwd=Session.worktreePath`. |
| Machine-readable output | Appears feasible | `--output-format json` and `--output-format stream-json` are documented for `--print`. |
| Auth failure detection | Partly feasible | `claude auth status` returns JSON with `loggedIn`. Need tests for unauthenticated/nonzero behavior. |
| Usage-limit detection | Unknown until real run | No quota-consuming command was run. Future adapter should parse stream-json errors, stderr, and nonzero exits for limit/rate strings. |
| Interruption | Feasible at process level | Future adapter can terminate the subprocess and mark the run interrupted from AgentHub state, like `CodexAdapter`. Need real-run behavior confirmation. |

## Expected Adapter Design

A future `ClaudeCodeAdapter` should be a sibling of `CodexAdapter`, not a
frontend or orchestration redesign.

Suggested implementation shape:

- `DEFAULT_CLAUDE_BINARY = "claude"` or an absolute discovered path with
  `CLAUDE_CODE_CLI_PATH` override.
- A small `ClaudeProcess` / `ClaudeProcessRunner` abstraction matching the
  existing Codex test pattern.
- `createRun` builds the command, evaluates command guardrails, sets
  subprocess cwd to the session worktree, and stores run state.
- `streamEvents` reads stdout incrementally. Prefer `stream-json` and map
  parseable event types to:
  - `task.state` for run start/progress
  - `message.delta` for partial assistant text or tool/progress messages
  - `completed` on successful terminal result
  - `error` on auth, usage-limit, parse, or nonzero-exit failures
- `interrupt` terminates the subprocess and emits/records a
  `CLAUDE_CODE_INTERRUPTED` failure from AgentHub state if the CLI does not
  emit a dedicated event.
- `collectArtifacts` can remain empty for P0/P1 parity; AgentHub already
  collects git diffs after successful runs.
- `cleanup` removes in-memory run state.

Suggested normalized error codes:

- `CLAUDE_CODE_NOT_FOUND`
- `CLAUDE_CODE_AUTH_REQUIRED`
- `CLAUDE_CODE_USAGE_LIMIT`
- `CLAUDE_CODE_GUARDRAIL_BLOCKED`
- `CLAUDE_CODE_STDOUT_PARSE_ERROR`
- `CLAUDE_CODE_INTERRUPTED`
- `CLAUDE_CODE_EXIT_ERROR`

## Risks and Unknowns

- Real `stream-json` shape was not captured. Implementation needs fake-process
  tests plus one approved smoke run before claiming live compatibility.
- Usage-limit and auth-required text patterns are unknown beyond the successful
  `auth status` JSON on this machine.
- Permission behavior needs a bounded write smoke. The CLI supports several
  permission modes, but this note does not prove which one is safest for
  unattended demo edits.
- Tool allowlist syntax should be verified with a non-mutating command before
  using it in a write-capable adapter.
- Claude Code may read project-local configuration unless `--bare`,
  `--setting-sources`, or explicit settings are used. A future adapter should
  decide whether to suppress ambient config for deterministic demo behavior.
- Cost/quota exposure should be bounded with `--max-budget-usd` where practical.
- No real file mutation was run, so this note does not claim the future adapter
  can complete the AgentHub demo.

## Recommendation

Non-interactive Claude Code execution appears feasible enough to justify a
future implementation spike, but it should start with a fake-process adapter
test suite and a read-only CLI smoke. A write-capable smoke should require an
explicit user approval and should run only inside a disposable session
worktree.
