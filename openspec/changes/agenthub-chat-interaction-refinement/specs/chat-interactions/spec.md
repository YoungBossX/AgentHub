## ADDED Requirements

### Requirement: Intentional chat input and reading
The workspace SHALL prevent accidental IME submission and preserve user reading intent.

#### Scenario: Confirming Chinese input
- **WHEN** Enter occurs during composition, with keyCode 229, or within 500ms after composition ends
- **THEN** no message is submitted
- **AND** normal Enter after the guard interval and Shift+Enter retain their intended behavior

#### Scenario: Following and returning to new messages
- **WHEN** new output arrives
- **THEN** only an unpaused reader within 40px of the bottom is followed
- **AND** manual scroll intent immediately pauses following
- **AND** a distance over 120px shows 跳至最新, with unread counts when applicable
- **AND** explicit latest/bottom navigation resumes following without changing history semantics

### Requirement: Stable chat surfaces and pane interactions
The workspace SHALL keep outlines dimensionless and pane changes cancellable.

#### Scenario: Nested controls
- **WHEN** a surface contains action buttons
- **THEN** controls use borderless hover fills and retain visible focus
- **AND** outlines use inset shadows and outer radii equal inner radii plus padding

#### Scenario: Resizing the result pane
- **WHEN** the user drags a separator
- **THEN** a transparent shield prevents the preview from taking pointer input
- **AND** Escape restores the pre-drag layout without saving it
- **AND** double-click divides chat and results equally, excluding the session sidebar
- **AND** releasing with chat strictly over 82 percent collapses the result pane while retaining a usable reopen width

### Requirement: Identifiable long filenames
The workspace SHALL preserve filename suffixes and full file identity.

#### Scenario: A filename exceeds its label width
- **WHEN** an attachment or Diff file label is too long
- **THEN** the middle is visually abbreviated and the complete extension remains visible
- **AND** full title/accessibility text and original action values are preserved
