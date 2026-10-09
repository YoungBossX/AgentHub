## ADDED Requirements

### Requirement: Workspace prompts augment existing Agent behavior
The system SHALL persist an optional systemPrompt for each existing runtime role
without granting additional tools, paths, network access or adapter capabilities.

#### Scenario: Enabled role prompt is saved and loaded
- **WHEN** a user saves a valid multiline prompt for an enabled runtime role
- **THEN** the workspace settings SHALL retain the text across database reload
- **AND** other workspaces SHALL keep their own prompts
- **AND** blank or disabled overrides SHALL inherit the assigned Agent default

#### Scenario: Invalid input is rejected
- **WHEN** a prompt exceeds 8000 characters, is not a string or contains NUL
- **THEN** validation SHALL reject it before persistence

### Requirement: Execution inputs preserve prompt identity
The system SHALL freeze the effective coding prompt per TaskRun and preserve
mandatory role, target, completion and safety enforcement.

#### Scenario: Settings change while a run is queued
- **WHEN** configuration is changed after creating a TaskRun
- **THEN** that run SHALL retain its original prompt
- **AND** a new run SHALL resolve current configuration
- **AND** caller plan context SHALL NOT replace the frozen prompt
- **AND** public metrics SHALL expose a hash/source receipt without raw prompt text

#### Scenario: Legacy run or corrupt binding
- **WHEN** a legacy run without a binding prepares a request
- **THEN** it SHALL freeze the current effective prompt under existing persistence fences
- **WHEN** an existing binding has invalid identity or digest
- **THEN** request preparation SHALL fail before provider execution

### Requirement: LLM Planner transports apply the configured prompt
The system SHALL render the effective planner prompt in each existing LLM
transport while retaining the mandatory structured output and safety contract.

#### Scenario: Planner builds a provider request
- **WHEN** an LLM planner prepares a request with a workspace override
- **THEN** the redacted prepared input SHALL contain that prompt
- **AND** Responses, chat, Anthropic and Claude CLI transports SHALL include it
- **AND** deterministic/scripted results SHALL NOT be presented as model compliance
