## ADDED Requirements

### Requirement: Bounded adaptive composer
The workbench SHALL resize its textarea for draft and available-width changes,
preserve external focus refs and existing IME/send behavior, and bound long input
to a native internal scroll area without changing the draft or selection.

#### Scenario: Paste and clear a long draft
- **WHEN** a user pastes a multiline draft and later clears it
- **THEN** the textarea grows to its cap, retains scrolling and shrinks to its
  initial height after clearing without submitting the draft

### Requirement: Narrow viewport input access
The narrow workbench SHALL fit an available unzoomed visual viewport, preserve
desktop/unsupported/zoom fallback and provide touch and safe-area-aware composer
controls without disabling browser zoom.

#### Scenario: Keyboard changes the visual viewport
- **WHEN** the unzoomed narrow visual viewport resizes or pans
- **THEN** the workbench follows its height and top offset and releases all
  listeners and temporary bounds when the owning component unmounts

### Requirement: Minimal public presentation update
README.md and root index.html SHALL describe verified UI behavior with minimal
copy changes while preserving structure, styles, scripts, assets and old metrics.

#### Scenario: Public copy follows implementation
- **WHEN** the adaptive composer is verified
- **THEN** existing capability text is adjusted without claiming native mobile,
  native desktop, OS keyboard acceptance or new real API performance results
