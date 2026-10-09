# Include pinned conversation messages in Agent context

## Why
The PDF explicitly requires manually pinned messages to remain long-term
conversation context. Current pin persistence and navigation work, but both
planning and coding only select eight recent messages. An older pinned message
therefore disappears from provider input.

## What Changes
Add a shared, bounded pinned-message selector for the current Session. Include
its references and selection evidence in canonical planning/execution context,
separate from trusted memory and system instructions. Retain original identity,
sender, timestamps and explicit truncation/omission metadata. Pin/unpin affects
new prepared requests, without rewriting prior snapshots or running requests.

## Impact
One focused Agent-context repair. No new tables, adapters, permissions, model
providers, dependencies, deployment or implicit promotion to trusted memory.
