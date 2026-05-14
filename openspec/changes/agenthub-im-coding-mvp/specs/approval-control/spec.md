## ADDED Requirements

### Requirement: Command allowlist enforcement
The system MUST execute only allowlisted commands during P0 adapter, diff, preview, and deploy flows.

#### Scenario: Non-allowlisted command is requested
- **GIVEN** an adapter or script requests a command outside the allowlist
- **WHEN** the backend evaluates the command
- **THEN** the command is blocked
- **AND** an approval request or error is emitted according to policy

### Requirement: Protected path enforcement
The system MUST protect `.git/`, `.env`, `.env.*`, `secrets/`, `node_modules/`, and system paths from unapproved edits.

#### Scenario: Adapter tries to edit protected path
- **GIVEN** a task run is active
- **WHEN** a proposed file operation targets a protected path
- **THEN** the backend blocks the operation unless explicit approval policy permits it
- **AND** the UI shows an approval or error state

### Requirement: Approval request payload
The system MUST represent approval requests with ApprovalRequestPayload containing `approvalType`, `reason`, `requestedAction`, `riskLevel`, and optional `command`, `path`, and `expiresAt`.

#### Scenario: Security approval is requested
- **GIVEN** an adapter requests a risky action
- **WHEN** the backend emits `approval.requested`
- **THEN** the event payload identifies whether it is `product_confirmation` or `security_approval`
- **AND** includes a reason, requested action, risk level, and any relevant command or path

### Requirement: Approval-required actions
The system MUST require approval for deploy, git push, deleting files, editing protected paths, running non-allowlisted commands, and network access.

#### Scenario: Deploy requires approval
- **GIVEN** a preview has succeeded
- **WHEN** the user initiates a real deploy action
- **THEN** the system requests approval before performing the deploy
- **AND** the related TaskRun can move to `waiting_approval`

### Requirement: Waiting approval state
The system MUST move the related Task and TaskRun to `waiting_approval` while an approval request is pending.

#### Scenario: User approval is pending
- **GIVEN** a TaskRun emits an approval request
- **WHEN** the approval has not been approved, denied, expired, failed, or interrupted
- **THEN** the TaskRun remains in `waiting_approval`
- **AND** the UI shows the approval card with approve and deny actions

### Requirement: Network off by default
The system MUST keep network access off by default for P0 agent execution, with optional allowlist behavior only.

#### Scenario: Adapter requests network access
- **GIVEN** a task run is active with default permissions
- **WHEN** the adapter requests network access
- **THEN** the system blocks the access unless allowlisted and approved

### Requirement: No arbitrary host access
The system MUST NOT grant full host access, arbitrary shell execution, unbounded background processes, or unreviewed deploy in P0.

#### Scenario: Script requests arbitrary shell
- **GIVEN** `ScriptedMockAdapter` is executing
- **WHEN** its script requests arbitrary shell access
- **THEN** the backend rejects the operation
- **AND** the task run records a guardrail error or approval state

### Requirement: Basic approval UI
The system MUST provide a basic approval UI for pending approval requests.

#### Scenario: User approves a requested action
- **GIVEN** an approval request is shown in the chat stream
- **WHEN** the user approves the request
- **THEN** the backend calls adapter `approve`
- **AND** the task run can continue from `waiting_approval`
