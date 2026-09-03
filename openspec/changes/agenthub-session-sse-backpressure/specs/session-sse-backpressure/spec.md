# Session SSE Backpressure

## ADDED Requirements

### Requirement: Local Session wake state is payload-free and coalesced

AgentHub SHALL retain at most one pending local wake state and one outstanding
wake callback per active Session SSE subscriber. The wake SHALL NOT retain a
TaskRunEvent or its payload. Coalescing or losing a local wake SHALL NOT lose a
persisted event.

#### Scenario: A producer outpaces one Session client

- **GIVEN** an open Session stream that is not currently consuming wakeups
- **WHEN** many TaskRunEvents are committed and published in the same process
- **THEN** that subscriber retains one payload-free wake state
- **AND** producer threads do not enqueue one callback or ORM event per publish
- **AND** resuming the stream replays all committed rows from SQLite.

### Requirement: Session SSE replay retains a bounded row batch

AgentHub SHALL query persisted Session events after the durable cursor in a
fixed positive batch size. It SHALL advance the cursor and continue querying
through a fixed high-water cursor captured at the start of that replay cycle,
without duplication, reordering, or truncation. Rows committed after the
high-water cursor SHALL remain available to the next wake, poll, or request.

#### Scenario: A client resumes behind more than one replay batch

- **WHEN** more persisted events exist after the supplied Session cursor than
  fit in one batch
- **THEN** the stream queries and emits successive bounded batches
- **AND** every event is emitted once in persisted cursor order
- **AND** continuous producers cannot prevent that replay cycle from ending
- **AND** later rows are emitted by a subsequent replay cycle
- **AND** the public SSE frame and cursor contracts remain unchanged.

### Requirement: Existing recovery and idle behavior remains intact

The bounded transport SHALL preserve subscription-before-backlog ordering,
fresh-transaction cross-process polling, payload-free heartbeat comments, and
subscriber cleanup when the response iterator closes.

#### Scenario: A local notification is absent or the stream is idle

- **WHEN** another worker commits an event without a local wake
- **THEN** periodic SQLite replay still emits it after bounded delay
- **AND** an otherwise idle stream still emits the existing heartbeat comment
- **AND** closing the stream removes its in-process subscriber.
