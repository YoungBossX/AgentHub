# Bind the deterministic login plan to its registered demo target

## Why
The login-page chat fallback displays a target inferred from its planned files,
but persists no targetId or safeTarget on its frontend and QA tasks. The current
execution scope gate correctly rejects the writing run before adapter launch.

## What Changes
- Resolve the existing built-in demo frontend target when constructing the login
  plan and persist explicit target bindings for frontend execution and QA review.
- Keep the three-step serial plan, existing adapters, source-only write policy,
  and fail-closed scope/lock checks.
- Verify HTTP planning persistence and an isolated ScriptedMock execution with
  actual files, scope evidence and nonempty Diff.

## Impact
One planner repair task. No changes to worktree dependency links, historical
tasks, schema, providers, UI, Preview/deployment or dependency installation.
