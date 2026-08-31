## Cursor

`TaskRunEvent.sequence` remains a per-TaskRun ordering field. The SSE resume
cursor is the encoded `(created_at, id)` pair. Session queries order by those
same columns and return only rows strictly after the decoded pair.

New event timestamps are allocated after SQLite has granted the writer lock and
are made strictly greater than the largest persisted event timestamp. A
`created_at` index keeps that allocation and replay bounded for the local demo.
This makes the persisted pair monotonic across concurrent TaskRuns even when
the Windows clock returns duplicate values. Existing same-timestamp rows retain
ID as a deterministic legacy tie-breaker.

This preserves existing per-run event consumers and avoids adding a new SQLite
column to already-created local databases.

## Delivery

The Session endpoint creates an in-memory subscriber before enumerating the
persisted backlog. Queue items are wake-up signals only: every wake opens a fresh
read transaction and replays rows strictly newer than the last emitted cursor
in persisted order. Subscriber notifications use `call_soon_threadsafe`, because
synchronous FastAPI routes can publish from worker threads. A notification for
an item already included in the backlog is therefore harmless. Frames omit
`event:` so browser `onmessage` is the single compatible event handler;
`eventType` remains in JSON.

## Frontend

The workspace shell holds a Session-ID-to-cursor ref. The EventSource effect
depends on backend URL and selected Session, not on each received cursor. An
incoming standard message updates only the active Session's cursor and refreshes
its tasks through a single-flight, dirty-coalescing request. Transient refresh
failures use at most three exponential-backoff retries, and a newer event resets
that budget. Retry timers are cancelled when the selected Session changes.
`onerror` does not call `close()`, preserving native reconnect.

## Safety

Cursor parsing accepts only server-issued timestamps and UUID event IDs. Invalid
cursor input returns a client error. The change sends no additional secret,
filesystem, provider, or artifact data.
