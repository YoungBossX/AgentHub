## Why

The real coding adapters declare `network=off` and tell providers to stay inside
the assigned Session worktree, but the command allowlist does not enforce the
required provider-native containment flags. A future or alternate caller can
therefore launch a recognized Codex or Claude executable with weaker arguments
while still passing AgentHub's command guardrail.

Codex already requests its platform-native `workspace-write` sandbox, while the
installed Claude Code CLI exposes a restricted mode that removes shell, network,
and code-running tools and confines file tools to the working directory. These
boundaries need to be mandatory launch invariants rather than conventions.

## What changes

- Require the exact bounded Codex execution shape: non-interactive execution,
  `workspace-write`, the assigned working directory, and no sandbox-bypass or
  extra writable-root arguments.
- Run Claude Code in restricted and safe modes with an explicit file-tool set
  and no MCP configuration inherited from the host.
- Make the command guardrail reject either real adapter when any containment
  invariant is missing or conflicting.
- Prove accepted and rejected command shapes with focused regression tests.
- Terminate option parsing before every user-derived instruction so an
  instruction that starts with a dash cannot become a CLI flag.

## Out of scope

- Docker or a new sandbox runtime.
- Treating a replaced or malicious provider executable as trusted, a generic
  external OS/container wrapper, provider-endpoint network allowlisting, or a
  cross-platform process-tree kill-on-close implementation.
- Changing the ScriptedMockAdapter, planner, preview, deployment, or fallback
  behavior.
- Preview iframe sandboxing, generated-project dependency pinning, or SSE
  backpressure.
- Claiming that prompt instructions or post-run changed-file checks constitute
  process isolation.
