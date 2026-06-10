## ADDED Requirements

### Requirement: Selected empty folder provisioning
AgentHub SHALL allow a user-selected empty folder to become a controlled generic new-project root.

#### Scenario: Empty folder is provisioned as fullstack project root
- **WHEN** a user submits a selected empty folder and a simple fullstack app request
- **THEN** AgentHub MUST create a generic project scaffold inside that folder
- **AND** the scaffold MUST include frontend, backend, docs, README, and agenthub project metadata
- **AND** the scaffold MUST NOT contain business-specific code tied to a single acceptance prompt

#### Scenario: Non-empty folder is rejected unless already safe
- **WHEN** the selected folder contains unrelated files before provisioning
- **THEN** AgentHub MUST reject provisioning with a concrete error
- **AND** it MUST NOT register targets or start agents

#### Scenario: Protected paths remain denied
- **WHEN** a provisioned target is registered
- **THEN** denied paths MUST include `.git`, `.env`, `.env.*`, `node_modules`, secrets, virtualenvs, cache directories, and build outputs
- **AND** project-root escapes MUST remain impossible through target path validation

### Requirement: Provisioning registers frontend and backend targets
AgentHub SHALL register role-scoped external targets for the provisioned project.

#### Scenario: Fullstack provisioning registers active targets
- **WHEN** provisioning succeeds for a fullstack request
- **THEN** AgentHub MUST register one frontend target rooted at `frontend`
- **AND** one backend target rooted at `backend`
- **AND** each target MUST expose a ProjectProfile and safe validation commands
- **AND** the selected Session MUST have active frontend and backend target IDs set to the new targets

#### Scenario: Target IDs are deterministic and generic
- **WHEN** AgentHub derives target IDs for a selected project
- **THEN** IDs MUST be based on the preferred slug or generic request slug
- **AND** IDs MUST NOT include business-specific special cases such as Pomodoro-only branches

### Requirement: Generic planner task creation
AgentHub SHALL create runnable frontend/backend tasks for simple new fullstack app requests after provisioning.

#### Scenario: Fullstack request creates runnable tasks
- **WHEN** a user asks for a simple fullstack app in a provisioned session
- **THEN** the planner MUST create frontend and backend coding tasks targeting the active provisioned targets
- **AND** each task MUST be accepted by PlanValidator
- **AND** each task MUST be eligible for normal TaskRun creation

#### Scenario: Multiple app domains use the same path
- **WHEN** the user requests a Pomodoro app, Todo app, bookkeeping app, or reading notes app
- **THEN** AgentHub MUST route them through the same new-project provisioning and planner path
- **AND** it MUST NOT branch on those domain names to create special tasks

### Requirement: New-project execution uses reliable runtime
AgentHub SHALL execute new-project coding tasks through the existing durable runtime path.

#### Scenario: New-project TaskRun uses durable execution
- **WHEN** a frontend or backend task for a provisioned project is run
- **THEN** it MUST enter the durable run engine scheduling path
- **AND** it MUST participate in session queue, target lock, heartbeat, timeout, interrupt, provider evidence, and diagnostics

#### Scenario: Terminal states release locks
- **WHEN** a new-project TaskRun completes, fails, is interrupted, times out, or becomes stale
- **THEN** any held target lock MUST be released idempotently
- **AND** waiting queue entries MUST be reevaluated

### Requirement: No fake provider success
AgentHub SHALL report provider failures honestly for new-project tasks.

#### Scenario: Provider unavailable during new-project execution
- **WHEN** Claude, Codex, or another configured provider is unavailable, quota-limited, unauthorized, timed out, or circuit-blocked
- **THEN** AgentHub MUST record provider evidence and diagnostics
- **AND** it MUST NOT mark the TaskRun completed unless a real successful execution path completed
