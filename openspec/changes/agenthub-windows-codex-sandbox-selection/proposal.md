# Select a verified Windows native sandbox for Codex

## Why
AgentHub ignores user Codex configuration to preserve containment. On the current
Windows CLI this also omits the native sandbox selection and tool creation is
blocked. A fresh normal-permission fixture succeeded with only the explicit
unelevated selection, but AgentHub's exact command allowlist rejects that argv.
Owner-only temporary fixtures separately fail ACL checks and must not be used
to infer that all workspaces are inaccessible.

## What Changes
- Emit a fixed Windows-only native sandbox selection while retaining the full
  existing workspace-write command and sanitized process environment.
- Accept only that exact prefix in the command guardrail on Windows; reject
  other config keys, values, positions, duplicate flags and widened access.
- Verify adapter/security regressions and fresh real coding cases; preserve
  historical failures and write-completion gates.

## Impact
One runtime repair task. No user-config loading, full-access fallback, manual
host ACL changes, sandbox setup, dependencies, new adapters or UI changes.
Unelevated uses restricted-token/ACL isolation and weaker network isolation than
elevated. This does not claim an elevated sandbox or hostile-code isolation.
