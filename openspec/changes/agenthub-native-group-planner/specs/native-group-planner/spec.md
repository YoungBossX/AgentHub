## ADDED Requirements

### Requirement: Selected Planner actually plans the group
The system SHALL call the existing selected native Planner using its actual
System Prompt and tool policy, preserving ordered execution-role/target assignments.

#### Scenario: Valid native group plan
- **WHEN** a configured or explicitly selected Planner returns a valid task plan
- **THEN** tasks SHALL use its actual titles, file plans, acceptance and validation criteria
- **AND** every selected execution profile and target SHALL remain bound
- **AND** writes SHALL stay serial and reviews SHALL wait for all relevant writes
- **AND** provider and prompt evidence SHALL identify the actual coordination source

#### Scenario: Unsafe, incomplete or failed Planner
- **WHEN** the provider fails, returns a non-task outcome, omits or replaces assignments, violates permissions, or a selected profile becomes unavailable
- **THEN** planning SHALL fail explicitly with no partial tasks or coordinator reply
- **AND** it SHALL NOT silently claim deterministic planning as native success

### Requirement: Existing local execution boundaries remain
The system SHALL preserve disabled-Planner deterministic coordination, direct
single-role behavior, explicit review completion and all existing runtime fences.

#### Scenario: Planner disabled
- **WHEN** no native Planner is selected and the built-in provider is disabled
- **THEN** existing deterministic group coordination SHALL remain available and clearly identified
