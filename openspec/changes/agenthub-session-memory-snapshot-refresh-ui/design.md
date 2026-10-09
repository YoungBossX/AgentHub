# Design

The sidebar links to `/settings/memory?session=<selected-id>`. The server page reads the session query and passes it into the client. The client validates membership using the existing workspace session list before allowing refresh. A missing or unknown selection remains unselected until the user chooses a session.

The client offers separate actions: reload workspace memory items and explicitly POST to the selected session's existing `/memory-snapshot/refresh` endpoint. Only a successful response matching the selected session and workspace may replace that session's displayed snapshot ID. The UI never infers snapshot validity or version from its ID.

All conflicting controls are disabled while an operation is pending; asynchronous initial/filter loads are cancelled on dependency changes or unmount. Refresh responses are ignored after unmount or backend changes. HTTP 409 is presented as a conflict with a retry instruction after active work finishes; other failures also retain the prior binding. Server-side active-run and historical TaskRun protection remain authoritative.

Acceptance uses component tests for correct session selection, no-selection/invalid-selection behavior, explicit refresh, list-only reload, duplicate prevention, successful binding replacement, rejected refresh, and stale responses. API tests cover the POST endpoint and failure propagation; sidebar/server-page tests cover navigation. Existing backend refresh tests are rerun with temporary persistence.
