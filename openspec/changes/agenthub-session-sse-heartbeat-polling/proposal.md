## Why

Session SSE currently uses an in-memory queue as the only live wake-up path.
Persisted replay makes reconnect safe, but an event committed by another API
worker, or a lost local wake-up with no later event, can leave an already-open
stream idle until the browser reconnects. The stream also emits no keep-alive
traffic, so an idle connection can be closed by an intermediary without an
application-visible event.

## What changes

- Keep the in-process subscriber queue as the low-latency fast path.
- Periodically re-read SQLite after the last durable Session cursor so events
  committed by another process or without a wake-up are delivered with bounded
  delay.
- Emit standard SSE comment heartbeats while the stream is otherwise idle.
- Add focused backend regressions for notification-free persisted delivery and
  heartbeat framing.

## Impact

- Changes only the Session SSE route, focused tests, and current documentation.
- Preserves SQLite as the persistent source of truth and adds no support entity,
  migration, external broker, WebSocket, adapter, or frontend protocol change.
- Adds one small indexed replay query per active Session stream per polling
  interval in the local single-user baseline.
