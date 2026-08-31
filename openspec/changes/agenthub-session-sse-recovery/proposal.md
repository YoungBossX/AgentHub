## Why

The local demo promises persisted `TaskRunEvent` SSE recovery, but the current
transport sends named SSE events while the workspace shell listens only through
`EventSource.onmessage`. In addition, event sequence numbers restart for each
TaskRun but are used as a Session-wide resume cursor. A first run can therefore
prevent a later run in the same Session from being delivered after reconnect.

## What changes

- Define a durable, Session-scoped SSE cursor from persisted TaskRunEvent
  creation time and ID while retaining the existing per-TaskRun sequence.
- Emit standard SSE message frames and preserve lifecycle types in the payload.
- Close the backlog/subscription race by registering the Session subscriber
  before reading persisted events and de-duplicating by cursor.
- Keep a separate browser cursor for each selected Session and allow native
  EventSource reconnects.
- Add focused backend and frontend regression tests.

## Impact

- Changes `apps/api/app/events.py`, the Session events endpoint, API client
  cursor handling, SQLite index maintenance, the workspace shell subscriber,
  and their tests.
- Preserves SQLite, SSE, local single-user scope, existing adapters, and
  TaskRunEvent as the sole persistent event support entity.
- Adds no column or support entity and requires no data migration; the existing
  table receives an idempotent `created_at` index.
- Does not add WebSocket, a new adapter, or platform scope.
