## ADDED Requirements

### Requirement: Fresh internal scope computation and persistence
Write completion SHALL compute its decision from one fresh complete snapshot
inside its persistence operation. It SHALL preserve all existing collection,
ownership, target, policy, baseline, lease, lock and commit fences.

#### Scenario: Normal write completion
- **WHEN** a writing adapter finishes with permitted new output
- **THEN** one full post-run snapshot supplies the persisted scope decision
- **AND** both that decision and its durable marker must pass before artifacts

#### Scenario: Supplied decision
- **WHEN** a caller supplies a scope decision to the existing persistence API
- **THEN** it is freshly revalidated and a stale or forged mismatch fails closed

#### Scenario: Changed authorization during validation
- **WHEN** ownership, metrics, baseline, policy or the held lock changes before persistence
- **THEN** no successful decision or artifact is authorized by that validation

### Requirement: Bounded performance evidence
Performance acceptance SHALL use actual fresh API runs with matching workload
and snapshot counts. The implementation SHALL NOT cache or filter snapshots or
skip protected paths, race checks, named streams or descriptor checks.

#### Scenario: Measured completion
- **WHEN** original and revised runs are compared
- **THEN** real file output, scope decisions, nonempty Diff and API responsiveness are verified alongside timing
- **AND** model execution and generic functional acceptance are not inferred from ScriptedMock timing
