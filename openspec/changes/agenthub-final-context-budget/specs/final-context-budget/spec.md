## ADDED Requirements

### Requirement: Bound the final managed input
The system SHALL measure and bound the assembled application-managed request before provider invocation while preserving mandatory rules and frozen source selections.

#### Scenario: Combined sources overflow
- **WHEN** separately bounded memories, Skills and references assemble into an oversized request
- **THEN** invocation is rejected without truncating required rules or changing historical snapshots.

#### Scenario: Provider-specific additions
- **WHEN** native review contracts, MCP instructions, images or output schemas are added
- **THEN** the final gate includes their applicable character or byte contribution before process or HTTP invocation.

#### Scenario: Follow-up after streamed execution
- **WHEN** prior runs contain many streamed UI events or large artifact telemetry
- **THEN** Planner input contains bounded historical task/run/artifact summaries and explicit omission counts, without replaying raw event payloads or changing the full UI/database trace
- **AND** current user text, selected rules, Skills, pins and references retain their existing selection and final rejection policies.

### Requirement: Explain input accounting honestly
The system SHALL expose content-free final request totals, source inclusion/omission reasons and immutable hashes using explicit units.

#### Scenario: Inspect a historical receipt
- **WHEN** the user opens an execution or Planner receipt
- **THEN** they see the recorded request accounting and coverage limits without treating character counts as model token consumption.
