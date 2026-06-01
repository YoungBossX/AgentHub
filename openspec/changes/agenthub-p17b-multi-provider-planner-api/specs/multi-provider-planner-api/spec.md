## ADDED Requirements

### Requirement: Planner Provider Protocol Registry
The system MUST define a protocol-level registry for PlannerProvider
implementations.

#### Scenario: Supported planner protocols are registered
- **WHEN** AgentHub initializes planner provider metadata
- **THEN** the registry MUST include `openai_responses`,
  `openai_compatible_chat`, `anthropic_messages`, `claude_cli`, `fake_test`,
  and `disabled`.

#### Scenario: Existing Claude CLI remains available
- **WHEN** the Planner runtime selects `claude_cli`
- **THEN** AgentHub MUST preserve the existing local Claude CLI planner
  provider behavior.

#### Scenario: Disabled and fake providers remain explicit
- **WHEN** the Planner runtime selects `disabled` or `fake_test`
- **THEN** AgentHub MUST preserve explicit disabled and test-only behavior
- **AND** it MUST NOT report fake/test output as real provider success.

### Requirement: Provider Presets
The system MUST define built-in Planner provider presets mapped to protocol
implementations.

#### Scenario: Built-in presets are available
- **WHEN** AgentHub exposes Planner provider presets
- **THEN** it MUST include `openai_api`, `deepseek_api`, `mimo_api`,
  `anthropic_api`, and `custom_openai_compatible`.

#### Scenario: Presets map to protocols
- **WHEN** a preset is resolved
- **THEN** `openai_api` MUST map to `openai_responses`
- **AND** `deepseek_api`, `mimo_api`, and `custom_openai_compatible` MUST map
  to `openai_compatible_chat`
- **AND** `anthropic_api` MUST map to `anthropic_messages`.

#### Scenario: Presets expose safe defaults
- **WHEN** preset metadata is returned
- **THEN** it MUST include display name, protocol, default model, capability
  flags, and default base URL when applicable
- **AND** it MUST NOT include raw API keys.

#### Scenario: Custom OpenAI-compatible base URL is supported
- **WHEN** the selected preset is `custom_openai_compatible`
- **THEN** runtime configuration MUST allow a custom base URL
- **AND** the base URL MUST be validated before use.

### Requirement: Environment-only Secrets
The system MUST read Planner API keys only from environment variables.

#### Scenario: Runtime config stores key reference only
- **WHEN** Planner runtime configuration is saved
- **THEN** it MAY store `apiKeyEnv`
- **AND** it MUST NOT store a raw API key value.

#### Scenario: Default key env names are supported
- **WHEN** built-in API presets are used
- **THEN** AgentHub MUST support default env var names such as
  `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `MIMO_API_KEY`, and
  `ANTHROPIC_API_KEY`.

#### Scenario: Missing key is explicit
- **WHEN** the selected API provider requires a key and the referenced env var
  is missing
- **THEN** provider availability MUST be `missing_key`
- **AND** the PlannerProvider MUST return or record a normalized missing-key
  error without making a real API call.

#### Scenario: Secrets are never exposed
- **WHEN** provider config, availability, mission trace, logs, errors, or
  evidence are returned
- **THEN** raw API keys and authorization headers MUST NOT be included.

### Requirement: Planner Request Response Contract
The system MUST use one provider contract for all Planner API providers.

#### Scenario: API provider receives PlannerRequest
- **WHEN** an API PlannerProvider is invoked
- **THEN** it MUST receive the original user message, CanonicalSharedContext
  summary, Target Registry summary, recent messages, artifact references,
  supported roles/modes/capabilities, ConversationOutcome schema, and
  guardrails.

#### Scenario: API provider returns ConversationOutcome
- **WHEN** an API PlannerProvider succeeds
- **THEN** it MUST return one `ConversationOutcome` with outcome type
  `assistant_reply`, `task_plan`, `clarification`, `refusal`,
  `approval_required`, or `unsupported`.

#### Scenario: Task plan includes PlanDraft
- **WHEN** the outcome type is `task_plan`
- **THEN** the outcome MUST include a PlanDraft
- **AND** the PlanDraft MUST pass schema validation and PlanValidator before
  tasks are persisted or TaskRuns are created.

#### Scenario: Non-task outcomes do not execute
- **WHEN** the outcome type is `assistant_reply`, `clarification`, `refusal`,
  `approval_required`, or `unsupported`
- **THEN** AgentHub MUST NOT create a TaskRun.

### Requirement: Structured Output Strategy
The system MUST validate structured output from every Planner API provider
before task creation.

#### Scenario: OpenAI Responses uses structured output
- **WHEN** `openai_responses` is used and JSON schema output is supported
- **THEN** the request MUST prefer structured output or JSON schema mode for
  `ConversationOutcome`.

#### Scenario: Anthropic provider uses strongest schema mode
- **WHEN** `anthropic_messages` is used
- **THEN** the request MUST use Anthropic structured output, tool/schema mode,
  or the strongest available schema-constrained mode.

#### Scenario: Compatible chat uses capability-driven JSON mode
- **WHEN** `openai_compatible_chat` is used
- **THEN** the request MUST use JSON schema, JSON object mode,
  `response_format`, tool calls, or strict JSON prompting according to provider
  capability flags.

#### Scenario: Unvalidated output is rejected
- **WHEN** model output cannot be parsed into a valid ConversationOutcome
- **THEN** AgentHub MUST reject the output
- **AND** it MUST NOT create tasks from that output.

### Requirement: Provider Capability Flags
The system MUST describe Planner provider behavior with explicit capability
flags.

#### Scenario: Capability flags are exposed
- **WHEN** provider or preset metadata is returned
- **THEN** it MUST include protocol, `supportsJsonSchema`,
  `supportsJsonObject`, `supportsToolCalls`, `supportsSystemPrompt`,
  `supportsBaseUrl`, `defaultTimeoutSeconds`, and `defaultModel` where
  applicable.

#### Scenario: Request construction follows capabilities
- **WHEN** AgentHub builds an API planner request
- **THEN** it MUST choose request shape and structured output strategy from the
  selected provider capability flags rather than relying only on vendor name.

### Requirement: Error Handling And Evidence
The system MUST record Planner API provider errors honestly and without
secrets.

#### Scenario: Common provider errors are normalized
- **WHEN** an API PlannerProvider fails due to missing key, invalid base URL,
  timeout, auth failure, quota or rate limit, invalid JSON, schema validation
  failure, or PlanValidator rejection
- **THEN** AgentHub MUST record normalized error metadata.

#### Scenario: Planner evidence records provider details
- **WHEN** a Planner API provider is used
- **THEN** planner evidence and mission trace MUST record provider id, preset
  id, protocol, model, duration, status, planner source, validation result,
  and fallback reason when applicable.

#### Scenario: Evidence does not expose secrets
- **WHEN** planner evidence or mission trace is returned
- **THEN** it MUST NOT include API key values, authorization headers, or raw
  secret-bearing request metadata.

#### Scenario: Fallback is auditable
- **WHEN** provider failure triggers fallback
- **THEN** fallback MUST be explicit and auditable
- **AND** AgentHub MUST NOT claim provider success.

### Requirement: Runtime Config Integration
The system MUST integrate Planner API provider selection into Agent Runtime
Configuration.

#### Scenario: Planner preset can be selected
- **WHEN** a user configures Planner runtime settings
- **THEN** the UI/API MUST allow selecting a safe Planner provider preset and
  model.

#### Scenario: Custom base URL is configurable
- **WHEN** the selected preset supports custom OpenAI-compatible endpoints
- **THEN** the UI/API MUST allow configuring a base URL
- **AND** it MUST validate the base URL before use.

#### Scenario: API key env name is configurable
- **WHEN** a user configures an API Planner provider
- **THEN** the UI/API MUST allow configuring `apiKeyEnv`
- **AND** it MUST NOT allow entering or storing the raw key value.

#### Scenario: Provider availability is visible
- **WHEN** runtime config or provider metadata is loaded
- **THEN** AgentHub MUST expose availability as `configured`, `missing_key`,
  or `unavailable`
- **AND** it MUST NOT expose secrets.

#### Scenario: Coding agent settings remain separate
- **WHEN** Planner provider runtime config changes
- **THEN** Frontend, Backend, QA, and Review coding agent provider config MUST
  remain separate.

### Requirement: Multi-provider Planner API Tests
The system MUST verify API planner provider behavior through fake-client and
policy tests.

#### Scenario: Fake clients cover provider success
- **WHEN** tests run for API PlannerProvider implementations
- **THEN** fake-client tests MUST cover OpenAI Responses success,
  OpenAI-compatible success, and Anthropic Messages success.

#### Scenario: Failure tests cover unsafe and invalid output
- **WHEN** tests run for failure paths
- **THEN** they MUST cover missing API key, invalid JSON, and `task_plan`
  rejected by PlanValidator.

#### Scenario: Chat outcome creates no TaskRun
- **WHEN** a fake API provider returns `assistant_reply`
- **THEN** tests MUST verify no TaskRun is created.

#### Scenario: Evidence excludes secrets
- **WHEN** tests inspect planner evidence
- **THEN** they MUST verify provider/model/protocol are recorded
- **AND** raw secrets are absent.

### Requirement: Rehearsal And Freeze Review
The system MUST rehearse multi-provider planner behavior without faking real
provider success.

#### Scenario: Real smoke requires real key
- **WHEN** a real API key is available
- **THEN** P17b MAY run one bounded real provider smoke
- **AND** it MUST record the provider, model, outcome, validation result, and
  caveats.

#### Scenario: Missing keys are acceptable evidence
- **WHEN** no real API keys are available
- **THEN** P17b MUST validate missing-key behavior and fake-client coverage
- **AND** it MUST NOT claim real provider success.

#### Scenario: Conversational rehearsal remains intact
- **WHEN** P17b rehearsal runs
- **THEN** `你好` MUST produce `assistant_reply` and no TaskRun
- **AND** `帮我做打砖块` MUST produce `task_plan` or an honest provider
  failure
- **AND** unsafe path requests MUST produce refusal or approval-required
  outcomes according to policy.

#### Scenario: Prior baselines remain intact
- **WHEN** P17b validation completes
- **THEN** P6-P17 baselines for runtime config, target registry,
  PlanValidator, scheduler, coding agents, diff, review, preview, and staging
  deploy MUST remain intact.
