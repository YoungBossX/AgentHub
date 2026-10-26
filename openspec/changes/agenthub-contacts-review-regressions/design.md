# Design

Reuse the trusted disposable build, ASGI bridge and sandboxed browser harness.
The new opt-in `contacts-review-v4` keeps the 28 v3 check identities and adds
five checks at each viewport (38 total). Only the browser's delivered POST
response is corrupted after the real backend confirms 201; injected faults are
explicitly labeled. Verify one POST, real persisted records, safe GET recovery,
preserved known lists and neutral save acknowledgements rather than fake rows.
Always attempt safe GET reconciliation after invalid JSON; preserving the known
list is the fallback if that GET fails, not a replacement for attempting it.
Initial GET failure must not assert a confirmed empty list.
Delayed initial GET success/failure must not overwrite a later saved state. Both
blocking edits while initial loading and discarding obsolete responses are valid.
Successful reconciliation may use the actual saved row as its acknowledgement;
a separate status notice is required only when reconciliation fails. Any visible
notice must still be neutral. The initial 34-check draft and its false rejection
are preserved with their frozen policy, never relabeled as final-v4 results.

The v3 case remains the default Chinese benchmark; its frozen outcomes do not
change. A new Session in a copied fixture receives an explicit bounded repair
request. Old native review fingerprints are not rebound to relocated sources.
New native QA reviews current source and Diff under existing read restrictions.
Unused login selectors are removed only in that copy, preserving the primary
P0 login baseline. Corrective metrics are separate from the natural ten tasks.
