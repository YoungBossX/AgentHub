## ADDED Requirements

### Requirement: Connect declared tools through actual MCP transport
The system SHALL expose selected read-only documentation tools through a real MCP
connection in supported Codex runs and show configured versus actual usage.

#### Scenario: Read documentation
- **WHEN** an enabled compatible Agent calls a selected document tool
- **THEN** the gateway verifies its current execution identity and returns only bounded assigned-target documentation with source hashes.

### Requirement: Preserve execution isolation and credential boundaries
The system SHALL bind ephemeral credentials to one execution and retain durable
call evidence without exposing credentials or broadening general tool permissions.

#### Scenario: Expiry, termination or restart
- **WHEN** credentials expire, a run terminates, ownership changes or API restarts
- **THEN** calls fail closed and cannot access another execution's documents.

#### Scenario: Disabled or incompatible connection
- **WHEN** the connection is disabled or the adapter is unsupported
- **THEN** the default execution path is preserved and no successful MCP use is fabricated.
