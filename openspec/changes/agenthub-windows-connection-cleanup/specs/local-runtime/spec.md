## ADDED Requirements

### Requirement: A reset connection cannot strand completed transport cleanup
The local API SHALL finish the known Windows Proactor socket-shutdown cleanup
failure without treating other failures as harmless or changing Agent execution.

#### Scenario: A peer reset interrupts the standard-library cleanup callback
- **WHEN** the exact closing callback raises WinError 10054 at socket.shutdown
- **THEN** the socket and its server registration are released exactly once
- **AND** normal API lifespan and owned preview cleanup can finish
- **AND** recovery is recorded without repeating protocol callbacks

#### Scenario: Unrelated exception or unsupported runtime shape
- **WHEN** the platform, loop, callback, error, traceback or cleanup state does not match
- **THEN** the existing exception handler receives the failure
- **AND** no speculative transport or task state mutation occurs

#### Scenario: API lifecycle ends
- **WHEN** startup or normal shutdown completes or fails
- **THEN** handler ownership is restored without replacing another owner's newer handler
- **AND** persisted messages, results and worktrees remain available after restart
