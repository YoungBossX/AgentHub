# Workbench reading experience

## Why

The user approved the six-item follow-up to visual polish: contrast, information
hierarchy, empty inspector behavior, Chinese typography, chat following and
task/version-oriented results. Keep the ten established visual rules.

## What Changes

- Fix semantic button foregrounds and small-text contrast; use 14px body/12px
  supporting workbench text with existing system fonts.
- Put stage/action first and move technical counts/routine detail into disclosures.
- Collapse the inspector automatically when unselected, preserve per-session user
  choices, and reveal explicitly selected artifacts without losing pane widths.
- Use one chat scroll container, follow output near the bottom, retain reading
  position above it, and offer a counted new-message return action.
- Group results by actual task/run membership; default to current outputs and
  retain historical runs and document versions without implying current success.

## Impact

Frontend presentation only. No dependencies, provider calls, schema changes,
adapter/permission changes, commit or push. Preserve stored data and old evidence.
