## ADDED Requirements

### Requirement: Oversized entry points SHALL compose cohesive modules

The API application entry point, Planner entry point, and workspace shell SHALL
delegate coherent responsibilities to focused modules without changing their
externally observable contracts.

#### Scenario: API route family extraction preserves the contract

- **WHEN** an existing agent settings, TaskRun, artifact, preview, deployment,
  or Session-event endpoint is moved from the application entry point
- **THEN** its path, HTTP method, dependencies, status behavior, and response
  payload remain compatible
- **AND** `app.main:app` continues to expose the route through router composition

#### Scenario: Planning internals are modularized behind one entry point

- **WHEN** planning helpers are separated by responsibility
- **THEN** callers continue to use `plan_for_message`
- **AND** the same inputs produce the same bounded task or conversation outcome

#### Scenario: Workspace shell internals are modularized without UI drift

- **WHEN** event handling or presentation sections are extracted
- **THEN** `WorkspaceShell` remains the page-level export
- **AND** existing session, SSE refresh, artifact, and task interaction tests
  retain their behavior
