## ADDED Requirements

### Requirement: Explain current work and next action
The workbench SHALL show state-grounded phase, blocker and an existing next action without equating completed execution or model opinion with acceptance.

#### Scenario: Work is waiting or failed
- **WHEN** a task needs approval, waits for a dependency or lock, or fails
- **THEN** the user sees a concrete explanation and an entry to the existing task controls.

### Requirement: Edit Skill references as bounded files
The workbench SHALL support relative-path/content controls and bounded UTF-8 import while retaining server validation and revision checks.

#### Scenario: Invalid path, duplicate or save conflict
- **WHEN** references are unsafe or the saved version changed
- **THEN** invalid content is not applied and the user's draft is retained with a clear explanation.

### Requirement: Bound long conversation work
The system SHALL bound initial retrieval and rendered history while allowing explicit access to older messages and preserving source ownership and realtime updates.

#### Scenario: Load older history while new messages arrive
- **WHEN** a user loads an older page during an SSE refresh
- **THEN** messages remain ordered and deduplicated, older data is not silently replaced and initial/rendering limits are respected.
