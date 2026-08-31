# Change: Modularize oversized API and workspace source files

## Why

`apps/api/app/main.py`, `apps/api/app/planning.py`, and
`apps/web/src/components/workspace-shell.tsx` currently combine several
independent responsibilities. Their size makes route ownership, planning
boundaries, and UI state transitions harder to review without changing the
product behavior.

## What Changes

- Move coherent FastAPI route families and their response mappers out of
  `main.py` into dedicated router modules.
- Separate planning routing, intent helpers, and task builders behind the
  existing `plan_for_message` contract.
- Separate workspace-shell orchestration state from focused presentation and
  event-handling modules.
- Preserve all HTTP routes, response payloads, Planner decisions, SSE semantics,
  UI behavior, and current local-demo boundaries.

## Out of Scope

- New API behavior, database schema, migrations, adapters, or product features.
- WebSocket, Redis, background agents, or production deployment changes.
- Broad renaming or formatting unrelated to the extracted responsibility.
