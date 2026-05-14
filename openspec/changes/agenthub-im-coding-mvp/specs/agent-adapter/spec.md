## ADDED Requirements

### Requirement: Minimal adapter lifecycle
The system MUST define a unified adapter interface with `getCapabilities`, `createRun`, `streamEvents`, `interrupt`, `approve`, `collectArtifacts`, and `cleanup`.

#### Scenario: Backend starts an adapter run
- **GIVEN** a task is assigned to an enabled agent
- **WHEN** the backend starts execution
- **THEN** it reads adapter capabilities
- **AND** calls `createRun` for the selected adapter
- **AND** consumes adapter events through `streamEvents`

### Requirement: Adapter capabilities
The system MUST expose AdapterCapabilities for each adapter with streaming, interrupt, approval, file edit, shell command, diff artifact, preview artifact, network, and optional max runtime support flags.

#### Scenario: Orchestrator checks adapter capabilities
- **GIVEN** an agent is configured with an adapter type
- **WHEN** the orchestrator assigns a task to that agent
- **THEN** the backend can inspect the adapter capability descriptor
- **AND** avoids assuming unsupported adapter behavior

### Requirement: CodexAdapter local CLI execution
The system MUST include `CodexAdapter` as the only P0 real coding adapter, implemented through local CLI invocation.

#### Scenario: CodexAdapter modifies code in session worktree
- **GIVEN** a TaskRun has a Session worktree
- **WHEN** `CodexAdapter` executes the task successfully
- **THEN** the adapter invokes the local Codex CLI inside the session worktree
- **AND** it can produce real file modifications collected later by git diff

#### Scenario: Codex API wrapper is not used in P0
- **GIVEN** `CodexAdapter` is configured for P0
- **WHEN** an adapter run starts
- **THEN** the system uses local CLI invocation
- **AND** does not require an API or cloud task wrapper

### Requirement: ScriptedMockAdapter fallback
The system MUST include `ScriptedMockAdapter` that executes controlled scripts which make real Vite React demo repo file changes.

#### Scenario: Fallback completes after real adapter failure
- **GIVEN** `CodexAdapter` fails for a demo task
- **WHEN** the user retries with fallback
- **THEN** `ScriptedMockAdapter` executes a controlled script in the session worktree
- **AND** the Vite React demo repo contains real file changes after the fallback completes

### Requirement: Unified adapter events
The system MUST normalize adapter output into `message.delta`, `task.state`, `approval.requested`, `artifact.diff.ready`, `artifact.preview.ready`, `artifact.deploy.ready`, `error`, and `completed` events.

#### Scenario: Adapter emits progress
- **GIVEN** an adapter run is active
- **WHEN** the adapter reports progress, approval, artifact, failure, or completion
- **THEN** the backend persists a TaskRunEvent for the normalized event
- **AND** emits the corresponding event type to the session stream

### Requirement: Adapter cleanup
The system MUST clean up adapter-owned foreground or background resources after completion, failure, or interruption.

#### Scenario: Interrupted adapter is cleaned up
- **GIVEN** an adapter run is streaming
- **WHEN** the user interrupts the run
- **THEN** the backend calls `interrupt`
- **AND** calls `cleanup` before marking cleanup complete

### Requirement: P1 adapter deferral
The system MUST keep ClaudeCodeAdapter, HumanAgentAdapter, and Codex API/cloud task wrappers outside P0.

#### Scenario: P0 adapter list is loaded
- **GIVEN** the P0 system starts
- **WHEN** available adapters are registered
- **THEN** only `CodexAdapter` and `ScriptedMockAdapter` are required for the demo path
- **AND** P1 adapters are not required for P0 acceptance
