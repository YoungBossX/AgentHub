## ADDED Requirements

### Requirement: Readable focused workbench
The UI SHALL preserve established visual rules while improving contrast,
typography, routine-detail hierarchy and contextual inspector space usage.

#### Scenario: Empty workbench and explicit selection
- **WHEN** a session has no selected artifact
- **THEN** the automatic inspector is collapsed and current guidance remains visible
- **AND** explicit artifact selection opens it while manual close survives refresh

#### Scenario: Dark primary action and supporting text
- **WHEN** light/dark workbench and Agent forms are rendered
- **THEN** action foregrounds and ordinary supporting text meet 4.5:1 contrast
- **AND** technical evidence remains available without crowding the default view

### Requirement: Respect conversation reading position
The UI SHALL follow output only while near the bottom, preserve upward reading,
provide a bounded new-message notice, and isolate scroll state by session/view.

#### Scenario: Appends during upward reading
- **WHEN** new messages or text arrive while the reader is above the bottom
- **THEN** the viewport stays put and an explicit return action reports new messages
- **AND** repeated updates do not duplicate the count or affect another session

### Requirement: Current results and historical versions
The UI SHALL group artifacts by authoritative task/run membership, show current
run evidence first and keep prior runs/document versions accessible as history.

#### Scenario: Failed retry with earlier successful artifacts
- **WHEN** the newest run fails or has no artifacts
- **THEN** the current section shows that actual state without promoting older success
- **AND** historical artifact and document-version evidence can still be inspected
