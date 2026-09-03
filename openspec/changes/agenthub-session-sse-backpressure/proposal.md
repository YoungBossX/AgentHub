## Why

The Session SSE transport treats its in-memory queue as a wake-up hint, but the
queue is currently unbounded and stores a complete `TaskRunEvent` for every
publish. A slow or stalled client can therefore retain an ever-growing copy of
durable events. Reconnect and live replay also materialize every row after the
cursor in one `.all()` result, so bounding only the queue would leave backlog
memory proportional to Session history.

## What changes

- Replace per-event queueing with one payload-free, thread-safe, coalescing wake
  state per active Session subscriber.
- Prevent producer threads from scheduling more than one outstanding event-loop
  wake callback per subscriber.
- Replay persisted Session events in fixed-size cursor batches while preserving
  complete ordered delivery, with one fixed high-water cursor per replay cycle
  so continuous producers cannot keep a one-shot replay open forever.
- Add focused regressions for burst publishing, payload-free wakeups, bounded
  replay, subscription cleanup, ordering, polling, and heartbeat compatibility.

## Out of scope

- Capping or deleting persisted TaskRunEvent history.
- Limiting the byte size of one persisted event payload.
- Adding a broker, WebSocket, distributed event bus, or multi-host semantics.
- Changing browser EventSource behavior, cursor format, polling interval,
  heartbeat interval, producer commit order, or frontend refresh logic.
- Final candidate-set audit, cleanup, commit, or push.
