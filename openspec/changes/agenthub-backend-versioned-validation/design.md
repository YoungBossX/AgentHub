# Fixed FastAPI profile

`fastapi-contract-v1` captures bounded, regular non-protected files beneath
`apps/demo-api`, hashes source plus Python/dependency/harness/environment policy,
and copies inputs into a disposable directory. Use the current installed Python
with isolated mode and no bytecode writes. Execute only a platform-owned harness:
syntax compilation and in-process FastAPI health/contact CRUD, input validation,
duplicate, CORS and OpenAPI regression contracts. Neither edited tests nor pytest
configuration from the target execute. New endpoints outside these contracts
remain unverified.

The harness starts with sanitized environment and an isolated home/temp directory.
Python audit checks reject network connections/listeners, subprocesses, dynamic
native loading, host file reads and writes outside a disposable data directory.
These guards reduce accidental side effects; Python audit hooks are not an OS
security sandbox and do not authorize arbitrary hostile repository execution.
Only the already supported built-in demo target is enabled.

Require structured complete check coverage and matching exit status. Recheck
source, policy and copied inputs after execution; cancellation, stale input,
missing dependencies, process failure, incomplete output or lost ownership cannot
publish acceptance. Reuse same-run/generation durable event and restart behavior.
Select freshness capture by verified Task target/profile; cross-profile receipts
fail closed. QA requires exactly the profile's required command kinds and labels
backend build not applicable. Existing frontend and unsupported targets retain
their behavior. No adapter permissions, deployment options or dependencies change.
