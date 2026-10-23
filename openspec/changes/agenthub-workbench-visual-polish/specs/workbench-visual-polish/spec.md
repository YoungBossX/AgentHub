## ADDED Requirements

### Requirement: Consistent workbench surfaces and typography
The workbench SHALL implement the supplied warm light/dark palettes, borderless
surface hierarchy, double-shadow input focus, dark weight offset of 40, aligned
inline icons, tabular numerals and pretty paragraph wrapping.

#### Scenario: Theme and keyboard navigation
- **WHEN** the user switches themes or focuses the composer/search/settings inputs
- **THEN** surfaces and text update together and keyboard focus remains visible
- **AND** pane resizing and process, Diff and result views remain usable

### Requirement: Accessible bounded interaction feedback
The UI SHALL use Grid disclosures, append-only grapheme reveal, physical spring
feedback and copy confirmation with a 2500ms lifetime.

#### Scenario: Incremental output and repeated copying
- **WHEN** prose is appended or a copy operation succeeds repeatedly
- **THEN** existing prose is not animated again and each copy gets a fresh lifetime
- **AND** reduced motion disables animation without hiding text or feedback

#### Scenario: Disclosure and drag cancellation
- **WHEN** the user collapses a section or cancels a resize
- **THEN** collapsed controls cannot receive focus and cancelled widths are restored
- **AND** no content-height calculation or database change is required
