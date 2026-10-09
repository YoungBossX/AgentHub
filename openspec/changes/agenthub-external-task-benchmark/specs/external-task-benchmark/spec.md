## ADDED Requirements

### Requirement: Benchmark inputs are fixed and isolated
The benchmark SHALL create fresh external target repositories and SQLite persistence, keep evaluators outside assigned targets, hash suite inputs and refuse existing output directories or output inside the development checkout.

#### Scenario: Prepare-only execution
- **WHEN** preparation is requested
- **THEN** all selected fixtures have a recorded failing baseline evaluator and frozen input hashes
- **AND** no provider is invoked or provider success rate reported

#### Scenario: Unsafe or occupied output
- **WHEN** the destination is occupied, inside the checkout or a system root
- **THEN** the runner rejects it before overwriting files

### Requirement: Live evidence follows actual execution
The benchmark SHALL use existing target registration and TaskRun worker services with the existing CodexAdapter, retain failures, and never fabricate provider, build, preview or deployment success.

#### Scenario: Successful bounded case
- **WHEN** execution completes with observed provider turn evidence, valid memory receipt, passed scope, unchanged evaluators/scaffold, nonempty matching Diff and passing functional checks
- **THEN** the report marks that case passed and includes its real task/run/snapshot/diff identities

#### Scenario: Failed run or forged acceptance
- **WHEN** a run fails, an evaluator changes, memory evidence is absent, scope fails, or provider turn evidence is missing
- **THEN** the case remains failed even if its functional evaluator exits zero

#### Scenario: Aggregate result
- **WHEN** live cases are summarized
- **THEN** every selected case remains in the denominator, including failures
- **AND** the report bounds claims to the synthetic suite without inferred speedup or general model quality
