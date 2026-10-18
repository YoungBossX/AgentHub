## ADDED Requirements

### Requirement: Bound rule based task creation
The server SHALL distinguish explicit recipients from requested actions, and SHALL
not turn recognized negation, explanation, status inquiry or quoted examples into
write tasks. Ambiguous multi-action or missing-slot input SHALL require a valid
Planner result or clarification rather than generic fallback.

#### Scenario: A recipient receives a non-write request
- **WHEN** a direct or group message asks for explanation or negates a modification
- **THEN** no writer task is persisted or automatically dispatched.

#### Scenario: Planner cannot resolve an ambiguous request
- **WHEN** rule input is ambiguous and the Planner is absent, fails or returns a non-task result
- **THEN** the server preserves that boundary and does not execute a partial rule match.

### Requirement: Uniform bounded recognition evidence
The server SHALL record versioned request type, source, routing, action/target,
bounded parameters and reason codes from server decisions in existing message and
task evidence. Client-provided evidence SHALL NOT control routing or permissions.

#### Scenario: Structured Planner response
- **WHEN** the existing Planner produces a validated conversation outcome
- **THEN** its mapped recognition result uses the shared schema without an additional model call.

### Requirement: Reproducible offline intent evaluation
Evaluation SHALL use versioned labeled cases and report sample counts, type/route/
parameter checks and unsafe rule-execution errors, separate from real LLM accuracy.

#### Scenario: Offline evaluation completes
- **WHEN** the frozen corpus is evaluated
- **THEN** each mismatch is retained and aggregate numbers include all cases and category denominators.
