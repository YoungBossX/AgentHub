# AgentHub Change Log

## P17b-5.4 Capability-driven Planner Structured Output Strategy

**Date:** 2026-06-01

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planner_providers.py` | Added capability-driven structured output strategy selection and used it for OpenAI-compatible JSON object mode. |
| `apps/api/tests/test_planner_providers.py` | Added strategy coverage for JSON schema, tool schema, JSON object, and strict JSON prompt fallback. |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | Marked P17b-5.4 complete. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_providers.py::test_structured_output_strategy_follows_protocol_capabilities tests/test_planner_providers.py::test_openai_compatible_chat_planner_provider_uses_fake_client -q` | Pass: 2 tests. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | Pass. |

---

## P17b-5.3 Anthropic Planner Tool Schema Mode

**Date:** 2026-06-01

### Modified Files

| File | Change |
|---|---|
| `apps/api/tests/test_planner_providers.py` | Strengthened Anthropic Messages provider coverage to assert ConversationOutcome tool/schema output. |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | Marked P17b-5.3 complete. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_providers.py::test_anthropic_messages_planner_provider_uses_fake_client -q` | Pass: 1 test. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | Pass. |

---

## P17b-5.2 OpenAI Responses JSON Schema Mode

**Date:** 2026-06-01

### Modified Files

| File | Change |
|---|---|
| `apps/api/tests/test_planner_providers.py` | Strengthened OpenAI Responses provider coverage to assert strict ConversationOutcome JSON schema mode. |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | Marked P17b-5.2 complete. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_providers.py::test_openai_responses_planner_provider_uses_fake_client -q` | Pass: 1 test. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | Pass. |

---

## P17b-5.1 Shared ConversationOutcome Structured-output Helpers

**Date:** 2026-06-01

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planner_contracts.py` | Added shared ConversationOutcome JSON schema and planner system prompt helpers. |
| `apps/api/app/planner_providers.py` | Reused the shared structured-output helpers in OpenAI Responses, OpenAI-compatible, and Anthropic provider payloads. |
| `apps/api/tests/test_planner_contracts.py` | Added coverage for the shared schema and prompt helper. |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | Marked P17b-5.1 complete. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_contracts.py::test_conversation_outcome_structured_output_helpers_are_shared tests/test_planner_providers.py::test_openai_responses_planner_provider_uses_fake_client tests/test_planner_providers.py::test_anthropic_messages_planner_provider_uses_fake_client -q` | Pass: 3 tests. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | Pass. |

---

## P17b-4.5 API Planner Non-task Outcome Handling

**Date:** 2026-06-01

### Modified Files

| File | Change |
|---|---|
| `apps/api/tests/test_planning.py` | Added API planner coverage proving `assistant_reply` creates an Orchestrator chat message and no Task/TaskRun. |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | Marked P17b-4.5 complete. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planning.py::test_api_planner_assistant_reply_creates_orchestrator_message_without_task -q` | Pass: 1 test. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | Pass. |

---

## P17b-4.4 API Planner Validation Path

**Date:** 2026-06-01

### Modified Files

| File | Change |
|---|---|
| `apps/api/tests/test_llm_planner.py` | Added API-provider integration coverage proving task plans pass ConversationOutcome, PlanDraft schema validation, and PlanValidator before persistence. |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | Marked P17b-4.4 complete. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_llm_planner.py::test_api_planner_provider_output_flows_through_plan_validator tests/test_llm_planner.py::test_api_planner_provider_unsafe_plan_is_rejected_before_persistence -q` | Pass: 2 tests. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | Pass. |

---

## P17b-4.3 Anthropic Messages Planner Provider

**Date:** 2026-06-01

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planner_providers.py` | Added a fake-client-testable Anthropic Messages PlannerProvider using tool/schema output for ConversationOutcome. |
| `apps/api/tests/test_planner_providers.py` | Added success and missing-key coverage for the Anthropic provider without real API calls. |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | Marked P17b-4.3 complete. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_providers.py::test_anthropic_messages_planner_provider_uses_fake_client tests/test_planner_providers.py::test_anthropic_messages_planner_provider_missing_key_fails_without_call -q` | Pass: 2 tests. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | Pass. |

---

## P17b-4.2 OpenAI-compatible Chat Planner Provider

**Date:** 2026-06-01

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planner_providers.py` | Added a fake-client-testable OpenAI-compatible Chat PlannerProvider for DeepSeek, MiMo, and custom compatible endpoints. |
| `apps/api/tests/test_planner_providers.py` | Added success and missing-key coverage for the OpenAI-compatible provider without real API calls. |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | Marked P17b-4.2 complete. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_providers.py::test_openai_compatible_chat_planner_provider_uses_fake_client tests/test_planner_providers.py::test_openai_compatible_chat_planner_provider_missing_key_fails_without_call -q` | Pass: 2 tests. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | Pass. |

---

## P17b-4.1 OpenAI Responses Planner Provider

**Date:** 2026-06-01

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planner_providers.py` | Added a fake-client-testable OpenAI Responses PlannerProvider with env-only key lookup and structured-output request payload. |
| `apps/api/tests/test_planner_providers.py` | Added success and missing-key tests for the OpenAI Responses provider without real API calls. |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | Marked P17b-4.1 complete. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_providers.py::test_openai_responses_planner_provider_uses_fake_client tests/test_planner_providers.py::test_openai_responses_planner_provider_missing_key_fails_without_call -q` | Pass: 2 tests. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | Pass. |

---

## P17b-3.4 Planner API Missing-key And Secret-leak Tests

**Date:** 2026-06-01

### Modified Files

| File | Change |
|---|---|
| `apps/api/tests/test_planner_providers.py` | Added missing-key and configured-key secret-free metadata coverage for OpenAI, DeepSeek, MiMo, Anthropic, and custom compatible planner presets. |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | Marked P17b-3.4 complete. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_providers.py::test_api_planner_presets_report_missing_keys_without_secret_leaks tests/test_planner_providers.py::test_api_planner_preset_configured_key_metadata_is_secret_free -q` | Pass: 10 tests. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | Pass. |

---

## P17b-3.3 Runtime Config Secret-safe Responses

**Date:** 2026-06-01

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/schemas.py` | Ignored accidental raw Planner API secret fields such as `apiKey` and authorization headers in runtime role requests. |
| `apps/api/tests/test_agent_runtime_config.py` | Added API coverage proving raw secret inputs do not appear in validate, save, or fetch responses. |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | Marked P17b-3.3 complete. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_agent_runtime_config.py::test_runtime_config_api_ignores_raw_api_key_field tests/test_agent_runtime_config.py::test_runtime_config_responses_do_not_expose_raw_secret_fields -q` | Pass: 2 tests. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | Pass. |

---

## P17b-3.2 Runtime Config API Key Reference Handling

**Date:** 2026-06-01

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/agent_runtime_config.py` | Added `apiKeyEnv` to runtime role config and rejected invalid env-name references. |
| `apps/api/app/schemas.py` | Allowed `apiKeyEnv` in runtime config requests/responses while accepting and ignoring raw `apiKey` values. |
| `apps/api/app/main.py` | Mapped runtime config `apiKeyEnv` through API response and request conversion. |
| `apps/api/tests/test_agent_runtime_config.py` | Added runtime config tests for `apiKeyEnv` persistence and ignored raw API key fields. |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | Marked P17b-3.2 complete. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_agent_runtime_config.py::test_runtime_config_round_trips_workspace_role_defaults tests/test_agent_runtime_config.py::test_runtime_config_rejects_raw_or_invalid_api_key_env tests/test_agent_runtime_config.py::test_runtime_config_api_persists_valid_workspace_config tests/test_agent_runtime_config.py::test_runtime_config_api_ignores_raw_api_key_field -q` | Pass: 4 tests. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | Pass. |

---

## P17b-3.1 Environment-only Planner API Key Resolver

**Date:** 2026-06-01

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planner_providers.py` | Added an environment-only Planner API key resolver with missing-key metadata and invalid env-name rejection. |
| `apps/api/tests/test_planner_providers.py` | Added tests for configured keys, missing keys, invalid env names, and secret-free metadata. |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | Marked P17b-3.1 complete. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_providers.py::test_resolve_planner_api_key_reads_environment_without_exposing_secret tests/test_planner_providers.py::test_resolve_planner_api_key_reports_missing_key_without_api_call tests/test_planner_providers.py::test_resolve_planner_api_key_rejects_invalid_env_names -q` | Pass: 6 tests. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | Pass. |

---

## P17b-2.4 Custom Planner Base URL Validation

**Date:** 2026-06-01

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planner_providers.py` | Added Planner provider base URL validation for custom OpenAI-compatible presets and unsupported overrides. |
| `apps/api/tests/test_planner_providers.py` | Added coverage for accepted custom URLs, rejected unsafe URLs, and unsupported base URL overrides. |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | Marked P17b-2.4 complete. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_providers.py::test_validate_planner_provider_base_url_supports_custom_compatible_url tests/test_planner_providers.py::test_validate_planner_provider_base_url_rejects_unsafe_custom_url tests/test_planner_providers.py::test_validate_planner_provider_base_url_rejects_unsupported_override -q` | Pass: 9 tests. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | Pass. |

---

## P17b-2.3 Planner Preset Defaults

**Date:** 2026-06-01

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planner_providers.py` | Added safe preset defaults for Planner API base URL, default model, API key env name, and protocol capabilities. |
| `apps/api/tests/test_planner_providers.py` | Added coverage that preset metadata exposes expected defaults while remaining secret-free. |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | Marked P17b-2.3 complete. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_providers.py::test_planner_provider_presets_include_safe_defaults_and_capabilities -q` | Pass: 1 test. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | Pass. |

---

## P17b-2.2 Planner Preset Protocol Mapping

**Date:** 2026-06-01

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planner_providers.py` | Mapped Planner provider presets to protocol identifiers. |
| `apps/api/tests/test_planner_providers.py` | Added coverage for preset-to-protocol mapping. |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | Marked P17b-2.2 complete. |
| `docs/change-log.md` | Recorded this implementation. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_providers.py::test_planner_provider_presets_map_to_protocols -q` | Pass: 1 test. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | Pass. |

---

## P17b-2.1 Planner Provider Presets

**Date:** 2026-06-01

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planner_providers.py` | Added built-in Planner provider preset metadata for OpenAI, DeepSeek, MiMo, Anthropic, and custom OpenAI-compatible APIs. |
| `apps/api/tests/test_planner_providers.py` | Added preset registry coverage. |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | Marked P17b-2.1 complete. |
| `docs/change-log.md` | Recorded this implementation. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_providers.py::test_planner_provider_preset_registry_lists_builtin_presets -q` | Pass: 1 test. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | Pass. |

---

## P17b-1.4 Planner Protocol Registry Tests

**Date:** 2026-06-01

### Modified Files

| File | Change |
|---|---|
| `apps/api/tests/test_planner_providers.py` | Added full registry no-secret metadata coverage for planner provider protocols. |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | Marked P17b-1.4 complete. |
| `docs/change-log.md` | Recorded this implementation. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_providers.py -q` | Pass: 17 tests. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | Pass. |

---

## P17b-1.3 Preserve Existing Planner Providers

**Date:** 2026-06-01

### Modified Files

| File | Change |
|---|---|
| `apps/api/tests/test_planner_providers.py` | Added regression coverage proving `claude_cli`, `fake_test`, and `disabled` provider resolution remains compatible. |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | Marked P17b-1.3 complete. |
| `docs/change-log.md` | Recorded this implementation. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_providers.py::test_existing_planner_provider_resolution_stays_compatible -q` | Pass: 1 test. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | Pass. |

---

## P17b-1.2 Planner Provider Capability Flags

**Date:** 2026-06-01

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planner_providers.py` | Added capability flags to PlannerProvider protocol metadata. |
| `apps/api/tests/test_planner_providers.py` | Added coverage for capability metadata and no-secret fields. |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | Marked P17b-1.2 complete. |
| `docs/change-log.md` | Recorded this implementation. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_providers.py::test_planner_provider_protocol_metadata_exposes_capability_flags -q` | Pass: 1 test. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | Pass. |

---

## P17b-1.1 Planner Provider Protocol Metadata

**Date:** 2026-06-01

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planner_providers.py` | Added protocol-level PlannerProvider metadata for OpenAI Responses, OpenAI-compatible chat, Anthropic Messages, Claude CLI, fake test, and disabled planner protocols. |
| `apps/api/tests/test_planner_providers.py` | Added registry coverage for supported planner protocols. |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/*` | Added the P17b OpenSpec artifacts and marked P17b-1.1 complete. |
| `docs/change-log.md` | Recorded this implementation. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_providers.py::test_planner_provider_protocol_registry_lists_supported_protocols -q` | Pass: 1 test. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | Pass. |

---

## P17-8 Rehearsal And Freeze Review

**Date:** 2026-05-29

### Modified Files

| File | Change |
|---|---|
| `apps/api/tests/test_planning.py` | Updated runtime config planner-provider test to use the new ConversationOutcome provider path. |
| `docs/p17-freeze-review.md` | Added P17 freeze evidence, runtime boundary, validation results, caveats, and recommended tag. |
| `docs/project-state.md` | Recorded P17 freeze readiness and conversational routing baseline. |
| `docs/change-log.md` | Recorded this freeze review. |
| `openspec/changes/agenthub-p17-conversational-orchestrator-routing/tasks.md` | Marked P17-8, non-goals, and validation complete after verification. |

### What Changed

P17 freeze review confirms AgentHub now treats no-mention and `@orchestrator`
messages as conversation outcomes first: chat stays chat, task plans are
validated before scheduling, and coding agents are not invoked for normal
conversation.

### Validation

| Command | Result |
|---|---|
| P17 targeted conversational router/schema/reply/plan/fallback/follow-up tests | Pass: 44 tests. |
| `pnpm check` | Pass. |
| `pnpm test` | Pass: web 44 tests, API 319 tests, demo-api 5 tests. |
| `pnpm demo:api:test` | Pass: 5 tests. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p17-conversational-orchestrator-routing --strict` | Pass. |

---

## P17-7 Friendly Fallback

**Date:** 2026-05-29

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planning.py` | Added friendly pure-chat fallback when LLM routing is disabled/unavailable and marked fallback frontend tasks with `plannerSource: fallback`. |
| `apps/api/tests/test_planning.py` | Added coverage for disabled-router chat fallback and audited frontend fallback metadata. |
| `openspec/changes/agenthub-p17-conversational-orchestrator-routing/tasks.md` | Marked P17-7 complete after targeted validation. |
| `docs/change-log.md` | Recorded this implementation. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planning.py::test_disabled_llm_router_returns_friendly_chat_fallback_without_task tests/test_planning.py::test_no_mention_message_routes_to_orchestrator_and_auto_starts_demo_task -q` | Pass: 2 tests. |

---

## P17-6 Follow-up Routing Context

**Date:** 2026-05-29

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/canonical_context.py` | Added `missionTrace` to CanonicalSharedContext provider-visible fields. |
| `apps/api/app/llm_planner.py` | Added mission trace to planner context and allowed follow-up sessions to preserve current task evidence. |
| `apps/api/app/planning.py` | Allowed Orchestrator messages with existing tasks to enter the LLM router instead of limiting LLM routing to empty sessions. |
| `apps/api/tests/test_llm_planner.py` | Added planner input coverage for follow-up mission trace context. |
| `apps/api/tests/test_planning.py` | Added coverage that follow-up messages still call the LLM router. |
| `openspec/changes/agenthub-p17-conversational-orchestrator-routing/tasks.md` | Marked P17-6 complete after targeted validation. |
| `docs/change-log.md` | Recorded this implementation. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_llm_planner.py::test_llm_planner_input_includes_followup_mission_trace -q` | Pass: 1 test. |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planning.py::test_followup_message_still_routes_through_llm_router -q` | Pass: 1 test. |

---

## P17-5 Clarification Refusal And Approval Outcomes

**Date:** 2026-05-29

### Modified Files

| File | Change |
|---|---|
| `apps/api/tests/test_planning.py` | Added coverage for clarification, refusal, and approval-required ConversationOutcome replies creating no tasks. |
| `openspec/changes/agenthub-p17-conversational-orchestrator-routing/tasks.md` | Marked P17-5 complete after targeted validation. |
| `docs/change-log.md` | Recorded this implementation. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planning.py::test_non_task_conversation_outcomes_do_not_create_tasks -q` | Pass: 3 tests. |

---

## P17-4 Task Plan Path

**Date:** 2026-05-29

### Modified Files

| File | Change |
|---|---|
| `apps/api/tests/test_planning.py` | Added coverage for `ConversationOutcome(task_plan)` producing a validated frontend task through the LLM path. |
| `openspec/changes/agenthub-p17-conversational-orchestrator-routing/tasks.md` | Marked P17-4 complete after targeted validation. |
| `docs/change-log.md` | Recorded this implementation. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planning.py::test_conversation_task_plan_creates_validated_task tests/test_planning.py::test_llm_task_plan_bypasses_legacy_signal_gates -q` | Pass: 2 tests. |

---

## P17-3 Conversational Reply Path

**Date:** 2026-05-29

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/llm_planner.py` | Split provider output handling into ConversationOutcome parsing and task-plan persistence so non-task outcomes can stop before task creation. |
| `apps/api/app/planning.py` | Persisted non-task ConversationOutcome replies as `orchestrator` chat messages with no TaskRun. |
| `apps/api/tests/test_planning.py` | Added coverage for `你好` producing an orchestrator reply and no tasks. |
| `openspec/changes/agenthub-p17-conversational-orchestrator-routing/tasks.md` | Marked P17-3 complete after targeted validation. |
| `docs/change-log.md` | Recorded this implementation. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planning.py::test_llm_assistant_reply_creates_orchestrator_message_without_task tests/test_planning.py::test_no_mention_message_uses_configured_llm_planner_provider -q` | Pass: 2 tests. |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_llm_planner.py -q` | Pass: 5 tests. |

---

## P17-2b LLM-first Orchestrator Entry

**Date:** 2026-05-29

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/llm_planner.py` | Added ConversationOutcome parsing for LLM planner output while preserving PlannerResponse compatibility for existing tests and fake providers. |
| `apps/api/app/planner_providers.py` | Updated the Claude CLI planner prompt to request a single ConversationOutcome and separate chat/routing decisions from coding execution. |
| `apps/api/tests/test_planner_contracts.py` | Added ConversationOutcome parser coverage for task plans and assistant replies. |
| `apps/api/tests/test_planner_providers.py` | Updated prompt assertions for the ConversationOutcome contract. |
| `openspec/changes/agenthub-p17-conversational-orchestrator-routing/tasks.md` | Marked P17-2b complete after targeted validation. |
| `docs/change-log.md` | Recorded this implementation. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_contracts.py tests/test_planner_providers.py tests/test_llm_planner.py -q` | Pass: 34 tests. |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planning.py::test_no_mention_message_uses_configured_llm_planner_provider tests/test_planning.py::test_runtime_config_selects_planner_provider_for_no_mention_message tests/test_planning.py::test_llm_task_plan_bypasses_legacy_signal_gates -q` | Pass: 3 tests. |

---

## P17-2a Retire Legacy Signal Gates From Primary Routing

**Date:** 2026-05-29

### Modified Files

| File | Change |
|---|---|
| `apps/api/tests/test_planning.py` | Added coverage proving an LLM `task_plan` bypasses legacy safe/unsupported signal gates and reaches PlanValidator/task persistence directly. |
| `openspec/changes/agenthub-p17-conversational-orchestrator-routing/tasks.md` | Marked P17-2a complete after targeted validation. |
| `docs/change-log.md` | Recorded this implementation. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planning.py::test_llm_task_plan_bypasses_legacy_signal_gates -q` | Pass: 1 test. |

---

## P17-1 ConversationOutcome Schema

**Date:** 2026-05-29

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planner_contracts.py` | Added the `ConversationOutcome` contract for assistant replies, task plans, clarification, refusal, approval-required, unsupported, planner provider evidence, validation result, and fallback/error metadata. |
| `apps/api/tests/test_planner_contracts.py` | Added schema tests for assistant replies, required task plan drafts, and planner/coding provider evidence separation. |
| `openspec/changes/agenthub-p17-conversational-orchestrator-routing/tasks.md` | Marked P17-1 complete after targeted validation. |
| `docs/change-log.md` | Recorded this implementation. |

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_contracts.py -q` | Pass: 14 tests. |

---

## P16-7 Rehearsal And Freeze Review

**Date:** 2026-05-29

### Modified Files

| File | Change |
|---|---|
| `docs/p16-freeze-review.md` | Added P16 freeze decision, runtime config evidence, safety caveats, and recommended tag. |
| `docs/project-state.md` | Recorded P16 freeze readiness and configured role/provider target. |
| `docs/change-log.md` | Recorded this freeze review. |
| `openspec/changes/agenthub-p16-agent-runtime-configuration/tasks.md` | Marked P16-7, non-goals, and validation complete after verification. |

### What Changed

P16 freeze review confirms that runtime config can configure Planner,
Frontend, and Backend provider defaults while preserving P6-P15b baselines and
the existing target/approval safety model.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass. |
| `pnpm test` | Pass: web 43 tests, API 304 tests, demo-api 5 tests. |
| `pnpm demo:api:test` | Pass: 5 tests. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p16-agent-runtime-configuration --strict` | Pass. |

---

## P16-6 Safety And Policy Enforcement

**Date:** 2026-05-29

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/agent_runtime_config.py` | Added role/mode policy validation so runtime config cannot assign backend to platform maintenance mode. |
| `apps/api/tests/test_agent_runtime_config.py` | Added negative API validation coverage for backend platform maintenance mode. |
| `apps/api/tests/test_task_runs.py` | Added execution coverage proving backend runtime config does not bypass platform approval. |
| `docs/project-state.md` | Recorded P16-6 safety policy behavior. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p16-agent-runtime-configuration/tasks.md` | Marked P16-6 complete after validation. |

### What Changed

Runtime config remains subordinate to existing Target Registry, platform mode,
and approval policy. It can choose safe role providers, but it cannot turn an
ordinary backend role into unapproved AgentHub platform maintenance.

### Validation

| Command | Result |
|---|---|
| P16-6 targeted negative policy tests | Pass: 2 tests. |

---

## P16-5 Runtime Config Evidence

**Date:** 2026-05-29

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/schemas.py` | Added top-level `providerAssignment` and `runtimeConfigResolution` fields to TaskRun responses. |
| `apps/api/app/main.py` | Returned provider/runtime config resolution metadata in TaskRun API responses. |
| `apps/api/app/mission_trace.py` | Included runtime config resolution in mission trace task-run entries. |
| `apps/api/app/planning.py` | Attached runtime config resolution to planner evidence for runtime-selected planner runs. |
| `apps/api/tests/test_planning.py` | Added planner evidence assertions for runtime-selected Planner provider. |
| `apps/api/tests/test_task_runs.py` | Added TaskRun response and mission trace runtime config evidence coverage. |
| `docs/project-state.md` | Recorded P16-5 evidence behavior. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p16-agent-runtime-configuration/tasks.md` | Marked P16-5 complete after validation. |

### What Changed

Runtime config choices are now visible in API and mission trace evidence, making
Planner/Frontend/Backend provider resolution auditable without exposing
secrets or protected paths.

### Validation

| Command | Result |
|---|---|
| P16-5 targeted planner/task-run/mission-trace tests | Pass: 3 tests. |

---

## P16-4 Runtime Config Resolution

**Date:** 2026-05-29

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/agent_runtime_config.py` | Added enabled role resolution metadata for workspace runtime config. |
| `apps/api/app/planner_providers.py` | Allowed explicit runtime provider IDs such as `claude-cli-planner` to resolve the real Claude CLI planner. |
| `apps/api/app/planning.py` | Routed no-mention Orchestrator planning through enabled Planner runtime config when present. |
| `apps/api/app/provider_assignments.py` | Added runtime-config provider assignment source before legacy matrix/default selection. |
| `apps/api/app/task_runs.py` | Applied enabled Frontend/Backend runtime config to TaskRun adapter/provider selection. |
| `apps/api/tests/test_planner_providers.py` | Added runtime provider ID resolver coverage. |
| `apps/api/tests/test_planning.py` | Added Planner runtime config routing coverage. |
| `apps/api/tests/test_task_runs.py` | Added Frontend/Backend runtime adapter override coverage. |
| `docs/project-state.md` | Recorded P16-4 behavior and next evidence step. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p16-agent-runtime-configuration/tasks.md` | Marked P16-4 complete after validation. |

### What Changed

Runtime config now affects actual planner and code-agent resolution while
preserving explicit adapter overrides and legacy defaults when no config exists.

### Validation

| Command | Result |
|---|---|
| P16-4 targeted planner/provider/task-run tests | Pass: 5 tests. |

---

## P16-3 Agent Runtime Settings UI

**Date:** 2026-05-29

### Modified Files

| File | Change |
|---|---|
| `apps/web/src/lib/api.ts` | Added Agent Runtime Config types plus GET/PUT client helpers. |
| `apps/web/src/components/agent-runtime-settings.tsx` | Added the sidebar runtime settings UI for Planner, Frontend, and Backend roles. |
| `apps/web/src/components/session-sidebar.tsx` | Added a slot for the runtime settings panel. |
| `apps/web/src/components/workspace-shell.tsx` | Loaded/saved workspace runtime config and wired the runtime settings panel. |
| `apps/web/src/lib/api.test.ts` | Added runtime config client helper coverage. |
| `apps/web/src/components/workspace-shell.test.tsx` | Added runtime settings render coverage. |
| `docs/project-state.md` | Recorded P16-3 behavior and limitation. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p16-agent-runtime-configuration/tasks.md` | Marked P16-3 complete after validation. |

### What Changed

AgentHub now has a user-facing runtime settings panel for configuring Planner,
Frontend, and Backend Agent defaults from existing safe profile/provider
metadata. The UI persists through the runtime config API but does not yet affect
actual provider resolution.

### Validation

| Command | Result |
|---|---|
| `pnpm --filter @agenthub/web check` | Pass. |
| `pnpm --filter @agenthub/web test` | Pass: 43 tests. |

---

## P16-2 Runtime Config API

**Date:** 2026-05-29

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/provider_configs.py` | Added `claude-cli-planner` provider metadata for configurable Planner Agent selection. |
| `apps/api/app/agent_runtime_config.py` | Added runtime config validation against AgentProfile and ProviderConfig metadata. |
| `apps/api/app/schemas.py` | Added runtime config request/response and validation schemas. |
| `apps/api/app/main.py` | Added runtime config GET, validate, and PUT workspace endpoints. |
| `apps/api/tests/test_agent_runtime_config.py` | Added runtime config API default, validation, persistence, and invalid-assignment tests. |
| `apps/api/tests/test_models.py` | Updated the model boundary whitelist for `AgentRuntimeConfig`. |
| `apps/api/tests/test_provider_configs.py` | Updated provider registry expectations for the planner provider. |
| `docs/project-state.md` | Recorded P16-2 behavior and remaining limitation. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p16-agent-runtime-configuration/tasks.md` | Marked P16-2 complete after validation. |

### What Changed

Workspace runtime config can now be read, validated, and persisted through API
endpoints. The API exposes safe selectable provider/profile metadata and blocks
invalid role/profile/provider/mode combinations before persistence.

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_agent_runtime_config.py tests/test_provider_configs.py -q` | Pass: 9 tests. |

---

## P16-1 Agent Runtime Config Model

**Date:** 2026-05-29

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/models.py` | Added `AgentRuntimeConfig` table model for workspace/global-scoped runtime role defaults. |
| `apps/api/app/agent_runtime_config.py` | Added runtime role config dataclasses, default effective config, workspace config upsert, JSON serialization, and unsupported-role validation. |
| `apps/api/tests/test_agent_runtime_config.py` | Added model/default/round-trip/serialization tests. |
| `docs/project-state.md` | Recorded P16-1 behavior and limitation. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p16-agent-runtime-configuration/*` | Added P16 OpenSpec artifacts and marked P16-1 complete after validation. |

### What Changed

AgentHub can now persist a workspace-level runtime configuration skeleton for
planner, frontend, backend, and review roles. If no config exists, effective
runtime config reports `configSource=default` with disabled overrides, so
existing provider behavior remains unchanged.

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_agent_runtime_config.py -q` | Pass: 4 tests. |

---

## P15b-7 Real LLM Planner Breakout Rehearsal And Freeze Review

**Date:** 2026-05-29

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planning.py` | Wired no-mention orchestrator planning to the real LLM planner provider when enabled; preserved deterministic fallback on planner failure; included safe explicitly referenced demo frontend files in direct assignment plans. |
| `apps/api/app/planner_providers.py` | Tightened the Claude CLI planner prompt to require one PlannerResponse JSON object, bounded tasks, valid roles, valid artifact types, and stable dependency aliases. |
| `apps/api/app/planner_contracts.py` | Safely normalized real-provider `version` and `guardrailNotes` variants that appeared during smoke. |
| `apps/api/app/plan_validator.py` | Allowed configured validation commands with safe result suffixes such as `pnpm build succeeds` while still rejecting unsupported commands. |
| `apps/api/app/llm_planner.py` | Normalized safe target-based dependency aliases before task graph validation. |
| `apps/api/app/main.py` | Allowed planned `llm_v1` review tasks to be satisfied by generated review artifacts. |
| `apps/api/app/scheduler.py` | Treated completed upstream dependency diff files as safe dirty-worktree context for downstream follow-up tasks. |
| `apps/api/tests/test_llm_planner.py` | Added dependency-alias normalization and safe command-note validation coverage. |
| `apps/api/tests/test_planner_contracts.py` | Added safe scalar normalization coverage. |
| `apps/api/tests/test_planner_providers.py` | Updated Claude CLI planner prompt assertions. |
| `apps/api/tests/test_planning.py` | Added real planner routing test coverage and safe referenced demo file coverage. |
| `apps/api/tests/test_scheduler.py` | Added downstream dirty-worktree inheritance coverage for completed dependency diffs. |
| `apps/api/tests/test_task_runs.py` | Added coverage for generated review artifacts satisfying planned `llm_v1` review tasks. |
| `docs/p15b-freeze-review.md` | Added P15b freeze decision, first failed run evidence, follow-up fix evidence, build/preview/staging evidence, caveats, and recommended tag. |
| `docs/project-state.md` | Recorded P15b-7 behavior, evidence, and remaining caveats. |
| `docs/change-log.md` | Recorded this freeze review. |
| `openspec/changes/agenthub-p15b-real-llm-planner-engine/tasks.md` | Marked P15b-7 and validation complete after verification. |

### What Changed

P15b now proves the real LLM planner path end to end: the Breakout request was
planned by the Claude CLI planner provider with planner source `real_llm`, then
executed through real coding adapters. The initial Claude Code implementation
produced diff/review/preview evidence but failed local staging deploy because
`pnpm build` caught a TypeScript strictness error. A follow-up fix used the same
AgentHub task/run path; Claude Code recorded a real provider runtime error, then
Codex completed the fix, build passed, preview was healthy, and local staging
deploy was ready.

### Validation

| Command | Result |
|---|---|
| P15b-7 real planner / Breakout smoke | Pass after follow-up: staging deploy `f26b64e1-0174-46be-8040-e978b7eacd22` ready at `http://127.0.0.1:65495`. |
| P15b-7 targeted planner / scheduler / task-run tests | Pass: 31 tests. |
| `pnpm check` | Pass. |
| `pnpm test` | Pass: web 41 tests, API 289 tests, demo-api 5 tests. |
| `pnpm demo:api:test` | Pass: 5 tests. |
| `git diff --check` | Pass. |
| `openspec validate agenthub-p15b-real-llm-planner-engine --strict` | Pass. |

---

## P15b-6 Planner Evidence And Mission Trace

**Date:** 2026-05-28

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/llm_planner.py` | Recorded safe planner evidence on created `llm_v1` tasks, including provider identity, source, duration, validation result, rationale, plan ID, and created task IDs. |
| `apps/api/app/mission_trace.py` | Exposed planner evidence for real/fake LLM, disabled/fallback, and deterministic planning paths in mission trace task entries. |
| `apps/api/tests/test_llm_planner.py` | Added planner evidence and mission trace coverage for fake/test planner output without raw provider output leakage. |
| `docs/project-state.md` | Recorded P15b-6 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p15b-real-llm-planner-engine/tasks.md` | Marked P15b-6 complete after verification. |

### What Changed

`llm_v1` task plans now keep auditable planner evidence after successful schema
and policy validation. Mission trace exposes planner source as real/fake,
disabled/fallback, or deterministic depending on the path. Evidence is metadata
only; raw provider output and credentials are not included.

### Validation

| Command | Result |
|---|---|
| P15b-6 targeted planner evidence / mission trace tests | Pass: 6 tests. |

---

## P15b-5 PlanValidator Hardening For Real LLM Output

**Date:** 2026-05-28

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/plan_validator.py` | Hardened task graph validation for registered target policy, platform mode, agent profile capability/safety, validation command policy, and dependency keys. |
| `apps/api/app/llm_planner.py` | Passed enabled AgentProfile metadata into PlanValidator for `llm_v1` task creation. |
| `apps/api/tests/test_llm_planner.py` | Added rejection coverage for unsafe role/write capability and unsupported validation command output. |
| `docs/project-state.md` | Recorded P15b-5 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p15b-real-llm-planner-engine/tasks.md` | Marked P15b-5 complete after verification. |

### What Changed

Real LLM candidate task graphs now pass through stricter policy validation
before tasks are persisted. Validation checks known targets, target path policy,
platform mode/approval requirements, AgentProfile supported targets/modes,
safe-for-write and safe-for-review flags, dependency key references, and
target-scoped validation command policy.

Unsafe plans fail honestly before TaskRun auto-start or persistence.

### Validation

| Command | Result |
|---|---|
| P15b-5 targeted LLM planner/contract/planning tests | Pass: 40 tests. |

---

## P15b-4 Structured Output Parsing And Validation

**Date:** 2026-05-28

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/llm_planner.py` | Added safe JSON extraction for a single embedded planner JSON object and rejection for ambiguous multiple payloads. |
| `apps/api/tests/test_planner_contracts.py` | Added embedded JSON extraction, ambiguous JSON rejection, missing-field rejection, and no-silent-normalization coverage. |
| `docs/project-state.md` | Recorded P15b-4 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p15b-real-llm-planner-engine/tasks.md` | Marked P15b-4 complete after verification. |

### What Changed

Planner output parsing now accepts either direct JSON or one safely extracted
outer JSON object from provider prose/fenced output. Multiple outer JSON
payloads are treated as ambiguous and rejected. The extracted payload still
must satisfy the `PlannerResponse` schema before task graph validation.

The parser does not silently rewrite unknown targets, roles, paths, or unsafe
values into allowed values; those continue into policy validation unchanged and
must be rejected there.

### Validation

| Command | Result |
|---|---|
| P15b-4 targeted planner contract/LLM planner/provider tests | Pass: 24 tests. |

---

## P15b-3 Real Planner Provider Implementation

**Date:** 2026-05-28

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planner_providers.py` | Added `claude_cli` real planner provider path, constrained command shape, timeout handling, and normalized auth/quota/runtime/unavailable errors. |
| `apps/api/app/config.py` | Added `AGENTHUB_LLM_PLANNER_TIMEOUT_SEC` for real planner provider timeout control. |
| `apps/api/tests/test_planner_providers.py` | Added `claude_cli` resolver, command-shape, success, timeout, missing binary, and normalized error coverage. |
| `docs/project-state.md` | Recorded P15b-3 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p15b-real-llm-planner-engine/tasks.md` | Marked P15b-3 complete after verification. |

### What Changed

AgentHub can now explicitly select `AGENTHUB_LLM_PLANNER_PROVIDER=claude_cli`
as a real planner provider. The provider invokes Claude CLI in print mode with
a planning-only prompt, captures stdout/stderr, applies a timeout, and records
normalized failures for auth, quota, timeout, unavailable executable, empty
output, and runtime errors.

This only adds the real provider path. It does not run a real planner smoke,
does not claim planner success, and still requires structured parsing,
validation, and later rehearsal before freeze.

### Validation

| Command | Result |
|---|---|
| P15b-3 targeted planner provider/contract/LLM planner tests | Pass: 20 tests. |

---

## P15b-2 Planner Request / Response Contract

**Date:** 2026-05-28

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planner_contracts.py` | Added `PlannerRequest`, `PlannerResponse`, planner task response schema, and provider-visible redaction helper. |
| `apps/api/app/llm_planner.py` | Added `build_llm_planner_request`, routed existing planner input through the request contract, and schema-validates planner output with `PlannerResponse`. |
| `apps/api/tests/test_planner_contracts.py` | Added request context, protected-value redaction, response schema, incomplete response rejection, and parse integration coverage. |
| `apps/api/tests/test_llm_planner.py` | Updated fake planner payloads to the formal response contract. |
| `docs/project-state.md` | Recorded P15b-2 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p15b-real-llm-planner-engine/tasks.md` | Marked P15b-2 complete after verification. |

### What Changed

`llm_v1` planning now has formal request and response contracts. The request
preserves the original user request, includes canonical context, target
registry/project analyzer summaries, recent messages, artifact references,
supported roles/modes/capabilities, and guardrails, then redacts provider-visible
secret-like values and protected absolute paths.

Planner output is now checked against `PlannerResponse` before the existing
PlanValidator path. This defines the required plan/task fields that later real
provider output must satisfy.

### Validation

| Command | Result |
|---|---|
| P15b-2 targeted planner contract/provider/planning tests | Pass: 40 tests. |

---

## P15b-1 Planner Provider Abstraction

**Date:** 2026-05-28

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planner_providers.py` | Added planner provider interface, result/error metadata, disabled provider, fake/test provider, and explicit provider resolver. |
| `apps/api/app/config.py` | Added `AGENTHUB_LLM_PLANNER_PROVIDER` setting with disabled default. |
| `apps/api/app/llm_planner.py` | Wired planner provider result metadata into LLM planner task metadata and fallback metadata. |
| `apps/api/app/planning.py` | Recorded selected planner provider metadata in deterministic fallback plans and rejected unknown planner provider configuration honestly. |
| `apps/api/tests/test_planner_providers.py` | Added provider abstraction, disabled/fake provider, selection, invalid provider, and fallback metadata coverage. |
| `apps/api/tests/test_llm_planner.py` | Updated LLM planner tests to use the fake/test planner provider result contract. |
| `apps/api/tests/test_planning.py` | Updated fallback metadata expectations to include planner provider identity and source. |
| `docs/project-state.md` | Recorded P15b-1 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p15b-real-llm-planner-engine/tasks.md` | Marked P15b-1 complete after verification. |

### What Changed

AgentHub now has an explicit planner-provider foundation for `llm_v1`:
disabled and fake/test providers, standard provider result/error metadata,
explicit provider selection by `AGENTHUB_LLM_PLANNER_PROVIDER`, and planner
fallback metadata that records provider ID, provider type, planner source, and
status.

This does not add a real LLM planner call yet. Unknown provider configuration
is reported as an invalid provider fallback instead of silently substituting a
different provider.

### Validation

| Command | Result |
|---|---|
| P15b-1 targeted planner/provider tests | Pass: 35 tests. |

---

## P15-7 Freeze Review

**Date:** 2026-05-28

### Modified Files

| File | Change |
|---|---|
| `docs/p15-freeze-review.md` | Added P15 freeze decision, Breakout evidence, non-goals, caveats, and recommended tag. |
| `docs/project-state.md` | Recorded P15 freeze status. |
| `docs/change-log.md` | Recorded this freeze review. |
| `openspec/changes/agenthub-p15-real-coding-assistant-upgrade/tasks.md` | Marked P15-7, explicit non-goals, and validation complete after verification. |

### What Changed

P15 freeze review confirms AgentHub is ready to freeze as Real Coding Assistant
Upgrade. The phase preserves prior baselines while enabling bounded
target-scoped frontend implementation requests to run through passthrough
instructions and real Claude Code execution.

### Validation

| Command | Result |
|---|---|
| Final P15 validation suite | Pass. |

---

## P15-6 Breakout Game Real Coding Smoke

**Date:** 2026-05-28

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planning.py` | Added generic `passthrough_v1` routing for bounded frontend implementation requests inside the registered demo frontend target. |
| `apps/api/app/claude_code_adapter.py` | Allowed Claude Code to use `Write` alongside `Read`, `Edit`, and `MultiEdit` so real runs can create new files inside the assigned worktree. |
| `apps/api/app/guardrails.py` | Updated the documented Claude Code command allowlist to permit the expanded write tool set. |
| `apps/api/app/diffs.py` | Included untracked files in diff artifacts, stats, changed files, and downstream review/ledger evidence. |
| `apps/api/tests/test_planning.py` | Added no-mention Breakout request coverage for `passthrough_v1` routing. |
| `apps/api/tests/test_claude_code_adapter.py` | Updated Claude Code command-shape coverage for `Write`. |
| `apps/api/tests/test_guardrails.py` | Updated runtime command policy coverage for the expanded Claude Code tool list. |
| `apps/api/tests/test_diffs.py` | Added untracked file diff collection coverage. |
| `docs/p15-breakout-smoke.md` | Recorded real Claude Code Breakout smoke evidence and caveats. |
| `docs/project-state.md` | Recorded P15-6 behavior, evidence, and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p15-real-coding-assistant-upgrade/tasks.md` | Marked P15-6 complete after targeted verification and smoke evidence. |

### What Changed

AgentHub can now route a bounded frontend implementation request into
`passthrough_v1` without rewriting it into the old demo template. The Breakout
smoke used real `ClaudeCodeAdapter` execution and produced a completed run,
real diff, scripted review, target-scoped build evidence, healthy preview, and
local staging deployment.

The smoke also fixed two practical execution blockers discovered by real use:
Claude Code needed `Write` permission for new files, and diff collection needed
to include untracked agent-created files.

### Validation

| Command / Smoke | Result |
|---|---|
| P15-6 targeted planning/adapter/guardrail/diff tests | Pass: 6 tests. |
| Real Breakout smoke | Pass with caveat: browser-click automation unavailable. |

---

## P15-5 Planner Rationale And Task Review Metadata

**Date:** 2026-05-28

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/schemas.py` | Added `planReviewMetadata` to task responses. |
| `apps/api/app/main.py` | Derived read-only plan review metadata from `planJson`, `planDraft`, task graph, dependencies, planned files, acceptance criteria, and validation expectations. |
| `apps/api/tests/test_planning.py` | Added API coverage for planner mode, rationale, target, planned files, task graph, and read-only metadata. |
| `apps/web/src/lib/api.ts` | Added client type support for plan review metadata. |
| `apps/web/src/components/task-card-list.tsx` | Rendered a compact read-only plan review summary in task cards. |
| `apps/web/src/components/task-card-list.test.tsx` | Added UI coverage for planner rationale, task graph count, target, planned files, acceptance, validation, and read-only state. |
| `docs/project-state.md` | Recorded P15-5 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p15-real-coding-assistant-upgrade/tasks.md` | Marked P15-5 complete after targeted verification. |

### What Changed

Task responses now expose a read-only `planReviewMetadata` summary so the UI can
show how a task was planned without mutating the plan. The task card timeline
shows planner mode, target, rationale, assigned role, planned files, task graph
count, acceptance criteria count, and validation expectation count.

The metadata is derived from existing plan data and does not alter scheduling,
adapter dispatch, task execution, or plan editing behavior.

### Validation

| Command | Result |
|---|---|
| P15-5 targeted API/UI metadata tests | Pass: 46 tests. |

---

## P15-4 Project Command Policy

**Date:** 2026-05-28

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/project_command_policy.py` | Added target-scoped command policy evaluation derived from Target Registry check/test/build commands. |
| `apps/api/app/external_evidence.py` | Validated target-scoped command evidence against the selected target policy and recorded `targetId` in artifact metadata/events. |
| `apps/api/app/schemas.py` | Added optional `targetId` to command evidence create/response schemas. |
| `apps/api/app/main.py` | Passed `targetId` through the command evidence API and response mapping. |
| `apps/api/tests/test_external_evidence.py` | Added coverage for target-scoped command evidence acceptance, target ID recording, and wrong-command rejection. |
| `docs/project-state.md` | Recorded P15-4 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p15-real-coding-assistant-upgrade/tasks.md` | Marked P15-4 complete after targeted verification. |

### What Changed

Command evidence can now be target-aware. When a command evidence request or
task plan identifies a target, AgentHub checks the command against that target's
registered `checkCommand`, `testCommand`, or `buildCommand` before storing the
evidence. Stored command evidence records stdout, stderr, exit code, status,
command type, command string, and target ID honestly.

Legacy command evidence without a target remains compatible with the existing
global allowlist path.

### Validation

| Command | Result |
|---|---|
| P15-4 targeted command evidence/review/instruction tests | Pass: 9 tests. |

---

## P15-3 Permissive Target Guardrails

**Date:** 2026-05-28

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/guardrails.py` | Added target-aware path evaluation that combines registered target allowed/denied paths with existing protected path checks. |
| `apps/api/app/main.py` | Updated orchestrator auto-start safety checks to use Target Registry path policy instead of the older narrow demo file allowlist. |
| `apps/api/tests/test_guardrails.py` | Added target path policy coverage for allowed target files, cross-target files, and protected dependency paths. |
| `apps/api/tests/test_planning.py` | Added auto-start policy coverage for broader frontend target files under registered allowed paths. |
| `docs/project-state.md` | Recorded P15-3 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p15-real-coding-assistant-upgrade/tasks.md` | Marked P15-3 complete after targeted verification. |

### What Changed

Registered target metadata now drives the safety boundary for broader coding
tasks. Safe frontend auto-run can cover meaningful files inside
`demo-frontend` allowed paths, such as new components under `apps/demo/src`,
without falling back to the old login-page-only file list.

The broader permission is still target-scoped. Protected paths, denied paths,
cross-target backend/platform paths, absolute paths, traversal paths, and
ordinary platform-code modification remain blocked.

### Validation

| Command | Result |
|---|---|
| P15-3 targeted guardrail and planning tests | Pass: 5 tests. |

---

## P15-2 Passthrough Instruction Mode

**Date:** 2026-05-28

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/instruction_builder.py` | Added passthrough instruction rendering for `llm_v1` / `passthrough_v1` plans before deterministic demo-template branches. |
| `apps/api/tests/test_task_runs.py` | Added Breakout-style instruction coverage proving the original request is preserved and old demo-slot rewrite is skipped. |
| `docs/project-state.md` | Recorded P15-2 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p15-real-coding-assistant-upgrade/tasks.md` | Marked P15-2 complete after targeted verification. |

### What Changed

Provider instructions now preserve original request/task descriptions for
`llm_v1` and `passthrough_v1` plans. The shared target, context, contract,
artifact, acceptance, validation, and guardrail sections still render through
the existing provider-specific wrappers, but old login-page/button/demo-slot
instructions no longer override passthrough plans.

### Validation

| Command | Result |
|---|---|
| P15-2 targeted instruction tests | Pass: 4 tests. |

---

## P15-1 LLM Planner v1

**Date:** 2026-05-28

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/llm_planner.py` | Added LLM planner input builder, structured JSON parser, PlanDraft/task creation service, target/role validation, and fallback metadata helper. |
| `apps/api/app/planner_service.py` | Extended PlanDraft metadata with planner mode, acceptance criteria, validation expectations, guardrail notes, and fallback reason. |
| `apps/api/app/plan_validator.py` | Allowed validation against registered target allowed paths for LLM planner outputs while preserving old demo defaults. |
| `apps/api/app/config.py` | Added `AGENTHUB_LLM_PLANNER_ENABLED` setting, disabled by default. |
| `apps/api/app/planning.py` | Recorded explicit `llm_v1` fallback metadata on orchestrator deterministic fallback plans. |
| `apps/api/tests/test_llm_planner.py` | Added LLM planner input, valid output, task persistence, and unsafe output rejection coverage. |
| `apps/api/tests/test_planning.py` | Added regression assertions for PlanDraft planner mode and disabled LLM fallback metadata. |
| `docs/project-state.md` | Recorded P15-1 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p15-real-coding-assistant-upgrade/tasks.md` | Marked P15-1 complete after targeted verification. |

### What Changed

P15 now has an `llm_v1` planning foundation without claiming a live LLM planner
success. The new planner service can build provider-visible planning context,
parse structured JSON output, validate target/role/file safety through
PlanValidator, and persist validated tasks. Existing deterministic paths remain
the runtime default and now record why `llm_v1` was not used.

### Validation

| Command | Result |
|---|---|
| P15-1 targeted planner tests | Pass: 7 tests. |

---

## P14-7 Rehearsal And Freeze Review

**Date:** 2026-05-28

### Modified Files

| File | Change |
|---|---|
| `docs/p14-freeze-review.md` | Added P14 freeze decision, rehearsal evidence, caveats, and recommended tag. |
| `docs/project-state.md` | Recorded P14-7 freeze result and current P14 status. |
| `docs/change-log.md` | Recorded this freeze review. |
| `openspec/changes/agenthub-p14-custom-agent-provider-foundation/tasks.md` | Marked P14-7, explicit non-goals, and validation complete after verification. |

### What Changed

P14 freeze review confirmed the custom agent/provider foundation is complete
without adding marketplace behavior or unsafe custom execution. The review
verified built-in profiles, provider-aware selection, capability/target
rejection, Agent Contact UI metadata, safe draft metadata, deterministic
mixed-provider evidence, and P6-P13 baseline preservation.

### Validation

| Command | Result |
|---|---|
| P14 targeted backend rehearsal tests | Pass: 11 tests. |
| P14 targeted frontend UI/API tests | Pass: 9 files / 40 tests. |

---

## P14-6 Safe Custom Agent Draft

**Date:** 2026-05-28

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/models.py` | Added `AgentProfileDraft` metadata table for safe draft profiles. |
| `apps/api/app/agent_profile_drafts.py` | Added draft creation/listing service with safety validation. |
| `apps/api/app/agent_profiles.py` | Converted draft rows into AgentProfile registry responses. |
| `apps/api/app/schemas.py` | Added draft creation request schema. |
| `apps/api/app/main.py` | Added draft create/list endpoints and included drafts in workspace AgentProfile registry responses. |
| `apps/api/tests/test_agent_profile_drafts.py` | Added API coverage for review-only draft creation and unsafe draft rejection. |
| `apps/api/tests/test_models.py` | Updated model boundary coverage for the new metadata table. |
| `docs/project-state.md` | Recorded P14-6 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p14-custom-agent-provider-foundation/tasks.md` | Marked P14-6 complete after targeted verification. |

### What Changed

AgentHub can now define safe custom AgentProfile draft metadata without making
drafts executable write agents. Draft profiles are forced to review-only or
disabled states and are included in the AgentProfile registry for inspection.

Draft creation rejects arbitrary shell commands, unsafe tool permissions,
unrestricted filesystem access, write capability, unknown providers, and
adapter/provider mismatch.

### Validation

| Command | Result |
|---|---|
| Safe draft/model/profile targeted tests | Pass: 6 tests. |

---

## P14-5 Agent Contact UI Upgrade

**Date:** 2026-05-28

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/schemas.py` | Added provider ID, supported targets, and supported modes to the Agent contact response contract. |
| `apps/api/app/main.py` | Returned P14 profile metadata from `/workspaces/{workspace_id}/agents`, including virtual review/fallback contacts. |
| `apps/api/tests/test_planning.py` | Added contact API assertions for provider and target/mode metadata. |
| `apps/web/src/lib/api.ts` | Added provider/target/mode fields to the AgentContact client type. |
| `apps/web/src/components/agent-contact-list.tsx` | Rendered provider badges, supported target chips, capability chips, and unavailable/auth/draft/disabled status labels. |
| `apps/web/src/lib/api.test.ts` | Updated contact API client fixture coverage for provider and target metadata. |
| `apps/web/src/app/page.test.tsx` | Updated page fixture AgentContact metadata. |
| `apps/web/src/components/workspace-shell.test.tsx` | Added UI assertions for provider and supported target display. |
| `docs/project-state.md` | Recorded P14-5 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p14-custom-agent-provider-foundation/tasks.md` | Marked P14-5 complete after targeted verification. |

### What Changed

The existing Agent Contact UI now exposes the P14 registry metadata already
used by backend policy: provider identity, adapter type, supported targets,
capability tags, and availability status. The visual Direct chat / Group
workflow modes and all task execution controls are unchanged.

### Validation

| Command | Result |
|---|---|
| Web contact/API/page targeted tests | Pass: 40 tests. |
| Workspace agent contact API targeted test | Pass: 1 test. |

---

## P14-4 Agent Selection Policy

**Date:** 2026-05-28

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/agent_selection_policy.py` | Added target, mode, capability, write-safety, and review-safety validation for TaskRun agent selection. |
| `apps/api/app/task_runs.py` | Applied Agent Selection Policy during TaskRun creation and recorded selection metadata in TaskRun metrics. |
| `apps/api/app/agent_profiles.py` | Added explicit platform-maintenance support metadata to the backend profile while preserving scheduler approval gates. |
| `apps/api/tests/test_agent_selection_policy.py` | Added selection-policy coverage for metadata, unsupported targets, missing capabilities, and unsafe review assignment. |
| `docs/project-state.md` | Recorded P14-4 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p14-custom-agent-provider-foundation/tasks.md` | Marked P14-4 complete after verification. |

### What Changed

TaskRun creation now validates the assigned agent profile against the task's
target, required mode, required capabilities, and write/review safety flags.
Invalid target or capability assignments fail honestly before adapter
execution. Successful runs record `agentSelection` metadata in
`TaskRun.metricsJson`.

Platform maintenance remains approval-gated by the existing scheduler and
guardrail path; P14-4 only makes profile support explicit enough for the
selection policy.

### Validation

| Command | Result |
|---|---|
| Targeted agent selection policy tests | Pass: 4 tests. |
| Platform maintenance TaskRun regression test | Pass: 1 test. |

---

## P14-3 Capability And Mode Schema

**Date:** 2026-05-28

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/agent_capabilities.py` | Added controlled supported modes and capability tags with validation helpers. |
| `apps/api/app/agent_profiles.py` | Aligned built-in AgentProfile capability tags and supported modes to the controlled schema. |
| `apps/api/app/provider_configs.py` | Validated provider config supported modes against the controlled schema. |
| `apps/api/tests/test_agent_capabilities.py` | Added schema and rejection coverage for unsupported modes/capability tags. |
| `apps/api/tests/test_planning.py` | Updated AgentProfile and contact assertions to controlled capability/mode values. |
| `apps/web/src/lib/api.test.ts` | Updated API fixtures for controlled capability/mode values. |
| `docs/project-state.md` | Recorded P14-3 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p14-custom-agent-provider-foundation/tasks.md` | Marked P14-3 complete after verification. |

### What Changed

AgentHub now defines controlled execution modes:

- `frontend`;
- `backend`;
- `qa`;
- `review`;
- `platform_maintenance`;
- `read_only`;
- `debug`.

AgentHub also defines controlled capability tags:

- `code_write`;
- `code_review`;
- `test_run`;
- `diff_analysis`;
- `preview`;
- `deploy_staging`;
- `platform_change`.

Built-in AgentProfile and ProviderConfig metadata now uses these controlled
values. Unsupported values fail validation instead of becoming free-form
permissions.

### Validation

| Command | Result |
|---|---|
| Targeted capability/profile/provider tests | Pass: 5 tests. |
| Targeted web API tests | Pass: 40 tests. |

---

## P14-2 Provider Config Registry

**Date:** 2026-05-28

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/provider_configs.py` | Added non-secret provider config metadata for Claude Code CLI, Codex CLI, and Scripted Mock. |
| `apps/api/app/schemas.py` | Added ProviderConfig API response schema. |
| `apps/api/app/main.py` | Added read-only `/provider-configs` endpoint. |
| `apps/api/tests/test_provider_configs.py` | Added provider config API coverage and secret-field guard. |
| `apps/web/src/lib/api.ts` | Added ProviderConfig client type and `listProviderConfigs`. |
| `apps/web/src/lib/api.test.ts` | Added web API coverage for provider config metadata. |
| `docs/project-state.md` | Recorded P14-2 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p14-custom-agent-provider-foundation/tasks.md` | Marked P14-2 complete after verification. |

### What Changed

AgentHub now exposes a read-only Provider Config Registry for current local
providers:

- Claude Code CLI;
- Codex CLI;
- Scripted Mock.

Provider config metadata includes provider ID, display name, adapter type,
auth status, availability, default roles, and supported modes. The registry
does not store or expose secrets, tokens, API keys, or raw credentials.

P14-2 does not implement cloud token management, provider marketplace behavior,
provider installation, or adapter dispatch changes.

### Validation

| Command | Result |
|---|---|
| Targeted provider config API test | Pass: 1 test. |
| Targeted web API tests | Pass: 40 tests. |

---

## P14-1 Agent Profile Registry

**Date:** 2026-05-28

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/agent_profiles.py` | Promoted AgentProfile into a registry-style service, added status, and added virtual review/fallback profiles. |
| `apps/api/app/schemas.py` | Added AgentProfile `status` to API responses. |
| `apps/api/app/main.py` | Returned registry profiles, including built-in review and fallback profiles, from the workspace profile API. |
| `apps/api/tests/test_planning.py` | Updated profile API coverage for registry fields, status, review profile, and fallback profile. |
| `apps/web/src/lib/api.ts` | Added `status` to the AgentProfile client type. |
| `apps/web/src/lib/api.test.ts` | Updated client API fixture coverage for AgentProfile status. |
| `docs/project-state.md` | Recorded P14-1 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p14-custom-agent-provider-foundation/tasks.md` | Marked P14-1 complete after verification. |

### What Changed

AgentHub now exposes a stable Agent Profile Registry contract for built-in
profiles. The workspace profile API includes active database-backed agents plus
virtual review and fallback profiles. Profiles now include `status` so
available, planned, disabled, or future draft-only states can be represented
without implying write execution.

P14-1 does not add provider config, capability enforcement, custom draft
creation, marketplace behavior, or adapter dispatch changes.

### Validation

| Command | Result |
|---|---|
| Targeted profile API tests | Pass: 2 tests. |
| Targeted web API tests | Pass: 39 tests. |

---

## P13-8 Mixed-provider Rehearsal and Freeze Review

**Date:** 2026-05-27

### Modified Files

| File | Change |
|---|---|
| `apps/api/tests/test_cross_provider_rehearsal.py` | Added deterministic P13 freeze rehearsal for backend=Codex and frontend=Claude Code provider assignments through diff/review/preview/local staging deploy evidence. |
| `docs/p13-freeze-review.md` | Recorded P13 freeze decision, rehearsal path, evidence, and caveats. |
| `docs/project-state.md` | Recorded P13-8 freeze result and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p13-cross-provider-agent-coordination/tasks.md` | Marked P13-8 and explicit non-goals complete after verification. |

### What Changed

P13 now has a deterministic freeze rehearsal that simulates a bounded mixed
provider workflow without claiming live Claude/Codex execution. The rehearsal
creates a shared mini CRM contract, assigns backend work to Codex and frontend
work to Claude Code, verifies provider-aware handoff metadata, captures diff
and review evidence, starts a healthy preview, records a local staging
deployment, and checks mission trace provider visibility.

### Validation

| Command | Result |
|---|---|
| P13 mixed-provider rehearsal test | Pass: 1 test. |

---

## P13-7 Mixed-provider Scheduler Integration

**Date:** 2026-05-27

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/scheduler.py` | Preserved provider ID, provider assignment, retry ID, and fallback ID in terminal scheduler metadata. |
| `apps/api/tests/test_scheduler.py` | Added mixed-provider scheduler coverage for dependencies, target locks, different-target concurrency, and failure metadata. |
| `docs/project-state.md` | Recorded P13-7 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p13-cross-provider-agent-coordination/tasks.md` | Marked P13-7 complete after verification. |

### What Changed

Scheduler terminal metadata now keeps provider assignment details alongside the
existing adapter type. Retry and fallback references are also preserved when
present, so recovery state remains auditable in mixed-provider workflows.

Regression coverage verifies:

- frontend Claude Code tasks wait for backend Codex dependencies;
- same-target write locks are provider independent;
- different frontend/backend targets can queue with different providers;
- failed mixed-provider runs preserve provider assignment in scheduler state.

### Validation

| Command | Result |
|---|---|
| Targeted mixed-provider scheduler tests | Pass: 4 tests. |
| Full scheduler tests | Pass: 23 tests. |

---

## P13-6 Cross-provider Evidence Normalization

**Date:** 2026-05-27

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/provider_evidence.py` | Added a shared provider evidence normalizer for TaskRun-backed artifacts. |
| `apps/api/app/diffs.py` | Added provider evidence to diff artifact metadata and diff-ready events. |
| `apps/api/app/reviews.py` | Added scripted review provider evidence and origin provider evidence to review artifacts/events. |
| `apps/api/app/previews.py` | Added provider evidence to preview artifact metadata and preview-ready events. |
| `apps/api/app/deployments.py` | Added provider evidence to deployment artifact metadata and deploy events. |
| `apps/api/tests/test_diffs.py` | Added coverage for diff and review evidence metadata. |
| `apps/api/tests/test_previews.py` | Added coverage for preview evidence metadata. |
| `apps/api/tests/test_deployments.py` | Added coverage for deployment evidence metadata. |
| `docs/project-state.md` | Recorded P13-6 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p13-cross-provider-agent-coordination/tasks.md` | Marked P13-6 complete after verification. |

### What Changed

Diff, scripted review, preview, and deployment artifacts now include normalized
provider evidence derived from TaskRun metadata. The evidence records task run
ID, run status, adapter type, provider ID, provider assignment metadata,
changed files, logs where relevant, artifact references, and retry/fallback
references when present.

Scripted review artifacts also record `originProviderEvidence`, preserving the
identity of the provider-backed coding run that produced the reviewed diff
instead of masking it behind the deterministic review adapter.

### Validation

| Command | Result |
|---|---|
| Targeted diff/review/preview/deploy evidence tests | Pass: 4 tests. |

---

## P13-5 Provider-specific Instruction Mapping

**Date:** 2026-05-27

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/instruction_adapters/codex.py` | Added a Codex-specific instruction wrapper while preserving the shared core instruction. |
| `apps/api/app/instruction_adapters/claude_code.py` | Added a Claude Code-specific instruction wrapper while preserving the shared core instruction. |
| `apps/api/tests/test_task_runs.py` | Added regression coverage that Codex and Claude Code instructions preserve the same canonical contract, target, handoff, validation, and guardrail facts. |
| `docs/project-state.md` | Recorded P13-5 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p13-cross-provider-agent-coordination/tasks.md` | Marked P13-5 complete after verification. |

### What Changed

Codex and Claude Code instruction adapters now apply provider-specific wrapper
text while keeping the shared role instruction and Canonical Shared Context
unchanged. This lets provider prompt formatting differ without dropping shared
mission facts.

Regression coverage verifies both providers preserve the same contract ID,
frontend/backend target IDs, upstream handoff references, implemented route
details, validation expectations, and guardrails.

### Validation

| Command | Result |
|---|---|
| Targeted provider instruction mapping tests | Pass: 2 tests. |
| Full TaskRun tests | Pass: 52 tests. |

---

## P13-4 Handoff Protocol v1

**Date:** 2026-05-27

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/handoffs.py` | Added provider-aware handoff metadata, diff-based changed files, implemented route/component hints, review warnings, and suggested follow-up scope. |
| `apps/api/tests/test_task_runs.py` | Added handoff protocol coverage for frontend-to-review and review-to-fix transitions, downstream canonical context, and mission trace visibility. |
| `docs/project-state.md` | Recorded P13-4 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p13-cross-provider-agent-coordination/tasks.md` | Marked P13-4 complete after verification. |

### What Changed

Handoff artifacts now carry provider-aware metadata for cross-provider
transitions:

- `fromProviderId` / `fromAdapterType`;
- `toProviderId` / `toAdapterType`;
- changed files from the latest diff artifact when available;
- implemented route and component hints;
- artifact references;
- review warnings and suggested follow-up scope;
- verification status and risk notes.

Downstream session context and Canonical Shared Context include the enriched
handoff metadata, and mission trace exposes the same artifact metadata through
existing artifact navigation.

### Validation

| Command | Result |
|---|---|
| Targeted handoff protocol tests | Pass: 2 tests. |
| Full TaskRun tests | Pass: 51 tests. |

---

## P13-3 Canonical Context Usage Enforcement

**Date:** 2026-05-27

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/instruction_adapters/shared_sections.py` | Rendered provider-visible instruction context from the filtered Canonical Shared Context instead of the legacy session context payload. |
| `apps/api/app/instruction_builder.py` | Used canonical safe paths when listing preferred frontend files so protected plan paths are not copied into provider instructions. |
| `apps/api/tests/test_task_runs.py` | Added coverage for Canonical Shared Context rendering, legacy context exclusion, protected path filtering, and snapshot persistence. |
| `docs/project-state.md` | Recorded P13-3 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p13-cross-provider-agent-coordination/tasks.md` | Marked P13-3 complete after verification. |

### What Changed

CodexAdapter and ClaudeCodeAdapter TaskRun instructions now include a
`Canonical Shared Context` JSON section sourced from the filtered
`canonical_shared_context_v1` contract. The old `legacyContext` payload is no
longer rendered into provider instructions.

Frontend role instructions now derive preferred file lists from canonical safe
paths instead of raw plan files, preventing protected values such as dependency
directory paths, host absolute paths, or secret-bearing metadata from leaking
through the human-readable instruction body.

TaskRun metadata continues to persist `canonicalContextSnapshot`, preserving an
auditable record of what context was prepared for provider execution.

### Validation

| Command | Result |
|---|---|
| Targeted canonical-context instruction tests | Pass: 3 tests. |
| Full TaskRun tests | Pass: 50 tests. |

---

## P13-2 Provider-aware Agent Profile

**Date:** 2026-05-26

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/agent_profiles.py` | Added supported role metadata and aligned AgentProfile adapter/provider fields with P13 provider assignment policy. |
| `apps/api/app/provider_assignments.py` | Added read-only profile provider assignment resolution using configured role assignments or built-in provider defaults. |
| `apps/api/app/schemas.py` | Added `supportedRoles` to AgentProfile API responses. |
| `apps/api/app/main.py` | Returned supported roles in workspace agent profile responses. |
| `apps/api/tests/test_planning.py` | Added API coverage for provider-aware profiles and assignment-matched profile metadata. |
| `apps/web/src/lib/api.ts` | Added `supportedRoles` to the AgentProfile client type. |
| `apps/web/src/lib/api.test.ts` | Updated profile API fixture coverage for provider-aware metadata. |
| `docs/project-state.md` | Recorded P13-2 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p13-cross-provider-agent-coordination/tasks.md` | Marked P13-2 complete after verification. |

### What Changed

AgentProfile responses now expose `supportedRoles` in addition to provider ID,
adapter type, supported targets, supported modes, and safety flags.
Built-in profiles map current role agents to provider-aware defaults such as
`frontend -> local-codex-cli`, `backend -> local-codex-cli`, and
`qa/review -> local-scripted-review`.

When `AGENTHUB_PROVIDER_ASSIGNMENT_MATRIX.roles` configures a built-in role,
the corresponding AgentProfile reflects that configured adapter/provider
choice. This keeps profile metadata compatible with the P13-1 provider
assignment matrix without adding user-created custom agents or changing
execution dispatch behavior.

### Validation

| Command | Result |
|---|---|
| Targeted agent profile API tests | Pass: 2 tests. |
| Targeted web API tests | Pass: 39 tests. |

---

## P13-1 Provider Assignment Matrix

**Date:** 2026-05-26

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/provider_assignments.py` | Added provider assignment matrix resolution for role defaults, target overrides, explicit adapter selection, and legacy default fallback metadata. |
| `apps/api/app/task_runs.py` | Routed TaskRun adapter selection through provider assignment resolution and recorded assignment metadata on runs and state events. |
| `apps/api/app/mission_trace.py` | Exposed provider assignment metadata in mission trace TaskRun entries. |
| `apps/api/tests/test_task_runs.py` | Added Provider Assignment Matrix tests for frontend, backend, review, target override, legacy fallback, invalid assignment rejection, and mission trace visibility. |
| `docs/project-state.md` | Recorded P13-1 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p13-cross-provider-agent-coordination/tasks.md` | Marked P13-1 complete after targeted verification. |

### What Changed

P13-1 adds an explicit and auditable provider assignment foundation. Runtime
configuration may assign providers by role through
`AGENTHUB_PROVIDER_ASSIGNMENT_MATRIX.roles` and may override by target through
`AGENTHUB_PROVIDER_ASSIGNMENT_MATRIX.targets`. Target-specific assignments
take precedence over role defaults.

TaskRuns now record a `providerAssignment` payload in `metricsJson` with role,
adapter type, provider ID, source, target ID, supported mode, and fallback
policy. Mission trace TaskRun entries expose the same assignment metadata.

Existing adapter selection remains compatible: when no P13 matrix assignment
is configured, AgentHub preserves the legacy Agent metadata and
`AGENTHUB_DEFAULT_CODE_ADAPTER` behavior.

### Validation

| Command | Result |
|---|---|
| Targeted provider assignment tests | Pass: 5 tests. |
| Targeted task run / scheduler / planning tests | Pass: 92 tests. |

---

## P12-10 E2E Rehearsal And Freeze Review

**Date:** 2026-05-26

### Modified Files

| File | Change |
|---|---|
| `docs/p12-freeze-review.md` | Added P12 freeze evidence, caveats, validation notes, and recommended tag. |
| `docs/project-state.md` | Recorded P12 freeze status and evidence IDs. |
| `docs/change-log.md` | Recorded this freeze review. |
| `openspec/changes/agenthub-p12-platform-core-consolidation/tasks.md` | Marked P12-10, non-goals, and validation complete after verification. |

### Review Result

P12 is ready to freeze as Platform Core Consolidation.

The freeze rehearsal verified the consolidated local demo path from a new
session through orchestrator planning, ScriptedMock frontend execution, diff,
review, handoff, preview, local staging deploy, follow-up modification,
artifact version v2, updated preview, and updated local staging deploy.

### Validation

| Command | Result |
|---|---|
| P12 freeze rehearsal | Pass |
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `pnpm demo:api:test` | Pass |
| `git diff --check` | Pass |
| `openspec validate agenthub-p12-platform-core-consolidation --strict` | Pass |

Recommended freeze tag:
`p12-platform-core-consolidation-freeze`.

---

## Repository Hygiene

**Date:** 2026-05-25

### Modified Files

| File | Change |
|---|---|
| `.gitignore` | Added public-doc allowlist rules and ignored internal planning, OpenSpec, research, PDF, Office, and demo evidence documents. |
| `docs/change-log.md` | Recorded repository hygiene cleanup. |

### What Changed

The repository now keeps common public project documents visible while ignoring
internal planning and research documents by default. This keeps future GitHub
pushes focused on source, configuration, tests, and public project entrypoints.

---

## P11-6 E2E Rehearsal And Freeze Review

**Date:** 2026-05-25

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/deployments.py` | Fixed local static serving to use `sys.executable` instead of assuming `python` exists on the host. |
| `apps/api/tests/test_deployments.py` | Added regression coverage for the static server interpreter command. |
| `docs/p11-freeze-review.md` | Added P11 freeze evidence, caveats, validation notes, and recommended tag. |
| `docs/project-state.md` | Recorded P11-6 freeze result and evidence IDs. |
| `docs/change-log.md` | Recorded this freeze review. |
| `openspec/changes/agenthub-p11-real-staging-deploy-provider/tasks.md` | Marked P11-6, non-goals, and validation complete after verification. |

### Review Result

P11 is ready to freeze as Real Staging Deploy Provider.

The freeze rehearsal used a real local staging deploy for the built-in
`demo-frontend` target. It ran `pnpm build`, served the built `dist` directory
on a local URL, verified the URL returned HTML, and recorded deployment logs,
status history, target metadata, and source artifact references.

### Validation

| Command | Result |
|---|---|
| Real local staging rehearsal | Pass |
| Targeted deployment regression tests | Pass |
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `git diff --check` | Pass |
| `openspec validate agenthub-p11-real-staging-deploy-provider --strict` | Pass |

Recommended freeze tag:
`p11-real-staging-deploy-provider-freeze`.

---

## P11-5 Deploy Gate

**Date:** 2026-05-25

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/deployments.py` | Added staging deploy gates for production requests, preview health, failed review, and target policy violations. |
| `apps/api/app/schemas.py` | Added deployment environment request field. |
| `apps/api/app/main.py` | Passed requested deployment environment to `DeployService`. |
| `apps/api/tests/test_deployments.py` | Added deploy gate tests for failed review, unhealthy preview, target policy violation, production rejection, and successful staging path. |
| `docs/project-state.md` | Recorded P11-5 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p11-real-staging-deploy-provider/tasks.md` | Marked P11-5 complete after targeted verification. |

### What Changed

P11-5 adds conservative staging deploy gates before the local staging provider
runs. Staging deploy now rejects production/prod environment requests, failed
or unhealthy preview prerequisites, failed latest review artifacts, and
changed files outside the target registry path policy.

Mock deploy remains available for existing demo and fallback paths.

### Validation

| Command | Result |
|---|---|
| Targeted deployment tests | Pass: 17 tests. |

---

## P11-4 Deploy Logs And Status Artifact

**Date:** 2026-05-25

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/deployments.py` | Added deployment source metadata, logs, status history, failed deployment artifact persistence, and expanded deployment response mapping. |
| `apps/api/app/main.py` | Returned deploy provider type, target/source references, logs, and status history in deployment responses. |
| `apps/api/app/schemas.py` | Added deployment response fields for deploy evidence and status history. |
| `apps/api/tests/test_deployments.py` | Added deployment evidence, failed artifact, and API response coverage. |
| `apps/web/src/lib/api.ts` | Added deploy evidence fields to the frontend API type. |
| `apps/web/src/lib/api.test.ts` | Updated deployment fixture payload coverage. |
| `apps/web/src/components/deploy-card.tsx` | Rendered target/source references, status history, and logs in deployment cards. |
| `apps/web/src/components/deploy-card.test.tsx` | Added deploy card evidence assertions. |
| `apps/web/src/components/__fixtures__/sample-deployment.ts` | Added sample deploy evidence metadata. |
| `docs/project-state.md` | Recorded P11-4 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p11-real-staging-deploy-provider/tasks.md` | Marked P11-4 complete after targeted verification. |

### What Changed

P11-4 makes deployment evidence visible and durable. Deployment artifacts and
API responses now include target ID, provider type, source preview/diff/review
references, logs, and status history. The deploy card renders those details
inline so staging deploys can be reviewed like other AgentHub artifacts.

Local staging provider failures now persist failed deployment artifacts with
diagnostic logs instead of disappearing behind an exception. Unknown providers
still fail before artifact creation.

### Validation

| Command | Result |
|---|---|
| Targeted deployment tests | Pass: 13 tests. |
| Targeted deploy card/frontend tests | Pass: 37 tests. |

---

## P11-3 Local Staging Deploy Provider

**Date:** 2026-05-25

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/deployments.py` | Added `local_staging` provider, build runner, static directory server runner, target/worktree resolution, health checking, and provider-selected deploy creation. |
| `apps/api/app/main.py` | Allowed `POST /previews/{previewId}/deploy` to accept `providerId` while preserving mock as the default. |
| `apps/api/app/schemas.py` | Added deploy create request schema. |
| `apps/api/app/target_registry.py` | Aligned demo frontend build command with target-root execution. |
| `apps/api/tests/test_deployments.py` | Added local staging success, build failure, missing output, and API provider selection tests. |
| `apps/api/tests/test_target_registry.py` | Updated deploy config assertions for target-root build execution. |
| `docs/project-state.md` | Recorded P11-3 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p11-real-staging-deploy-provider/tasks.md` | Marked P11-3 complete after targeted verification. |

### What Changed

P11-3 adds a real local staging provider path. It reads deploy configuration
from Target Registry, runs the target build command, checks the configured
output directory, starts a local static server, performs a URL health check,
and records a staging deployment when the URL is ready.

The API remains compatible with existing mock deploy callers and now accepts
`providerId: local_staging` for staging deploy requests. Deterministic
TestClient smoke coverage verifies the local provider selection without
starting long-lived external services.

### Validation

| Command | Result |
|---|---|
| Targeted deployment / target registry tests | Pass: 24 tests. |

---

## P11-2 Target-aware Deploy Configuration

**Date:** 2026-05-25

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/target_registry.py` | Added deploy metadata to target projects and `resolve_deploy_config()` for deployable frontend targets. |
| `apps/api/app/models.py` | Added external target deploy metadata fields for staging output, staging serve command, and deploy provider IDs. |
| `apps/api/app/external_workspaces.py` | Accepted and persisted external target deploy provider metadata. |
| `apps/api/app/schemas.py` | Exposed deploy metadata in external target and target project request/response schemas. |
| `apps/api/app/main.py` | Returned deploy metadata through target registry and external target APIs. |
| `apps/api/tests/test_target_registry.py` | Added deploy config resolution and non-deployable target tests. |
| `apps/api/tests/test_external_workspaces.py` | Added external target deploy metadata API coverage. |
| `docs/project-state.md` | Recorded P11-2 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p11-real-staging-deploy-provider/tasks.md` | Marked P11-2 complete after targeted verification. |

### What Changed

P11-2 makes Target Registry the source of truth for deploy configuration.
Deployable frontend targets can now expose build command, staging output
directory, staging serve command, and allowed deploy provider IDs. The built-in
demo frontend advertises mock and local staging provider availability, while
backend/platform targets fail honestly through `resolve_deploy_config()`.

External frontend targets may carry deploy metadata through registration and
workspace target APIs. P11-2 does not execute deploy commands yet.

### Validation

| Command | Result |
|---|---|
| Targeted target registry / external workspace tests | Pass: 16 tests. |

---

## P11-1 Deploy Provider Abstraction

**Date:** 2026-05-25

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/deployments.py` | Added a deploy provider result contract, provider selection, mock provider compatibility path, and failed/unknown provider handling. |
| `apps/api/tests/test_deployments.py` | Added deploy provider abstraction tests for metadata, provider selection, unknown provider rejection, failed provider results, and mock compatibility. |
| `docs/project-state.md` | Recorded P11-1 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p11-real-staging-deploy-provider/tasks.md` | Marked P11-1 complete after targeted verification. |

### What Changed

P11-1 introduces the first deploy provider abstraction without changing the
current runtime deploy semantics. Existing mock deploy behavior remains
available through `create_mock_deployment()`, while the newer
`create_deployment()` path selects a provider by ID and records standardized
provider metadata in the deployment artifact.

Unknown providers are rejected before artifact creation. Failed provider
results are reported honestly and do not create ready deployment artifacts.

### Validation

| Command | Result |
|---|---|
| Targeted deployment tests | Pass: 9 tests. |

---

## P10-8 Robustness Rehearsal And Freeze Review

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `docs/p10-freeze-review.md` | Added P10 freeze evidence, validation notes, caveats, and recommended tag. |
| `docs/project-state.md` | Recorded P10-8 freeze result and recommended tag. |
| `docs/change-log.md` | Recorded this freeze review. |
| `openspec/changes/agenthub-p10-scheduler-robustness-conflict-recovery/tasks.md` | Marked P10-8 complete after validation. |

### Review Result

P10 is ready to freeze as Scheduler Robustness and Conflict Recovery.

The freeze review used deterministic local tests and existing P6/P7/P8/P9
baseline coverage. It did not run a fresh real Claude/Codex mutation.

### Validation

| Command | Result |
|---|---|
| Targeted P10 rehearsal tests | Pass |
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `git diff --check` | Pass |
| `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict` | Pass |

Recommended freeze tag:
`p10-scheduler-robustness-conflict-recovery-freeze`.

---

## P10-7 Recovery Actions

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/recovery.py` | Added auditable recovery actions for stale task failure, stale lock release, retry, and downstream stop/resume. |
| `apps/api/app/task_runs.py` | Allowed recovery to request checkpoint retry mode while preserving retry safety checks. |
| `apps/api/tests/test_recovery.py` | Added recovery action audit and behavior tests. |
| `docs/project-state.md` | Recorded P10-7 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p10-scheduler-robustness-conflict-recovery/tasks.md` | Marked P10-7 complete after validation. |

### What Changed

P10-7 adds explicit service-level recovery actions. Stale task failure, stale
lock release, retry from current state, retry from checkpoint, downstream stop,
and downstream resume now produce `recovery.action` audit events. Recovery
actions reuse P10 heartbeat, stale lock, checkpoint, retry, and scheduler
readiness safeguards rather than adding automatic merge/reset behavior.

### Validation

| Command | Result |
|---|---|
| Targeted recovery action tests | Pass: 4 tests. |
| Targeted recovery/scheduler/task-run regression tests | Pass: 61 tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `git diff --check` | Pass |
| `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict` | Pass |

---

## P10-6 Conflict Detection

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/scheduler.py` | Added scheduler-level file overlap, dirty worktree, and contract drift conflict detection. |
| `apps/api/app/task_runs.py` | Uses full scheduler readiness before TaskRun creation so conflicts block execution. |
| `apps/api/tests/test_scheduler.py` | Added file overlap, dirty worktree, and contract drift conflict tests. |
| `apps/api/tests/test_task_runs.py` | Adjusted checkpoint fixture to avoid intentionally dirty denied files now covered by conflict tests. |
| `docs/project-state.md` | Recorded P10-6 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p10-scheduler-robustness-conflict-recovery/tasks.md` | Marked P10-6 complete after validation. |

### What Changed

Scheduler readiness now blocks common conflicts before write execution:
unsequenced overlapping planned files, dirty worktree files outside planned
safe files, and stale/mismatched contract context. Conflicts are recorded in
task scheduler metadata and are not auto-merged.

### Validation

| Command | Result |
|---|---|
| Targeted conflict detection tests | Pass: 3 tests. |
| Targeted scheduler/task-run regression tests | Pass: 57 tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `git diff --check` | Pass |
| `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict` | Pass |

---

## P10-5 Failure Propagation Hardening

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/previews.py` | Gated preview creation on completed TaskRun and completed dependencies. |
| `apps/api/app/deployments.py` | Gated mock deploy on completed TaskRun and completed dependencies behind the preview. |
| `apps/api/tests/test_previews.py` | Added failed TaskRun and failed dependency preview rejection tests. |
| `apps/api/tests/test_deployments.py` | Added failed TaskRun and failed dependency mock deploy rejection tests. |
| `docs/project-state.md` | Recorded P10-5 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p10-scheduler-robustness-conflict-recovery/tasks.md` | Marked P10-5 complete after validation. |

### What Changed

Preview and mock deploy no longer proceed after failed or incomplete
prerequisites. Manual preview now requires a completed TaskRun and completed
dependencies. Mock deploy keeps its healthy-preview requirement and also
requires the backing TaskRun and dependencies to be complete.

### Validation

| Command | Result |
|---|---|
| Targeted preview/deploy prerequisite rejection tests | Pass: 4 tests. |
| Targeted scheduler/preview/deploy/fallback recovery tests | Pass: 29 tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `git diff --check` | Pass |
| `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict` | Pass |

---

## P10-4 Retry Idempotency

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/task_runs.py` | Added retry metadata, dirty worktree retry safety checks, and unsafe retry blocking. |
| `apps/api/tests/test_task_runs.py` | Added retry idempotency metadata and unsafe external dirty-worktree retry tests. |
| `docs/project-state.md` | Recorded P10-4 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p10-scheduler-robustness-conflict-recovery/tasks.md` | Marked P10-4 complete after validation. |

### What Changed

Retries now record `previousRunId`, failure summary, retry mode, checkpoint
reference, and dirty worktree decision. Automatic retry is blocked when current
dirty files fall outside the prior checkpoint or planned safe paths, preventing
blind retries into external project local edits.

### Validation

| Command | Result |
|---|---|
| Targeted retry idempotency tests | Pass: 2 tests. |
| Targeted task-run retry/checkpoint/liveness tests | Pass: 10 tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `git diff --check` | Pass |
| `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict` | Pass |

---

## P10-3 Pre-run Snapshot / Checkpoint

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/task_runs.py` | Added pre-run checkpoint creation for write TaskRuns and checkpoint audit events. |
| `apps/api/tests/test_task_runs.py` | Added demo and external target checkpoint coverage. |
| `docs/project-state.md` | Recorded P10-3 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p10-scheduler-robustness-conflict-recovery/tasks.md` | Marked P10-3 complete after validation. |

### What Changed

Write TaskRuns now store `metrics_json.preRunCheckpoint` and emit
`task.checkpoint.created` before execution. Checkpoints include target metadata,
Target Registry path policy, base commit when available, scoped dirty files,
planned files, contract ID/hash, and creation time. External targets use their
registered root and path policy.

### Validation

| Command | Result |
|---|---|
| Targeted checkpoint tests | Pass: 2 tests. |
| Targeted task-run/scheduler liveness and lock tests | Pass: 16 tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `git diff --check` | Pass |
| `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict` | Pass |

---

## P10-2 Stale Target Lock Cleanup

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/scheduler.py` | Added stale target lock cleanup for stale write-lock owner TaskRuns with audit events and scheduler refresh. |
| `apps/api/tests/test_scheduler.py` | Added coverage that active owners are not released and stale owners release derived target locks. |
| `docs/project-state.md` | Recorded P10-2 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p10-scheduler-robustness-conflict-recovery/tasks.md` | Marked P10-2 complete after validation. |

### What Changed

P10-2 keeps the existing P8 derived target-lock model, but adds an explicit
cleanup path:

- active TaskRuns with valid leases remain lock holders;
- expired write-lock owner TaskRuns can be marked stale and failed;
- cleanup writes `target_lock.released` events with target, owner, lock mode,
  lease, release timestamp, and reason;
- waiting tasks are re-evaluated after stale owner cleanup.

### Validation

| Command | Result |
|---|---|
| Targeted stale lock cleanup tests | Pass: 2 tests. |
| Targeted scheduler/task-run lock and liveness tests | Pass: 14 tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `git diff --check` | Pass |
| `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict` | Pass |

---

## P10-1 TaskRun Heartbeat And Lease

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/models.py` | Added TaskRun liveness fields for runner identity, heartbeat, lease expiry, and stale metadata. |
| `apps/api/app/db.py` | Added SQLite backfill for TaskRun heartbeat/lease/stale columns. |
| `apps/api/app/task_runs.py` | Added runner lease initialization, heartbeat refresh, stale run detection, and honest stale failure marking. |
| `apps/api/app/schemas.py` | Exposed TaskRun liveness metadata in API response schema. |
| `apps/api/app/main.py` | Included liveness metadata in TaskRun API responses. |
| `apps/api/tests/test_task_runs.py` | Added heartbeat, lease, and stale detection tests. |
| `apps/api/tests/test_models.py` | Updated model boundary and response alias tests for liveness fields. |
| `docs/project-state.md` | Recorded P10-1 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p10-scheduler-robustness-conflict-recovery/tasks.md` | Marked P10-1 complete after validation. |

### What Changed

TaskRuns now have local runner liveness metadata:

- new runs get `runner_id`, `last_heartbeat_at`, and `lease_expires_at`;
- active runs can refresh heartbeat and lease metadata;
- expired active leases can be marked failed with `TASK_RUN_STALE`;
- stale transitions write audit events and do not claim adapter success.

### Validation

| Command | Result |
|---|---|
| Targeted heartbeat/stale tests | Pass: 4 tests. |
| Targeted model/task-run tests | Pass: 6 tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `git diff --check` | Pass |
| `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict` | Pass |

---

## P9-8 External Project E2E Rehearsal And Freeze Review

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `docs/p9-freeze-review.md` | Added P9 freeze evidence, rehearsal IDs, validation notes, caveats, and recommended tag. |
| `docs/project-state.md` | Recorded P9-8 freeze result and recommended tag. |
| `docs/change-log.md` | Recorded this freeze review. |
| `openspec/changes/agenthub-p9-external-project-workspace-mode/tasks.md` | Marked P9-8 complete after validation. |

### Review Result

P9 is ready to freeze as External Project Workspace Mode.

P9 did not run a fresh real Claude/Codex mutation. It used a temporary local
Vite-style external project and controlled service calls to verify analysis,
registration, target selection, external task/run routing, diff, command
evidence, and review policy.

### P9 Rehearsal Evidence

| Field | Value |
|---|---|
| Sample root | `/tmp/agenthub-p9-external-sample` |
| Session ID | `09977dc0-1eac-49f6-ae78-cb7ae7aa9ccc` |
| Target ID | `external-p9-sample` |
| Analysis status / type | `ready`, `vite-react` |
| Task / run | `ce8fe3de-6969-4273-84e9-274ab440f39b`, `1d6d2916-b179-4bb7-ad7a-642733dfd175` |
| Adapter type | `scripted_mock` controlled rehearsal |
| Changed files | `src/App.tsx` |
| Diff artifact | `7bf6efa3-289b-4cb8-9644-6ca6e283b230` |
| Command evidence | `c6d581bf-e80a-4fb9-bb21-f0db1cb9ff4d`, `b01ccc78-b3d4-44fc-b758-4c9558d2f594`, `9a256f14-fe1f-4e4b-9dc7-78c4402edd01` |
| Review artifact / status | `383e7822-0145-4950-9bd1-b3dffb170b36`, `passed` |

### Validation

| Command | Result |
|---|---|
| P9 temporary external rehearsal | Pass |
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `pnpm demo:api:test` | Pass |
| `git diff --check` | Pass |
| `openspec validate agenthub-p9-external-project-workspace-mode --strict` | Pass |

Recommended freeze tag:
`p9-external-project-workspace-mode-freeze`.

---

## P9-7 External Project Review

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/reviews.py` | Added external target allowed/denied path review and command evidence findings. |
| `apps/api/tests/test_external_reviews.py` | Added denied-path, outside-allowed-path, failed-evidence, missing-evidence, and clean-pass review tests. |
| `docs/project-state.md` | Recorded P9-7 behavior and limitation. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p9-external-project-workspace-mode/tasks.md` | Marked P9-7 complete after validation. |

### What Changed

P9-7 makes external reviews policy-aware:

- denied path edits fail or warn explicitly;
- outside-allowed-path edits produce findings;
- missing or failed configured check/test/build evidence is reported honestly;
- clean external target diffs with passing evidence can pass review.

### Validation

| Command | Result |
|---|---|
| Targeted external review/evidence/diff tests | Pass: 13 tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `git diff --check` | Pass |
| `openspec validate agenthub-p9-external-project-workspace-mode --strict` | Pass |

---

## P9-6 External Evidence Pipeline

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/diffs.py` | Scoped external diff collection to target allowed paths while excluding denied/dependency paths. |
| `apps/api/app/external_evidence.py` | Added command evidence artifact recording for check/test/build output. |
| `apps/api/app/schemas.py` | Added command evidence request/response schemas. |
| `apps/api/app/main.py` | Added create/list API endpoints for command evidence artifacts. |
| `apps/api/app/context_pack.py` | Added latest command evidence metadata to session context packs. |
| `apps/api/tests/test_diffs.py` | Added external diff path policy coverage. |
| `apps/api/tests/test_external_evidence.py` | Added command evidence service/API tests for passed and failed outputs. |
| `docs/project-state.md` | Recorded P9-6 behavior and limitation. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p9-external-project-workspace-mode/tasks.md` | Marked P9-6 complete after validation. |

### What Changed

P9-6 adds capability-based external evidence:

- external diffs respect target path policy;
- check/test/build command outputs can be stored as `command_evidence`
  artifacts;
- failed command exits remain failed evidence;
- preview remains optional for external targets.

### Validation

| Command | Result |
|---|---|
| Targeted external evidence/diff tests | Pass: 41 tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `git diff --check` | Pass |
| `openspec validate agenthub-p9-external-project-workspace-mode --strict` | Pass |

---

## P9-5 External Project Task Execution

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/models.py` | Added session active frontend/backend target IDs. |
| `apps/api/app/db.py` | Added SQLite column backfill for existing local session tables. |
| `apps/api/app/schemas.py` | Added active target fields and session target selection request schema. |
| `apps/api/app/main.py` | Added session target selection API and external frontend auto-start safety check. |
| `apps/api/app/planning.py` | Routed direct mentions and bounded Orchestrator frontend requests to selected external targets. |
| `apps/api/app/task_runs.py` | Uses external target root as TaskRun worktree path for external target tasks. |
| `apps/api/tests/test_external_workspaces.py` | Added session target selection tests. |
| `apps/api/tests/test_planning.py` | Added external direct frontend and Orchestrator auto-start routing tests. |
| `apps/api/tests/test_task_runs.py` | Added external TaskRun worktree-path assertion. |
| `apps/api/tests/test_models.py` | Updated model boundary expectations for active target fields. |
| `docs/project-state.md` | Recorded P9-5 behavior and limitation. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p9-external-project-workspace-mode/tasks.md` | Marked P9-5 complete after validation. |

### What Changed

P9-5 gives registered external targets an executable task path:

- sessions can select active external frontend/backend targets;
- direct assignment tasks target active external projects when selected;
- bounded no-mention UI requests can be routed by Orchestrator to active
  external frontend targets and auto-started through TaskRun;
- TaskRun execution requests use the external target root as worktree path;
- unsupported broad requests remain rejected instead of silently executing.

### Validation

| Command | Result |
|---|---|
| Targeted external execution/routing tests | Pass: 64 tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `git diff --check` | Pass |
| `openspec validate agenthub-p9-external-project-workspace-mode --strict` | Pass |

---

## P9-4 External Target Instruction Builder

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/instruction_builder.py` | Added external frontend/backend/review instruction bodies using registered target metadata and configured command evidence. |
| `apps/api/tests/test_task_runs.py` | Added external frontend, backend, and review instruction coverage. |
| `docs/project-state.md` | Recorded P9-4 behavior and limitation. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p9-external-project-workspace-mode/tasks.md` | Marked P9-4 complete after validation. |

### What Changed

P9-4 makes role instructions target-aware for registered external projects:

- frontend/backend instructions no longer reduce external targets to demo app
  paths;
- target root, allowed paths, denied paths, project type, package manager,
  detected framework, and configured validation commands are included;
- review instructions stay read-oriented and call out command evidence honesty;
- built-in demo instructions are preserved.

### Validation

| Command | Result |
|---|---|
| Targeted task-run/instruction tests | Pass: 44 tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `git diff --check` | Pass |
| `openspec validate agenthub-p9-external-project-workspace-mode --strict` | Pass |

---

## P9-3 External Target Registry Integration

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/target_registry.py` | Added workspace-aware merged registry reads and external-target-to-`TargetProject` mapping. |
| `apps/api/app/main.py` | Added merged workspace target list API. |
| `apps/api/app/schemas.py` | Added target project response schema. |
| `apps/api/app/context_pack.py` | Resolves external `targetId` metadata into session context packs. |
| `apps/api/app/instruction_builder.py` | Allows instruction generation to use target metadata from context packs. |
| `apps/api/app/scheduler.py` | Makes target write locks validate registered external targets. |
| `apps/api/tests/test_target_registry.py` | Added merged registry and external backend/frontend mapping tests. |
| `apps/api/tests/test_external_workspaces.py` | Added merged targets API coverage. |
| `apps/api/tests/test_scheduler.py` | Added external target write-lock coverage. |
| `apps/api/tests/test_task_runs.py` | Added context-pack-to-instruction external target coverage. |
| `docs/project-state.md` | Recorded P9-3 behavior and limitation. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p9-external-project-workspace-mode/tasks.md` | Marked P9-3 complete after validation. |

### What Changed

P9-3 integrates registered external targets into AgentHub's existing target
metadata path:

- merged registry reads include built-in and external targets;
- external targets carry path policy and command metadata in the same shape as
  built-in targets;
- context packs and role instructions can reference external target metadata;
- scheduler target locks apply to registered external target IDs.

### Validation

| Command | Result |
|---|---|
| Targeted registry/scheduler/task-run tests | Pass: 56 tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `git diff --check` | Pass |
| `openspec validate agenthub-p9-external-project-workspace-mode --strict` | Pass |

---

## P9-2 Project Analyzer

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/project_analyzer.py` | Added read-only analyzer for common JS/Python project shapes, safe path inference, command inference, denied-path defaults, and uncertainty status. |
| `apps/api/app/schemas.py` | Added external project analysis request/response schemas. |
| `apps/api/app/main.py` | Added workspace-scoped external target analysis API. |
| `apps/api/tests/test_project_analyzer.py` | Added Vite React, Next.js, FastAPI, Node API, Python package, unknown-project, and API response tests. |
| `docs/project-state.md` | Recorded P9-2 behavior and limitation. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p9-external-project-workspace-mode/tasks.md` | Marked P9-2 complete after validation. |

### What Changed

P9-2 adds project analysis without granting execution permissions:

- analyzes `package.json`, lockfiles, Vite/Next config, Python project files,
  FastAPI entry points, and source/test directories;
- infers project type, package manager, detected framework, allowed paths,
  denied paths, and command candidates;
- returns `needs_confirmation` with warnings for unknown or incomplete
  projects;
- never installs dependencies or runs arbitrary commands.

### Validation

| Command | Result |
|---|---|
| Targeted analyzer tests | Pass: 11 tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `git diff --check` | Pass |
| `openspec validate agenthub-p9-external-project-workspace-mode --strict` | Pass |

---

## P9-1 External Workspace Registration

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/models.py` | Added persisted `ExternalProjectTarget` model for external workspace target registration. |
| `apps/api/app/external_workspaces.py` | Added registration service, root/path validation, denied-path defaults, and list/read helpers. |
| `apps/api/app/schemas.py` | Added external target create and response schemas. |
| `apps/api/app/main.py` | Added workspace-scoped create/list/read APIs for external targets. |
| `apps/api/tests/test_external_workspaces.py` | Added registration, unsafe-root, bounded-path, and built-in registry regression tests. |
| `apps/api/tests/test_models.py` | Updated model boundary expectations for the new external target table. |
| `docs/project-state.md` | Recorded P9-1 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p9-external-project-workspace-mode/tasks.md` | Marked P9-1 complete after validation. |

### What Changed

P9-1 adds the external workspace registration layer without changing execution
semantics:

- local external project roots can be registered as workspace-scoped external
  targets;
- registration stores target metadata, commands, package manager, detected
  framework, allowed paths, and denied paths;
- unsafe broad roots and unbounded allowed paths are rejected;
- built-in P7/P8 target registry entries remain unchanged.

### Validation

| Command | Result |
|---|---|
| Targeted external workspace tests | Pass: 18 tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `git diff --check` | Pass |
| `openspec validate agenthub-p9-external-project-workspace-mode --strict` | Pass |

---

## P8-6 P8 E2E Rehearsal And Freeze Review

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `docs/p8-freeze-review.md` | Added P8 freeze evidence, scheduler rehearsal IDs, validation notes, caveats, and recommended tag. |
| `docs/project-state.md` | Recorded P8-6 freeze result and recommended tag. |
| `docs/change-log.md` | Recorded this freeze review. |
| `openspec/changes/agenthub-p8-dependency-scheduler-target-locks/tasks.md` | Marked P8-6 complete after validation. |

### Review Result

P8 is ready to freeze as Dependency-aware Scheduler and Target Locks.

P8 did not run a fresh real Claude/Codex mutation. It used a temporary git
worktree and controlled local fake adapter to verify scheduler order, target
locks, failed dependency blocking, review artifact creation, healthy preview
plumbing, and mock deploy plumbing. P6 remains the latest real
`ClaudeCodeAdapter` mini CRM execution evidence.

### P8 Rehearsal Evidence

| Field | Value |
|---|---|
| Session ID | `3fad4108-f0ea-4134-8b31-fb2ab911fadd` |
| Contract ID | `contract-mini_crm_contacts` |
| Backend task / run | `e7f85f87-fa8a-4203-a33f-682e568a6d50`, `72cf0f92-1c65-460e-b697-4e37cbcefed0` |
| Frontend task / run | `e37a46b0-834b-4396-b703-8ecdfd1bf27b`, `bb28106d-d1f8-4431-8245-d40db304edfa` |
| Review task | `336a0c82-6caf-4d84-b421-4ccfcdd17ad7` |
| Diff artifacts | `104f1a7b-fa6f-4842-9152-a8e2acc0bbce`, `e92f2e27-c463-4a41-8dad-c7fce2eb87ce` |
| Preview / health | `56d01fc3-affb-4f6a-bf46-973469a81e1d`, `healthy` |
| Mock deploy / provider | `d94dade3-8b3e-4ea0-a0a9-61b2b085ce9e`, `mock` |
| Target lock evidence | waiting task `7e507b15-3cd6-4be3-89d1-893e3777045a`, holder run `3c241653-2a4e-4782-b58c-729cdc98d1bf` |
| Failed dependency evidence | failed task `39d5151f-888a-4790-bd66-9044f6328053`, blocked task `84e11005-0148-4926-993c-6c002555507b` |
| Platform protection | task `4ed028eb-998c-4ca4-8aa0-e0c2dd9dd2f8`, run `ca3f70d9-d4aa-49ed-9e47-c757c432bde5`, state `waiting_approval` |

### Validation

| Command | Result |
|---|---|
| P8 temporary API rehearsal | Pass |
| `pnpm check` | Pass |
| `pnpm test` | Pass: 37 web tests, 155 API tests, 5 demo-api tests. |
| `pnpm demo:api:test` | Pass: 5 tests. |
| `git diff --check` | Pass |
| `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict` | Pass |

Recommended freeze tag:
`p8-dependency-scheduler-target-locks-freeze`.

---

## P8-5 Scheduler UI Trace

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `apps/web/src/components/task-card-list.tsx` | Added scheduler status labels, task-card scheduler summary, and execution-trace flags for waits/blocks. |
| `apps/web/src/components/task-card-list.test.tsx` | Added coverage for scheduler target-lock, retry, and fallback metadata rendering. |
| `docs/project-state.md` | Recorded P8-5 UI trace behavior and limitation. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p8-dependency-scheduler-target-locks/tasks.md` | Marked P8-5 complete after validation. |

### What Changed

P8-5 makes scheduler decisions visible in the existing UI:

- task cards show scheduler state, reason, target ID, blocking dependencies,
  target lock holder run IDs, write-lock state, retryable state, and fallback
  availability;
- the execution trace flags dependency waits, target lock waits, and blocked
  states;
- existing artifact and run controls remain in place.

### Validation

| Command | Result |
|---|---|
| Targeted task-card-list tests | Pass: 37 web tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass: 37 web tests, 155 API tests, 5 demo-api tests. |
| `git diff --check` | Pass |
| `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict` | Pass |

---

## P8-4 Failure Recovery And Blocked States

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/scheduler.py` | Added terminal TaskRun scheduler metadata for completed, retryable, and fallback-available states. |
| `apps/api/app/task_runs.py` | Records terminal scheduler state before refreshing downstream dependency and lock state. |
| `apps/api/tests/test_scheduler.py` | Added coverage for fallback availability, retryable state, and fallback completion unblocking downstream tasks. |
| `docs/project-state.md` | Recorded P8-4 failure recovery behavior and limitation. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p8-dependency-scheduler-target-locks/tasks.md` | Marked P8-4 complete after validation. |

### What Changed

P8-4 makes scheduler failure recovery states explicit:

- completed TaskRuns write `planJson.scheduler.state: completed`;
- failed/interrupted Codex coding runs expose `fallback_available`;
- failed/interrupted non-Codex runs expose `retryable`;
- downstream tasks remain blocked after upstream failure;
- completed retry/fallback runs re-evaluate downstream tasks and can unblock
  them when dependency and target-lock rules are satisfied.

### Validation

| Command | Result |
|---|---|
| Targeted scheduler failure tests | Pass: 13 tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass: 36 web tests, 155 API tests, 5 demo-api tests. |
| `git diff --check` | Pass |
| `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict` | Pass |

---

## P8-3 Auto-run Pipeline

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planning.py` | Marks contract-first backend/frontend tasks as auto-startable. |
| `apps/api/app/main.py` | Extends safe auto-start to demo backend tasks and adds contract-first pipeline progression after coding TaskRun completion. |
| `apps/api/tests/test_planning.py` | Updated mini CRM planning expectations to cover backend auto-start through TaskRun. |
| `docs/project-state.md` | Recorded P8-3 pipeline behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p8-dependency-scheduler-target-locks/tasks.md` | Marked P8-3 complete after validation. |

### What Changed

P8-3 wires the bounded contract-first pipeline into existing execution paths:

- backend and frontend contract-first tasks can auto-start when dependencies
  and locks allow;
- backend completion can trigger the frontend coding task;
- coding completion still uses existing diff collection, scripted review, and
  ledger refresh;
- ready contract review / QA tasks are completed from generated review
  artifacts instead of running a mutating QA adapter;
- frontend completion attempts existing Vite preview and creates mock deploy
  only from a healthy preview.

### Validation

| Command | Result |
|---|---|
| Targeted mini CRM planning / scheduler tests | Pass: 11 tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass: 36 web tests, 152 API tests, 5 demo-api tests. |
| `git diff --check` | Pass |
| `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict` | Pass |

---

## P8-2 Target Write Locks

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/scheduler.py` | Added target ID resolution, write-lock detection, lock-holder metadata, platform target blocking, and combined scheduler readiness. |
| `apps/api/app/main.py` | Uses combined scheduler readiness before safe task auto-start. |
| `apps/api/app/task_runs.py` | Enforces target write locks before manual TaskRun creation and refreshes session scheduler state after terminal runs. |
| `apps/api/tests/test_scheduler.py` | Added frontend/backend lock, lock release, read-only review, and platform lock protection tests. |
| `docs/project-state.md` | Recorded P8-2 target lock behavior and limitation. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p8-dependency-scheduler-target-locks/tasks.md` | Marked P8-2 complete after validation. |

### What Changed

P8-2 adds target write locks on top of the P8-1 dependency scheduler:

- active same-session write TaskRuns hold a target lock for their resolved
  `targetId`;
- another runnable write task for the same target becomes
  `waiting_target_lock` instead of starting;
- waiting lock metadata identifies the target and active holder TaskRun IDs;
- terminal TaskRuns release locks by re-evaluating session scheduler state;
- read-only Review / QA tasks do not acquire target write locks by default;
- ordinary app backend tasks cannot acquire an `agenthub-platform` write lock
  without explicit platform mode and approval.

### Validation

| Command | Result |
|---|---|
| Targeted scheduler lock tests | Pass: 10 tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass: 36 web tests, 152 API tests, 5 demo-api tests. |
| `git diff --check` | Pass |
| `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict` | Pass |

---

## P8-1 Dependency-aware Task Scheduler

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/scheduler.py` | Added dependency readiness decisions, scheduler metadata persistence, session refresh, and downstream refresh helpers. |
| `apps/api/app/main.py` | Evaluates scheduler dependency readiness after planning and before auto-starting safe tasks. |
| `apps/api/app/task_runs.py` | Refreshes downstream scheduler state when an upstream TaskRun reaches a terminal state. |
| `apps/api/tests/test_scheduler.py` | Added dependency readiness, auto-start blocking, ready auto-start, and downstream blocking coverage. |
| `apps/api/tests/test_planning.py` | Updated planning API expectations to expose `waiting_dependency` state and scheduler metadata for dependent tasks. |
| `docs/project-state.md` | Recorded P8-1 baseline behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p8-dependency-scheduler-target-locks/tasks.md` | Marked P8-1 complete after validation. |

### What Changed

P8-1 makes declared task dependencies operational for the scheduler path:

- incomplete dependencies prevent automatic TaskRun creation;
- completed dependencies allow an auto-start-eligible task to queue;
- synthetic Manager planning tasks are marked `completed` when the task graph
  is created, preserving the existing no-mention frontend auto-run path;
- failed, interrupted, or blocked dependencies mark downstream tasks
  `blocked`;
- dependency state is visible through `planJson.scheduler`;
- manual TaskRun creation remains unchanged outside scheduled auto-start.

### Validation

| Command | Result |
|---|---|
| Targeted scheduler/planning tests | Pass: 7 tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass: 36 web tests, 147 API tests, 5 demo-api tests. |
| `git diff --check` | Pass |
| `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict` | Pass |

---

## P7-6 E2E Rehearsal And Freeze Review

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `docs/p7-freeze-review.md` | Added P7 freeze evidence, reused P6 real execution evidence, API rehearsal IDs, validation notes, and caveats. |
| `docs/project-state.md` | Recorded P7-6 freeze result and recommended tag. |
| `docs/change-log.md` | Recorded this freeze review. |
| `openspec/changes/agenthub-p7-target-registry-permissioned-execution/tasks.md` | Marked P7-6 complete after validation. |

### Review Result

P7 is ready to freeze as Target Project Registry + Permissioned Execution.

P7 did not run a fresh real Claude/Codex mutation. It reused the P6 final
`ClaudeCodeAdapter` mini CRM evidence for diff, review, preview, and mock
deploy, then verified P7-specific behavior through API rehearsal and regression
validation.

### P7 API Rehearsal Evidence

| Field | Value |
|---|---|
| Mini CRM session ID | `d0500f2c-a480-4903-aea5-5d2d72b2bf31` |
| Contract ID | `contract-mini_crm_contacts` |
| Frontend / backend target IDs | `demo-frontend`, `demo-backend` |
| Demo API base URL | `http://127.0.0.1:5174` |
| Mini CRM task IDs | `952bcfd1-12b9-41ca-b81d-694a66b4dcea`, `d382a368-0cd2-4d46-86c6-790b691d4b58`, `5966d060-0df4-463d-94e1-d7bebdddf729`, `634bb541-3b0e-47ad-a408-13392b6dea11` |
| Platform session ID | `57d92dde-710f-484e-b86a-f7c0e06e22e6` |
| Platform task / run | `fc86452a-a92b-4894-844d-372b5df799e1`, `7ef6efcb-979c-4984-a1a2-2f29f893bc79` |
| Platform target / state | `agenthub-platform`, `waiting_approval` |
| Platform approval | `security_approval`, `high` |

### Validation

| Command | Result |
|---|---|
| P7 API rehearsal script | Pass |
| `pnpm check` | Pass |
| `pnpm test` | Pass: 36 web tests, 142 API tests, 5 demo-api tests. |
| `pnpm demo:api:test` | Pass: 5 tests. |
| `git diff --check` | Pass |
| `openspec validate agenthub-p7-target-registry-permissioned-execution --strict` | Pass |

Recommended freeze tag:
`p7-target-registry-permissioned-execution-freeze`.

---

## P7-5 Platform Maintenance Mode

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planning.py` | Added explicit platform maintenance routing while preserving ordinary `@backend` routing to `demo-backend`. |
| `apps/api/app/task_runs.py` | Added approval-gated TaskRun creation for `agenthub-platform` tasks. |
| `apps/api/tests/test_planning.py` | Added coverage for ordinary backend routing and explicit platform mode task creation. |
| `apps/api/tests/test_task_runs.py` | Added coverage for platform maintenance TaskRun approval requests. |
| `docs/project-state.md` | Recorded P7-5 platform mode behavior. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p7-target-registry-permissioned-execution/tasks.md` | Marked P7-5 complete after validation. |

### What Changed

P7-5 introduces explicit AgentHub platform maintenance mode:

- ordinary `@backend` requests target `demo-backend` / `apps/demo-api`;
- explicit `platform mode` or platform-maintenance phrasing creates
  `agenthub-platform` tasks;
- platform tasks require `platformMode: true` and `requiresApproval: true`;
- platform TaskRuns start in `waiting_approval` and emit a
  `security_approval` request instead of queueing execution immediately.

### Validation

| Command | Result |
|---|---|
| Targeted routing/approval tests | Pass: 3 tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass: 36 web tests, 142 API tests, 5 demo-api tests. |
| `git diff --check` | Pass |
| `openspec validate agenthub-p7-target-registry-permissioned-execution --strict` | Pass |

---

## P7-4 Target-aware Review / QA

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/reviews.py` | Added target-registry review checks for allowed paths, denied paths, API-base consistency, and contract/task target consistency. |
| `apps/api/tests/test_task_runs.py` | Added review coverage for platform-code mutation failures and task target mismatch failures. |
| `docs/project-state.md` | Recorded P7-4 review behavior. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p7-target-registry-permissioned-execution/tasks.md` | Marked P7-4 complete after validation. |

### What Changed

P7-4 makes the deterministic review artifact target-aware:

- full-stack diffs that stay inside `demo-frontend` and `demo-backend`
  allowed paths pass;
- frontend local API base URLs must match the registry-resolved
  `demo-backend` base URL;
- ordinary app diffs that modify `apps/api` fail review with high risk;
- task target IDs are checked against contract target IDs.

Review remains advisory and non-blocking for preview/mock deploy in this phase.

### Validation

| Command | Result |
|---|---|
| Targeted review tests in `tests/test_task_runs.py` | Pass: 4 tests. |
| `bash scripts/check-api.sh` | Pass |
| `pnpm check` | Pass |
| `pnpm test` | Pass: 36 web tests, 141 API tests, 5 demo-api tests. |
| `git diff --check` | Pass |
| `openspec validate agenthub-p7-target-registry-permissioned-execution --strict` | Pass |

---

## P7-3 Target-aware Contract Planner

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planning.py` | Updated contract-first planning to derive frontend/backend target IDs, safe paths, raw target compatibility fields, and demo backend base URL from the registry. |
| `apps/api/tests/test_planning.py` | Added coverage for target IDs, registry-derived contract metadata, and target IDs in generated task graphs. |
| `docs/project-state.md` | Recorded P7-3 planner behavior. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p7-target-registry-permissioned-execution/tasks.md` | Marked P7-3 complete after validation. |

### What Changed

P7-3 keeps the existing P6 mini CRM path compatible while making contract-first
plans target-aware:

- app contracts now include `frontendTargetId: demo-frontend` and
  `backendTargetId: demo-backend`;
- `backendTarget`, `frontendTarget`, `backendAllowedPaths`,
  `frontendAllowedPaths`, `backendBaseUrl`, and `demoApiBaseUrl` are derived
  from registry metadata;
- backend, frontend, and review task plans include target IDs;
- task graph metadata includes target IDs for target-bound execution steps.

### Validation

| Command | Result |
|---|---|
| `pytest tests/test_planning.py -q` | Pass: 18 tests. |
| `bash scripts/check-api.sh` | Pass |
| `pnpm check` | Pass |
| `pnpm test` | Pass: 36 web tests, 139 API tests, 5 demo-api tests. |
| `git diff --check` | Pass |
| `openspec validate agenthub-p7-target-registry-permissioned-execution --strict` | Pass |

---

## P7-2 Target-aware Instruction Builder

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/instruction_builder.py` | Resolved role instructions through target registry metadata, including target IDs, allowed paths, commands, related backend base URL, and platform-mode requirements. |
| `apps/api/app/context_pack.py` | Added resolved target metadata and related target metadata to session context packs when target IDs are present. |
| `apps/api/app/main.py` | Removed the unused legacy `instruction_for_task` helper so instruction generation has one backend boundary. |
| `apps/api/tests/test_task_runs.py` | Added instruction/request coverage for target-aware backend, frontend, contract, context pack, and platform-maintenance behavior. |
| `docs/project-state.md` | Recorded P7-2 behavior and remaining migration caveats. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p7-target-registry-permissioned-execution/tasks.md` | Marked P7-2 complete after validation. |

### What Changed

P7-2 keeps P6 instruction behavior compatible while allowing P7 target-aware
plans to drive instruction construction:

- frontend instructions reference `demo-frontend`, `apps/demo/src`, and the
  registry-resolved `demo-backend` base URL;
- backend instructions reference `demo-backend`, `apps/demo-api`, and
  `pnpm demo:api:test`;
- explicit `agenthub-platform` tasks produce platform-maintenance instructions
  that require platform mode and approval;
- context packs expose `targetProject` and `relatedTargetProjects` metadata for
  adapter request construction.

P7-3 still needs to update planner output so target IDs are emitted by default.

### Validation

| Command | Result |
|---|---|
| `pytest tests/test_task_runs.py -q` | Pass: 26 tests. |
| `bash scripts/check-api.sh` | Pass |
| `pnpm check` | Pass |
| `pnpm test` | Pass: 36 web tests, 139 API tests, 5 demo-api tests. |
| `git diff --check` | Pass |
| `openspec validate agenthub-p7-target-registry-permissioned-execution --strict` | Pass |

---

## P7-1 Target Project Registry

**Date:** 2026-05-24

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/target_registry.py` | Added a static Target Project Registry with demo frontend, demo backend, and AgentHub platform target records. |
| `apps/api/tests/test_target_registry.py` | Added registry coverage for target metadata, related backend lookup, denied paths, and platform approval requirements. |
| `docs/project-state.md` | Recorded P7-1 target registry baseline and remaining migration caveat. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p7-target-registry-permissioned-execution/tasks.md` | Marked P7-1 complete after focused registry validation. |

### What Changed

P7-1 creates a single backend registry boundary for target metadata:

- `demo-frontend` maps to `apps/demo`, allows frontend app work under
  `apps/demo/src`, and relates to `demo-backend`;
- `demo-backend` maps to `apps/demo-api`, exposes
  `http://127.0.0.1:5174` as the demo backend base URL, and denies `apps/api`;
- `agenthub-platform` represents AgentHub platform maintenance and requires
  explicit platform mode plus approval.

Default denied paths include `.env*`, `node_modules`, `.git`, and `secrets`.
P7-1 does not yet migrate planner, instruction builder, or review logic to
consume the registry; that starts in P7-2 and P7-3/P7-4.

### Validation

| Command | Result |
|---|---|
| `pytest tests/test_target_registry.py -q` | Pass: 7 tests. |
| `bash scripts/check-api.sh` | Pass |
| `pnpm check` | Pass |
| `pnpm test` | Pass: 36 web tests, 138 API tests, 5 demo-api tests. |
| `git diff --check` | Pass |
| `openspec validate agenthub-p7-target-registry-permissioned-execution --strict` | Pass |

---

## P6-7 Final Full-stack Rehearsal And Freeze Review

**Date:** 2026-05-23

### Modified Files

| File | Change |
|---|---|
| `apps/demo-api/app/main.py` | Added local-preview CORS support so Vite previews can call the safe demo backend. |
| `apps/demo-api/tests/test_contacts.py` | Added CORS preflight coverage for local preview origins. |
| `docs/project-state.md` | Recorded final P6-7 freeze evidence and remaining caveats. |
| `docs/change-log.md` | Recorded this final rehearsal. |
| `openspec/changes/agenthub-p6-agent-execution-upgrade/tasks.md` | Marked P6-7 complete after the final rehearsal passed. |

### Review Result

P6 is ready to freeze as a practical agent execution capability upgrade for the
local single-user Agent Coding Workspace.

Fresh no-mention request:

```text
帮我做一个 mini CRM，包含联系人和备注
```

The final rehearsal used real `ClaudeCodeAdapter` execution for both Backend
Agent and Frontend Agent runs. The generated frontend used the contract demo
API base URL `http://127.0.0.1:5174`, and the final diff did not contain
`http://localhost:8000` or `http://127.0.0.1:8000`.

Browser inspection of the preview showed the contacts list with `Ada Lovelace`
and `Grace Hopper`, verifying that the mini CRM loaded data from the demo API.

### Evidence

| Field | Value |
|---|---|
| Session ID | `d39ed32a-8426-4c75-86a1-9fd10a57f44c` |
| Contract ID | `contract-mini_crm_contacts` |
| Demo API base URL | `http://127.0.0.1:5174` |
| Backend task / run | `efe6482b-b2e3-43a7-bae9-2aa0b44dde41`, `908a5708-3334-474c-8af6-b18e6ceaa319` |
| Frontend task / run | `f1d141d1-7fcb-4629-9ed1-20fd957d6ef4`, `7a01e9ea-8d5d-4690-ae4c-35fbca0b6309` |
| Adapter type | `claude_code` for both coding runs |
| Final diff artifact | `a89dba5d-cc92-490c-aca1-6c00cd20cc5c` |
| Final review artifact | `076f01c5-1949-4fa6-9715-623e41642edb` |
| Final review status / risk | `passed`, `low` |
| Preview | `d515ffaf-bf9d-481d-9b51-77aa57eb2cef`, `http://127.0.0.1:62947`, healthy |
| Mock deployment | `ff54062e-35ca-462d-a5f7-e9a4786517ec`, `mock`, `ready` |

### Remaining Caveats

- The planned QA/Review task remains pending; automatic post-diff review
  supplies contract consistency evidence.
- Review remains deterministic `scripted_mock`, not real Claude review.
- Deployment remains mock-labeled and is not production deployment.
- P6 remains bounded to supported mini app families, not arbitrary SaaS
  generation.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass: 36 web tests, 131 API tests, 5 demo-api tests. |
| `pnpm demo:api:test` | Pass: 5 tests. |
| `git diff --check` | Pass |
| `openspec validate agenthub-p6-agent-execution-upgrade --strict` | Pass |

Recommended freeze tag: `p6-agent-execution-upgrade-freeze`.

---

## P6-7a Demo API Base Alignment Fix

**Date:** 2026-05-23

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planning.py` | Added `demoApiBaseUrl` to contract-first app contracts and validation expectations. |
| `apps/api/app/instruction_builder.py` | Updated contract-aware Frontend Agent instructions to require the demo backend base URL and forbid AgentHub platform API base URLs for generated app data. |
| `apps/api/app/reviews.py` | Added scripted review detection for frontend diffs that reference the AgentHub platform API instead of the demo API base. |
| `apps/api/tests/test_planning.py` | Added contract coverage for `demoApiBaseUrl` and validation expectations. |
| `apps/api/tests/test_task_runs.py` | Added instruction and review coverage for demo API base alignment. |
| `apps/demo-api/app/main.py` | Added local-preview CORS support so Vite previews can call the safe demo backend. |
| `apps/demo-api/tests/test_contacts.py` | Added CORS preflight coverage for local preview origins. |
| `docs/project-state.md` | Recorded P6-7a behavior and remaining freeze caveat. |
| `docs/change-log.md` | Recorded this implementation. |

### What Changed

P6-7a fixes the P6-7 freeze blocker at the planning, instruction, and review
layers:

- mini app `appContract` payloads now include
  `demoApiBaseUrl: "http://127.0.0.1:5174"`;
- Frontend Agent instructions for contract-aware full-stack tasks now require
  using that demo backend base URL for app data calls;
- Frontend Agent instructions explicitly forbid calling
  `http://localhost:8000` or `http://127.0.0.1:8000` for generated app data;
- scripted review now warns when a contract-aware frontend diff references the
  AgentHub platform API base instead of the demo API base.
- the demo API now allows local preview origins through CORS.

P6-7a originally did not run a new real Claude/Codex mutation. A later final
P6-7 rehearsal verified that generated frontend code uses the demo API base and
browser-visible mini CRM data loads from `apps/demo-api`.

### Validation

| Command | Result |
|---|---|
| `pytest tests/test_planning.py tests/test_task_runs.py -q` | Pass: 43 tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass: 36 web tests, 131 API tests, 4 demo-api tests. |
| `pnpm demo:api:test` | Pass: 4 tests. |
| `git diff --check` | Pass |
| `openspec validate agenthub-p6-agent-execution-upgrade --strict` | Pass |

---

## P6-7 Full-stack Vertical Slice Rehearsal And Freeze Review

**Date:** 2026-05-23

### Modified Files

| File | Change |
|---|---|
| `docs/project-state.md` | Recorded the P6-7 freeze review result, persistent preview evidence, and integration blocker. |
| `docs/change-log.md` | Recorded this freeze review. |

### Review Result

P6 is not ready to freeze yet.

P6-7 reused the P6-6 real execution evidence instead of running another
Claude/Codex mutation. The existing P6-6 backend and frontend coding TaskRuns
both used `ClaudeCodeAdapter` and completed successfully. The final diff and
review artifacts still show a shared `contract-mini_crm_contacts` contract and
target-aware changes under both `apps/demo-api` and `apps/demo/src`.

### Persistent Preview Evidence

The old `127.0.0.1:8000` process accepted TCP connections but did not respond
to `/health`, so the rehearsal started a fresh persistent AgentHub API on
`127.0.0.1:8010` using `pnpm dev:api`.

Preview was started through the persistent API for frontend task run
`ade5c49c-097d-448e-831c-d10c6bdc3a71`.

| Field | Value |
|---|---|
| Preview ID | `3e500940-4d46-423b-af66-b36f1e6ba604` |
| Preview URL | `http://127.0.0.1:65046` |
| Preview health | `healthy` |
| Immediate `curl -I` | `200 OK` |
| Delayed `curl -I` after 20 seconds | `200 OK` |
| Mock deployment ID | `6b14e81b-c1d6-40ed-b6c4-88a3f846db60` |
| Mock deployment provider/status | `mock`, `ready` |

The temporary preview process and the temporary `8010` / `5174` dev services
were stopped after verification.

### Freeze Blocker

The generated frontend preview is reachable, but the app is not fully
integrated with the safe demo backend by default:

- `apps/demo-api` serves correctly on `http://127.0.0.1:5174`;
- `GET /health` and `GET /contacts` worked against `5174`;
- the generated P6-6 frontend code hardcodes
  `const API_BASE = "http://localhost:8000"`;
- browser inspection showed the preview stuck at `Loading contacts...`;
- `curl http://127.0.0.1:8000/contacts` timed out against the stale AgentHub API
  process.

The OpenSpec P6-7 checkbox remains unchecked. The recommended next task is a
targeted fix to pass the demo API base URL into contract-aware frontend
instructions and to add review/test coverage for frontend/backend API-base
consistency.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass: 36 web tests, 130 API tests, 4 demo-api tests. |
| `pnpm demo:api:test` | Pass: 4 tests. |
| `git diff --check` | Pass |
| `openspec validate agenthub-p6-agent-execution-upgrade --strict` | Pass |

---

## P6-6 Mini CRM Full-stack Vertical Slice

**Date:** 2026-05-22

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/reviews.py` | Added contract-aware scripted review checks so review artifacts can verify that final full-stack diffs include both backend and frontend contract targets. |
| `apps/api/tests/test_task_runs.py` | Added coverage for contract-aware review validation of backend and frontend changed files. |
| `docs/p6-mini-crm-vertical-slice.md` | Recorded P6-6 smoke evidence, IDs, changed files, validation notes, and caveats. |
| `docs/project-state.md` | Recorded the P6-6 vertical slice result and remaining caveats. |
| `docs/change-log.md` | Recorded this implementation and rehearsal. |
| `openspec/changes/agenthub-p6-agent-execution-upgrade/tasks.md` | Marked P6-6 complete after validation. |

### What Changed

P6-6 verified a bounded mini CRM full-stack vertical slice with the request:

```text
帮我做一个 mini CRM，包含联系人和备注
```

Orchestrator generated the shared `contract-mini_crm_contacts` app contract.
The Backend Agent task targeted `apps/demo-api`, the Frontend Agent task
targeted `apps/demo/src`, and both coding TaskRuns used `ClaudeCodeAdapter`.

The final accumulated diff covered:

- `apps/demo-api/app/main.py`;
- `apps/demo-api/tests/test_contacts.py`;
- `apps/demo/src/App.tsx`;
- `apps/demo/src/styles.css`.

The final automatic review artifact passed with low risk and verified contract
consistency for `contract-mini_crm_contacts`. The preview artifact was healthy
at creation and the deploy artifact remained mock-labeled.

### Evidence

| Field | Value |
|---|---|
| Session ID | `ad122cf7-afe7-4921-bbd9-b7e815539427` |
| Contract ID | `contract-mini_crm_contacts` |
| Backend task / run | `590cb06b-4a47-422e-b68f-79a873d4c84a`, `d6779d0f-afa3-4124-9117-c40b651dd79a` |
| Frontend task / run | `12ffc19d-f483-4f8d-a541-4c5b935a49b4`, `ade5c49c-097d-448e-831c-d10c6bdc3a71` |
| Adapter type | `claude_code` for both coding runs |
| Final diff artifact | `db403329-7f0c-4b2c-9134-d2d7ee652564` |
| Final review artifact | `1782b85d-c7f9-4d93-b699-27bd27a05ef7` |
| Preview | `79bfff4f-4991-470b-8862-eb43e7dac852`, `http://127.0.0.1:55592`, healthy at creation |
| Mock deployment | `e7b676d6-1505-43f8-be78-7120bfaef831`, `mock`, `ready` |

### Validation

| Command | Result |
|---|---|
| `pytest tests/test_task_runs.py -q` | Pass: 24 tests. |
| smoke worktree `apps/demo-api` tests | Pass: 6 tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass: 36 web tests, 130 API tests, 4 demo-api tests. |
| `pnpm demo:api:test` | Pass: 4 tests. |
| `git diff --check` | Pass |
| `openspec validate agenthub-p6-agent-execution-upgrade --strict` | Pass |

### Caveats

- This was API-driven rehearsal, not browser click rehearsal.
- The review path used deterministic `ScriptedMockAdapter` review behavior.
- The planned QA/Review task remained pending because the automatic post-diff
  review artifact supplied contract consistency evidence.
- A later `curl` to the recorded preview URL could not connect after the
  one-shot TestClient process exited, so long-lived preview availability should
  be checked under persistent `pnpm dev:api` during P6-7.
- Mock deploy remained mock-labeled and did not perform production deployment.

---

## P6-5 Target-Aware Contract-First Orchestrator

**Date:** 2026-05-22

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planning.py` | Added bounded app intent detection and contract-first task graph generation for todo, notes, and mini CRM contacts apps. |
| `apps/api/app/context_pack.py` | Added explicit `appContract` context in session context packs. |
| `apps/api/app/instruction_builder.py` | Added contract-aware role guidance for Manager, Backend, Frontend, and QA/Review instructions. |
| `apps/api/tests/test_planning.py` | Added coverage for bounded app parsing, no-mention mini CRM contract planning, target mapping, and unsupported SaaS boundaries. |
| `apps/api/tests/test_task_runs.py` | Added coverage that backend, frontend, and review instructions reference the same shared contract. |
| `docs/project-state.md` | Recorded P6-5 behavior, targets, and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p6-agent-execution-upgrade/tasks.md` | Marked P6-5 complete after validation. |

### What Changed

Orchestrator can now recognize bounded full-stack mini app requests for todo,
notes, and mini CRM contacts. For those requests, it generates a shared
`appContract` plan payload and creates a serial task graph:

```text
Manager / Contract task -> Backend Agent task -> Frontend Agent task -> QA / Review task
```

The contract contains app name/type, user goal, entities, fields, API routes,
frontend pages, `backendTarget: apps/demo-api`, `frontendTarget: apps/demo`,
validation expectations, and the task graph. Backend, frontend, and review
tasks all reference the same `contractId` and `appContract`.

P6-5 keeps the generated tasks pending by default. It does not implement actual
full-stack app generation, contract artifact persistence, production deploy,
auth, payments, multi-tenancy, Docker, provider marketplace, PR creation, or
permission for app backend tasks to edit `apps/api`.

Existing login-page, bounded frontend, no-mention dashboard auto-run, direct
`@frontend`, and direct `@backend` paths remain intact.

### Validation

| Command | Result |
|---|---|
| `pytest tests/test_planning.py tests/test_task_runs.py -q` | Pass: 41 tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `git diff --check` | Pass |
| `openspec validate agenthub-p6-agent-execution-upgrade --strict` | Pass |

Manual real Claude/Codex execution was not run for P6-5. The task is scoped to
contract-first planning and contract-aware instruction generation.

---

## P6-4 Safe Demo Backend Target Scaffold

**Date:** 2026-05-22

### Modified Files

| File | Change |
|---|---|
| `apps/demo-api/app/main.py` | Added isolated FastAPI demo backend with health and contacts endpoints. |
| `apps/demo-api/tests/test_contacts.py` | Added demo backend endpoint tests. |
| `apps/demo-api/README.md` | Documented demo backend purpose, endpoints, and commands. |
| `scripts/check-demo-api.sh` | Added compile check wrapper for the demo backend. |
| `scripts/test-demo-api.sh` | Added pytest wrapper for the demo backend. |
| `scripts/dev-demo-api.sh` | Added local uvicorn dev wrapper for the demo backend. |
| `package.json` | Added `check:demo-api`, `demo:api:test`, and `demo:api:dev`; included demo-api checks/tests in root validation. |
| `apps/api/app/planning.py` | Updated direct `@backend` assignment to create a safe `apps/demo-api` task when the scaffold exists. |
| `apps/api/app/instruction_builder.py` | Updated Backend Agent instructions to target `apps/demo-api` and keep `apps/api` protected. |
| `apps/api/tests/test_planning.py` | Updated direct backend mention coverage for safe demo backend task creation. |
| `apps/api/tests/test_task_runs.py` | Updated backend instruction coverage for the available demo backend target. |
| `AGENTS.md` | Added demo-api commands and scaffold description to project guardrails. |
| `docs/project-state.md` | Recorded P6-4 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p6-agent-execution-upgrade/tasks.md` | Marked P6-4 complete after validation. |

### What Changed

Added `apps/demo-api` as a safe application backend target for Backend Agent
work. The scaffold is intentionally small: a FastAPI contacts API with
in-memory data and `GET /health`, `GET /contacts`, and `POST /contacts`.

Direct `@backend` requests now create a pending `backend_change` task assigned
to the Backend Agent when `apps/demo-api` exists. The task is bounded to
`apps/demo-api` files and does not auto-start in P6-4. AgentHub platform
backend files under `apps/api` remain protected by instruction and planning
metadata.

P6-4 does not implement contract-first orchestration, full-stack generation,
production deploy, Docker, cloud database, auth, payments, multi-tenancy, or
automatic frontend integration with the demo API.

### Validation

| Command | Result |
|---|---|
| `pnpm check:demo-api` | Pass |
| `pnpm demo:api:test` | Pass: 4 tests. |
| `pytest tests/test_planning.py tests/test_task_runs.py -q` | Pass: 37 tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `git diff --check` | Pass |
| `openspec validate agenthub-p6-agent-execution-upgrade --strict` | Pass |

---

## P6-2 / P6-3 Session Context Pack And Role-Based Instructions

**Date:** 2026-05-22

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/context_pack.py` | Added a reusable session context pack builder for adapter execution. |
| `apps/api/app/instruction_builder.py` | Added role-specific instruction generation for manager, frontend, backend, and QA/review tasks. |
| `apps/api/app/main.py` | Updated TaskRun request construction to attach `sessionContext` and use role-based instructions. |
| `apps/api/tests/test_task_runs.py` | Added coverage for context pack contents, artifact metadata, selected artifact validation, frontend request preservation, backend missing-target honesty, and review diff context. |
| `docs/project-state.md` | Recorded P6-2/P6-3 behavior and limitations. |
| `docs/change-log.md` | Recorded this implementation. |
| `openspec/changes/agenthub-p6-agent-execution-upgrade/tasks.md` | Marked P6-2 and P6-3 complete after validation. |

### What Changed

Implemented the P6 session context and instruction quality layer. Adapter
requests now include a `sessionContext` object in `planContext`, and generated
instructions embed the same context as JSON for Claude Code / Codex.

The context pack includes the original user request, current task metadata,
recent same-session messages, ledger summary, latest changed files, latest diff
metadata, latest review summary, latest preview/deploy state, selected artifact
context when provided, safe target paths, and validation expectations.

Role-specific instruction behavior:

- Manager / Orchestrator: plan, route, clarify, or reject unsupported requests
  honestly.
- Frontend: preserve the original request, include session context, keep
  legacy login-page/button/title paths intact, and allow meaningful bounded
  changes inside `apps/demo/src`.
- Backend: prepare for `apps/demo-api` while clearly stating that the target is
  unavailable and `apps/api` must not be modified.
- QA / Review: remain read-oriented and focus on diff, changed files, ledger,
  preview/deploy status, and advisory findings.

P6-2/P6-3 do not add a demo backend scaffold, full-stack generation,
Manager/Worker scheduling, production deploy, new adapters, or broader
guardrail permissions.

### Validation

| Command | Result |
|---|---|
| `pytest tests/test_planning.py tests/test_task_runs.py -q` | Pass: 37 tests. |
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `git diff --check` | Pass |
| `openspec validate agenthub-p6-agent-execution-upgrade --strict` | Pass |

Manual follow-up smoke did not run a new real Claude/Codex mutation. Follow-up
context support was verified through backend tests that inspect generated
`sessionContext` and role instructions.

---

## P6-1b Orchestrator Autonomy Real Smoke

**Date:** 2026-05-22

### Modified Files

| File | Change |
|---|---|
| `docs/p6-orchestrator-autonomy-smoke.md` | Added detailed real smoke evidence for no-mention Orchestrator auto-run. |
| `docs/project-state.md` | Recorded P6-1b smoke result, evidence IDs, and caveats. |
| `docs/change-log.md` | Recorded this P6-1b smoke documentation update. |

### What Was Verified

Ran one API-driven real execution smoke with
`AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code` and the request:

```text
帮我把当前 demo app 改成一个 dashboard，有三张统计卡片和一个最近活动列表
```

The normal no-mention message routed to Orchestrator / Manager, created a safe
demo frontend task, auto-started a TaskRun, invoked `ClaudeCodeAdapter`,
produced a real diff, generated a scripted Review artifact, started a healthy
preview during the smoke, and created a mock deploy card.

Evidence:

- session ID: `cca9af54-1338-4cdd-b239-7f8b6e1dcc76`;
- message ID: `48bad4c0-8ddf-4514-bf35-d2561082c22e`;
- task ID: `63a8aded-b311-40f3-a54c-a40d232102c5`;
- task run ID: `210f3f89-df0f-4e72-8c20-d505faed5ea2`;
- adapter type: `claude_code`;
- final state: `completed`;
- changed files: `apps/demo/src/App.tsx`,
  `apps/demo/src/styles.css`;
- diff artifact ID: `7114d52a-925a-4c4d-a00b-4d6c8775a20c`;
- review artifact ID: `ce989818-5d85-4f88-9f70-8b9b5e69d606`;
- preview ID / health during smoke:
  `841f7fd6-bb75-4e80-b19c-9b228f5040fb`, `healthy`;
- mock deployment ID / status:
  `7c9fab78-2b5f-44b3-a9fc-2af0d912a757`, `ready`.

### Caveats

This smoke used FastAPI `TestClient`, not browser click automation. The
preview was healthy during the smoke, but a follow-up `curl` after the
one-shot TestClient process exited could not reach the preview URL. Verify
long-lived preview availability again under `pnpm dev:api` during a later
browser rehearsal.

The Review artifact used deterministic `scripted_mock` review behavior.
ScriptedMock fallback execution was not needed because real Claude Code
completed successfully.

---

## P6-1 Orchestrator Autonomy Spike

**Date:** 2026-05-22

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planning.py` | Added default Orchestrator routing, explicit direct assignment routing, safe demo frontend task creation, backend missing-target response, and `@review` routing through QA-backed review tasks. |
| `apps/api/app/main.py` | Added safe demo task auto-start after message planning and a generic demo frontend instruction that preserves the original user request. |
| `apps/api/tests/test_planning.py` | Added coverage for no-mention Orchestrator routing, auto-started demo frontend tasks, direct `@frontend`, `@backend`, and `@review` behavior. |
| `apps/api/tests/test_task_runs.py` | Added coverage for generic demo frontend instructions and plan context preservation. |
| `apps/api/tests/test_chat_events.py` | Updated message scoping expectations for Orchestrator boundary responses. |
| `docs/project-state.md` | Recorded P6-1 behavior, validation, and limitations. |
| `docs/change-log.md` | Recorded this P6-1 implementation. |
| `openspec/changes/agenthub-p6-agent-execution-upgrade/proposal.md` | Updated P6-1 wording for Orchestrator auto-run. |
| `openspec/changes/agenthub-p6-agent-execution-upgrade/design.md` | Documented the narrow auto-run spike decision and boundaries. |
| `openspec/changes/agenthub-p6-agent-execution-upgrade/specs/agent-execution/spec.md` | Added the auto-run requirement scenario for Orchestrator-created safe demo coding tasks. |
| `openspec/changes/agenthub-p6-agent-execution-upgrade/tasks.md` | Marked P6-1 complete after validation. |

### What Changed

Implemented P6-1 as a narrow Orchestrator autonomy spike. Normal user messages
without explicit role mentions now route to Orchestrator / Manager by default.
When Orchestrator can map a request to a safe demo frontend target, it creates
a frontend task and automatically starts a TaskRun through the existing
execution path.

Explicit mentions now act as assignment shortcuts:

- `@frontend` creates a pending frontend task for bounded demo UI requests;
- `@backend` reports that a safe demo backend target is required before backend
  execution can run;
- `@qa` creates a QA review-style task;
- `@review` creates a read-only review task backed by the QA agent path.

Generic demo frontend instructions now preserve the original user request and
allow broader edits inside `apps/demo/src`, while still blocking `.env`,
secrets, `node_modules`, production deploy, dependency installation, arbitrary
host commands, and AgentHub platform backend edits.

P6-1 does not add a full approval/risk engine, Manager/Worker scheduler,
full-stack app generation, production deploy, multi-user IM, provider
marketplace, Docker sandbox, or PR creation.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass: 36 web tests and 121 API tests. |
| `git diff --check` | Pass |
| `openspec validate agenthub-p6-agent-execution-upgrade --strict` | Pass |

Manual browser smoke was not run for P6-1. No real Claude/Codex success was
claimed in this task.

---

## P5-7 E2E Rehearsal And Freeze Review

**Date:** 2026-05-22

### Modified Files

| File | Change |
|---|---|
| `AGENTS.md` | Aligned baseline guardrails with the completed P5 ledger/review/artifact UI state. |
| `docs/project-state.md` | Recorded P5 freeze readiness, evidence, caveats, validation, and recommended tag name. |
| `docs/change-log.md` | Recorded this P5-7 freeze review. |
| `openspec/changes/agenthub-p5-platform-evolution/tasks.md` | Marked P5-7 complete after validation. |

### What Changed

Completed the P5 freeze review for
`agenthub-p5-platform-evolution`. The review confirms AgentHub now presents as
a local single-user IM-style multi-agent coding workspace v1 while preserving
the P4 final demo loop:

```text
requirement -> plan -> agent execution -> diff -> preview -> mock deploy
```

The review used the P4 browser evidence for real Claude Code and fallback
execution paths, plus P5 backend/frontend test coverage and code review for the
new workspace shape:

- Agent contact list and local Direct chat / Group workflow visual modes;
- session execution ledger and Workspace Context card;
- bounded Dynamic Manager Planner v1;
- non-blocking Review Agent artifacts;
- Multi-Agent Execution Trace;
- Diff, Review, Preview, and Mock Deploy artifact message cards.

No new Claude/Codex mutation was run during P5-7. P5 remains explicitly scoped
to a local single-user workspace and does not add multi-user IM, external IM
integration, production deploy, provider marketplace, Docker sandbox, PR
creation, or unrestricted arbitrary editing.

### Validation

| Command | Result |
|---|---|
| `openspec validate agenthub-p5-platform-evolution --strict` | Pass |
| `pnpm check` | Pass |
| `pnpm test` | Pass: 36 web tests and 116 API tests. |
| `git diff --check` | Pass |

Recommended freeze tag after committing:

```text
agenthub-p5-platform-evolution-freeze
```

---

## P5-6 Artifact Message Cards v2

**Date:** 2026-05-21

### Modified Files

| File | Change |
|---|---|
| `apps/web/src/components/task-card-list.tsx` | Added inline message-style cards for Diff, Review, Preview, and Mock Deploy artifacts with panel/context/action affordances. |
| `apps/web/src/components/task-card-list.test.tsx` | Added frontend coverage for artifact cards, context selection, review action, preview open, and mock deploy action behavior. |
| `apps/web/src/components/workspace-shell.tsx` | Added local session-scoped follow-up artifact context chip and wired review/deploy/preview card actions to existing APIs. |
| `apps/web/src/components/workspace-shell.test.tsx` | Updated API mocks for the Review action. |
| `docs/project-state.md` | Recorded P5-6 behavior, limitations, and validation. |
| `docs/change-log.md` | Recorded this P5-6 implementation. |
| `openspec/changes/agenthub-p5-platform-evolution/tasks.md` | Marked P5-6 complete after validation. |

### What Changed

Implemented frontend-first artifact message cards for the P5 IM-style
workspace. Diff, Review, Preview, and Mock Deploy artifacts now render as
inline cards inside the task timeline with source task/run metadata, status,
key artifact details, and action buttons.

Mapped card actions only to existing behavior:

- inspect artifact in the right Artifact Panel;
- use Diff or Review as local follow-up context;
- trigger the existing Review API for a Diff when no review is loaded;
- open an existing Preview;
- create an existing mock deploy card from a healthy Preview.

The composer now shows a session-scoped local follow-up context chip for the
selected artifact. P5-6 does not persist artifact references in backend message
records, and it does not change planner or adapter semantics.

Mock Deploy remains clearly labeled as mock evidence rather than production
deployment.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass: 36 web tests and 116 API tests. |
| `git diff --check` | Pass |
| `openspec validate agenthub-p5-platform-evolution --strict` | Pass |

---

## P5-5 Dynamic Manager Planner v1

**Date:** 2026-05-21

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planning.py` | Added a bounded rule-based Manager planner v1, structured task graph metadata, graph validation, and dynamic frontend intent classification. |
| `apps/api/app/main.py` | Added bounded adapter instructions for the new frontend change targets. |
| `apps/api/tests/test_planning.py` | Added coverage for dynamic intents, graph metadata, follow-up review tasks, and unsupported fallback behavior. |
| `docs/project-state.md` | Recorded P5-5 behavior, limitations, and validation. |
| `docs/change-log.md` | Recorded this P5-5 implementation. |
| `openspec/changes/agenthub-p5-platform-evolution/tasks.md` | Marked P5-5 complete after validation. |

### What Changed

Implemented a deterministic local Manager planner v1 for bounded frontend
change intents. The planner now classifies these supported requests:

- title or heading text change;
- primary button text change;
- theme/accent color change;
- simple input field addition;
- simple status/help text addition;
- small layout copy adjustment.

Supported orchestrator-led requests produce a structured task graph with goal,
planner version, intent, task nodes, assigned agent role, priority,
dependencies, and expected artifact types. The graph creates Manager, Frontend
Coding, and Review tasks. Same-session follow-up requests create a serial
Frontend Coding task followed by a Review task.

The original login-page path remains deterministic and is labeled
`deterministic_login_v1`. Unsupported broad requests fall back to the existing
deterministic behavior and do not create tasks or claim support.

P5-5 does not call an LLM planner, implement unrestricted arbitrary editing,
change adapter dispatch, add Manager/Worker scheduling, add production deploy,
or add real multi-user IM.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass: 34 web tests and 116 API tests. |
| `git diff --check` | Pass |
| `openspec validate agenthub-p5-platform-evolution --strict` | Pass |

---

## P5-4 Multi-Agent Execution Trace UI

**Date:** 2026-05-21

### Modified Files

| File | Change |
|---|---|
| `apps/web/src/components/task-card-list.tsx` | Added a derived multi-agent execution trace for Manager, Coding Agent, Diff, Review, Preview, and Mock Deploy stages. |
| `apps/web/src/components/task-card-list.test.tsx` | Added coverage for trace rendering, fallback highlighting, review warning highlighting, and artifact links. |
| `docs/project-state.md` | Recorded P5-4 behavior, limitations, and validation. |
| `docs/change-log.md` | Recorded this P5-4 implementation. |
| `openspec/changes/agenthub-p5-platform-evolution/tasks.md` | Marked P5-4 complete after validation. |

### What Changed

Implemented a frontend-first multi-agent execution trace in the task timeline.
The trace derives its state from existing tasks, task runs, artifacts, reviews,
previews, and deployments. It shows:

- Manager planned;
- Coding Agent ran;
- Diff produced;
- Review Agent reviewed;
- Preview healthy;
- Mock deploy ready.

Each stage shows agent or service identity, adapter/service type, status, and
artifact links where available. Diff, Review, Preview, and Mock Deploy nodes
reuse the existing artifact selection behavior so the right-side artifact panel
remains the detailed inspector.

Fallback recovery and review warning states are highlighted. System-generated
steps are labeled as services rather than autonomous agents.

P5-4 does not change adapter dispatch, task execution, diff collection, preview,
mock deployment, Review Agent semantics, or backend runtime behavior. It does
not add Manager/Worker scheduling, dynamic planning, real multi-user IM,
production deploy, or real Claude/Codex review execution.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass: 34 web tests and 113 API tests. |
| `git diff --check` | Pass |
| `openspec validate agenthub-p5-platform-evolution --strict` | Pass |

---

## P5-3 Review Agent Workflow

**Date:** 2026-05-21

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/models.py` | Added persisted `Review` records linked to review artifacts and reviewed diff artifacts. |
| `apps/api/app/reviews.py` | Added deterministic scripted review creation, listing, idempotency, and event emission. |
| `apps/api/app/ledger.py` | Included latest review summary in session ledger summaries. |
| `apps/api/app/schemas.py` | Added the Review artifact response schema. |
| `apps/api/app/main.py` | Added review endpoints and automatic non-blocking scripted review creation after diff generation. |
| `apps/api/tests/test_models.py` | Updated model boundary coverage for Review. |
| `apps/api/tests/test_diffs.py` | Covered automatic review creation, manual/idempotent review creation, and ledger summary updates. |
| `apps/web/src/lib/api.ts` | Added Review artifact types and review API helpers. |
| `apps/web/src/lib/api.test.ts` | Added client API coverage for review create/list endpoints. |
| `apps/web/src/components/__fixtures__/sample-review.ts` | Added a reusable review artifact fixture. |
| `apps/web/src/components/task-card-list.tsx` | Loaded Review artifacts and rendered review timeline chips. |
| `apps/web/src/components/task-card-list.test.tsx` | Covered review timeline chip and artifact panel handoff behavior. |
| `apps/web/src/components/preview-card.tsx` | Added Review artifacts to the right-side artifact panel. |
| `apps/web/src/components/preview-card.test.tsx` | Covered Review artifact rendering. |
| `docs/project-state.md` | Recorded P5-3 behavior, limitations, and validation. |
| `docs/change-log.md` | Recorded this P5-3 implementation. |
| `openspec/changes/agenthub-p5-platform-evolution/tasks.md` | Marked P5-3 complete after validation. |

### What Changed

Implemented a non-blocking Review Agent workflow after diff generation. When a
TaskRun produces a diff, AgentHub now creates a persisted Review artifact using
the deterministic `scripted_mock` review path. The review includes status,
risk level, summary, files reviewed, findings, suggested changes, reviewed diff
artifact ID, and adapter type.

The review path is advisory only. It does not prevent preview creation or mock
deployment, and it does not change existing coding adapter behavior. No real
Claude or Codex review execution was run or claimed in this task.

The right artifact panel now supports Review artifacts alongside Diff, Preview,
and Mock Deploy. The task timeline loads review artifacts and shows a review
chip when one is available. The session ledger summary includes the latest
review summary after refresh.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass: 33 web tests and 113 API tests. |
| `git diff --check` | Pass |
| `openspec validate agenthub-p5-platform-evolution --strict` | Pass |

---

## P5-2 Shared Context and Execution Ledger

**Date:** 2026-05-21

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/models.py` | Added persisted `SessionExecutionLedger` for session-scoped context snapshots. |
| `apps/api/app/ledger.py` | Added deterministic ledger refresh/read helpers derived from messages, tasks, runs, and artifacts. |
| `apps/api/app/schemas.py` | Added the execution ledger response schema. |
| `apps/api/app/main.py` | Added `GET /sessions/{session_id}/ledger` and refreshed ledger after message/planning, diff, preview, and mock deploy events. |
| `apps/api/tests/test_models.py` | Updated model boundary coverage for the new ledger table. |
| `apps/api/tests/test_planning.py` | Covered ledger creation after requirement planning. |
| `apps/api/tests/test_diffs.py` | Covered ledger updates after diff collection. |
| `apps/api/tests/test_previews.py` | Covered ledger updates after healthy preview creation. |
| `apps/api/tests/test_deployments.py` | Covered ledger updates after mock deployment creation. |
| `apps/web/src/lib/api.ts` | Added `SessionExecutionLedger` and `getSessionLedger`. |
| `apps/web/src/lib/api.test.ts` | Added client API coverage for session ledger reads. |
| `apps/web/src/components/workspace-shell.tsx` | Added the selected-session `Workspace Context` card. |
| `apps/web/src/components/workspace-shell.test.tsx` | Added UI coverage for the workspace context ledger card. |
| `docs/project-state.md` | Recorded P5-2 state, refresh points, limitations, and validation. |
| `docs/change-log.md` | Recorded this P5-2 implementation. |
| `openspec/changes/agenthub-p5-platform-evolution/tasks.md` | Marked P5-2 complete after validation. |

### What Changed

Implemented a lightweight persisted execution ledger for each session. The
ledger stores the current goal, active agents, latest task/run/diff/preview/mock
deploy references, changed files, last successful adapter, summary Markdown,
and update timestamp.

The ledger is refreshed from existing database records after user
message/planning, diff collection, healthy preview creation or refresh, and mock
deployment creation. The read endpoint also refreshes from persisted data so
older sessions can be reconstructed without adding cross-session memory.

The frontend now renders a compact `Workspace Context` card in the workspace
shell for the selected session. It shows the current goal, active agents, latest
evidence, adapter, and changed files while keeping the existing task timeline
and artifact panel intact.

P5-2 does not add vector DB, embeddings, cross-session long-term memory, Review
Agent execution, Manager/Worker scheduling, or adapter execution changes.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass: 30 web tests and 113 API tests. |
| `git diff --check` | Pass |
| `openspec validate agenthub-p5-platform-evolution --strict` | Pass |

---

## P5-1 Agent Registry and IM Contact UI

**Date:** 2026-05-21

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/schemas.py` | Added the agent contact response schema for IM-style registry metadata. |
| `apps/api/app/repositories.py` | Ordered enabled agent lookup for deterministic registry output. |
| `apps/api/app/main.py` | Added the workspace-scoped agent contact registry endpoint and display metadata mapping. |
| `apps/api/tests/test_planning.py` | Added backend coverage for built-in contacts, Review placeholder, and ScriptedMock fallback service. |
| `apps/web/src/lib/api.ts` | Added `AgentContact` and `listWorkspaceAgents`. |
| `apps/web/src/lib/api.test.ts` | Added client API coverage for workspace agent contacts. |
| `apps/web/src/app/page.tsx` | Loaded agent contacts for the workspace shell. |
| `apps/web/src/app/page.test.tsx` | Covered passing fetched contacts into the shell. |
| `apps/web/src/components/workspace-shell.tsx` | Added the Agent Contact UI and Direct chat / Group workflow visual modes. |
| `apps/web/src/components/workspace-shell.test.tsx` | Added UI coverage for contacts and visual modes. |
| `docs/project-state.md` | Recorded P5-1 state, limitations, and validation. |
| `docs/change-log.md` | Recorded this P5-1 implementation. |
| `openspec/changes/agenthub-p5-platform-evolution/tasks.md` | Marked P5-1 complete after validation. |

### What Changed

Implemented P5-1 without changing runtime execution semantics. AgentHub now
has a backend-backed contact registry shape for enabled built-in agents and
renders them as first-class IM-style contacts in the workspace sidebar.

The registry exposes display name, avatar initials, role, adapter type,
capability tags, status, contact type, and write/review safety flags. It keeps
the existing `CodexAdapter`, `ClaudeCodeAdapter`, and `ScriptedMockAdapter`
model intact, adds a Review Agent placeholder for future P5 review workflow
work, and keeps ScriptedMock visible as the fallback service.

The UI adds Direct chat and Group workflow as local visual modes only. P5-1
does not add multi-user accounts, external IM integration, Manager/Worker
scheduling, dynamic planning, Review Agent execution, provider marketplace, or
production deploy.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass: 28 web tests and 114 API tests. |
| `git diff --check` | Pass |
| `openspec validate agenthub-p5-platform-evolution --strict` | Pass |

---

## P4-6 Final Freeze Review

**Date:** 2026-05-20

### Modified Files

| File | Change |
|---|---|
| `docs/project-state.md` | Recorded final freeze readiness, caveats, validation results, and recommended tag name. |
| `docs/change-log.md` | Recorded this final freeze review. |
| `openspec/changes/agenthub-final-demo-hardening/tasks.md` | Marked P4-6 complete after validation. |

### What Changed

Completed the final freeze review for `agenthub-final-demo-hardening`.

The review verified that baseline docs consistently describe AgentHub as a
local single-user Agent Coding Workspace / strong demo MVP and do not claim a
full IM multi-user platform, production deploy, provider marketplace, Docker
sandbox, PR creation, or broad arbitrary natural-language editing.

Remaining caveats are documented:

- deploy is mock-backed, not production deployment;
- browser click automation limitations are recorded;
- `pnpm demo:reset` does not delete `.worktrees`;
- `pnpm demo:reset` does not stop stale preview or dev-server processes;
- mobile/responsive polish remains future work.

No app code, runtime behavior, adapter behavior, UI redesign, or production
deployment work changed.

### Validation

| Command | Result |
|---|---|
| `openspec validate agenthub-im-coding-mvp --strict` | Pass |
| `openspec validate agenthub-final-demo-hardening --strict` | Pass |
| `pnpm check` | Pass |
| `pnpm test` | Pass: 26 web tests and 113 API tests. |
| `git diff --check` | Pass |

Recommended final tag after committing this review:

```text
agenthub-final-demo-hardening-freeze
```

---

## P4-5 Final Project Summary / Interview Explanation

**Date:** 2026-05-20

### Modified Files

| File | Change |
|---|---|
| `docs/project-summary-for-interview.md` | Added a truthful final summary for demo, review, and interview use. |
| `docs/project-state.md` | Recorded P4-5 summary scope. |
| `docs/change-log.md` | Recorded this documentation update. |
| `openspec/changes/agenthub-final-demo-hardening/tasks.md` | Marked P4-5 complete after doc validation. |

### What Changed

Created a final project summary that explains AgentHub as a local single-user
Agent Coding Workspace / strong demo MVP. The summary covers the problem,
architecture, session worktree model, adapter model, artifact pipeline,
failure-recovery path, follow-up text-change flow, real versus mock components,
explicit non-goals, design trade-offs, and interview talking points.

The summary refers to `docs/e2e-capability-audit.md` for evidence rather than
inventing new IDs.

No app code or runtime behavior changed.

### Validation

| Command | Result |
|---|---|
| `git diff --check` | Pass |

---

## P4-4 Final Demo Checklist

**Date:** 2026-05-20

### Modified Files

| File | Change |
|---|---|
| `docs/final-demo-checklist.md` | Added an evidence-first final demo checklist for reset, startup, real-agent path, fallback path, follow-up path, evidence IDs, and troubleshooting. |
| `docs/demo-script.md` | Linked the final demo checklist from setup instructions. |
| `docs/project-state.md` | Recorded P4-4 checklist scope. |
| `docs/change-log.md` | Recorded this documentation update. |
| `openspec/changes/agenthub-final-demo-hardening/tasks.md` | Marked P4-4 complete after doc validation. |

### What Changed

Created a final demo checklist that can be followed before rehearsal,
recording, or review. It covers:

- `pnpm demo:reset`;
- backend and frontend startup;
- optional `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code`;
- fixed request `@orchestrator build a login page for the demo app`;
- task run and adapter verification;
- diff artifact, preview iframe, and mock deploy card checks;
- forced-failure fallback through `ScriptedMockAdapter`;
- follow-up request `把按钮文案改成 Sign in`;
- evidence ID capture;
- troubleshooting for ports, API availability, Claude/Codex auth or quota,
  stale preview, and reset refusal while the API has SQLite open.

No app code or runtime behavior changed.

### Validation

| Command | Result |
|---|---|
| `git diff --check` | Pass |

---

## P4-3 Safe Demo Reset Helper

**Date:** 2026-05-20

### Modified Files

| File | Change |
|---|---|
| `scripts/demo-reset.sh` | Added a non-destructive local demo reset helper that backs up SQLite state before rebuilding the seeded DB. |
| `package.json` | Added `pnpm demo:reset`. |
| `AGENTS.md` | Added `pnpm demo:reset` to the documented project command allowlist. |
| `README.md` | Documented safe reset behavior, backup location, and restore method. |
| `docs/demo-script.md` | Added clean rehearsal setup guidance. |
| `docs/project-state.md` | Recorded P4-3 reset helper behavior. |
| `docs/change-log.md` | Recorded this task. |
| `openspec/changes/agenthub-final-demo-hardening/tasks.md` | Marked P4-3 complete after reset rehearsal and validation. |

### What Changed

Added a repeatable reset workflow for local demo state:

```bash
pnpm demo:reset
```

The helper backs up `apps/api/data/agenthub.sqlite3` and any SQLite WAL/SHM
files under `apps/api/data/backups/demo-reset-<timestamp>/`, removes only the
active SQLite files after backup, then recreates and seeds the DB with the
existing SQLModel initialization path.

The helper does not delete `.worktrees`, source code, dependencies, or preview
files, and it does not stop running preview or dev-server processes. It refuses
to run while the SQLite database is open by the API process and prints restore
instructions for the backup it created.

### Validation

| Command | Result |
|---|---|
| `pnpm demo:reset` while API had SQLite open | Pass: refused reset and printed the owning process. |
| `pnpm demo:reset` after stopping API | Pass: backed up the DB and recreated seeded SQLite state. |
| SQLite seed check | Pass: 1 user, 1 workspace, 4 agents, 0 sessions, 0 task runs, 0 previews. |
| `.worktrees` check | Pass: `.worktrees` remained present and was not deleted. |
| `pnpm check` | Pass |
| `pnpm test` | Pass: 26 web tests and 113 API tests. |
| `git diff --check` | Pass |

Reset rehearsal backup:

```text
apps/api/data/backups/demo-reset-20260520-124612/
```

---

## Long-Term Platform Roadmap

**Date:** 2026-05-20

### Modified Files

| File | Change |
|---|---|
| `docs/platform-roadmap.md` | Added a long-term AgentHub platform roadmap from current local demo baseline to IM-style multi-agent collaboration platform. |
| `docs/change-log.md` | Recorded this roadmap documentation update. |

### What Changed

Created a strategic roadmap that keeps the current final-demo-hardening scope
separate from future platform work. It covers dynamic orchestrator planning,
shared context and memory, manager/worker scheduling, a Claude Code security
review agent, multi-user IM integration, plugin/skill ecosystem, and real deploy
providers.

The roadmap explicitly states that these phases are not current three-week
tasks and should become focused OpenSpec changes before implementation.

### Validation

| Command | Result |
|---|---|
| `git diff --check` | Pass |

---

## P4-2 Browser E2E Click Rehearsal

**Date:** 2026-05-20

### Modified Files

| File | Change |
|---|---|
| `docs/e2e-capability-audit.md` | Added P4-2 browser-click rehearsal evidence for real Claude Code and fallback paths, plus reload and UI caveats. |
| `docs/project-state.md` | Recorded P4-2 evidence IDs and the reload caveat in the stable project state. |
| `docs/change-log.md` | Recorded this documentation update. |
| `openspec/changes/agenthub-final-demo-hardening/tasks.md` | Marked P4-2 complete after browser rehearsal and validation. |

### What Changed

Documented a browser UI click rehearsal for the final AgentHub demo hardening
change. The rehearsal verified:

```text
requirement -> plan -> UI Start run -> agent execution -> diff -> preview -> mock deploy
```

Real-agent path:

- Session: `59ad209a-1f8d-4134-97c4-e4ad275b6f67`
- TaskRun: `f1e78e9e-2f6b-4b9c-b4a7-5879d513c555`
- Adapter: `claude_code`
- Diff artifact: `b4c0fae4-bfeb-4105-a506-64de639472c6`
- Preview: `4eb1622b-fb10-49e7-9b3d-5c256fad4b29`
- Preview URL: `http://127.0.0.1:49373`
- Deployment: `6c5a423c-ec7b-4070-9a05-87a8dddd91a1`
- Provider/status: `mock`, `ready`

Fallback path:

- Session: `c148a1d6-8cd1-4efb-a797-7d10bbe475aa`
- Failed Codex TaskRun: `e7cead6e-93cd-4195-9a53-e258da253a81`
- Failed error code: `CODEX_DEMO_FORCED_FAILURE`
- Fallback TaskRun: `36d68849-f644-4242-a64b-27c05b8cf2d8`
- Adapter: `scripted_mock`
- Diff artifact: `fbe67726-20e3-4ad5-9b08-d4514aa97cbe`
- Preview: `6c7f6f46-e287-4698-b6be-c99058f69b11`
- Preview URL: `http://127.0.0.1:49752`
- Deployment: `a0b5d533-acee-4b2a-a384-103197d46481`
- Provider/status: `mock`, `ready`

### Caveats

- The broad browser locator for the Start button initially matched all three
  task cards; the rehearsal recovered by targeting the second `开始运行` button
  for the frontend task.
- After reload, the artifact panel defaults to the Diff tab even when preview
  and deployment artifacts are persisted. Clicking `预览1` restores the preview
  URL and iframe view.
- No app code, product behavior, UI redesign, provider marketplace, production
  deploy, Docker sandbox, WebSocket/multiplayer, PR creation, or broad editing
  feature was added.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `git diff --check` | Pass |

### Follow-Up Browser Spot Check

On 2026-05-20, the persisted P4-2 real Claude Code and fallback sessions were
re-opened in the Codex in-app browser without running another real agent
mutation.

- Real Claude Code session
  `59ad209a-1f8d-4134-97c4-e4ad275b6f67` still showed completed
  `claude_code` evidence, the `apps/demo/src/App.tsx` diff chip, preview iframe
  `http://127.0.0.1:49373`, and mock deployment
  `6c5a423c-ec7b-4070-9a05-87a8dddd91a1`.
- Fallback session `c148a1d6-8cd1-4efb-a797-7d10bbe475aa` still showed
  `CODEX_DEMO_FORCED_FAILURE`, `scripted_mock`, `兜底已恢复`, `Diff 就绪`,
  `预览健康`, and `模拟部署就绪`.

---

## P4-1 Baseline Governance Cleanup

**Date:** 2026-05-20

### Modified Files

| File | Change |
|---|---|
| `AGENTS.md` | Updated the repo guardrails from P0-only wording to the current final-demo baseline, including Codex, Claude Code, and scripted mock adapters. |
| `README.md` | Reframed AgentHub as a local single-user Agent Coding Workspace / strong demo MVP and documented current adapter paths. |
| `docs/project-state.md` | Added P4-1 governance baseline notes preserving P0/P1/P2/P3/P4 verified paths. |
| `docs/change-log.md` | Recorded this cleanup. |
| `openspec/changes/agenthub-im-coding-mvp/specs/worktree-diff/spec.md` | Changed the optional patch-validation requirement to strict-compatible MUST wording. |
| `openspec/changes/agenthub-final-demo-hardening/proposal.md` | Added a documentation/verification capability for strict OpenSpec validation. |
| `openspec/changes/agenthub-final-demo-hardening/specs/demo-baseline-hardening/spec.md` | Added governance and evidence-discipline requirements for final demo hardening. |
| `openspec/changes/agenthub-final-demo-hardening/tasks.md` | Marked P4-1 complete after validation. |

### What Changed

Aligned baseline governance around the current project state:

- AgentHub is now consistently described as a local single-user Agent Coding
  Workspace / strong demo MVP, not a complete multi-user IM collaboration
  platform.
- `CodexAdapter`, `ClaudeCodeAdapter`, and `ScriptedMockAdapter` are all treated
  as current adapters and must not be removed or regressed.
- The fallback-based P0 path remains preserved.
- Production deploy, provider marketplace, Docker sandbox, WebSocket/multiplayer,
  external IM integrations, PR creation, broad arbitrary editing, and enterprise
  workflows remain out of scope.
- The previous OpenSpec strict-validation issue in `worktree-diff` is fixed.

### Validation

| Command | Result |
|---|---|
| `openspec validate agenthub-im-coding-mvp --strict` | Pass |
| `openspec validate agenthub-final-demo-hardening --strict` | Pass |
| `pnpm check` | Pass |
| `pnpm test` | Pass (26 web tests, 113 API tests) |
| `git diff --check` | Pass |

### Remaining Governance Caveats

- P4-2 still needs a browser E2E click rehearsal; P4-0 verified the
  browser-facing API path but did not complete automated browser clicking.
- Pre-existing dirty files, including local app/test/doc changes and untracked
  screenshots, were left untouched unless directly required by P4-1.
- No app runtime behavior was changed for this task.

---

## P4-0 Full E2E Agent Execution Capability Audit

**Date:** 2026-05-19

### Modified Files

| File | Change |
|---|---|
| `docs/e2e-capability-audit.md` | Added the P4-0 execution capability audit, evidence IDs, limitations, and conclusions. |
| `docs/project-state.md` | Recorded the P4-0 verified real-agent, fallback, and follow-up paths. |
| `docs/change-log.md` | Recorded this audit. |

### What Changed

Documented a full E2E capability audit for the current AgentHub execution
pipeline. The audit used `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code` and
verified:

```text
requirement -> orchestrator plan -> Direct Start -> ClaudeCodeAdapter -> file mutation -> diff -> healthy preview -> mock deploy
```

It also verified the forced Codex failure plus ScriptedMockAdapter fallback path
and the same-session natural-language follow-up path for `把按钮文案改成 Sign in`.

### Audit Result

- Real agent path: Pass through browser-facing API endpoints.
- Fallback path: Pass.
- Follow-up path: Pass.
- Browser click automation: Not fully verified because Playwright is not
  installed and Chrome AppleScript control was blocked by a macOS Apple Events
  permission prompt.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (139 tests: 26 web + 113 API) |
| `git diff --check` | Pass |

---

## Frontend Chinese Copy and Typography Polish

**Date:** 2026-05-19

### Modified Files

| File | Change |
|---|---|
| `apps/web/src/app/globals.css` | Added a Chinese-first font stack and global line-height/text rendering tuning. |
| `apps/web/src/lib/date-format.ts` | Changed compact timestamps to Chinese month/day formatting. |
| `apps/web/src/lib/date-format.test.ts` | Updated timestamp expectations for Chinese date output. |
| `apps/web/src/components/workspace-shell.tsx` | Localized command-center shell labels, error copy, composer placeholder, demo pipeline, sidebar, chat, and timeline headings. |
| `apps/web/src/components/task-card-list.tsx` | Localized task statuses, run history, evidence chips, approval copy, and run controls while preserving existing callbacks. |
| `apps/web/src/components/preview-card.tsx` | Localized preview/artifact panel labels, action buttons, summary metadata, empty state, and iframe title. |
| `apps/web/src/components/diff-card.tsx` | Localized diff artifact labels, changed-file metadata, and expand/collapse control. |
| `apps/web/src/components/deploy-card.tsx` | Localized deploy-card labels and common status/title display. |
| `apps/web/src/components/health-card.tsx` | Localized backend health badge display. |
| Frontend component tests | Updated assertions for localized UI copy. |
| `docs/change-log.md` | Recorded this localization and typography pass. |

### What Changed

The frontend now presents the command-center chrome in Chinese while keeping
backend data, adapter names, file paths, URLs, and technical product terms such
as `Diff`, `Vite`, and `API` intact where they help the coding-agent demo.

Spacing and typography were adjusted lightly for Chinese readability:

- Chinese-first system font stack with `PingFang SC`, `Microsoft YaHei`, and
  Noto CJK fallbacks.
- Global body line height set to `1.5`.
- Timeline item gap tightened slightly for denser Chinese labels.
- User-facing date formatting now renders like `5月17日 02:06`.

### Validation

| Command | Result |
|---|---|
| `pnpm --filter @agenthub/web check` | Pass |
| `pnpm --filter @agenthub/web test` | Pass (26 web tests) |
| `pnpm check` | Pass |
| `pnpm test` | Pass (26 web tests, 113 API tests) |
| `git diff --check` | Pass |
| Browser render check | Pass: verified Chinese shell copy, Chinese-first font stack, viewport-height document, internal scroll regions, and composer visibility. Screenshot captured at `/tmp/agenthub-zh-ui-check.png`. |

### Known Limitations

- Task titles, session titles, adapter names, artifact titles, paths, URLs, and
  raw backend status strings can still be English when they come from persisted
  backend data or intentionally technical identifiers.

---

## P3 UI Sync Error Handling

**Date:** 2026-05-19

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/main.py` | Allowed both `http://127.0.0.1:3000` and `http://localhost:3000` as local frontend CORS origins. |
| `apps/api/tests/test_health.py` | Added CORS regression coverage for loopback and localhost frontend origins. |
| `apps/web/src/components/workspace-shell.tsx` | Added guarded client-side session sync error handling for messages, tasks, SSE task refresh, and UI actions. |
| `apps/web/src/components/workspace-shell.test.tsx` | Added a regression test that simulates browser fetch failures and verifies a user-facing backend sync warning is shown. |
| `docs/change-log.md` | Recorded the fix. |

### What Changed

Browser-side session refreshes now catch failed `fetch` calls instead of
leaking unhandled promise rejections. When the FastAPI backend is unreachable or
a session sync request fails, the UI keeps the existing page mounted and shows a
compact warning telling the user to check the backend URL.

The backend now accepts both common local browser origins, so opening the web UI
at `localhost:3000` or `127.0.0.1:3000` does not trip CORS while fetching from
the API on port 8000. Expected client sync failures no longer call
`console.error`, so they do not appear as Next/browser error stacks in the dev
terminal.

### Why

The browser reported unhandled rejections from `listSessionMessages` and
`listSessionTasks` when `fetch` failed while switching or loading sessions. The
failure should be visible and recoverable in the UI rather than surfacing as a
runtime error. In local development, the browser origin can also differ between
`localhost` and `127.0.0.1`; CORS must allow both forms.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (139 tests: 26 web + 113 API) |
| `git diff --check` | Pass |

---

## TaskRun Test Environment Isolation

**Date:** 2026-05-19

### Modified Files

| File | Change |
|---|---|
| `apps/api/tests/test_task_runs.py` | Isolated TaskRun API tests from inherited `AGENTHUB_DEFAULT_CODE_ADAPTER` shell state while preserving explicit Claude default-adapter coverage. |
| `docs/change-log.md` | Recorded the test isolation fix. |

### What Changed

The TaskRun tests now clear `AGENTHUB_DEFAULT_CODE_ADAPTER` in the shared
`client` fixture so default Codex assertions are stable even when a developer
starts tests from a shell configured for Claude Code demos. Tests that
intentionally verify `claude_code` selection still set the environment variable
explicitly with `monkeypatch`.

### Validation

| Command | Result |
|---|---|
| `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code pnpm test:api` | Pass (112 API tests) |
| `pnpm check` | Pass |
| `pnpm test` | Pass (25 web tests, 112 API tests) |
| `git diff --check` | Pass |

### Known Limitations

- This does not change runtime adapter selection behavior; it only stabilizes
  the test environment.

---

## Command-Center Layout Scrolling Fix

**Date:** 2026-05-18

### Modified Files

| File | Change |
|---|---|
| `apps/web/src/app/globals.css` | Locked `html` and `body` to viewport height and disabled document-level scrolling. |
| `apps/web/src/app/page.tsx` | Changed the page root to a viewport-height, overflow-hidden app shell. |
| `apps/web/src/app/page.test.tsx` | Updated the shell ownership assertion for the viewport-height layout. |
| `apps/web/src/components/workspace-shell.tsx` | Made the command-center shell, sidebar, center timeline, and composer use bounded flex/grid sizing with internal scroll regions. |
| `apps/web/src/components/preview-card.tsx` | Made the Artifact Detail panel a bounded internal scroll region. |
| `docs/change-log.md` | Recorded this layout scrolling fix. |

### What Changed

This pass keeps the command-center structure, state ownership, APIs, and demo
actions unchanged while fixing page-level scrolling:

- The app shell now uses viewport height with overflow hidden.
- The left session list scrolls inside the sidebar.
- The center chat/task timeline scrolls inside the center panel.
- The composer remains anchored at the bottom of the center workspace.
- The right Artifact Detail panel scrolls internally instead of stretching the
  document.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (25 web tests, 112 API tests) |
| `git diff --check` | Pass |
| Browser layout check | Pass: Chrome DevTools measurement showed document/body scroll heights equal viewport height, `html`/`body` overflow hidden, sidebar and center scroll regions overflowing internally, Artifact Panel using internal overflow, composer visible at bottom, and header visible. Screenshot captured at `/tmp/agenthub-scroll-check.png`. |

### Known Limitations

- This is a layout mechanics pass only; it does not redesign the task timeline
  or add full Artifact Panel tabs.

---

## P3 UI Final Visual QA Pass

**Date:** 2026-05-18

### Modified Files

| File | Change |
|---|---|
| `apps/web/src/components/task-card-list.tsx` | Increased task timeline readability with stronger selected artifact emphasis, larger task titles, denser dependency text, and retained vertical rail hierarchy. |
| `apps/web/src/components/preview-card.tsx` | Added Artifact Detail summary metadata for source task, task run, changed file, diff stats, preview health/status, and deploy status/provider. |
| `apps/web/src/components/workspace-shell.tsx` | De-emphasized low-value smoke sessions, reduced sidebar metadata repetition, and labeled the top pipeline as the demo flow. |
| `docs/change-log.md` | Recorded this final visual QA polish pass. |

### What Changed

This pass keeps the command-center structure and artifact state ownership
unchanged while tightening the visual presentation:

- Center task cards now have stronger title weight and selected-artifact focus.
- The left session list visually de-emphasizes repeated smoke sessions and only
  shows task-focus metadata for the active session.
- The right Artifact Detail panel now includes a source-task summary and
  artifact-specific stats:
  - Diff: file count, changed file, additions, deletions.
  - Preview: health, status, port, host.
  - Deploy: provider, status, environment, URL.
- The top pipeline now carries an explicit `Demo flow` label.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (25 web tests, 112 API tests) |
| `git diff --check` | Pass |
| Browser render check | Pass: captured `/tmp/agenthub-final-visual-qa.png` against the running local UI. |

### Known Limitations

- This does not add new Artifact Panel workflows or production-grade tabs.
- Mobile/responsive behavior is still a future pass.
- Smoke sessions remain selectable; they are only visually de-emphasized.

---

## P3 UI Redesign Phase 3: Timeline and Artifact Panel Polish

**Date:** 2026-05-18

### Modified Files

| File | Change |
|---|---|
| `apps/web/src/components/task-card-list.tsx` | Polished the center task list into a stronger vertical execution rail, improved task card spacing, and made fallback recovery read as a clearer Codex failed → fallback recovered → artifacts ready sequence. |
| `apps/web/src/components/task-card-list.test.tsx` | Updated the task marker assertion for the polished task label. |
| `apps/web/src/components/preview-card.tsx` | Strengthened Artifact Panel hierarchy with clearer detail header, segmented Diff/Preview/Deploy selector, selected artifact label, and stronger active tab state. |
| `apps/web/src/components/workspace-shell.tsx` | Reduced sidebar session-list noise and improved top pipeline status readability. |
| `docs/change-log.md` | Recorded this Phase 3 visual polish pass. |

### What Changed

Phase 3 keeps the Phase 2 data ownership and API behavior intact while polishing
visual hierarchy:

- The center task timeline now has a vertical rail with numbered task nodes.
- Task cards are lighter, more scannable, and less boxy.
- Run history is grouped with clearer run counts and recovery status.
- Fallback recovery now presents as:
  `Codex failed -> fallback recovered -> artifacts ready`.
- Sidebar sessions show less repeated metadata; only the selected session shows
  task focus detail.
- The top pipeline uses clearer status pills for completed, recovered, ready,
  running, and pending states.
- The Artifact Panel now reads as a detail panel with a clearer header, selected
  artifact type label, and segmented Diff / Preview / Deploy controls.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (25 web tests, 112 API tests) |
| `git diff --check` | Pass |
| Browser render check | Pass: captured `/tmp/agenthub-phase3-polish.png` against the existing local web/API services. |

### Known Limitations

- This is still not a full task execution-detail page.
- Artifact Panel controls are polished but remain a compact selector, not full
  production tabs.
- Mobile layout remains a later pass.

---

## P3 UI Redesign Phase 2: Artifact Panel Ownership

**Date:** 2026-05-18

### Modified Files

| File | Change |
|---|---|
| `apps/web/src/components/task-card-list.tsx` | Removed inline detailed Diff, Preview, and Deploy card rendering from the center timeline; task cards now show artifact summary chips and clearer recovery/run summaries. |
| `apps/web/src/components/preview-card.tsx` | Expanded the right panel into an Artifact Panel that can render selected diff, preview, or deployment details and expose existing preview/deploy actions. |
| `apps/web/src/components/workspace-shell.tsx` | Added frontend-only artifact selection state, default latest-artifact selection, and right-panel callbacks while preserving existing API calls and SSE refresh. |
| `apps/web/src/components/task-card-list.test.tsx` | Updated task timeline tests to assert summary chips, artifact selection, and artifact item handoff instead of inline detail cards. |
| `apps/web/src/components/preview-card.test.tsx` | Updated panel tests for selected artifact rendering. |
| `docs/change-log.md` | Recorded this Phase 2 frontend redesign slice. |

### What Changed

The center task timeline now stays focused on execution state. It no longer
duplicates detailed diff, preview, or deployment cards inline after each task.
Instead, each task card exposes only compact artifact evidence:

- Diff ready
- Changed file
- Preview health
- Deploy mock ready
- Recovered / fallback state

`TaskCardList` still uses the existing frontend API client functions to fetch
TaskRun artifacts, but it now converts them into frontend-only
`ArtifactPanelItem` objects and hands them to `WorkspaceShell`. `WorkspaceShell`
keeps the selected artifact id and defaults the panel to the latest available
artifact when no valid selection exists.

The right Artifact Panel now owns artifact detail rendering:

- Diff artifacts render through the existing `DiffCard`.
- Preview artifacts render through the existing `PreviewCard` plus iframe.
- Deployment artifacts render through the existing `DeployCard`.

Existing behavior is preserved:

- Start, Retry, Retry with ScriptedMockAdapter, Force Codex failure, Interrupt,
  Approve, and Deny remain in the center task cards.
- Preview refresh, open, stop, and mock deploy actions remain wired to the
  existing API callbacks through the right panel.
- No backend API changes were made.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (25 web tests, 112 API tests) |
| `git diff --check` | Pass |
| Browser render check | Pass: captured `/tmp/agenthub-phase2-artifact-panel.png`; right panel defaulted to the latest diff artifact while center timeline no longer rendered inline artifact detail cards. |

### Known Limitations

- This does not implement full Artifact Panel tabs or a task detail page.
- The panel still uses a compact selector rail; richer artifact browsing remains
  a later visual pass.
- The center task timeline still needs another pass for a denser vertical rail
  treatment once artifact ownership settles.

---

## P3 UI Visual QA Refinement Pass 1

**Date:** 2026-05-18

### Modified Files

| File | Change |
|---|---|
| `apps/web/src/app/page.tsx` | Removed the capped outer page card wrapper so the command center reads as a full workspace. |
| `apps/web/src/app/page.test.tsx` | Updated the shell ownership assertion for the full-screen page structure. |
| `apps/web/src/components/health-card.tsx` | Compressed Backend health into a single header badge with tooltip detail. |
| `apps/web/src/components/preview-card.tsx` | Refined the right Artifact Panel placeholder with tab-like labels, Safari-style preview chrome, dotted preview canvas, and a visible waiting card. |
| `apps/web/src/components/workspace-shell.tsx` | Tuned header hierarchy, pipeline treatment, sidebar selected state, central empty-state card, composer surface, and orchestrator plan styling. |
| `docs/change-log.md` | Recorded this visual QA refinement pass. |

### Visual QA Method

Used the three root-level reference PNGs (`1.png`, `2.png`, `3.png`) as the
available visual references because `docs/ui-redesign/assets` is absent in this
checkout. The main workspace target is `3.png`.

Captured the current UI with local Google Chrome headless:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new \
  --disable-gpu \
  --hide-scrollbars \
  --window-size=1440,1000 \
  --virtual-time-budget=5000 \
  --screenshot=/tmp/agenthub-main-workspace-task-refined.png \
  "http://127.0.0.1:3000?session=cb653482-c31a-48da-a8ee-31ed8cd367e3"
```

### Top Visual Mismatches Found

1. The command center still read as a large rounded page card instead of a
   full-screen workspace.
2. Header height and Backend health weight made the pipeline feel secondary.
3. Sidebar selected-session styling was too generic and did not match the
   reference's stronger active rail.
4. The right Artifact Panel placeholder lacked the preview-canvas quality of
   the reference.
5. Orchestrator/empty-state cards needed lighter hierarchy and softer borders.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (25 web tests, 112 API tests) |
| `git diff --check` | Pass |

### Known Limitations

- This pass intentionally does not implement execution-detail pages or full
  Artifact Panel tabs.
- Sidebar timestamps remain backed by the existing date formatter to avoid
  introducing hydration-sensitive relative-time rendering in this visual-only
  slice.

---

## P3 UI Redesign Slice 1: Command Center Shell

**Date:** 2026-05-18

### Modified Files

| File | Change |
|---|---|
| `apps/web/src/app/globals.css` | Added command-center design tokens for surfaces, primary indigo, muted text, borders, and code colors. |
| `apps/web/src/app/page.tsx` | Replaced the old page wrapper with a command-center container and moved health into the workspace shell header slot. |
| `apps/web/src/app/page.test.tsx` | Updated the home-page test to assert the shell owns the command-center page structure. |
| `apps/web/src/components/health-card.tsx` | Slimmed backend health from a large page card into a compact status surface for the header. |
| `apps/web/src/components/preview-card.tsx` | Reworked the right preview area into an Artifact Panel placeholder while preserving preview refresh/close and iframe behavior. |
| `apps/web/src/components/task-card-list.tsx` | Reframed tasks as a timeline with agent tags, run history, evidence chips, and preserved run/approval/preview/deploy controls. |
| `apps/web/src/components/task-card-list.test.tsx` | Updated assertions for the new timeline labels and split run-history markup. |
| `apps/web/src/components/ui/button.tsx` | Aligned button radius and primary color with the command-center token direction. |
| `apps/web/src/components/workspace-shell.tsx` | Rebuilt the frontend shell into a left sidebar, central IM chat/task timeline, top demo pipeline, and right artifact panel layout while preserving existing state ownership and API callbacks. |
| `docs/change-log.md` | Recorded this frontend-only redesign slice. |

### What Changed

Implemented the first real UI redesign slice from `docs/ui-redesign-spec.md`.
The previous page-level card layout was replaced with an IM-style Coding Agent
Command Center:

1. A fixed left workspace/session sidebar with workspace identity, session
   list, current-session status metadata, and full-width New Session action.
2. A central workspace containing the current session header, chat bubbles,
   orchestrator plan callout, task timeline container, and composer.
3. A right Artifact Panel placeholder that visually reserves the final
   diff/preview/deploy workspace without adding unsupported tabs.
4. A top demo pipeline showing the P0 loop:
   Requirement → Plan → Run → Diff → Preview → Deploy.

All existing frontend API calls and callbacks for Start, Retry, Force failure,
Fallback, Preview, Deploy, Approve, Deny, Interrupt, SSE refresh, and persisted
session/task/run/artifact fetching remain wired through the existing client
functions.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (25 web tests, 112 API tests) |
| `git diff --check` | Pass |
| Manual local render check | Pass: reused existing `127.0.0.1:8000` and `127.0.0.1:3000` services; verified rendered HTML includes the command-center title, demo pipeline stages, Backend status, New Session action, and Artifact Panel placeholder. |

### Known Limitations

- This slice intentionally does not implement full Artifact Panel tabs.
- Pipeline Preview and Deploy stages remain visual placeholders until the
  artifact-panel phase connects richer artifact state.
- `docs/ui-redesign/assets` was not present in this checkout; root-level
  untracked reference PNGs were left untouched.
- Screenshot capture was not produced because Playwright was not installed in
  the workspace; the manual check used the already-running local Next.js server
  and rendered HTML verification.

---

## Frontend Design Handoff Brief

**Date:** 2026-05-17

### Modified Files

| File | Change |
|---|---|
| `docs/frontend-design-brief.md` | Added a Gemini handoff brief documenting current frontend capabilities, UI surfaces, flows, architecture, API constraints, design problems, and implementation constraints. |
| `docs/change-log.md` | Recorded this documentation-only handoff task. |

No app code, backend code, frontend code, adapter code, tests, or dependencies
changed.

### What Changed

Created a documentation-only frontend design brief so Gemini can propose a
better AgentHub UI while staying inside verified P1 capabilities and current API
constraints.

The brief records:

- AgentHub's IM-style coding-agent product positioning.
- Verified P1 direct Codex and fallback capabilities.
- Current session, chat, task, run, diff, preview, panel, deploy, and health UI
  surfaces.
- Main success, fallback, and reload/recovery flows.
- Current Next.js frontend architecture, API client functions, data types, state
  fetching, and SSE usage.
- Backend/API constraints Gemini must not exceed.
- Objective current UI weaknesses and design requirements for Gemini.
- Implementation constraints for a future Codex frontend pass.

### Validation

| Command | Result |
|---|---|
| `git diff --check` | Pass |

### Known Limitations

- This task did not redesign or implement UI changes.
- Approval card UI remains outside the frozen P1 judge path and is documented
  as not present in the current frontend.

---

## P1-1: Direct UI Start TaskRun Dispatch Fix

**Date:** 2026-05-16

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/main.py` | +86/-3 lines |
| `apps/api/tests/test_task_runs.py` | +107 lines (3 new tests) |

### Modified Functions / Areas

- `apps/api/app/main.py`
  - `create_task_run_for_task` — changed from `def` to `async def`, added `BackgroundTasks` parameter, now dispatches `_background_execute_task_run` after creating the TaskRun.
  - `adapter_for_type` (new) — resolves `AgentAdapter` instance from adapter type string.
  - `execute_task_run` (new) — reusable helper that builds an `AgentRunRequest`, dispatches adapter execution via `run_adapter_event_stream`, and collects diff on completion.
  - `_background_execute_task_run` (new) — async background task that creates an independent DB session, resolves the adapter, calls `execute_task_run`, and normalizes unexpected failures to `failed` state with `ADAPTER_EXECUTION_ERROR`.

- `apps/api/tests/test_task_runs.py`
  - `test_direct_ui_start_dispatch_creates_queued_run_with_adapter_type` (new)
  - `test_direct_ui_start_background_execution_persists_events` (new)
  - `test_direct_ui_start_scripted_mock_background_execution_persists_events` (new)

### What Changed

`POST /tasks/{task_id}/runs` previously only created a `queued` TaskRun database row and returned immediately. No adapter execution was dispatched. The TaskRun remained stuck in `queued` state forever.

After this fix, the endpoint:
1. Creates the TaskRun in `queued` state (unchanged).
2. Dispatches `_background_execute_task_run` via FastAPI `BackgroundTasks`.
3. Returns the TaskRun response promptly.
4. The background task creates an independent DB session, resolves the appropriate adapter (`CodexAdapter` or `ScriptedMockAdapter`), and invokes the existing `execute_task_run` path.
5. TaskRunEvents are persisted, state transitions are applied, and diffs are collected on completion.
6. Unexpected adapter failures are normalized to `failed` state.

### Why

Direct UI Start was the only execution path that did not dispatch adapter execution. The working paths (`force-codex-failure` and `retry-with-fallback`) already called `run_adapter_event_stream` after creating the run. This fix unifies Direct UI Start with the existing dispatch pattern while using `BackgroundTasks` to avoid blocking the HTTP response on long-running adapter execution.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (77 tests: 21 web + 56 API) |
| `git diff --check` | Pass |

### Known Limitations

- Real Codex success was not tested because Codex CLI is not installed on this machine.
- This fix verifies Direct UI Start at the dispatch level (background execution is scheduled, adapter invocation is attempted, TaskRunEvents are persisted, failures are normalized).
- Full artifact generation (diff, preview, deploy) still depends on successful adapter execution against a real session worktree.
- The existing fallback-based P0 demo path (`Force Codex failure` → `Retry with ScriptedMockAdapter` → diff → preview → deploy) remains intact and unchanged.

---

## P1-2: Real Codex CLI Execution Verification

**Date:** 2026-05-16

### Modified Files

| File | Change |
|---|---|
| `apps/api/tests/test_codex_adapter.py` | +30 lines (4 new tests) |
| `apps/api/tests/test_task_runs.py` | +19/-2 lines (strengthened assertions) |

### Modified Functions / Areas

- `apps/api/tests/test_codex_adapter.py`
  - `test_codex_adapter_default_binary_is_macos_codex_app_path` (new) — verifies `DEFAULT_CODEX_BINARY` constant.
  - `test_codex_adapter_respects_codex_cli_path_env_var` (new) — verifies `CODEX_CLI_PATH` env var override.
  - `test_codex_adapter_falls_back_to_default_when_env_var_unset` (new) — verifies fallback to default when env var absent.
  - `test_codex_adapter_constructor_binary_override_takes_precedence` (new) — verifies explicit `codex_binary` parameter takes highest priority.

- `apps/api/tests/test_task_runs.py`
  - `test_direct_ui_start_background_execution_persists_events` — strengthened assertions: now verifies adapter lifecycle events exist beyond queued, and failed runs carry a `CODEX_*` error code with a non-null error message.

### What Changed

1. Added 4 new unit tests for `CodexAdapter` binary resolution (default path, env var override, constructor override, fallback precedence).
2. Strengthened the background dispatch integration test to assert that CodexAdapter produces recognizable `CODEX_*` error codes when execution fails.
3. Performed a real Codex CLI smoke test against the session worktree to verify the adapter path works end-to-end when Codex is available.

### Real Codex CLI Smoke Test Result

- **Codex CLI available:** `/Applications/Codex.app/Contents/Resources/codex` (v0.131.0-alpha.9) — **Yes.**
- **Codex CLI authenticated:** Logged in using ChatGPT — **Yes.**
- **Command shape:** Matches `docs/adapter-notes.md` exactly (`--ask-for-approval never exec --json --cd <worktree> --sandbox workspace-write "<instruction>"`).
- **JSONL events produced:** `thread.started`, `turn.started`, `item.started`, `item.completed` — **Yes.**
- **Exit code:** `0` — **Yes.**
- **File changes in worktree:** Not tested (read-only smoke). Codex searched and located `apps/demo/src/App.tsx` across multiple session worktree directories.

### Why

P1-1 fixed Direct UI Start dispatch but did not verify whether the real CodexAdapter CLI path actually works. P1-2 closes that verification gap: confirms Codex CLI is present and executable, confirms its command shape matches the documented spec, confirms it produces JSONL lifecycle events inside the session worktree, and adds CI-safe tests that do not depend on real Codex.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (81 tests: 21 web + 60 API) |
| `git diff --check` | Pass |
| Real Codex read-only smoke (manual) | Pass (JSONL events, worktree navigation confirmed) |
| Real Codex write-and-diff smoke (manual) | Pass (see below) |

### Real Codex Write-and-Diff Smoke Test (2026-05-16)

**Outcome A: Real write-and-diff through Direct UI Start verified (API-level, not UI-level).**

A new session worktree was created. A task was assigned to the frontend agent (CodexAdapter). CodexAdapter was invoked with instruction: `"In apps/demo/src/App.tsx, find the element with data-agenthub-target='primary-action-button' and change only its text to 'Codex Verified'."`

Results:
- **26 TaskRunEvents persisted** including `thread.started`, `turn.started`, `item.started`/`item.completed` (command_execution and file_change), `turn.completed`.
- **Codex modified the file:** `apps/demo/src/App.tsx` — replaced button text from `"Continue"` to `"Codex Verified"`.
- **TaskRun state:** `completed`.
- **Diff artifact collected:** `artifact.diff.ready` event persisted with `artifactId` and `diffId`. Git diff confirmed 1 file changed, 1 insertion, 1 deletion.
- **Transient stderr noise:** Codex emits `"Reconnecting..."` messages as `{"type":"error"}` JSONL events during execution; these are mapped to `CODEX_EXIT_ERROR` error events but do not prevent the run from completing when `turn.completed` follows. This is a known Codex CLI behavior, not an adapter bug.

The verification was performed through direct Python invocation of `CodexAdapter` + `run_adapter_event_stream` + `collect_task_run_diff` rather than through the HTTP endpoint, because `BackgroundTasks` + synchronous `process.communicate()` in CodexAdapter blocks the FastAPI event loop, preventing concurrent request handling during long Codex runs. This event-loop blocking is a pre-existing limitation that also affects the `force-codex-failure` and `retry-with-fallback` endpoints.

### Known Limitations

- Real Codex CLI **is available** (v0.131.0-alpha.9, logged in via ChatGPT) in the current validation environment. This is environment-dependent.
- **Real write-and-diff verified** (API-level): Codex modified `apps/demo/src/App.tsx`, changed file confirmed by `git diff`, diff artifact collected by backend service.
- Direct UI Start endpoint dispatches real Codex execution in background. `process.communicate()` was blocking the event loop; this is resolved in P1-3.
- `FileNotFoundError` from missing worktree vs missing Codex binary both map to `CODEX_NOT_FOUND`. This pre-existing ambiguity is not addressed in P1-2.
- Transient Codex `"Reconnecting..."` JSONL events are mapped to `CODEX_EXIT_ERROR` error events but do not prevent successful completion when followed by `turn.completed`.
- The existing fallback-based P0 demo path remains intact and unchanged.

---

## P1-3: Non-Blocking Subprocess Execution Fix

**Date:** 2026-05-16

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/codex_adapter.py` | +2 lines: added `import asyncio`, changed `communicate()` to `await asyncio.to_thread(communicate)` |
| `apps/api/tests/test_codex_adapter.py` | +49 lines: `DelayedFakeCodexProcess`, non-blocking test, `_drain_events` helper |
| `docs/change-log.md` | P1-3 entry |

### Modified Functions / Areas

- `apps/api/app/codex_adapter.py`
  - `streamEvents` (line 161): replaced synchronous `state.process.communicate()` with `await asyncio.to_thread(state.process.communicate)`.
  - Added `import asyncio`.

- `apps/api/tests/test_codex_adapter.py`
  - `DelayedFakeCodexProcess` (new) — fake process that sleeps in `communicate()` to simulate a long-running subprocess.
  - `test_codex_adapter_does_not_block_event_loop_during_communicate` (new) — proves a concurrent `asyncio.sleep` completes promptly while the adapter's `communicate()` runs in the thread pool.
  - `_drain_events` (new) — helper to collect events from an async generator.

### What Changed

The blocking `process.communicate()` call inside `CodexAdapter.streamEvents()` was wrapped in `asyncio.to_thread()`. This moves the blocking subprocess wait to a worker thread, keeping the asyncio event loop free to serve other requests (health checks, SSE, task queries).

### Why

P1-2 confirmed that `BackgroundTasks` + synchronous `process.communicate()` blocks the FastAPI asyncio event loop for the entire duration of Codex execution (30-90s). During this time, no other HTTP requests could be served — health checks, SSE event delivery, and task queries would all hang. `asyncio.to_thread()` isolates the blocking operation in a thread pool, allowing the event loop to remain responsive.

### HTTP Direct UI Start Verification

ScriptedMockAdapter was tested through the full HTTP path:

| Step | Result |
|---|---|
| `POST /tasks/{task_id}/runs` | Returned 201 with queued TaskRun |
| Health check during execution | `ok` in ~5ms throughout |
| TaskRun final state | `completed` |
| Diff artifact | 1 file changed (`apps/demo/src/App.tsx`), 11 additions, 4 deletions |

CodexAdapter ran via direct `_background_execute_task_run` invocation:
- 9 TaskRunEvents persisted (queued → streaming events → error events)
- TaskRun finalized as `failed` with `CODEX_USAGE_LIMIT` (account hit usage limit)
- Event loop remained free during Codex subprocess execution

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (82 tests: 21 web + 61 API) |
| `git diff --check` | Pass |
| HTTP Direct UI Start + ScriptedMockAdapter | Pass (diff collected) |
| Direct `_background_execute_task_run` + CodexAdapter | Pass (events persisted, usage limit normalized) |

### Known Limitations

- Events are still persisted in batch after `communicate()` returns, not streamed in real-time during Codex execution. Real-time per-line event streaming would require replacing `communicate()` with an async readline loop — deferred.
- Real Codex hit a usage limit during P1-3 verification, so real Codex success through HTTP was not verified. The normalized failure path (CODEX_USAGE_LIMIT) was verified.
- `asyncio.to_thread` is Python 3.9+; the project requires Python 3.9+.
- The existing fallback-based P0 demo path remains intact and unchanged.

---

## P1-4: Incremental Codex JSONL Streaming

**Date:** 2026-05-16

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/codex_adapter.py` | Replaced whole-process stdout collection with incremental stdout JSONL line streaming and concurrent stderr capture. |
| `apps/api/tests/test_codex_adapter.py` | Added streaming process fakes and tests for incremental event yield, pre-completion persistence, and event-loop responsiveness. |
| `docs/change-log.md` | Added this P1-4 entry. |

### Modified Functions / Areas

- `apps/api/app/codex_adapter.py`
  - `CodexProcess` — now exposes `stdout_lines()`, `wait()`, and `stderr_text()` instead of a whole-process `communicate()` contract.
  - `SubprocessCodexProcess.stdout_lines` — reads stdout one line at a time with `asyncio.to_thread(stdout.readline)`.
  - `SubprocessCodexProcess.stderr_text` — drains stderr concurrently while stdout is streamed.
  - `CodexAdapter.streamEvents` — parses each complete JSONL stdout line as soon as it is available, yields mapped `AgentEvent`s immediately, then handles stderr and exit status after the process completes.
  - `_finish_process` — waits for process completion and returns the normalized stderr excerpt.

- `apps/api/tests/test_codex_adapter.py`
  - `StepwiseFakeCodexProcess` — fake process that pauses after the first JSONL line so tests can prove events are yielded before process completion.
  - `test_codex_adapter_streams_jsonl_before_process_completion` — verifies the first mapped event is yielded before the fake process has waited/exited.
  - `test_codex_streamed_events_persist_before_process_completion` — verifies `run_adapter_event_stream` persists the first TaskRunEvent before process completion.
  - `test_codex_adapter_does_not_block_event_loop_while_waiting_for_jsonl` — verifies unrelated async tasks can run while Codex stdout is waiting.

### What Changed

Before P1-4, `CodexAdapter.streamEvents()` used:

```python
stdout, stderr = await asyncio.to_thread(state.process.communicate)
```

That kept the FastAPI event loop responsive, but it still collected all stdout
after Codex exited. TaskRunEvents were parsed and persisted in a batch at the
end of the subprocess run.

After P1-4, the adapter streams stdout incrementally:

1. Start stderr capture concurrently.
2. Await each stdout JSONL line as it becomes available.
3. Parse the line immediately.
4. Map it to an `AgentEvent`.
5. Yield the event immediately to `run_adapter_event_stream`.
6. Let `run_adapter_event_stream` persist the event before SSE delivery.
7. After stdout closes, wait for process completion and handle stderr/exit code.

### Why

P1-3 solved event-loop blocking, but not realtime visibility. The UI/SSE path
could remain responsive, but it could not observe Codex progress until the
process finished. P1-4 makes Codex JSONL stdout a true stream so persisted
TaskRunEvents can appear while Codex is still running.

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_codex_adapter.py` | Pass (14 tests) |
| `pnpm check` | Pass |
| `pnpm test` | Pass (84 tests: 21 web + 63 API) |
| `git diff --check` | Pass |

### Manual Verification Result

HTTP Direct Start with real Codex was attempted against a new planned frontend
task:

- Session: `62919139-e820-47d0-9557-ae7653740082`
- TaskRun: `360e7781-a3cf-4692-bf7f-67f5447c0f36`
- Initial state: `queued`
- Observed state during execution: `streaming`
- Health checks during execution: `ok` in 1-9ms
- Persisted event replay lines: 12
- Final state: `failed`
- Normalized error code: `CODEX_EXIT_ERROR`
- Normalized error message:
  `Reconnecting... 2/5 (timeout waiting for child process to exit)`
- Diff artifact: not produced

This verifies that HTTP Direct Start no longer remains stuck at `queued`, that
real Codex execution is attempted, that events/state become visible while Codex
is running, and that the API remains responsive. It does **not** verify HTTP
Direct Start -> real Codex file mutation -> diff artifact, because the real
Codex process failed before producing a successful file change.

### Known Limitations

- The adapter now streams Codex stdout incrementally, but real HTTP write-and-diff verification still depends on local Codex quota/auth/process stability.
- Stderr is captured concurrently and attached to final fallback/error handling, but mapped intermediate events may not include final stderr because they are emitted before process completion.
- Preview/deploy through a real Codex success path remains unverified unless the manual HTTP run reaches a successful file mutation and diff artifact.
- The existing fallback-based P0 demo path remains intact and must stay available.

---

## P1-5: Codex Reconnect Handling and HTTP Direct Start Diagnosis

**Date:** 2026-05-16

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/codex_adapter.py` | Treat Codex reconnect JSON events as informational progress, preserve specific Codex error codes when a later generic `turn.failed` arrives. |
| `apps/api/app/main.py` | Generate a bounded demo-file instruction for planned frontend login-page tasks instead of sending the broad task title to Codex. |
| `apps/api/tests/test_codex_adapter.py` | Added reconnect and specific-error preservation tests. |
| `apps/api/tests/test_task_runs.py` | Added a test for bounded frontend login-page run instructions. |
| `docs/change-log.md` | Added this P1-5 entry. |

### Modified Functions / Areas

- `apps/api/app/codex_adapter.py`
  - `_map_codex_json_event` — maps `Reconnecting... N/5 (timeout waiting for child process to exit)` JSON events to `message.delta` progress events instead of terminal errors.
  - `_is_reconnecting_error` (new) — detects reconnect progress messages from Codex JSON stdout.
  - `_is_generic_failure_event` (new) — detects generic `CODEX_EXIT_ERROR` / `Codex run failed.` events.
  - `CodexAdapter.streamEvents` — skips a later generic `turn.failed` error when a more specific Codex error was already emitted, so actionable errors such as `CODEX_USAGE_LIMIT` are not overwritten.

- `apps/api/app/main.py`
  - `instruction_for_task` (new) — converts the planned frontend login-page task into a small, explicit instruction targeting `apps/demo/src/App.tsx` and `data-agenthub-target="login-page-slot"`.
  - `agent_run_request_for` — now uses `instruction_for_task(task)` instead of the broad task title.

### What Changed

P1-4 showed HTTP Direct Start failed with:

```text
CODEX_EXIT_ERROR: Reconnecting... 2/5 (timeout waiting for child process to exit)
```

P1-5 found that this was an adapter mapping bug. Running the same Codex CLI
command manually showed that Codex can emit `Reconnecting... 5/5`, then log
`falling back to HTTP`, continue emitting normal item events, modify files, and
finish with `turn.completed`. The reconnect JSON event is therefore not
necessarily terminal.

The adapter now treats reconnect JSON events as progress messages. Real failure
comes from the process exit code, a non-reconnect Codex error, or a specific
Codex failure such as usage limit or authentication failure.

P1-5 also narrowed the HTTP Direct Start instruction. Previously the backend
sent only the task title, `Build the Vite React login page`, so Codex treated
the request like a broad OpenSpec implementation task and read large OpenSpec
files before touching the demo app. The backend now sends a bounded,
file-targeted instruction for the deterministic demo login-page task.

### Why

The direct Python write-and-diff smoke succeeded because it used a narrow file
edit instruction. HTTP Direct Start used a broad task title and also treated
Codex reconnect progress as terminal. Those differences made the HTTP path fail
before mutation/diff despite the CLI being capable of real file edits in the
same session worktree.

### Validation

| Command | Result |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_codex_adapter.py tests/test_task_runs.py` | Pass (29 tests) |
| `pnpm check` | Pass |
| `pnpm test` | Pass (89 tests: 21 web + 68 API) |
| `git diff --check` | Pass |

### Manual Verification Result

HTTP Direct Start with real Codex was attempted after the reconnect-mapping and
bounded-instruction fixes:

- Session: `1eac3075-ac06-4504-94f9-76dd4b17ad9d`
- TaskRun: `dac99e3d-2bb5-4f93-a31d-da9480c04ae6`
- Initial state: `queued`
- Observed state during execution: `streaming`
- Health checks during execution: `ok` in 1-5ms
- Persisted event replay lines: 27
- Final state: `failed`
- Final normalized error code: `CODEX_EXIT_ERROR`
- Final normalized error message: `Codex run failed.`
- Diff artifact: not produced

Inspecting persisted events showed the useful underlying error before the final
generic failure:

```text
CODEX_USAGE_LIMIT: You've hit your usage limit. To get more access now, send a request to your admin or try again at 10:02 PM.
```

After P1-5, tests ensure this specific `CODEX_USAGE_LIMIT` error is preserved
instead of being overwritten by a later generic `turn.failed` event.

The fallback path was also exercised in the same session after Codex failed:

- Retry with ScriptedMockAdapter: completed
- Diff artifact: produced
- Changed file: `apps/demo/src/App.tsx`
- Diff stats: 1 file changed, 11 additions, 4 deletions
- Preview: healthy at `http://127.0.0.1:64508`
- Deployment: mock provider, status `ready`

### Known Limitations

- HTTP Direct Start with real Codex file mutation and diff collection was not
  verified because the local Codex account hit a usage limit during the HTTP
  run.
- Manual CLI verification confirmed reconnect events can be followed by
  fallback-to-HTTP, file mutation, `git diff`, and `turn.completed`; the adapter
  now handles that event shape.
- Preview/deploy through a real Codex success path remains unverified until
  Codex quota permits a successful HTTP Direct Start mutation.
- The existing fallback-based P0 demo path remains intact and verified.

---

## P1-6: HTTP Direct Start Real Codex End-to-End Rehearsal

**Date:** 2026-05-16

### Modified Files

| File | Change |
|---|---|
| `docs/change-log.md` | Added this P1-6 rehearsal result. |

### What Changed

No product code was changed for P1-6. This was a focused rehearsal after the
P1-5 reconnect/error-handling fixes and after Codex usage limits reset.

### Manual Verification Result

HTTP Direct Start with real Codex was rehearsed through the backend API path
used by the UI:

- Session: `a0b51d27-0473-44f3-b079-bbb02fdf00bb`
- User request:
  `@orchestrator build a login page for the demo app`
- Codex-backed task: `f9e982c3-df76-4740-b38c-e14e8cb3497c`
- TaskRun: `fa23fb4a-6506-4b0e-a608-3197356d0628`
- Initial state: `queued`
- Observed state during execution: `streaming`
- Final state: `completed`
- Error code/message: none
- Persisted event replay lines: 84
- Health checks during execution: `ok` in 1-5ms
- Worktree:
  `.worktrees/98449267-914c-4f26-82b5-e1d176d64f91/a0b51d27-0473-44f3-b079-bbb02fdf00bb`

Real Codex changed:

```text
apps/demo/src/App.tsx
```

The collected diff artifact was persisted:

- Artifact ID: `782e16f4-36b5-46f3-86cf-42c3fb6119e9`
- Diff ID: `5df0273d-f9fc-46b3-bbfa-242d5d185667`
- Changed files: `["apps/demo/src/App.tsx"]`
- Stats: 1 file changed, 20 additions, 4 deletions

The file diff replaced the deterministic login-page slot copy with a compact
login form containing email and password fields. This verifies:

```text
HTTP Direct Start -> real Codex file mutation -> diff artifact
```

### Fallback Verification

The P1-6 direct Codex run completed, so fallback was not needed in this
rehearsal. P1-5 verified the fallback path immediately before this run:

- Retry with ScriptedMockAdapter completed.
- Diff artifact was produced for `apps/demo/src/App.tsx`.
- Preview became healthy.
- Mock deployment card was created.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (89 tests: 21 web + 68 API) |
| `git diff --check` | Pass |

### Known Limitations

- Preview and mock deploy were not triggered from the real Codex success run in
  this rehearsal. The verified P1-6 scope was real Codex mutation plus diff
  artifact.
- The Codex run took about 163 seconds and emitted reconnect progress before
  completion, so demos should still keep the ScriptedMockAdapter fallback
  available.

---

## P1-7: Real Codex Preview and Mock Deploy Rehearsal

**Date:** 2026-05-16

### Modified Files

| File | Change |
|---|---|
| `docs/change-log.md` | Added this P1-7 rehearsal result. |

### Modified Functions or Areas

No product code changed. This rehearsal used the existing preview and deploy
APIs after the successful real Codex Direct Start run from P1-6.

### What Changed

No backend, frontend, adapter, preview, or deploy implementation was changed.
The only change was documenting the focused verification result for continuing
from a real Codex diff artifact to preview and mock deployment.

### Why

P1-6 verified:

```text
HTTP Direct Start -> real Codex file mutation -> diff artifact
```

P1-7 verifies whether the existing artifact path can continue from that same
real Codex TaskRun to:

```text
healthy Vite preview -> mock deploy card
```

### Manual Verification Result

The rehearsal reused the successful real Codex Direct Start run from P1-6:

- Session: `a0b51d27-0473-44f3-b079-bbb02fdf00bb`
- Codex-backed task: `f9e982c3-df76-4740-b38c-e14e8cb3497c`
- TaskRun: `fa23fb4a-6506-4b0e-a608-3197356d0628`
- Changed file from real Codex: `apps/demo/src/App.tsx`
- Diff artifact ID: `782e16f4-36b5-46f3-86cf-42c3fb6119e9`
- Diff ID: `5df0273d-f9fc-46b3-bbfa-242d5d185667`

The existing preview API was called for that TaskRun:

```text
POST /task-runs/fa23fb4a-6506-4b0e-a608-3197356d0628/preview
```

Preview result:

- Preview ID: `877daf34-cabe-4ddf-8726-94677ba18831`
- Preview artifact ID: `a14d9194-b198-4d17-a152-79e71cc0590a`
- URL: `http://127.0.0.1:53089`
- Port: `53089`
- Command: `pnpm dev --host 127.0.0.1 --port 53089`
- Process ID: `32754`
- Health status: `healthy`
- Artifact status: `ready`

The preview URL served the Vite React HTML shell successfully.

The existing mock deploy API was called for the healthy preview:

```text
POST /previews/877daf34-cabe-4ddf-8726-94677ba18831/deploy
```

Deployment result:

- Deployment ID: `9ba427d9-1ea8-454a-8890-e243075fcec7`
- Deployment artifact ID: `a623f388-8891-4282-9f7d-6b0074a9152c`
- Provider: `mock`
- Environment: `preview`
- Status: `ready`
- Commit SHA/worktree ref:
  `9777b992c46ebb52150c19131410c3dfea54c268+worktree`
- URL:
  `https://mock.agenthub.local/deployments/9ba427d9-1ea8-454a-8890-e243075fcec7`
- Deploy log URI:
  `mock://deployments/9ba427d9-1ea8-454a-8890-e243075fcec7/logs`

This verifies:

```text
HTTP Direct Start -> real Codex file mutation -> diff artifact -> healthy Vite preview -> mock deploy
```

The preview and deployment records are backend-created and persisted. The
frontend already reads these persisted preview/deployment APIs, but this
P1-7 rehearsal used the backend API path directly rather than clicking through
the browser UI.

### Fallback Verification

The fallback path was not needed for this rehearsal because the real Codex run
from P1-6 had already completed and produced a diff. The fallback-based P0 demo
path remains covered by the existing tests and prior P1-5/P1-6 verification:

```text
forced Codex failure -> ScriptedMockAdapter fallback -> diff -> preview -> mock deploy
```

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (89 tests: 21 web + 68 API) |
| `git diff --check` | Pass |

### Known Limitations

- This P1-7 rehearsal triggered preview and deploy through the existing backend
  APIs, not by clicking the browser UI.
- Real Codex execution remains dependent on local Codex quota and CLI stability;
  keep the ScriptedMockAdapter fallback available for demos.

---

## Codex Workflow Documentation

**Date:** 2026-05-17

### Modified Files

| File | Change |
|---|---|
| `AGENTS.md` | Added project-wide mandatory Codex rules. |
| `docs/codex-task-template.md` | Added a reusable short-prompt workflow template. |
| `docs/project-state.md` | Added stable P0/P1 state, P1-6/P1-7 evidence, and the P1-8 UI gap. |
| `docs/change-log.md` | Recorded this documentation-only workflow change. |

### What Changed

Moved repeated long-prompt context into stable project documents:

- `AGENTS.md` now names mandatory rules for future Codex work, including
  minimal task scope, honest verification claims, preserving the fallback-based
  P0 demo, avoiding forbidden non-P0/P1 features unless explicitly requested,
  updating the change log when engineering files change, and not committing or
  pushing unless explicitly instructed.
- `docs/codex-task-template.md` defines the standard read/check/diagnose/edit
  workflow and final-response checklist.
- `docs/project-state.md` records current P0/P1 state, including P1-6 real
  Codex direct-start diff verification, P1-7 backend API preview/deploy
  verification, and the concrete P1-7 evidence IDs.

### Why

Future Codex prompts can now reference these documents instead of repeating the
same long context, constraints, and wrap-up requirements each time.

### Scope

Documentation only. No app code, backend code, tests, dependencies, or runtime
behavior were changed.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Not run; documentation-only change. |
| `pnpm test` | Not run; documentation-only change. |
| `git diff --check` | Pass |

### Known Limitations

- This change does not verify any app behavior.

---

## P1-8: Browser UI Preview and Mock Deploy Rehearsal

**Date:** 2026-05-17

### Modified Files

| File | Change |
|---|---|
| `apps/web/src/app/page.tsx` | Let `WorkspaceShell` use the full page width so its own right-side preview panel does not compete with the health card. |
| `apps/web/src/app/page.test.tsx` | Added a focused page layout contract test. |
| `docs/project-state.md` | Updated P1-8 from a known gap to verified browser UI state. |
| `docs/change-log.md` | Recorded this P1-8 continuation. |

### Modified Functions or Areas

- `apps/web/src/app/page.tsx`
  - Changed the page content wrapper from `grid gap-4 md:grid-cols-[1fr_360px]`
    to `grid gap-4`.
  - `WorkspaceShell` already owns its internal workspace/session/task/preview
    columns, so the health card now stacks below the full-width workspace shell.

### What Changed

The browser UI rehearsal showed that the outer page constrained
`WorkspaceShell` beside the health card while `WorkspaceShell` also rendered an
internal right-side preview panel. That made the task column cramped and made
the preview/deploy controls difficult to operate at desktop width.

The fix is intentionally small: it changes only the outer page layout. Existing
task cards, diff cards, preview cards, deploy cards, API clients, backend
preview/deploy APIs, adapters, and artifact persistence are unchanged.

### Why

P1-7 verified the post-diff path through backend APIs. P1-8 verifies that a user
can operate the same post-diff path through the browser UI after a real Codex
Direct Start run has produced a real diff artifact.

### Manual Browser Verification Result

The browser UI was opened at:

```text
http://127.0.0.1:3000/?session=a0b51d27-0473-44f3-b079-bbb02fdf00bb
```

The selected session reused the successful real Codex Direct Start run from
P1-6/P1-7:

- Session: `a0b51d27-0473-44f3-b079-bbb02fdf00bb`
- Codex-backed task: `f9e982c3-df76-4740-b38c-e14e8cb3497c`
- TaskRun: `fa23fb4a-6506-4b0e-a608-3197356d0628`
- Changed file from real Codex: `apps/demo/src/App.tsx`
- Diff artifact ID: `782e16f4-36b5-46f3-86cf-42c3fb6119e9`
- Diff ID: `5df0273d-f9fc-46b3-bbfa-242d5d185667`

Browser UI checks:

- The persisted diff card appeared for the real Codex TaskRun.
- The diff card expanded and changed-file details remained visible.
- The UI `Start preview` button created a new healthy Vite preview.
- The UI `Open preview` button opened the right-side iframe panel.
- The iframe loaded the Vite React demo from the session worktree.
- The UI `Create deploy card` button created a new persisted mock deploy card.
- After page reload, the diff, preview cards, and mock deploy cards remained
  visible.

Fresh UI-created preview:

- Preview ID: `810324d7-2ba9-47e6-b676-7391e87cb131`
- Preview artifact ID: `927f3b23-2bea-43a4-a420-13432ae39064`
- URL: `http://127.0.0.1:64067`
- Port: `64067`
- Health status: `healthy`
- Artifact status: `ready`

Fresh UI-created deployment:

- Deployment ID: `58c7812c-31f8-49ee-8b08-28d38264cd87`
- Deployment artifact ID: `da95fe77-167e-4df2-9ef4-e2d450fa3bb1`
- Provider: `mock`
- Environment: `preview`
- Status: `ready`
- URL:
  `https://mock.agenthub.local/deployments/58c7812c-31f8-49ee-8b08-28d38264cd87`

This verifies through the browser UI:

```text
real Codex Direct Start -> diff card -> Start preview -> preview iframe -> Create deploy card
```

### Fallback Verification

No fallback was needed during P1-8 because it reused the successful real Codex
TaskRun from P1-6. The fallback-based P0 demo remains covered by existing tests
and prior verification:

```text
forced Codex failure -> ScriptedMockAdapter fallback -> diff -> preview -> mock deploy
```

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (90 tests: 22 web + 68 API) |
| `git diff --check` | Pass |

---

## Minimal Claude Code Adapter

**Date:** 2026-05-17

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/claude_code_adapter.py` | Added a minimal Claude Code adapter using subprocess cwd isolation and stream-json parsing. |
| `apps/api/app/main.py` | Added `claude_code` adapter dispatch support. |
| `apps/api/app/guardrails.py` | Allowed bounded Claude CLI commands through the existing command guardrail path. |
| `apps/api/tests/test_claude_code_adapter.py` | Added fake-runner tests for command shape, event streaming, persistence, and normalized failures. |
| `apps/api/tests/test_guardrails.py` | Added command-policy coverage for the Claude Code CLI shape. |
| `docs/project-state.md` | Recorded the current Claude Code adapter status and limitations. |
| `docs/change-log.md` | Recorded this implementation. |

### Diagnosis

The existing adapter contract and `run_adapter_event_stream` persistence flow
already support another local CLI adapter. The missing pieces were a
Claude-specific subprocess runner, stream-json event mapper, error-code
normalization, command guardrail allowance, and dispatch support for
`adapterType: claude_code`.

### What Changed

Added `ClaudeCodeAdapter` as a sibling of `CodexAdapter`. It builds the
documented command shape:

```bash
claude --print --verbose --output-format stream-json --include-partial-messages \
  --permission-mode dontAsk --allowedTools Read,Edit,MultiEdit \
  --no-session-persistence --max-budget-usd 1.00 "<instruction>"
```

The process is started with `cwd=<session_worktree_path>`. The adapter parses
stdout incrementally and maps Claude Code events to normalized `task.state`,
`message.delta`, `completed`, and `error` events. It normalizes missing CLI,
auth required, usage limit, interruption, timeout, parse error, guardrail
blocking, and non-zero exit failures.

No frontend UI, provider marketplace, deployment behavior, Codex behavior, or
ScriptedMockAdapter fallback behavior changed.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (133 tests: 25 web + 108 API) |
| `git diff --check` | Pass |

### Known Limitations

- Tests use fake process runners only; CI and local tests do not call real
  Claude Code.
- No real Claude mutation was run or claimed.
- Real Claude `stream-json` output, permission behavior, auth failure text, and
  usage-limit text still need an explicitly approved smoke before demo use.

---

## P2-7: Explicit ClaudeCodeAdapter Smoke Rehearsal

**Date:** 2026-05-18

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/claude_code_adapter.py` | Added the required `--verbose` flag for real Claude `--output-format stream-json` execution and mapped real `stream_event` text deltas. |
| `apps/api/app/guardrails.py` | Required `--verbose` in the bounded Claude Code command allowlist shape. |
| `apps/api/tests/test_claude_code_adapter.py` | Updated command-shape coverage for `--verbose` and added stream-event text/thinking delta coverage. |
| `apps/api/tests/test_guardrails.py` | Updated command-policy coverage for `--verbose`. |
| `docs/project-state.md` | Recorded the real Claude smoke evidence and limitations. |
| `docs/change-log.md` | Recorded this P2-7 rehearsal. |

### Diagnosis

The fake-runner adapter implementation was structurally correct, but the first
real Claude Code smoke revealed one concrete CLI requirement:

```text
Error: When using --print, --output-format=stream-json requires --verbose
```

That failure happened before any file mutation. The adapter and guardrail
command shape were updated with the smallest possible fix: add `--verbose`.
The successful smoke also showed that verbose output includes low-level
`stream_event` records, including thinking deltas, so the adapter now maps text
deltas and filters thinking deltas instead of preserving them as raw messages.

### Smoke Method

Created a detached disposable worktree:

```text
/Users/luotianhang/Desktop/agenthub/.worktrees/claude-smoke-96d46af7-dc74-4d71-a062-c9be42cd1332
```

Then ran one tiny real `ClaudeCodeAdapter` instruction through the backend
adapter flow:

```text
change only the primary action button text in apps/demo/src/App.tsx to "Claude smoke"
```

No broad prompt, dependency install, browser UI flow, or repeated mutation
loop was run.

### Result

First attempt:

- TaskRun: `c66f1f86-2407-487a-b18f-cf01abd3a7f3`
- Final state: `failed`
- Error code: `CLAUDE_CODE_EXIT_ERROR`
- Error message:
  `Error: When using --print, --output-format=stream-json requires --verbose`
- File mutation: none

Second attempt after the `--verbose` fix:

- Session: `4cf32311-1a9b-4eda-9ec3-ab0d010691fc`
- Task: `a5557a9a-99de-4962-9d25-86ed548ea7ca`
- TaskRun: `095ae634-c188-4ffc-a502-53a500d20e14`
- AdapterRun: `claude-code-94cc6074-f15d-4290-b050-c2383363f44d`
- Final state: `completed`
- Persisted adapter events: 337
- Diff artifact: `95bb1d0b-12a3-4a0e-be3e-c07cf1bf79d4`
- Diff: `9f69bc39-6b32-42ca-8a86-cf9fbfa62343`
- Changed file: `apps/demo/src/App.tsx`
- Diff stats: 1 file changed, 1 addition, 1 deletion

Direct git diff in the disposable worktree showed only:

```diff
-            Continue
+            Claude smoke
```

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (134 tests: 25 web + 109 API) |
| `git diff --check` | Pass |

### Known Limitations

- This was a direct backend smoke, not full browser UI execution.
- Only one tiny real Claude mutation was verified.
- Claude `stream-json` emits verbose low-level `stream_event` records; text
  deltas and thinking-delta filtering are covered, but broader stream event
  shapes remain unverified.
- Real auth-failure and usage-limit outputs remain unverified.

---

## P2-8: Claude Code Direct-Start Selection

**Date:** 2026-05-18

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/task_runs.py` | Added `AGENTHUB_DEFAULT_CODE_ADAPTER` selection for codex-backed frontend/backend coding agents. |
| `apps/api/tests/test_task_runs.py` | Added coverage for Claude default selection, explicit adapter preservation, non-code adapter preservation, and invalid env values. |
| `docs/project-state.md` | Recorded the P2-8 selection behavior and current limits. |
| `docs/change-log.md` | Recorded this P2-8 implementation. |

### Diagnosis

Normal Direct Start creates a TaskRun through `create_task_run()`, which used
the assigned agent's stored `adapter_type` unless an endpoint passed an
explicit adapter. The seeded frontend and backend agents use `codex`, so normal
demo execution continued to default to Codex even after the minimal
`ClaudeCodeAdapter` was available.

### What Changed

Added an environment/config switch:

```bash
AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code
```

When set, frontend/backend coding agents whose stored adapter is `codex` create
new TaskRuns with `adapterType: claude_code`. When unset, behavior is unchanged.
Explicit adapter choices still win, so forced Codex failure and
retry-with-ScriptedMockAdapter fallback keep working as before. Non-code
adapters, including `scripted_mock`, are not changed by the env var.

No frontend UI selector, provider marketplace, seed rewrite, Codex removal, or
ScriptedMockAdapter behavior change was added.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (137 tests: 25 web + 112 API) |
| `git diff --check` | Pass |

### Known Limitations

- P2-8 did not run another real Claude mutation; P2-7 remains the real Claude
  smoke evidence.
- The selection method is environment-based. A browser-visible provider picker
  remains out of scope.

---

## P2-9: Claude Default Adapter Mode Documentation

**Date:** 2026-05-18

### Modified Files

| File | Change |
|---|---|
| `docs/demo-script.md` | Documented how to start the API with Claude Code as the default coding adapter and how to present the mode during demos. |
| `docs/project-state.md` | Recorded P2-9 Direct Start selection evidence and remaining limits. |
| `docs/change-log.md` | Recorded this P2-9 documentation and rehearsal result. |

No app code, adapter code, backend API behavior, frontend UI, provider
marketplace, or test behavior changed for P2-9.

### Diagnosis

P2-8 added the selection mechanism, but the demo script did not yet tell future
operators how to start AgentHub in Claude-default mode. Browser Direct Start
with `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code` also had not been manually
rehearsed.

### What Changed

The demo script now documents:

```bash
AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code pnpm dev:api
```

It also distinguishes the verified levels:

- P2-7 verified a direct backend real Claude mutation and diff artifact.
- P2-8 verified env-based selection in tests.
- P2-9 verified Direct Start creates a `claude_code` TaskRun when the env var
  is set.
- Full browser UI Claude-default execution through diff/preview/deploy remains
  unrehearsed.

### Minimal Rehearsal

Ran an in-memory API Direct Start check with
`AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code`. The request did not launch real
Claude; it verified the selection layer only.

Evidence:

- Endpoint: `POST /tasks/{task_id}/runs`
- Response status: `201`
- Session: `1c662ede-d0be-4349-8c86-20f49be6fb53`
- Task: `c28cda5b-67c7-44a8-bd2b-e43ebbc64217`
- TaskRun: `a1c191ea-1414-4746-95ca-d6c51b36b4f8`
- Adapter type: `claude_code`
- State: `queued`
- Queued event payload: `{"adapterType":"claude_code","state":"queued"}`

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (137 tests: 25 web + 112 API) |
| `git diff --check` | Pass |

### Known Limitations

- No real Claude execution was run for P2-9.
- Full browser UI Claude-default execution through diff/preview/deploy remains
  unrehearsed.
- P2-7 remains the real Claude mutation and diff artifact evidence.

---

## P2 Final Freeze Review

**Date:** 2026-05-18

### Modified Files

| File | Change |
|---|---|
| `docs/demo-script.md` | Updated the introduction to include P2 stabilization and Claude-default mode notes. |
| `docs/p2-roadmap.md` | Reconciled the original P2 plan with the final completed P2 state and remaining caveats. |
| `docs/project-state.md` | Recorded the P2 final freeze review result. |
| `docs/change-log.md` | Recorded this freeze review. |

No app code, adapter code, backend API behavior, frontend behavior, tests, or
dependencies changed during the P2 final freeze review.

### Review Result

The reviewed docs are aligned on the current P2 state:

- P2 stabilization work is complete through P2-9.
- P1 real Codex Direct Start and fallback-based P0 paths remain preserved.
- Claude default mode is documented with
  `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code`.
- Remaining caveats are visible:
  - full browser UI Claude-default execution through diff/preview/deploy is
    unrehearsed
  - real Claude auth-failure and usage-limit outputs remain partially
    unverified
  - broad arbitrary natural-language editing remains out of scope
  - production deploy remains out of scope

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (137 tests: 25 web + 112 API) |
| `git diff --check` | Pass |

---

## P2-3: Natural-Language Second-Change Orchestration

**Date:** 2026-05-17

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/planning.py` | Added deterministic follow-up intent parsing and one-task frontend follow-up planning. |
| `apps/api/app/main.py` | Added bounded follow-up task instructions for primary button and demo heading text changes. |
| `apps/api/app/scripted_mock.py` | Extended the fallback adapter to apply deterministic button and heading text updates. |
| `apps/api/tests/test_planning.py` | Added follow-up parsing and planning coverage. |
| `apps/api/tests/test_task_runs.py` | Added task-run instruction coverage for follow-up button and heading changes. |
| `apps/api/tests/test_scripted_mock_adapter.py` | Added fallback mutation and second-diff continuity coverage. |
| `docs/project-state.md` | Recorded P2-3 verified state and rehearsal evidence. |
| `docs/change-log.md` | Recorded this P2-3 implementation. |

### Root Cause

Before P2-3, planning only recognized the initial
`@orchestrator build a login page for the demo app` flow. Later messages in the
same session, such as `把按钮文案改成 Sign in`, did not create a focused
follow-up task. The fallback adapter also used fixed copy for its button-update
path, so it could not deterministically apply the requested second-change text.

### What Changed

P2-3 adds a small rule/template layer for demo-safe follow-up text changes:

- primary button text changes, including English and Chinese phrasing
- demo heading/title text changes, including English and Chinese phrasing

When an existing session already has tasks, a supported follow-up request
creates one frontend task assigned to the seeded frontend agent. The task
depends on the latest existing task, keeps `planJson` bounded to
`apps/demo/src/App.tsx`, and reuses the existing session worktree through the
normal TaskRun lifecycle.

No general autonomous planner, arbitrary natural-language editing, new adapter,
preview/deploy redesign, frontend redesign, or provider work was added.

### Manual Verification

Used the local API with an isolated rehearsal session:

- Session: `d65fc331-39f2-432b-9828-89723b9f3c32`
- Initial frontend task: `3f7f6f65-9f72-4add-ab0a-c9a944dc3b23`
- Initial fallback TaskRun: `607ad185-8eb2-4158-8219-e124880e68a7`
- Initial diff artifact: `c83c21d5-dad8-4d56-b0b8-cf1bc9de2bc3`
- Initial preview: `511ee0ca-e0dc-4054-8775-e487e81f7303`
- Follow-up request: `把按钮文案改成 Sign in`
- Follow-up task: `3ce6aa3d-97bf-4e16-b85a-33676e62bef2`
- Follow-up fallback TaskRun: `7a4f5763-ebbe-4d51-a207-b36b1fff7091`
- Follow-up diff artifact: `f1ca4318-0b41-48a8-9b27-acb957448734`
- Follow-up preview: `551aa58f-ab73-49f3-96c2-e6db8994bdd6`
- Follow-up preview health: `healthy`

The follow-up task reused the same session worktree, produced a second diff for
`apps/demo/src/App.tsx`, and the refreshed preview became healthy. Execution was
verified with `ScriptedMockAdapter` fallback rather than real Codex to avoid
quota dependency during this task.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (123 tests: 25 web + 98 API) |
| `git diff --check` | Pass |

### Known Limitations

- P2-3 intentionally supports only narrow button/title text-change requests.
- Real Codex execution of the follow-up task was not rehearsed in this task.
- Browser iframe refresh after the second change was not separately rehearsed;
  preview refresh was verified through the backend preview API.

---

## P2-4: Verify Browser Preview Iframe Refresh After Second Change

**Date:** 2026-05-17

### Modified Files

| File | Change |
|---|---|
| `docs/project-state.md` | Recorded P2-4 browser rehearsal evidence and current limitations. |
| `docs/demo-script.md` | Replaced the stale second-change caveat with the verified narrow follow-up flow. |
| `docs/change-log.md` | Recorded this P2-4 verification result. |

No app code, backend code, frontend code, adapter code, tests, or dependencies
changed for P2-4.

### Diagnosis

The preview refresh path already had the needed UI behavior:

- `Start preview` creates a new backend preview for the selected TaskRun and
  sets that preview as the right-side panel iframe.
- `Open preview` selects a persisted preview card for the right-side panel.
- `Refresh preview` re-reads persisted preview state for the selected TaskRun
  and bumps the iframe key when the selected preview belongs to that run.

The remaining P2-3 gap was verification, not missing product code. Persisted
preview cards from earlier sessions can outlive their local Vite processes, so
P2-4 used fresh `Start preview` actions during the browser rehearsal.

### Manual Verification

Verified through browser UI interaction:

```text
initial task -> ScriptedMockAdapter fallback -> first diff -> Start preview -> iframe at first preview URL -> follow-up text change -> ScriptedMockAdapter fallback -> second diff -> Start preview -> iframe refreshed to second preview URL
```

Evidence:

- Session: `cb653482-c31a-48da-a8ee-31ed8cd367e3`
- Initial frontend task: `5f2c26c2-6511-4b8f-b359-b9de5c9e5a50`
- Initial fallback TaskRun: `cfeff131-8cbf-4bcc-95b9-1aa84dbf5130`
- Initial diff artifact: `737085ee-7b73-4715-8303-df64b3a14132`
- Initial preview: `c077ba2d-7bd4-4c49-8e0c-313e2ecd641c`
- Initial preview URL: `http://127.0.0.1:61087`
- Follow-up request: `把按钮文案改成 Sign in`
- Follow-up task: `0f9ff26c-8216-4489-b71a-3628c1a7ab7a`
- Follow-up fallback TaskRun: `f8d78651-5347-43de-8553-12b29c8c3647`
- Follow-up diff artifact: `b48b3b33-feb2-4313-805d-89811a5cb51c`
- Follow-up preview: `44ea9495-04b5-419a-ba64-0701eaa83ec8`
- Follow-up preview URL: `http://127.0.0.1:61292`

The right-side preview panel iframe changed from `http://127.0.0.1:61087` to
`http://127.0.0.1:61292`. The follow-up preview was healthy, and the same URL
opened as a top-level page showed the updated `Sign in` button. Direct DOM
inspection inside the cross-origin iframe is not supported by the current
in-app browser runtime, so iframe content was verified visually and through the
top-level preview URL.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (123 tests: 25 web + 98 API) |
| `git diff --check` | Pass |

### Known Limitations

- Real Codex was not used for P2-4 execution; the browser rehearsal used the
  reliable forced-failure plus `ScriptedMockAdapter` fallback path.
- Broad arbitrary natural-language editing remains out of scope.

---

## P2-5: Add GitHub Actions CI

**Date:** 2026-05-17

### Modified Files

| File | Change |
|---|---|
| `.github/workflows/ci.yml` | Added the pull request and push CI workflow. |
| `docs/project-state.md` | Recorded the P2-5 CI state. |
| `docs/change-log.md` | Recorded this P2-5 implementation. |

No app code, backend code, frontend code, adapter code, test behavior,
deployment, Docker, or production release workflow changed for P2-5.

### Diagnosis

Manual validation repeatedly uses:

```text
pnpm check
pnpm test
git diff --check
```

The API check and test scripts expect a repository-local Python virtualenv at
`.venv/bin/python`, so CI needs to create that virtualenv before invoking the
existing pnpm scripts.

### What Changed

Added one minimal GitHub Actions workflow that runs on `pull_request` and
`push`. It checks out the repo, installs pnpm 10.33.4, sets up Node.js 22 and
Python 3.11, installs JavaScript dependencies with `pnpm install
--frozen-lockfile`, installs API dependencies into `.venv`, then runs:

```text
pnpm check
pnpm test
git diff --check
```

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (123 tests: 25 web + 98 API) |
| `git diff --check` | Pass |

### Known Limitations

- The workflow has been validated locally by syntax inspection and the local
  validation commands below; it has not yet run on GitHub Actions.

---

## Claude Code Adapter Feasibility Notes

**Date:** 2026-05-17

### Modified Files

| File | Change |
|---|---|
| `docs/claude-code-adapter-notes.md` | Added local Claude Code CLI feasibility findings and future adapter design notes. |
| `docs/change-log.md` | Recorded this documentation-only investigation. |

No app code, backend behavior, frontend behavior, adapter implementation, test
behavior, or runtime configuration changed.

### What Was Inspected

Adapter architecture:

- `apps/api/app/adapters.py`
- `apps/api/app/codex_adapter.py`
- `apps/api/app/scripted_mock.py`
- `apps/api/app/main.py`

Safe Claude CLI commands:

```bash
which claude
claude --version
claude --help
claude -p --help
claude auth --help
claude auth status
```

No real prompt execution or file mutation was run.

### Result

Claude Code CLI is installed and authenticated on this machine:

- Binary: `/Users/luotianhang/.npm-global/bin/claude`
- Version: `2.1.143 (Claude Code)`
- Auth status: `loggedIn: true`, `authMethod: api_key_helper`

Help output indicates non-interactive execution is available with
`--print`/`-p`, machine-readable output is available with
`--output-format json` or `--output-format stream-json`, and instructions can
be passed as a positional prompt. No direct `--cd` option was observed, so a
future adapter should set subprocess `cwd` to `Session.worktreePath`.

Tentative future command shape:

```bash
claude --print --output-format stream-json --include-partial-messages \
  --permission-mode dontAsk --allowedTools "Read,Edit,MultiEdit" \
  --no-session-persistence --max-budget-usd <small-budget> "<instruction>"
```

Run with subprocess `cwd=<session_worktree_path>`.

### Validation

| Command | Result |
|---|---|
| `git diff --check` | Pass |

### Known Limitations

- Real `stream-json` output was not captured.
- No quota-consuming command was run.
- Usage-limit and unauthenticated failure patterns still need real/fake-process
  test coverage before implementation.
- Permission mode and tool allowlist behavior need a bounded smoke before any
  write-capable adapter claim.

---

## P2 Roadmap Planning

**Date:** 2026-05-17

### Modified Files

| File | Change |
|---|---|
| `docs/p2-roadmap.md` | Added the P2 stabilization roadmap. |
| `docs/change-log.md` | Recorded this documentation-only planning change. |

No app code, backend code, frontend code, adapter code, tests, or dependencies
changed.

### What Changed

Created a P2 scope plan focused on stabilization, known caveats, and demo
reliability after the P1 freeze. The roadmap captures:

- the current P1 final verified state
- remaining P1 caveats
- immediate P2 task order
- objective, scope, affected modules, acceptance criteria, validation method,
  and non-goals for each proposed task
- frontend redesign as explicitly deferred

### Proposed P2 Task Order

1. P2-1 fix locale hydration warning.
2. P2-2 approval card UI/rehearsal.
3. P2-3 natural-language second-change orchestration.
4. P2-4 GitHub Actions CI.
5. P2-5 demo reset / clean-state helper.

### Validation

| Command | Result |
|---|---|
| `git diff --check` | Pass |

---

## P2-1: Fix Locale-Specific Hydration Warning

**Date:** 2026-05-17

### Modified Files

| File | Change |
|---|---|
| `apps/web/src/lib/date-format.ts` | Added deterministic compact timestamp formatting from ISO-like timestamp text. |
| `apps/web/src/lib/date-format.test.ts` | Added unit coverage for locale-independent formatting. |
| `apps/web/src/components/workspace-shell.tsx` | Replaced runtime-locale session timestamp formatting with deterministic formatting. |
| `apps/web/src/components/preview-card.tsx` | Replaced runtime-locale preview checked-time formatting with deterministic formatting. |
| `apps/web/src/components/preview-card.test.tsx` | Updated preview timestamp assertion to the deterministic text. |
| `docs/change-log.md` | Recorded this P2-1 implementation. |

### Root Cause

`workspace-shell.tsx` and `preview-card.tsx` used
`new Intl.DateTimeFormat(undefined, ...)`, which selects the current runtime
locale. During development SSR/hydration, the server rendered session dates in
one locale while the browser hydrated in another, producing a text mismatch such
as `May 17, 02:06 AM` versus `5月17日 02:06`.

### What Changed

P2-1 adds `formatCompactDateTime`, which formats ISO-like timestamps from their
source components instead of relying on runtime locale defaults. Session list,
selected-session metadata, and preview checked timestamps now render stable text
such as:

```text
May 17, 02:06
```

No backend APIs, task-run lifecycle behavior, preview/deploy logic, or frontend
layout were changed.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (92 tests: 24 web + 68 API) |
| `git diff --check` | Pass |

### Manual Verification

Opened and reloaded the AgentHub UI at `http://127.0.0.1:3000` against the
local API at `http://127.0.0.1:8000`. The session list, selected-session
metadata, backend health card, and preview panel rendered successfully, and the
previous locale-specific hydration overlay did not appear. Session timestamps
rendered as deterministic compact text such as `May 17, 02:06`.

### Known Limitations

- The formatter is intentionally compact and English-labeled for deterministic
  local demo rendering. This is not a full internationalization system.

---

## P2-2: Verify and Minimally Complete Approval Card UI/Rehearsal

**Date:** 2026-05-17

### Modified Files

| File | Change |
|---|---|
| `apps/api/app/schemas.py` | Added approval request/decision API schemas and exposed optional approval payloads on TaskRun responses. |
| `apps/api/app/main.py` | Added latest approval request mapping plus approve/deny TaskRun endpoints. |
| `apps/api/app/guardrails.py` | Fixed `git -C <path>` parsing for commands that contain no following subcommand, preserving allowlist behavior. |
| `apps/api/tests/test_task_runs.py` | Added API coverage for visible approval payloads and approve/deny endpoints. |
| `apps/api/tests/test_events.py` | Kept the new SSE event tests deterministic with real datetime values. |
| `apps/api/tests/test_guardrails.py` | Existing local guardrail edge-case tests now pass against the parser fix. |
| `apps/web/src/lib/api.ts` | Added approval request types and approve/deny API client helpers. |
| `apps/web/src/lib/api.test.ts` | Added API client coverage for approve/deny calls. |
| `apps/web/src/components/task-card-list.tsx` | Added a compact approval card for `waiting_approval` runs. |
| `apps/web/src/components/task-card-list.test.tsx` | Added approval card rendering and action coverage. |
| `apps/web/src/components/workspace-shell.tsx` | Wired approval actions through the existing task refresh flow. |
| `docs/project-state.md` | Recorded P2-2 verified state and rehearsal evidence. |
| `docs/change-log.md` | Recorded this P2-2 implementation. |

### Diagnosis

The backend already had the core P0 approval primitives:
`ApprovalRequestPayload`, `request_task_run_approval`, `approve_task_run`, and
`deny_task_run`. Adapter events could also transition a run to
`waiting_approval`. The product API did not expose the latest approval payload,
there were no public approve/deny endpoints, and the frontend treated
`waiting_approval` like a generic active run with only an interrupt control.

### What Changed

TaskRun API responses now include `approvalRequest` only while the run is in
`waiting_approval`. The frontend renders that payload as a small approval card
showing approval type, requested action, risk/reason, and command/path details
when present. Approve and Deny reuse the existing guardrail service methods and
refresh the selected task list.

No enterprise RBAC, policy admin, provider marketplace, production deploy
approval, frontend redesign, or new approval persistence entity was added.

### Manual Verification

Used an isolated local rehearsal session:

- Session: `67421999-3b16-44c4-ade3-98cb31331549`
- Approved TaskRun: `5653e8f9-0057-478f-913c-ac25b4484216`
- Denial rehearsal TaskRun: `54bde1de-b9f7-4f2b-9357-98d51b3675c7`

The browser UI rendered a `product_confirmation` approval card and the Approve
button moved that run from `waiting_approval` to `queued`. A
`security_approval` approval card rendered for the second run; backend/API tests
cover the denial transition and frontend tests cover the Deny button wiring.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (116 tests: 25 web + 91 API) |
| `git diff --check` | Pass |

### Known Limitations

- Approval resolution only updates the TaskRun state; it does not resume adapter
  execution automatically. This is sufficient for the current approval-card
  rehearsal and keeps scheduler/orchestrator behavior out of scope.
- The browser automation Deny click was not reliable during manual rehearsal,
  so denial is verified through backend/API tests and frontend button wiring
  tests rather than a full browser click.

### Known Limitations

- P1-8 reused the successful real Codex TaskRun from P1-6 instead of spending
  another Codex run.
- Browser UI verification covered the post-diff artifact controls. It did not
  re-run Codex from the browser during P1-8.
- Real Codex execution remains dependent on local Codex quota and CLI stability;
  keep the ScriptedMockAdapter fallback available for demos.

---

## P1-9: Demo Readiness and Reproducibility Check

**Date:** 2026-05-17

### Modified Files

| File | Change |
|---|---|
| `docs/demo-script.md` | Updated the main demo path to reflect the real browser UI Codex flow and moved the forced-failure path to a fallback demo path. |
| `docs/project-state.md` | Added P1-9 clean-start rehearsal status and evidence. |
| `docs/change-log.md` | Recorded this P1-9 result. |

### What Changed

Documentation was updated to match the current browser UI demo behavior:

- The main demo path now uses `Start run` on the frontend implementation task
  when local Codex is available.
- The forced Codex failure plus ScriptedMockAdapter path is still documented as
  the reliable fallback path.
- `docs/project-state.md` now records clean-start P1-9 evidence.

No product code, backend code, adapter code, preview/deploy services, or
dependencies changed for P1-9.

### Why

P1-8 proved the browser UI post-diff controls using an existing successful
Codex run. P1-9 verifies whether a fresh browser demo can reproduce the full
path from a clean backend/frontend start.

### Clean-Start Manual Verification Result

The backend and frontend were restarted using the documented commands:

```bash
pnpm dev:api
pnpm dev:web
```

The browser UI was opened at:

```text
http://127.0.0.1:3000
```

Clean-start flow:

1. Created a new session from the UI.
2. Sent `@orchestrator build a login page for the demo app`.
3. Clicked `Start run` on the frontend implementation task.
4. Observed the Codex run progress through active state.
5. Confirmed the run completed.
6. Confirmed the diff card appeared.
7. Clicked `Start preview`.
8. Confirmed a healthy Vite preview opened in the right-side iframe panel.
9. Clicked `Create deploy card`.
10. Reloaded the page and confirmed diff, preview, and deploy cards remained
    visible.

Evidence:

- Session: `666fa20b-6f54-4342-b844-39594b903da3`
- Task: `c90396af-1b9f-42f4-a6dd-9daa4f3913f6`
- TaskRun: `b1882cda-47f6-4035-b12d-ba3d72d67939`
- Adapter: `codex`
- Final TaskRun state: `completed`
- Error code/message: none
- Base ref: `ad9136f91fe9776c33e839359a2203d64fbbf322`
- Head ref: `ad9136f91fe9776c33e839359a2203d64fbbf322+worktree`
- Diff: `8a0155a6-b865-4cee-987e-82d773b9f20e`
- Diff artifact: `c832b249-c2c3-444c-ac97-6b3e811e5c70`
- Changed file: `apps/demo/src/App.tsx`
- Diff stats: 1 file changed, 14 additions, 4 deletions
- Preview: `b363eb09-7251-4b8e-a5b4-3c59775b58b7`
- Preview artifact: `f93ebc25-b8c7-47e9-ac11-aeee777c604e`
- Preview URL: `http://127.0.0.1:51763`
- Preview health/status: `healthy`, `ready`
- Deployment: `d97e447a-c8d0-41b7-95f8-e40008d83eb0`
- Deployment artifact: `d85e9bcf-9b92-4c3c-958a-352f855e59a9`
- Provider/environment/status: `mock`, `preview`, `ready`
- Deployment URL:
  `https://mock.agenthub.local/deployments/d97e447a-c8d0-41b7-95f8-e40008d83eb0`

This verifies:

```text
clean start -> real Codex Direct Start -> diff card -> Start preview -> preview iframe -> Create deploy card
```

### UI Readiness Notes

- Core labels are clear enough for a judge/demo scenario: `Start run`, run
  history, `Start preview`, `Open preview`, and `Create deploy card`.
- The visible active state is simple but adequate: the run appears as
  `queued`/`streaming` with an `Interrupt` control while Codex runs.
- If Codex is unavailable, unauthenticated, usage-limited, or too slow, the
  fallback-based P0 demo remains the safe path.

### Fallback Verification

The fallback path was not used during P1-9 because real Codex completed. The
fallback-based P0 demo remains covered by existing tests and prior
verification:

```text
forced Codex failure -> ScriptedMockAdapter fallback -> diff -> preview -> mock deploy
```

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (90 tests: 22 web + 68 API) |
| `git diff --check` | Pass |

### Known Limitations

- Real Codex execution remains dependent on local Codex quota and CLI stability.
- P1-9 did not reset the SQLite database or delete existing worktrees; it
  restarted backend/frontend processes and created a fresh session from the UI.

---

## P1-10: Demo Freeze and Final Acceptance Checklist

**Date:** 2026-05-17

### Modified Files

| File | Change |
|---|---|
| `docs/p1-acceptance-checklist.md` | Added the final frozen P1 acceptance checklist. |
| `docs/project-state.md` | Marked the P1 demo baseline as frozen and linked the checklist. |
| `docs/change-log.md` | Recorded this P1-10 freeze result. |

### What Changed

P1 is now documented as a frozen local demo baseline for:

```text
real Codex Direct Start -> diff card -> Start preview -> preview iframe -> Create deploy card
```

The new acceptance checklist captures completed capabilities, concrete evidence,
validation status, known unverified items, known risks, fallback-based P0
status, explicitly out-of-scope items, and recommended next phase.

No app code, backend code, adapter code, tests, preview/deploy services, or
dependencies changed for P1-10.

### Why

P1-9 proved the demo is reproducible from a clean backend/frontend start. P1-10
freezes that state so future work has a stable demo baseline and a clear record
of what is verified, what remains risky, and what stays out of scope.

### Frozen Baseline

Frozen P1 path:

```text
real Codex Direct Start -> diff card -> Start preview -> preview iframe -> Create deploy card
```

Frozen evidence comes from the P1-9 clean-start rehearsal:

- Session: `666fa20b-6f54-4342-b844-39594b903da3`
- TaskRun: `b1882cda-47f6-4035-b12d-ba3d72d67939`
- Diff artifact: `c832b249-c2c3-444c-ac97-6b3e811e5c70`
- Preview: `b363eb09-7251-4b8e-a5b4-3c59775b58b7`
- Deployment: `d97e447a-c8d0-41b7-95f8-e40008d83eb0`
- Provider/status: `mock`, `ready`

Fallback-based P0 path remains preserved:

```text
forced Codex failure -> ScriptedMockAdapter fallback -> real diff -> healthy Vite preview -> mock deploy card
```

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (90 tests: 22 web + 68 API) |
| `git diff --check` | Pass |

### Known Unverified Items

- P1-9 did not reset the SQLite database or delete existing worktrees.
- Fallback-based P0 was not manually re-run during P1-9 because real Codex
  completed; it remains covered by tests and prior verification.
- Natural-language second-change orchestration remains a documented caveat.
- Approval card UI was not part of the frozen P1 judge path.

### Known Risks

- Real Codex execution depends on local CLI availability, authentication,
  quota, and CLI stability.
- Codex run duration can vary, so the ScriptedMockAdapter fallback should
  remain ready for demos.
- Preview health depends on setup-time demo dependencies.

---

## P1-11: Clean-State and Fallback Rehearsal

**Date:** 2026-05-17

### Modified Files

| File | Change |
|---|---|
| `docs/project-state.md` | Recorded the clean SQLite rehearsal, fresh session worktree evidence, and fallback rehearsal evidence. |
| `docs/p1-acceptance-checklist.md` | Marked the clean-state and manual fallback readiness items verified. |
| `docs/change-log.md` | Recorded this P1-11 rehearsal result. |

No app code, backend code, frontend code, adapter code, tests, or dependencies
changed for P1-11.

### Backup / Reset Method

- Moved the active SQLite database to
  `/tmp/agenthub-p1-11-backup-20260517-095901/agenthub.sqlite3.before-p1-11`.
- Recorded the pre-rehearsal Git worktree registry and directory inventory at:
  - `/tmp/agenthub-p1-11-backup-20260517-095901/worktree-list-before.txt`
  - `/tmp/agenthub-p1-11-backup-20260517-095901/worktree-dirs-before.txt`
- Left existing `.worktrees` checkouts in place to avoid disturbing Git's
  registered worktree metadata.
- Reinitialized a clean SQLite database with `pnpm db:init`.
- Created fresh session-level worktrees through the UI during rehearsal.

### Clean-State Rehearsal

Verified path:

```text
clean SQLite -> fresh session worktree -> real Codex Direct Start -> real diff -> healthy Vite preview -> mock deploy card
```

Evidence:

- Session: `72668a90-74a0-45c6-a0c4-98e8cfa54c27`
- Task: `7e0a4e97-1b80-404d-bcab-4616418627e3`
- TaskRun: `4c92132f-3c89-47cc-b8a4-3f1395825c39`
- Diff: `bb45131e-42f8-47d7-88eb-c8126d694b0a`
- Diff artifact: `243ce682-748b-42ad-9354-dd8eed1f3e67`
- Preview: `a30d07e2-470c-4614-a864-c21ac0b52363`
- Preview URL: `http://127.0.0.1:58634`
- Deployment: `448b7d91-5064-43c2-a849-3e89634e14bd`
- Provider/status: `mock`, `ready`

### Fallback Rehearsal

Verified path:

```text
forced Codex failure -> ScriptedMockAdapter fallback -> real diff -> healthy Vite preview -> mock deploy card
```

Evidence:

- Session: `695287ed-2967-4360-8520-a5fdc1be46e3`
- Task: `1a790664-c817-42eb-a953-d7c0f11cccb0`
- Failed Codex TaskRun: `1b50d047-0c08-4ff2-a4d7-12412b36f786`
- Failed run error code: `CODEX_DEMO_FORCED_FAILURE`
- Fallback TaskRun: `c35d52f5-bf27-4656-aee1-b0321eb2bd96`
- Diff: `8a8f05bf-6559-44f4-bafc-fb87881c4750`
- Diff artifact: `91b6c898-bf2b-4c0c-b44b-f6a236a72ef0`
- Preview: `e1be7c11-1cc7-42f9-8441-62c7eb0a1b92`
- Preview URL: `http://127.0.0.1:59152`
- Deployment: `cb8c7f95-42f7-4213-8273-4201500bf8b3`
- Provider/status: `mock`, `ready`

The browser UI still showed the failed Codex run, fallback run, diff, preview,
and deploy card after reload.

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (90 tests: 22 web + 68 API) |
| `git diff --check` | Pass |

### Known Limitations

- Existing registered `.worktrees` checkouts were not moved or deleted. P1-11
  verified clean app state by backing up the SQLite database and creating new
  session-level worktrees from the clean DB.
- Real Codex execution still depends on local CLI availability, authentication,
  quota, and CLI stability.

---

## P1 Final Freeze Review

**Date:** 2026-05-17

### Modified Files

| File | Change |
|---|---|
| `README.md` | Updated the stale P0 direct-start caveat to the verified P1 direct Codex state and added P1 reset/restore notes. |
| `docs/demo-script.md` | Added P1-11 restore details and the non-blocking locale hydration warning caveat. |
| `docs/project-state.md` | Added restore note and final freeze review summary. |
| `docs/p1-acceptance-checklist.md` | Added final freeze review validation slot and locale hydration warning caveat. |
| `docs/change-log.md` | Recorded this freeze review. |

No app code, backend code, frontend code, adapter code, tests, or dependencies
changed for the final freeze review.

### What Changed

The review found one stale README caveat from the P0 freeze era: it still said
the `Start run` UI only creates a queued TaskRun and that the complete artifact
path is fallback-only. That is no longer true after P1. The README now matches
the P1 verified state:

```text
Start run -> real Codex Direct Start -> real diff -> healthy Vite preview -> mock deploy card
```

The docs now also explicitly state the P1-11 SQLite restore method and the
non-blocking locale-specific hydration warning observed during P1-11.

### Freeze Review Result

- P1-11 is committed at `faca556`.
- No tag currently points at P1-11 HEAD.
- P1 is ready to freeze once the validation below remains green.
- Remaining caveats are visible:
  - natural-language second-change orchestration remains a caveat
  - approval card UI is outside the frozen P1 judge path
  - production deploy is out of scope
  - locale-specific development hydration warning was observed but did not
    block rehearsal

### Validation

| Command | Result |
|---|---|
| `pnpm check` | Pass |
| `pnpm test` | Pass (90 tests: 22 web + 68 API) |
| `git diff --check` | Pass |
