# Design

Keep the established visual style and flex controls. Constrain the composer grid's
implicit minimum so narrow viewports cannot hide its Send button. Verify actual
control rectangles/hit targets with and without attachments/context, keyboard and
input-method behavior, dark/light themes and the existing desktop layout.

Replace datetime.utcnow with datetime.now(timezone.utc).replace(tzinfo=None).
This removes the deprecated call but retains UTC instants, microseconds and the
existing timezone-naive SQLite/API convention. Do not reinterpret old timestamps
as local time or migrate stored data. Check a fixed clock plus persisted values,
event/lease ordering and full backend regressions with deprecations made errors.

Read the original design PDF again and audit its local requirements against the
current source and concrete runtime evidence. Verify fresh native execution,
continuation, multiple Sessions, group dispatch and aggregation, failure/interrupt
recovery, configurable instructions, artifacts and local preview. Keep historic
evidence immutable; disclose provider/model/environment limits and bounded APIs.
Run final checks on the final files and preserve a reproducible evidence index.
Only mark this task and the overall goal complete after all applicable local
requirements have sufficient evidence; explicitly deferred production/native-client
and competition-submission deliverables remain outside the user's current scope.

The audit found that selected-code context is supported by the API but has no UI
entry point. Wire explicit selection in the complete-source editor to the existing
composer context, bounded to 2,400 characters. Keep the file, source artifact and
draft provenance, clear stale selections when content changes, and keep context
scoped to the current Session. Quoting must never apply edits or submit a message.
Carry the existing bounded message references into native planning as well as
execution; validate artifact ownership and keep reference text below system trust.
The failed native sample where the Planner guessed a title from an attachment is
retained separately from any corrected run.
