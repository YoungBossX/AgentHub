## ADDED Requirements

### Requirement: Explicit participants are never silently omitted
The system SHALL route every distinct mentioned execution role in a bounded group
and disclose deterministic coordination without claiming native Planner execution.

#### Scenario: Coding and review participants
- **WHEN** a message mentions coding and review roles in any order
- **THEN** all coding roles SHALL receive tasks in mention order
- **AND** review tasks SHALL wait for all writes and bind to each relevant target
- **AND** custom aliases SHALL preserve selected profile identity through execution
- **AND** repeated identical mentions SHALL NOT create duplicate assignments

#### Scenario: Invalid group assignment
- **WHEN** any participant is unknown, disabled, ambiguous, incompatible or requests
  unapproved platform scope, or a custom Planner is selected for group decomposition
- **THEN** the request SHALL fail explicitly without partial tasks or a plan response

### Requirement: Group planning preserves execution boundaries
The system SHALL validate registered targets, paths, capabilities and dependencies
before committing a complete group, and SHALL retain existing execution fences.

#### Scenario: Explicit review is not satisfied by a coding report
- **WHEN** a write generates an advisory review artifact
- **THEN** it SHALL NOT mark an explicitly assigned group reviewer completed
- **AND** completion SHALL require the selected review task's own execution

### Requirement: Contact selection supports multiple participants
The UI SHALL append distinct participants in group mode and replace the leading
participant prefix in direct mode without sending messages or starting execution.

#### Scenario: Select contacts
- **WHEN** users select multiple contacts in group mode
- **THEN** the composer SHALL retain all selected aliases and the request text
- **AND** repeated selection SHALL NOT duplicate an alias
