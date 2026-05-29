## Why

P15b proved AgentHub can use a real LLM planner provider, real coding agents,
validated builds, preview, and local staging deploy. P16 then made Planner,
Frontend, and Backend provider choices configurable at runtime.

The next severe product gap is routing: normal messages such as `你好` are
still blocked by legacy deterministic/demo/signal routing before they reach
LLM reasoning. AgentHub should behave like a conversational coding assistant:
friendly chat gets an assistant response, programming requests become validated
plans, unclear requests ask clarification, unsafe requests are refused or sent
through approval, and follow-ups use session context.

## What Changes

- Add a `ConversationOutcome` contract for message routing decisions:
  `assistant_reply`, `task_plan`, `clarification`, `refusal`,
  `approval_required`, and `unsupported`.
- Use one LLM provider call for Orchestrator routing and planning: the provider
  returns a single `ConversationOutcome`; `task_plan` outcomes carry a
  PlanDraft, and non-task outcomes never create tasks.
- Clarify the runtime boundary: the Conversation Router uses the configured
  Planner LLM runtime, while frontend/backend/review tasks use their configured
  coding agent runtimes after a validated `task_plan`.
- Make no-mention and `@orchestrator` messages route to an LLM-first
  Orchestrator.
- Keep `@frontend`, `@backend`, `@qa`, and `@review` as explicit assignment
  shortcuts.
- Retire legacy signal-word gates from the primary route. Helpers such as
  `_is_safe_demo_frontend_request`, `_is_safe_external_frontend_request`,
  `_is_passthrough_frontend_request`, and `_is_unsupported_broad_request` must
  not block or rewrite an LLM `task_plan` outcome.
- Move deterministic demo planners to fallback rather than primary routing
  gate.
- Add a conversational reply path so greetings and normal chat create
  `orchestrator` sender messages and no TaskRun.
- Preserve PlanValidator, Target Registry, Scheduler, Guardrails, runtime
  config, provider evidence, and deterministic fallback for executable work.
- Record both planner provider/config evidence and coding agent provider/config
  evidence in task/run/mission trace surfaces where applicable.
- Extend follow-up routing so LLM reasoning is not limited to empty sessions.
- Add an audited friendly fallback: pure chat gets a friendly reply; clear safe
  frontend coding intent may create a fallback passthrough frontend task;
  backend/platform/high-risk/ambiguous requests ask clarification or require
  approval.
- Rehearse greetings, capability chat, coding request, legacy signal bypass,
  unsafe request, follow-up, and planner disabled paths.

## Capabilities

### New Capabilities

- `conversational-routing`: LLM-first Orchestrator message routing that can
  produce assistant replies, task plans, clarification questions, refusals,
  approval-required outcomes, unsupported outcomes, and friendly fallback.

### Modified Capabilities

- Existing planning and task creation become downstream of a validated
  conversation outcome for no-mention and `@orchestrator` messages.

## Impact

- Backend:
  - adds the conversation outcome schema and router boundary;
  - routes no-mention and `@orchestrator` messages through LLM-first
    Orchestrator;
  - persists assistant reply / clarification / refusal messages without
    creating TaskRuns;
  - validates executable plans before task creation and sends LLM `task_plan`
    outcomes directly into schema validation plus PlanValidator, not legacy
    signal gates;
  - keeps deterministic demo planner as fallback.
- Frontend:
  - displays assistant replies and clarification/refusal messages through the
    existing chat stream;
  - no new major UI surface is required for P17.
- Runtime and security:
  - keeps Planner provider/config separate from Frontend, Backend, and Review
    coding agent provider/config;
  - uses P16 Agent Runtime Configuration where available: the Conversation
    Router resolves the Planner runtime, and scheduled frontend/backend/review
    tasks resolve their own runtime agent providers;
  - ensures normal chat messages never invoke Claude Code, Codex, or any other
    coding agent runtime;
  - records `plannerProvider` and `codingAgentProvider` evidence in mission
    trace and run metadata where applicable;
  - defers a full model settings UI, while preserving the future settings model
    for Planner LLM, Frontend coding agent, Backend coding agent, and Review
    agent provider/model choices;
  - executable plans still pass PlanValidator, Target Registry, scheduler, and
    guardrails;
  - unsafe requests are refused or routed to approval;
  - real LLM failures are recorded honestly and do not fake success.
