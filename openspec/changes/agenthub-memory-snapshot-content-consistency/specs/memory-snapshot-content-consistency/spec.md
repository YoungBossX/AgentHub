## ADDED Requirements

### Requirement: Immutable memory inputs
The system MUST preserve eligible memory content, item versions, retrieval metadata, and scoring time in each new snapshot.

#### Scenario: Live memory changes after a snapshot
- **WHEN** memory is edited, retired, replaced, deleted, or added after snapshot creation
- **THEN** the same snapshot, query, and filters MUST yield the same selected content and scores
- **AND** only an explicit refresh MUST expose the new collection to an existing Session

#### Scenario: Persistent and isolated snapshots
- **WHEN** a snapshot is reloaded from SQLite
- **THEN** retrieval MUST use its stored members and exact workspace boundary, including target and role filters
- **AND** an unscoped snapshot MUST NOT include another workspace's memories

### Requirement: Bound request evidence
The system MUST use the TaskRun-bound snapshot for coding and the original planner request for planning evidence.

#### Scenario: Session refresh after request preparation
- **WHEN** a Session changes snapshot after a request was prepared
- **THEN** its earlier TaskRun binding and planner evidence MUST retain the snapshot actually used

#### Scenario: Memory redaction before provider delivery
- **WHEN** protected content is removed from a selected memory
- **THEN** the receipt MUST identify the visible fields and visible content hashes without treating removed content as delivered
- **AND** coding evidence MUST be saved through the existing execution-lease fencing checks

### Requirement: Honest compatibility and integrity
The system MUST distinguish unavailable historical content from a verified frozen collection.

#### Scenario: Legacy snapshot has no frozen content
- **WHEN** an existing v1 snapshot is used
- **THEN** the system MUST expose legacy_unavailable and inject no fabricated historical memory
- **AND** explicit refresh MUST create a complete v2 snapshot

#### Scenario: Damaged or mismatched bound snapshot
- **WHEN** stored v2 content is invalid or a bound snapshot is missing or belongs to another workspace
- **THEN** request construction MUST fail without silently falling back to the current memory store
