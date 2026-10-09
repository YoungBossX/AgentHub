## ADDED Requirements

### Requirement: User edits are prepared from complete current source
The workbench SHALL allow editing complete current UTF-8 source and preparing a
bounded text Diff for a registered Session target without changing files yet.

#### Scenario: User edits code or supplies a text patch
- **WHEN** the user prepares changes to permitted target files
- **THEN** the server validates exact before content and returns a complete proposed difference
- **AND** historical Agent Diff fragments are not treated as complete files or blindly reapplied
- **AND** invalid paths, modes, binary data or malformed/conflicting hunks are rejected

### Requirement: Applying a prepared Diff is explicit and fenced
Application SHALL preserve canonical ownership, file versions and execution
exclusion, and persist a user-origin operation without fabricating Agent success.

#### Scenario: User applies a prepared operation
- **WHEN** the source versions and ownership still match and no execution conflicts exist
- **THEN** the bounded changes are applied and recorded as a user edit
- **AND** repeated delivery returns the existing operation result without another write

#### Scenario: Files change or application is interrupted
- **WHEN** expected content changes, a write fails, or the API stops during application
- **THEN** conflicting or partial results remain observable with original evidence
- **AND** recovery does not overwrite foreign changes or silently resume execution

### Requirement: Current results preserve authorship and validation truth
The workbench SHALL distinguish user-applied files from original Agent artifacts
and from test, review and preview validation evidence.

#### Scenario: User previews edited code or returns to it after restart
- **WHEN** the edited canonical files are viewed or previewed
- **THEN** the user revision and actual current result are visible
- **AND** prior Agent success or reviews are not claimed as validation of the edit
