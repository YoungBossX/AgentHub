## ADDED Requirements

### Requirement: P5 Workspace Positioning

The system MUST evolve AgentHub into a local single-user IM-style multi-agent
coding workspace v1 while preserving the frozen final demo baseline.

#### Scenario: P5 baseline is reviewed

- **WHEN** a maintainer reviews the P5 OpenSpec change
- **THEN** the change describes AgentHub as local and single-user for P5
- **AND** it preserves the verified requirement -> plan -> agent execution ->
  diff -> preview -> mock deploy loop
- **AND** it does not claim full multi-user IM, real deploy, provider
  marketplace, Docker sandbox, or external IM integration.

### Requirement: Agent Contacts And Workflow Modes

The system MUST expose built-in agents as IM-style contacts and MUST support
direct-chat and group-workflow visual modes without adding real multi-user
accounts.

#### Scenario: User opens the P5 workspace

- **WHEN** the workspace UI loads
- **THEN** it shows built-in agents with avatar, name, role, adapterType,
  capability tags, and status
- **AND** it provides direct-chat and group-workflow visual modes
- **AND** those modes are represented as local single-user product modes.

### Requirement: Execution Ledger

The system MUST persist a session-scoped execution ledger for current goal,
active agents, latest plan/task/run/diff/review/preview/deploy, changed files,
and review summary.

#### Scenario: Session is reloaded after agent execution

- **WHEN** the user reloads a session after a workflow has produced artifacts
- **THEN** the execution ledger can be read for that session
- **AND** it references persisted messages, tasks, runs, artifacts, and changed
  files
- **AND** it does not expose context from another session.

### Requirement: Review Agent Workflow

The system MUST create a review artifact after a coding diff is produced, and
the P5 v1 review MUST be non-blocking by default.

#### Scenario: Coding task produces a diff

- **WHEN** a coding TaskRun completes and a diff artifact is available
- **THEN** a Review Agent task or review workflow is run
- **AND** a review artifact is persisted with `passed`, `warning`, or `failed`
  status
- **AND** the review artifact links to the reviewed diff
- **AND** preview and mock deploy remain available unless a later explicit
  policy changes the non-blocking default.

### Requirement: Multi-Agent Execution Trace

The system MUST show Manager, Coding Agent, Review Agent, QA/Preview/Deploy
services, and produced artifacts as a visible execution trace.

#### Scenario: User inspects a completed workflow

- **WHEN** a user opens the workflow trace
- **THEN** they can see Manager planning, coding execution, diff collection,
  review, preview, and mock deploy steps
- **AND** each step links to relevant messages, task runs, or artifact cards
- **AND** service steps are labeled as services rather than autonomous agents.

### Requirement: Dynamic Manager Planner V1

The system MUST support a bounded dynamic Manager planner for frontend change
intents and MUST preserve deterministic fallback planning.

#### Scenario: Manager receives a supported frontend change request

- **WHEN** the Manager planner handles a supported frontend change intent
- **THEN** it emits a structured task graph with bounded task count, allowed
  roles, allowed target files, and dependency depth
- **AND** same-session write tasks remain serial
- **AND** invalid or unsupported planner output falls back to deterministic
  planning or fails safely.

### Requirement: Artifact Message Cards V2

The system MUST render Diff, Preview, Review, and Mock Deploy as inline message
cards and MUST support session-scoped artifact references for follow-up
interaction.

#### Scenario: User references a prior artifact

- **WHEN** the user selects or references a prior artifact in a follow-up
  interaction
- **THEN** the reference is validated against the current session
- **AND** the follow-up context identifies the selected artifact
- **AND** mock deploy artifacts remain labeled as mock rather than production
  deployment.

### Requirement: P5 Evidence Discipline

The system MUST document real Claude/Codex execution only when it was actually
run and MUST preserve `CodexAdapter`, `ClaudeCodeAdapter`, and
`ScriptedMockAdapter`.

#### Scenario: P5 E2E rehearsal is recorded

- **WHEN** P5 E2E evidence is documented
- **THEN** real adapter execution is labeled with the actual adapter used
- **AND** fallback or scripted behavior is labeled as fallback or scripted
- **AND** the current diff, preview, and mock deploy flow remains intact.
