## ADDED Requirements

### Requirement: Fresh local runtime evidence retains execution lineage

The system SHALL support a fresh local browser Session from chat planning through
real coding execution, matching nonempty Diff, advisory Review and healthy Vite
Preview, followed by an ordinary chat change and persisted reload.
Acceptance SHALL record provider identities, run and artifact references, actual
rendered output and limitations without substituting historical artifacts or
claiming scripted reports as real QA/provider execution.

#### Scenario: Login and ordinary follow-up through browser controls
- **WHEN** a new Session requests a demo login page and then a button text change
- **THEN** both coding runs SHALL preserve scope and completion validation
- **AND** the follow-up SHALL complete without manually rewriting its plan
- **AND** its own healthy Preview SHALL render the form and updated button

#### Scenario: Persistent local UI remains usable
- **WHEN** the user refreshes Preview and reloads the workspace
- **THEN** chat and execution artifacts SHALL retain their Session association
- **AND** theme and column width preferences SHALL survive reload
- **AND** the narrow workspace SHALL avoid page-wide horizontal overflow

#### Scenario: Persisted plans use generated graph role fields
- **WHEN** a task plan omits assignedRole and its graph uses assignedAgentRole
- **THEN** planning details SHALL use the task's assigned Agent role
- **AND** task breakdown details SHALL preserve graph role labels
- **AND** existing explicit plan role fields SHALL remain supported

#### Scenario: Provider probe checks run with a custom local launcher
- **WHEN** the CLI launcher is a configured absolute path
- **THEN** health probing SHALL use that command and persist only safe summaries
- **AND** contract tests SHALL explicitly control launcher configuration rather
  than depending on the developer's host environment

#### Scenario: Scope checking outlasts an HTTP request timeout
- **WHEN** a background run captures its scope baseline or finalizes file output
- **THEN** blocking checks SHALL yield the API event loop for other requests
- **AND** exact execution ownership, lease and commit validation SHALL remain required
- **AND** cancellation SHALL drain the synchronous worker before the caller reuses
  or closes its database Session, including repeated cancellation and worker errors
