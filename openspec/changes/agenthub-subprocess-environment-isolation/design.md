## Finding boundary

The source is the FastAPI process environment, which can contain planner and
coding-provider credentials. The affected sinks are `CodexAdapter`,
`ClaudeCodeAdapter`, the Claude CLI planner, the Vite preview runner, the staging
build runner, the local static-server child, and Codex/Claude CLI health probes.
These subprocesses either omit `env` or copy
`os.environ` and remove only `NODE`.

The invariant is that a child receives only the environment required by its
declared role. Project-controlled commands must receive no provider or AgentHub
control-plane secrets. A real coding adapter may receive only its own provider
credential/configuration variables. Sensitive values must not be persisted back
through adapter events, preview diagnostics, or deployment logs.

## Patch strategy

Introduce a small dependency-free environment-policy module. It builds a
portable runtime base from an explicit key allowlist, adds public frontend
prefixes for project processes, and adds a provider-specific allowlist for each
real adapter and the Claude CLI planner. Environment names are matched
case-insensitively so Windows cannot bypass the policy with alternate casing.

The same module recursively redacts exact sensitive environment values and
secret assignments. Apply it at evidence boundaries as defense in depth; do not
change public response shapes or silently convert an unsafe child environment
back to full inheritance.

Keep existing runner protocols unchanged so test fakes and service injection
remain compatible. Concrete subprocess runners construct the environment
internally.

Selected-provider credentials remain an explicit trusted CLI privilege because
environment-based CLI login is supported. Exact-value/assignment redaction is
defense in depth for accidental echoes; it does not claim to prevent a trusted
provider CLI from deliberately transforming or exfiltrating its own credential.

## Validation

Use RED/GREEN unit tests for profile separation, case-insensitive keys, public
frontend variables, Windows runtime variables, direct subprocess kwargs, and
nested evidence redaction. Then run the affected adapter, preview, deployment,
and event suites, owning API checks, strict OpenSpec validation, and candidate
whitespace/temporary-artifact checks.
