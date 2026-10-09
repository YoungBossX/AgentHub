## ADDED Requirements

### Requirement: Custom profiles are editable and workspace scoped
The system SHALL persist custom names, aliases, prompts, capabilities, registered
targets and supported native tool policies without activating legacy drafts.

#### Scenario: Create, edit and disable a custom Agent
- **WHEN** a user saves a compatible custom profile in the Agent settings
- **THEN** the profile SHALL reload with its configuration and appear in contacts
- **AND** enabled profiles SHALL be selectable for their compatible runtime role
- **AND** editing SHALL preserve identity and disabling SHALL prevent new execution

#### Scenario: Invalid or duplicate permissions
- **WHEN** a profile requests an unknown provider/target/tool policy, unsupported
  role/capability, platform scope or duplicate/reserved workspace alias
- **THEN** the system SHALL reject the change without modifying existing profiles

### Requirement: Selection applies the actual custom profile
The system SHALL select custom profiles through runtime settings or explicit
workspace mentions and preserve task/run/provider lineage.

#### Scenario: Custom coding Agent executes
- **WHEN** a compatible custom profile is selected for a coding task
- **THEN** the existing adapter SHALL receive its frozen prompt and tool policy
- **AND** task target/mode/capability checks and all scope/completion fences SHALL apply
- **AND** public evidence SHALL identify the custom profile without raw prompt text
- **AND** a queued run SHALL NOT gain permissions from later profile edits

#### Scenario: Disabled, foreign or incompatible selection
- **WHEN** a task or request selects a disabled, foreign or incompatible profile
- **THEN** execution SHALL fail before provider launch without built-in substitution

#### Scenario: Custom alias and Planner
- **WHEN** a workspace message names a custom alias
- **THEN** its compatible role SHALL route through the existing planning path
- **AND** the chosen profile SHALL remain explicit through coding or LLM planning
- **AND** unknown, disabled or ambiguous aliases SHALL be rejected

### Requirement: Tool policies have native enforcement
The system SHALL expose only tool policies supported by the existing adapter.

#### Scenario: Claude review is read-only
- **WHEN** a custom review profile prepares a Claude request
- **THEN** both --tools and --allowedTools SHALL contain only Read
- **AND** no Bash, write, unrestricted network or filesystem permissions SHALL be granted

#### Scenario: Codex coding policy
- **WHEN** a custom Codex coding profile executes
- **THEN** it SHALL retain the existing CLI sandbox, assigned worktree, network-off
  policy and file-output gates
- **AND** the UI SHALL describe native coding tools without claiming shell-tool removal
