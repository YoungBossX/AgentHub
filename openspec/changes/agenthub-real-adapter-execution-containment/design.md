## Finding boundary

The affected sources are the command lists constructed by `CodexAdapter` and
`ClaudeCodeAdapter`. The sink is the subprocess start after
`evaluate_command()`. Before this change, the Codex branch accepted every command
whose basename was `codex` or `codex.exe`; the Claude branch checked output and
permission flags but did not require restricted execution.

The invariant is that a real provider CLI is executable only when its argv
retains AgentHub's complete containment profile. Executable-name recognition is
necessary but insufficient.

## Patch strategy

Keep the current provider-native approach and strengthen it at two layers. The
adapter builders emit the bounded arguments, and the central command guardrail
independently validates the exact security-relevant shape and binds Codex's
`--cd` value to the resolved runner working directory. Codex must use
`workspace-write`, `never` approval, its assigned `--cd`, and no bypass or extra
writable-root flags. Claude Code must use restricted mode, an explicit
file-only tool set, strict MCP configuration, non-persistent sessions, and its
existing budget and structured-output controls. Both commands terminate option
parsing before the instruction argument.

This deliberately fails closed on an older provider CLI that does not understand
the required arguments. Silently retrying without containment would recreate
the finding.

## Validation

Use RED/GREEN tests for both generated command lists and the central allowlist.
Cover missing, conflicting, and bypass arguments as well as the accepted runtime
shape. Then run the full guardrail and both real-adapter test modules, strict
OpenSpec validation, and an independent post-patch security review.
