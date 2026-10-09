# Evidence-bound group result summaries

## Why
Explicit groups now execute and review automatically, but the coordinator never
returns the combined outcome to the conversation. Users must reconstruct which
participants completed, what artifacts exist, and what still needs attention.

## What Changes
New groups freeze their selected coordinator and generate a persistent summary
when execution settles. Use the configured native no-tool Planner for actual
interpretation; disclose deterministic receipts when no native Planner exists.
Bind summaries to latest attempts and artifact evidence, preserve failure/retry
history, reject stale output, and expose provenance plus retry in the chat UI.

## Impact
One scoped local backend/UI task, reusing Message records and existing Planner
transports, SQLite writer fences and SSE. No dependency, schema-table, adapter,
deployment or platform expansion. Historical group plans remain unchanged.
