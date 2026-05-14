## ADDED Requirements

### Requirement: Vite React preview runner
The system MUST support preview startup for exactly one P0 demo app stack: Vite React.

#### Scenario: Preview starts for Vite React demo app
- **GIVEN** a TaskRun has produced changes in the Vite React demo app
- **WHEN** preview startup begins
- **THEN** the backend runs the fixed Vite preview command in the session worktree
- **AND** records the preview port and URL

### Requirement: Setup-time dependency installation
The system MUST install demo app dependencies during setup and MUST NOT run dependency installation during agent execution.

#### Scenario: Preview starts without installing dependencies
- **GIVEN** the Vite React demo repo dependencies were installed during setup
- **WHEN** an agent task finishes and preview starts
- **THEN** the preview runner does not run `pnpm install`
- **AND** uses the existing setup-time dependencies

### Requirement: Fixed preview command
The system MUST start preview with `pnpm dev --host 127.0.0.1 --port <port>`.

#### Scenario: Backend starts preview command
- **GIVEN** a preview port is allocated
- **WHEN** the preview runner starts the Vite React app
- **THEN** it runs `pnpm dev --host 127.0.0.1 --port <port>`
- **AND** stores the command, port, URL, process information, and health status

### Requirement: Preview card
The system MUST show a preview card when a preview URL is healthy.

#### Scenario: User opens preview panel
- **GIVEN** a healthy preview exists
- **WHEN** the user opens the preview card
- **THEN** the UI displays the preview in a right-side panel or iframe

### Requirement: Preview refresh after second change
The system MUST allow the demo flow to show an updated preview after a second small change in the same session worktree.

#### Scenario: Button text change refreshes preview
- **GIVEN** the user previously opened a preview
- **WHEN** the user asks to make the button text more friendly and the agent changes the Vite React demo repo
- **THEN** the system updates the diff
- **AND** the preview reflects the latest session worktree state

### Requirement: Deploy card after preview
The system MUST show a backend-created deploy card after preview succeeds.

#### Scenario: Preview success creates deploy card
- **GIVEN** a preview artifact is healthy
- **WHEN** deploy card creation runs
- **THEN** the backend stores a Deployment record
- **AND** the UI shows provider, environment, status, URL, commit or ref information, and log reference when available

### Requirement: Mock deploy fallback
The system MUST keep the demo path working when real deploy is unavailable.

#### Scenario: Real deploy is disabled or fails
- **GIVEN** real deployment is unavailable or unstable
- **WHEN** the demo reaches deploy
- **THEN** the backend creates a mock Deployment record
- **AND** the UI shows a mock deploy card without claiming a real provider deployment succeeded
