## Why

P17 made AgentHub conversational by routing messages through a
ConversationOutcome-first Planner boundary, but the only implemented real
PlannerProvider is still `claude_cli`. AgentHub needs native API-based planner
provider support so users can configure OpenAI, DeepSeek, MiMo, Anthropic, or
custom OpenAI-compatible Planner LLMs without relying on CC Switch or treating
coding agents as the chat entrypoint.

## What Changes

- Add a Planner Provider Protocol Registry for:
  - `openai_responses`;
  - `openai_compatible_chat`;
  - `anthropic_messages`;
  - existing `claude_cli`;
  - existing `fake_test`;
  - existing `disabled`.
- Add provider presets:
  - `openai_api` -> `openai_responses`;
  - `deepseek_api` -> `openai_compatible_chat`;
  - `mimo_api` -> `openai_compatible_chat`;
  - `anthropic_api` -> `anthropic_messages`;
  - `custom_openai_compatible` -> `openai_compatible_chat`.
- Add environment-only secret handling for Planner API providers. Runtime
  config may store provider id, protocol, model, base URL, timeout, and
  `apiKeyEnv`, but never raw API keys.
- Ensure all API planner providers consume `PlannerRequest` and return a
  validated `ConversationOutcome`.
- Use provider capability flags to select structured output strategy:
  JSON schema, JSON object mode, tool/schema mode, or strict JSON prompting
  plus parser validation.
- Extend runtime config and Agent Runtime Settings so users can select Planner
  provider preset/model/base URL/apiKeyEnv while keeping coding agent runtime
  configuration separate.
- Record planner provider/model/protocol/error/fallback evidence in mission
  trace without exposing secrets.
- Add fake-client tests for success and failure paths, plus rehearsal coverage
  for chat, task planning, and unsafe requests.

## Capabilities

### New Capabilities

- `multi-provider-planner-api`: AgentHub-native API PlannerProvider protocols,
  presets, runtime configuration, environment-only secrets, structured
  ConversationOutcome parsing, provider evidence, and tests for OpenAI,
  OpenAI-compatible, Anthropic, Claude CLI, fake, and disabled planner paths.

### Modified Capabilities

- None.

## Impact

- Backend:
  - expands planner provider resolution beyond `claude_cli`;
  - adds protocol/preset metadata and capability flags;
  - adds API client abstractions for OpenAI Responses, OpenAI-compatible chat,
    and Anthropic Messages;
  - keeps PlanValidator and Target Registry authoritative for executable
    plans;
  - records normalized provider evidence and missing-key/error states.
- Frontend:
  - extends Agent Runtime Settings for Planner provider preset/model/base URL
    and `apiKeyEnv` name;
  - displays provider availability as configured, missing key, or unavailable;
  - does not expose secrets.
- Runtime and security:
  - reads raw API keys only from environment variables;
  - never returns keys to frontend, logs, mission trace, errors, or evidence;
  - keeps Planner API providers separate from Claude Code/Codex coding agents;
  - does not add provider marketplace, cloud token management, production
    deploy, or CC Switch integration.
