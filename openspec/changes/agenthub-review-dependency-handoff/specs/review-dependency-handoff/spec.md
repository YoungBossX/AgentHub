## ADDED Requirements

### Requirement: Generated demo reviews satisfy planned advisory review dependencies

The system SHALL close pending login and dynamic frontend planned reviews from
matching generated Review artifacts of each dependency's latest completed run.
It SHALL require same-Session dependencies and matching run-owned Diff artifacts,
preserve scheduler/integration readiness, and persist report lineage and verdict.
It SHALL NOT synthesize a QA TaskRun or replace an explicitly started review run.

#### Scenario: An ordinary second chat change follows login execution
- **WHEN** a login frontend run completes and generates a matching advisory report
- **THEN** its planned QA task SHALL become completed with report references
- **AND** an ordinary subsequent button-change HTTP message SHALL be eligible to execute
- **AND** its actual modification and generated review SHALL retain scope/completion gates

#### Scenario: Advisory findings remain visible
- **WHEN** a matching report has warning or failed verdict
- **THEN** the planned review SHALL be satisfied as a completed report
- **AND** its stored source verdict SHALL remain warning or failed
- **AND** completion SHALL NOT claim functional acceptance or real QA execution

#### Scenario: A follow-up waits for active login execution
- **WHEN** an ordinary dynamic autoStart follow-up waits on login QA
- **THEN** the existing continuation path SHALL start it after the dependency closes
- **AND** finalizer validation reads SHALL NOT autoflush its pending terminal state
- **AND** all execution identity, queue, lock, lease and generation checks SHALL remain required

#### Scenario: A new chat message resumes a persisted pending review
- **WHEN** a Session has a pending planned review with current matching persisted evidence
- **THEN** new user-message planning SHALL reconcile that review before choosing dependencies
- **AND** it SHALL preserve completed TaskRun evidence and the original report verdict

#### Scenario: Evidence is absent or belongs to another execution
- **WHEN** a dependency lacks a current completed run/report, its Diff is mismatched,
  its dependency belongs to another Session, or the review task already has a TaskRun
- **THEN** generated-review satisfaction SHALL NOT complete the planned review task
