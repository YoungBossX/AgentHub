# Resize the three-column workbench

## Why
The sidebar and artifact inspector have fixed widths. Users need to drag either
boundary to allocate space to conversations, execution details and results.

## What Changes
- Add two desktop drag separators, preserving a usable minimum center width.
- Support keyboard adjustment, double-click reset and local width persistence.
- Keep existing drawers, inspector collapse/expand and theme behavior.

## Impact
One frontend task; no dependencies, API or execution changes. Do not change
preview iframe policy or start agent runs during visual acceptance.
