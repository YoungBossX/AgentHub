## ADDED Requirements

### Requirement: Maintain a frozen SQLite migration history
The platform SHALL use a fixed Alembic revision history as the sole schema mutation authority while retaining SQLite and SQLModel. Historical revisions SHALL NOT derive their operations from changing runtime models or seeds.

#### Scenario: Initialize an empty database
- **WHEN** an authorized initialization owns the exclusive database maintenance lease
- **THEN** the fixed revision creates the baseline schema and records its version only after successful validation.

#### Scenario: Inspect a missing database
- **WHEN** the developer runs migration status for a missing database
- **THEN** status reports its absence without creating a database or running schema mutations.

### Requirement: Adopt only recognized legacy schemas without losing data
Legacy adoption SHALL classify and validate the schema before mutation. It SHALL preserve all existing records, existing column values and attachment bytes, and SHALL NOT blindly stamp a revision.

#### Scenario: Upgrade a supported unversioned database
- **WHEN** a legacy database matches the documented compatibility contract
- **THEN** only fixed supported missing tables, columns and indexes are added, original values are verified, and the baseline version is recorded after validation.

#### Scenario: Encounter incompatible schema or duplicate unique values
- **WHEN** an existing database contains unknown revisions, incompatible structures or data that prevents a required unique index
- **THEN** the upgrade is refused before DDL without deleting, merging or rewriting records to force success.

### Requirement: Require offline exclusion and verifiable backup
Every schema upgrade of an existing database SHALL pass the controlled offline coordinator, acquire exclusive maintenance ownership, create a consistent verified SQLite backup including committed WAL content, and rehearse migration in an isolated copy before upgrading the original.

#### Scenario: The API is running
- **WHEN** an API process holds its shared lifetime lease
- **THEN** upgrade refuses without stopping the API, deleting its lease file or changing schema.

#### Scenario: Backup or rehearsal fails
- **WHEN** backup creation, integrity validation or isolated rehearsal fails
- **THEN** the original schema and revision are unchanged and no successful completion receipt is published.

#### Scenario: An in-place upgrade fails
- **WHEN** the original upgrade fails after additive DDL has begun
- **THEN** execution stops, the verified backup and failure stage remain available, the revision does not advance, partial state is recognizable for safe retry, and the source database is not automatically overwritten.

### Requirement: Preserve startup behavior without implicit legacy repair
API startup SHALL initialize only empty databases under exclusive ownership and verify current schemas under its shared lifetime lease before seeds, recovery and workers. Existing legacy or outdated schemas SHALL require explicit offline migration.

#### Scenario: A legacy database is opened by the API
- **WHEN** startup encounters a legacy or outdated schema
- **THEN** startup fails before seed and execution recovery, with an actionable offline migration instruction and no schema mutation.

#### Scenario: Competing initializers
- **WHEN** multiple processes initialize the same empty database
- **THEN** maintenance ownership prevents concurrent schema mutation and the serving process revalidates the schema after acquiring its shared lifetime lease.

### Requirement: Remove only superseded schema maintenance code
The change SHALL remove superseded runtime column/index repair implementations after replacement verification and preserve historical compatibility test cases through migration-level tests. It SHALL NOT prune user data or runtime artifacts.

#### Scenario: Cleanup after successful implementation validation
- **WHEN** the new migration path satisfies compatibility tests
- **THEN** obsolete implementation references are removed while database files, lease/WAL files, sessions, attachments, backups, worktrees and historical evidence remain untouched.
