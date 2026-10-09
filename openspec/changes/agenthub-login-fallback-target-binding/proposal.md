# Bind demo login intents before fallback execution

## Why
Actual local startup acceptance found that direct frontend and deterministic group
login requests persist `demo_frontend_request`. Explicit ScriptedMock retry then
correctly rejects the unsupported target, despite the template being supported.
The older deterministic Orchestrator plan already binds `login_page`.

## What Changes
Recognize bounded demo login creation in the shared frontend-intent parser and
persist its structured target in direct assignments, which groups also reuse.
Keep specific follow-up intents and external/native planning boundaries. Verify
login failure/retry, real files/Diff/Preview, and same-Session button modification
through direct, group and Orchestrator routes without weakening adapter checks.

## Impact
One planner/fallback repair. No new adapter, schema, UI, dependency install,
deployment, scope expansion or rewrite of historical TaskRun snapshots.
