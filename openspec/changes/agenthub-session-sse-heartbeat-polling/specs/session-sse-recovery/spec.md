# Session SSE Polling and Heartbeat

## ADDED Requirements

### Requirement: Open Session streams observe persisted events without a local wake-up

The Session SSE stream SHALL periodically query persisted events strictly after
its last durable Session cursor while it remains open. An in-process subscriber
notification MAY trigger the same query earlier, but correctness SHALL NOT
depend on a notification arriving in the same process.

#### Scenario: Another process commits an event

- **GIVEN** an open Session stream has emitted its persisted backlog
- **WHEN** a TaskRunEvent for that Session is committed without publishing to
  the stream's in-memory subscriber queue
- **THEN** the stream emits the event after a bounded polling delay
- **AND THEN** it advances through the same durable Session cursor contract.

### Requirement: Idle Session streams emit payload-free heartbeats

The Session SSE stream SHALL emit a standard SSE comment heartbeat after a
bounded idle interval. The heartbeat SHALL contain no TaskRun or user payload,
SHALL NOT be encoded as an event, and SHALL NOT advance the durable cursor.

#### Scenario: An idle stream remains observable

- **GIVEN** an open Session stream has no newer persisted events
- **WHEN** the heartbeat interval elapses
- **THEN** the stream emits an SSE comment frame
- **AND THEN** browser `EventSource.onmessage` receives no application event and
  its `Last-Event-ID` remains unchanged.
