## ADDED Requirements

### Requirement: Enforce declared relationships on every application connection
Every SQLite application connection SHALL enable and verify foreign key enforcement before transactions. Runtime operations SHALL NOT disable enforcement, synthesize missing parent records or introduce cascade deletion to bypass violations.

#### Scenario: A child references a missing parent
- **WHEN** a write inserts or updates a child to reference a nonexistent parent
- **THEN** the database rejects the write and the transaction does not publish successful state or events.

#### Scenario: A new pooled connection is opened
- **WHEN** the application opens another physical SQLite connection
- **THEN** enforcement is enabled on that connection independently of previously opened connections.

### Requirement: Upgrade supported historical structures without rewriting records
A fixed revision following immutable v1 SHALL add the TaskRun event unique index and restore missing foreign keys only for recognized historical structures. Existing database upgrades SHALL require offline exclusive maintenance, a verified WAL-aware external backup, isolated rehearsal and old-value and BLOB preservation verification.

#### Scenario: A supported historical table lacks a foreign key
- **WHEN** the offline upgrade identifies a recognized missing relationship with valid data
- **THEN** it restores the constraint through the controlled migration, verifies every existing field value and attachment byte, and records the new revision only after validation.

#### Scenario: Existing data prevents enforcement
- **WHEN** expected relationships contain orphan references or events contain duplicate or invalid sequence values
- **THEN** upgrade refuses without deleting, merging, renumbering or silently repairing records.

#### Scenario: The database already has complete relationships
- **WHEN** the recognized v1 database contains all required foreign keys
- **THEN** the upgrade preserves its tables without unnecessary rebuilds while adding the required index and revision.

#### Scenario: Rebuilding a legacy table fails
- **WHEN** table copying, replacement or validation fails during the controlled transaction
- **THEN** the transaction is rolled back, the verified backup and failure stage remain available, and no successful upgrade or automatic source overwrite is reported.

### Requirement: Allocate event order within the owning write transaction
Event sequence allocation SHALL acquire a database write guard before reading the maximum sequence. A unique index SHALL enforce task_run_id and sequence uniqueness. Staging SHALL NOT commit or discard its caller's transaction, and notifications SHALL occur only after commit.

#### Scenario: Independent writers append events for the same TaskRun
- **WHEN** independent connections or processes append events in bounded competing transactions
- **THEN** successful events have distinct increasing TaskRun-local sequences and matching committed state, with no silent event loss.

#### Scenario: A staged event is rolled back
- **WHEN** the caller rolls back the transaction containing state and staged events
- **THEN** neither the state change nor the events are persisted or notified.

#### Scenario: A prior read snapshot cannot become a writer
- **WHEN** lock acquisition times out or the transaction cannot upgrade its snapshot
- **THEN** failure is explicit and bounded, no partial success is reported, and only a safely replayable complete database transaction may be retried without repeating external side effects.

### Requirement: Preserve durable SSE replay semantics
The change SHALL retain the existing timestamp and UUID cursor format and allocate timestamps while the write guard is held through transaction completion. It SHALL preserve historical event identifiers, sequence values, timestamps and payloads.

#### Scenario: Different TaskRuns commit interleaved events
- **WHEN** a client resumes from an existing cursor and reads bounded pages
- **THEN** all committed subsequent events in that Session can be replayed once in cursor order, including concurrent TaskRun events.

### Requirement: Keep verification and cleanup outside user data
New test databases, backups, temporary copies and receipts SHALL reside under E:\Docker. Cleanup SHALL be limited to verified superseded code and owned inactive temporary artifacts after replacement validation, preserving immutable migration history, user records, managed worktrees and historical evidence.

#### Scenario: An artifact's ownership or active use is uncertain
- **WHEN** cleanup cannot prove that an artifact is owned, inactive and within the intended temporary directory
- **THEN** it is retained rather than deleted by a broad path prefix or Docker prune operation.
