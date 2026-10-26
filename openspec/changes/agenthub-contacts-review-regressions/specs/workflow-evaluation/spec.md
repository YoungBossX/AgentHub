## ADDED Requirements

### Requirement: Contacts review regression evidence
The developer evaluator SHALL support a separate opt-in contacts review contract
without relabeling historical v1-v3 receipts or changing adapter permissions.

#### Scenario: Server saved but response JSON is invalid
- **WHEN** the real backend returns 201 and the fixed harness corrupts its delivered JSON
- **THEN** the UI SHALL avoid reporting a failed save or automatically repeating POST
- **AND** it SHALL attempt GET reconciliation, displaying real stored results on success
- **AND** if that GET fails it SHALL preserve the known list with a neutral saved acknowledgement

#### Scenario: Initial list request fails
- **WHEN** the fixed harness injects an initial GET failure
- **THEN** the UI SHALL show a recoverable error without asserting a confirmed empty list

#### Scenario: Initial response arrives after a save
- **WHEN** an initial GET success or failure arrives after a newer save and refresh
- **THEN** the UI SHALL retain the saved state without restoring obsolete errors
- **AND** it MAY prevent editing during initial loading instead of allowing that race

#### Scenario: Corrective evidence is separate
- **WHEN** a copied generated case is repaired and reviewed
- **THEN** original source, data and historical verdicts SHALL remain unchanged
- **AND** new receipts SHALL identify the current source and independent corrective run
