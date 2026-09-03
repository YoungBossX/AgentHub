## Finding boundary

Every TaskRunEvent is committed to SQLite before `publish_event` notifies local
subscribers. The notification currently schedules `queue.put_nowait(event)` on
an unbounded asyncio queue. The stream discards the queue item and immediately
queries SQLite, proving that the ORM event payload is retained only by mistake.

The same stream calls `list_session_events(...).all()` for initial backlog and
every live replay. A slow consumer suspends the async generator at `yield`, so
the remaining list and any incoming queue items stay resident until the client
continues or disconnects.

The invariant is that one subscriber's application-layer live state must not
grow with the number of events produced while it is slow. SQLite remains the
source of truth, and all rows after the durable cursor must still be delivered
in order when the consumer resumes.

## Wake coalescing

Use a small queue-compatible wake object backed by `asyncio.Event`. A lock
protects a single pending bit across publisher threads. The first publish marks
the wake pending and schedules `Event.set` on the subscriber loop; later
publishes coalesce until the consumer acknowledges the wake. The callback and
wake carry no TaskRunEvent, so each subscriber retains at most one payload-free
signal and one outstanding callback.

If the loop closes during scheduling, clear the pending state and keep the
existing behavior of relying on durable replay. Subscriber removal remains in
the async context manager's `finally` block.

## Batched replay

Add an optional positive limit to the shared Session event query while leaving
its default behavior unchanged for existing internal callers. The SSE route
uses batches of 100 rows, advances the same `(created_at, id)` cursor after each
frame, and queries the next batch until the cycle's fixed high-water cursor is
reached. Rows committed after that snapshot remain for the next wake or poll.
Initial backlog, non-stream replay, local wake, and polling all use this helper.

This bounds retained replay objects by row count, not by byte size of an
individual persisted payload. It does not impose retention or truncate event
delivery.

## Compatibility

- Subscription still happens before initial backlog enumeration.
- SQLite order, standard `id:`/`data:` frames, payload schema, and cursor format
  do not change.
- Local events still wake immediately; missing/coalesced notifications remain
  recoverable through one-second fresh-transaction polling.
- Heartbeats remain payload-free comments after fifteen idle seconds.
- `Last-Event-ID`, per-Session browser cursors, native reconnect, and frontend
  single-flight refresh behavior do not change.

## Validation

Capture RED failures for an unbounded 1,000-event wake burst and unbounded
backlog query, then challenge continuous producers against a fixed replay
high-water cursor. Run the complete SSE backend suite, adjacent event producers,
the complete API suite, unchanged Web SSE tests, strict OpenSpec validation,
candidate whitespace checks, and one fresh independent read-only patch review.
