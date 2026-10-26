## ADDED Requirements

### Requirement: Honest and actionable local port diagnostics
The developer launcher SHALL preserve port configuration and existing listeners,
distinguish bind error causes, and only suggest alternatives confirmed by a probe.

#### Scenario: Windows excludes the selected API port
- **WHEN** binding fails with EACCES and a fixed read-only OS query confirms an excluded range
- **THEN** diagnostics identify that range and provide a probed alternative command
- **AND** no service starts, no port is silently changed and no system setting is written

#### Scenario: Occupied port or unavailable diagnostic
- **WHEN** a selected listener exists or a reservation query/probe fails
- **THEN** the listener remains intact and diagnostics retain the real error code
- **AND** an unconfirmed range or alternative is never reported as verified

### Requirement: Preserve execution behavior during extraction
The coordinator SHALL retain its current task, ownership, provider, validation,
artifact and continuation contracts while delegating cohesive responsibilities.

#### Scenario: Cancellation, stale ownership and downstream continuation
- **WHEN** a run is cancelled, loses ownership or completes with dependent tasks
- **THEN** the existing release, terminal-write and dependency behavior remains unchanged
- **AND** refactoring alone does not change model success or validation semantics

### Requirement: Version-bound ten-task evidence
The final evaluation SHALL run five supported Chinese workflow categories twice
under one frozen implementation/policy/operator identity and retain all outcomes.

#### Scenario: Failed or incomplete real task
- **WHEN** a native workflow fails or lacks required QA/validation/usage evidence
- **THEN** that result remains in the cohort with its actual denominator and unknown values
- **AND** any repair/retry is separately attributable, never a replacement first success

### Requirement: Reproducible and traceable demonstration
The project SHALL provide concise operator instructions and identify the exact
final-version run supplying showcased process, Diff, review and application views.

#### Scenario: Historical benchmark and latest showcase coexist
- **WHEN** public presentation includes a successful latest sample and older metrics
- **THEN** their version, denominator and purpose remain distinct and links resolve
