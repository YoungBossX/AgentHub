## ADDED Requirements

### Requirement: Preserve a consistent offline workspace
The maintenance tool SHALL preserve SQLite and owned Git worktree state in a verified local snapshot without overwriting existing data.

#### Scenario: Runtime or source changes during capture
- **WHEN** the API owns the database, execution is active or captured files change
- **THEN** snapshot completion is refused and no complete manifest is published.

#### Scenario: Restore rehearsal
- **WHEN** an intact snapshot is restored into a new isolated destination
- **THEN** SQLite integrity, bytes, heads, index state and captured files are checked without changing original paths or executing saved project code.

### Requirement: Require explicit bounded cleanup
Cleanup SHALL preview and revalidate reference-free fixed caches before moving them into an owned quarantine.

#### Scenario: Preview becomes stale
- **WHEN** a cache, database reference or worktree ownership changes before apply
- **THEN** apply is refused without silently broadening the selected paths.
