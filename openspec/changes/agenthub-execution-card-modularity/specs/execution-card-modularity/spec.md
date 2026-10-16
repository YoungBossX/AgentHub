## ADDED Requirements

### Requirement: Centralize execution lease authority
The system SHALL implement execution ownership records, comparisons, capture and lease renewal in one module independent of the orchestration engine while preserving existing runtime behavior and import compatibility.

#### Scenario: An obsolete or mismatched execution attempts renewal
- **WHEN** the run, generation, session, queue or write lock differs from its frozen ownership token
- **THEN** renewal and finalization remain rejected without extending a competing owner's authority or publishing artifacts.

### Requirement: Separate task-card responsibilities
Task-card presentation SHALL separate pure plan interpretation, plan summaries and artifact cards from fetching/orchestration without changing UI actions or evidence meaning.

#### Scenario: Existing plan and artifact controls
- **WHEN** a user approves/rejects a plan, selects a versioned artifact, requests review/context, opens preview or uses recovery/fallback
- **THEN** existing callbacks, disabled-state gates, evidence labels and selection behavior remain unchanged.
