## Context

P17 established the routing architecture AgentHub needs:

```text
user message
-> Conversation Router / Planner LLM
-> ConversationOutcome
-> if task_plan: schema validation + PlanValidator
-> Scheduler
-> Frontend / Backend / Review coding agents
```

The current real planner implementation is local `claude_cli`. That is useful
for development, but it leaves AgentHub dependent on one local CLI path and
does not let users configure common API-based Planner LLMs from AgentHub's own
runtime configuration model.

P17b adds API planner providers for planning and conversation routing only.
They do not read or edit code, do not run shell commands, and do not replace
ClaudeCodeAdapter or CodexAdapter. Coding work still starts only after a
validated `task_plan` reaches the scheduler.

## Goals / Non-Goals

**Goals:**

- Add protocol-level PlannerProvider support for OpenAI Responses,
  OpenAI-compatible chat, Anthropic Messages, existing Claude CLI, fake test,
  and disabled providers.
- Add built-in presets for OpenAI, DeepSeek, MiMo, Anthropic, and custom
  OpenAI-compatible providers.
- Keep secrets environment-only and never expose raw keys.
- Make provider behavior capability-driven where possible.
- Ensure every provider returns `ConversationOutcome`; `task_plan` outcomes
  must include PlanDraft and still pass PlanValidator.
- Integrate provider preset/model/base URL/apiKeyEnv selection into Planner
  runtime config and Agent Runtime Settings.
- Record honest provider evidence and missing-key/error states.
- Preserve P6-P17 baselines and the Planner/coding-agent runtime split.

**Non-Goals:**

- Using API LLMs as coding agents.
- Replacing ClaudeCodeAdapter or CodexAdapter.
- Storing raw API keys.
- Exposing secrets to frontend, logs, mission trace, errors, or evidence.
- CC Switch integration.
- Provider marketplace or cloud token manager.
- Production deploy.
- Bypassing PlanValidator, Target Registry, Scheduler, or guardrails.
- Removing `claude_cli`.

## Decisions

### Decision: Protocol Registry Is The Provider Foundation

P17b should introduce a protocol registry separate from vendor presets. The
core protocols are:

- `openai_responses`: official OpenAI / ChatGPT Responses API;
- `openai_compatible_chat`: DeepSeek, MiMo, OpenRouter, vLLM, and custom
  OpenAI-compatible chat-completions endpoints;
- `anthropic_messages`: Claude / Anthropic Messages API;
- `claude_cli`: existing local Claude CLI planner;
- `fake_test`: deterministic test provider;
- `disabled`: explicit disabled provider.

Presets point to protocols. This avoids hardcoding behavior per vendor when
multiple vendors share the same API shape.

### Decision: Presets Carry Defaults, Runtime Config Carries Selection

Built-in presets should define display name, protocol, default base URL,
default model, default `apiKeyEnv`, and capability flags. Runtime config may
store:

- provider/preset id;
- protocol;
- model;
- base URL;
- timeout;
- `apiKeyEnv` name;
- enabled/fallback policy metadata already supported by P16.

Runtime config must never store raw API keys. The frontend may show the env var
name and availability state, but not the secret value.

### Decision: Environment-only Secrets

Planner API providers read raw API keys from process environment variables
only. Recommended defaults:

- `OPENAI_API_KEY`;
- `DEEPSEEK_API_KEY`;
- `MIMO_API_KEY`;
- `ANTHROPIC_API_KEY`.

Custom OpenAI-compatible providers may specify a custom `apiKeyEnv` name.
Provider errors and evidence may record that a key is missing, but must not
include key values, authorization headers, or request bodies containing
secrets.

### Decision: One Planner Contract For Every Provider

Every provider receives a `PlannerRequest` containing the original user
message, CanonicalSharedContext summary, Target Registry summary, recent
messages, artifact references, supported roles/modes/capabilities, the
ConversationOutcome schema, and guardrails.

Every provider returns a `ConversationOutcome`:

- `assistant_reply`;
- `task_plan`;
- `clarification`;
- `refusal`;
- `approval_required`;
- `unsupported`.

If the outcome is `task_plan`, it must include PlanDraft and then pass schema
validation plus PlanValidator before tasks are persisted. Non-task outcomes
must create no TaskRun.

### Decision: Structured Output Is Capability-driven

Provider capability flags should guide request construction:

- `supportsJsonSchema`;
- `supportsJsonObject`;
- `supportsToolCalls`;
- `supportsSystemPrompt`;
- `supportsBaseUrl`;
- `defaultTimeoutSeconds`;
- `defaultModel`;
- `protocol`.

`openai_responses` should prefer strict structured output/JSON schema.
`anthropic_messages` should prefer structured tool/schema mode where supported.
`openai_compatible_chat` should use the strongest available JSON mode or
`response_format` when supported. If a compatible endpoint cannot guarantee
strict output, use strict JSON prompting and the existing parser/schema
validation. No unvalidated model output may create tasks.

### Decision: API Providers Are Not Coding Agents

P17b must preserve the P17 runtime boundary. API planner providers only decide
intent and produce `ConversationOutcome` / PlanDraft. They must not:

- edit files;
- run commands;
- inspect arbitrary host paths;
- deploy;
- bypass scheduler or target locks;
- replace ClaudeCodeAdapter/CodexAdapter.

Coding agents continue to use configured Frontend/Backend/Review runtime
providers after a validated task plan.

### Decision: Evidence Is Honest And Secret-free

Planner evidence and mission trace should record:

- provider preset id;
- protocol;
- model;
- base URL host or redacted base URL;
- duration;
- planner source;
- status;
- validation result;
- fallback reason;
- normalized error code/summary.

It must not record API key values, authorization headers, full request payloads
with secrets, or raw response bodies that might contain protected host paths.

### Decision: UI Extends Existing Runtime Settings

P17b should extend the P16 Agent Runtime Settings rather than add a separate
marketplace. The Planner section should allow selecting safe built-in presets,
model, base URL for custom OpenAI-compatible providers, timeout where
appropriate, and `apiKeyEnv` name. It should display availability as:

- `configured`;
- `missing_key`;
- `unavailable`.

Frontend, Backend, and Review coding agent settings remain separate.

## Risks / Trade-offs

- **Risk: API output is invalid or prose-heavy.** Mitigation: structured
  output where available plus strict parser/schema validation before any task
  creation.
- **Risk: OpenAI-compatible providers vary in feature support.** Mitigation:
  capability flags and graceful fallback to strict JSON prompting.
- **Risk: secrets leak into logs or UI.** Mitigation: env-only secret lookup,
  redacted evidence, and tests for missing-key and no-secret responses.
- **Risk: users confuse planner providers with coding agents.** Mitigation:
  separate runtime config surfaces and explicit evidence fields for planner vs
  coding agent providers.
- **Risk: provider outages break chat.** Mitigation: P17 friendly fallback and
  explicit missing-key/unavailable evidence.
- **Risk: unsafe plans pass from an API model.** Mitigation: PlanValidator,
  Target Registry, command policy, and platform approval remain mandatory.

## Migration Plan

1. Add protocol registry and provider presets.
2. Add environment-only secret resolver and redaction rules.
3. Implement API provider clients behind fake-client-testable interfaces.
4. Route API provider responses through the existing ConversationOutcome and
   PlanDraft parser/validation path.
5. Extend runtime config API/UI to expose Planner preset/model/baseUrl/apiKeyEnv.
6. Add provider evidence and mission trace metadata.
7. Run fake-client coverage and freeze review; run a real API smoke only if a
   real key is available.

Rollback strategy: leave presets disabled or select `disabled`/`claude_cli`;
existing P17 fallback and Claude CLI planner path remain available.

## Open Questions

- Which MiMo default base URL and model should be treated as the initial
  built-in preset defaults may need confirmation during implementation.
- Whether OpenAI-compatible custom providers should allow per-provider JSON
  capability overrides in the first implementation or start with safe defaults.
