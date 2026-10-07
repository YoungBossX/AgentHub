# Design

Materialize active/warm MemoryItems for the exact workspace once when creating a snapshot. Store their complete serializable retrieval fields and a content digest in meta_json; derive collection versions from that same materialized set. Include the fixed scoring timestamp and member digest in context_pack_hash. Snapshot reads validate schema, digest, content hashes, and workspace membership. A missing workspace selects only unscoped records, never every workspace.

Share the existing keyword ranking logic between live management/evaluation retrieval and snapshot-backed production retrieval. Production ranking uses snapshot.created_at for recency and stale filtering, so identical queries and filters against the same snapshot remain stable after live-store changes or time passing.

The coding ContextPack accepts an explicit trusted snapshot ID supplied from TaskRun metrics, with workspace validation. Persist the filtered canonical context and memory usage receipt through the existing execution-lease fencing/CAS code. A receipt describes the prepared provider request; it does not claim execution success or compliance.

Planner evidence is derived from the exact planner_input used to obtain its result. Later runtime-evidence enrichment preserves that snapshot and receipt even if the Session was refreshed while the provider was planning.

Legacy v1 IDs are never backfilled with current memory. Their metadata exposes contentStatus=legacy_unavailable, their memory list is empty, and explicit Session refresh creates v2. Invalid or missing bound snapshots fail with a bounded error. Ordinary lifecycle retirement affects future snapshots; copies retained in snapshots are historical evidence, not an erasure feature.

Validation covers changed/deleted/replaced members, new members, refresh, ranking time, role/target/workspace boundaries, persisted reopen, bound-run reconstruction, legacy/corrupt content, planner refresh races, and actual visible-content evidence. No real provider compliance claim follows from these deterministic checks.
