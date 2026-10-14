## ADDED Requirements

### Requirement: Configure and select workspace instruction packages
The system SHALL validate SKILL.md and bounded textual references, expose built-ins
and workspace packages, support Agent defaults and explicit per-message overrides.

#### Scenario: Explicit empty selection
- **WHEN** a message specifies an empty skillIds list
- **THEN** that message's tasks do not inherit default Skills.

### Requirement: Retain reproducible skill evidence without privilege escalation
The system SHALL freeze selected content and identity before model execution,
verify integrity before loading, and record actual loading compatibility.

#### Scenario: Configuration edited after run creation
- **WHEN** a skill is edited or disabled after a run is queued
- **THEN** the run and its retries retain the original bound package content.

#### Scenario: Skill requests additional permissions
- **WHEN** a skill requests a tool or path outside existing permission policy
- **THEN** existing tool/path controls remain effective.

#### Scenario: Historical or scripted execution
- **WHEN** a run lacks a binding or uses ScriptedMock
- **THEN** the UI does not claim the Skill was followed by a model.
