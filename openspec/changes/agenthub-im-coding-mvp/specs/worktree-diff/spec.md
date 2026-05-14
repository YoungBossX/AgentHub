## ADDED Requirements

### Requirement: Session worktree isolation for diffs
The system MUST collect diffs from the Session worktree used by all TaskRuns in that Session.

#### Scenario: Session changes remain isolated
- **GIVEN** two sessions exist for the same workspace repository
- **WHEN** both sessions run agent tasks
- **THEN** their file modifications occur in different session worktree paths
- **AND** their diffs are collected independently

### Requirement: Real git diff collection
The system MUST generate diffs from actual workspace changes using Git CLI and `git diff -p`.

#### Scenario: File changes become patch text
- **GIVEN** CodexAdapter or ScriptedMockAdapter modifies files in a session worktree
- **WHEN** the backend collects diff artifacts
- **THEN** it runs Git CLI in that session worktree
- **AND** stores patch text generated from real file changes

### Requirement: TaskRun diff refs
The system MUST record each TaskRun's `baseRef` before execution and use that TaskRun-specific boundary when collecting and storing diff artifacts.

#### Scenario: TaskRun records baseRef before execution
- **GIVEN** a TaskRun is about to start in a session worktree
- **WHEN** execution is queued
- **THEN** the system records `baseRef` from the current session worktree commit SHA or explicit git ref
- **AND** adapter execution starts only after the TaskRun-specific `baseRef` is stored

#### Scenario: Diff uses TaskRun-specific boundary
- **GIVEN** a TaskRun has recorded `baseRef`
- **WHEN** diff collection runs after adapter execution
- **THEN** the diff is generated from that TaskRun's `baseRef` using `git diff -p baseRef -- .` or equivalent semantics
- **AND** the Diff record stores the TaskRun's base and head refs

#### Scenario: Follow-up run gets independent diff boundary
- **GIVEN** a session already has completed TaskRuns in its session worktree
- **WHEN** a follow-up TaskRun starts in the same session
- **THEN** the follow-up TaskRun records a new `baseRef`
- **AND** its diff collection does not overwrite prior TaskRun diff refs or artifacts

### Requirement: Changed files and stats
The system MUST collect changed files and diff stats alongside patch text.

#### Scenario: Diff card receives summary data
- **GIVEN** a session worktree has modified files
- **WHEN** diff collection completes
- **THEN** the Diff record contains `changedFilesJson` and `statsJson`
- **AND** the UI can render a changed files list and patch summary

### Requirement: Protected generated dependencies
The system MUST exclude `node_modules` from diff collection and protect it from agent edits.

#### Scenario: node_modules is present in demo repo
- **GIVEN** Vite React dependencies were installed during setup
- **WHEN** diff collection runs or an adapter proposes edits
- **THEN** `node_modules` is not included in diff artifacts
- **AND** agent edits to `node_modules` are blocked by protected path rules

### Requirement: Expandable diff inspection
The system MUST let the user expand a diff card and inspect file-level changes.

#### Scenario: User opens a diff card
- **GIVEN** a diff artifact exists
- **WHEN** the user expands the diff card
- **THEN** the UI shows file-level changes
- **AND** detailed changes can be inspected through Monaco Diff Editor or an equivalent Monaco-based diff view

### Requirement: Optional patch validation
The system SHOULD support `git apply --check` for generated patch validation when it is safe and useful.

#### Scenario: Patch validation runs
- **GIVEN** a patch has been generated
- **WHEN** patch validation is enabled
- **THEN** the backend runs `git apply --check` without mutating the worktree
- **AND** stores or reports the validation result
