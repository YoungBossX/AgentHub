## ADDED Requirements

### Requirement: Applicable rules precede lexical experience
The system MUST include all applicable active system/user-confirmed project rules regardless of query terms and experience limits. It MUST prioritize applicable active confirmed preferences before relevant optional experience, without granting permissions.

#### Scenario: Unrelated or empty query
- **WHEN** a request has no keywords matching an applicable trusted rule
- **THEN** the complete rule MUST still be selected
- **AND** unmatched optional experience MUST NOT be included

#### Scenario: Restricted or untrusted memories
- **WHEN** workspace, target or role differs or the required target/role context is unknown
- **THEN** the restricted memory MUST NOT be selected
- **AND** pending, archived, rejected and deleted memories MUST remain excluded
- **AND** external/untrusted items MUST NOT become mandatory rules
- **AND** session-scoped items without persistent Session ownership and target-scoped items without target IDs MUST NOT be widened to workspace rules

### Requirement: Whole-item deterministic memory budget
The system MUST enforce a 16,000-character default budget measured over the complete ASCII-escaped, sorted, two-space-indented JSON memory array, including selection metadata. It MUST preserve original item content and hashes.

#### Scenario: Optional experience exceeds remaining budget
- **WHEN** an optional item cannot fit
- **THEN** the whole item MUST be omitted and its omission counted
- **AND** later smaller items MAY be selected within the budget

#### Scenario: Rules alone exceed the budget
- **WHEN** mandatory rules cannot fit in full
- **THEN** request preparation MUST fail with a sanitized actionable budget error before provider invocation
- **AND** rules MUST NOT be silently dropped or truncated
- **AND** coding failure persistence MUST retain execution ownership fencing

### Requirement: Shared frozen selection evidence
The system MUST apply the same policy to Planner and coding requests using their existing frozen inputs, while recording layer/reason and bounded selection-budget evidence.

#### Scenario: Frozen snapshot is reused
- **WHEN** live memory changes after a snapshot or the snapshot is reloaded
- **THEN** equal frozen inputs, query, context and budget MUST yield equal selections and budget evidence
- **AND** receipts MUST describe filtered prepared requests without asserting provider success

#### Scenario: Legacy snapshot
- **WHEN** the bound snapshot has no provable historical content
- **THEN** memory selection MUST remain empty without live-store fallback
