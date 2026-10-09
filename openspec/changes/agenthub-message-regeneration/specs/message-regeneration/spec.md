## ADDED Requirements

### Requirement: Regenerated responses retain their authoritative source
The local workbench SHALL allow an eligible reply/plan to reprocess its original
request and a settled current group summary to regenerate only its interpretation.

#### Scenario: User regenerates a reply or plan
- **WHEN** the user confirms regeneration of a complete response with settled source work
- **THEN** the server appends a source-bound request using the original text, context and attachments
- **AND** current planning/execution safety gates apply without rewriting old results
- **AND** the UI explains current-state execution and displays source and progress

#### Scenario: User regenerates a group summary
- **WHEN** the current settled summary is regenerated
- **THEN** the existing coordinator produces a new fenced interpretation of evidence
- **AND** no coding task is rerun

### Requirement: Repeated or interrupted preparation is observable and bounded
Regeneration SHALL preserve durable operation identity and reject invalid or
concurrent source work without bypassing task or summary ownership.

#### Scenario: Duplicate request or network response loss
- **WHEN** the same operation ID is submitted again for the same source
- **THEN** the existing operation is returned without another dispatch
- **AND** foreign or mismatched operation IDs are rejected

#### Scenario: Failure or API restart during preparation
- **WHEN** preparation fails or is interrupted by restart
- **THEN** the persisted operation displays failure and retains any partial evidence
- **AND** model execution is not automatically resumed

#### Scenario: Session changes during an outstanding request
- **WHEN** the user switches Session before the response arrives
- **THEN** the operation stays in its source Session and does not replace the selected Session's messages
