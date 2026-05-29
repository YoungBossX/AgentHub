## ADDED Requirements

### Requirement: ConversationOutcome Schema
The system MUST define a structured conversation outcome contract for
Orchestrator message routing.

#### Scenario: Outcome types are explicit
- **WHEN** the router classifies a message
- **THEN** the outcome MUST use one of `assistant_reply`, `task_plan`,
  `clarification`, `refusal`, `approval_required`, or `unsupported`.

#### Scenario: Outcome metadata is auditable
- **WHEN** a conversation outcome is produced
- **THEN** it MUST include reply text when applicable, plan draft when
  applicable, risk level, reason, planner provider metadata, validation result,
  and fallback or error metadata when applicable.

#### Scenario: Executable outcome is validated
- **WHEN** the outcome type is `task_plan`
- **THEN** the plan draft MUST pass schema validation and PlanValidator before
  tasks are persisted or TaskRuns are created.

#### Scenario: Single provider call returns outcome
- **WHEN** P17 routes a no-mention or `@orchestrator` message through the LLM
  Orchestrator
- **THEN** the provider MUST return a single `ConversationOutcome`
- **AND** `task_plan` MUST carry the PlanDraft candidate
- **AND** non-task outcomes MUST NOT create tasks.

### Requirement: Planner And Coding Agent Runtime Separation
The system MUST keep the Conversation/Planner LLM runtime separate from
Frontend, Backend, and Review coding agent runtimes.

#### Scenario: Conversation router uses planner runtime
- **WHEN** a no-mention or `@orchestrator` message enters conversational
  routing
- **THEN** the Conversation Router MUST use the configured Planner runtime
- **AND** it MUST NOT use ClaudeCodeAdapter, CodexAdapter, or any other coding
  agent as the normal conversation entrypoint.

#### Scenario: Planner LLM owns intent and plan drafting
- **WHEN** the Conversation Router processes a user message
- **THEN** the Planner LLM MUST decide whether the outcome is
  `assistant_reply`, `task_plan`, `clarification`, `refusal`, or
  `approval_required`
- **AND** it MUST generate a PlanDraft only for `task_plan` outcomes.

#### Scenario: Coding agents run only after validated task plan
- **WHEN** a `task_plan` outcome has passed ConversationOutcome schema
  validation, PlanDraft schema validation, and PlanValidator
- **THEN** Scheduler-created Frontend, Backend, QA, and Review tasks MUST use
  configured runtime agent providers for their roles
- **AND** those coding agents MUST be responsible for code reading/editing,
  target-scoped commands, and diff/build/review/preview/deploy evidence.

#### Scenario: Normal chat does not invoke coding agents
- **WHEN** a user sends normal chat such as `你好` or `你能做什么`
- **THEN** the system MUST NOT invoke Claude Code, Codex, ScriptedMock, or
  another coding agent runtime
- **AND** it MUST create no TaskRun.

#### Scenario: Mission trace distinguishes planner and coding providers
- **WHEN** conversational routing and any downstream task execution produce
  mission trace or run evidence
- **THEN** the evidence MUST distinguish `plannerProvider` from
  `codingAgentProvider` where applicable
- **AND** it MUST preserve the configured provider/runtime source used for each
  stage.

#### Scenario: Runtime settings model remains separated
- **WHEN** AgentHub exposes or consumes runtime configuration in P17
- **THEN** Planner LLM provider/model configuration MUST remain separate from
  Frontend coding agent, Backend coding agent, and Review agent
  provider/model configuration
- **AND** P17 MAY use existing P16 runtime configuration where available
- **AND** it MUST NOT introduce arbitrary shell-command agents.

### Requirement: LLM-first Message Router
The system MUST route normal Orchestrator messages through LLM-first intent
classification before deterministic demo planning.

#### Scenario: No mention routes to LLM Orchestrator
- **WHEN** a user sends a message without an explicit role mention
- **THEN** the message MUST route to the LLM Orchestrator by default.

#### Scenario: Orchestrator mention routes to LLM Orchestrator
- **WHEN** a user sends a message with `@orchestrator`
- **THEN** the message MUST route to the LLM Orchestrator.

#### Scenario: Explicit assignment shortcuts remain
- **WHEN** a user sends `@frontend`, `@backend`, `@qa`, or `@review`
- **THEN** the system MUST preserve those explicit assignment modes.

#### Scenario: Deterministic planner is fallback
- **WHEN** no-mention or `@orchestrator` routing is available
- **THEN** deterministic demo planning MUST NOT be the primary gate
- **AND** it MUST be used only as a safe fallback path.

#### Scenario: Legacy signal gates are not primary
- **WHEN** the LLM Orchestrator returns `task_plan`
- **THEN** `_is_safe_demo_frontend_request`,
  `_is_safe_external_frontend_request`, `_is_passthrough_frontend_request`, and
  `_is_unsupported_broad_request` MUST NOT block, reject, or rewrite the plan
- **AND** the plan MUST flow directly into ConversationOutcome schema
  validation, PlanDraft schema validation, and PlanValidator.

### Requirement: Conversational Reply Path
The system MUST support normal assistant conversation without creating coding
tasks.

#### Scenario: Greeting gets assistant reply
- **WHEN** the user sends `你好` or an equivalent normal greeting
- **THEN** the system MUST create an `orchestrator` sender reply message
- **AND** it MUST NOT create a Task or TaskRun.

#### Scenario: Capability chat gets assistant reply
- **WHEN** the user sends `你能做什么`
- **THEN** the system MUST create an `orchestrator` sender reply message
- **AND** it MUST NOT create a Task or TaskRun.

#### Scenario: Pure chat stays in chat stream
- **WHEN** an `assistant_reply` outcome is produced
- **THEN** the reply MUST appear in the session message stream
- **AND** SSE recovery MUST remain compatible where message events are emitted.

#### Scenario: No new sender type
- **WHEN** P17 creates assistant replies, clarification questions, refusals,
  approval explanations, or unsupported explanations
- **THEN** those messages MUST use the existing `orchestrator` sender type.

### Requirement: Task Plan Path
The system MUST convert programming requests into validated executable plans.

#### Scenario: Programming request creates validated plan
- **WHEN** the user asks for a bounded programming change
- **THEN** the LLM Orchestrator MUST produce a `task_plan` outcome
- **AND** the plan MUST be validated before task creation.

#### Scenario: PlanValidator remains authoritative
- **WHEN** an LLM-generated plan references targets, files, roles,
  dependencies, capabilities, approvals, or validation commands
- **THEN** PlanValidator and Target Registry MUST reject unsafe or unsupported
  values before execution.

#### Scenario: No hardcoded demo primary path
- **WHEN** the user asks for a reasonable frontend coding task such as a game
  or UI feature
- **THEN** the primary route MUST NOT depend on a hardcoded Breakout, login, or
  button-text regex/template path.

#### Scenario: LLM task plan enters PlanValidator directly
- **WHEN** a `task_plan` outcome contains a PlanDraft
- **THEN** the system MUST run ConversationOutcome schema validation, PlanDraft
  schema validation, and PlanValidator
- **AND** it MUST NOT run legacy safe/unsupported signal-word gates before
  PlanValidator.

### Requirement: Clarification Refusal And Approval Outcomes
The system MUST distinguish unclear, unsafe, and high-risk requests before
execution.

#### Scenario: Ambiguous request asks clarification
- **WHEN** the user request is too ambiguous to plan safely
- **THEN** the system MUST create an `orchestrator` clarification reply
- **AND** it MUST NOT create executable tasks.

#### Scenario: Unsafe target-outside request is refused
- **WHEN** the user asks AgentHub to modify protected paths, system paths, or
  unregistered external paths
- **THEN** the system MUST create an `orchestrator` refusal outcome
- **AND** it MUST NOT create executable tasks.

#### Scenario: High-risk platform request requires approval
- **WHEN** the user asks for platform maintenance or another high-risk action
- **THEN** the outcome MUST be `approval_required` or an equivalent approval
  path
- **AND** executable work MUST NOT bypass platform mode, approval, Target
  Registry, or guardrails.

### Requirement: Follow-up Routing
The system MUST route follow-up messages through the same LLM Orchestrator
contract using session context.

#### Scenario: Follow-up includes workspace context
- **WHEN** the user sends a follow-up after prior execution
- **THEN** the router input MUST include recent messages, CanonicalSharedContext,
  mission trace, selected artifact context when present, latest diff/review/
  build/preview/deploy evidence, active tasks, and current goal.

#### Scenario: LLM routing is not empty-session only
- **WHEN** the session already has tasks or artifacts
- **THEN** no-mention and `@orchestrator` follow-ups MUST still be eligible for
  LLM routing.

#### Scenario: Follow-up executable work is validated
- **WHEN** a follow-up produces a task plan
- **THEN** the plan MUST pass the same validation and guardrails as a first
  request.

### Requirement: Friendly Fallback
The system MUST fail conversationally and honestly when LLM routing is
disabled or unavailable.

#### Scenario: Planner disabled gives friendly fallback
- **WHEN** LLM routing is disabled and the user sends normal chat
- **THEN** the system MUST return an honest `orchestrator` fallback reply
- **AND** it MUST NOT return a demo-boundary rejection.

#### Scenario: Planner disabled may passthrough safe frontend coding
- **WHEN** LLM routing is disabled and the user sends a clear safe frontend
  coding request
- **THEN** the system MAY create one fallback passthrough frontend task
- **AND** the plan metadata MUST include `plannerSource: fallback`
- **AND** the task MUST still pass Target Registry and PlanValidator policy.

#### Scenario: Planner disabled does not passthrough risky requests
- **WHEN** LLM routing is disabled and the request is backend, platform,
  high-risk, ambiguous, target-outside, or unsafe
- **THEN** the system MUST ask clarification, require approval, refuse, or
  report unsupported honestly
- **AND** it MUST NOT silently create a frontend task.

#### Scenario: Planner unavailable records error
- **WHEN** LLM routing fails due to auth, quota, timeout, invalid output, or
  runtime error
- **THEN** the system MUST record normalized error metadata
- **AND** it MUST NOT claim LLM success.

#### Scenario: Safe deterministic fallback remains
- **WHEN** LLM routing is unavailable and the message clearly matches a known
  safe deterministic coding flow
- **THEN** the system MAY use deterministic fallback
- **AND** fallback evidence MUST be explicit.

### Requirement: P17 Rehearsal And Freeze Review
The system MUST verify conversational routing without regressing prior
AgentHub baselines.

#### Scenario: Greeting rehearsal
- **WHEN** P17 rehearsal sends `你好`
- **THEN** the result MUST be `orchestrator` assistant reply
- **AND** no Task or TaskRun MUST be created.

#### Scenario: Capability rehearsal
- **WHEN** P17 rehearsal sends `你能做什么`
- **THEN** the result MUST be `orchestrator` assistant reply
- **AND** no Task or TaskRun MUST be created.

#### Scenario: Coding rehearsal
- **WHEN** P17 rehearsal sends `帮我做打砖块`
- **THEN** the result MUST be an LLM `task_plan` or an honest provider
  failure
- **AND** the system MUST NOT use a hardcoded Breakout planner template as the
  primary success path
- **AND** legacy signal gates MUST NOT block the LLM task plan.

#### Scenario: Disabled planner fallback rehearsal
- **WHEN** LLM routing is disabled and P17 rehearsal sends clear safe frontend
  coding intent
- **THEN** the system MAY create an audited fallback passthrough frontend task
  with `plannerSource: fallback`.

#### Scenario: Disabled planner chat rehearsal
- **WHEN** LLM routing is disabled and P17 rehearsal sends pure chat
- **THEN** the system MUST return a friendly `orchestrator` reply
- **AND** no task MUST be created.

#### Scenario: Unsafe request rehearsal
- **WHEN** P17 rehearsal asks to modify a protected system path
- **THEN** the result MUST be refusal or approval-required according to policy
- **AND** no unsafe task MUST execute.

#### Scenario: Baselines remain intact
- **WHEN** P17 freeze review runs validation
- **THEN** P6-P16 baselines for runtime config, target registry, planner,
  scheduler, recovery, external workspaces, diff, review, build, preview, and
  staging deploy MUST remain intact.
