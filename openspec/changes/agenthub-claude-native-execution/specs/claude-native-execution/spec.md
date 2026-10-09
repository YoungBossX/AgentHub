# Claude Native Execution

## ADDED Requirements

### Requirement: Native launch preserves execution containment
The system SHALL launch the installed native Claude executable on Windows without
a shell and SHALL preserve restricted/safe mode, strict MCP and frozen file tools.

#### Scenario: Windows npm installation
- **WHEN** Claude is installed through an npm shim with an adjacent native executable
- **THEN** coding, Planner and health checks resolve the native executable
- **AND** no shell or weaker containment profile is introduced.

### Requirement: Restricted execution receives bounded provider configuration
The system SHALL copy only approved SDK authentication, base URL and model env
fields from user settings, with explicit process configuration taking precedence.
It SHALL NOT import project settings, hooks, plugins, MCP, command helpers or
control-plane credentials, and SHALL redact imported credentials from evidence.

#### Scenario: User settings contain credentials and customizations
- **WHEN** a restricted Claude run starts with credentials in user settings
- **THEN** only approved provider environment fields reach the process
- **AND** customization commands are not executed and secret values are redacted.

#### Scenario: Missing or invalid settings
- **WHEN** user settings are absent, malformed, oversized or use a relative config directory
- **THEN** no settings fields are imported
- **AND** normal explicit credentials or honest provider failure remain in effect.

### Requirement: Native stream text remains accurate and private
The system SHALL decode CLI text as UTF-8, reconcile streamed text with repeated
assistant snapshots, and redact credentials even when split between text deltas.

#### Scenario: Partial text followed by a snapshot
- **WHEN** the CLI emits partial text and a matching assistant snapshot
- **THEN** the stored response contains each text block once
- **AND** later distinct messages with identical text remain visible.
