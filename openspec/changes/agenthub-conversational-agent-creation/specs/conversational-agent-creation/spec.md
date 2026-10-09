## ADDED Requirements

### Requirement: Natural language produces a reviewable Agent configuration
The local workspace SHALL provide a creation conversation that can clarify and
refine an editable custom-Agent draft using a configured real Planner.

#### Scenario: User requests and refines an Agent
- **WHEN** the user describes an Agent or supplies a follow-up with current edits
- **THEN** the server returns a clarification or a validated draft with provider provenance
- **AND** no profile, task or file mutation occurs until the user explicitly saves
- **AND** the draft can be edited and restored after a browser refresh in the same tab

#### Scenario: Provider or output is invalid
- **WHEN** the provider is disabled, fails, is revoked or returns invalid configuration
- **THEN** the UI preserves the current draft and displays an actionable failure
- **AND** no arbitrary tools, target paths or permissions are accepted

### Requirement: Saved Agents preserve existing execution boundaries
Generated configuration SHALL use the same custom-Agent validation, persistence,
mention routing and native tool restrictions as manual configuration.

#### Scenario: User saves and enables a reviewed draft
- **WHEN** the user explicitly saves a valid configuration and chooses to enable it
- **THEN** the profile appears in the directory and is usable by its alias
- **AND** actual runs freeze its prompt, identity, tools and target scope

#### Scenario: Scope changes or responses arrive late
- **WHEN** the workspace changes or a prior generation finishes after leaving the builder
- **THEN** its result does not replace another workspace's draft or newer edits
- **AND** duplicate clicks do not create duplicate generation or save requests
