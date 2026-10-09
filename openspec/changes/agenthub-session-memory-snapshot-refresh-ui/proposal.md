# Session memory snapshot refresh UI

## Why
The memory page displays the first available session snapshot and its refresh button only reloads memory items. Users cannot explicitly adopt updated memory for the session they are working in.

## What Changes
- Carry the selected chat session into memory settings and display only that session's snapshot.
- Allow explicit selection when entering settings without a valid session; never substitute another session silently.
- Separate list reload from snapshot refresh, using the existing session refresh API.
- Preserve the displayed binding on failure, explain active-run conflicts, and prevent duplicate or stale UI operations.
- Explain that memory edits affect future snapshots and refresh does not rewrite historical TaskRun bindings.

## Impact
One frontend task. No new backend endpoint, database change, dependency, provider behavior, automatic refresh, Skill/MCP, or execution permission changes.
