# Consistent local time display

## Why
Session and Preview UI currently truncate UTC API timestamps while the event
timeline labels UTC separately. This makes local timestamps ambiguous and
duplicates permissive date parsing in execution overlap and SSE visuals.

## What Changes
Centralize strict instant parsing: legacy offset-free API datetimes mean UTC;
explicit Z/offsets retain their meaning. Display existing UI times in the
browser's local timezone with explicit timezone labels and inspectable original
and UTC values. Keep deterministic SSR and matching first hydration output.

## Impact
One frontend-only local task. Preserve backend SQLite datetimes, snapshot and
lease semantics, API contracts, event payload privacy and execution behavior.
No dependencies, settings, adapters, new tables or deployment changes.
