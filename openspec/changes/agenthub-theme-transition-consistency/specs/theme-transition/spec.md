## ADDED Requirements

### Requirement: Consistent foreground and background during theme changes
The workbench SHALL apply a theme palette without animating only part of its
foreground/background pair, then restore normal component hover transitions.

#### Scenario: Explicit, rapid or cross-tab theme change
- **WHEN** the user switches a theme, switches again before rendering settles, or another tab updates the stored theme
- **THEN** the document changes colors together and only the latest change may clear the temporary transition pause after rendering
- **AND** persistence, storage failure handling and preview iframe contents remain unchanged
