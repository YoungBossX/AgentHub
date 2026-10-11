## ADDED Requirements

### Requirement: QA separates execution from acceptance
The system SHALL persist deterministic rule, model, and command evidence
independently for each new review, with server-owned acceptance status.

#### Scenario: Scripted report passes
- **WHEN** deterministic checks pass without a native review or tests
- **THEN** the report shows model not run and tests not run
- **AND** QA remains incomplete even if the execution completed.

#### Scenario: Model cannot override failed checks
- **WHEN** a model reports passed and deterministic rules or command evidence fail
- **THEN** the combined QA result is blocked and preserves both source verdicts.
- **AND** the existing local staging gate refuses the blocked result.

#### Scenario: Recorded command is not version-bound acceptance
- **WHEN** same-run configured command evidence reports success
- **THEN** its command kind, exit code and artifact source remain visible
- **AND** lack of file-version binding prevents a full acceptance claim.

### Requirement: QA evidence remains scoped and durable
The system SHALL preserve review-time evidence through API reloads and events.

#### Scenario: Other or later evidence exists
- **WHEN** another run has passed tests or new receipts arrive after a report
- **THEN** the existing report is not upgraded using those receipts.

#### Scenario: Legacy report is opened
- **WHEN** a report has no layered QA snapshot
- **THEN** the UI shows incomplete historical evidence without manufacturing checks.
