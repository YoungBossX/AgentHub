## ADDED Requirements

### Requirement: Core entity persistence boundary
The system MUST implement P0 persistence using User, Workspace, Session, Message, Agent, Task, TaskRun, TaskRunEvent, Artifact, Diff, Preview, and Deployment entities.

#### Scenario: Task run creates artifacts and events
- **GIVEN** a task run completes with file changes
- **WHEN** the backend collects diff, preview, and deploy outputs
- **THEN** the system stores those outputs using Artifact, Diff, Preview, and Deployment records
- **AND** stores run trace events using TaskRunEvent records
- **AND** no unrelated P0 domain entity is required for the happy path

### Requirement: TaskRunEvent support entity
The system MUST include TaskRunEvent as the only P0 support entity beyond the core domain model.

#### Scenario: Adapter event is persisted
- **GIVEN** an adapter emits a normalized event
- **WHEN** the backend processes the event
- **THEN** it stores a TaskRunEvent with `taskRunId`, `eventType`, `payloadJson`, `sequence`, and `createdAt`
- **AND** the stored sequence can be used for replay or debugging

### Requirement: TaskRun lifecycle
The system MUST expose TaskRun states `created`, `queued`, `streaming`, `waiting_approval`, `applying_changes`, `collecting_diff`, `starting_preview`, `completed`, `failed`, and `interrupted`.

#### Scenario: Successful task run reaches completed
- **GIVEN** an adapter run starts
- **WHEN** the adapter streams changes, diff collection succeeds, and preview starts
- **THEN** the TaskRun transitions through the required lifecycle states
- **AND** ends in `completed`

#### Scenario: Approval pauses a task run
- **GIVEN** a task run requires user approval
- **WHEN** the approval request is emitted
- **THEN** the TaskRun state becomes `waiting_approval`
- **AND** the run does not continue until approval is granted or the request is denied, expired, failed, or interrupted

### Requirement: TaskRun diff refs
Each TaskRun MUST record `baseRef` before execution and `headRef` after execution for TaskRun-specific diff collection.

#### Scenario: baseRef is captured before execution
- **GIVEN** a TaskRun is about to start in a session worktree
- **WHEN** the backend prepares adapter execution
- **THEN** it records `baseRef` as the current git commit SHA or another explicit git ref before adapter execution begins

#### Scenario: headRef is captured after execution
- **GIVEN** a TaskRun has finished adapter execution
- **WHEN** the backend prepares diff collection or run completion
- **THEN** it records `headRef` as the current HEAD, a temporary ref, or a working-tree snapshot marker
- **AND** the Diff artifact uses the TaskRun's `baseRef` and `headRef` for traceability

#### Scenario: Retry preserves previous refs
- **GIVEN** a TaskRun failed or was interrupted with existing `baseRef` or `headRef`
- **WHEN** the user retries the task
- **THEN** the system creates a new TaskRun with a new `baseRef`
- **AND** does not overwrite the previous TaskRun's `baseRef` or `headRef`

### Requirement: Artifact association
The system MUST associate artifacts with the TaskRun that produced them.

#### Scenario: Diff artifact belongs to task run
- **GIVEN** a task run produces a diff
- **WHEN** the backend stores the diff artifact
- **THEN** the Artifact record references that TaskRun
- **AND** the Diff record references the Artifact

### Requirement: Error mapping
The system MUST persist normalized `errorCode` and `errorMessage` on failed TaskRuns.

#### Scenario: Adapter fails
- **GIVEN** an adapter run encounters a known failure
- **WHEN** the run is marked failed
- **THEN** the TaskRun stores a normalized error code and human-readable message
- **AND** the UI can offer retry from that failed state

### Requirement: SSE recovery from persisted state
The system MUST allow the UI to recover session messages, tasks, task runs, terminal states, artifacts, approval requests, and replayable task-run events after page refresh or SSE reconnect.

#### Scenario: User refreshes during or after execution
- **GIVEN** a session has messages, TaskRuns, TaskRunEvents, and artifacts
- **WHEN** the user refreshes the page or reconnects SSE
- **THEN** the UI reconstructs the current session state from persisted backend records
- **AND** can replay task-run events after the last received sequence when available
