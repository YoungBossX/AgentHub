# Memory snapshot content consistency

## Why
P18 binds sessions and TaskRuns to snapshot IDs, but production retrieval still reads mutable MemoryItems. Updating, retiring, or adding memory can therefore change the content used under an unchanged snapshot ID. Planner evidence can also be overwritten with a later Session snapshot.

## What Changes
- Freeze eligible memory members, their versions, full retrieval data, and the scoring time in a v2 snapshot using the existing SQLite meta_json column.
- Retrieve planner and coding memory from that fixed content. TaskRuns use their persisted binding; Session refresh remains explicit and blocked during active runs.
- Record memory usage from the filtered provider request, including original item identity/version/hash, selection evidence, visible content hashes, and redaction status.
- Preserve v1 history without fabricating content: mark it legacy_unavailable and inject no unprovable historical memory until explicit refresh. Reject damaged v2 content without a live-store fallback.

## Impact
One focused memory consistency task. No new database entity, dependency, adapter, Skill/MCP, session summary engine, automatic learning, or changes to execution permissions. Snapshot content hashes describe frozen memory inputs, not the entire prompt or proof that a provider obeyed memory.
