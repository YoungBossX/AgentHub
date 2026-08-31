# Session SSE Recovery

## ADDED Requirements

### Requirement: Browser-compatible persisted Session event frames

The system SHALL emit persisted `TaskRunEvent` values for Session SSE as
standard SSE `message` frames. Each frame SHALL provide a durable Session
cursor in both its `id:` field and JSON payload. The JSON payload SHALL retain
the event ID, TaskRun ID, lifecycle `eventType`, event payload, per-TaskRun
sequence, and creation time. The server SHALL NOT use the SSE `event:` field
for lifecycle types.

#### Scenario: A lifecycle event reaches EventSource.onmessage

- **WHEN** a TaskRun lifecycle event is encoded for a Session stream
- **THEN** its frame contains `id:` and `data:` lines without an `event:` line
- **AND THEN** the JSON payload contains `eventType` and a durable cursor.

### Requirement: Durable replay cursor is scoped to a Session

The system SHALL order Session replay by the persisted pair
`(TaskRunEvent.created_at, TaskRunEvent.id)`. The cursor SHALL be strictly
validated and SHALL resume only events after that pair. The existing
`TaskRunEvent.sequence` SHALL remain scoped to its TaskRun.

#### Scenario: A later TaskRun resumes after an earlier TaskRun cursor

- **GIVEN** two TaskRuns in the same Session whose first events both have
  per-TaskRun sequence `1`
- **WHEN** the client requests replay after the first TaskRun event cursor
- **THEN** the stream includes the second TaskRun event.

#### Scenario: An invalid cursor is rejected

- **WHEN** a client supplies a malformed Session replay cursor
- **THEN** the Session events endpoint responds with HTTP 400
- **AND THEN** it does not silently replay from the beginning.

### Requirement: Session stream reconnect and handoff are lossless within persisted evidence

The Session stream SHALL register its in-memory subscriber before enumerating
persisted backlog events and SHALL de-duplicate any overlap using the durable
cursor. A non-empty `Last-Event-ID` header SHALL take precedence over query
`after` before cursor validation, enabling native EventSource reconnect. New
persisted event cursors SHALL be monotonic across TaskRuns. Worker-thread
publish notifications SHALL wake the subscriber's event loop, and a live wake
SHALL replay fresh persisted rows in cursor order instead of trusting queue
arrival order.

#### Scenario: A boundary event is emitted once

- **GIVEN** an event is both persisted in the backlog and observed by the
  newly registered Session subscriber
- **WHEN** the stream begins delivery
- **THEN** the event is emitted once.

#### Scenario: Native EventSource reconnect takes precedence

- **GIVEN** a client provides a valid `Last-Event-ID` and a malformed query
  `after` value
- **WHEN** it reconnects to the Session events endpoint
- **THEN** the endpoint resumes after `Last-Event-ID`
- **AND THEN** it does not reject the unused query cursor.

#### Scenario: Reversed live notifications preserve persisted order

- **GIVEN** two committed events whose publish notifications arrive newest first
- **WHEN** the live Session stream handles those notifications
- **THEN** it replays both events once in persisted cursor order
- **AND THEN** its resume cursor does not skip the older committed event.

#### Scenario: A synchronous publisher wakes the async stream

- **GIVEN** a Session subscriber is awaiting a queue notification
- **WHEN** a synchronous worker thread publishes a persisted event
- **THEN** the subscriber event loop is notified thread-safely.

### Requirement: Workspace subscription state is isolated by Session

The workspace shell SHALL retain the last durable SSE cursor per Session. It
SHALL not recreate its EventSource after every received message, SHALL allow
native reconnect on connection error, and SHALL ignore late task-refresh
results after the subscribed Session is no longer active. It SHALL serialize
same-Session SSE refresh requests and retry a transient failure with bounded
backoff even when no later event arrives.

#### Scenario: Switching sessions does not reuse another cursor

- **GIVEN** Session A has received an SSE cursor
- **WHEN** the user switches to Session B and later returns to Session A
- **THEN** Session B opens without Session A's cursor
- **AND THEN** Session A resumes from its own cursor.

#### Scenario: A stale task refresh cannot overwrite the selected Session

- **GIVEN** an SSE-triggered task refresh for Session A is pending
- **WHEN** the user switches to Session B before that refresh settles
- **THEN** the Session A result does not update Session B tasks, errors, or
  artifact refresh state.

#### Scenario: A transient refresh failure does not strand terminal state

- **GIVEN** the workspace has accepted an SSE cursor for a terminal event
- **WHEN** the first task refresh fails transiently and no later event arrives
- **THEN** the workspace retries with bounded backoff
- **AND THEN** a later successful refresh updates the visible task timeline.
