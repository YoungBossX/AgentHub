## ADDED Requirements

### Requirement: Settings target the selected session
The memory settings UI SHALL carry the selected chat session into settings, validate it against the current workspace, and display only its snapshot binding.

#### Scenario: Chat session is not first in the list
- **WHEN** the user opens memory settings from a selected session
- **THEN** the page shows that session's snapshot and refresh targets its ID

#### Scenario: Missing or invalid session selection
- **WHEN** no matching session is available for the supplied selection
- **THEN** snapshot refresh is disabled until the user explicitly selects an available session
- **AND** no other session snapshot is substituted silently

### Requirement: Refresh is explicit and preserves failure boundaries
The UI SHALL separate memory-list reload from snapshot refresh, use the existing server refresh API, and replace the displayed binding only on matching success.

#### Scenario: Successful refresh
- **WHEN** the user explicitly refreshes the selected session snapshot
- **THEN** the returned binding is shown and conflicting controls are disabled while pending
- **AND** the UI explains that historical TaskRun bindings remain unchanged

#### Scenario: Refresh conflict or failure
- **WHEN** the server rejects refresh or the request fails
- **THEN** the previous binding remains displayed and an actionable error is shown
- **AND** the UI does not claim success or refresh another session

#### Scenario: List reload and memory edits
- **WHEN** the user reloads the list or updates a memory status
- **THEN** no session snapshot refresh is requested automatically

#### Scenario: Stale asynchronous response
- **WHEN** the page is unmounted or its backend changes during refresh
- **THEN** the stale result does not update the current page
