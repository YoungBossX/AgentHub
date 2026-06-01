## 1. Planner Provider Protocol Registry

- [x] 1.1 Add protocol-level PlannerProvider metadata for `openai_responses`, `openai_compatible_chat`, `anthropic_messages`, `claude_cli`, `fake_test`, and `disabled`.
- [x] 1.2 Define provider capability flags: protocol, `supportsJsonSchema`, `supportsJsonObject`, `supportsToolCalls`, `supportsSystemPrompt`, `supportsBaseUrl`, `defaultTimeoutSeconds`, and `defaultModel`.
- [x] 1.3 Preserve existing `claude_cli`, `fake_test`, and `disabled` planner behavior.
- [x] 1.4 Add registry tests proving protocols and capability flags resolve without exposing secrets.

## 2. Provider Presets

- [x] 2.1 Add built-in presets: `openai_api`, `deepseek_api`, `mimo_api`, `anthropic_api`, and `custom_openai_compatible`.
- [x] 2.2 Map presets to protocols: OpenAI to `openai_responses`, DeepSeek/MiMo/custom compatible to `openai_compatible_chat`, and Anthropic to `anthropic_messages`.
- [x] 2.3 Add preset defaults for display name, protocol, base URL, model, `apiKeyEnv`, and capabilities.
- [x] 2.4 Support custom base URL validation for `custom_openai_compatible`.

## 3. Environment-only Secrets

- [x] 3.1 Add an environment-only API key resolver for Planner API providers.
- [x] 3.2 Allow runtime config to store `apiKeyEnv` but reject or ignore raw API key values.
- [x] 3.3 Ensure frontend/API/runtime config responses never return raw API keys or authorization headers.
- [x] 3.4 Add missing-key and no-secret-leak tests for OpenAI, DeepSeek, MiMo, Anthropic, and custom env names.

## 4. Planner API Provider Implementations

- [x] 4.1 Implement fake-client-testable `openai_responses` PlannerProvider.
- [x] 4.2 Implement fake-client-testable `openai_compatible_chat` PlannerProvider for DeepSeek, MiMo, OpenRouter, vLLM, and custom compatible endpoints.
- [x] 4.3 Implement fake-client-testable `anthropic_messages` PlannerProvider.
- [x] 4.4 Route all provider responses through ConversationOutcome parsing, PlanDraft schema validation, and PlanValidator before task persistence.
- [x] 4.5 Preserve non-task outcomes as `orchestrator` replies with no TaskRun.

## 5. Structured Output Strategy

- [x] 5.1 Add shared ConversationOutcome JSON schema / structured-output payload helpers.
- [ ] 5.2 Use JSON schema mode for `openai_responses` where supported.
- [ ] 5.3 Use tool/schema or strongest available structured mode for `anthropic_messages`.
- [ ] 5.4 Use capability-driven JSON schema, JSON object, tool-call, response-format, or strict JSON prompt strategy for `openai_compatible_chat`.
- [ ] 5.5 Add invalid JSON and schema-validation failure tests proving unvalidated output creates no task.

## 6. Runtime Config And Settings UI

- [ ] 6.1 Extend Planner runtime config model/schema to include preset/protocol/model/baseUrl/timeout/apiKeyEnv metadata without raw secrets.
- [ ] 6.2 Extend runtime config API validation for provider preset, model, base URL, apiKeyEnv, and availability state.
- [ ] 6.3 Extend Agent Runtime Settings UI Planner section for preset/model/base URL/apiKeyEnv selection.
- [ ] 6.4 Display Planner provider availability as `configured`, `missing_key`, or `unavailable`.
- [ ] 6.5 Keep Frontend, Backend, QA, and Review coding agent runtime settings separate.

## 7. Evidence And Mission Trace

- [ ] 7.1 Record planner provider preset, protocol, model, duration, planner source, status, validation result, fallback reason, and normalized error metadata.
- [ ] 7.2 Expose provider evidence in planner evidence and mission trace without secrets.
- [ ] 7.3 Normalize missing key, invalid base URL, timeout, auth failure, quota/rate limit, invalid JSON, schema validation failure, and PlanValidator rejection errors.
- [ ] 7.4 Add tests proving fallback is explicit and real provider success is not faked.

## 8. Test Matrix

- [ ] 8.1 Add fake-client OpenAI Responses provider success tests.
- [ ] 8.2 Add fake-client OpenAI-compatible provider success tests.
- [ ] 8.3 Add fake-client Anthropic provider success tests.
- [ ] 8.4 Add tests for assistant reply creating no TaskRun.
- [ ] 8.5 Add tests for unsafe task_plan rejected by PlanValidator.
- [ ] 8.6 Run targeted planner provider, runtime config, conversational routing, and mission trace tests.

## 9. Rehearsal And Freeze Review

- [ ] 9.1 If real API keys are available, run one bounded real provider smoke and record provider/model/outcome/validation evidence.
- [ ] 9.2 If no real API keys are available, validate missing-key behavior and fake-client coverage without claiming real provider success.
- [ ] 9.3 Verify `你好` -> `assistant_reply` with no TaskRun.
- [ ] 9.4 Verify `帮我做打砖块` -> `task_plan` or honest provider failure, then PlanValidator when a plan is produced.
- [ ] 9.5 Verify unsafe path request -> refusal or approval-required.
- [ ] 9.6 Verify P6-P17 baselines remain intact.
- [ ] 9.7 Update `docs/project-state.md`, `docs/change-log.md`, and add `docs/p17b-freeze-review.md`.
- [ ] 9.8 Run `pnpm check`, `pnpm test`, `pnpm demo:api:test`, `git diff --check`, and `openspec validate agenthub-p17b-multi-provider-planner-api --strict`.

## 10. Explicit Non-goals

- [ ] 10.1 Confirm P17b does not use API LLMs as coding agents, replace ClaudeCodeAdapter or CodexAdapter, store raw API keys, expose secrets to frontend, add CC Switch integration, add provider marketplace, add cloud token manager, add production deploy, bypass PlanValidator, or remove `claude_cli`.
