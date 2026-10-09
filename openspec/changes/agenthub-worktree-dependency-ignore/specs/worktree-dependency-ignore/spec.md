## ADDED Requirements

### Requirement: Setup dependency links do not create false dirty conflicts

The system SHALL exclude the fixed setup dependency paths node_modules and
apps/demo/node_modules from Git untracked status during server-owned Session
worktree initialization. It SHALL preserve existing Git exclude content and
verify repository ownership before modifying Git metadata. Repeated setup SHALL
be idempotent and SHALL NOT delete or replace existing dependency links.

#### Scenario: New or reused worktree has directory-only historical ignores

- **WHEN** a Session worktree uses a HEAD with node_modules/ and setup creates or
  reuses the two dependency symbolic links
- **THEN** Git status SHALL report no untracked setup dependency links
- **AND** an otherwise clean frontend task SHALL remain runnable
- **AND** setup SHALL retain the same links and assigned Session path on reuse

#### Scenario: Dirty source and protected paths remain guarded

- **WHEN** an unrelated source file becomes dirty or a protected dependency path changes
- **THEN** the ordinary dirty-conflict or protected-scope checks SHALL still reject it
- **AND** the repair SHALL NOT filter arbitrary files out of those checks or authorize
  adapters to edit node_modules or Git metadata

#### Scenario: Existing path belongs to another repository

- **WHEN** Session setup finds a Git worktree from a different repository
- **THEN** it SHALL fail without writing that repository's excludes or creating links

#### Scenario: Git environment or metadata redirects setup

- **WHEN** the host inherits a GIT_DIR override or the exclude file redirects to
  another file through a symbolic link or hard link
- **THEN** Git commands SHALL use the existing sanitized project environment
- **AND** redirected exclude files SHALL be rejected before appending rules
- **AND** unassigned repository or file contents SHALL remain unchanged
