# Design

Store nullable pinned_at/archived_at on Session and pinned_at on Message. Add
idempotent SQLite upgrades for existing databases. Independent organization
PATCH APIs accept strict booleans, reject empty/unknown/null inputs and only
update explicitly supplied metadata columns under a transaction. They never
rewrite Session.status/updated_at/last_message_at, worktree, target, memory,
Message.content/context or TaskRun state. Message pinning checks its Session.

Archival is reversible list organization. It does not cancel execution, delete
records, remove worktrees or disable existing workflows. Archived sessions
remain reachable by explicit URL and restore action. Pin timestamps survive
archive/restore; repeated identical PATCH calls keep the original timestamps.

The workspace list API defaults to active sessions, with explicit active,
archived and all views. Internal repository callers retain all-session access
and creation numbering counts archived sessions. Within each view pins precede
recent sessions with deterministic ID tie breaking. The local UI loads all
sessions, switches active/archive views, searches within the selected view and
shows pin/archive/restore actions without nested buttons. Explicit archived
selection remains readable even when hidden from the active sidebar.

Each message has pin/unpin; a separate key-message list preserves original
conversation order and jumps to the original bubble. Failures preserve local
state and display errors; late callbacks cannot replace another Session's
messages. GETs only serialize pins. Pin/archive state is recovered from SQLite
on reload/restart rather than browser storage. No pin content is automatically
promoted to trusted memory or extra agent instructions.

Verify old-database upgrade/idempotence/data preservation, ordering/filtering,
reversible operations, strict request/session boundaries, concurrent updates,
execution snapshot invariance and a real ongoing provider during organization.
Verify browser desktop/dark/narrow UI, reload/restart and required regressions.
