## ADDED Requirements

### Requirement: Reversible session organization
The system SHALL persist Session pins and archive state without changing
execution state, scope, worktrees, history or run snapshot identity.

#### Scenario: Pin, archive and restore
- **WHEN** a user pins, archives or restores a session
- **THEN** active/archive lists and ordering reflect the stored metadata after
  refresh and restart, and all prior records and worktrees remain available

#### Scenario: Organizing during execution
- **WHEN** organization actions occur while a provider is running
- **THEN** those actions do not invalidate the run or change its execution scope

### Requirement: Persistent key-message pins
The system SHALL let a user pin/unpin an existing message within its Session
and jump from a key-message list to the original conversation bubble.

#### Scenario: Message boundaries and recovery
- **WHEN** a user pins a message and reloads the session
- **THEN** the same message is pinned and its content/lineage are unchanged;
  foreign-session message updates and invalid inputs are rejected

#### Scenario: Legacy database upgrade
- **WHEN** the local app opens a pre-feature SQLite database
- **THEN** an idempotent additive upgrade preserves existing data and initializes
  all prior messages/sessions as unpinned and unarchived
