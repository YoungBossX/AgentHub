## Context

AgentHub has accumulated the execution foundations needed for an LLM-first
coding assistant: real planner provider support, runtime provider config,
target registry, PlanValidator, scheduler, task locks, recovery, artifacts,
mission trace, and staging deploy evidence.

The current routing boundary is still too demo-shaped. `planning.py` can parse
mentions and construct task plans, but a plain conversational message such as
`你好` can be rejected or mishandled before the LLM Orchestrator has a chance to
decide whether it is chat, coding work, clarification, refusal, or approval.
P17 moves intent selection into a typed conversation outcome while preserving
all existing execution validation.

The implementation must explicitly retire legacy signal-word helpers from the
primary Orchestrator path. Existing helpers such as
`_is_safe_demo_frontend_request`, `_is_safe_external_frontend_request`,
`_is_passthrough_frontend_request`, and `_is_unsupported_broad_request` may
remain available only after LLM routing is disabled/unavailable or invalid and
the system has entered an auditable fallback branch.

## Goals / Non-Goals

**Goals:**

- Let no-mention and `@orchestrator` messages reach an LLM-first Orchestrator.
- Support assistant replies for greetings and normal chat.
- Support validated task plans for programming requests.
- Support clarification, refusal, approval-required, and unsupported outcomes.
- Let follow-up messages use current session context, mission trace, artifact
  references, and latest evidence.
- Keep Conversation/Planner LLM runtime separate from Frontend, Backend, and
  Review coding agent runtimes.
- Record both planner provider evidence and coding agent provider evidence in
  mission trace / run metadata where applicable.
- Preserve deterministic fallback without letting it block normal chat.
- Ensure an LLM `task_plan` outcome flows directly to schema validation plus
  PlanValidator, without a second pass through legacy signal-word gates.

**Non-Goals:**

- Removing Target Registry, PlanValidator, scheduler, recovery, or guardrails.
- Replacing ClaudeCodeAdapter, CodexAdapter, or ScriptedMockAdapter.
- Treating Claude Code or Codex as the universal normal-chat entrypoint.
- Building the full model/provider settings UI; P17 may define the separation
  model and use existing P16 runtime config where available.
- Adding provider marketplace, artifact editor, production deploy, or
  multi-user IM.
- Running real Claude/Codex during the planning task.

## Decisions

### Decision: ConversationOutcome Is The Router Contract

The router should return a typed `ConversationOutcome` instead of directly
creating tasks or rejecting text through legacy routing. The outcome should
include:

- `outcomeType`;
- `reply`;
- `planDraft`;
- `riskLevel`;
- `reason`;
- `plannerProvider`;
- `validationResult`;
- optional fallback/error metadata.

Executable `task_plan` outcomes are the only outcomes that may proceed to task
creation, and only after validation.

### Decision: LLM Router And Planner Are One Call In P17

P17 should not split routing and planning into two provider calls. The
Orchestrator provider call returns exactly one `ConversationOutcome`:

- `assistant_reply` carries reply text and creates no task;
- `clarification` carries a question/reply and creates no task;
- `refusal` carries refusal text and creates no task;
- `approval_required` carries reason/risk/approval metadata and does not create
  executable work until the approval path allows it;
- `unsupported` carries an honest unsupported explanation and creates no task;
- `task_plan` carries a PlanDraft/task graph candidate for validation.

This keeps intent, rationale, risk, and plan evidence consistent. It also
prevents a router saying "coding request" and a second planner silently
changing intent or falling back to old demo templates.

### Decision: Planner LLM And Coding Agents Are Separate Runtimes

AgentHub should not route normal conversation directly into Claude Code,
Codex, or any other coding executor. The runtime boundary is:

```text
user message
-> Conversation Router / Planner LLM
-> ConversationOutcome
-> if task_plan: PlanValidator
-> Scheduler
-> Frontend / Backend / Review coding agents
```

The Planner LLM is responsible for understanding user intent, deciding whether
the message is chat, task, clarification, refusal, or approval-required, and
generating a PlanDraft when needed. Coding agents are responsible for reading
and editing code, running target-scoped project commands, and producing
diff/build/review/preview/deploy evidence.

P17 should use P16 Agent Runtime Configuration where available:

- the Conversation Router resolves the configured Planner runtime;
- frontend tasks resolve the configured Frontend coding agent provider;
- backend tasks resolve the configured Backend coding agent provider;
- review tasks resolve the configured Review agent provider.

Mission trace and run evidence should distinguish `plannerProvider` from
`codingAgentProvider`. A pure chat outcome must never invoke coding agents.
Future settings UI should allow users to configure Planner LLM, Frontend
coding agent, Backend coding agent, and Review agent provider/model choices,
but the full settings surface is deferred beyond P17.

### Decision: LLM-first For Orchestrator, Shortcuts Stay Explicit

No-mention messages and `@orchestrator` should use the LLM Orchestrator first.
Explicit role mentions remain advanced-user shortcuts:

- `@frontend` creates or routes direct frontend assignments;
- `@backend` creates or routes backend assignments;
- `@qa` and `@review` create or route read-oriented review/QA assignments.

This keeps fast explicit assignment behavior without making normal users type
`@orchestrator` for ordinary requests.

### Decision: Chat Is A First-class Outcome

Pure chat must not create coding tasks. A greeting such as `你好` should create
an assistant/orchestrator reply message, emit normal chat updates, and leave the
task timeline empty.

Clarification, refusal, approval explanation, unsupported, and normal assistant
reply messages should use the existing sender type `orchestrator` in P17. Do
not introduce a new message sender type in this phase.

### Decision: LLM Task Plans Bypass Legacy Signal Gates

Once the LLM Orchestrator returns `task_plan`, AgentHub must not send the
request back through legacy signal-word checks such as:

- `_is_safe_demo_frontend_request`;
- `_is_safe_external_frontend_request`;
- `_is_passthrough_frontend_request`;
- `_is_unsupported_broad_request`.

The `task_plan` path is:

```text
ConversationOutcome(task_plan)
-> ConversationOutcome schema validation
-> PlanDraft schema validation
-> PlanValidator
-> task persistence / scheduler
```

Legacy deterministic/demo routing may still be used only after an explicit
fallback decision.

### Decision: Deterministic Planning Is Fallback

Legacy deterministic demo planners should remain available for reliability,
but they should not be the first gate for no-mention chat. If the LLM router is
disabled or unavailable, AgentHub should choose between a friendly assistant
fallback response and deterministic fallback when the message clearly matches a
known safe coding flow.

The fallback split is:

- pure chat receives a friendly `orchestrator` reply and no task;
- clear safe frontend coding intent may create one fallback passthrough
  frontend task, marked with `plannerSource: fallback`;
- backend, platform, high-risk, ambiguous, or target-outside requests ask a
  clarification question, require approval, or refuse honestly;
- every fallback records provider/error/fallback metadata.

### Decision: Follow-ups Are Routed Through The Same Contract

P15b originally constrained LLM planning toward empty sessions. P17 should
allow follow-up routing with session context: recent messages, selected
artifact, mission trace, latest diff/review/build/preview/deploy evidence,
current goal, active tasks, and target policy.

### Decision: Validation Remains Authoritative

LLM routing decides intent. AgentHub still validates all executable plans:

- targets, roles, modes, capabilities;
- allowed and denied paths;
- dependency references;
- platform mode and approval requirements;
- command policy;
- scheduler/lock eligibility.

Unsafe plans must fail as refusal, approval-required, unsupported, or fallback;
they must not become passthrough frontend tasks.

## Risks / Trade-offs

- **Risk: LLM router returns invalid structured output.** Mitigation:
  schema validation and deterministic/friendly fallback.
- **Risk: Chat response masks a coding request.** Mitigation: tests for common
  coding requests, plan outcome evidence, and fallback only for honest cases.
- **Risk: Unsafe request becomes executable.** Mitigation: PlanValidator and
  Target Registry remain mandatory before task creation.
- **Risk: Provider outage breaks normal chat.** Mitigation: friendly fallback
  message when planner/router is disabled or unavailable.
- **Risk: Follow-up context leaks protected paths.** Mitigation:
  CanonicalSharedContext filtering remains required before provider-visible
  context.

## Migration Plan

1. Add `ConversationOutcome` schema and tests.
2. Add an LLM-first Orchestrator router that consumes canonical/session context
   and runtime config.
3. Add assistant reply persistence for chat/clarification/refusal/unsupported
   outcomes.
4. Route task plan outcomes through existing plan validation and task creation.
5. Add follow-up context into router input.
6. Keep deterministic demo planner as fallback.
7. Rehearse P17 flows and document freeze evidence.

Rollback strategy: disable LLM-first router and keep the existing deterministic
planner/fallback path. Assistant reply handling can remain harmless because it
does not execute tasks.

## Open Questions

- Whether approval-required outcomes create an approval card immediately or a
  read-only `orchestrator` explanation first remains an implementation detail,
  but executable work must not start before the existing approval path allows
  it.
