# Close planned demo reviews and unblock subsequent chat changes

## Why
Generated advisory Review artifacts satisfy contract/LLM review tasks, but the
same mechanism omits deterministic login and dynamic frontend plans. Their QA
tasks stay pending and block the next ordinary chat message.

## What Changes
- Include deterministic_login_v1 and dynamic_manager_v1 in planned review closure.
- Require latest completed dependency runs with matching same-Session Diff/Review
  artifacts; persist source references and report verdict without creating a QA run.
- Reconcile valid persisted reports before planning a new user chat message so
  existing pending QA tasks can recover without rewriting completed executions.
- Preserve explicit review runs and advisory/non-blocking verdict semantics.
- Start waiting dynamic autoStart tasks once dependencies close; suppress ORM
  autoflush during finalizer validation reads without weakening its ownership checks.
- Verify two ordinary HTTP messages, actual dispatcher/adapter execution and
  report lineage, plus missing/stale/mismatched evidence negative controls.

## Impact
One review dependency repair. No new adapter, UI, schema, provider, dependency,
Preview/deployment automation, or changes to write/scope/completion permissions.
