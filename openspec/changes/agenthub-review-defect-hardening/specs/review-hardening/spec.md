## ADDED Requirements

### Requirement: Local API controls enforce request boundaries
The API SHALL reject untrusted Host or Origin values and require the explicit
control header for mutations, with the separately authenticated MCP gateway
retaining its own execution-bound credential checks.

#### Scenario: An untrusted page attempts a bodyless control
- **WHEN** an untrusted page submits interrupt, approve or another mutation
- **THEN** the request MUST fail before any persistent or process mutation
- **AND** authorized workbench and explicit local clients MUST remain usable

### Requirement: Preview reads remain within serving scope
Preview SHALL serve only the frontend root and necessary installed dependencies,
with protected and unrelated filesystem paths rejected.

#### Scenario: A preview requests unrelated source or a protected alias
- **WHEN** HTTP or a source import requests unrelated source or protected files
- **THEN** the server MUST reject the read
- **AND** ordinary rendering and dependency loading MUST continue to work

### Requirement: Default Skill limits are atomic
The workspace SHALL enforce default Skill count and prompt-byte budgets across
concurrent package saves.

#### Scenario: Two saves compete for remaining budget
- **WHEN** different Skill saves individually fit but together exceed a budget
- **THEN** at most one MUST succeed and the persisted defaults MUST stay valid

### Requirement: Diagnostics distinguish content from failures
Diagnostics SHALL infer failure categories only from failure evidence.

#### Scenario: Successful events mention failure-related words
- **WHEN** successful selection, passing validation or ordinary prose mentions auth, adapter or validation
- **THEN** those events MUST NOT become failure factors or recovery suggestions
- **AND** explicit failures and unsuccessful postprocessing MUST remain visible
