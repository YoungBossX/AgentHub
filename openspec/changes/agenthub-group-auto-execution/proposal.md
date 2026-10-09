# Automatic execution of bounded group assignments

## Why
Explicit multi-Agent plans currently require a separate start action for every
participant. A completed writer does not dispatch the selected reviewer. This
leaves the local group workflow unfinished despite a valid dependency graph.

## What Changes
New explicit groups automatically execute approved target assignments through
the existing queue and dispatcher. Retain an explicit manual request mode and
preserve historical manual plans. Continue ready assignments after successful
completion or explicit retry; stop at failures, interruption and approval gates.
Reconcile persisted automatic groups after service restart without rerunning a
terminal attempt. Completion aggregation is a separate follow-up task.

## Impact
Scoped backend changes; no schema, adapter, dependency or platform additions.
