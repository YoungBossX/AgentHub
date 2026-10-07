# Memory rule layers and bounded context

## Why
Frozen memory snapshots now preserve request inputs, but keyword retrieval can omit applicable project rules and the five-item limit does not bound memory size. Missing target/role filters can also admit restricted memories.

## What Changes
- Include active, system/user-confirmed project rules without requiring a keyword match; select confirmed active preferences next and relevant experience last.
- Apply exact workspace and known target/role boundaries before selecting any layer. Restricted items require an explicit matching context; unknown context does not mean all targets/roles.
- Bound the complete serialized memory array, including metadata, using a deterministic 16,000-character JSON budget. Preserve whole items; skip optional items that do not fit and reject requests if mandatory rules alone exceed the budget.
- Share the selection policy between Planner and coding requests, preserving frozen snapshot inputs and request receipts. Record layer/reason and budget/count evidence without exposing omitted content.
- Return an actionable, sanitized budget error before provider invocation; coding preparation failures retain existing execution fencing.

## Impact
One focused task with no new database entity, dependency, UI, tokenizer, embedding service, Skill/MCP, or permission changes. The budget bounds the serialized memory value, not the entire prompt or model token count. Snapshot v2 remains unchanged; selection policy is versioned separately. Active confirmed preferences are optional guidance; warm rules and external/untrusted items remain relevance-based experience.
