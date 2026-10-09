## ADDED Requirements

### Requirement: Write completion requires observed output
The server SHALL reject write TaskRuns without new scope-validated changes or a nonempty collected Diff before successful Review or downstream actions, and SHALL record bounded completion evidence. Read-only TaskRuns SHALL retain their existing completion path. Finalization SHALL preserve exact execution-generation ownership.

#### Scenario: Provider returns text only
- **WHEN** a write adapter completes without changing the assigned target
- **THEN** the TaskRun fails with a no-changes error and no successful Review or downstream delivery

#### Scenario: Preexisting dirty files
- **WHEN** the target already has a patch but this write attempt adds no changes
- **THEN** the TaskRun fails rather than attributing the old patch to this attempt

#### Scenario: Scoped output exists
- **WHEN** new changes pass scope validation and a nonempty Diff is collected
- **THEN** the TaskRun can complete with output evidence without implying functional acceptance

### Requirement: Native sandbox diagnosis preserves boundaries
Codex configuration SHALL retain workspace-write, assigned cwd, no approvals, ignored ambient config and network-off. Diagnostics SHALL preserve raw observed evidence and distinguish model assertions from executed file operations.

#### Scenario: Windows native sandbox selection
- **WHEN** a fixed native sandbox selection is verified on Windows
- **THEN** only that bounded platform setting is added without bypassing sandbox or loading user config
