## Rehearsal boundary

The rehearsal uses a fresh Git repository outside AgentHub and registers it as
an explicit external frontend target. The target contains a minimal existing
Vite React app and grants only the files required by that app. The user request
asks for one exact copy change in one file. The real local Codex CLI runs with
network disabled through `CodexAdapter`; ScriptedMock fallback cannot satisfy
this task.

The AgentHub API uses a fresh rehearsal-only SQLite database. P18c memory rules
are inserted through the existing memory service before session creation, then
the session snapshot is explicitly refreshed after target registration. The
rehearsal records the resulting memory item IDs, snapshot ID, instruction
hashes, context-pack hash, target registry version, and runtime configuration
version.

On Windows the provider health probe resolves the signed application binary as
`codex.exe`. The command guard previously compared the basename only with
`codex`, so the probe could report healthy while adapter launch was guaranteed
to fail closed. The compatibility rule accepts only the exact case-normalized
basenames `codex` and `codex.exe`; names such as `codex-wrapper.exe` remain
outside the allowlist. All arguments, sandbox flags, scope checks, and network
restrictions remain unchanged.

The Preview artifact continues to record the portable allowlisted command
`pnpm dev --host 127.0.0.1 --port <port>`. Immediately before process creation,
Windows resolves only an exact `pnpm` executable token to `pnpm.cmd` using the
sanitized Preview PATH. The resolved launcher path is not accepted for any
lookalike command and does not alter the recorded evidence, child working
directory, environment filtering, health checks, or process lifecycle.

The Windows `pnpm.cmd` shim can spawn Vite and esbuild below its wrapper
process. Stopping only the wrapper leaves those descendants serving and holding
the target directory after the Preview row says `stopped`. The Windows stop
path therefore terminates the tracked PID and its process tree before closing
and deleting the runner-owned temporary log. Other platforms retain the direct
terminate/wait/kill sequence.

## Success evidence

A successful rehearsal requires all of the following from the same TaskRun:

- the public message path creates and schedules the external-target task;
- the selected adapter/provider is `codex` / `local-codex-cli`;
- the persisted TaskRun reaches `completed` after final scope validation;
- the provider stream contains terminal completion evidence;
- the generated Diff lists the exact bounded changed files;
- the generated Review is persisted;
- a public API Preview becomes healthy, is stopped, and leaves no target-bound
  process or runner-owned temporary log;
- no AgentHub platform file is changed by the provider.

Instruction SHA-256 is computed over the exact UTF-8 instruction supplied to
the adapter. Patch SHA-256 is computed over the exact persisted UTF-8 patch.
Historical decoder-recovered P18c evidence remains historical and is not
upgraded into a successful run.

## Delivery gate

After evidence is written, all available project tests and checks, strict
OpenSpec validation, UTF-8 validation, Markdown relative-link validation, and
Git whitespace checks must pass. The final audit lists every modified and
untracked file intended for the delivery commit and excludes databases,
credentials, provider logs, external rehearsal repositories, caches,
`node_modules`, and worktree metadata.
