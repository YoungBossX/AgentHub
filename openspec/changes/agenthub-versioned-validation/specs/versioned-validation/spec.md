## ADDED Requirements

### Requirement: Validation executes trusted commands on a frozen copy
The system SHALL automatically run the supported Vite demo validation profile
before completing a supported Agent run, without granting shell tools to agents.

#### Scenario: Successful validation
- **WHEN** supported source passes type check, build and build-output smoke tests
- **THEN** actual exit codes and bounded logs are persisted with source and policy fingerprints
- **AND** matching rule and native model approval may establish configured checks passed.

#### Scenario: Unsupported or failed validation
- **WHEN** configuration is unsupported, dependencies are missing, a command fails, or execution times out
- **THEN** validation is explicitly unavailable or failed and cannot establish acceptance
- **AND** a failed build cannot use old build output to pass tests.

### Requirement: Only current complete evidence establishes acceptance
The system SHALL reject stale, interrupted, unrelated or manually submitted
receipts as proof of current source validation.

#### Scenario: Edit or policy change
- **WHEN** source, test harness, configuration or dependency lock changes
- **THEN** the current report is shown as expired or unverifiable
- **AND** its historical snapshot remains unchanged.

#### Scenario: Cancellation or restart
- **WHEN** execution is cancelled, ownership is lost or a running receipt survives restart
- **THEN** no success is inferred and subprocesses are cleaned up on normal cancellation.
