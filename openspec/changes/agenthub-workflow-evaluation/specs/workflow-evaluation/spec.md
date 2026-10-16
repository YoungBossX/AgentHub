## ADDED Requirements

### Requirement: Evaluate representative complete workflows
The system SHALL provide reproducible API, multi-file, coordinated frontend/backend,
follow-up and recovery scenarios through existing natural-language planning and
execution services in an isolated local workspace.

#### Scenario: Independent acceptance
- **WHEN** a scenario finishes
- **THEN** passing requires matching source/Diff/execution evidence and every immutable independent contract, including integration checks for coordinated targets.

#### Scenario: Planner unavailable or fallback
- **WHEN** the configured native Planner fails or is unavailable
- **THEN** its actual failure or fallback remains visible and cannot establish native planning success.

### Requirement: Preserve attempts and honest measurement
The system SHALL preserve failures and retries and report explicit denominators,
durations and execution sources without using historical or simulated success as
fresh real-provider evidence.

#### Scenario: Repeated scenarios and recovery
- **WHEN** fresh repetitions or a retry are executed
- **THEN** first-attempt and final outcomes remain distinct with original failures and lineage intact.

#### Scenario: Prepare-only or injected execution
- **WHEN** a run prepares fixtures, uses a test double or injects a failure
- **THEN** the report labels its mode and does not present it as natural provider performance.
