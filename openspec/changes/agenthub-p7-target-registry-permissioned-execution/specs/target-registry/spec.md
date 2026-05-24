## ADDED Requirements

### Requirement: Target Registry Source Of Truth

The system MUST provide a Target Project Registry as the source of truth for
supported execution targets, including demo frontend, demo backend, and
AgentHub platform targets.

#### Scenario: Target registry is inspected

- **WHEN** a maintainer inspects the target registry
- **THEN** it includes a `demo-frontend` target for `apps/demo`
- **AND** it includes a `demo-backend` target for `apps/demo-api`
- **AND** it includes an `agenthub-platform` target for AgentHub platform code
- **AND** each target includes target ID, name, type, root, allowed paths,
  denied paths, commands, allowed agents, and approval/platform-mode metadata
  when applicable.

#### Scenario: Demo backend target is resolved

- **WHEN** the system resolves the `demo-backend` target
- **THEN** the target type is `backend`
- **AND** the root is `apps/demo-api`
- **AND** the base URL is `http://127.0.0.1:5174`
- **AND** ordinary backend app work is allowed only inside the demo backend
  target's allowed paths
- **AND** `apps/api` is denied for ordinary demo backend work.

#### Scenario: AgentHub platform target is resolved

- **WHEN** the system resolves the `agenthub-platform` target
- **THEN** the target type is `platform`
- **AND** the target requires explicit platform mode
- **AND** the target requires approval before adapter execution
- **AND** the target uses stricter validation than ordinary app targets.

### Requirement: Target-aware Contract Planning

The system MUST generate target-aware app contracts and tasks for bounded
full-stack app requests by referencing target IDs and registry-resolved
metadata.

#### Scenario: Orchestrator plans a mini CRM request

- **WHEN** the user asks for a supported mini CRM contacts app
- **THEN** Orchestrator creates an app contract with `frontendTargetId` set to
  `demo-frontend`
- **AND** the app contract has `backendTargetId` set to `demo-backend`
- **AND** the app contract uses the demo backend base URL from the target
  registry
- **AND** generated frontend and backend tasks reference their target IDs
- **AND** generated tasks also include resolved safe paths for compatibility
  with the existing execution path.

#### Scenario: Unsupported target operation is requested

- **WHEN** a user asks for an operation that cannot be mapped to a supported
  target
- **THEN** the system MUST NOT silently execute an adapter run
- **AND** it MUST ask for clarification or return an honest unsupported
  response.

### Requirement: Target-aware Instructions

The system MUST build role instructions from target registry metadata instead
of scattered hardcoded paths and URLs.

#### Scenario: Frontend Agent instruction is built for full-stack app work

- **WHEN** a frontend task targets `demo-frontend` and references a backend
  target
- **THEN** the instruction tells the agent to work only inside the
  `demo-frontend` allowed paths
- **AND** the instruction includes the registry-resolved backend base URL
- **AND** the instruction tells the agent not to call the AgentHub platform API
  for generated app data.

#### Scenario: Backend Agent instruction is built for app backend work

- **WHEN** a backend task targets `demo-backend`
- **THEN** the instruction tells the agent to work only inside the
  `demo-backend` allowed paths
- **AND** the instruction tells the agent not to modify `apps/api`
- **AND** the instruction includes the demo backend validation command from the
  target registry when available.

#### Scenario: Platform maintenance instruction is built

- **WHEN** a task targets `agenthub-platform`
- **THEN** the instruction identifies the task as platform maintenance
- **AND** it includes stricter validation expectations
- **AND** it states that platform mode and approval are required.

### Requirement: Permissioned Execution Boundaries

The system MUST enforce target-aware execution boundaries for adapter tasks and
MUST preserve protected path guardrails.

#### Scenario: Ordinary backend task attempts platform mutation

- **WHEN** an ordinary app backend task targets `demo-backend`
- **AND** the task or resulting diff attempts to modify `apps/api`
- **THEN** the system MUST report a target policy violation
- **AND** the system MUST NOT claim unrestricted backend success.

#### Scenario: Frontend task edits outside allowed paths

- **WHEN** a frontend task targets `demo-frontend`
- **AND** the resulting diff includes files outside the target's allowed paths
- **THEN** review MUST report an allowed-path violation
- **AND** protected paths such as `.env`, `.git`, `node_modules`, and `secrets`
  MUST remain denied.

#### Scenario: Platform maintenance is explicitly requested

- **WHEN** a user explicitly requests AgentHub platform maintenance mode
- **THEN** the system MAY create a task targeting `agenthub-platform`
- **AND** the task MUST require approval before adapter execution
- **AND** the task MUST use the platform target's stricter validation
  expectations.

### Requirement: Target-aware Review And QA

The system MUST review diffs and app contracts against target registry policy.

#### Scenario: Full-stack diff is reviewed

- **WHEN** a full-stack app diff is reviewed
- **THEN** review checks that changed frontend files are inside the frontend
  target allowed paths
- **AND** review checks that changed backend files are inside the backend
  target allowed paths
- **AND** review checks that denied paths are not modified
- **AND** review checks that contract target IDs match task target IDs.

#### Scenario: Frontend calls wrong backend base URL

- **WHEN** a frontend diff calls a backend base URL that does not match the
  registry-resolved backend target base URL
- **THEN** review MUST report a backend-base mismatch
- **AND** the finding SHOULD identify the expected target base URL.

#### Scenario: Final P6 mini CRM path is reviewed through P7

- **WHEN** the P6 mini CRM vertical slice is rehearsed through target registry
  metadata
- **THEN** review passes when the accumulated diff touches only allowed
  `demo-frontend` and `demo-backend` paths
- **AND** the frontend uses the registry-resolved `demo-backend` base URL
- **AND** mock deploy remains mock-labeled.

### Requirement: P7 Baseline Preservation

The system MUST preserve the P4/P5/P6 local single-user workspace baseline
while adding target registry and permissioned execution.

#### Scenario: P7 freeze review is performed

- **WHEN** P7 is reviewed for freeze
- **THEN** the P6 mini CRM vertical slice still works through target registry
  metadata
- **AND** `CodexAdapter`, `ClaudeCodeAdapter`, and `ScriptedMockAdapter` remain
  valid adapters
- **AND** ordinary app tasks remain bounded to demo targets
- **AND** platform-code mutation is blocked or approval-gated unless platform
  mode is explicit
- **AND** P7 does not claim multi-user IM, production deployment, Docker
  sandboxing, PR creation, unrestricted repository editing, distributed
  scheduling, or arbitrary SaaS generation.
