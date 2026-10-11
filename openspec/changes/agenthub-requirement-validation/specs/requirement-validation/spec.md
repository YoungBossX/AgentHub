## ADDED Requirements

### Requirement: Validate supported requirements through real interaction
The system SHALL validate supported demo login and text-change contracts in a
fresh browser against the bound output and retain named acceptance evidence.

#### Scenario: Login form
- **WHEN** a login-page task produces a form
- **THEN** desktop and narrow browser checks verify labeled editable inputs, empty and invalid-email rejection, and valid submission
- **AND** no authentication or external network request is performed.

#### Scenario: Literal copy change
- **WHEN** a supported heading or button-copy task is validated
- **THEN** the visible text must match the frozen expected text
- **AND** the primary button must be clickable for a button-copy task.

### Requirement: Fail closed on absent or stale acceptance evidence
The system SHALL preserve source, policy and requirement provenance without
turning skipped or historical checks into requirement acceptance.

#### Scenario: Missing runtime or unsupported task
- **WHEN** the browser is unavailable or the structured requirement is unsupported
- **THEN** requirement coverage is explicitly unavailable or not configured, never passed.

#### Scenario: Changed requirement or source
- **WHEN** source, requirement contract or harness policy changes
- **THEN** previous acceptance is expired or unverifiable on read without changing its stored snapshot.
