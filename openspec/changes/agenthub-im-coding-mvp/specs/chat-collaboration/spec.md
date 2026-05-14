## ADDED Requirements

### Requirement: IM-style message stream
The system MUST render an IM-style chat stream containing user, orchestrator, role-agent, system, and artifact-related messages.

#### Scenario: Messages from multiple senders appear in one session
- **GIVEN** a session is selected
- **WHEN** the user sends a request and the orchestrator assigns tasks to role agents
- **THEN** the chat stream shows messages from the user, orchestrator, and assigned role agents in chronological order

### Requirement: Orchestrator mention parsing
The system MUST parse `@orchestrator` mentions and route the message to the orchestrator flow.

#### Scenario: User asks orchestrator to build a login page
- **GIVEN** a session is selected
- **WHEN** the user sends `@orchestrator build a login page`
- **THEN** the system creates an orchestrator-handled message
- **AND** the orchestrator begins planning visible tasks for the request

### Requirement: Role-agent mention parsing
The system MUST parse role-agent mentions including `@frontend`, `@backend`, and `@qa`.

#### Scenario: User mentions a frontend agent
- **GIVEN** role agents are enabled
- **WHEN** the user sends a message containing `@frontend`
- **THEN** the system resolves the mention to the enabled frontend role agent
- **AND** the created task or direct message references that agent role

### Requirement: Streamed chat updates
The system MUST use SSE for P0 realtime chat, task, and artifact updates, with TaskRunEvent-backed recovery.

#### Scenario: Task state updates stream into chat
- **GIVEN** a task run is active
- **WHEN** the backend emits task state events
- **THEN** the frontend receives the events through SSE
- **AND** the chat stream updates without requiring a page reload

#### Scenario: SSE reconnect replays missed task run events
- **GIVEN** the frontend last received a TaskRunEvent sequence number
- **WHEN** the SSE connection reconnects
- **THEN** the backend can replay persisted TaskRunEvents after that sequence
- **AND** the frontend can recover missed task, approval, artifact, error, and completion updates

### Requirement: Message persistence
The system MUST persist chat messages with `sessionId`, sender fields, markdown content, kind, parent linkage, stream state, and creation time.

#### Scenario: User reloads a session
- **GIVEN** a session contains prior user, orchestrator, and agent messages
- **WHEN** the user reloads the page and opens that session
- **THEN** the system restores the persisted message history for that session

### Requirement: Approval card messages
The system MUST render pending approval requests as chat-stream approval cards.

#### Scenario: Approval request appears in chat
- **GIVEN** a TaskRun enters `waiting_approval`
- **WHEN** the backend emits an `approval.requested` event
- **THEN** the chat stream shows an approval card
- **AND** the card displays the approval type, reason, requested action, risk level, and relevant command or path when present
