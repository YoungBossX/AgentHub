## ADDED Requirements

### Requirement: Pinned conversation references survive the recent window
The platform SHALL supply pinned messages from the current Session to freshly
prepared planner and execution requests even when they are older than the
recent-message window, within explicit deterministic context limits.

#### Scenario: Old pinned message
- **WHEN** a pinned message has more than eight newer conversation messages
- **THEN** its reference remains in canonical provider context
- **AND** unrelated Sessions are excluded and recent messages do not duplicate it

#### Scenario: Pin or unpin after a request
- **WHEN** a user changes pin state after a request has been prepared
- **THEN** later requests reflect the new selection
- **AND** saved earlier request snapshots and message contents remain unchanged

### Requirement: Bounded reference trust and evidence
Pinned content SHALL remain conversation reference without acquiring system
instruction, trusted memory or tool authorization status. The selector SHALL
filter protected values and expose deterministic limits and omission evidence.

#### Scenario: Oversized or numerous pinned messages
- **WHEN** pinned content exceeds the per-message, count or serialized budget
- **THEN** the selected payload stays bounded and partial or omitted content is explicit

#### Scenario: Actual execution
- **WHEN** an Agent uses a pinned reference in a newly prepared task
- **THEN** request evidence and output are checked independently of UI pin state
