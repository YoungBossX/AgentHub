## ADDED Requirements

### Requirement: Chat Workspace Remains Session Focused
The system MUST keep detailed Agent Runtime Settings out of the primary chat/session sidebar.

#### Scenario: Chat page shows only a compact settings entry
- **WHEN** a user opens the AgentHub chat workspace
- **THEN** the page MUST prioritize workspace/session navigation, agent contacts, chat, tasks, and artifacts
- **AND** it MUST show at most a compact settings entry point for runtime configuration.

#### Scenario: Runtime form is not rendered inline
- **WHEN** a user views the session sidebar
- **THEN** the sidebar MUST NOT render the full Planner, Frontend, Backend, and Review runtime configuration form inline.

### Requirement: Dedicated Runtime Settings Page
The system MUST provide a dedicated page or route for Agent Runtime Settings.

#### Scenario: User opens runtime settings
- **WHEN** a user activates the chat page settings entry point
- **THEN** AgentHub MUST navigate to or display a dedicated runtime settings page
- **AND** the page MUST expose Planner, Frontend, Backend, and Review runtime configuration controls.

#### Scenario: Runtime settings preserve existing config behavior
- **WHEN** the runtime settings page loads
- **THEN** it MUST load the existing runtime config, provider config, agent profile, and planner preset metadata through the current APIs or compatible read-only metadata APIs.

### Requirement: Save And Cancel Runtime Settings
The system MUST support explicit Save and Cancel actions for runtime settings edits.

#### Scenario: Save persists draft settings
- **WHEN** a user changes runtime settings and clicks Save
- **THEN** AgentHub MUST validate and persist the draft runtime config through the existing runtime config save path
- **AND** it MUST show whether the save succeeded or failed.

#### Scenario: Cancel discards draft settings
- **WHEN** a user changes runtime settings and clicks Cancel
- **THEN** AgentHub MUST discard unsaved draft changes
- **AND** it MUST restore the persisted runtime config or return to the prior chat page without saving.

#### Scenario: Unsaved changes do not affect active runtime config
- **WHEN** a user edits settings but has not clicked Save
- **THEN** AgentHub MUST NOT use those draft settings for planner or coding agent resolution.

### Requirement: User-friendly Provider Status Labels
The system MUST translate internal runtime/provider status values into user-facing labels and explanations.

#### Scenario: Unchecked status is presented clearly
- **WHEN** a provider has internal status `unchecked`
- **THEN** the UI MUST present it as an undetected or not-yet-verified state
- **AND** it MUST NOT display only the raw word `unchecked` as the primary user-facing label.

#### Scenario: Missing key status is actionable
- **WHEN** a Planner API provider has internal availability `missing_key`
- **THEN** the UI MUST explain that the configured environment variable is missing
- **AND** it MUST NOT expose or request a raw API key value.

#### Scenario: No-auth provider status is clear
- **WHEN** a provider has internal status `not_required`
- **THEN** the UI MUST present it as not requiring authentication.

#### Scenario: Required validation errors are field-specific
- **WHEN** validation reports a required field or missing runtime role configuration
- **THEN** the UI MUST show a user-facing message that identifies the missing field or role
- **AND** it MUST NOT rely only on the raw word `required`.

### Requirement: Runtime Settings Preserve Safety Boundaries
The system MUST keep P16/P17/P17b runtime safety boundaries while moving settings to a dedicated page.

#### Scenario: Raw API keys are not stored
- **WHEN** a user configures Planner API settings
- **THEN** the settings page MUST allow configuring an environment variable name
- **AND** it MUST NOT allow saving a raw API key value.

#### Scenario: Planner and coding agents remain separate
- **WHEN** a user configures Planner, Frontend, Backend, or Review runtime settings
- **THEN** Planner provider configuration MUST remain separate from coding agent provider configuration.

#### Scenario: Invalid runtime config is rejected
- **WHEN** a user attempts to save an invalid provider/profile/role/mode configuration
- **THEN** AgentHub MUST reject the save or return validation errors honestly
- **AND** it MUST NOT silently substitute another provider unless fallback is explicitly configured and auditable.
