## ADDED Requirements

### Requirement: Deterministic login tasks persist their execution target

The system SHALL bind frontend and QA tasks created by the deterministic demo
login-page planner to the existing registered demo frontend target before
persisting tasks and graph metadata. Their safeTarget SHALL remain within that
target's registered source path. The frontend task SHALL retain its source-only
planned files and the planning/frontend/QA sequence SHALL remain unchanged.

#### Scenario: A chat-created login task reaches the scoped execution boundary

- **WHEN** a new Session receives `@orchestrator build a login page for the demo app`
- **THEN** persisted frontend and QA plans SHALL resolve to `demo-frontend`
- **AND** the frontend run SHALL acquire the existing target lock and capture its
  own scope baseline rather than fail because its plan has no target binding
- **AND** an isolated ScriptedMock run SHALL create actual allowed source changes
  and a nonempty Diff through the existing scope and completion gates

#### Scenario: A malformed binding remains rejected

- **WHEN** a writing run has a missing or unverifiable execution target
- **THEN** existing fail-closed target, scope and artifact checks SHALL remain in force
- **AND** the planner repair SHALL NOT grant fallback write access or permission
  to protected paths, platform targets or external host directories
