# Explicit review → repair → revalidation

## Issue selection and source binding

Derive bounded stable issue IDs from immutable stored findings, failed command
receipts and failed browser contract checks. Deduplicate rule findings already
present in the report. Original free-text/native findings require explicit user
confirmation even when a later model says passed. Version-bound fixed check IDs
may be machine verified only by the matching newer profile/check at current source.

Prepare a draft for a Session-owned report: reject cross-session/target references,
invalid issue IDs, unsupported protected paths, and source versions that cannot be
verified. Freeze original report identity/content hash, selected issues, target and
source manifest. Native bound file receipts or same-run automatic validation
provide source provenance; legacy reports without either remain explicitly
unverifiable and can still use the existing manual quote flow.

The user edits and explicitly sends the draft. Rebuild the trusted repair binding
server-side instead of accepting client-supplied frozen metadata. Recheck source
at send and again under owned write execution before launching a coding Agent.
Pending drafts must not create tasks or change files. Concurrent source changes
fail closed. Only existing role/target/scope permissions apply. Review text remains
reference material, not a way to override permissions.

## Execution and outcomes

Send the request through ordinary planning/routing/queue and bind resulting tasks
to the original repair message. Preserve same target, originating review and
selected issues. Explicit current-state retry may adopt its actual new base only
when linked to a previously validated repair execution; record that lineage and
base rather than silently claiming the original source is unchanged. Read-only QA
after coding evaluates new source and does not reuse the initial write precondition.

Display waiting/running/failed/expired outcomes and the new Diff and validation
sources. Matching version-bound failed check → current passed check can show
checks recovered; arbitrary findings stay changed-but-unverified or still pending.
Never infer resolved solely from changed text, a missing later finding or model
approval. An explicit local-user verification is labeled user-confirmed, bound to
the current source and invalidated by subsequent changes; retain confirmation
history without changing the original report or frozen request.

## UI and compatibility

Review cards offer issue checkboxes and a prepare-draft action. The existing
composer shows the linked report/selection/version and supports editing/cancel;
send is explicit. Show repair history and revalidation next to the original report,
including links to resulting tasks/artifacts and clear unknown/expired states.
Preserve ordinary messages, quoted artifacts, regeneration, Skills, attachments,
themes and narrow layouts. No extra tool permissions or dependencies.
