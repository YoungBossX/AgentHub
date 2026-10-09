## ADDED Requirements

### Requirement: Adjustable desktop pane widths
The workbench SHALL let users resize both desktop boundaries while preserving
the center's minimum width and existing execution and preview behavior.

#### Scenario: Resize and restore
- **WHEN** the user drags or keyboard-adjusts a separator
- **THEN** only the selected side pane changes within bounds
- **AND** the preference survives reload when storage is available
- **AND** double-click restores that side's default width

#### Scenario: Cancel drag or change layout
- **WHEN** a drag is cancelled, focus is lost or the viewport leaves desktop size
- **THEN** drag capture and the temporary shield are released
- **AND** narrow layouts and collapsed/expanded inspector modes remain usable

#### Scenario: Invalid persisted widths
- **WHEN** saved widths are malformed or storage is unavailable
- **THEN** the layout remains usable with bounded default widths
