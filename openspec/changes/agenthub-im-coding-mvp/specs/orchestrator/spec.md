## ADDED Requirements

### Requirement: P0 task planning
The orchestrator MUST convert an `@orchestrator` coding request into 2-4 visible tasks.

#### Scenario: Login page request creates visible plan
- **GIVEN** a session is selected
- **WHEN** the user sends `@orchestrator build a login page for the demo app`
- **THEN** the orchestrator creates between two and four tasks
- **AND** the chat stream displays the plan to the user

### Requirement: Role-agent assignment
The orchestrator MUST assign planned tasks to enabled role agents such as frontend, backend, or QA.

#### Scenario: Frontend task is assigned
- **GIVEN** the orchestrator creates a UI implementation task
- **WHEN** task assignment runs
- **THEN** the task references an enabled frontend agent
- **AND** the UI shows the assigned role agent

### Requirement: Simple dependency handling
The orchestrator MUST support simple serial dependencies and at most one simple parallel group.

#### Scenario: Dependent task waits for prior task
- **GIVEN** the orchestrator creates a serial implementation task and QA task
- **WHEN** the implementation task is still running
- **THEN** the QA task remains pending until its dependency completes

### Requirement: Task state visibility
The orchestrator MUST expose task states `pending`, `planning`, `running`, `waiting_approval`, `completed`, `failed`, and `interrupted`.

#### Scenario: Task states update during execution
- **GIVEN** a planned task starts execution
- **WHEN** the task moves through execution and artifact collection
- **THEN** the chat stream shows visible state changes for that task

### Requirement: Retry and interrupt orchestration
The orchestrator MUST support retry for failed or interrupted tasks and interrupt for running tasks.

#### Scenario: User retries interrupted task
- **GIVEN** a task is interrupted
- **WHEN** the user clicks retry
- **THEN** the system creates a new TaskRun for the same Task
- **AND** the task can continue through the selected adapter path

#### Scenario: User retries with scripted fallback
- **GIVEN** a CodexAdapter TaskRun fails
- **WHEN** the user chooses retry with fallback
- **THEN** the orchestrator creates a new TaskRun for the same Task using ScriptedMockAdapter
- **AND** previous TaskRun history remains visible

### Requirement: Result summary
The orchestrator MUST summarize completed work and link related artifacts.

#### Scenario: Orchestrated flow completes
- **GIVEN** all required tasks for a request are completed
- **WHEN** diff and preview artifacts exist
- **THEN** the orchestrator posts a summary that references the changed files, preview, and deploy card
