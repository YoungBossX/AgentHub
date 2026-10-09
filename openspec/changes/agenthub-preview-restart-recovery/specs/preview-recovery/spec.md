## ADDED Requirements

### Requirement: Bounded Preview process ownership
The system SHALL distinguish tracked process exit from unknown ownership and
signal only preview processes created by the current runner.

#### Scenario: API restarts or exits
- **WHEN** the API gracefully exits or reads a Preview from an earlier instance
- **THEN** its owned subprocesses are cleaned up on exit and unknown PIDs are
  neither adopted nor signaled; persisted records retain accurate diagnostics

### Requirement: Explicit one-click Preview recovery
The system SHALL use fresh backend health for explicit refresh/restart, retain
old artifacts and apply the existing delivery/scope gates to new previews.

#### Scenario: Cached healthy selection is no longer healthy
- **WHEN** the selected Preview looks healthy locally but a refresh discovers
  no healthy Preview for the run
- **THEN** one explicit action creates and selects a fresh owned Preview without
  creating new TaskRuns, altering source files or deleting historical results

#### Scenario: OS allocates a browser restricted port or artifact reads arrive separately
- **WHEN** a default high-port candidate is occupied or a partial artifact list arrives before the new Preview
- **THEN** allocation retries within a fixed bound for a port at least 16384, fails clearly on exhaustion, and the explicit Preview selection survives partial refreshes
