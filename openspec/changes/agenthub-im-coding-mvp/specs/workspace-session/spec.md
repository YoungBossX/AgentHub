## ADDED Requirements

### Requirement: Single-user workspace creation
The system MUST support a single-user workspace bound to one Vite React demo repository with `repoUrl`, `rootPath`, and `defaultBranch` metadata.

#### Scenario: User opens the demo workspace
- **GIVEN** the local demo environment is running
- **WHEN** the user opens AgentHub
- **THEN** the system shows a selectable workspace backed by the configured Vite React demo repository
- **AND** the workspace can be used to create coding sessions

### Requirement: Multiple session management
The system MUST allow the user to create and switch between at least three sessions in one workspace.

#### Scenario: User switches between sessions
- **GIVEN** one workspace exists
- **WHEN** the user creates three sessions and selects each session from the session list
- **THEN** the chat stream, task state, and artifacts shown in the UI match the selected session

### Requirement: Session-level worktree binding
The system MUST create and persist exactly one git worktree for each Session in P0.

#### Scenario: Session gets a worktree
- **GIVEN** a workspace exists
- **WHEN** the user creates a new session
- **THEN** the system creates or assigns a deterministic session-level git worktree
- **AND** stores the path on `Session.worktreePath`

#### Scenario: TaskRuns reuse session worktree
- **GIVEN** a session has a `worktreePath`
- **WHEN** multiple TaskRuns execute in that session
- **THEN** each TaskRun uses the same session worktree path
- **AND** each TaskRun records that path for traceability

### Requirement: Cross-session worktree isolation
The system MUST prevent multiple sessions from sharing the same worktree path.

#### Scenario: Multiple sessions use separate worktrees
- **GIVEN** two sessions exist in the same workspace
- **WHEN** each session starts agent execution
- **THEN** the sessions have different `worktreePath` values
- **AND** changes from one session do not appear in the other session's worktree

### Requirement: Session status and recency
The system MUST maintain session `status` and `lastMessageAt` so the UI can show active and recent sessions.

#### Scenario: New message updates session recency
- **GIVEN** a session exists
- **WHEN** the user sends a chat message in that session
- **THEN** the session `lastMessageAt` is updated
- **AND** the session remains selectable without losing its prior messages
