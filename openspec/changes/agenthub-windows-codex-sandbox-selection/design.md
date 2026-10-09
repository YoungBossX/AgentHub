# Design

Only on sys.platform == win32, prepend the exact global options
`-c windows.sandbox="unelevated"` immediately after the configured Codex executable.
Keep never approval, exec/json, assigned --cd, workspace-write, ephemeral,
ignore-user-config, ignore-rules, and the instruction delimiter unchanged.
On other platforms preserve the original command.

The central guardrail recognizes the 17-token shape only on Windows with the
exact fixed prefix, then validates the remaining original 15-token shape and
assigned working directory. It does not accept arbitrary TOML configuration,
extra roots, network flags, duplicate options or bypasses. The original bounded
command remains recognized for compatibility; this adds no unbounded variant.

Use a fresh external directory with normal inherited permissions for live
acceptance, as the benchmark runner already does. Do not modify historic fixtures
or repair arbitrary directory ACLs. Keep the prior 0/3 reports byte-for-byte.
First run one real task, then a fresh three-case suite if that succeeds. Record
source/input hashes, Provider events, scope, immutable evaluators, real Diff,
completionValidation and independent functional results separately. No successful
minimum probe or nonempty patch alone is full benchmark acceptance.
