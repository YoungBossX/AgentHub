## ADDED Requirements

### Requirement: Prepare explicit repairs from immutable review issues
The system SHALL let users select bounded issues from a Session-owned report and
prepare a repair draft with source and original-report provenance.

#### Scenario: Prepare without executing
- **WHEN** the user selects issues and prepares a draft
- **THEN** the draft records the original report and source version without creating tasks or writing target files.

#### Scenario: Stale, cross-session or forged selection
- **WHEN** source/report bindings no longer match or selection belongs elsewhere
- **THEN** preparation or sending fails without silently rebinding historical evidence.

### Requirement: Execute and revalidate within existing permissions
The system SHALL route explicitly sent repairs through existing task execution,
check source under write ownership and retain run/retry/result provenance.

#### Scenario: Repair output and current independent verification
- **WHEN** a repair changes source and current matching configured checks pass
- **THEN** the UI links the actual Diff/check receipts and only the specifically verified checks can be labeled recovered.

#### Scenario: Model opinion or later source changes
- **WHEN** only a model says passed or the source changes after validation
- **THEN** arbitrary findings remain unverified or their confirmation expires rather than being marked fixed.

### Requirement: Preserve explicit user verification and history
The system SHALL distinguish source-bound local-user confirmation from automatic
checks and retain original reports and prior decision history.

#### Scenario: Confirm and subsequently edit
- **WHEN** a user confirms a finding at a known version and files later change
- **THEN** the old confirmation remains historical and is not presented as current verification.
