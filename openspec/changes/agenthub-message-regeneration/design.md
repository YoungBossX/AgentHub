# Design

## Source and execution
Resolve the clicked reply/plan and original user request within the same Session.
Only complete chat/plan replies and settled current group summaries are eligible.
Service diagnostics, user input, streaming responses, missing/foreign sources and
unfinished tasks do not become runnable merely because a client supplies IDs.

For request regeneration, append a new user request with the original text and
context, and authoritative references to the original attachment-bearing request.
Re-enter the existing planner, approval, scheduler, queue, scope and completion
paths. Current worktree/configuration/memory and recent messages apply; this is
not an exact historical replay or an undo of previous file changes. Keep original
message contents, task/run states and artifacts. Require explicit UI confirmation
with this behavior before dispatch.

For a summary, reuse its frozen coordinator policy and fresh evidence with the
existing lease, owner, evidence fingerprint and selection fences. Only the current
settled summary may request another interpretation. No coding task is created.

## Persistence and concurrency
Add Message.regeneration_json, default `{}`, through existing SQLite incremental
initialization. The normal message-create request cannot set it. Store source
response/request IDs, attachment source, kind, state and safe failure status here.
Client-generated UUID operation ID becomes the new message ID; repeated transport
requests with that ID return the same persisted operation and never dispatch again.
Serialize preparation using the Session database write lock; competing preparation
for the same Session is rejected. Revalidate eligibility under the lock. Release
the transaction before model calls. Standard task safety remains authoritative.

If preparation fails, retain the new request with a visible failed state and any
partial plan/run evidence. At startup mark interrupted request preparation failed;
never resume model calls automatically. This follows the existing single-process
local API runtime boundary. Later deliberate regeneration uses a new operation ID.

## Interface and verification
Keep existing styles, show the source and operation state, and allow jumping to
the original. On network uncertainty, reuse the same operation ID until the result
is resolved. Session switches cannot insert old responses into another Session.
Pending preparation must refresh even before a TaskRunEvent exists.

Verify old-schema upgrade, same/foreign Session ownership, source integrity,
attachments/context, idempotency/concurrency, active work rejection, exceptions,
restart and summary fences. Verify actual browser confirmation/history/error and
theme/narrow layout, a native regeneration with persisted matching output, and
unchanged old results. Run relevant regressions and strict OpenSpec before closure.
