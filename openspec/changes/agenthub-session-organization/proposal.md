# Local session organization

## Why
The design PDF requires session pinning, archival and pinned key messages.
Current sessions are only chronological and none of those actions persist.

## What Changes
Add reversible, persisted presentation metadata to existing Session/Message
records, scoped update APIs, active/archive navigation and pinned-message jumps.
Preserve worktrees, histories, execution identity and current run fences.

## Impact
One local single-user OpenSpec task; additive SQLite columns only, no new tables,
dependencies, providers, execution modes or deployment scope.
