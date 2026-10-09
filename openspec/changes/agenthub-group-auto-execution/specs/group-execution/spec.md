## ADDED Requirements

### Requirement: Automatic bounded group execution
The system SHALL automatically dispatch newly validated explicit group tasks
using the existing runtime and dependency gates unless the request explicitly
selects manual group execution. It SHALL preserve historical manual plans.

#### Scenario: Writer and selected reviewer
- **WHEN** a user submits an approved writer and reviewer group
- **THEN** the writer executes first and its successful completion allows a
  separate read-only TaskRun for the selected reviewer without a second start
  action or substitution by a generated writer report

#### Scenario: Failure and explicit retry
- **WHEN** an upstream run fails or is interrupted
- **THEN** dependent tasks remain blocked until an explicit retry succeeds and
  no failed or interrupted attempt is automatically rerun

#### Scenario: Concurrent wake or restart
- **WHEN** multiple workers wake or the local service restarts
- **THEN** ready automatic assignments resume through durable runtime gates
  without creating duplicate initial runs or executing historical manual plans

#### Scenario: Preparation rejection
- **WHEN** runtime preparation rejects an automatic assignment
- **THEN** its automatic execution is stopped and an honest diagnostic remains
  visible for correction and explicit manual start
