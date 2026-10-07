# Design

## Selection
Use the existing frozen candidates and as-of time. Filter workspace, status, explicit scope, target and role before ranking. Active project_rule items with trust_level system or user_confirmed form the mandatory rules layer. Active user_preference items with the same trust levels form an optional preference layer. Other eligible memories require a positive lexical score and form the experience layer.

Sort each layer deterministically by importance/identity for rules and preferences, and existing score/time/identity for experience. The existing limit controls selected experience only; mandatory rules do not compete for its slots. Unknown target or role excludes memories carrying that restriction. No target is inferred from untrusted message text.

The current MemoryItem schema has no Session owner. Session-scoped items are therefore excluded rather than widened into workspace rules; target-scoped items require target IDs. User-scoped items remain workspace-bound within the existing single-user baseline. Adding persistent Session ownership is a separate task.

## Budget
Measure json.dumps(selected context items, ensure_ascii=True, sort_keys=True, indent=2), including item identity, content, scores, ranks, and selection metadata. The default is 16,000 serialized characters, reproducible without a provider-specific tokenizer. It is not a limit on the full canonical envelope or model tokens. Mandatory rules are indivisible. Overflow raises MEMORY_CONTEXT_BUDGET_EXCEEDED; optional items that cannot fit are skipped whole, and later smaller items may still fit.

## Evidence and compatibility
Keep relevantMemories as an array and the existing contentHash as the original frozen item hash. Add layer and selectionReason to selected items, and a bounded memorySelection object carrying policy version, budget unit/limit/used, layer counts and omitted optional counts. Carry selection evidence through canonical shared context and the prepared-request receipt. Existing secret/path filtering still determines provider visibility. The receipt remains prepared-request evidence only.

Planner API budget failure is HTTP 422 with fixed actionable text; no rule content appears in errors. Coding request preparation persists a failure through the existing supervisor and durable ownership checks, before adapter.createRun. Legacy unavailable snapshots remain empty. Live changes cannot alter a bound snapshot. No migration or live database initialization is needed.
