## ADDED Requirements

### Requirement: Persistent workbench theme choice
The UI SHALL allow explicit switching between light and dark themes using an
accessible toolbar button, with light as the default.

#### Scenario: Switch and reload
- **WHEN** the user switches to dark or light
- **THEN** the workbench, task graph and Diff editor adopt that theme
- **AND** a reload restores the saved choice before application hydration

#### Scenario: Storage unavailable or preference invalid
- **WHEN** local storage is unavailable or contains an unsupported value
- **THEN** startup falls back to light and explicit switching remains usable

#### Scenario: Another tab changes the theme
- **WHEN** another same-origin tab updates or clears the saved preference
- **THEN** the current document and toggle reflect the supported preference
- **AND** preview iframe security and application content remain unchanged
