# Message regeneration

## Why
The design PDF includes regenerating chat responses. The workbench currently
offers quoting, copying and failed TaskRun retries, but cannot regenerate a
reply/plan or a completed group summary while retaining its source.

## What Changes
Add explicit regeneration from a persisted response. A reply/plan reprocesses
its original user request through current planning/execution gates, preserving
the original text, quoted context and immutable attachments. The UI explains
that current files/configuration/context apply and new coding tasks may execute.
A group summary regenerates only its evidence interpretation, without rerunning
the group's tasks. Preserve old messages/results and display lineage.

Use persisted operation identity to prevent duplicate dispatch; reject active
or unfinished source work and recover interrupted preparation on API restart.
Do not reuse the failed-run retry endpoint for completed requests.

## Impact
One focused task; one backwards-compatible Message metadata column, API/UI and
tests/evidence. No new adapter, dependencies, rollback, arbitrary patch writing,
model execution resumption, production deployment or multi-user scope.
