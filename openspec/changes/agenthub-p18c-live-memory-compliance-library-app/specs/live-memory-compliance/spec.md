## ADDED Requirements

### Requirement: Active memory rules are prepared before live session

The system SHALL ensure the P18c long-term memory rules are active before
creating the live library-management rehearsal session.

#### Scenario: Memory exists before session
- **WHEN** the P18c live session is created
- **THEN** the six memory rules under test MUST already be active canonical
  memory items
- **AND** the session MUST receive a `memorySnapshotId` created after those
  memory items are active

#### Scenario: User prompt omits memory rules
- **WHEN** the live library-management request is submitted
- **THEN** the user prompt MUST NOT restate the project location, framework,
  persistence, change-log, platform-boundary, or provider-evidence memory rules

### Requirement: Live provider evidence is mandatory for live compliance

The system SHALL use ClaudeCodeAdapter or CodexAdapter for live compliance when
auth, quota, and runtime permit.

#### Scenario: Real provider available
- **WHEN** ClaudeCodeAdapter or CodexAdapter successfully executes the task
- **THEN** the freeze review MUST record provider identity, TaskRun id, diff
  evidence, build/check/test evidence when available, and generated app evidence

#### Scenario: Real provider unavailable
- **WHEN** no real provider can execute because of auth, quota, CLI, runtime, or
  configuration failure
- **THEN** the freeze review MUST record the exact blocker
- **AND** the system MUST NOT claim live memory compliance success

#### Scenario: ScriptedMock fallback appears
- **WHEN** ScriptedMock is used for fallback or diagnostics
- **THEN** its result MUST be labeled fallback/mock
- **AND** it MUST NOT be used to claim live memory compliance

### Requirement: Library management app meets bounded functional scope

The live coding task SHALL create a working local demo Library Management App
matching the user request.

#### Scenario: Login flow
- **WHEN** the generated app is opened
- **THEN** it MUST show a login page accepting the fixed local demo credentials
  `18088888888` / `888888`
- **AND** successful login MUST navigate to a management page

#### Scenario: Book management operations
- **WHEN** the user is on the management page
- **THEN** the app MUST support adding, deleting, editing, and querying books

#### Scenario: localStorage persistence
- **WHEN** books are added or modified
- **THEN** the app MUST persist simple demo data in localStorage by default
- **AND** it MUST NOT create a non-requested backend or database

### Requirement: Memory compliance violations are detected

The system SHALL evaluate the live result against P18c memory compliance checks.

#### Scenario: Change-log memory compliance
- **WHEN** frontend code changes are produced
- **THEN** missing applicable `docs/change-log.md` evidence MUST be flagged as
  `memory_compliance_violation`

#### Scenario: Project location memory compliance
- **WHEN** the new frontend app is not created under
  `~/Desktop/agenthub-rehearsals/`
- **THEN** the result MUST be flagged as
  `project_location_memory_violation`

#### Scenario: Persistence memory compliance
- **WHEN** a backend or database is created without the user requesting it
- **THEN** the result MUST be flagged as `persistence_memory_violation`

#### Scenario: Target boundary compliance
- **WHEN** `apps/api` or AgentHub platform code is modified without explicit
  platform maintenance mode
- **THEN** the result MUST be flagged as `target_boundary_violation`

#### Scenario: Provider evidence compliance
- **WHEN** provider success is claimed without TaskRun, diff, and build or
  validation evidence
- **THEN** the result MUST be flagged as `provider_evidence_violation`

#### Scenario: Snapshot consistency compliance
- **WHEN** Planner, coding agent, review/eval, TaskRun, or mission trace use
  different memory snapshots
- **THEN** the result MUST be flagged as `snapshot_consistency_violation`

### Requirement: Evaluation metrics are reported

The system SHALL report P18c memory compliance metrics in the freeze review.

#### Scenario: Metrics included
- **WHEN** the P18c freeze review is generated
- **THEN** it MUST include Preference Recall Rate, Project Memory Recall Rate,
  Cross-Agent Consistency Rate, Snapshot Consistency Rate, Change-log Missing
  Rate, Target Boundary Violation Count, Persistence Memory Violation Count,
  Provider Evidence Violation Count, and Task Success Delta when comparable
  control evidence exists

#### Scenario: No comparable control
- **WHEN** no comparable memory-off control run exists
- **THEN** Task Success Delta MUST be recorded as unknown or inconclusive rather
  than positive

### Requirement: Freeze review is auditable

The system SHALL produce an auditable P18c freeze review document.

#### Scenario: Freeze review evidence
- **WHEN** P18c implementation completes or stops on a blocker
- **THEN** `docs/p18c-freeze-review.md` MUST record real provider used or exact
  unavailable reason, session id, task/run id, memorySnapshotId, AGENTS.md and
  CLAUDE.md hashes, active memory ids under test, changed files, diff artifact,
  review artifact, build/check/test evidence, preview/staging evidence when
  available, memory compliance results, follow-up status, and limitations
