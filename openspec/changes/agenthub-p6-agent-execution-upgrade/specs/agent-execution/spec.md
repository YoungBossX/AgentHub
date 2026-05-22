## ADDED Requirements

### Requirement: P6 Execution Capability Positioning

The system MUST upgrade AgentHub's practical agent execution capability while
preserving the P4/P5 local single-user workspace baseline and the existing
`CodexAdapter`, `ClaudeCodeAdapter`, and `ScriptedMockAdapter`.

#### Scenario: P6 scope is reviewed

- **WHEN** a maintainer reviews the P6 change
- **THEN** the change describes P6 as an agent execution capability upgrade
- **AND** it preserves the existing diff, review, preview, artifact card, and
  mock deploy flow
- **AND** it does not claim arbitrary SaaS generation, production deploy,
  multi-user IM, provider marketplace, Docker sandbox, or PR creation.

### Requirement: Message Routing And Direct Agent Assignment

The system MUST route messages without explicit role mentions to Orchestrator /
Manager by default, and MUST treat explicit role mentions as higher-priority
assignment instructions. The system MUST auto-start Orchestrator-created safe
demo-target coding tasks through the existing TaskRun path.

#### Scenario: User sends a message without explicit role mention

- **WHEN** the user sends a normal message without `@orchestrator`,
  `@frontend`, `@backend`, `@qa`, or `@review`
- **THEN** the system routes the message to Orchestrator / Manager
- **AND** Orchestrator can answer conversationally, create role tasks, generate
  a contract or task graph, ask for clarification, or reject unsupported
  requests honestly
- **AND** the system does not silently execute an adapter run for another role.

#### Scenario: Orchestrator creates a safe demo coding task

- **WHEN** Orchestrator creates a safe demo-target frontend coding task from a
  normal or `@orchestrator` message
- **THEN** the system automatically starts a TaskRun through the existing
  TaskRun execution path
- **AND** the TaskRun uses the configured existing code adapter
- **AND** the task instruction preserves the user's original request and safe
  demo target boundaries.

#### Scenario: User selects an artifact without explicit role mention

- **WHEN** the user sends a follow-up message with selected artifact context but
  no explicit role mention
- **THEN** the selected artifact is included in Orchestrator context
- **AND** the selected artifact does not bypass Orchestrator by default
- **AND** Orchestrator decides the next task, clarification, or rejection.

#### Scenario: User explicitly mentions a coding agent

- **WHEN** the user sends a supported direct mention such as `@frontend update
  the demo app hero copy` or `@backend add a contacts endpoint to the demo API`
- **THEN** the system creates an executable task assigned to the mentioned role
- **AND** the task preserves the user's original request
- **AND** the task can be started through the existing TaskRun path
- **AND** the task is bounded to safe target directories for that role.

#### Scenario: User explicitly mentions Orchestrator

- **WHEN** the user sends a message with `@orchestrator`
- **THEN** the system routes the message to Orchestrator / Manager
- **AND** Orchestrator applies the same decision policy as the default route.

#### Scenario: User directly mentions an unsupported role request

- **WHEN** the user sends a direct mention request that cannot be safely bounded
- **THEN** the system does not claim execution success
- **AND** it either returns an honest unsupported response or creates a
  clarification task
- **AND** it does not start an adapter run with unrestricted workspace access.

### Requirement: Session Context Pack

The system MUST construct a session-scoped context pack for agent execution that
includes current goal, recent messages, execution ledger, selected artifact,
latest diff metadata, changed files, preview/deploy status, and relevant
contract data when present.

#### Scenario: Agent instruction is built for a follow-up task

- **WHEN** an executable task is started after prior artifacts exist in the same
  session
- **THEN** the adapter instruction includes a structured context pack for that
  session
- **AND** the pack identifies selected artifact context when the user selected
  one
- **AND** the pack includes latest diff, changed files, preview health, mock
  deploy status, and current goal when available
- **AND** the pack excludes records from other sessions.

### Requirement: Role-Based Instruction Builder

The system MUST build role-specific adapter instructions for frontend, backend,
QA/review, and manager tasks while preserving safety boundaries and meaningful
user intent.

#### Scenario: Frontend instruction is generated

- **WHEN** a frontend executable task starts
- **THEN** the instruction targets the demo frontend work area
- **AND** it includes the original user request and relevant session context
- **AND** it preserves protected-path and dependency-install guardrails
- **AND** it is not rewritten into an unrelated login-page-only instruction.

#### Scenario: Backend instruction is generated

- **WHEN** a backend executable task starts
- **THEN** the instruction targets the safe demo backend work area
- **AND** it includes relevant contract and frontend integration context
- **AND** it does not allow free mutation of the AgentHub platform backend.

#### Scenario: QA or review instruction is generated

- **WHEN** a QA or review executable task starts
- **THEN** the instruction focuses on diff, contract, risk, changed files, and
  evidence
- **AND** the resulting review remains advisory unless a later explicit policy
  introduces blocking gates.

### Requirement: Demo Backend Target

The system MUST provide or plan a safe demo backend target for Backend Agent
work so backend execution can be evaluated without mutating the AgentHub control
plane backend.

#### Scenario: Backend Agent task is created

- **WHEN** the system creates a backend execution task
- **THEN** the task targets the demo backend target, such as `apps/demo-api`
- **AND** protected platform paths remain guarded
- **AND** the generated diff is collected through the existing artifact flow.

### Requirement: Contract-First Orchestrator

The system MUST support contract-first orchestration for bounded full-stack mini
app requests, producing a shared app contract before frontend and backend
implementation tasks.

#### Scenario: Orchestrator receives a bounded mini app request

- **WHEN** the user asks for a supported mini app such as todo, notes, or mini
  CRM contacts, either with `@orchestrator` or with no explicit role mention
- **THEN** the system creates a structured app contract
- **AND** the contract defines goal, entities, API endpoints, UI screens,
  target directories, and acceptance criteria
- **AND** backend and frontend tasks reference the same contract
- **AND** same-session write tasks remain serial unless conflict handling exists.

### Requirement: Bounded Full-Stack Vertical Slice

The system MUST verify one bounded full-stack mini app path from user
requirement through contract, backend task, frontend task, QA/review, diff,
preview, and mock deploy.

#### Scenario: Mini app vertical slice is rehearsed

- **WHEN** P6 E2E rehearsal runs a supported mini app request
- **THEN** the evidence records the requirement, contract, task IDs, task run
  IDs, adapter types, changed files, diff artifacts, review artifacts, preview
  status, and mock deployment status
- **AND** real Claude/Codex execution is documented only if actually run
- **AND** fallback or scripted behavior is labeled honestly
- **AND** mock deploy remains labeled as mock.

### Requirement: Execution Safety And Honesty

The system MUST fail honestly or ask for clarification for unsupported requests,
and MUST preserve safe target boundaries for all direct and orchestrated
execution tasks.

#### Scenario: User requests unsupported arbitrary application generation

- **WHEN** the user asks for an unsupported arbitrary SaaS, ambiguous
  assignment, production deploy, payment/auth/multi-tenant system, or
  unrestricted platform-code mutation
- **THEN** the system does not create an unrestricted coding task
- **AND** it explains the unsupported boundary or asks for a bounded target
- **AND** it preserves the P4/P5 baseline behavior.
