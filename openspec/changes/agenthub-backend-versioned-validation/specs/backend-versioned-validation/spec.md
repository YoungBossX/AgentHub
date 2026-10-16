## ADDED Requirements

### Requirement: Automatically validate assigned built-in backend source
The system SHALL run platform-owned syntax and API contract checks against a
temporary copy of the assigned built-in FastAPI target without running edited
tests, installing dependencies or contacting a running service.

#### Scenario: Valid source and complete fixed contracts
- **WHEN** an owned demo-backend execution reaches finalization
- **THEN** the server records actual check/test outcomes bound to source and policy fingerprints and the current execution generation.

#### Scenario: Unsafe, failed or incomplete validation
- **WHEN** inputs are unsafe, commands fail, coverage is incomplete or execution is cancelled or loses ownership
- **THEN** no passing acceptance is established and durable evidence preserves the actual outcome.

### Requirement: Preserve profile-specific evidence and historical integrity
The system SHALL use only the same execution's unchanged source and profile when
combining command evidence with rules and native model review.

#### Scenario: Source change or profile mismatch
- **WHEN** source, installed validation policy, target or profile no longer matches
- **THEN** QA reports expired or unverifiable evidence without rewriting history.

#### Scenario: Python backend has no frontend build
- **WHEN** backend check/test pass with a matching native review and rules
- **THEN** QA can establish configured-check acceptance while marking build not applicable and clearly limiting coverage to the fixed API contracts.
