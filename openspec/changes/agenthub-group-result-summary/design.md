# Design

Freeze actual planning-time coordinator prompt, selected profile identity,
provider settings without credentials, and group task IDs privately on the
server-created plan Message. New group metadata references that Message. A
configured native coordinator summarizes through existing provider transports
under planner_no_tools; an unconfigured built-in coordinator returns an explicitly
deterministic execution receipt. Do not substitute deterministic model success
when a configured provider fails.

Collect a bounded database-only evidence snapshot from latest TaskRun attempts,
their matching Diff/Review artifacts and version hashes. Preserve selected role
and target identity, retry counts, report provenance, and read-only/static-review
boundaries. Completed means every latest attempt and required artifact exists;
failed reports are still completed review execution. Render server facts
separately from native interpretation and never claim test execution from a
review verdict. Summarize settled failures/interruption, approval gates, and
manual continuation as well as complete groups; defer while adapters are active.

Claim one summary attempt per input fingerprint under the SQLite writer lock.
Store owner/lease/attempt and a real summary Message before the provider call;
call without holding a transaction. Recheck latest evidence and selected
profile availability/permissions under a writer fence before publication.
Reject stale completions and old owners. Preserve prior attempts as historical
Messages, recover expired claims after restart, and require explicit retry for
provider/output errors. Summary failures never alter coding/review run states.

Wake reconciliation through the existing dispatcher and local group loop.
Publish Message/receipt changes with same-transaction TaskRunEvent-backed SSE
where a group run exists. A narrow pending-summary polling fallback covers
groups rejected before their first run. Read endpoints only serialize current
status; they never invoke providers or write summaries. Avoid changing Session
updated_at during summary publication so unrelated live request fences remain
valid. New UI cards show current/history state, native/deterministic source,
task/artifact receipts, static-review limitation and failed-summary retry.

Verify controlled invalid/stale/revoked/duplicate/retry/restart conditions,
actual native Planner-to-Agents-to-coordinator execution and prompt binding,
browser/SSE/persistence, full regressions and saved evidence hashes.
