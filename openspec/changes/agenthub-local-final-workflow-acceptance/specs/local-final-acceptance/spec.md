## ADDED Requirements

### Requirement: Local controls and time contracts remain usable
The local workspace SHALL keep message controls visible and actionable at supported
narrow widths and preserve its existing UTC persistence semantics without calling
the deprecated UTC acquisition API.

#### Scenario: A user composes a message at 320px
- **WHEN** the message input, attachment and Send controls are displayed
- **THEN** the controls remain within the viewport and can be used
- **AND** desktop layout, keyboard input and existing attachment/context behavior remain intact

#### Scenario: The backend stores a new timestamp
- **WHEN** the shared clock helper is used
- **THEN** its value represents UTC with preserved microseconds and no timezone object
- **AND** existing database rows, API representation and lease comparisons remain compatible

#### Scenario: A user quotes selected source code
- **WHEN** the user selects code in the complete-source editor and explicitly quotes it
- **THEN** the composer retains the bounded exact text, file and source artifact
- **AND** marks its source as an editor draft without applying or sending it
- **AND** stale selections and another Session cannot reuse that context

#### Scenario: A user reselects the current Session
- **WHEN** the current Session is selected again in the sidebar
- **THEN** its loaded artifacts and composer context remain available
- **AND** selecting another Session still clears the previous selected-code context

### Requirement: Final local completion is evidence bounded
The project SHALL reconcile applicable design requirements with current code,
automated checks and actual local runtime behavior before claiming completion.

#### Scenario: Final acceptance is recorded
- **WHEN** the local workflows have been exercised
- **THEN** native Agent success, deterministic fallback, simulated faults and verification limits are distinguished
- **AND** missing or failed requirements remain open instead of being marked complete from unrelated tests
