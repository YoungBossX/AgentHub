## ADDED Requirements

### Requirement: Unambiguous local timestamps
The system SHALL interpret offset-free API datetimes as UTC and preserve
explicit offsets, displaying existing UI timestamps in the browser timezone
with inspectable original and UTC values and visible timezone labels.

#### Scenario: Local display and recovery
- **WHEN** the browser loads or reloads Session, Preview or event timestamps
- **THEN** valid times show the same instant in its local timezone, including
  date crossings, and original values remain inspectable without database writes

#### Scenario: Server and browser timezone differ
- **WHEN** server-rendered UI hydrates in a browser with a different timezone
- **THEN** the initial snapshots match and later local display updates without
  hydration errors or misleading timezone labels

### Requirement: Strict consistent instant parsing
The system SHALL use the same strict instant parser for event display,
Session ordering and execution overlap, rejecting invalid dates and clocks.

#### Scenario: Invalid or equivalent representations
- **WHEN** timestamps have invalid fields or encode the same instant differently
- **THEN** invalid inputs do not create synthetic dates or events, equivalent
  instants compare consistently, and execution/storage contracts stay unchanged
