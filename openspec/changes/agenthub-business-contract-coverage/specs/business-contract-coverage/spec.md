## ADDED Requirements

### Requirement: Check existing API business boundaries
The server SHALL independently check declared contact field bounds/types, identity/defaults, duplicate non-mutation and unsupported methods in its trusted disposable ASGI harness.

#### Scenario: Invalid input or duplicate request
- **WHEN** an invalid or duplicate contact is submitted
- **THEN** it is rejected and existing records remain unchanged; missing assertions cannot establish success.

### Requirement: Verify explicit contacts recovery
Integration acceptance SHALL identify the selected fixed contract and bind complete browser checks to both source inputs and the trusted harness policy.

#### Scenario: Duplicate or synthetic server rejection
- **WHEN** the resilience-v2 browser submits a rejected request
- **THEN** accessible error feedback is visible, form/list state is retained, and a later actual successful retry persists across reload; synthetic faults remain labeled.

#### Scenario: Incomplete or stale evidence
- **WHEN** contract/check coverage, exit result, source or policy does not match
- **THEN** acceptance cannot be reported as passed.
