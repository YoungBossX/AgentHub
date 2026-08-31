## Delivery loop

The in-memory Session subscriber remains a fast-path notification mechanism.
The streaming loop waits for either a queue item or a one-second timeout. After
either outcome it opens a fresh SQLite read transaction and replays rows strictly
after the last emitted `(created_at, id)` cursor. Queue arrival order and process
identity therefore do not determine correctness.

This is bounded-latency cross-process observation, not a distributed event bus.
It is intentionally implemented with the existing indexed SQLite replay query
because AgentHub remains a local single-user workspace. A later multi-host design
can replace the polling wake-up without changing the persisted cursor contract.

## Heartbeat

If no event frame has been emitted for fifteen seconds, the stream writes an SSE
comment frame (`: keep-alive`). Comments are ignored by `EventSource`, do not
invoke `onmessage`, and do not update `Last-Event-ID`. Any emitted event or
heartbeat resets the idle timer.

## Safety and load

- Polling only reads persisted TaskRunEvent rows through the existing Session
  cursor query and exposes no new data.
- The one-second interval bounds recovery latency while remaining proportionate
  to the local single-user baseline.
- The queue remains the normal low-latency path, so local event delivery does not
  wait for the poll interval.
- Heartbeats carry no task, provider, filesystem, or user payload.
