# Add persistent light and dark themes

## Why
The conversation workbench has no theme switch and its fixed light surfaces are
unsuitable for users who prefer a dark interface.

## What Changes
- Add an accessible light/dark toggle to the existing workspace toolbar.
- Persist the explicit choice locally, initialize it before hydration, and keep
  open tabs in sync. Preserve light as the default and tolerate blocked storage.
- Theme the existing UI palette, task graph and read-only Diff editor.

## Impact
One frontend task. No dependencies, backend/API changes or agent execution.
Preview iframe contents remain controlled by the preview application itself.
