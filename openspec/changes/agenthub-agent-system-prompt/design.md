# Design

Store optional systemPrompt in existing AgentRuntimeConfig.roles_json. Null/blank
inherits Agent.system_prompt; disabled role configuration does not apply overrides.
Limit overrides to 8000 characters and reject NUL before persistence.

Freeze the effective text, identity and SHA-256 in private TaskRun metrics at run
creation, after retry metadata. Public metrics expose only a receipt. Existing
queued legacy runs freeze at request preparation under the existing context CAS.
Configuration changes affect new runs; retries resolve current configuration.
Caller planContext cannot supply the effective prompt. Integrity/identity failures
fail closed. Prompts augment role behavior; existing target and safety instructions
and all execution permission checks remain mandatory.

LLM planning builds the effective orchestrator prompt into PlannerRequest, then
existing redaction and immutable prepared payload handling freeze provider inputs.
All four planner transports render it before the mandatory JSON contract and
guardrails. Deterministic and scripted paths do not claim model prompt obedience.

The runtime UI edits each enabled role, preserves text across provider changes,
supports save/cancel, and explains inheritance, future-run behavior and limits.
