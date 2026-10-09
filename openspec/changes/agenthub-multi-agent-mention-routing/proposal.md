# Route every explicitly mentioned execution Agent

Mention parsing currently recognizes multiple Agents, but planning dispatches only
the first role. This silently loses user assignments and makes group mode misleading.
Add a bounded deterministic coordinator for explicitly selected coding/review roles,
using the existing Task, scheduler, target registry and TaskRun execution paths.

## Impact
Atomic group planning, explicit target/profile lineage and group contact selection.
No new adapter, database table, permission, dependency or multi-user feature.
Custom Planner-led group decomposition is outside this focused change: requests
selecting a custom Planner with execution participants must fail explicitly instead
of silently substituting the deterministic coordinator.
